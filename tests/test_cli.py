#!/usr/bin/env python3
"""The command line, end to end. Every subcommand, actually run.

WHY THIS EXISTS (from a real defect, 2026-08-29). A reader tried the README's
own quickstart and could not get past it. All three subcommands raised on a
clean checkout -- `validate.check` did not exist, `fingerprint.compute` was
called with one argument out of two, and `date.today` was missing its parens in
two places -- while the suite reported 90 passed. Nothing imported voiceloop.cli.

Every module the command line calls is generated from the engine; this file is
not, so an engine signature can move and leave these call sites addressing a
shape that is gone. The suite was structurally blind to that. These tests run
the real subcommands against a real temp corpus and read what they wrote, so a
signature drift lands as a red test instead of as a stranger's bug report.

Fixtures are built here rather than read from a corpus: voiceloop ships with an
empty corpus/ on purpose and test_no_founder_data.py holds that direction.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voiceloop import cli, fingerprint  # noqa: E402

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Distinct lengths and rhythms so the percentile bands are computed over real
# spread rather than one repeated sentence.
POSTS = [
    "The gate passed and the draft was empty. Clean is not the same as good.",
    "I shipped it on a Friday. It broke on a Sunday, and the log said nothing at "
    "all, which is the part that cost me the weekend.",
    "Nobody reads the second paragraph. Write the first one twice.",
    "A check that cannot fail is decoration. Name the input that turns it red, "
    "or delete it and stop pretending you have coverage.",
]


def _corpus(tmp, rows=None):
    """A minimal but REAL corpus dir: the loader's actual file names and shapes."""
    os.makedirs(tmp, exist_ok=True)
    rows = POSTS if rows is None else rows
    with open(os.path.join(tmp, "exemplars.jsonl"), "w", encoding="utf-8") as fh:
        for i, text in enumerate(rows):
            fh.write(json.dumps({"id": f"p-{i:02d}", "kind": "post",
                                 "channel": "linkedin", "status": "active",
                                 "weight": 1.0, "text": text}) + "\n")
    return tmp


class CorrectionsAdd(unittest.TestCase):

    def test_writes_a_real_iso_date_not_a_method_repr(self):
        """The paren bug, pinned. `date.today` without parens is not a date, and
        an f-string renders it as a builtin-method repr instead of raising
        somewhere obvious. Asserting the SHAPE of the value catches both the
        crash and the silent-garbage variant of the same mistake."""
        with tempfile.TemporaryDirectory() as tmp:
            rc = cli.main(["corrections", "add", "--corpus-dir", tmp,
                           "--slug", "take-a-side", "--instruction", "Say it plainly."])
            self.assertEqual(rc, 0)
            with open(os.path.join(tmp, "corrections.jsonl"), encoding="utf-8") as fh:
                row = json.loads(fh.readline())
        self.assertTrue(ISO_DATE.match(row["date"]), row["date"])
        self.assertTrue(row["id"].endswith("-take-a-side"), row["id"])
        self.assertTrue(ISO_DATE.match(row["id"][:10]), row["id"])
        self.assertNotIn("built-in", json.dumps(row))
        self.assertNotIn("method", json.dumps(row))

    def test_readme_invocation_verbatim(self):
        """The exact command printed in the README. If this file drifts from the
        README the README is what a stranger runs, so it is the thing to pin."""
        with tempfile.TemporaryDirectory() as tmp:
            rc = cli.main([
                "corrections", "add", "--corpus-dir", tmp,
                "--slug", "lands-a-verdict-not-a-neutral-read",
                "--instruction", "Take a side out loud and add the consequence.",
                "--quote", "I disagree with the band-aid. Leadership will point at it later."])
        self.assertEqual(rc, 0)

    def test_appends_never_rewrites(self):
        """Append-only is the project's stated contract, so it gets a test."""
        with tempfile.TemporaryDirectory() as tmp:
            cli.main(["corrections", "add", "--corpus-dir", tmp, "--slug", "one",
                      "--instruction", "First."])
            cli.main(["corrections", "add", "--corpus-dir", tmp, "--slug", "two",
                      "--instruction", "Second."])
            with open(os.path.join(tmp, "corrections.jsonl"), encoding="utf-8") as fh:
                rows = [json.loads(line) for line in fh if line.strip()]
        self.assertEqual([r["instruction"] for r in rows], ["First.", "Second."])


