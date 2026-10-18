"""Build and run a JUnit test suite against one Java code base, then parse the JUnit XML reports.

Three build modes are supported:
  * javac  - compile sources + tests with javac and run them with the JUnit Platform console
             launcher (downloaded automatically). Needs only a JDK. Puts the shared input data
             directory on the test classpath so both code bases' tests read the same inputs.
  * maven  - run `mvn test` in the project root and read target/surefire-reports.
  * gradle - run `gradle test` in the project root and read build/test-results/test.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
LIB_DIR = PROJECT_DIR / "lib"
WORK_DIR = PROJECT_DIR / ".work"

JUNIT_VERSION = "1.10.2"
JUNIT_JAR_NAME = f"junit-platform-console-standalone-{JUNIT_VERSION}.jar"
JUNIT_JAR_URL = (
    "https://repo1.maven.org/maven2/org/junit/platform/junit-platform-console-standalone/"
    f"{JUNIT_VERSION}/{JUNIT_JAR_NAME}"
)

BUILD_TOOLS = ("javac", "maven", "gradle")


@dataclass
class ProjectConfig:
    label: str  # "legacy" or "newgen"
    root: Path
    build_tool: str = "javac"
    source_dirs: list[Path] = field(default_factory=list)  # javac mode only
    test_dirs: list[Path] = field(default_factory=list)  # javac mode only
    input_dirs: list[Path] = field(default_factory=list)  # shared input data on the test classpath, javac mode only
    classpath: list[Path] = field(default_factory=list)  # extra jars/dirs, javac mode only
    java_home: str = ""  # empty -> java/javac/mvn from PATH
    release: str = ""  # javac --release value, e.g. "8" or "17"
    timeout: int = 900


@dataclass
class TestCase:
    suite: str
    name: str
    display_name: str
    status: str  # passed | failed | error | skipped
    time: float
    message: str = ""
    details: str = ""
    stdout: str = ""
    case_id: str = ""  # input case recorded by the test ("RESULT|<case>|<output>"), if any
    output: str | None = None  # actual output the code returned for that input case

    @property
    def id(self) -> str:
        return f"{self.suite}#{self.name}"

    @property
    def key(self) -> str:
        """What the two runs are matched on: the input case when recorded, else the test id."""
        return self.case_id or self.id


@dataclass
class RunResult:
    label: str
    ok: bool  # True when the suite ran (even if tests failed); False on build/launch failure
    stage: str  # where it stopped: setup | compile-main | compile-test | test | done
    tests: list[TestCase]
    duration: float
    log: str
    error: str = ""

    def counts(self) -> dict[str, int]:
        c = {"total": len(self.tests), "passed": 0, "failed": 0, "error": 0, "skipped": 0}
        for t in self.tests:
            c[t.status] += 1
        return c


class BuildError(Exception):
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage


def _exe(cfg: ProjectConfig, name: str) -> str:
    if cfg.java_home:
        suffix = ".exe" if os.name == "nt" else ""
        return str(Path(cfg.java_home) / "bin" / f"{name}{suffix}")
    return name


def _env(cfg: ProjectConfig) -> dict[str, str]:
    env = dict(os.environ)
    if cfg.java_home:
        env["JAVA_HOME"] = cfg.java_home
        env["PATH"] = str(Path(cfg.java_home) / "bin") + os.pathsep + env.get("PATH", "")
    return env


def _run(cmd: list[str], cfg: ProjectConfig, log: list[str], cwd: Path | None = None) -> int:
    log.append("$ " + " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            env=_env(cfg),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=cfg.timeout,
            shell=os.name == "nt" and cmd[0].lower().endswith((".cmd", ".bat")),
        )
    except FileNotFoundError as e:
        raise BuildError("setup", f"Executable not found: {cmd[0]} ({e})") from e
    except subprocess.TimeoutExpired as e:
        raise BuildError("test", f"Timed out after {cfg.timeout}s: {' '.join(cmd)}") from e
    log.append(proc.stdout)
    if proc.stderr:
        log.append(proc.stderr)
    return proc.returncode


def ensure_junit_jar() -> Path:
    jar = LIB_DIR / JUNIT_JAR_NAME
    if not jar.exists():
        LIB_DIR.mkdir(parents=True, exist_ok=True)
        tmp = jar.with_suffix(".part")
        urllib.request.urlretrieve(JUNIT_JAR_URL, tmp)
        tmp.replace(jar)
    return jar


def _java_files(dirs: list[Path]) -> list[Path]:
    files: list[Path] = []
    for d in dirs:
        files.extend(sorted(Path(d).rglob("*.java")))
    return files


def _write_argfile(path: Path, files: list[Path]) -> None:
    # javac @argfile avoids the Windows command-line length limit.
    path.write_text("\n".join(f'"{f.resolve().as_posix()}"' for f in files), encoding="utf-8")


def _cp(entries: list[Path | str]) -> str:
    return os.pathsep.join(str(e) for e in entries)


def _run_javac_mode(cfg: ProjectConfig, log: list[str]) -> Path:
    try:
        junit = ensure_junit_jar()
    except OSError as e:
        raise BuildError("setup", f"Could not download JUnit console launcher from {JUNIT_JAR_URL}: {e}") from e

    work = WORK_DIR / cfg.label
    shutil.rmtree(work, ignore_errors=True)
    main_out, test_out, reports = work / "classes", work / "test-classes", work / "reports"
    for d in (main_out, test_out, reports):
        d.mkdir(parents=True)

    release = ["--release", cfg.release] if cfg.release else []
    javac = _exe(cfg, "javac")

    main_src = _java_files(cfg.source_dirs)
    if not main_src:
        raise BuildError("compile-main", f"No .java files found in {[str(d) for d in cfg.source_dirs]}")
    _write_argfile(work / "main.args", main_src)
    rc = _run(
        [javac, *release, "-encoding", "UTF-8", "-d", str(main_out), "-cp", _cp(cfg.classpath) or ".",
         f"@{work / 'main.args'}"],
        cfg, log,
    )
    if rc != 0:
        raise BuildError("compile-main", "Main sources failed to compile - see the build log.")

    test_src = _java_files(cfg.test_dirs)
    if not test_src:
        raise BuildError("compile-test", f"No .java files found in {[str(d) for d in cfg.test_dirs]}")
    _write_argfile(work / "test.args", test_src)
    rc = _run(
        [javac, *release, "-encoding", "UTF-8", "-d", str(test_out),
         "-cp", _cp([main_out, junit, *cfg.classpath]), f"@{work / 'test.args'}"],
        cfg, log,
    )
    if rc != 0:
        raise BuildError("compile-test", "Tests failed to compile against this code base - see the build log.")

    # Exit code 1 just means some tests failed; the XML report is what matters.
    # Captured stdout carries the RESULT lines, so it has to be written into the report.
    _run(
        [_exe(cfg, "java"), "-jar", str(junit), "execute", "--disable-banner", "--details=tree",
         "--class-path", _cp([main_out, test_out, *cfg.input_dirs, *cfg.classpath]), "--scan-class-path",
         "--config=junit.platform.output.capture.stdout=true", "--reports-dir", str(reports)],
        cfg, log,
    )
    return reports


def _run_maven_mode(cfg: ProjectConfig, log: list[str]) -> Path:
    wrapper = cfg.root / ("mvnw.cmd" if os.name == "nt" else "mvnw")
    mvn = str(wrapper) if wrapper.exists() else ("mvn.cmd" if os.name == "nt" else "mvn")
    _run([mvn, "-B", "test", "-Dmaven.test.failure.ignore=true"], cfg, log, cwd=cfg.root)
    return cfg.root / "target" / "surefire-reports"


def _run_gradle_mode(cfg: ProjectConfig, log: list[str]) -> Path:
    wrapper = cfg.root / ("gradlew.bat" if os.name == "nt" else "gradlew")
    gradle = str(wrapper) if wrapper.exists() else ("gradle.bat" if os.name == "nt" else "gradle")
    _run([gradle, "test", "--continue"], cfg, log, cwd=cfg.root)
    return cfg.root / "build" / "test-results" / "test"


def _display_name(system_out: str, fallback: str) -> str:
    for line in system_out.splitlines():
        if line.startswith("display-name:"):
            return line.split(":", 1)[1].strip()
    return fallback


def _recorded_result(system_out: str) -> tuple[str, str | None]:
    """Return (case id, output) from the first "RESULT|<case>|<output>" line a test printed."""
    for line in system_out.splitlines():
        if line.startswith("RESULT|"):
            _, case_id, output = (line.rstrip("\r").split("|", 2) + [""])[:3]
            return case_id.strip(), output
    return "", None


def parse_reports(reports_dir: Path) -> list[TestCase]:
    tests: list[TestCase] = []
    for xml_file in sorted(reports_dir.glob("TEST-*.xml")):
        root = ET.parse(xml_file).getroot()
        suites = [root] if root.tag == "testsuite" else root.iter("testsuite")
        for suite in suites:
            for tc in suite.iter("testcase"):
                status, message, details = "passed", "", ""
                for tag in ("failure", "error", "skipped"):
                    el = tc.find(tag)
                    if el is not None:
                        status = "failed" if tag == "failure" else tag
                        message = el.get("message", "") or ""
                        details = (el.text or "").strip()
                        break
                # The console launcher writes metadata and captured output as separate <system-out>s.
                stdout = "\n".join((el.text or "").strip() for el in tc.findall("system-out")).strip()
                case_id, output = _recorded_result(stdout)
                name = tc.get("name", "")
                tests.append(TestCase(
                    suite=tc.get("classname", suite.get("name", "")),
                    name=name,
                    display_name=_display_name(stdout, name),
                    status=status,
                    time=float(tc.get("time", "0") or 0),
                    message=message,
                    details=details,
                    stdout=stdout,
                    case_id=case_id,
                    output=output,
                ))
    return tests


def run_suite(cfg: ProjectConfig) -> RunResult:
    """Build and test one code base. Never raises: failures are reported in the RunResult."""
    log: list[str] = []
    start = time.perf_counter()
    try:
        if cfg.build_tool == "javac":
            reports = _run_javac_mode(cfg, log)
        elif cfg.build_tool == "maven":
            reports = _run_maven_mode(cfg, log)
        elif cfg.build_tool == "gradle":
            reports = _run_gradle_mode(cfg, log)
        else:
            raise BuildError("setup", f"Unknown build tool {cfg.build_tool!r}; expected one of {BUILD_TOOLS}")

        tests = parse_reports(reports) if reports.exists() else []
        if not tests:
            raise BuildError("test", f"No JUnit XML results found in {reports}. Check the build log.")
        return RunResult(cfg.label, True, "done", tests, time.perf_counter() - start, "\n".join(log))
    except BuildError as e:
        return RunResult(cfg.label, False, e.stage, [], time.perf_counter() - start, "\n".join(log), str(e))
