"""Generate bulk pacs.008 input cases: many messages that vary several fields at once.

Usage:  python tools/generate_bulk_inputs.py [--count N] [--seed S]

Each message starts from the valid baseline (sample/inputs/pacs008/p8_01_valid.xml) and takes one value
from every dimension in DIMENSIONS. The cases are chosen in two steps:

1. Pairwise coverage: every pair of values from any two dimensions appears together in at least one case.
   Most interaction bugs need only two fields to line up, so this finds them with a few dozen cases
   instead of the millions a full cross product would need.
2. Random fill: seeded random combinations top the set up to --count, to catch three-way interactions.

The cases have no expected result. Both test suites only record what the code returned, and DiffLens
flags every case where legacy and new gen disagree (differential testing). The output is deterministic
for a given --count and --seed, so reruns produce the same files.

Writes sample/inputs/pacs008/bulk/B0001.xml ... and sample/inputs/pacs008_bulk.csv.
"""

from __future__ import annotations

import argparse
import csv
import random
import shutil
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUTS = ROOT / "sample" / "inputs"
BASELINE = INPUTS / "pacs008" / "p8_01_valid.xml"
OUT_DIR = INPUTS / "pacs008" / "bulk"
OUT_CSV = INPUTS / "pacs008_bulk.csv"

CHARGE = ('<ChrgsInf><Amt Ccy="EUR">5.00</Amt>'
          '<Agt><FinInstnId><BICFI>BANKDEFFXXX</BICFI></FinInstnId></Agt></ChrgsInf>')
CDTR = "<Cdtr><Nm>Globex SA</Nm><PstlAdr><TwnNm>Paris</TwnNm><Ctry>FR</Ctry></PstlAdr></Cdtr>"
DBTR_NAME = "<Nm>Acme GmbH</Nm>"
ANY_BIC = "<Id><OrgId><AnyBIC>ACMEDEFFXXX</AnyBIC></OrgId></Id>"
RMT = "<RmtInf><Ustrd>Invoice 2026-001</Ustrd></RmtInf>"
UETR = "8a562c67-ca16-48ba-b074-65581be6f001"


def sub(old: str, new: str) -> list[tuple[str, str]]:
    return [(old, new)]


