# DiffLens

DiffLens runs a **legacy** Java code base and a **new-gen** Java code base on **the same input cases**, each
with **its own test suite**, then compares the results input by input in a Streamlit UI.

```
                        ┌──► legacy tests  ──► legacy code  ──► JUnit XML + outputs ─┐
   shared input cases ──┤                                                            │
   (sample/inputs/)     └──► new-gen tests ──► new-gen code ──► JUnit XML + outputs ─┤
                                                                                     ▼
              Streamlit UI ◄── comparison per input case (regression / fixed / output differs / same)
```

## Setup

1. Install **Python 3.10+** (python.org; tick "Add to PATH") and a **JDK** (`java`/`javac`).
2. Install dependencies:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate          # Windows  (source .venv/bin/activate on macOS/Linux)
   pip install -r requirements.txt
   ```
3. Run:
   ```bash
   streamlit run app.py
   ```

Click **▶️ Run tests** on the Comparison page.

**Streamlit Community Cloud:** `packages.txt` installs a JDK (`default-jdk-headless`) on deploy, since
the cloud image has only Python. The JUnit launcher is downloaded into `lib/` on the first run.

## How same-input testing works

* **Input cases** live in a shared CSV file (`sample/inputs/pacs008.csv`). Each row is one case: a unique
  case id, the input messages, and the expected result, for example
  `P8-13,p8_13_invalid_uetr.xml,422 REJECTED UETR rows=0`.
* **Each side has its own tests** (`sample/legacy/src/test/java`, `sample/newgen/src/test/java`), written
  in that side's style and with any class or method names. They read the inputs with
  `@CsvFileSource(resources = "/pacs008.csv", numLinesToSkip = 1)`.
* **Every test records what the code actually returned** through its `Recorder` helper, which prints
  `RESULT|<case id>|<output>` (exceptions are recorded as `throws <ExceptionName>`). The
  test then asserts that output against the expected column.
* **The comparator matches the two runs on the case id**, not on test names, and compares both the
  pass/fail status and the actual outputs. Tests that record nothing are matched on
  `fully.qualified.TestClass#method(params)[index]` instead.

To add a case, add a row to the CSV file. Both suites pick it up on the next run.

### Hand-written edge cases

`sample/inputs/pacs008.csv` has **54 pacs.008 cases**, each with an exact expected result and a
`description` column that names the edge case it targets (JUnit ignores extra trailing columns):

| Kind of edge case | Examples |
|---|---|
| Boundaries | InstrId 16 vs 17 chars, remittance 140 vs 141 chars, 14 vs 15 digits |
| Empty and null | empty body, missing XML elements |
| Malformed data | amount with a thousands separator, truncated XML, empty body, wrong message type |
| Security | DOCTYPE with an external entity (XXE) is refused |
| State | duplicate InstrId, duplicate MsgId, exact resend, two payments in one DB |

New hand-written messages are generated with `python tools/generate_pacs008_inputs.py`.

### Bulk testing

`sample/inputs/pacs008_bulk.csv` adds **500 generated cases** (`B-0001` ...) whose messages are in
`sample/inputs/pacs008/bulk/`. Regenerate them, or change the size, with:

```bash
python tools/generate_bulk_inputs.py --count 500 --seed 2026
```

**How the cases are chosen.** Every message starts from the valid baseline and takes one value from each
of 10 dimensions (currency, amount, InstrId, settlement method, charges, BIC, debtor, creditor address,
remittance, UETR): 6,048,000 possible combinations. The generator first builds a **pairwise** set, 68
cases in which every pair of values from any two dimensions appears together at least once. Most
interaction bugs need only two fields to line up, so this finds them at a tiny fraction of the full cross
product. Seeded **random** combinations then fill up to `--count` to reach three-way interactions.
The same count and seed always produce the same files.

**How they are checked: differential testing.** Bulk cases have no expected result (the column is
empty). Each suite's `bulk` test method only records what the code returned, and DiffLens flags every
case where legacy and new gen return different output. You never have to work out 500 correct
answers: the legacy system is the reference. Test methods named `bulk...` are treated as compare-only,
so they are left out of the pass rates and reported as "+500 bulk compared".

**How to read the result.** Hundreds of differences usually share a few causes. The **Root causes** tab
compares the two outputs word by word and groups the cases by the words only one side produced. For the
sample, 331 differing bulk cases come down to three rule codes: R49 and INSTRID (new gen's stricter
SR2025 and CBL rules) and R17 (the deliberate migration bug).

