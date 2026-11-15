# -*- coding: utf-8 -*-
"""Does a temperature written through Home Assistant reach the machine?

    python ops/write_check.py                 # read only: what the machine holds now
    python ops/write_check.py --set 94.6      # WRITES the machine, then reads it back

This is the knob's temperature write made from the PC instead, and judged
the same way the knob now judges it (issue #2): by the value the machine
reports back, not by Home Assistant answering 200.

Without --set it changes nothing. With --set it changes the coffee boiler
target on a real machine that may be hot, so it is never run by an agent or
a schedule without Tomer saying so for that run.

Exit codes, the same as ops/verify.py:
    0  the machine reports the value that was sent
    1  the write was refused, or accepted and never showed up
    2  could not look -- no HA_URL/HA_TOKEN, Home Assistant unreachable, or
       the entity missing. Never reported as a pass.

The self-clean start is deliberately not here: proving it means moving the
paddle, which a script cannot do.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify import CouldNotLook, ha_state  # noqa: E402

ENTITY = "number.la_minea_micra_coffee_target_temperature"
# The knob gives the machine this long (temp_confirm_ms) before calling a
# write ignored. A PC on the same LAN gets the same allowance and a little more.
CONFIRM_S = 10.0


def set_value(entity: str, value: float) -> tuple[int, str]:
    """Call number.set_value and return HA's status and body, whatever they are."""
    url = os.environ.get("HA_URL", "").rstrip("/")
    token = os.environ.get("HA_TOKEN", "")
    if not url or not token:
        raise CouldNotLook("HA_URL and HA_TOKEN are not both set")
    body = json.dumps({"entity_id": entity, "value": value}).encode("utf-8")
    request = urllib.request.Request(
        "%s/api/services/number/set_value" % url, data=body, method="POST",
        headers={"Authorization": "Bearer " + token,
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        # A refusal is an answer, not a failure to look: HA says 400/500 with
        # the integration's message in the body. That message is the point.
        return error.code, error.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError) as error:
        raise CouldNotLook("could not reach Home Assistant: %s" % error)


def as_float(state: dict) -> float | None:
    try:
        return float(state.get("state"))
    except (TypeError, ValueError):
        return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--set", type=float, default=None, metavar="CELSIUS",
                        help="write this target and read it back (changes the machine)")
    parser.add_argument("--entity", default=ENTITY)
    args = parser.parse_args(argv)

    try:
        before = ha_state(args.entity)
    except CouldNotLook as why:
        print("NOT CHECKED: %s" % why)
        return 2
    held = as_float(before)
    print("machine holds %s (last changed %s)"
          % (before.get("state"), before.get("last_changed")))
    if args.set is None:
        print("read only -- pass --set to test a write")
        return 0 if held is not None else 2

    try:
        status, text = set_value(args.entity, args.set)
    except CouldNotLook as why:
        print("NOT CHECKED: %s" % why)
        return 2
    print("number.set_value %.1f -> HTTP %d %s" % (args.set, status, text.strip()[:300]))
    if status >= 400:
        print("REFUSED: Home Assistant refused the write; the machine still holds %s"
              % before.get("state"))
        return 1

    deadline = time.monotonic() + CONFIRM_S
    now = held
    while time.monotonic() < deadline:
        try:
            now = as_float(ha_state(args.entity))
        except CouldNotLook as why:
            print("NOT CHECKED: %s" % why)
            return 2
        if now is not None and abs(now - args.set) < 0.05:
            print("CONFIRMED: the machine reports %.1f" % now)
            return 0
        time.sleep(1.0)
    print("IGNORED: Home Assistant accepted it, but after %.0f s the machine "
          "still reports %s" % (CONFIRM_S, now))
    return 1


if __name__ == "__main__":
    sys.exit(main())
