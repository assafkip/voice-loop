"""The loop's command line: log a correction, recompute the fingerprint, validate.

`corrections add` is the ONE writer for corrections.jsonl and the whole point of
this project. Every other voice tool learns from what you published. This learns
from the delta between what the model wrote and what you rewrote, which is the
only place your actual preferences are legible.

Append-only on purpose. A correction is a dated fact about what you wanted at a
moment, not a setting to be edited later. Superseding one means writing a newer
row, so the trail of how a voice changed stays readable.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os

from . import corpus, fingerprint, validate


def _corrections_add(args):
    row = {
        "id": args.id or f"{_dt.date.today.isoformat}-{args.slug}",
        "date": args.at or _dt.date.today.isoformat,
        "quote": args.quote or "",
        "instruction": args.instruction,
        "scope": args.scope or [],
        "class": args.klass,
        "status": "active",
    }
    path = os.path.join(args.corpus_dir, corpus.CORRECTIONS)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"correction {row['id']} recorded; it rides in the next assembled prompt")
    return 0


def _fingerprint(args):
    voice = corpus.load(args.corpus_dir)
    doc = fingerprint.compute(voice)
    out = os.path.join(args.corpus_dir, corpus.FINGERPRINT)
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, indent=1, sort_keys=True)
    os.replace(tmp, out)          # atomic: a half-written fingerprint is worse than none
    print(f"fingerprint written to {out} from {len(voice.exemplars)} exemplar(s)")
    return 0


def _validate(args):
    findings = validate.check(corpus.load(args.corpus_dir))
    for f in findings:
        print(f"{f.get('level', 'warn')}: {f.get('detail', f)}")
    print(f"{len(findings)} finding(s)")
    return 1 if any(f.get("level") == "error" for f in findings) else 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="voiceloop", description="the voice loop")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--corpus-dir", default=os.environ.get("VOICE_LOOP_CORPUS", "corpus"))
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("fingerprint", parents=[common],
                   help="recompute the measured bands from your exemplars")
    sub.add_parser("validate", parents=[common], help="check the corpus for problems")

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

    args = parser.parse_args(argv)
    if args.cmd == "fingerprint":
        return _fingerprint(args)
    if args.cmd == "validate":
        return _validate(args)
    if args.cmd == "corrections":
        return _corrections_add(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main)
