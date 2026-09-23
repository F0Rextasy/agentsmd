import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "scripts", "agentsmd")
FIX = os.path.join(ROOT, "bench", "fixtures")
EXAMPLES = os.path.join(ROOT, "examples")


def run(*args):
    return subprocess.run([sys.executable, CLI, *args], capture_output=True,
                          text=True, cwd=ROOT, timeout=30)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


class AgentsmdTests(unittest.TestCase):
    def test_discover_nested_and_skips_vendored_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "AGENTS.md"), "# Root\n")
            write(os.path.join(tmp, "pkg", "AGENTS.md"), "# Pkg\n")
            write(os.path.join(tmp, "node_modules", "x", "AGENTS.md"), "# Vendored\n")
            result = run("discover", "--root", tmp, "--format", "json")
            data = json.loads(result.stdout)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(data["files"], ["AGENTS.md", "pkg/AGENTS.md"])
            self.assertEqual(data["count"], 2)

    def test_clean_fixture_is_finding_free_in_text_and_json(self):
        clean = os.path.join(FIX, "clean")
        as_json = run("lint", "--root", clean, "--format", "json")
        data = json.loads(as_json.stdout)
        self.assertEqual(as_json.returncode, 0)
        self.assertEqual(data["findings"], [])
        self.assertEqual(data["files"], 1)
        self.assertEqual(data["exit"], 0)
        as_text = run("lint", "--root", clean)
        self.assertEqual(as_text.returncode, 0)
        self.assertIn("1 file(s), 0 finding(s)", as_text.stdout)

    def test_missing_path_flagged_but_plain_spans_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "AGENTS.md"),
                  "# Refs\n\n## Layout\n\nSee `notes/` for details, "
                  "run `git status` first, package name `pkg` stays.\n")
            result = run("lint", "--root", tmp, "--format", "json")
            data = json.loads(result.stdout)
            self.assertEqual(result.returncode, 1)
            rules = [f["rule"] for f in data["findings"]]
            self.assertEqual(rules, ["missing-path"])
            self.assertIn("notes/", data["findings"][0]["message"])

    def test_unclosed_fence_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "AGENTS.md"),
                  "# Fences\n\n## Example\n\n```json\n{ \"open\": true\n")
            result = run("lint", "--root", tmp, "--format", "json")
            data = json.loads(result.stdout)
            self.assertEqual(result.returncode, 1)
            self.assertEqual([f["rule"] for f in data["findings"]],
                             ["unclosed-fence"])
            self.assertEqual(data["findings"][0]["line"], 5)

    def test_over_budget_honors_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "AGENTS.md"), "# Budget\n\nBody text.\n")
            self.assertEqual(run("lint", "--root", tmp).returncode, 0)
            strict = run("lint", "--root", tmp, "--max-bytes", "5",
                         "--format", "json")
            data = json.loads(strict.stdout)
            self.assertEqual(strict.returncode, 1)
            self.assertEqual([f["rule"] for f in data["findings"]],
                             ["over-budget"])
            self.assertEqual(data["findings"][0]["severity"], "warn")

    def test_no_title_reported_at_line_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "AGENTS.md"), "## Commands\n\nRun it.\n")
            result = run("lint", "--root", tmp, "--format", "json")
            data = json.loads(result.stdout)
            self.assertEqual(result.returncode, 1)
            self.assertEqual([f["rule"] for f in data["findings"]], ["no-title"])
            self.assertEqual(data["findings"][0]["line"], 1)

    def test_duplicated_section_only_when_bodies_match(self):
        dup = run("lint", "--root", os.path.join(FIX, "dup"), "--format", "json")
        data = json.loads(dup.stdout)
        self.assertEqual(dup.returncode, 1)
        rules = {f["rule"] for f in data["findings"]}
        self.assertEqual(rules, {"duplicated-section"})
        flagged = [f for f in data["findings"] if f["rule"] == "duplicated-section"]
        self.assertEqual(flagged[0]["file"], "packages/app/AGENTS.md")
        # examples hierarchy redefines the same section with different text:
        # an intentional override, not a duplicate.
        overridden = run("lint", "--root", EXAMPLES, "--format", "json")
        self.assertEqual(overridden.returncode, 0)
        self.assertEqual(json.loads(overridden.stdout)["findings"], [])

    def test_effective_compiles_child_wins_with_provenance(self):
        result = run("effective", os.path.join(FIX, "dup", "packages", "app"),
                     "--root", os.path.join(FIX, "dup"), "--format", "json")
        data = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(data["sources"], ["AGENTS.md", "packages/app/AGENTS.md"])
        by_title = {s["title"]: s for s in data["sections"]}
        self.assertEqual(by_title["Review"]["source"], "packages/app/AGENTS.md")
        self.assertEqual(by_title["Build"]["source"], "AGENTS.md")
        self.assertEqual(by_title["Deploy"]["source"], "packages/app/AGENTS.md")


if __name__ == "__main__":
    unittest.main()