**Performance.** 554 cases run as fast as the original 54 did, because:

* compiled classes are reused while the sources, javac settings and classpath are unchanged (compiling
  was half of every run);
* the GitHub download is skipped when the branch still points at the commit already downloaded;
* the test JVMs start with `-XX:TieredStopAtLevel=1 -XX:+UseSerialGC`, which suits short runs;
* the console prints a summary, not one line per test (per-test results are read from the XML report);
* the comparison is computed once per run, not on every page interaction.

| Run (both sides in parallel) | 54 cases, before | 554 cases, now |
|---|---|---|
| First run (compile) | 3.8 s | 3.6 s |
| Repeat run (sources unchanged) | 3.8 s | 1.9 s |

### Browsing inputs

The **Input files** page opens any input file picked in the left panel (*Test cases*, *Messages* or
*Bulk*). A case file lists every case with its inputs, the expected result and, after a run, both
sides' actual outputs. A pacs.008 message is shown with plain field names, the cases that send it, and
its diff against the valid baseline.

## pacs.008 sample (CBPR+ SR2025)

Both sample code bases contain a `com.example.pacs008` application for the OneClearstream CBPR+
`pacs.008.001.08` usage guideline, laid out as MVC:

```
com.example.pacs008
├── controller/   Pacs008Controller: POST /payments/pacs008 → service → view, picks the HTTP status
├── view/         PaymentView, TextPaymentView: renders the result
├── service/      Pacs008Service: map → validate → convert → save; ProcessingResult
├── model/        Pacs008Message (domain), CreditTransferDto, ValidationError
├── mapper/       Pacs008XmlMapper (XML → model, namespace-aware, DTD/XXE disabled), Pacs008DtoConverter
├── validation/   Pacs008Validator: CBPR+ business rules
└── repository/   PaymentRepository, InMemoryPaymentRepository (virtual DB)
```

The controller answers `201 ACCEPTED <MsgId> <InstrId> <Ccy> <Amount> rows=N`, or `422` (rule
violations), `409` (duplicate) or `400` (unreadable XML) followed by `REJECTED <rule codes> rows=N`.

Rules checked on both sides: NbOfTxs fixed value 1, SttlmMtd, MsgId/EndToEndId, UETR v4 pattern, BIC
pattern, amount td=14/fd=5, R3 (BAH From/To = Instructing/Instructed Agent), R5, R8, R15, R17, R19, R20,
R22, R52/R67 (name when AnyBIC absent), R55/R73 (TwnNm + Ctry).

Deliberate differences between the two versions:

| Behaviour | Legacy | New gen |
|---|---|---|
| InstrId length | up to 35 | up to 16 (CBL usage) |
| Unstructured address (`AdrLine`) | accepted | rejected, R49 (structured only from Nov 2025) |
| Virtual DB unique key | MsgId | InstrId (CBL: unique per instruction) |
| R17 (CRED needs ChrgsInf) | enforced | migration bug: never fires |

Input messages are in `sample/inputs/pacs008/`, and the cases (one or more messages per case, run
against a fresh virtual DB) are in `sample/inputs/pacs008.csv`.

## What you see

| Area | Content |
|---|---|
| Metrics | Total, passed, failed, errors, skipped, pass rate and run time for each side, with deltas |
| Report downloads | **Excel report** and **HTML report** of the run (see below) |
| 🔀 Differences | Only the input cases whose result differs |
| 🔎 Root causes | Differing cases grouped by the output words only one side produced |
| 📋 All tests | Every input case side by side with both outputs, with filters, search and CSV export |
| 🔍 Failure details | Actual output, message and stack trace from both sides next to each other |
| 📜 Build logs | Raw compiler / launcher / Maven / Gradle output |

Categories: 🔴 **Regression** (passes on legacy, fails on new gen) · 🟢 **Fixed** · 🟡 **Changed**
(e.g. failed → error) · 🟠 **Output differs** (same status, different output for the same input) ·
➖/➕ only in one run · ⚪ same.

## Run history and test reports

Every run is saved automatically. The **Run history** page in the left panel lists the saved runs, newest
first, with their status, case counts, regressions, fixes and pass rates. Select a run to see its numbers
(with the change against the run before it) and to:

