"""Form: is the draft SHAPED like him. The half `luar_scorer` never measured."""
import json
import os

from voiceloop import form

# One definition of where the corpus is, and it is the module's own. These tests
# ship in two packages that name the directory differently; a path rebuilt here is a
# second source of truth that works in exactly one of them.
CORPUS = form.corpus_path()


def _skip_without_a_corpus():
    """This package ships an empty corpus on purpose: the engine is public, the
    author's writing is not. A sweep over no rows proves nothing, so it skips rather
    than passing vacuously or failing on someone else's checkout."""
    import pytest
    if not os.path.exists(CORPUS) or os.path.getsize(CORPUS) == 0:
        pytest.skip("no corpus in this checkout; bring your own to run the sweep")


class TestThePopulationIsPostsOnly:
    """The bug that made the first read of this corpus wrong.

    LinkedIn holds 24 posts, 10 article-excerpts and 3 comments. Measuring all 37
    moves the median from 808 to 756 and stretches the range to 2449, which reads as
    "he writes long" and is an artifact of grading articles as posts. That mistake
    produced a written conclusion that his corpus DISAGREED with the founder's
    research. It agrees.
    """

    def test_excerpts_and_comments_are_excluded(self):
        _skip_without_a_corpus()
        with open(CORPUS, encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle if line.strip()]
        texts = form.corpus_posts("linkedin")
        for row in rows:
            if row.get("channel") == "linkedin" and row.get("kind") in ("article-excerpt",
                                                                       "comment"):
                assert row["text"] not in texts, row.get("id")

    def test_a_generated_row_can_never_shape_the_reference(self):
        """Same refusal `luar_scorer.usable_as_reference` makes. Two definitions of
        'may this row speak for him' is how a decontamination misses a consumer."""
        assert form._usable({"generated": True, "text": "x", "kind": "post"}) is False
        assert form._usable({"eligible_for_voice_reference": False, "text": "x"}) is False
        assert form._usable({"status": "retired", "text": "x"}) is False


class TestTheBandsAreDerivedNotCopied:
    def test_linkedin_bands_come_from_the_live_corpus(self):
        _skip_without_a_corpus()
        band = form.bands("linkedin")
        assert band and band["n"] >= 8
        assert band["chars"]["p25"] < band["chars"]["median"] < band["chars"]["p75"]

    def test_a_thin_corpus_refuses_rather_than_guessing(self, tmp_path):
        _skip_without_a_corpus()
        """A quartile from three rows is a number with a hidden confidence interval,
        and it would be read as his practice."""
        thin = tmp_path / "thin.jsonl"
        thin.write_text("\n".join(json.dumps(
            {"channel": "linkedin", "kind": "post", "text": "short one."})
            for _ in range(3)), encoding="utf-8")
        assert form.bands("linkedin", path=str(thin)) is None

    def test_no_median_is_hardcoded_in_the_module(self):
        """The derivation split this repo keeps writing scars about: a copied median
        stops being true the day he writes another post."""
        with open(form.__file__, encoding="utf-8") as handle:
            code = [l for l in handle if not l.strip().startswith("#")]
        body = "".join(code).split('"""', 2)[-1]
        for stale in ("808", "756", "1200"):
            assert stale not in body, f"{stale} is hardcoded; derive it"


class TestItCatchesWhatTwelveDraftsMissed:
    def test_a_long_hook_is_flagged(self):
        _skip_without_a_corpus()
        long_hook = ("I pulled 30 days of run history on a client's extraction job, "
                     "automation they already owned and had trusted for a while. Rows "
                     "stopped.")
        flags = form.report(long_hook, "linkedin")["flags"]
        assert any("hook runs long" in f for f in flags)

    def test_an_overlong_post_is_flagged(self):
        _skip_without_a_corpus()
        rep = form.report("word. " * 400, "linkedin")
        assert any("longer than he writes" in f for f in rep["flags"])

    def test_it_can_fail_in_the_OTHER_direction(self):
        _skip_without_a_corpus()
        """The negative self-test. A checker that only ever says 'too long' is not
        measuring a band, it is applying a cap."""
        rep = form.report("Rows stopped.", "linkedin")
        assert any("shorter than he writes" in f for f in rep["flags"])


class TestXFollowsTheAlgorithmNotTheCorpus:
    """Founder call 2026-08-20, and the one place form deliberately departs from his
    corpus. His X median is 133; the dwell floor is 280."""

    def test_a_short_x_post_is_flagged_against_the_dwell_floor(self):
        _skip_without_a_corpus()
        rep = form.report("Nobody watched the input.", "x")
        assert rep["char_rule"]["kind"] == "dwell-floor"
        assert any("dwell floor" in f for f in rep["flags"])

    def test_linkedin_still_uses_his_corpus_band(self):
        _skip_without_a_corpus()
        assert form.report("x" * 900, "linkedin")["char_rule"]["kind"] == "corpus-band"

    def test_his_x_corpus_is_still_reported_even_though_it_does_not_rule(self):
        _skip_without_a_corpus()
        """Departing from his corpus is a decision, not a reason to hide it."""
        rep = form.report("short", "x")
        assert rep["corpus"]["chars"]["median"] > 0
