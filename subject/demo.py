import argparse
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from subject.attention import select_crystal
from subject.composer import compose_packet
from subject.core import Subject
from subject.crystallizer import crystallize
from subject.exporter import export_packet_md, load_latest_packet, load_packet
from subject.reader import read_selected_crystal


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crystal", action="store_true", help="write a crystal artifact")
    parser.add_argument(
        "--crystal-twice",
        action="store_true",
        help="write crystals twice without new events",
    )
    parser.add_argument("--select-crystal", action="store_true", help="select a crystal")
    parser.add_argument(
        "--select-strategy",
        default="latest",
        help="selection strategy (default: latest)",
    )
    parser.add_argument("--read-crystal", action="store_true", help="read selected crystal")
    parser.add_argument("--compose", action="store_true", help="compose a packet")
    parser.add_argument("--tail-n", type=int, default=20, help="history tail size")
    parser.add_argument("--export", action="store_true", help="export latest packet to markdown")
    parser.add_argument("--pipeline", action="store_true", help="run select->read->compose->export")
    parser.add_argument(
        "--pipeline-crystal",
        action="store_true",
        help="crystallize before running the pipeline",
    )
    parser.add_argument("--latest-export", action="store_true", help="show latest export")
    parser.add_argument("--head", type=int, default=40, help="number of lines to show")
    parser.add_argument("--budget", type=int, default=None, help="initial budget")
    parser.add_argument("--workspace", default="storage", help="workspace directory")
    args = parser.parse_args()

    crystal_calls = 2 if args.crystal_twice else (1 if args.crystal else 0)
    base_budget = args.budget if args.budget is not None else 1 + crystal_calls
    s = Subject(
        initial_value=0,
        initial_budget=base_budget,
        workspace_dir=args.workspace,
    )

    if args.latest_export:
        latest_path, latest_rel = _find_latest_export(Path(args.workspace))
        if latest_path is None or latest_rel is None:
            print("LATEST_EXPORT: SKIP (NO_EXPORTS)")
        else:
            print(f"LATEST_EXPORT: {latest_rel.as_posix()}")
            head_lines = _read_head(latest_path, args.head)
            if head_lines:
                print(head_lines, end="" if head_lines.endswith("\n") else "\n")
        return

    if args.crystal_twice:
        for idx in range(5):
            s.state.history.append({"type": "BOOT", "index": idx})
        rel_path = crystallize(s, min_new_events=5)
        _print_crystal("CRYSTAL #1", rel_path, s.state.history)
        rel_path = crystallize(s, min_new_events=5)
        _print_crystal("CRYSTAL #2", rel_path, s.state.history)
    elif args.crystal:
        s.state.history.append({"type": "BOOT"})
        rel_path = crystallize(s, min_new_events=1)
        _print_crystal("CRYSTAL", rel_path, s.state.history)

    selected = None
    selection_signature = None
    selection_info = None
    crystal_payload = None
    packet_path = None
    packet_payload = None

    if args.pipeline:
        pipeline_reason = None
        if args.pipeline_crystal:
            s.state.history.append({"type": "BOOT"})
            rel_path = crystallize(s, min_new_events=1)
            if rel_path is None:
                pipeline_reason = _last_skip_reason(
                    s.state.history,
                    {"CRYSTAL_SKIP"},
                    "OTHER",
                )

        if pipeline_reason is None:
            selected = select_crystal(s, strategy=args.select_strategy)
            if selected is None:
                pipeline_reason = _last_skip_reason(
                    s.state.history,
                    {"CRYSTAL_SELECT_SKIP"},
                    "NO_CRYSTALS",
                )
            else:
                selection_signature = s.state.history[-1].get("signature")
                selection_info = {
                    "path": s.state.history[-1].get("path"),
                    "signature": selection_signature,
                }

        if pipeline_reason is None:
            crystal_payload = read_selected_crystal(s, selected, selection_signature)
            if crystal_payload is None:
                pipeline_reason = _last_skip_reason(
                    s.state.history,
                    {"CRYSTAL_READ_DENY"},
                    "INVALID",
                )

        if pipeline_reason is None:
            packet_path = compose_packet(
                s,
                selection=selection_info,
                crystal=crystal_payload,
                tail_n=args.tail_n,
            )
            if packet_path is None:
                pipeline_reason = _last_skip_reason(
                    s.state.history,
                    {"PACKET_SKIP"},
                    "OTHER",
                )
            else:
                packet_payload = load_packet(s.workspace_dir, packet_path)

        if pipeline_reason is None:
            export_path = export_packet_md(s, packet_payload) if packet_payload else None
            if export_path is None:
                pipeline_reason = _last_skip_reason(
                    s.state.history,
                    {"EXPORT_SKIP"},
                    "OTHER",
                )
            else:
                print(f"PIPELINE: OK packet={packet_path} export={export_path}")
        if pipeline_reason is not None:
            print(f"PIPELINE: SKIP ({pipeline_reason})")

    if args.select_crystal and not args.pipeline:
        selected = select_crystal(s, strategy=args.select_strategy)
        if selected:
            print(f"SELECT: {selected} (reason=LATEST)")
            if s.state.history and s.state.history[-1].get("type") == "CRYSTAL_SELECT":
                selection_signature = s.state.history[-1].get("signature")
                selection_info = {
                    "path": s.state.history[-1].get("path"),
                    "signature": selection_signature,
                }
        else:
            reason = "NO_CRYSTALS"
            if s.state.history and s.state.history[-1].get("type") == "CRYSTAL_SELECT_SKIP":
                reason = str(s.state.history[-1].get("reason", "NO_CRYSTALS"))
            print(f"SELECT: SKIP ({reason})")

    if args.read_crystal and not args.pipeline:
        if not selected:
            print("READ: SKIP (NO_SELECTION)")
        else:
            payload = read_selected_crystal(s, selected, selection_signature)
            if payload is None:
                reason = "INVALID"
                if s.state.history and s.state.history[-1].get("type") == "CRYSTAL_READ_DENY":
                    reason = str(s.state.history[-1].get("reason", "INVALID"))
                print(f"READ: SKIP ({reason})")
            else:
                print(f"READ: {selected}")
                print(f"KIND: {payload.get('kind')}")
                payload_body = payload.get("payload", {})
                if isinstance(payload_body, dict) and "summary" in payload_body:
                    print(f"SUMMARY: {payload_body.get('summary')}")
                if isinstance(payload_body, dict) and "events" in payload_body:
                    print(f"EVENTS: {len(payload_body.get('events'))}")
                crystal_payload = payload

    if args.compose and not args.pipeline:
        if selection_info is None or crystal_payload is None:
            if selected is None:
                selected = select_crystal(s, strategy=args.select_strategy)
            if selected:
                if s.state.history and s.state.history[-1].get("type") == "CRYSTAL_SELECT":
                    selection_signature = s.state.history[-1].get("signature")
                    selection_info = {
                        "path": s.state.history[-1].get("path"),
                        "signature": selection_signature,
                    }
            if crystal_payload is None and selected:
                crystal_payload = read_selected_crystal(s, selected, selection_signature)
        packet_path = compose_packet(
            s,
            selection=selection_info,
            crystal=crystal_payload,
            tail_n=args.tail_n,
        )
        if packet_path:
            packet_payload = load_packet(s.workspace_dir, packet_path)
            print(f"COMPOSE: {packet_path}")
        else:
            reason = "OTHER"
            if s.state.history and s.state.history[-1].get("type") == "PACKET_SKIP":
                reason = str(s.state.history[-1].get("reason", "OTHER"))
            print(f"COMPOSE: SKIP ({reason})")

    if args.export and not args.pipeline:
        if packet_payload is None and packet_path:
            packet_payload = load_packet(s.workspace_dir, packet_path)
        if packet_payload is None:
            packet_payload = load_latest_packet(s.workspace_dir)
            if packet_payload:
                packet_path = packet_payload.get("path")
        if packet_payload is None:
            print("EXPORT: SKIP (NO_PACKET)")
        else:
            export_path = export_packet_md(s, packet_payload)
            if export_path:
                print(f"EXPORT: {export_path}")
            else:
                reason = "OTHER"
                if s.state.history and s.state.history[-1].get("type") == "EXPORT_SKIP":
                    reason = str(s.state.history[-1].get("reason", "OTHER"))
                print(f"EXPORT: SKIP ({reason})")

    print("STEP 1")
    s.step(5)
    print(s.state)

    print("STEP 2 (should DENY)")
    s.step(5)
    print(s.state)

    print("WRITE OK")
    s.write_artifact("ok.txt", "hello")

    print("WRITE VIOLATION")
    s.write_artifact("../README.md", "nope")

    print("HISTORY")
    for event in s.state.history:
        print(event)


