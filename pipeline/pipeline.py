#!/usr/bin/env python3
"""
Technical Debt Evolution Pipeline
MSc Dissertation - Automated SonarQube data collection across git histories.

Usage:
    python pipeline.py --repo piggymetrics          # process all commits
    python pipeline.py --repo piggymetrics --test   # process first 5 commits only
    python pipeline.py                               # process all repos
"""

import argparse
import csv
import logging
import os
import subprocess
import sys
import time
import yaml
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SONAR_HOST = os.environ.get("SONAR_HOST", "http://localhost:9000")
# Analysis token — used by sonar-scanner to push results (scan permission only)
SONAR_TOKEN = os.environ.get("SONAR_TOKEN", "<REDACTED>")
# Admin credentials — used for API reads (measures, CE tasks) which need Browse permission
SONAR_API_USER = os.environ.get("SONAR_API_USER", "admin")
SONAR_API_PASS = os.environ.get("SONAR_API_PASS", "<REDACTED>")
DISSERTATION_DIR = Path.home() / "dissertation"
SCRIPT_DIR       = Path(__file__).resolve().parent   # ~/Documents/dissertation/
RESULTS_DIR      = SCRIPT_DIR / "results"            # results always land next to pipeline.py

BUILD_TIMEOUT = 600   # 10 minutes per build (geoserver-cloud with test compilation needs 5-7 min)
SCAN_TIMEOUT = 600    # 10 minutes per scan (large repos + SonarQube backlog can push past 3 min)
POLL_INTERVAL = 5     # seconds between SonarQube status polls
POLL_MAX_WAIT = 900   # max seconds to wait for analysis to finish

REPOS = [
    {"name": "piggymetrics",                   "url": "https://github.com/sqshq/piggymetrics.git",                           "branch": "master"},
    {"name": "geoserver-cloud",                "url": "https://github.com/geoserver/geoserver-cloud.git",                    "branch": "main"},
    {"name": "train-ticket",                   "url": "https://github.com/FudanSELab/train-ticket.git",                      "branch": "master"},
    {"name": "robot-shop",                     "url": "https://github.com/instana/robot-shop.git",                           "branch": "master"},
    {"name": "microservices-demo",             "url": "https://github.com/GoogleCloudPlatform/microservices-demo.git",        "branch": "main"},
    {"name": "spring-petclinic-microservices", "url": "https://github.com/spring-petclinic/spring-petclinic-microservices.git","branch": "main"},
    {"name": "DeathStarBench",                 "url": "https://github.com/delimitrou/DeathStarBench.git",                    "branch": "master"},
    {"name": "taotao-cloud-project",           "url": "https://github.com/shuigedeng/taotao-cloud-project.git",              "branch": "main"},
    {"name": "erda",                           "url": "https://github.com/erda-project/erda.git",                            "branch": "master"},
    {"name": "light-4j",                       "url": "https://github.com/networknt/light-4j.git",                           "branch": "master"},
]

CSV_COLUMNS = [
    "commit_hash",
    "commit_date",
    "commit_message",
    "sqale_index",
    "ncloc",
    "files",
    "complexity",
    "code_smells",
    "bugs",
    "vulnerabilities",
    "microservice_count",
    "build_status",
    "jdk_used",
]

METRIC_KEYS = "sqale_index,ncloc,files,complexity,code_smells,bugs,vulnerabilities"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def clone_or_verify(repo: dict) -> Path:
    """Clone repo into ~/dissertation/<name> if not already present."""
    repo_dir = DISSERTATION_DIR / repo["name"]
    if repo_dir.exists():
        log.info(f"Repo already cloned at {repo_dir}")
    else:
        log.info(f"Cloning {repo['url']} ...")
        subprocess.run(
            ["git", "clone", repo["url"], str(repo_dir)],
            check=True,
        )
    return repo_dir


