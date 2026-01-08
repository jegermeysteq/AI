"""Crystalize subject history into immutable artifacts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from subject.core import SubjectState


CRYSTAL_COST = 1
INDEX_VERSION = "0.2"


def crystallize(
    state: Any, rel_dir: str = "storage/crystals", min_new_events: int = 5
) -> Optional[str]:
    subject, subject_state = _resolve_subject(state)
    history = list(subject_state.history)
    budget = subject_state.budget

    last_event_index = _last_crystal_write_index(history)

    if budget < CRYSTAL_COST:
        event = {
            "type": "CRYSTAL_SKIP",
            "reason": "NO_BUDGET",
            "last_event_index": last_event_index,
        }
        _set_subject_state(subject, history + [event], budget)
        return None

    from_index = last_event_index + 1
    new_events = history[from_index:]

    if len(new_events) < min_new_events:
        event = {
            "type": "CRYSTAL_SKIP",
            "reason": "NOT_ENOUGH_NEW_EVENTS",
            "event_count": len(new_events),
            "min_new_events": min_new_events,
            "last_event_index": last_event_index,
        }
        _set_subject_state(subject, history + [event], budget - CRYSTAL_COST)
        return None

    crystal_body = {
        "version": INDEX_VERSION,
        "kind": "event_digest",
        "payload": {
            "events": new_events,
            "from_index": from_index,
            "to_index": from_index + len(new_events) - 1,
            "event_count": len(new_events),
        },
    }
    signature = _signature_for_crystal(crystal_body)
    rel_dir_clean = _clean_rel_dir(rel_dir, getattr(subject, "workspace_dir", None))
    index_rel_path = _join_rel(rel_dir_clean, "index.json")
    index_path = _workspace_path(subject, index_rel_path)

    index_payload = _load_index_payload(index_path)
    crystals = index_payload["crystals"]
    known_signatures = {entry.get("signature") for entry in crystals if entry.get("signature")}

    if signature in known_signatures:
        event = {
            "type": "CRYSTAL_SKIP",
            "reason": "DUPLICATE",
            "signature": signature,
            "last_event_index": last_event_index,
        }
        _set_subject_state(subject, history + [event], budget - CRYSTAL_COST)
        return None

    next_index = int(index_payload["next_index"])
    to_index = from_index + len(new_events) - 1
    crystal_name = f"crystal_{next_index:04d}.json"
    crystal_rel_path = _join_rel(rel_dir_clean, crystal_name)
    crystal_payload = dict(crystal_body)
    crystal_payload["signature"] = signature
    crystal_payload["created_at"] = _timestamp()

    subject.write_artifact(crystal_rel_path, _stable_json(crystal_payload))
    history_after_write = list(subject.state.history)

    if history_after_write and history_after_write[-1].get("type") == "DENY":
        event = {
            "type": "CRYSTAL_SKIP",
            "reason": "OTHER",
            "detail": "MEMBRANE_VIOLATION",
            "signature": signature,
            "path": crystal_rel_path,
            "last_event_index": last_event_index,
        }
        _set_subject_state(subject, history_after_write + [event], budget - CRYSTAL_COST)
        return None

    entry = {
        "index": next_index,
        "path": crystal_rel_path,
        "signature": signature,
        "kind": "event_digest",
        "from_index": from_index,
        "to_index": to_index,
        "event_count": len(new_events),
        "created_at": _timestamp(),
    }
    index_payload["version"] = INDEX_VERSION
    index_payload["next_index"] = next_index + 1
    index_payload["last_event_index"] = to_index
    index_payload["crystals"] = crystals + [entry]

    subject.write_artifact(index_rel_path, _stable_json(index_payload))
    history_after_index = list(subject.state.history)
    if history_after_index and history_after_index[-1].get("type") == "DENY":
        event = {
            "type": "CRYSTAL_SKIP",
            "reason": "OTHER",
            "detail": "MEMBRANE_VIOLATION",
            "signature": signature,
            "path": index_rel_path,
            "last_event_index": last_event_index,
        }
        _set_subject_state(subject, history_after_index + [event], budget - CRYSTAL_COST)
        return None

    event = {
        "type": "CRYSTAL_WRITE",
        "index": next_index,
        "path": crystal_rel_path,
        "signature": signature,
        "event_count": len(new_events),
        "from_index": from_index,
        "last_event_index": to_index,
    }
    _set_subject_state(subject, history_after_index + [event], budget - CRYSTAL_COST)
    return crystal_rel_path


def _resolve_subject(state: Any) -> Tuple[Any, SubjectState]:
    if hasattr(state, "state") and hasattr(state, "write_artifact"):
        return state, state.state
    if hasattr(state, "subject") and hasattr(state, "history") and hasattr(state, "budget"):
        return state.subject, state
    raise TypeError("crystallize expects a Subject or a state with subject reference")


def _last_crystal_write_index(history: List[Dict[str, object]]) -> int:
    for event in reversed(history):
        if event.get("type") == "CRYSTAL_WRITE":
            try:
                return int(event.get("last_event_index", -1))
            except (TypeError, ValueError):
                return -1
    return -1


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _signature_for_crystal(crystal: Dict[str, Any]) -> str:
    normalized = _stable_json(crystal)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


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


def _default_index_payload() -> Dict[str, Any]:
    return {
        "version": INDEX_VERSION,
        "next_index": 0,
        "last_event_index": -1,
        "crystals": [],
    }


def _load_index_payload(index_path: Path) -> Dict[str, Any]:
    payload = _default_index_payload()
    if not index_path.exists():
        return payload
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return payload
    if not isinstance(data, dict):
        return payload

    payload["next_index"] = _coerce_int(data.get("next_index"), payload["next_index"])
    payload["last_event_index"] = _coerce_int(
        data.get("last_event_index"), payload["last_event_index"]
    )
    crystals = data.get("crystals")
    if isinstance(crystals, list):
        payload["crystals"] = [entry for entry in crystals if isinstance(entry, dict)]
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
