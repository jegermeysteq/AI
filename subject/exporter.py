"""Packet exporter to Markdown."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Dict, List, Optional, Tuple

from subject.core import SubjectState


def export_packet_md(
    state: Any,
    packet: Dict[str, Any],
    *,
    rel_dir: str = "storage/exports",
    cost: int = 1,
) -> Optional[str]:
    subject, subject_state = _resolve_subject(state)
    history = list(subject_state.history)
    budget = subject_state.budget

    if budget < cost:
        event = {"type": "EXPORT_SKIP", "reason": "NO_BUDGET"}
        _set_subject_state(subject, history + [event], budget)
        return None

    packet_index = _packet_index(packet)
    if packet_index is None:
        event = {"type": "EXPORT_SKIP", "reason": "INVALID_PACKET"}
        _set_subject_state(subject, history + [event], budget - cost)
        return None

    rel_dir_clean = _clean_rel_dir(rel_dir, getattr(subject, "workspace_dir", None))
    export_name = f"packet_{packet_index:04d}.md"
    export_rel_path = _join_rel(rel_dir_clean, export_name)

    markdown = _render_markdown(packet, packet_index)
    export_bytes = len(markdown.encode("utf-8"))

    subject.write_artifact(export_rel_path, markdown)
    history_after_write = list(subject.state.history)
    if history_after_write and history_after_write[-1].get("type") == "DENY":
        event = {
            "type": "EXPORT_SKIP",
            "reason": "OTHER",
            "detail": "MEMBRANE_VIOLATION",
            "path": export_rel_path,
        }
        _set_subject_state(subject, history_after_write + [event], budget - cost)
        return None

    crystal = packet.get("crystal", {})
    event = {
        "type": "EXPORT_WRITE",
        "path": export_rel_path,
        "bytes": export_bytes,
        "packet_index": packet_index,
        "crystal_signature": crystal.get("signature") if isinstance(crystal, dict) else None,
    }
    _set_subject_state(subject, history_after_write + [event], budget - cost)
    return export_rel_path


def load_latest_packet(
    workspace_dir: str, rel_index_path: str = "storage/packets/index.json"
) -> Optional[Dict[str, Any]]:
    index_rel = _normalize_rel_path(rel_index_path)
    if index_rel is None:
        return None
    index_path = Path(workspace_dir) / index_rel
    if not index_path.exists():
        return None
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    packets = payload.get("packets")
    if not isinstance(packets, list) or not packets:
        return None

    entry = _select_latest(packets)
    if not entry or not isinstance(entry, dict):
        return None
    path = entry.get("path")
    if not isinstance(path, str):
        return None
    packet = load_packet(workspace_dir, path)
    if packet is None:
        return None
    packet = dict(packet)
    packet["path"] = path
    if "index" not in packet and "index" in entry:
        packet["index"] = entry.get("index")
    return packet


def load_packet(workspace_dir: str, rel_path: str) -> Optional[Dict[str, Any]]:
    rel_clean = _normalize_rel_path(rel_path)
    if rel_clean is None:
        return None
    full_path = _resolve_full_path(Path(workspace_dir), rel_clean)
    if full_path is None or not full_path.exists():
        return None
    try:
        payload = json.loads(full_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _resolve_subject(state: Any) -> Tuple[Any, SubjectState]:
    if hasattr(state, "state") and hasattr(state, "write_artifact"):
        return state, state.state
    if hasattr(state, "subject") and hasattr(state, "history") and hasattr(state, "budget"):
        return state.subject, state
    raise TypeError("export_packet_md expects a Subject or a state with subject reference")


def _packet_index(packet: Dict[str, Any]) -> Optional[int]:
    if "index" in packet:
        try:
            return int(packet["index"])
        except (TypeError, ValueError):
            return None
    path = packet.get("path")
    if isinstance(path, str):
        name = Path(path).stem
        if name.startswith("packet_"):
            suffix = name.replace("packet_", "")
            if suffix.isdigit():
                return int(suffix)
    return None


def _render_markdown(packet: Dict[str, Any], packet_index: int) -> str:
    crystal = packet.get("crystal", {})
    crystal_path = crystal.get("path") if isinstance(crystal, dict) else None
    crystal_kind = crystal.get("kind") if isinstance(crystal, dict) else None
    crystal_signature = crystal.get("signature") if isinstance(crystal, dict) else None
    created_at = packet.get("created_at")
    intent = packet.get("intent")
    history_tail = packet.get("history_tail", [])
    payload = packet.get("payload", {})

    lines = [
        f"# Packet {packet_index}",
        f"- Created: {created_at}",
        f"- Crystal: {crystal_path} (kind={crystal_kind}, signature={crystal_signature})",
        f"- Intent: {intent}",
        "",
    ]

    if isinstance(payload, dict) and ("summary" in payload or "metrics" in payload):
        lines.append("## Crystal payload (if summary/metrics exist)")
        if "summary" in payload:
            lines.append(f"- Summary: {payload.get('summary')}")
        if "metrics" in payload:
            lines.append(f"- Metrics: {payload.get('metrics')}")
        lines.append("")

    lines.append("## History tail")
    lines.append("```json")
    lines.append(_stable_json(history_tail))
    lines.append("```")
    return "\n".join(lines) + "\n"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


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


def _resolve_full_path(workspace_dir: Path, rel_path: str) -> Optional[Path]:
    candidate = workspace_dir / rel_path
    if candidate.exists():
        return candidate
    if rel_path.startswith("packets/"):
        alt = workspace_dir / "storage" / rel_path
        if alt.exists():
            return alt
    return candidate


def _select_latest(entries: List[Dict[str, object]]) -> Optional[Dict[str, object]]:
    best_entry = None
    best_index = None
    for entry in entries:
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
    for entry in reversed(entries):
        if isinstance(entry, dict):
            return entry
    return None


def _set_subject_state(subject: Any, history: List[Dict[str, object]], budget: int) -> SubjectState:
    subject.state = SubjectState(
        value=subject.state.value,
        history=history,
        budget=budget,
    )
    return subject.state
