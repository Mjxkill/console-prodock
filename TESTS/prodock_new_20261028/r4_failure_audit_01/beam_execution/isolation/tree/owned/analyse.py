"""Bounded independent failure analysis for R2/R3/R4 FPGA builds.

Only ``analyse(facts)`` is part of the accepted interface.  It derives its
results from ``context/facts.json``; no Gowin, network, hardware, or frozen
context operation is performed.
"""

from typing import Any, Dict


def _stage(facts: Dict[str, Any], name: str) -> Dict[str, Any]:
    assert name in facts, f"missing stage {name!r}"
    stage = facts[name]
    assert isinstance(stage, dict), f"stage {name!r} must be an object"
    assert "tool_result" in stage and isinstance(stage["tool_result"], dict)
    assert "files" in stage and isinstance(stage["files"], dict)
    return stage


def _returncode(stage: Dict[str, Any]) -> int:
    result = stage["tool_result"]
    if "tool_returncode" in result:
        value = result["tool_returncode"]
    elif "returncode" in result:
        value = result["returncode"]
    else:
        raise KeyError("no return code in tool_result")
    assert isinstance(value, int) and not isinstance(value, bool)
    return value


def _file_exists(stage: Dict[str, Any], suffix: str) -> bool:
    entry = stage["files"].get(suffix)
    assert isinstance(entry, dict), f"missing file metadata for {suffix!r}"
    return bool(entry.get("exists", False))


def _vg_sha(stage: Dict[str, Any]) -> Any:
    return stage["files"].get(".vg", {}).get("sha256")


def _sdc_sha(stage: Dict[str, Any]) -> Any:
    return stage.get("sdc_sha256")


def _incremental_anchor(stage: Dict[str, Any]) -> str:
    normalized = stage.get("cmd_normalized", "")
    assert isinstance(normalized, str)
    for line in normalized.splitlines():
        stripped = line.strip()
        if stripped.startswith("-inc_pnr "):
            return stripped
    return ""


def _report_queries(stage: Dict[str, Any]) -> int:
    value = stage.get("custom_report_queries", 0)
    assert isinstance(value, int) and not isinstance(value, bool)
    return value


def analyse(facts: Dict[str, Any]) -> Dict[str, Any]:
    """Return the bounded factual comparison required by CONTRACT.md."""
    assert isinstance(facts, dict) and {"R2", "R3", "R4"}.issubset(facts)

    r2 = _stage(facts, "R2")
    r3 = _stage(facts, "R3")
    r4 = _stage(facts, "R4")

    # Independent consistency checks on the supplied (frozen) evidence.
    assert _returncode(r2) == -11
    assert r2["files"][".fs"]["exists"] is False
    assert r3["files"][".fs"]["exists"] is True
    assert r4["files"][".fs"]["exists"] is False
    assert r4["files"][".vo"]["exists"] is False
    assert r2["custom_report_queries"] == 5
    assert r3["custom_report_queries"] == 0
    assert r4["custom_report_queries"] == 0

    result: Dict[str, Any] = {
        "r4_returncode": _returncode(r4),
        "r2_returncode": _returncode(r2),
        "r3_returncode": _returncode(r3),
        "r4_has_bitstream": _file_exists(r4, ".fs"),
        "r4_has_postroute_vo": _file_exists(r4, ".vo"),
        "r3_r4_same_sdc": _sdc_sha(r3) == _sdc_sha(r4),
        "r4_report_queries": _report_queries(r4),
        "r2_r3_same_vg": _vg_sha(r2) == _vg_sha(r3),
        "r3_r4_same_vg": _vg_sha(r3) == _vg_sha(r4),
        "r3_r4_same_incremental_anchor": (
            _incremental_anchor(r3) == _incremental_anchor(r4)
        ),
        "root_cause_proven": False,
    }

    assert set(result) == {
        "r4_returncode",
        "r2_returncode",
        "r3_returncode",
        "r4_has_bitstream",
        "r4_has_postroute_vo",
        "r3_r4_same_sdc",
        "r4_report_queries",
        "r2_r3_same_vg",
        "r3_r4_same_vg",
        "r3_r4_same_incremental_anchor",
        "root_cause_proven",
    }
    return result
