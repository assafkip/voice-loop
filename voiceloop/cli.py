"""The loop's command line: log a correction, recompute the fingerprint, validate.

`corrections add` is the ONE writer for corrections.jsonl and the whole point of
this project. Every other voice tool learns from what you published. This learns
from the delta between what the model wrote and what you rewrote, which is the
only place your actual preferences are legible.

A correction is a dated fact about what you wanted at a moment, so the trail of
how a voice changed stays readable. `add` only ever appends, and no command here
deletes a row or edits an instruction.

RETIREMENT IS NOT DELETION, and it is mandatory rather than optional. Corrections
accumulate into the prompt forever, and `validate.check_correction_share` refuses
a corpus whose rules crowd past 70% of the thinnest assembly. Its own remedy note
names the mechanism: "retiring a superseded rule is a one-field edit", because
`corpus.active_corrections` renders only `status == "active"`. So `retire` and
`supersede` flip that one field and record why, in place, keeping the row, its
instruction, its quote and its date. `list` and `show` read.

WHY THE READING PATH WAS NOT ENOUGH (measured 2026-09-08). The reference corpus
sat at 72% on both channels, over the ceiling, with 22 active rows against 1
retired. The status field, the validator and the ceiling all existed; the only
way to change a status was to hand-edit JSONL, so nobody did, and the arm of the
system that assembles the full prompt was a configuration the validator refused.
A lifecycle with no operator surface is a lifecycle nobody runs.

WHY THIS FILE HAS ITS OWN TEST (from a real defect). Every module this imports is
generated from the engine; this file is not, so an engine signature can move and
leave the call sites here calling a shape that no longer exists. That is exactly
what happened: all three subcommands crashed on a clean checkout while the suite
stayed green, because nothing imported the command line. tests/test_cli.py runs
each subcommand end to end for that reason. Do not delete it as redundant.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys

from . import corpus, echo, fingerprint, slop_shapes, validate


def _now():
    """Injected in one place so a test can pin it. Never read twice per run."""
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def _corrections_path(args):
    return os.path.join(args.corpus_dir, corpus.CORRECTIONS)


def _read_corrections(path):
    """EVERY row, retired ones included. `corpus.active_corrections` filters; a
    lifecycle command has to see what it is about to change."""
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(
                    f"{path}:{number} is not valid JSON ({exc}); "
                    f"nothing was changed") from exc
    return rows


def _write_corrections(path, rows):
    """THE rewriter, and the only one. Atomic, for the same reason `fingerprint`
    is: a half-written corrections file silently drops rules, and a dropped rule
    is one the model never sees again.

    `add` appends instead of coming through here on purpose, so a log that races
    a rewrite loses nothing. That makes this the one place two writers could
    collide, which is why it is one function and not a pattern repeated per
    subcommand."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(tmp, path)


def _find_correction(rows, correction_id):
    for row in rows:
        if row.get("id") == correction_id:
            return row
    known = ", ".join(r.get("id", "?") for r in rows) or "none"
    raise SystemExit(f"no correction with id {correction_id!r}; corpus holds: {known}")


def _corrections_list(args):
    rows = _read_corrections(_corrections_path(args))
    if not rows:
        print("no corrections logged yet")
        return 0
    shown = [r for r in rows
             if args.status in (None, "all") or r.get("status", "active") == args.status]
    for row in shown:
        scope = ",".join(row.get("scope") or []) or "all"
        instruction = (row.get("instruction") or "").replace("\n", " ")
        if len(instruction) > 72:
            instruction = instruction[:69] + "..."
        print(f"{row.get('status', 'active'):9} {row.get('date', '?'):10} "
              f"{row.get('id', '?'):32} [{scope}] {instruction}")
    active = sum(1 for r in rows if r.get("status", "active") == "active")
    print(f"\n{len(shown)} shown, {active} active of {len(rows)} total")
    return 0


