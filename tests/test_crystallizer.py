import json
from pathlib import Path
from typing import Dict, List

from subject.core import Subject
from subject.crystallizer import _signature_for_crystal, crystallize


def _make_history(count: int) -> List[Dict[str, object]]:
    history: List[Dict[str, object]] = []
    for idx in range(count):
        history.append(
            {
                "type": "STEP",
                "input": idx,
                "result": idx,
                "cost": 1,
                "budget_after": 10 - idx,
            }
        )
    return history


def test_crystallize_writes_crystal(tmp_path: Path) -> None:
    history = _make_history(5)
    subject = Subject(history=history, initial_budget=1, workspace_dir=str(tmp_path))

    rel_path = crystallize(subject, rel_dir="crystals", min_new_events=5)

    crystal_path = tmp_path / "crystals" / "crystal_0000.json"
    index_path = tmp_path / "crystals" / "index.json"
    assert rel_path == "crystals/crystal_0000.json"
    assert crystal_path.exists()
    assert index_path.exists()
    assert subject.state.history[-1]["type"] == "CRYSTAL_WRITE"
    assert subject.state.budget == 0
    index_payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert index_payload["version"] == "0.2"
    assert index_payload["next_index"] == 1
    assert index_payload["last_event_index"] == 4
    assert index_payload["crystals"][0]["signature"]


def test_crystallize_skip_not_enough_events(tmp_path: Path) -> None:
    history = _make_history(2)
    subject = Subject(history=history, initial_budget=1, workspace_dir=str(tmp_path))

    rel_path = crystallize(subject, rel_dir="crystals", min_new_events=5)

    assert rel_path is None
    assert subject.state.history[-1]["type"] == "CRYSTAL_SKIP"
    assert subject.state.history[-1]["reason"] == "NOT_ENOUGH_NEW_EVENTS"
    assert subject.state.budget == 0
    assert list(tmp_path.iterdir()) == []


def test_crystallize_dedupe(tmp_path: Path) -> None:
    history = _make_history(5)
    crystal_body = {
        "version": "0.2",
        "kind": "event_digest",
        "payload": {
            "events": history,
            "from_index": 0,
            "to_index": 4,
            "event_count": 5,
        },
    }
    signature = _signature_for_crystal(crystal_body)
    crystals_dir = tmp_path / "crystals"
    crystals_dir.mkdir()
    index_path = crystals_dir / "index.json"
    index_path.write_text(
        json.dumps(
            {
                "version": "0.2",
                "next_index": 1,
                "last_event_index": 4,
                "crystals": [
                    {
                        "index": 0,
                        "path": "crystals/crystal_0000.json",
                        "signature": signature,
                        "kind": "event_digest",
                        "from_index": 0,
                        "to_index": 4,
                        "event_count": 5,
                        "created_at": "2024-01-01T00:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    subject = Subject(history=history, initial_budget=1, workspace_dir=str(tmp_path))

    rel_path = crystallize(subject, rel_dir="crystals", min_new_events=5)

    assert rel_path is None
    assert subject.state.history[-1]["type"] == "CRYSTAL_SKIP"
    assert subject.state.history[-1]["reason"] == "DUPLICATE"
    assert subject.state.budget == 0
    assert len(list(crystals_dir.glob("crystal_*.json"))) == 0


def test_crystallize_membrane_denies_traversal(tmp_path: Path) -> None:
    history = _make_history(5)
    subject = Subject(history=history, initial_budget=1, workspace_dir=str(tmp_path))

    rel_path = crystallize(subject, rel_dir="../crystals", min_new_events=5)

    assert rel_path is None
    assert subject.state.history[-1]["type"] == "CRYSTAL_SKIP"
    assert subject.state.history[-1]["reason"] == "OTHER"
    assert list(tmp_path.iterdir()) == []


def test_crystallize_incremental_skips_without_events(tmp_path: Path) -> None:
    history = _make_history(5)
    subject = Subject(history=history, initial_budget=2, workspace_dir=str(tmp_path))

    first_path = crystallize(subject, rel_dir="crystals", min_new_events=5)
    second_path = crystallize(subject, rel_dir="crystals", min_new_events=5)

    assert first_path == "crystals/crystal_0000.json"
    assert second_path is None
    assert subject.state.history[-1]["type"] == "CRYSTAL_SKIP"
    assert subject.state.history[-1]["reason"] == "NOT_ENOUGH_NEW_EVENTS"

    index_path = tmp_path / "crystals" / "index.json"
    index_payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert index_payload["next_index"] == 1
    assert index_payload["last_event_index"] == 4


def test_crystal_signature_consistency(tmp_path: Path) -> None:
    history = _make_history(3)
    subject = Subject(history=history, initial_budget=1, workspace_dir=str(tmp_path))

    rel_path = crystallize(subject, rel_dir="crystals", min_new_events=3)

    assert rel_path is not None
    crystal_path = tmp_path / rel_path
    index_path = tmp_path / "crystals" / "index.json"
    crystal_payload = json.loads(crystal_path.read_text(encoding="utf-8"))
    index_payload = json.loads(index_path.read_text(encoding="utf-8"))
    event_signature = subject.state.history[-1]["signature"]

    assert crystal_payload["signature"] == index_payload["crystals"][0]["signature"]
    assert crystal_payload["signature"] == event_signature
