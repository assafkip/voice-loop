"""The gate that came from OUTSIDE this system's scars, so its corpus sweep is a test.

`slop_shapes` blocks. Every other blocking word-pattern in this repo earned that
posture from a failure we watched; this one came from the founder's research
(2026-08-20). The standing scar is that list-based gates catch the founder -- six
once blocked his real vocabulary in a single session -- so the sweep that justified
blocking runs here on the LIVE corpus, not once in a session transcript.
"""
import json
import os

from voiceloop import form, slop_shapes

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


def _corpus():
    _skip_without_a_corpus()
    with open(CORPUS, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


#: HIS REAL PUBLISHED USES OF A BLOCKED SHAPE, founder-directed 2026-09-04.
#: He was given the fork this test names and chose to keep the gate and record
#: the exceptions: the gate exists to stop the MODEL staging a reveal, and he
#: writes what he likes.
#:
#: MEASURED before allowlisting, across all 1,151 of his authored LinkedIn
#: posts (the 2026-09-04 apify history pull), not against the corpus sample:
#: he uses `slop-dramatic-pause` in 6 of them, 0.5%. Every instance is `why?`
#: (3) or `the result?` (3). He has never written `the catch?`, `the kicker?`
#: or `the problem?` in thirteen years. Usage is RISING -- one in 2024, three
#: in 2025, two in 2026 -- so if this list keeps growing, the gate is arguing
#: with him and not with a machine, and that is the moment to reconsider it.
#:
#: Each entry is (row id, rule). The list is EXHAUSTIVE and a new hit still
#: fails, which is the property that makes this an allowlist and not an
#: exemption. Never add a row here to make a red test green: the whole point
#: of the failure is that it is loud.
HIS_MEASURED_USES = {
    ("li-2025-10-14-trust-safety-will-always-be-a", "slop-dramatic-pause"),
    ("li-2025-09-07-reading-this-made-me-sick-because", "slop-dramatic-pause"),
}

class TestTheResearchExamplesAllFire:
    """The four verbatim examples from social-writing-method.md section 14g. If a
    pattern stops matching the sentence it was written for, the gate is decoration."""

    def test_contrast_bridge(self):
        assert slop_shapes.check(
            "That is not a branding question. It is a system question.")

    def test_dramatic_pause(self):
        assert slop_shapes.check(
            "Records were missing. The result? Deals slipped through.")

    def test_false_secret(self):
        assert slop_shapes.check(
            "Here is what nobody tells you about data engineering.")

    def test_generic_advice_frame(self):
        assert slop_shapes.check("Stop chasing likes. Start solving problems.")


class TestHisOwnCorpusStaysClean:
    """THE justification for blocking, re-run on the live file.

    Measured 0 of 103 on 2026-08-20. If he ever writes one of these shapes, this
    fails and the gate is reconsidered -- which is the point. A gate that silently
    starts blocking its own author is the failure this test exists to make loud.
    """

    def test_no_false_positive_anywhere_in_the_corpus(self):
        hits = [(row.get("id"), v["rule"])
                for row in _corpus()
                for v in slop_shapes.check(row.get("text") or "")
                if (row.get("id"), v["rule"]) not in HIS_MEASURED_USES]
        assert hits == [], (
            f"slop_shapes now blocks writing the founder actually published: {hits}. "
            f"Either the pattern widened past its evidence or he has started using "
            f"the shape. Do not narrow the corpus to make this pass.")

    def test_the_rejected_loose_variant_is_still_rejected(self):
        """A bare negation opener was considered and refused as a pattern.

        `organic-false-dilemma` is his and opens that way. This pins the DECISION,
        not the code: if someone later widens the contrast-bridge pattern to catch a
        lone "This isn't...", that post starts failing and this test says why.
        """
        row = next((r for r in _corpus() if r.get("id") == "organic-false-dilemma"), None)
        assert row is not None, "the post this decision rests on left the corpus"
        assert slop_shapes.check(row["text"]) == []


class TestItReachesTheRealGateStack:
    """The gate's own posture. The decide-stack wiring proof lives in
    `test_verify_covers_every_gate.py`, because `decide` is this instance's gate
    orchestrator and is not part of the portable package this module ships in."""

    def test_it_is_not_warn_only(self):
        rows = slop_shapes.check("Stop chasing likes. Start solving problems.")
        assert rows and not any(r.get("warn_only") for r in rows)


class TestTheWideningIsSafeOnHisOwnCorpus:
    """The 2026-08-20 widening, held to the same bar as the original four.

    why this test and not a code comment: the constraint-ledger row for this gate
    records that a looser variant was measured and REJECTED because it hit
    `organic-false-dilemma`, a post he actually wrote. That is the whole risk of a
    pattern gate here, and `word-lists-catch-the-founder` is a standing scar. A
    number in a comment rots; this re-measures on every run against the live corpus,
    so a row added to `voice/exemplars.jsonl` tomorrow that trips a shape turns this
    red instead of silently blocking his own voice in production.
    """

    def _corpus(self):
        _skip_without_a_corpus()
        import json, os
        path = form.corpus_path()
        rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
        return [(r.get("id"), r["text"]) for r in rows
                if r.get("text") and r.get("generated") is not True
                and r.get("eligible_for_voice_reference") is not False
                and r.get("status") != "retired"]

    def test_no_shape_fires_on_anything_he_wrote(self):
        from voiceloop import slop_shapes
        corpus = self._corpus()
        if not corpus:
            import pytest
            pytest.skip("no corpus here; this package ships with an empty one and the "
                        "sweep is only meaningful against a real author's writing")
        assert len(corpus) >= 100, "corpus shrank; re-check the bar before trusting this"
        # Same allowlist as TestHisOwnCorpusStaysClean, read from the one constant
        # rather than restated. Two copies of "which of his posts are known" is how
        # an allowlist quietly becomes an exemption in one of the two places.
        caught = {}
        for rid, t in corpus:
            fired = [v for v in slop_shapes.check(t)
                     if (rid, v["rule"]) not in HIS_MEASURED_USES]
            if fired:
                caught[t[:60]] = fired
        assert caught == {}, f"a slop shape fires on his own writing: {list(caught)}"

    def test_the_two_new_shapes_are_actually_present(self):
        """A widening that got reverted leaves this test green and useless otherwise."""
        from voiceloop import slop_shapes
        names = {name for name, _pat, _instead in slop_shapes.SHAPES}
        assert {"slop-contrast-parallel", "slop-aphorism-close"} <= names

    def test_each_new_shape_catches_the_draft_that_motivated_it(self):
        from voiceloop import slop_shapes
        parallel = ("A system that fails loudly gets fixed. A system where two signals "
                    "quietly disagree half the time just keeps shipping decisions.")
        aphorism = "You can't fix what you haven't counted."
        assert any(v.get("rule") == "slop-contrast-parallel"
                   for v in slop_shapes.check(parallel))
        assert any(v.get("rule") == "slop-aphorism-close"
                   for v in slop_shapes.check(aphorism))
