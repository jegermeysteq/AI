import json
from pathlib import Path
from typing import Dict, List

from subject.attention import select_crystal
from subject.composer import compose_packet
from subject.core import Subject
from subject.crystallizer import crystallize
from subject.reader import read_selected_crystal


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


def test_compose_packet_happy_path(tmp_path: Path) -> None:
    history = _make_history(3)
    subject = Subject(history=history, initial_budget=2, workspace_dir=str(tmp_path))

    rel_path = crystallize(subject, rel_dir="storage/crystals", min_new_events=3)
    assert rel_path is not None

    selected = select_crystal(subject)
    signature = None
    if subject.state.history and subject.state.history[-1].get("type") == "CRYSTAL_SELECT":
        signature = subject.state.history[-1].get("signature")
    selection_info = {"path": selected, "signature": signature}
    crystal_payload = read_selected_crystal(subject, selected, signature)

    packet_path = compose_packet(
        subject,
        selection=selection_info,
        crystal=crystal_payload,
        rel_dir="storage/packets",
        tail_n=2,
    )

    assert packet_path is not None
    packet_full = tmp_path / packet_path
    assert packet_full.exists()
    packet = json.loads(packet_full.read_text(encoding="utf-8"))
    assert packet["version"] == "0.1"
    assert packet["crystal"]["signature"] == signature
    assert packet["intent"] == "Summarize crystal and propose next step"


def test_compose_packet_no_budget(tmp_path: Path) -> None:
    subject = Subject(initial_budget=0, workspace_dir=str(tmp_path))
    packet_path = compose_packet(subject, selection={"path": "x", "signature": "y"}, crystal={})

    assert packet_path is None
    assert subject.state.history[-1]["type"] == "PACKET_SKIP"
    assert subject.state.history[-1]["reason"] == "NO_BUDGET"
    assert not (tmp_path / "storage" / "packets").exists()


def test_compose_packet_path_safety(tmp_path: Path) -> None:
    history = _make_history(3)
    subject = Subject(history=history, initial_budget=2, workspace_dir=str(tmp_path))
    rel_path = crystallize(subject, rel_dir="storage/crystals", min_new_events=3)
    assert rel_path is not None

    selected = select_crystal(subject)
    signature = None
    if subject.state.history and subject.state.history[-1].get("type") == "CRYSTAL_SELECT":
        signature = subject.state.history[-1].get("signature")
    selection_info = {"path": selected, "signature": signature}
    crystal_payload = read_selected_crystal(subject, selected, signature)

    packet_path = compose_packet(
        subject,
        selection=selection_info,
        crystal=crystal_payload,
        tail_n=1,
    )

    assert packet_path is not None
    assert packet_path.startswith("storage/packets/")
    assert (tmp_path / packet_path).exists()