class Fingerprint(unittest.TestCase):

    def test_writes_bands_at_the_current_metrics_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            _corpus(tmp)
            rc = cli.main(["fingerprint", "--corpus-dir", tmp])
            self.assertEqual(rc, 0)
            doc = json.load(open(os.path.join(tmp, "fingerprint.json"), encoding="utf-8"))
        self.assertEqual(doc["metrics_version"], fingerprint.METRICS_VERSION)
        self.assertEqual(doc["corpus_size"], len(POSTS))
        self.assertTrue(doc["metrics"])

    def test_leaves_no_temp_file_behind(self):
        with tempfile.TemporaryDirectory() as tmp:
            _corpus(tmp)
            cli.main(["fingerprint", "--corpus-dir", tmp])
            self.assertNotIn("fingerprint.json.tmp", os.listdir(tmp))

    def test_empty_corpus_exits_one_without_a_traceback(self):
        """A fresh clone ships corpus/ with no exemplars ON PURPOSE, so this is
        the FIRST thing a new reader hits. compute() raises ValueError on an
        empty corpus; a stack trace there reads as a broken tool rather than as
        an empty inbox."""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(cli.main(["fingerprint", "--corpus-dir", tmp]), 1)
            self.assertFalse(os.path.exists(os.path.join(tmp, "fingerprint.json")))


class Validate(unittest.TestCase):

    def test_returns_an_int_and_survives_a_real_corpus(self):
        """check_all takes a DIRECTORY and returns a list of STRINGS. Both halves
        were wrong at this call site once, and the second half fails only at
        print time, which is after the exit code is already decided."""
        with tempfile.TemporaryDirectory() as tmp:
            _corpus(tmp)
            rc = cli.main(["validate", "--corpus-dir", tmp])
        self.assertIn(rc, (0, 1))

    def test_findings_are_strings_not_dicts(self):
        from voiceloop import validate
        with tempfile.TemporaryDirectory() as tmp:
            _corpus(tmp)
            for problem in validate.check_all(tmp):
                self.assertIsInstance(problem, str)


class TheLoopComposes(unittest.TestCase):

    def test_fingerprint_then_validate_reports_no_staleness(self):
        """THE gate assertion, and the reason 'it stopped crashing' is not the
        bar. validate hashes the POST-KIND corpus to decide whether the bands are
        current. A fingerprint command that computes over every kind writes a
        different corpus_sha, exits 0, and is then called stale by the very next
        validate -- two green commands and an unresolvable red gate between them."""
        with tempfile.TemporaryDirectory() as tmp:
            rows = POSTS + ["A note I emailed someone, which is not a post."]
            _corpus(tmp, rows)
            # make that last row a different kind, so the two selections differ
            path = os.path.join(tmp, "exemplars.jsonl")
            lines = open(path, encoding="utf-8").read().splitlines()
            last = json.loads(lines[-1])
            last["kind"] = "email"
            lines[-1] = json.dumps(last)
            open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")

            self.assertEqual(cli.main(["fingerprint", "--corpus-dir", tmp]), 0)
            from voiceloop import corpus, validate
            problems = validate.check_fingerprint_fresh(corpus.load(tmp))
        self.assertEqual(problems, [], f"fingerprint the CLI just wrote is not accepted: {problems}")


class ModuleEntryPoint(unittest.TestCase):

    def test_python_dash_m_runs(self):
        """`raise SystemExit(main)` without parens exits on a function object.
        The console script calls main() directly and never notices."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        proc = subprocess.run([sys.executable, "-m", "voiceloop.cli", "--help"],
                              cwd=root, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("voiceloop", proc.stdout)


if __name__ == "__main__":
    unittest.main()
