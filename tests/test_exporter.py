import json
from pathlib import Path
from typing import Dict, List

from subject.attention import select_crystal
from subject.composer import compose_packet
from subject.core import Subject
from subject.crystallizer import crystallize
from subject.exporter import export_packet_md
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


def test_export_packet_markdown(tmp_path: Path) -> None:
    history = _make_history(5)
    subject = Subject(history=history, initial_budget=2, workspace_dir=str(tmp_path))
    selection = {"path": "crystals/crystal_0000.json", "signature": "sig"}
    crystal = {"kind": "event_digest"}
    packet_path = compose_packet(subject, selection=selection, crystal=crystal, tail_n=2)
    assert packet_path is not None
    packet_full = tmp_path / packet_path
    packet = json.loads(packet_full.read_text(encoding="utf-8"))

    export_path = export_packet_md(subject, packet)

    assert export_path is not None
    export_full = tmp_path / export_path
    assert export_full.exists()
    text = export_full.read_text(encoding="utf-8")
    assert "signature=sig" in text
    assert "History tail" in text
    assert subject.state.history[-1]["type"] == "EXPORT_WRITE"
    assert subject.state.history[-1]["crystal_signature"] == "sig"


def test_export_packet_no_budget(tmp_path: Path) -> None:
    subject = Subject(initial_budget=0, workspace_dir=str(tmp_path))
    packet = {
        "index": 0,
        "version": "0.1",
        "created_at": "2024-01-01T00:00:00Z",
        "crystal": {"path": "crystals/crystal_0000.json", "signature": "sig", "kind": "event_digest"},
        "history_tail": [],
        "intent": "Summarize crystal and propose next step",
    }
    export_path = export_packet_md(subject, packet)

    assert export_path is None
    assert subject.state.history[-1]["type"] == "EXPORT_SKIP"
    assert subject.state.history[-1]["reason"] == "NO_BUDGET"


def test_compose_export_signature_consistency(tmp_path: Path) -> None:
    history = _make_history(3)
    subject = Subject(history=history, initial_budget=3, workspace_dir=str(tmp_path))
    rel_path = crystallize(subject, rel_dir="storage/crystals", min_new_events=3)
    assert rel_path is not None

    selected = select_crystal(subject)
    signature = None
    if subject.state.history and subject.state.history[-1].get("type") == "CRYSTAL_SELECT":
        signature = subject.state.history[-1].get("signature")
    selection_info = {"path": selected, "signature": signature}
    crystal_payload = read_selected_crystal(subject, selected, signature)

    packet_path = compose_packet(subject, selection=selection_info, crystal=crystal_payload)
    assert packet_path is not None
    packet_full = tmp_path / packet_path
    packet = json.loads(packet_full.read_text(encoding="utf-8"))

    export_path = export_packet_md(subject, packet)
    assert export_path is not None

    packet_signature = None
    export_signature = None
    for event in subject.state.history:
        if event.get("type") == "PACKET_WRITE":
            packet_signature = event.get("crystal_signature")
        if event.get("type") == "EXPORT_WRITE":
            export_signature = event.get("crystal_signature")

    assert packet_signature is not None
    assert export_signature == packet_signature