def _corrections_show(args):
    rows = _read_corrections(_corrections_path(args))
    row = _find_correction(rows, args.id)
    print(json.dumps(row, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _corrections_retire(args):
    """Off 'active', with the reason kept. The row and its instruction stay."""
    path = _corrections_path(args)
    rows = _read_corrections(path)
    row = _find_correction(rows, args.id)
    if row.get("status") == "retired":
        print(f"{args.id} is already retired ({row.get('retired_reason', 'no reason recorded')})")
        return 0
    row["status"] = "retired"
    row["retired_at"] = args.at or _dt.date.today().isoformat()
    row["retired_reason"] = args.reason
    _write_corrections(path, rows)
    print(f"correction {args.id} retired; it no longer rides in the assembled prompt")
    return 0


def _corrections_supersede(args):
    """One act, because two are how a corpus ends up carrying both rules.

    The replacement is appended active and carries `supersedes`, the old row is
    retired and carries `superseded_by`. Doing this as `add` then `retire` is the
    same two writes with a window in between where the prompt holds both rules,
    and that window is how the share ceiling was reached in the first place.
    """
    path = _corrections_path(args)
    rows = _read_corrections(path)
    old = _find_correction(rows, args.id)
    today = _dt.date.today().isoformat()
    new_id = args.new_id or f"{today}-{args.slug}"
    if any(r.get("id") == new_id for r in rows):
        raise SystemExit(f"a correction with id {new_id!r} already exists")
    replacement = {
        "id": new_id,
        "date": args.at or today,
        "quote": args.quote or old.get("quote") or "",
        "instruction": args.instruction,
        "scope": args.scope if args.scope is not None else (old.get("scope") or []),
        "class": args.klass or old.get("class") or "interpretive",
        "status": "active",
        "supersedes": old["id"],
    }
    old["status"] = "retired"
    old["retired_at"] = args.at or today
    old["retired_reason"] = f"superseded by {new_id}"
    old["superseded_by"] = new_id
    _write_corrections(path, rows + [replacement])
    print(f"correction {new_id} replaces {old['id']}; {old['id']} is retired")
    return 0


def _corrections_add(args):
    today = _dt.date.today().isoformat()
    row = {
        "id": args.id or f"{today}-{args.slug}",
        "date": args.at or today,
        "quote": args.quote or "",
        "instruction": args.instruction,
        "scope": args.scope or [],
        "class": args.klass,
        "status": "active",
    }
    path = os.path.join(args.corpus_dir, corpus.CORRECTIONS)
    os.makedirs(args.corpus_dir, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"correction {row['id']} recorded; it rides in the next assembled prompt")
    return 0


def _fingerprint(args):
    voice = corpus.load(args.corpus_dir)
    # POST-KIND ONLY, and this is load-bearing (from a real defect). The freshness
    # check in validate.check_fingerprint_fresh hashes the post-kind corpus. A
    # fingerprint computed over every kind writes a different corpus_sha, so the
    # very next `validate` reports the file this command just wrote as stale. The
    # two selections have to be the same selection.
    texts = [r.get("text") or "" for r in voice.active_exemplars()
             if r.get("kind") == "post"]
    if not texts:
        print(f"no post-kind exemplars in {args.corpus_dir}/{corpus.EXEMPLARS}; "
              f"add your own writing before fingerprinting", flush=True)
        return 1
    doc = fingerprint.compute(texts, _now())
    out = os.path.join(args.corpus_dir, corpus.FINGERPRINT)
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, indent=1, sort_keys=True)
    os.replace(tmp, out)          # atomic: a half-written fingerprint is worse than none
    print(f"fingerprint written to {out} from {len(texts)} post-kind exemplar(s)")
    return 0



def _score(args):
    """Score ARBITRARY text against the corpus. The command that makes this
    usable from outside the repo that owns the corpus.

    why this exists (2026-08-29): every other subcommand acts on the corpus.
    There was no way to ask the one question a writer actually has, which is
    "does THIS draft read like me", without importing the package and wiring the
    calls by hand. So the engine was reachable only by people willing to write
    Python, and a draft written anywhere else went unchecked.

    Report, never a rewrite. It says which measured bands the draft falls outside
    and which deterministic gates it trips. It cannot say the draft is GOOD; a
    clean result means nothing is detectably wrong, which is a different claim and
    the README is explicit about the difference.
    """
    text = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8").read()
    if not text.strip():
        print("nothing to score: empty input", file=sys.stderr)
        return 2

    voice = corpus.load(args.corpus_dir)
    problems = []
    notes = []

    # 1. Style distance, only if a fingerprint exists. No fingerprint is a REASON,
    #    not a silent pass: without measured bands there is nothing to be far from.
    if voice.fingerprint is None:
        problems.append(("fingerprint", "no fingerprint.json; run `voiceloop fingerprint` "
                                        "to compute bands before scoring distance"))
    else:
        for metric in fingerprint.out_of_band(text, voice.fingerprint, tier="blocking"):
            detail = fingerprint.score(text, voice.fingerprint).get(metric, {})
            problems.append(("band", f"{metric}: {detail.get('value')} outside "
                                     f"{detail.get('band')}"))

    # 2. Templated shapes. Deterministic, corpus-independent.
    for hit in slop_shapes.check(text):
        problems.append(("shape", hit if isinstance(hit, str) else str(hit)))

    # 3. Verbatim reuse of the author's own exemplars. The text most likely to be
    #    echoed is the text the model was shown, which is why this is checked.
    exemplar_texts = [r.get("text") or "" for r in voice.active_exemplars()]
    if exemplar_texts:
        for hit in echo.prompt_echo(text, exemplar_texts) or []:
            problems.append(("echo", f"reuses corpus phrasing: {hit!r}"))

    # 4. Banned vocabulary, and an HONEST REPORT when there is none.
    #
    # This looks for a `negative` list, which is the schema corpus/lexicon.json
    # ships. A real corpus may key its lexicon differently, and when it does this
    # branch finds nothing and says so rather than staying quiet. Measured
    # 2026-08-29: a lexicon with keys `prefer`/`voiceprint_terms`/`contraction_pairs`
    # produced ZERO findings on "excited to announce a revolutionary, best in class
    # solution that will supercharge your workflow" -- text nobody would call
    # on-voice. A vocabulary check that silently checks nothing is worse than no
    # check, because the clean result reads as a pass.
    banned = (voice.lexicon or {}).get("negative") or []
    for word in banned:
        if re.search(rf"\b{re.escape(str(word))}\b", text, re.I):
            problems.append(("lexicon", f"banned term: {word!r}"))
    if not banned:
        notes.append("no `negative` list in lexicon.json, so VOCABULARY WAS NOT "
                     "CHECKED. Bands, shapes and echo were.")

    for kind, detail in problems:
        print(f"{kind}: {detail}")
    for note in notes:
        print(f"NOT CHECKED: {note}")
    print(f"{len(problems)} finding(s) against {len(exemplar_texts)} exemplar(s)")
    # A clean result means nothing DETECTABLE is wrong. Every check here is a NO
    # check; none of them can say the draft is good. The README says this too.
    return 1 if problems else 0


def _validate(args):
    # check_all returns a list of STRINGS and takes the corpus DIRECTORY. Both
    # halves of that were wrong here once; the shapes are asserted in test_cli.py.
    problems = validate.check_all(args.corpus_dir)
    for problem in problems:
        print(f"error: {problem}")
    print(f"{len(problems)} finding(s)")
    return 1 if problems else 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="voiceloop", description="the voice loop")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--corpus-dir", default=os.environ.get("VOICE_LOOP_CORPUS", "corpus"))
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("fingerprint", parents=[common],
                   help="recompute the measured bands from your exemplars")
    sub.add_parser("validate", parents=[common], help="check the corpus for problems")
    p_score = sub.add_parser("score", parents=[common],
                             help="score any text against your corpus")
    p_score.add_argument("file", nargs="?", default="-",
                         help="file to score, or - for stdin (default)")

    p_corr = sub.add_parser("corrections", help="the loop").add_subparsers(
        dest="subcmd", required=True)
    p_add = p_corr.add_parser("add", parents=[common],
                              help="log what you changed and why")
    p_add.add_argument("--instruction", required=True,
                       help="what the next draft should do differently")
    p_add.add_argument("--slug", required=True, help="kebab-case id suffix")
    p_add.add_argument("--quote", help="your own words, verbatim")
    p_add.add_argument("--scope", nargs="*", help="channels; empty means all")
    p_add.add_argument("--class", dest="klass", default="interpretive",
                       choices=["deterministic", "interpretive"])
    p_add.add_argument("--id")
    p_add.add_argument("--at")

    p_list = p_corr.add_parser("list", parents=[common],
                               help="every correction and its status")
    p_list.add_argument("--status", choices=["active", "promoted", "retired", "all"],
                        help="filter; default shows all")
    p_show = p_corr.add_parser("show", parents=[common],
                               help="one correction, whole row")
    p_show.add_argument("id")
    p_retire = p_corr.add_parser(
        "retire", parents=[common],
        help="stop a correction riding in the prompt, keeping the row")
    p_retire.add_argument("id")
    p_retire.add_argument("--reason", required=True,
                          help="why it no longer applies; kept on the row")
    p_retire.add_argument("--at")
    p_sup = p_corr.add_parser(
        "supersede", parents=[common],
        help="replace a correction with a newer one, in one act")
    p_sup.add_argument("id", help="the correction being replaced")
    p_sup.add_argument("--instruction", required=True)
    p_sup.add_argument("--slug", required=True, help="kebab-case id suffix")
    p_sup.add_argument("--quote", help="defaults to the replaced row's quote")
    p_sup.add_argument("--scope", nargs="*", help="defaults to the replaced row's scope")
    p_sup.add_argument("--class", dest="klass",
                       choices=["deterministic", "interpretive"])
    p_sup.add_argument("--new-id", dest="new_id")
    p_sup.add_argument("--at")

    args = parser.parse_args(argv)
    if args.cmd == "fingerprint":
        return _fingerprint(args)
    if args.cmd == "score":
        return _score(args)
    if args.cmd == "validate":
        return _validate(args)
    if args.cmd == "corrections":
        # Dispatch on SUBCMD. It used to run `add` for anything under
        # `corrections`, which was invisible while `add` was the only one.
        return {
            "add": _corrections_add,
            "list": _corrections_list,
            "show": _corrections_show,
            "retire": _corrections_retire,
            "supersede": _corrections_supersede,
        }[args.subcmd](args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
