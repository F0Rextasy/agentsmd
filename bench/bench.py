"""agentsmd bench: 5 rule fixtures + 1 healthy tree, end-to-end CLI medians."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "scripts", "agentsmd")
FIXTURES = os.path.join(ROOT, "bench", "fixtures")

# (name, root, expected rule or None when healthy)
CASES = [
    ("clean", os.path.join(FIXTURES, "clean"), None),
    ("nopath", os.path.join(FIXTURES, "nopath"), "missing-path"),
    ("fence", os.path.join(FIXTURES, "fence"), "unclosed-fence"),
    ("notitle", os.path.join(FIXTURES, "notitle"), "no-title"),
    ("dup", os.path.join(FIXTURES, "dup"), "duplicated-section"),
    ("budget", None, "over-budget"),
]


def make_budget_fixture(directory):
    """A tree whose only defect is byte budget (> DEFAULT_MAX_BYTES)."""
    filler = "".join("- item %d with padding padding padding padding\n" % i
                     for i in range(600))
    text = "# Budget fixture\n\n## Filler\n\n" + filler
    path = os.path.join(directory, "AGENTS.md")
    os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return directory


def run_once(root):
    start = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, CLI, "lint", "--root", root, "--format", "json"],
        capture_output=True, text=True, timeout=30,
    )
    elapsed = (time.perf_counter() - start) * 1000
    return proc, elapsed


def main():
    results = {}
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        rows = []
        for name, root, expect in CASES:
            if root is None:
                root = make_budget_fixture(os.path.join(tmp, name))
            samples = []
            proc = None
            for _ in range(3):
                proc, elapsed = run_once(root)
                samples.append(elapsed)
            samples.sort()
            median = samples[1]
            data = json.loads(proc.stdout)
            detected = sorted({f["rule"] for f in data["findings"]})
            expected_exit = 1 if expect else 0
            signature_ok = (expect in detected) if expect else not detected
            exit_ok = proc.returncode == expected_exit
            ok = signature_ok and exit_ok
            if not ok:
                failures += 1
            rows.append((name, expect or "ok", ",".join(detected) or "-",
                         "yes" if signature_ok else "NO",
                         "%.0f" % median, "ok" if ok else "FAIL"))
            results[name] = {
                "root": os.path.basename(root),
                "expected": expect or "ok",
                "detected": detected,
                "exit": proc.returncode,
                "median_ms": round(median, 1),
                "verdict": "ok" if ok else "FAIL",
            }

    header = ("fixture", "expected", "detected", "signature", "median ms", "verdict")
    widths = (11, 20, 21, 10, 11, 8)
    line = "".join(h.ljust(w) for h, w in zip(header, widths))
    print(line)
    print("-" * (len(line) - 1))
    for row in rows:
        print("".join(str(c).ljust(w) for c, w in zip(row, widths)))

    out_path = os.path.join(ROOT, "bench", "results.json")
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, sort_keys=True)
        handle.write("\n")

    total = len(rows)
    print("bench: %d/%d fixtures correct" % (total - failures, total))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
