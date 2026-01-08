import json
from pathlib import Path
from typing import Dict

from subject.attention import select_crystal
from subject.core import Subject


def test_select_crystal_no_index(tmp_path: Path) -> None:
    subject = Subject(initial_budget=1, workspace_dir=str(tmp_path))

    selected = select_crystal(subject, rel_index_path="crystals/index.json")

    assert selected is None
    assert subject.state.history[-1]["type"] == "CRYSTAL_SELECT_SKIP"
    assert subject.state.history[-1]["reason"] == "NO_CRYSTALS"


def test_select_crystal_latest(tmp_path: Path) -> None:
    subject = Subject(initial_budget=1, workspace_dir=str(tmp_path))
    crystals_dir = tmp_path / "crystals"
    crystals_dir.mkdir(parents=True, exist_ok=True)
    index_path = crystals_dir / "index.json"
    crystal_path = crystals_dir / "crystal_0002.json"
    crystal_path.write_text(
        json.dumps(
            {
                "version": "0.2",
                "kind": "event_digest",
                "signature": "file_sig",
                "payload": {"events": []},
            }
        ),
        encoding="utf-8",
    )
    payload: Dict[str, object] = {
        "version": "0.2",
        "next_index": 3,
        "last_event_index": 5,
        "crystals": [
            {
                "index": 0,
                "path": "crystals/crystal_0000.json",
                "signature": "a",
                "kind": "event_digest",
                "from_index": 0,
                "to_index": 0,
                "event_count": 1,
                "created_at": "2024-01-01T00:00:00Z",
            },
            {
                "index": 2,
                "path": "crystals/crystal_0002.json",
                "signature": "index_sig",
                "kind": "event_digest",
                "from_index": 1,
                "to_index": 5,
                "event_count": 5,
                "created_at": "2024-01-01T00:00:00Z",
            },
        ],
    }
    index_path.write_text(json.dumps(payload), encoding="utf-8")

    selected = select_crystal(subject, rel_index_path="crystals/index.json")

    assert selected == "crystals/crystal_0002.json"
    assert subject.state.history[-1]["type"] == "CRYSTAL_SELECT"
    assert subject.state.history[-1]["reason"] == "LATEST"
    assert subject.state.history[-1]["index"] == 2
    assert subject.state.history[-1]["signature"] == "file_sig"
