"""Crystal reader utilities (read-only)."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Dict, List, Optional, Tuple

from subject.core import SubjectState


class CrystalReadError(Exception):
    def __init__(self, reason: str, detail: Optional[str] = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def read_crystal(
    workspace_dir: str, rel_path: str, expected_signature: Optional[str] = None
) -> Dict[str, Any]:
    rel_clean = _normalize_rel_path(rel_path)
    if rel_clean is None:
        raise CrystalReadError("VIOLATION")

    full_path = _resolve_full_path(Path(workspace_dir), rel_clean)
    if full_path is None or not full_path.exists():
        raise CrystalReadError("NOT_FOUND")

    try:
        data = json.loads(full_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise CrystalReadError("INVALID") from exc

    if not isinstance(data, dict):
        raise CrystalReadError("INVALID")

    if {"version", "kind", "payload"}.issubset(data.keys()):
        if not isinstance(data.get("payload"), dict):
            raise CrystalReadError("INVALID")
        if "signature" not in data and expected_signature:
            data["signature"] = expected_signature
        return data

    if "signature" in data and "events" in data:
        return {
            "version": "legacy",
            "kind": "event_digest",
            "payload": data,
            "signature": data.get("signature"),
        }

    if "events" in data and expected_signature:
        return {
            "version": "legacy",
            "kind": "event_digest",
            "payload": data,
            "signature": expected_signature,
        }

    raise CrystalReadError("INVALID")


def read_selected_crystal(
    state: Any, selection_path: Optional[str], expected_signature: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    subject, subject_state = _resolve_subject(state)
    history = list(subject_state.history)

    if not selection_path:
        event = {"type": "CRYSTAL_READ_DENY", "reason": "NOT_FOUND", "detail": "NO_SELECTION"}
        _set_subject_state(subject, history + [event])
        return None

    try:
        payload = read_crystal(
            getattr(subject, "workspace_dir", "."), selection_path, expected_signature
        )
    except CrystalReadError as exc:
        event = {"type": "CRYSTAL_READ_DENY", "reason": exc.reason, "path": selection_path}
        if exc.detail:
            event["detail"] = exc.detail
        _set_subject_state(subject, history + [event])
        return None

    signature = payload.get("signature")

    event = {
        "type": "CRYSTAL_READ",
        "path": selection_path,
        "kind": payload.get("kind"),
        "signature": signature,
    }
    _set_subject_state(subject, history + [event])
    return payload


def _resolve_subject(state: Any) -> Tuple[Any, SubjectState]:
    if hasattr(state, "state") and hasattr(state, "write_artifact"):
        return state, state.state
    if hasattr(state, "subject") and hasattr(state, "history") and hasattr(state, "budget"):
        return state.subject, state
    raise TypeError("read_selected_crystal expects a Subject or a state with subject reference")


def _normalize_rel_path(rel_path: str) -> Optional[str]:
    rel_posix = rel_path.replace("\\", "/").strip("/")
    posix_path = PurePosixPath(rel_posix)
    windows_path = PureWindowsPath(rel_posix)
    has_parent_ref = ".." in posix_path.parts or ".." in windows_path.parts
    is_absolute = posix_path.is_absolute() or windows_path.is_absolute()
    has_drive_or_root = bool(windows_path.drive) or bool(windows_path.root)
    if not rel_posix or is_absolute or has_drive_or_root or has_parent_ref:
        return None
    return rel_posix


def _resolve_full_path(workspace_dir: Path, rel_path: str) -> Optional[Path]:
    candidate = workspace_dir / rel_path
    if candidate.exists():
        return candidate
    if rel_path.startswith("crystals/"):
        alt = workspace_dir / "storage" / rel_path
        if alt.exists():
            return alt
    return candidate


def _set_subject_state(subject: Any, history: List[Dict[str, object]]) -> SubjectState:
    subject.state = SubjectState(
        value=subject.state.value,
        history=history,
        budget=subject.state.budget,
    )
    return subject.state