# Dimension -> {value label: text replacements on the baseline}. The first value of each dimension is the
# baseline (no change). Dimensions are applied in this order, so a later one sees earlier changes (the
# BIC dimension also rewrites the charge agent added by the charges dimension).
DIMENSIONS: dict[str, dict[str, list[tuple[str, str]]]] = {
    "currency": {
        "EUR": [],
        "USD": sub('IntrBkSttlmAmt Ccy="EUR"', 'IntrBkSttlmAmt Ccy="USD"'),
        "JPY": sub('IntrBkSttlmAmt Ccy="EUR"', 'IntrBkSttlmAmt Ccy="JPY"'),
        "XAU commodity": sub('IntrBkSttlmAmt Ccy="EUR"', 'IntrBkSttlmAmt Ccy="XAU"'),
        "lowercase eur": sub('IntrBkSttlmAmt Ccy="EUR"', 'IntrBkSttlmAmt Ccy="eur"'),
    },
    "amount": {
        "1000.00": [],
        "0.01": sub(">1000.00</IntrBkSttlmAmt>", ">0.01</IntrBkSttlmAmt>"),
        "0.00": sub(">1000.00</IntrBkSttlmAmt>", ">0.00</IntrBkSttlmAmt>"),
        "-5.00": sub(">1000.00</IntrBkSttlmAmt>", ">-5.00</IntrBkSttlmAmt>"),
        "5 decimals": sub(">1000.00</IntrBkSttlmAmt>", ">12.34567</IntrBkSttlmAmt>"),
        "6 decimals": sub(">1000.00</IntrBkSttlmAmt>", ">1.000001</IntrBkSttlmAmt>"),
        "14 digits": sub(">1000.00</IntrBkSttlmAmt>", ">999999999.99999</IntrBkSttlmAmt>"),
        "15 digits": sub(">1000.00</IntrBkSttlmAmt>", ">9999999999.99999</IntrBkSttlmAmt>"),
    },
    "instrId": {
        "10 chars": [],
        "16 chars": sub("<InstrId>INSTR-0001</InstrId>", "<InstrId>INSTR-0001-ABCDE</InstrId>"),
        "17 chars": sub("<InstrId>INSTR-0001</InstrId>", "<InstrId>INSTR-0001-ABCDEF</InstrId>"),
        "35 chars": sub("<InstrId>INSTR-0001</InstrId>", "<InstrId>" + "I" * 35 + "</InstrId>"),
        "slashes": sub("<InstrId>INSTR-0001</InstrId>", "<InstrId>/INS//03</InstrId>"),
        "trailing slash": sub("<InstrId>INSTR-0001</InstrId>", "<InstrId>INSTR-0001/</InstrId>"),
    },
    "settlement": {
        "INDA": [],
        "INGA": sub("<SttlmMtd>INDA</SttlmMtd>", "<SttlmMtd>INGA</SttlmMtd>"),
        "CLRG": sub("<SttlmMtd>INDA</SttlmMtd>", "<SttlmMtd>CLRG</SttlmMtd>"),
    },
    "charges": {
        "SHAR": [],
        "SLEV": sub("<ChrgBr>SHAR</ChrgBr>", "<ChrgBr>SLEV</ChrgBr>"),
        "DEBT no charge": sub("<ChrgBr>SHAR</ChrgBr>", "<ChrgBr>DEBT</ChrgBr>"),
        "DEBT 1 charge": sub("<ChrgBr>SHAR</ChrgBr>", "<ChrgBr>DEBT</ChrgBr>" + CHARGE),
        "DEBT 2 charges": sub("<ChrgBr>SHAR</ChrgBr>", "<ChrgBr>DEBT</ChrgBr>" + CHARGE + CHARGE),
        "CRED no charge": sub("<ChrgBr>SHAR</ChrgBr>", "<ChrgBr>CRED</ChrgBr>"),
        "CRED 1 charge": sub("<ChrgBr>SHAR</ChrgBr>", "<ChrgBr>CRED</ChrgBr>" + CHARGE),
    },
    "bic": {
        "BIC11": [],
        "BIC8": sub("BANKDEFFXXX", "BANKDEFF"),
        "lowercase BIC": sub("CEDELULLXXX", "cedelullxxx"),
    },
    "debtor": {
        "name": [],
        "AnyBIC only": sub(DBTR_NAME, ANY_BIC),
        "name and AnyBIC": sub(DBTR_NAME, DBTR_NAME + ANY_BIC),
        "no name or BIC": sub(DBTR_NAME, ""),
    },
    "creditor address": {
        "town and country": [],
        "full structured": sub(CDTR, "<Cdtr><Nm>Globex SA</Nm><PstlAdr><StrtNm>Rue de Rivoli</StrtNm><BldgNb>12"
                                     "</BldgNb><PstCd>75001</PstCd><TwnNm>Paris</TwnNm><Ctry>FR</Ctry></PstlAdr></Cdtr>"),
        "address lines only": sub(CDTR, "<Cdtr><Nm>Globex SA</Nm><PstlAdr><AdrLine>12 Rue de Rivoli</AdrLine>"
                                        "<AdrLine>75001 Paris France</AdrLine></PstlAdr></Cdtr>"),
        "hybrid": sub(CDTR, "<Cdtr><Nm>Globex SA</Nm><PstlAdr><TwnNm>Paris</TwnNm><Ctry>FR</Ctry>"
                            "<AdrLine>12 Rue de Rivoli</AdrLine></PstlAdr></Cdtr>"),
        "no town": sub(CDTR, "<Cdtr><Nm>Globex SA</Nm><PstlAdr><Ctry>FR</Ctry></PstlAdr></Cdtr>"),
    },
    "remittance": {
        "short": [],
        "none": sub(RMT, ""),
        "140 chars": sub(RMT, "<RmtInf><Ustrd>" + "R" * 140 + "</Ustrd></RmtInf>"),
        "141 chars": sub(RMT, "<RmtInf><Ustrd>" + "R" * 141 + "</Ustrd></RmtInf>"),
        "structured and related": sub(RMT, RMT + "<RltdRmtInf><RmtId>REM-0001</RmtId></RltdRmtInf>"),
    },
    "uetr": {
        "valid v4": [],
        "uppercase": sub(UETR, UETR.upper()),
        "version 1": sub(UETR, "8a562c67-ca16-18ba-b074-65581be6f001"),
        "not a UUID": sub(UETR, "not-a-valid-uetr"),
    },
}