def _print_crystal(prefix: str, rel_path: Optional[str], history: List[Dict[str, object]]) -> None:
    if rel_path:
        print(f"{prefix}: {rel_path}")
        return
    reason = "OTHER"
    if history and history[-1].get("type") == "CRYSTAL_SKIP":
        reason = str(history[-1].get("reason", "OTHER"))
    print(f"{prefix}: SKIP ({reason})")


def _last_skip_reason(
    history: List[Dict[str, object]], event_types: Set[str], fallback: str
) -> str:
    if history and history[-1].get("type") in event_types:
        return str(history[-1].get("reason", fallback))
    return fallback


def _find_latest_export(workspace_dir: Path) -> Tuple[Optional[Path], Optional[Path]]:
    exports_dir = workspace_dir / "storage" / "exports"
    if not exports_dir.exists() or not exports_dir.is_dir():
        return None, None
    candidates = sorted(exports_dir.glob("packet_*.md"))
    if not candidates:
        return None, None
    latest = candidates[-1]
    rel = Path("storage") / "exports" / latest.name
    return latest, rel


def _read_head(path: Path, line_count: int) -> str:
    if line_count <= 0:
        return ""
    lines: List[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for _ in range(line_count):
            line = handle.readline()
            if not line:
                break
            lines.append(line)
    return "".join(lines)


if __name__ == "__main__":
    main()
