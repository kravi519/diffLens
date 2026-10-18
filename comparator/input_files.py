"""Read the shared input files (CSV cases and pacs.008 XML messages) into readable form for the UI."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

COLUMN_LABELS = {"case": "Case", "expected": "Expected", "description": "Edge case", "files": "Messages"}

# ISO 20022 tag -> plain name. Unknown tags are shown as they are.
XML_LABELS = {
    "AppHdr": "Business application header", "GrpHdr": "Group header", "CdtTrfTxInf": "Credit transfer",
    "Fr": "From", "To": "To", "BizMsgIdr": "Business message ID", "MsgDefIdr": "Message definition",
    "BizSvc": "Business service", "CreDt": "Created", "CreDtTm": "Created", "MsgId": "Message ID",
    "NbOfTxs": "Number of transactions", "SttlmInf": "Settlement", "SttlmMtd": "Method",
    "SttlmAcct": "Settlement account", "PmtId": "Payment ID", "InstrId": "Instruction ID",
    "EndToEndId": "End-to-end ID", "UETR": "UETR", "IntrBkSttlmAmt": "Interbank settlement amount",
    "IntrBkSttlmDt": "Interbank settlement date", "ChrgBr": "Charge bearer", "ChrgsInf": "Charges",
    "Amt": "Amount", "Agt": "Agent", "InstgAgt": "Instructing agent", "InstdAgt": "Instructed agent",
    "Dbtr": "Debtor", "DbtrAcct": "Debtor account", "DbtrAgt": "Debtor agent", "Cdtr": "Creditor",
    "CdtrAcct": "Creditor account", "CdtrAgt": "Creditor agent", "Nm": "Name", "PstlAdr": "Postal address",
    "StrtNm": "Street", "BldgNb": "Building number", "PstCd": "Post code", "TwnNm": "Town", "Ctry": "Country",
    "AdrLine": "Address line", "IBAN": "IBAN", "BICFI": "BIC", "AnyBIC": "BIC", "OrgId": "Organisation ID",
    "RmtInf": "Remittance", "Ustrd": "Unstructured", "RltdRmtInf": "Related remittance", "RmtId": "Remittance ID",
    "Ccy": "Currency",
}
# Wrapper elements that add nesting but no meaning; their children are shown one level up.
XML_WRAPPERS = {"BusMsg", "Document", "FIToFICstmrCdtTrf", "FICdtTrf", "FinInstnId", "FIId", "Id", "Othr"}


def split_csv_line(line: str) -> list[str | None]:
    """Split one line like JUnit's @CsvFileSource: unquoted empty -> null, quoted "" -> empty string."""
    fields: list[str | None] = []
    buf: list[str] = []
    quoted = in_quotes = False
    i = 0
    while i < len(line):
        ch = line[i]
        if in_quotes:
            if ch == '"' and i + 1 < len(line) and line[i + 1] == '"':
                buf.append('"')
                i += 1
            elif ch == '"':
                in_quotes = False
            else:
                buf.append(ch)
        elif ch == '"':
            in_quotes = quoted = True
        elif ch == ",":
            fields.append(_field(buf, quoted))
            buf, quoted = [], False
        else:
            buf.append(ch)
        i += 1
    fields.append(_field(buf, quoted))
    return fields


def _field(buf: list[str], quoted: bool) -> str | None:
    text = "".join(buf)
    if quoted:
        return text
    text = text.strip()
    return text or None


def read_csv(path: Path) -> tuple[list[str], list[list[str | None]]]:
    """Header and rows of a JUnit CSV input file (blank lines skipped)."""
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [split_csv_line(line) for line in lines]
    return (rows[0], rows[1:]) if rows else ([], [])


def column_label(name: str) -> str:
    """CSV header to a sentence-case column title, e.g. firstName -> First name."""
    if name in COLUMN_LABELS:
        return COLUMN_LABELS[name]
    words = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name).lower()
    return words[:1].upper() + words[1:]


def show_value(value: str | None) -> str:
    """Make null, empty and padded values visible in a table."""
    if value is None:
        return "∅ null"
    if value == "" or value != value.strip():
        return f'"{value}"'
    return value


def xml_fields(text: str) -> list[tuple[str, str, str]]:
    """Flatten an XML message into (section, field, value) rows with plain names.

    Raises ET.ParseError for malformed XML. Entities are never resolved from outside the document, so a
    DOCTYPE with an external entity (XXE test case) fails to parse instead of reading a local file.
    """
    root = ET.fromstring(text)
    rows: list[tuple[tuple[str, int], str, str]] = []
    counts: dict[str, int] = {}

    def walk(el: ET.Element, section: tuple[str, int] | None, path: list[str]) -> None:
        tag = el.tag.split("}")[-1]
        name = XML_LABELS.get(tag, tag)
        if tag not in XML_WRAPPERS:
            if section is None:  # the first meaningful level below the wrappers is the section
                counts[name] = counts.get(name, 0) + 1
                section, path = (name, counts[name]), []
            else:
                path = path + [name]
        key = section or ("Message", 1)
        children = list(el)
        value = (el.text or "").strip()
        if value or (not children and not el.attrib):
            rows.append((key, " › ".join(path) or name, value))
        for attr, value in el.attrib.items():
            rows.append((key, " › ".join(path + [XML_LABELS.get(attr, attr)]), value))
        for child in children:
            walk(child, section, path)

    walk(root, None, [])
    # Number only the sections that repeat, e.g. "Credit transfer 1" and "Credit transfer 2".
    return [(f"{name} {i}" if counts.get(name, 1) > 1 else name, field, value)
            for (name, i), field, value in rows]
