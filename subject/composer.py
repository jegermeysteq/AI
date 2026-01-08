"""Packet composer for selected crystals."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from subject.core import SubjectState


INDEX_VERSION = "0.1"


def compose_packet(
    state: Any,
    *,
    selection: Optional[Dict[str, object]] = None,
    crystal: Optional[Dict[str, object]] = None,
    rel_dir: str = "storage/packets",
    tail_n: int = 20,
    cost: int = 1,
) -> Optional[str]:
    subject, subject_state = _resolve_subject(state)
    history = list(subject_state.history)
    budget = subject_state.budget

    if budget < cost:
        event = {"type": "PACKET_SKIP", "reason": "NO_BUDGET"}
        _set_subject_state(subject, history + [event], budget)
        return None

    if not selection:
        event = {"type": "PACKET_SKIP", "reason": "NO_SELECTION"}
        _set_subject_state(subject, history + [event], budget - cost)
        return None

    if not crystal:
        event = {"type": "PACKET_SKIP", "reason": "NO_CRYSTAL"}
        _set_subject_state(subject, history + [event], budget - cost)
        return None

    rel_dir_clean = _clean_rel_dir(rel_dir, getattr(subject, "workspace_dir", None))
    index_rel_path = _join_rel(rel_dir_clean, "index.json")
    index_path = _workspace_path(subject, index_rel_path)
    index_payload = _load_index_payload(index_path)

    next_index = int(index_payload["next_index"])
    packet_name = f"packet_{next_index:04d}.json"
    packet_rel_path = _join_rel(rel_dir_clean, packet_name)

    packet = {
        "index": next_index,
        "version": INDEX_VERSION,
        "created_at": _timestamp(),
        "crystal": {
            "path": selection.get("path"),
            "signature": selection.get("signature"),
            "kind": crystal.get("kind"),
        },
        "history_tail": history[-tail_n:] if tail_n > 0 else [],
        "intent": "Summarize crystal and propose next step",
    }
    packet_text = _stable_json(packet)
    packet_bytes = len(packet_text.encode("utf-8"))

    subject.write_artifact(packet_rel_path, packet_text)
    history_after_write = list(subject.state.history)
    if history_after_write and history_after_write[-1].get("type") == "DENY":
        event = {
            "type": "PACKET_SKIP",
            "reason": "OTHER",
            "detail": "MEMBRANE_VIOLATION",
            "path": packet_rel_path,
        }
        _set_subject_state(subject, history_after_write + [event], budget - cost)
        return None

    entry = {
        "index": next_index,
        "path": packet_rel_path,
        "bytes": packet_bytes,
        "crystal_signature": selection.get("signature"),
        "created_at": _timestamp(),
    }
    index_payload["version"] = INDEX_VERSION
    index_payload["next_index"] = next_index + 1
    index_payload["packets"] = index_payload["packets"] + [entry]

    subject.write_artifact(index_rel_path, _stable_json(index_payload))
    history_after_index = list(subject.state.history)
    if history_after_index and history_after_index[-1].get("type") == "DENY":
        event = {
            "type": "PACKET_SKIP",
            "reason": "OTHER",
            "detail": "MEMBRANE_VIOLATION",
            "path": index_rel_path,
        }
        _set_subject_state(subject, history_after_index + [event], budget - cost)
        return None

    event = {
        "type": "PACKET_WRITE",
        "index": next_index,
        "path": packet_rel_path,
        "bytes": packet_bytes,
        "crystal_signature": selection.get("signature"),
    }
    _set_subject_state(subject, history_after_index + [event], budget - cost)
    return packet_rel_path


def _resolve_subject(state: Any) -> Tuple[Any, SubjectState]:
    if hasattr(state, "state") and hasattr(state, "write_artifact"):
        return state, state.state
    if hasattr(state, "subject") and hasattr(state, "history") and hasattr(state, "budget"):
        return state.subject, state
    raise TypeError("compose_packet expects a Subject or a state with subject reference")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _clean_rel_dir(rel_dir: str, workspace_dir: Optional[str]) -> str:
    rel_dir_posix = rel_dir.replace("\\", "/").strip("/")
    if not workspace_dir:
        return rel_dir_posix
    workspace_posix = str(workspace_dir).replace("\\", "/").strip("/")
    if workspace_posix and rel_dir_posix.startswith(workspace_posix + "/"):
        rel_dir_posix = rel_dir_posix[len(workspace_posix) + 1 :]
    elif workspace_posix and rel_dir_posix == workspace_posix:
        rel_dir_posix = ""
    return rel_dir_posix.strip("/")


def _join_rel(*parts: str) -> str:
    cleaned = [part.strip("/\\") for part in parts if part and part.strip("/\\")]
    return "/".join(cleaned)


def _workspace_path(subject: Any, rel_path: str) -> Path:
    base = Path(getattr(subject, "workspace_dir", "."))
    return base / rel_path if rel_path else base


def _load_index_payload(index_path: Path) -> Dict[str, Any]:
    payload = {"version": INDEX_VERSION, "next_index": 0, "packets": []}
    if not index_path.exists():
        return payload
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return payload
    if not isinstance(data, dict):
        return payload

    payload["next_index"] = _coerce_int(data.get("next_index"), payload["next_index"])
    packets = data.get("packets")
    if isinstance(packets, list):
        payload["packets"] = [entry for entry in packets if isinstance(entry, dict)]
    return payload


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _set_subject_state(subject: Any, history: List[Dict[str, object]], budget: int) -> SubjectState:
    subject.state = SubjectState(
        value=subject.state.value,
        history=history,
        budget=budget,
    )
    return subject.state
