import json
from pathlib import Path

import pytest

from subject.attention import select_crystal
from subject.core import Subject
from subject.reader import CrystalReadError, read_crystal, read_selected_crystal


def _write_index(tmp_path: Path, path: str) -> None:
    payload = {
        "version": "0.2",
        "next_index": 1,
        "last_event_index": 0,
        "crystals": [
            {
                "index": 0,
                "path": path,
                "signature": "sig",
                "kind": "event_digest",
                "from_index": 0,
                "to_index": 0,
                "event_count": 1,
                "created_at": "2024-01-01T00:00:00Z",
            }
        ],
    }
    (tmp_path / "crystals").mkdir(parents=True, exist_ok=True)
    (tmp_path / "crystals" / "index.json").write_text(json.dumps(payload), encoding="utf-8")


def test_read_selected_crystal_ok(tmp_path: Path) -> None:
    subject = Subject(initial_budget=1, workspace_dir=str(tmp_path))
    crystal_path = tmp_path / "crystals" / "crystal_0000.json"
    crystal_payload = {
        "version": "0.2",
        "kind": "event_digest",
        "signature": "sig",
        "payload": {
            "summary": "demo",
            "events": [{"type": "BOOT"}],
        },
    }
    crystal_path.parent.mkdir(parents=True, exist_ok=True)
    crystal_path.write_text(json.dumps(crystal_payload), encoding="utf-8")
    _write_index(tmp_path, "crystals/crystal_0000.json")

    selected = select_crystal(subject, rel_index_path="crystals/index.json")
    payload = read_selected_crystal(subject, selected)

    assert payload is not None
    assert payload["kind"] == "event_digest"
    assert payload["payload"]["summary"] == "demo"
    assert subject.state.history[-1]["type"] == "CRYSTAL_READ"
    assert subject.state.history[-1]["signature"] == "sig"


def test_read_selected_crystal_legacy_signature_fallback(tmp_path: Path) -> None:
    subject = Subject(initial_budget=1, workspace_dir=str(tmp_path))
    crystal_path = tmp_path / "crystals" / "crystal_0000.json"
    crystal_payload = {
        "version": "0.2",
        "kind": "event_digest",
        "payload": {
            "summary": "legacy",
            "events": [{"type": "BOOT"}],
        },
    }
    crystal_path.parent.mkdir(parents=True, exist_ok=True)
    crystal_path.write_text(json.dumps(crystal_payload), encoding="utf-8")
    _write_index(tmp_path, "crystals/crystal_0000.json")

    selected = select_crystal(subject, rel_index_path="crystals/index.json")
    signature = None
    if subject.state.history and subject.state.history[-1].get("type") == "CRYSTAL_SELECT":
        signature = subject.state.history[-1].get("signature")
    payload = read_selected_crystal(subject, selected, signature)

    assert payload is not None
    assert subject.state.history[-1]["type"] == "CRYSTAL_READ"
    assert subject.state.history[-1]["signature"] == "sig"


def test_select_and_read_signature_match(tmp_path: Path) -> None:
    subject = Subject(initial_budget=1, workspace_dir=str(tmp_path))
    crystal_path = tmp_path / "crystals" / "crystal_0000.json"
    crystal_payload = {
        "version": "0.2",
        "kind": "event_digest",
        "signature": "match_sig",
        "payload": {"events": []},
    }
    crystal_path.parent.mkdir(parents=True, exist_ok=True)
    crystal_path.write_text(json.dumps(crystal_payload), encoding="utf-8")
    _write_index(tmp_path, "crystals/crystal_0000.json")

    selected = select_crystal(subject, rel_index_path="crystals/index.json")
    select_signature = None
    if subject.state.history and subject.state.history[-1].get("type") == "CRYSTAL_SELECT":
        select_signature = subject.state.history[-1].get("signature")
    payload = read_selected_crystal(subject, selected, select_signature)

    assert payload is not None
    assert subject.state.history[-1]["type"] == "CRYSTAL_READ"
    assert subject.state.history[-1]["signature"] == select_signature


def test_read_crystal_denies_traversal(tmp_path: Path) -> None:
    with pytest.raises(CrystalReadError) as excinfo:
        read_crystal(str(tmp_path), "../secret.json")

    assert excinfo.value.reason == "VIOLATION"