def pairwise(sizes: list[int], rng: random.Random, candidates: int = 30) -> list[tuple[int, ...]]:
    """Greedy all-pairs covering set (AETG-style): each case covers as many uncovered pairs as possible."""
    uncovered = {(i, a, j, b) for i, j in combinations(range(len(sizes)), 2)
                 for a in range(sizes[i]) for b in range(sizes[j])}
    cases: list[tuple[int, ...]] = []
    while uncovered:
        best, best_gain = None, -1
        seed_pair = min(uncovered)  # deterministic start: always cover at least this pair
        for _ in range(candidates):
            case: list[int | None] = [None] * len(sizes)
            i, a, j, b = seed_pair
            case[i], case[j] = a, b
            for d in rng.sample(range(len(sizes)), len(sizes)):
                if case[d] is not None:
                    continue
                gains = [sum((min(d, e), v if d < e else case[e], max(d, e), case[e] if d < e else v) in uncovered
                             for e in range(len(sizes)) if case[e] is not None) for v in range(sizes[d])]
                top = max(gains)
                case[d] = rng.choice([v for v, g in enumerate(gains) if g == top])
            gain = sum((i, case[i], j, case[j]) in uncovered for i, j in combinations(range(len(sizes)), 2))
            if gain > best_gain:
                best, best_gain = tuple(case), gain
        cases.append(best)
        uncovered -= {(i, best[i], j, best[j]) for i, j in combinations(range(len(sizes)), 2)}
    return cases


def build(choice: tuple[int, ...], template: str) -> tuple[str, str]:
    """Message text and a short description of its non-baseline values."""
    xml, parts = template, []
    for (dim, values), index in zip(DIMENSIONS.items(), choice):
        label, replacements = list(values.items())[index]
        for old, new in replacements:
            if old not in xml:
                raise ValueError(f"{dim}={label}: '{old}' not found in the message")
            xml = xml.replace(old, new)
        if index:
            parts.append(f"{dim} {label}")
    return xml, " · ".join(parts) or "baseline values"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--count", type=int, default=500, help="total number of cases (at least the pairwise set)")
    parser.add_argument("--seed", type=int, default=2026, help="random seed, for reproducible output")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    sizes = [len(values) for values in DIMENSIONS.values()]
    chosen = pairwise(sizes, rng)
    pair_count = len(chosen)
    seen = set(chosen)
    while len(chosen) < args.count:
        case = tuple(rng.randrange(n) for n in sizes)
        if case not in seen:
            seen.add(case)
            chosen.append(case)

    template = BASELINE.read_text(encoding="utf-8")
    shutil.rmtree(OUT_DIR, ignore_errors=True)
    OUT_DIR.mkdir(parents=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["case", "files", "expected", "description"])
        for n, choice in enumerate(chosen, 1):
            xml, description = build(choice, template)
            name = f"B{n:04d}.xml"
            (OUT_DIR / name).write_text(xml, encoding="utf-8", newline="\n")
            source = "pairwise" if n <= pair_count else "random"
            # Expected is left empty (null): the case is compared between legacy and new gen, not asserted.
            writer.writerow([f"B-{n:04d}", f"bulk/{name}", "", f"{source}: {description}"])

    full = 1
    for n in sizes:
        full *= n
    print(f"{len(chosen)} cases ({pair_count} pairwise + {len(chosen) - pair_count} random) out of "
          f"{full:,} possible combinations -> {OUT_CSV.relative_to(ROOT)}, {OUT_DIR.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