* **Download the Excel report**: sheets *Summary*, *Differences*, *Root causes*, *All cases* (both
  statuses, outputs, messages and timings per case), *Failures* (message and full stack trace of every
  failing test) and one *Build log* sheet per side; filters and frozen headers on every sheet;
* **Download the HTML report**: the same content as one web page that opens in any browser, prints
  cleanly and can be attached to an email;
* **Open in Comparison**: show the stored run on the Comparison page exactly as when it ran;
* **Delete run**.

The same two downloads are on the Comparison page after every run. Reports are built only when a button
is clicked, so they never slow the page down.

Runs are stored under `.work/history/` (about 50 KB each, compressed); the newest 50 are kept. On
Streamlit Community Cloud that folder is cleared when the app restarts or redeploys, so download the
reports you want to keep.

## Using your own projects

### Getting the code: GitHub with a bundled fallback

Both sides come from **GitHub**. The left panel of the Comparison page has, for each side, a
**Repository** field and a **Branch, tag or commit** field, pre-filled with
[kravi519/LegacyCode](https://github.com/kravi519/LegacyCode) and
[kravi519/NewGenCode](https://github.com/kravi519/NewGenCode) on `main`. Enter a commit id to compare an
exact version. The project folder is found automatically: the repository root if it has `src/main/java`,
else the one folder that does (`legacy/`, `newgen/`). For a repository with several Java projects, pick
one with a `https://github.com/org/repo/tree/<branch>/<folder>` URL.

DiffLens downloads a zip snapshot through the GitHub API, so git is not needed; private repositories need
the `GITHUB_TOKEN` environment variable. After a run, the left panel shows under each side what was
loaded (commit and folder), or why GitHub could not be used.

If GitHub cannot be used (no network, wrong URL, missing branch or folder, no access), DiffLens says why
and falls back automatically:

1. to the last downloaded copy of that repository (cached under `.work/repos/`), if there is one;
2. otherwise to the bundled copies in `sample/legacy` and `sample/newgen`.

Clear a side's Repository field to always use its bundled copy.

### Build tools

Each side has a **build tool** setting:

* **javac** (default, needs only a JDK): compiles `Source dirs`, compiles that side's `Test dirs`
  against it, and runs them with the JUnit 5 console launcher (downloaded into `lib/` on first run).
  The **shared input data dir** is put on the test classpath. Put third-party dependency jars in
  *Extra classpath* (for a Maven project: `mvn dependency:copy-dependencies` → `target/dependency/*.jar`;
  a directory of class files also works). JUnit 4 tests run too, through the vintage engine.
* **maven**: runs `mvn test` (or `mvnw`) in the project root and reads `target/surefire-reports`.
* **gradle**: runs `gradle test` (or `gradlew`) and reads `build/test-results/test`.

In maven/gradle mode, copy the input CSV files into each project's `src/test/resources`.

**Different JDKs:** set *JDK home* per side (for example a JDK 8 for legacy and JDK 21 for new gen),
or keep one modern JDK and set `javac --release 8` for legacy (the sample does this).

## Layout

```
app.py                      Streamlit entry point (navigation)
app_pages/comparison.py     Comparison page: run both sides and compare
app_pages/input_files.py    Input files page: open any input file from the left panel in a readable view
app_pages/run_history.py    Run history page: saved runs, report downloads, reopen or delete a run
comparator/history.py       save, list, load and prune runs under .work/history/
comparator/report.py        Excel and HTML test reports for one run
comparator/input_files.py   read CSV cases and flatten pacs.008 XML into plain-named fields
tools/                      generate_pacs008_inputs.py (hand-written edge cases),
                            generate_bulk_inputs.py (pairwise + random bulk cases)
comparator/source.py        get a side's code from GitHub, with cache and prebuilt fallback
comparator/java_runner.py   build + run one side, parse JUnit XML and recorded outputs
comparator/compare.py       match the runs by input case and classify results
comparator/agent.py         optional Claude agent (not used by the UI)
sample/inputs/              shared input cases: pacs008.csv + pacs008/ (hand-written),
                            pacs008_bulk.csv + pacs008/bulk/ (generated bulk cases)
sample/legacy/              legacy code (src/main/java) and its own tests (src/test/java); GitHub fallback
sample/newgen/              new-gen code (src/main/java) and its own tests (src/test/java); GitHub fallback
```
