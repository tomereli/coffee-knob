# -*- coding: utf-8 -*-
"""Did the device actually take the firmware that was just built?

    python ops/verify.py                      # this repo's device
    python ops/verify.py --device coffee-knob

Prints one line for ops/shipped.py --live, and exits 0 only when it proved
something. It REFUSES rather than passing: without a token, without a
reachable Home Assistant, or without the entity it needs, it says so and
exits 2. "We could not look" is not "it works", and a check that can be
skipped and still report green is decoration.

That rule is borrowed from health-mcp/ops/verify.py, whose own note says it
best: every other check there asked the server whether it was well, and on
2026-09-07 the server was perfect through four deploys while the app opened
to nothing.

WHAT IT PROVES, and why this and not something easier. A knob has no page to
render, so the analogue of "the app came up" is an observation only the new
firmware could produce. ESPHome's version text_sensor reports the config hash
the running binary was compiled from, and .esphome/build/<device>/
build_info.json holds the same number for what was just built. Equal means
the hardware is running THIS config. Not equal means it is running something
else, whatever `esphome run` said.

"The device rejoined the network" is deliberately NOT the test. That is this
project's healthz: necessary, cheap, and exactly the thing that stays green
while the wrong image runs.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_DEVICE = "coffee-knob"
# Where `esphome run` leaves its build tree, relative to the repo root. The
# firmware does not always sit at the top level.
BUILD_ROOTS = (".esphome/build", "firmware/.esphome/build")
HASH_IN_STATE = re.compile(r"config hash 0x([0-9a-fA-F]{1,8})")


class CouldNotLook(Exception):
    """The check could not run. Never reported as a pass."""


def built_hash(device: str) -> tuple[int, str]:
    for root in BUILD_ROOTS:
        path = REPO / root / device / "build_info.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return int(data["config_hash"]), str(data.get("build_time_str", ""))
    raise CouldNotLook(
        "no build_info.json for %s under %s -- build before verifying, or "
        "there is nothing to compare against"
        % (device, " or ".join(BUILD_ROOTS)))


def ha_state(entity: str) -> dict:
    url = os.environ.get("HA_URL", "").rstrip("/")
    token = os.environ.get("HA_TOKEN", "")
    if not url or not token:
        raise CouldNotLook(
            "HA_URL and HA_TOKEN are not both set, so Home Assistant cannot "
            "be asked anything -- set them or report that nothing was checked")
    request = urllib.request.Request(
        "%s/api/states/%s" % (url, entity),
        headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise CouldNotLook(
                "%s does not exist in Home Assistant. The version text_sensor "
                "has to be flashed once before it can verify anything -- the "
                "build that introduces it cannot be checked by it." % entity)
        raise CouldNotLook("Home Assistant answered %s for %s"
                           % (error.code, entity))
    except (urllib.error.URLError, TimeoutError) as error:
        raise CouldNotLook("could not reach Home Assistant: %s" % error)


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default=DEFAULT_DEVICE)
    parser.add_argument("--entity", default=None,
                        help="defaults to sensor.<device>_firmware")
    args = parser.parse_args(argv)
    entity = args.entity or "sensor.%s_firmware" % args.device.replace("-", "_")

    try:
        expected, built_at = built_hash(args.device)
        state = ha_state(entity)
    except CouldNotLook as why:
        print("NOT VERIFIED: %s" % why)
        return 2

    text = str(state.get("state", ""))
    found = HASH_IN_STATE.search(text)
    if not found:
        print("NOT VERIFIED: %s reads %r, which carries no config hash -- "
              "hide_hash must be false for this check to work"
              % (entity, text))
        return 2

    running = int(found.group(1), 16)
    if running != expected:
        print("MISMATCH: %s is running config hash 0x%08x, but the build here "
              "is 0x%08x (built %s). The device did not take this firmware."
              % (args.device, running, expected, built_at))
        return 1

    print("%s is running config hash 0x%08x, the one built %s"
          % (args.device, expected, built_at))
    return 0


if __name__ == "__main__":
    sys.exit(main())
