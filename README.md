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

The sidebar is pre-filled with the bundled sample. Click **▶️ Run tests**.

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

### Bulk edge-case testing

The sample ships **54 pacs.008 input cases**, each row ending in a `description` column that
names the edge case it targets (JUnit ignores extra trailing columns):

| Kind of edge case | Examples |
|---|---|
| Boundaries | InstrId 16 vs 17 chars, remittance 140 vs 141 chars, 14 vs 15 digits |
| Empty and null | empty body, missing XML elements |
| Malformed data | amount with a thousands separator, truncated XML, empty body, wrong message type |
| Security | DOCTYPE with an external entity (XXE) is refused |
| State | duplicate InstrId, duplicate MsgId, exact resend, two payments in one DB |

The **Input cases** page in the app's left panel lists every case with its inputs, the expected result
and, after a run, both sides' actual outputs; it also shows each pacs.008 message and its diff against
the valid baseline. New pacs.008 messages are generated with `python tools/generate_pacs008_inputs.py`.

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
| Verdict banner | Regressions found / differences / identical |
| Metrics | Total, passed, failed, errors, skipped, pass rate and run time for each side, with deltas |
| 🔀 Differences | Only the input cases whose result differs |
| 📋 All tests | Every input case side by side with both outputs, with filters, search and CSV export |
| 🔍 Failure details | Actual output, message and stack trace from both sides next to each other |
| 📜 Build logs | Raw compiler / launcher / Maven / Gradle output |

Categories: 🔴 **Regression** (passes on legacy, fails on new gen) · 🟢 **Fixed** · 🟡 **Changed**
(e.g. failed → error) · 🟠 **Output differs** (same status, different output for the same input) ·
➖/➕ only in one run · ⚪ same.

## Using your own projects

### Getting the code: GitHub with a bundled fallback

Each side can come from **GitHub** or a **local folder**. By default both come from GitHub:
legacy from [kravi519/LegacyCode](https://github.com/kravi519/LegacyCode) (folder `legacy`) and new gen
from [kravi519/NewGenCode](https://github.com/kravi519/NewGenCode) (folder `newgen`), branch `main`.
To use other code, edit *GitHub source* for a side in the sidebar: the repository URL, optionally a branch/tag/commit and the project folder inside the repo
(`https://github.com/org/repo/tree/<branch>/<folder>` URLs fill those in too). DiffLens downloads a zip
snapshot through the GitHub API, so git is not needed; private repositories need a *GitHub access token*
(or the `GITHUB_TOKEN` environment variable).

If GitHub cannot be used (no network, wrong URL, missing branch or folder, no access), DiffLens says why
and falls back automatically:

1. to the last downloaded copy of that repository (cached under `.work/repos/`), if there is one;
2. otherwise to the side's **Local folder (prebuilt fallback)**, by default the bundled copies in
   `sample/legacy` and `sample/newgen`.

A row under *Run tests* shows which source each side used. Leave the URL blank to always use the local
folder.

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
app_pages/input_cases.py    Input cases page: every input fed to both sides
tools/                      generate_pacs008_inputs.py (edge-case message generator)
comparator/source.py        get a side's code from GitHub, with cache and prebuilt fallback
comparator/java_runner.py   build + run one side, parse JUnit XML and recorded outputs
comparator/compare.py       match the runs by input case and classify results
comparator/agent.py         optional Claude agent (not used by the UI)
sample/inputs/              shared input cases (pacs008.csv + pacs008/ messages)
sample/legacy/              legacy code (src/main/java) and its own tests (src/test/java); GitHub fallback
sample/newgen/              new-gen code (src/main/java) and its own tests (src/test/java); GitHub fallback
```
