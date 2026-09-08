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


class TestCorrectionLifecycle(unittest.TestCase):
    """retire / supersede / list / show, run as commands against a real corpus.

    WHY (measured 2026-09-08). `validate.check_correction_share` refused the
    reference corpus at 72% on both channels and its own message says the remedy
    is retirement. Nothing on the command line could retire anything: the
    `corrections` branch of main() called `_corrections_add` whatever subcommand
    was typed. So the only way to clear the ceiling was hand-editing JSONL, and
    the full-prompt configuration stayed one the validator would not pass.

    Each test asserts on what the LOADER sees, not on the printed line, because
    the thing that matters is whether the rule still reaches the prompt.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _corpus(self.tmp)
        self.assertEqual(0, cli.main([
            "corrections", "add", "--corpus-dir", self.tmp,
            "--slug", "no-questions", "--instruction", "Never open on a question.",
            "--quote", "stop asking me things", "--scope", "x"]))

    def _rows(self):
        path = os.path.join(self.tmp, "corrections.jsonl")
        with open(path, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def _active(self):
        from voiceloop import corpus as _c
        return [r["id"] for r in _c.load(self.tmp).active_corrections()]

    def test_a_new_correction_reaches_the_prompt(self):
        # The negative control for every assertion below: if this is empty the
        # retire tests would pass for the wrong reason.
        self.assertEqual(1, len(self._active()))

    def test_retire_takes_the_rule_out_of_the_prompt_and_keeps_the_row(self):
        target = self._rows()[0]["id"]
        self.assertEqual(0, cli.main([
            "corrections", "retire", target, "--corpus-dir", self.tmp,
            "--reason", "the shape rule replaced it"]))
        self.assertEqual([], self._active())
        row = self._rows()[0]
        self.assertEqual("retired", row["status"])
        self.assertEqual("the shape rule replaced it", row["retired_reason"])
        # NOT deletion: the instruction and the quote survive the retirement.
        self.assertEqual("Never open on a question.", row["instruction"])
        self.assertEqual("stop asking me things", row["quote"])
        self.assertEqual(1, len(self._rows()))

    def test_supersede_leaves_exactly_one_rule_active_and_links_both_ways(self):
        old_id = self._rows()[0]["id"]
        self.assertEqual(0, cli.main([
            "corrections", "supersede", old_id, "--corpus-dir", self.tmp,
            "--slug", "open-on-the-claim",
            "--instruction", "Open on the claim or the event."]))
        active = self._active()
        self.assertEqual(1, len(active), "both rules rode the prompt at once")
        rows = {r["id"]: r for r in self._rows()}
        new_id = active[0]
        self.assertEqual(old_id, rows[new_id]["supersedes"])
        self.assertEqual(new_id, rows[old_id]["superseded_by"])
        self.assertEqual("retired", rows[old_id]["status"])
        # scope and class are inherited, so a replacement cannot silently widen
        # which channels the rule governs.
        self.assertEqual(["x"], rows[new_id]["scope"])

    def test_retiring_an_unknown_id_changes_nothing(self):
        before = self._rows()
        with self.assertRaises(SystemExit):
            cli.main(["corrections", "retire", "does-not-exist",
                      "--corpus-dir", self.tmp, "--reason", "x"])
        self.assertEqual(before, self._rows())
        self.assertEqual(1, len(self._active()))

    def test_list_and_show_read_without_writing(self):
        before = self._rows()
        self.assertEqual(0, cli.main(["corrections", "list", "--corpus-dir", self.tmp]))
        self.assertEqual(0, cli.main(["corrections", "show", before[0]["id"],
                                      "--corpus-dir", self.tmp]))
        self.assertEqual(before, self._rows())


class TestReviewRuns(unittest.TestCase):
    """`voiceloop review`: the full non-generation path, run as a command.

    WHY (2026-09-08). The package ships 35 modules and the command line reached
    four. The gate roster, the channel length rules, the figure check and the form
    read were reachable only by writing Python, so the published product was
    smaller than the source and the gap was invisible from outside.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _corpus(self.tmp)
        cli.main(["fingerprint", "--corpus-dir", self.tmp])

    def _run(self, argv):
        import io as _io
        import contextlib
        buf = _io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli.main(argv)
        return code, buf.getvalue()

    def test_review_runs_gates_that_score_does_not(self):
        path = os.path.join(self.tmp, "d.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("Ship it by [DATE] once the review clears and the log is quiet.")
        _, review_out = self._run(["review", path, "--corpus-dir", self.tmp])
        _, score_out = self._run(["score", path, "--corpus-dir", self.tmp])
        # placeholder_gate is in the review roster and in no part of score. If this
        # ever passes for both, review has stopped adding anything.
        assert "[DATE]" in review_out or "placeholder" in review_out, review_out
        assert "[DATE]" not in score_out and "placeholder" not in score_out, score_out

    def test_a_post_is_never_measured_against_the_reply_band(self):
        """THE FIRST LIVE RUN'S DEFECT. The roster called reply_format on every
        draft, so a 34-word POST came back "reply-too-short: below the 35-word floor
        measured from his own approved comments" -- a floor for a comment on someone
        else's thread, which says nothing about a post."""
        path = os.path.join(self.tmp, "short.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("One capability marked blocked, no date on the label, and nothing "
                     "wired to re-run the check. It is furniture now.")
        _, as_post = self._run(["review", path, "--corpus-dir", self.tmp])
        assert "reply-too-short" not in as_post, as_post
        # The negative control: the same text under --kind reply DOES trip it, so
        # this test cannot pass by the gate having been deleted.
        _, as_reply = self._run(["review", path, "--corpus-dir", self.tmp,
                                 "--kind", "reply", "--channel", "linkedin"])
        assert "reply-too-short" in as_reply, as_reply

    def test_a_channel_with_no_reply_band_is_reported_not_raised(self):
        """reply_format.band RAISES on an unknown channel and gate_walk deliberately
        does not catch, so this aborted the whole review instead of skipping a gate."""
        path = os.path.join(self.tmp, "r.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("A short one about a check that cannot fail.")
        code, out = self._run(["review", path, "--corpus-dir", self.tmp,
                               "--kind", "reply", "--channel", "reddit"])
        assert code in (0, 1), f"review aborted instead of reporting: {out}"
        assert "REPLY LENGTH WAS NOT CHECKED" in out, out

    def test_review_names_what_it_did_not_check(self):
        """A clean deterministic result is not a verdict that the draft is good, and
        the model-backed parts of this engine do not run here."""
        path = os.path.join(self.tmp, "d.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("A check that cannot fail is decoration. Name the input that "
                     "turns it red, or delete it and stop pretending you have coverage.")
        _, out = self._run(["review", path, "--corpus-dir", self.tmp])
        assert "NOT CHECKED: the semantic critic" in out, out
        assert "FIGURES WERE NOT CHECKED" in out, out