def get_commits(repo_dir: Path, branch: str, limit: int | None = None) -> list[dict]:
    """Return commits on <branch> in chronological order (oldest first).

    Each entry: {hash, date (ISO), message}
    Commits before 2015 are excluded — too old to build reliably.
    """
    cmd = [
        "git", "-C", str(repo_dir),
        "log", branch,
        "--format=%H|%aI|%s",   # hash | author-date ISO | subject
        "--reverse",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    commits = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue
        hash_, date_str, message = parts
        # Skip commits before 2015
        if date_str[:4] < "2015":
            continue
        commits.append({"hash": hash_, "date": date_str, "message": message.strip()})

    if limit:
        commits = commits[:limit]

    return commits


def checkout_commit(repo_dir: Path, commit_hash: str) -> None:
    """Hard-reset the working tree to the given commit (detached HEAD)."""
    subprocess.run(
        ["git", "-C", str(repo_dir), "checkout", "--force", commit_hash],
        check=True,
        capture_output=True,
    )


def restore_branch(repo_dir: Path, branch: str) -> None:
    """Switch back to the tip of <branch> after processing."""
    subprocess.run(
        ["git", "-C", str(repo_dir), "checkout", "--force", branch],
        capture_output=True,
    )


# ---------------------------------------------------------------------------
# Build detection and execution
# ---------------------------------------------------------------------------

def detect_build_tool(repo_dir: Path) -> str | None:
    """Return build tool name based on files present at current working tree."""
    checks = [
        ("pom.xml",           "maven"),
        ("build.gradle",      "gradle"),
        ("build.gradle.kts",  "gradle"),
        ("package.json",      "npm"),
        ("go.mod",            "go"),
        ("requirements.txt",  "python"),
    ]
    for filename, tool in checks:
        if (repo_dir / filename).exists():
            return tool
    return None


# Primary JAVA_HOME for Maven builds.
MAVEN_JAVA_HOME: dict[str, str] = {
    "default": "/usr/lib/jvm/java-17-openjdk-amd64",
}

# Per-repo test-skip flag.
# geoserver-cloud uses inter-module test-jar dependencies: -Dmaven.test.skip=true would
# prevent the test-jar goal from running, so sibling modules can't find the :tests artifact.
# -DskipTests skips execution only, lets test-jar get produced, and satisfies those deps.
# All other repos use -Dmaven.test.skip=true to skip even test compilation (handles repos
# with broken test source code that won't compile on modern JDKs).
MAVEN_SKIP_TESTS_FLAG: dict[str, str] = {
    "default":        "-Dmaven.test.skip=true",
    "geoserver-cloud": "-DskipTests",
}

_JDK_LABEL: dict[str, str] = {
    "/usr/lib/jvm/java-11-openjdk-amd64": "11",
    "/usr/lib/jvm/java-17-openjdk-amd64": "17",
}

# JDK is too new for an old jar/plugin → retry with Java 11.
_JDK_TOO_NEW_SIGNALS = (
    "class file version",            # plugin compiled for older JDK than the one running
    "Invalid CEN header",            # zip64 jar unreadable by Java 17+ (e.g. aspectjweaver 1.8.x)
    'does not "opens com.sun.tools', # Lombok/apt reflects into javac internals, blocked by Java 17+ module system
)

# JDK is too old for the project's enforcer rule. This VM only has Java 11 and 17
# installed, so if Java 17 (our newest) fails the enforcer, there's no newer JDK to
# escalate to — the build just fails.
_JDK_TOO_OLD_SIGNALS = (
    "not in the allowed range",  # maven-enforcer RequireJavaVersion rule
    "RequireJavaVersion failed",
)


def _run_maven(cmd: list[str], repo_dir: Path, java_home: str) -> subprocess.CompletedProcess:
    """Run a Maven command with the given JAVA_HOME and return the CompletedProcess."""
    return subprocess.run(
        cmd,
        cwd=str(repo_dir),
        timeout=BUILD_TIMEOUT,
        capture_output=True,
        text=True,
        env={**os.environ, "JAVA_HOME": java_home},
    )


def run_build(repo_dir: Path, tool: str, repo_name: str = "default") -> tuple[bool, str | None]:
    """Run the build for the detected tool. Returns (success, jdk_version_used).

    Maven cascade: Java 17 → Java 11 (JDK too new). If the enforcer rejects Java 17 for
    being too old, there's no newer JDK on this VM to escalate to, so the build fails.
    Maven [ERROR] output goes to stdout; signal detection checks stdout+stderr combined.
    jdk_version_used is None for non-Maven builds.
    """
    skip_flag = MAVEN_SKIP_TESTS_FLAG.get(repo_name, MAVEN_SKIP_TESTS_FLAG["default"])
    commands = {
        "maven":  ["mvn", "clean", "package", skip_flag, "-Ddockerfile.skip=true", "-q"],
        "gradle": ["gradle", "build", "-x", "test", "-q"],
        "npm":    ["npm", "install", "--silent"],
        "go":     ["go", "build", "./..."],
        "python": ["pip", "install", "-r", "requirements.txt", "-q"],
    }
    cmd = commands[tool]

    if tool != "maven":
        try:
            result = subprocess.run(
                cmd, cwd=str(repo_dir), timeout=BUILD_TIMEOUT, capture_output=True, text=True
            )
            if result.returncode != 0:
                combined = result.stdout + result.stderr
                log.warning(f"Build failed (exit {result.returncode}): {combined[-500:]}")
                return False, None
            return True, None
        except subprocess.TimeoutExpired:
            log.warning(f"Build timed out after {BUILD_TIMEOUT}s")
            return False, None
        except Exception as e:
            log.warning(f"Build error: {e}")
            return False, None

    # --- Maven: 3-tier JDK cascade ---
    # Tier 1: Java 17 (primary)
    primary = MAVEN_JAVA_HOME.get(repo_name, MAVEN_JAVA_HOME["default"])
    label   = _JDK_LABEL.get(primary, primary)
    try:
        r = _run_maven(cmd, repo_dir, primary)
    except subprocess.TimeoutExpired:
        log.warning(f"Build timed out after {BUILD_TIMEOUT}s (Java {label})")
        return False, label
    except Exception as e:
        log.warning(f"Build error: {e}")
        return False, label

    if r.returncode == 0:
        return True, label

    # Maven writes [ERROR] to stdout — check combined output for signals.
    combined = r.stdout + r.stderr
    log.debug(f"  Build stdout[300]: {combined[:300]}")

    if any(sig in combined for sig in _JDK_TOO_NEW_SIGNALS):
        # Tier 2a: JDK too new (module-opens, class-file, zip64) → Java 11
        log.warning(f"  Java {label}: JDK too new for project — retrying with Java 11")
        fb = "/usr/lib/jvm/java-11-openjdk-amd64"
        fb_label = "11"
        try:
            r2 = _run_maven(cmd, repo_dir, fb)
        except subprocess.TimeoutExpired:
            log.warning(f"Build timed out after {BUILD_TIMEOUT}s (Java {fb_label})")
            return False, fb_label
        except Exception as e:
            log.warning(f"Build error: {e}")
            return False, fb_label
        if r2.returncode == 0:
            log.info(f"  Java {fb_label} fallback succeeded")
            return True, fb_label
        log.warning(f"Build failed (exit {r2.returncode}): {(r2.stdout+r2.stderr)[-500:]}")
        return False, fb_label

    elif any(sig in combined for sig in _JDK_TOO_OLD_SIGNALS):
        # Enforcer rejects the current JDK as too old and wants something newer, but this
        # VM only has Java 11 and 17 installed — there's no newer JDK to escalate to.
        log.warning(f"  Java {label}: JDK too old for enforcer — no newer JDK installed on this VM, failing")
        log.warning(f"Build failed (exit {r.returncode}): {combined[-500:]}")
        return False, label

    else:
        log.warning(f"Build failed (exit {r.returncode}): {combined[-500:]}")
        return False, label


# ---------------------------------------------------------------------------
# SonarQube scan
# ---------------------------------------------------------------------------

def run_sonar_scan(repo_dir: Path, project_key: str) -> str | None:
    """Run sonar-scanner for the current working tree.

    Returns the CE task ID on success (used to poll status), or None on failure.
    The task ID is parsed from the scanner's stdout line:
      "More about the report processing at .../api/ce/task?id=<ID>"
    """
    props = [
        f"-Dsonar.projectKey={project_key}",
        f"-Dsonar.projectName={project_key}",
        "-Dsonar.sources=.",
        f"-Dsonar.host.url={SONAR_HOST}",
        # SonarQube 9.9 LTS uses sonar.login; sonar.token is a later addition
        f"-Dsonar.login={SONAR_TOKEN}",
        "-Dsonar.scm.disabled=true",
        "-Dsonar.sourceEncoding=UTF-8",
        # Always set java.binaries so mixed-language repos with some Java services
        # don't hard-fail; "." means "look here, no real classes needed".
        "-Dsonar.java.binaries=.",
    ]

    # Remove stale lock left by a killed scan process — sonar-scanner won't start if it exists
    lock_file = repo_dir / ".scannerwork" / ".sonar_lock"
    if lock_file.exists():
        lock_file.unlink()

    try:
        result = subprocess.run(
            ["sonar-scanner"] + props,
            cwd=str(repo_dir),
            timeout=SCAN_TIMEOUT,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            log.warning(f"sonar-scanner failed: {result.stdout[-800:]}")
            return None

        # Extract CE task ID from output so we can poll the exact task
        for line in result.stdout.splitlines():
            if "api/ce/task?id=" in line:
                task_id = line.split("api/ce/task?id=")[-1].strip()
                return task_id

        log.warning("sonar-scanner succeeded but no task ID found in output")
        return None
    except subprocess.TimeoutExpired:
        log.warning(f"sonar-scanner timed out after {SCAN_TIMEOUT}s")
        return None
    except Exception as e:
        log.warning(f"sonar-scanner error: {e}")
        return None


# ---------------------------------------------------------------------------
# SonarQube API helpers
# ---------------------------------------------------------------------------

def _sonar_auth() -> tuple[str, str]:
    """Return (username, password) for requests BasicAuth on read APIs.

    The scan token only has 'scan' permission; admin credentials are needed
    to call Browse-protected endpoints like api/measures and api/ce/task.
    """
    return (SONAR_API_USER, SONAR_API_PASS)


def wait_for_analysis(task_id: str) -> bool:
    """Poll api/ce/task?id=<task_id> until status is SUCCESS or FAILED.

    Uses the specific task ID returned by the scanner rather than the component
    endpoint, which requires admin privileges we don't have.
    Returns True if SUCCESS, False if FAILED/CANCELED/timeout.
    """
    url = f"{SONAR_HOST}/api/ce/task"
    deadline = time.time() + POLL_MAX_WAIT

    while time.time() < deadline:
        try:
            resp = requests.get(
                url,
                params={"id": task_id},
                auth=_sonar_auth(),
                timeout=10,
            )
            resp.raise_for_status()
            status = resp.json().get("task", {}).get("status", "")

            if status == "SUCCESS":
                return True
            if status in ("FAILED", "CANCELED"):
                log.warning(f"Analysis task status: {status}")
                return False
            log.debug(f"Analysis status: {status!r} — waiting {POLL_INTERVAL}s ...")
        except Exception as e:
            log.warning(f"Error polling analysis status: {e}")

        time.sleep(POLL_INTERVAL)

    log.warning("Timed out waiting for SonarQube analysis to complete")
    return False


def fetch_metrics(project_key: str) -> dict:
    """Fetch the requested metrics for the project. Returns dict of metric→value."""
    url = f"{SONAR_HOST}/api/measures/component"
    try:
        resp = requests.get(
            url,
            params={"component": project_key, "metricKeys": METRIC_KEYS},
            auth=_sonar_auth(),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        measures = data.get("component", {}).get("measures", [])
        return {m["metric"]: m.get("value") for m in measures}
    except Exception as e:
        log.warning(f"Failed to fetch metrics: {e}")
        return {}


# ---------------------------------------------------------------------------
# Docker-compose microservice count
# ---------------------------------------------------------------------------

def count_microservices(repo_dir: Path) -> int | None:
    """Parse docker-compose.yml (or docker-compose.yaml) and count services
    that have either a 'build' or 'image' key — these represent runnable
    microservices rather than abstract base definitions.
    """
    for filename in ("docker-compose.yml", "docker-compose.yaml"):
        compose_file = repo_dir / filename
        if compose_file.exists():
            try:
                with compose_file.open() as f:
                    doc = yaml.safe_load(f)
                services = doc.get("services", {}) if doc else {}
                count = sum(
                    1 for svc in services.values()
                    if isinstance(svc, dict) and ("build" in svc or "image" in svc)
                )
                return count
            except Exception as e:
                log.warning(f"Could not parse {filename}: {e}")
    return None


# ---------------------------------------------------------------------------
# Resume: load already-processed commit hashes from existing CSV
# ---------------------------------------------------------------------------

def load_processed_hashes(csv_path: Path) -> set[str]:
    """Return set of commit hashes already written to the CSV."""
    if not csv_path.exists():
        return set()
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        return {row["commit_hash"] for row in reader if row.get("commit_hash")}


# ---------------------------------------------------------------------------
# Core per-repo processing
# ---------------------------------------------------------------------------

def process_repo(repo: dict, test_mode: bool = False, skip: int = 0) -> None:
    name   = repo["name"]
    branch = repo["branch"]

    log.info(f"=== Starting repo: {name} ===")

    # 1. Clone / verify
    repo_dir = clone_or_verify(repo)

    # Ensure we're on the right branch tip before reading history
    restore_branch(repo_dir, branch)

    # 2. Collect commits — fetch all first, then apply skip/limit slice
    all_commits = get_commits(repo_dir, branch, limit=None)
    sliced = all_commits[skip:]
    commits = sliced[:5] if test_mode else sliced
    total   = len(commits)
    log.info(f"Found {total} commits to process (post-2015, skip={skip})")

    # 3. Output paths
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path  = RESULTS_DIR / f"{name}_results.csv"
    fail_path = RESULTS_DIR / f"{name}_failed.log"

    # 4. Resume: skip already-processed commits
    processed = load_processed_hashes(csv_path)
    if processed:
        log.info(f"Resuming — {len(processed)} commits already in CSV, skipping them")

    # Open CSV in append mode so we can resume
    csv_exists = csv_path.exists()

    # A resumed run appends rows shaped by the current CSV_COLUMNS, but the
    # header on disk was written by whichever version of this script created
    # the file.  When a column is added between runs (as jdk_used was), those
    # rows carry one field more than the header declares and every strict CSV
    # reader then drops them.  Reconcile before appending: a header that is a
    # prefix of CSV_COLUMNS is safe to extend in place, anything else is a
    # genuine schema divergence and must not be silently appended to.
    if csv_exists:
        with csv_path.open(newline="") as f:
            existing = next(csv.reader(f), [])
        if existing and existing != CSV_COLUMNS:
            if CSV_COLUMNS[:len(existing)] == existing:
                added = CSV_COLUMNS[len(existing):]
                body = csv_path.read_text(encoding="utf-8").split("\n", 1)[1]
                csv_path.write_text(",".join(CSV_COLUMNS) + "\n" + body, encoding="utf-8")
                log.warning(f"CSV header extended with {added} to match CSV_COLUMNS")
            else:
                sys.exit(
                    f"CSV schema mismatch in {csv_path.name}:\n"
                    f"  on disk: {existing}\n"
                    f"  expected: {CSV_COLUMNS}\n"
                    "Refusing to append — resolve manually to avoid corrupting the file."
                )

    csv_file   = csv_path.open("a", newline="")
    writer     = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
    if not csv_exists:
        writer.writeheader()

    fail_file = fail_path.open("a")

    try:
        for idx, commit in enumerate(commits, start=1):
            h       = commit["hash"]
            short_h = h[:7]
            date    = commit["date"]
            msg     = commit["message"]

            print(f"Processing commit {idx}/{total}: {short_h} ({date[:10]})")

            # Resume check
            if h in processed:
                log.debug(f"  Skipping already-processed commit {short_h}")
                continue

            # 3a. Checkout
            try:
                checkout_commit(repo_dir, h)
            except subprocess.CalledProcessError as e:
                log.warning(f"  git checkout failed for {short_h}: {e}")
                _write_failed(writer, fail_file, h, date, msg, "CHECKOUT_FAILED")
                csv_file.flush()
                continue

            # 3b. Detect build tool
            tool = detect_build_tool(repo_dir)
            log.info(f"  Build tool: {tool or 'none detected'}")

            # 3c. Build
            build_ok = True
            jdk_used = None
            if tool:
                build_ok, jdk_used = run_build(repo_dir, tool, repo_name=name)
                if not build_ok:
                    log.warning(f"  Build failed — will still attempt scan")

            # 3d. Sonar scan (attempt even if build failed; source metrics don't need binaries)
            task_id = run_sonar_scan(repo_dir, name)

            if not task_id:
                log.warning(f"  Scan failed for {short_h}")
                _write_failed(writer, fail_file, h, date, msg, "SCAN_FAILED", jdk_used=jdk_used)
                fail_file.write(f"{h} | {date[:10]} | {msg}\n")
                csv_file.flush()
                fail_file.flush()
                continue

            # 3e. Wait for analysis using the exact task ID from the scanner output
            analysis_ok = wait_for_analysis(task_id)
            if not analysis_ok:
                log.warning(f"  Analysis did not complete for {short_h}")
                _write_failed(writer, fail_file, h, date, msg, "ANALYSIS_FAILED", jdk_used=jdk_used)
                fail_file.write(f"{h} | {date[:10]} | {msg}\n")
                csv_file.flush()
                fail_file.flush()
                continue

            # 3f. Fetch metrics
            metrics = fetch_metrics(name)

            # 3g. Count microservices
            ms_count = count_microservices(repo_dir)

            # 3h. Write CSV row
            row = {
                "commit_hash":      h,
                "commit_date":      date,
                "commit_message":   msg,
                "sqale_index":      metrics.get("sqale_index"),
                "ncloc":            metrics.get("ncloc"),
                "files":            metrics.get("files"),
                "complexity":       metrics.get("complexity"),
                "code_smells":      metrics.get("code_smells"),
                "bugs":             metrics.get("bugs"),
                "vulnerabilities":  metrics.get("vulnerabilities"),
                "microservice_count": ms_count,
                "build_status":     "SUCCESS" if build_ok else "BUILD_FAILED_SCAN_OK",
                "jdk_used":         jdk_used,
            }
            writer.writerow(row)
            csv_file.flush()
            log.info(f"  Written row: sqale={metrics.get('sqale_index')} ncloc={metrics.get('ncloc')}")

    finally:
        # Always restore the branch tip regardless of what happened
        restore_branch(repo_dir, branch)
        csv_file.close()
        fail_file.close()

    log.info(f"=== Finished {name}. Results: {csv_path} ===")


def _write_failed(
    writer: csv.DictWriter,
    fail_file,
    commit_hash: str,
    commit_date: str,
    commit_message: str,
    status: str,
    jdk_used: str | None = None,
) -> None:
    """Write a failure row to the CSV and the fail log."""
    writer.writerow({
        "commit_hash":        commit_hash,
        "commit_date":        commit_date,
        "commit_message":     commit_message,
        "sqale_index":        None,
        "ncloc":              None,
        "files":              None,
        "complexity":         None,
        "code_smells":        None,
        "bugs":               None,
        "vulnerabilities":    None,
        "microservice_count": None,
        "build_status":       status,
        "jdk_used":           jdk_used,
    })
    fail_file.write(f"{commit_hash} | {commit_date[:10]} | {status} | {commit_message}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Technical debt pipeline — collect SonarQube metrics per commit"
    )
    parser.add_argument(
        "--repo",
        help="Process only this repo (by name, e.g. piggymetrics)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Process only the first 5 commits of each repo",
    )
    parser.add_argument(
        "--skip",
        type=int,
        default=0,
        metavar="N",
        help="Skip the first N commits (useful with --test to target a specific range)",
    )
    args = parser.parse_args()

    # Filter repos if --repo flag given
    repos_to_run = REPOS
    if args.repo:
        repos_to_run = [r for r in REPOS if r["name"] == args.repo]
        if not repos_to_run:
            sys.exit(f"Unknown repo name: {args.repo!r}. Choose from: {[r['name'] for r in REPOS]}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    for repo in repos_to_run:
        try:
            process_repo(repo, test_mode=args.test, skip=args.skip)
        except Exception as e:
            log.error(f"Unexpected error processing {repo['name']}: {e}", exc_info=True)
            # Continue to next repo rather than crashing the whole pipeline


if __name__ == "__main__":
    main()
