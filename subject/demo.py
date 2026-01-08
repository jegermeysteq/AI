import argparse
from typing import Dict, List, Optional

from subject.core import Subject
from subject.crystallizer import crystallize


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crystal", action="store_true", help="write a crystal artifact")
    parser.add_argument(
        "--crystal-twice",
        action="store_true",
        help="write crystals twice without new events",
    )
    parser.add_argument("--workspace", default="storage", help="workspace directory")
    args = parser.parse_args()

    crystal_calls = 2 if args.crystal_twice else (1 if args.crystal else 0)
    s = Subject(
        initial_value=0,
        initial_budget=1 + crystal_calls,
        workspace_dir=args.workspace,
    )

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


if __name__ == "__main__":
    main()
