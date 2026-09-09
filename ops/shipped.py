# -*- coding: utf-8 -*-
"""The block that goes at the end of "done".

Four facts, every time: what shipped, where to read it, what ran, and -- the
one he asked for by name -- whether anything opened the running thing after
the deploy.

Generated rather than typed. A hand-written footer carries a stale sha
eventually, and the whole value of this one is that he can trust it without
checking.

    python ops/shipped.py
    python ops/shipped.py --tag v1.2.0 --tests "44 labels, 0 errors" \
        --live "knob rejoined 11:15, wifi_signal published -86"

Ported from health-mcp/ops/shipped.py, which is the original. The format is
deliberately identical -- three lines, the same two links -- so a release
here reads the same as a release there.

WHAT IS DIFFERENT, and why: health-mcp reads what is live from a deploy
record its release engine writes. A knob has no such record, because its
deploy is a person running `esphome run` at a device. Until one exists
--tag is how you say which release you mean, and with no --tag this
describes the newest tag rather than claiming to know what is on the
hardware. It never guesses: a tag is not evidence that a device is running
it.

--live is a plain string and nothing here checks it. What makes it worth
reading is ops/verify.py, which refuses rather than passing when it cannot
look. Do not write this line by hand.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FALLBACK_SLUG = "tomereli/coffee-knob"


def git(*args: str) -> str:
    out = subprocess.run(["git", "-C", str(REPO)] + list(args),
                         capture_output=True, text=True, encoding="utf-8",
                         errors="replace")
    return out.stdout.strip() if out.returncode == 0 else ""


def slug() -> str:
    found = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$",
                      git("remote", "get-url", "origin").strip())
    return found.group(1) if found else FALLBACK_SLUG


def previous_tag(tag: str) -> str | None:
    tags = [t for t in git("tag", "--sort=creatordate").splitlines() if t.strip()]
    if tag not in tags:
        return None
    index = tags.index(tag)
    return tags[index - 1] if index else None


def build(tag: str, tests: str, live: str) -> str:
    repo = slug()
    sha = git("rev-list", "-n", "1", tag)[:7] or git("rev-parse", "--short", "HEAD")
    prev = previous_tag(tag)
    lines = ["%s · `%s`" % (tag, sha)]
    # No previous tag means no compare view exists, so the link is absent
    # rather than pointing at nothing.
    lines.append("[release](https://github.com/%s/releases/tag/%s)" % (repo, tag) +
                 (" · [diff](https://github.com/%s/compare/%s...%s)" % (repo, prev, tag)
                  if prev else ""))
    tail = [part for part in (tests, live) if part]
    if tail:
        lines.append(" · ".join(tail))
    return "\n".join(lines)


def main(argv=None) -> int:
    # The block is Hebrew as often as not and this runs under a console whose
    # default codec cannot represent it: printing would raise rather than
    # produce the one thing the script exists for.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default=None, help="which release")
    parser.add_argument("--tests", default="", help='what ran')
    parser.add_argument("--live", default="",
                        help="what was checked against the running device; "
                             "leave empty if nothing was, and say so in prose")
    args = parser.parse_args(argv)

    tag = args.tag or git("describe", "--tags", "--abbrev=0")
    if not tag:
        print("no tag to describe -- `git tag -a vX.Y.Z` first, or the two "
              "links in this block would point at nothing")
        return 1
    print(build(tag, args.tests, args.live))
    return 0


if __name__ == "__main__":
    sys.exit(main())
