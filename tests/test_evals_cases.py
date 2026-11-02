from pathlib import Path

import yaml

from emporio.tools import ALL_TOOLS

CASES_PATH = Path(__file__).resolve().parents[1] / "evals" / "cases.yaml"

VALID_EXPECT_KEYS = {
    "tools_all",
    "tools_any",
    "tools_none",
    "args",
    "args_absent",
    "contains_all",
    "contains_any",
    "not_contains",
    "brl_format",
    "no_fallback",
}

TOOL_NAMES = {t.name for t in ALL_TOOLS}


def _cases():
    return yaml.safe_load(CASES_PATH.read_text(encoding="utf-8"))


def test_yaml_loads():
    assert isinstance(_cases(), list)
    assert len(_cases()) == 27


def test_unique_ids_and_turns():
    cases = _cases()
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids))
    for case in cases:
        assert case.get("turns"), f"caso {case['id']} sem turnos"


def test_expect_keys_are_known():
    for case in _cases():
        for turn in case["turns"]:
            unknown = set(turn.get("expect", {})) - VALID_EXPECT_KEYS
            assert not unknown, f"{case['id']}: chaves desconhecidas {unknown}"


def test_referenced_tools_exist():
    for case in _cases():
        for turn in case["turns"]:
            expect = turn.get("expect", {})
            cited: set[str] = set()
            for key in ("tools_all", "tools_any", "tools_none"):
                cited.update(expect.get(key, []))
            for rule in expect.get("args", []):
                cited.add(rule["tool"])
            for rule in expect.get("args_absent", []):
                cited.add(rule["tool"])
            unknown = cited - TOOL_NAMES
            assert not unknown, f"{case['id']}: ferramentas inexistentes {unknown}"
