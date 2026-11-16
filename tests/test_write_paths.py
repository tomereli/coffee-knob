"""The knob's two writes to the machine, judged against recorded answers.

    python -m pytest tests/

Issue #2: from 1 Nov 2026 the La Marzocco integration refused every write to
the machine, and the knob showed a temperature that had never been set and
started a clean that never started. Home Assistant logs nothing when a call
from an ESPHome device fails, so nobody could see why.

These tests take the lambdas that decide a write's fate OUT OF
coffee-knob.yaml, verbatim, compile them with g++ around a stub of the
globals, and replay what Home Assistant and the machine answered. Each
scenario is a file in tests/recorded/ that says where its answer came from.
Nothing is reimplemented in Python. If the YAML changes, this tests the
change.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
from knob_lint import Loader  # noqa: E402  (reads !lambda and !secret)

CONFIG = REPO / "coffee-knob.yaml"
HARNESS = Path(__file__).with_name("write_harness.cpp.in")
RECORDED = Path(__file__).with_name("recorded")


def load_config() -> dict:
    return yaml.load(CONFIG.read_text(encoding="utf-8"), Loader=Loader)


def walk(node):
    """Every dict anywhere under node, depth first."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item)


def substitute(body: str, subs: dict) -> str:
    def repl(m):
        name = m.group(1) or m.group(2)
        if name not in subs:
            raise KeyError("lambda uses $%s, which substitutions: lacks" % name)
        return str(subs[name])
    return re.sub(r"\$\{(\w+)\}|\$(\w+)", repl, body)


def script(cfg: dict, script_id: str) -> dict:
    for s in cfg["script"]:
        if s.get("id") == script_id:
            return s
    raise KeyError("no script %s in coffee-knob.yaml" % script_id)


def first_lambda(steps) -> str:
    for step in steps:
        if isinstance(step, dict) and "lambda" in step:
            return str(step["lambda"])
    raise KeyError("no lambda step")


def action_to(cfg_node, entity_sub: str) -> list[dict]:
    """Every homeassistant.action whose data targets the given $substitution."""
    found = []
    for d in walk(cfg_node):
        call = d.get("homeassistant.action")
        if isinstance(call, dict) and (call.get("data") or {}).get("entity_id") == entity_sub:
            found.append(call)
    return found


def extract(cfg: dict) -> dict[str, str]:
    subs = cfg["substitutions"]
    out = {}

    sensor = next(s for s in cfg["sensor"] if s.get("id") == "coffee_temp")
    out["TEMP_ON_VALUE"] = first_lambda(sensor["on_value"])

    send = script(cfg, "send_temp")
    out["SEND_TEMP"] = first_lambda(send["then"])
    (call,) = action_to(send, "$micra_temp")
    out["TEMP_ON_ERROR"] = first_lambda(call["on_error"])
    out["TEMP_JUDGE"] = first_lambda(script(cfg, "temp_judge")["then"])

    start = script(cfg, "start_clean")
    out["CLEAN_START"] = next(str(d["lambda"]) for d in walk(start)
                              if "lambda" in d and "clean_req_ms" in str(d["lambda"]))
    (call,) = action_to(start, "$micra_backflush")
    out["CLEAN_ON_ERROR"] = first_lambda(call["on_error"])

    mirror = next(b for b in cfg["binary_sensor"] if b.get("id") == "micra_cleaning")
    out["CLEAN_ON_PRESS"] = first_lambda(mirror["on_press"])
    out["CLEAN_JUDGE"] = first_lambda(script(cfg, "clean_judge")["then"])

    return {k: substitute(v, subs) for k, v in out.items()}


@pytest.fixture(scope="session")
def harness(tmp_path_factory) -> Path:
    compiler = shutil.which("g++") or shutil.which("clang++")
    if compiler is None:
        # Refuse rather than pass: a test that cannot run has proved nothing.
        pytest.fail("no C++ compiler on PATH -- these tests compile the "
                    "shipped lambdas and cannot run without one")
    source = HARNESS.read_text(encoding="utf-8")
    for marker, body in extract(load_config()).items():
        source = source.replace("@@%s@@" % marker, body)
    assert not re.search(r"@@[A-Z_]+@@", source), "a lambda marker was left unfilled"
    build = tmp_path_factory.mktemp("harness")
    (build / "harness.cpp").write_text(source, encoding="utf-8")
    exe = build / "harness"
    subprocess.run([compiler, "-std=c++17", "-Wall", "-Werror", "-o", str(exe),
                    str(build / "harness.cpp")], check=True)
    return exe


def run(exe: Path, events: list) -> list[dict]:
    lines = []
    for ev in events:
        lines.append(" ".join(str(x) for x in ev))
    proc = subprocess.run([str(exe)], input="\n".join(lines) + "\n",
                          capture_output=True, text=True, check=True)
    rows = []
    for line in proc.stdout.splitlines():
        row = dict(kv.split("=", 1) for kv in line.split())
        rows.append({k: float(v) for k, v in row.items()})
    return rows


SCENARIOS = sorted(RECORDED.glob("*.json"))


@pytest.mark.parametrize("path", SCENARIOS, ids=[p.stem for p in SCENARIOS])
def test_recorded_answer(harness, path):
    scenario = json.loads(path.read_text(encoding="utf-8"))
    assert scenario.get("source"), "%s must say where its answer came from" % path.name
    rows = run(harness, scenario["events"])
    by_time = {int(r["t"]): r for r in rows}
    for want in scenario["expect"]:
        at = want["at"]
        assert at in by_time, "%s: no check at t=%d (have %s)" % (path.name, at, sorted(by_time))
        got = by_time[at]
        for key, value in want.items():
            if key == "at":
                continue
            assert got[key] == pytest.approx(value), (
                "%s at t=%d: %s is %s, expected %s" % (path.name, at, key, got[key], value))


def test_both_paths_have_a_recording_for_each_outcome():
    seen = {(json.loads(p.read_text())["path"], json.loads(p.read_text())["outcome"])
            for p in SCENARIOS}
    for path in ("temp", "clean"):
        for outcome in ("refused", "ignored", "confirmed"):
            assert (path, outcome) in seen, "no recording for %s %s" % (path, outcome)


def test_every_write_to_the_machine_hears_its_refusal():
    """A write with no on_error is how issue #2 stayed invisible for two weeks."""
    cfg = load_config()
    for sub in ("$micra_temp", "$micra_backflush"):
        calls = action_to(cfg, sub)
        assert calls, "nothing writes %s any more" % sub
        for call in calls:
            assert "on_error" in call, "a write to %s ignores its refusal" % sub


def test_the_temperature_has_one_writer():
    """Recipe recall used to call number.set_value itself, unjudged."""
    cfg = load_config()
    assert len(action_to(cfg, "$micra_temp")) == 1
    assert len(action_to(script(cfg, "send_temp"), "$micra_temp")) == 1
