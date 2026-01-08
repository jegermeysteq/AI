"""Crystal selection logic."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Dict, List, Optional, Tuple

from subject.core import SubjectState
from subject.reader import CrystalReadError, read_crystal


def select_crystal(
    state: Any,
    rel_index_path: str = "storage/crystals/index.json",
    strategy: str = "latest",
) -> Optional[str]:
    subject, subject_state = _resolve_subject(state)
    history = list(subject_state.history)

    index_rel = _normalize_rel_path(rel_index_path, getattr(subject, "workspace_dir", None))
    if index_rel is None:
        event = {"type": "CRYSTAL_SELECT_SKIP", "reason": "NO_CRYSTALS"}
        _set_subject_state(subject, history + [event])
        return None

    index_path = _workspace_path(subject, index_rel)
    payload = _load_index_payload(index_path)
    crystals = payload.get("crystals", [])
    if not crystals:
        event = {"type": "CRYSTAL_SELECT_SKIP", "reason": "NO_CRYSTALS"}
        _set_subject_state(subject, history + [event])
        return None

    if strategy != "latest":
        event = {"type": "CRYSTAL_SELECT_SKIP", "reason": "NO_CRYSTALS"}
        _set_subject_state(subject, history + [event])
        return None

    entry = _select_latest(crystals)
    if entry is None:
        event = {"type": "CRYSTAL_SELECT_SKIP", "reason": "NO_CRYSTALS"}
        _set_subject_state(subject, history + [event])
        return None

    entry_signature = entry.get("signature")
    file_signature = _load_crystal_signature(
        subject, entry.get("path"), entry_signature if isinstance(entry_signature, str) else None
    )
    signature = file_signature or entry_signature
    event = {
        "type": "CRYSTAL_SELECT",
        "reason": "LATEST",
        "index": entry.get("index"),
        "path": entry.get("path"),
        "signature": signature,
    }
    _set_subject_state(subject, history + [event])
    return entry.get("path")


def _resolve_subject(state: Any) -> Tuple[Any, SubjectState]:
    if hasattr(state, "state") and hasattr(state, "write_artifact"):
        return state, state.state
    if hasattr(state, "subject") and hasattr(state, "history") and hasattr(state, "budget"):
        return state.subject, state
    raise TypeError("select_crystal expects a Subject or a state with subject reference")


def _normalize_rel_path(rel_path: str, workspace_dir: Optional[str]) -> Optional[str]:
    rel_posix = rel_path.replace("\\", "/").strip("/")
    if workspace_dir:
        workspace_posix = str(workspace_dir).replace("\\", "/").strip("/")
        if workspace_posix and rel_posix.startswith(workspace_posix + "/"):
            rel_posix = rel_posix[len(workspace_posix) + 1 :]
        elif workspace_posix and rel_posix == workspace_posix:
            rel_posix = ""

    posix_path = PurePosixPath(rel_posix)
    windows_path = PureWindowsPath(rel_posix)
    has_parent_ref = ".." in posix_path.parts or ".." in windows_path.parts
    is_absolute = posix_path.is_absolute() or windows_path.is_absolute()
    has_drive_or_root = bool(windows_path.drive) or bool(windows_path.root)

    if not rel_posix or is_absolute or has_drive_or_root or has_parent_ref:
        return None
    return rel_posix


def _workspace_path(subject: Any, rel_path: str) -> Path:
    base = Path(getattr(subject, "workspace_dir", "."))
    return base / rel_path


def _load_index_payload(index_path: Path) -> Dict[str, object]:
    if not index_path.exists():
        return {}
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _select_latest(crystals: List[Dict[str, object]]) -> Optional[Dict[str, object]]:
    best_entry = None
    best_index = None
    for entry in crystals:
        if not isinstance(entry, dict):
            continue
        try:
            index_value = int(entry.get("index"))
        except (TypeError, ValueError):
            index_value = None
        if index_value is None:
            continue
        if best_index is None or index_value > best_index:
            best_index = index_value
            best_entry = entry

    if best_entry is not None:
        return best_entry
    for entry in reversed(crystals):
        if isinstance(entry, dict):
            return entry
    return None


def _load_crystal_signature(
    subject: Any, rel_path: Any, expected_signature: Optional[str]
) -> Optional[str]:
    if not isinstance(rel_path, str):
        return None
    try:
        payload = read_crystal(getattr(subject, "workspace_dir", "."), rel_path, expected_signature)
    except CrystalReadError:
        return None
    signature = payload.get("signature")
    return signature if isinstance(signature, str) else None


def _set_subject_state(subject: Any, history: List[Dict[str, object]]) -> SubjectState:
    subject.state = SubjectState(
        value=subject.state.value,
        history=history,
        budget=subject.state.budget,
    )
    return subject.state
