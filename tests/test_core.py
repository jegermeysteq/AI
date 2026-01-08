from pathlib import Path

from subject.core import Subject


def test_step_deterministic() -> None:
    subject_a = Subject(initial_value=0, initial_budget=3)
    subject_b = Subject(initial_value=0, initial_budget=3)

    subject_a.step(5)
    subject_b.step(5)

    assert subject_a.state.value == subject_b.state.value
    assert subject_a.state.budget == subject_b.state.budget
    assert subject_a.state.history[-1] == subject_b.state.history[-1]


def test_budget_deny() -> None:
    subject = Subject(initial_value=0, initial_budget=0)

    subject.step(5)

    assert subject.state.value == 0
    assert subject.state.history[-1]["type"] == "DENY"
    assert subject.state.history[-1]["reason"] == "NO_BUDGET"


def test_membrane_allows_write_in_workspace(tmp_path: Path) -> None:
    subject = Subject(workspace_dir=str(tmp_path))

    subject.write_artifact("ok.txt", "hello")

    target = tmp_path / "ok.txt"
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "hello"
    assert subject.state.history[-1]["type"] == "ARTIFACT_WRITE"


def test_membrane_denies_traversal(tmp_path: Path) -> None:
    subject = Subject(workspace_dir=str(tmp_path))

    subject.write_artifact("../README.md", "x")

    assert subject.state.history[-1]["type"] == "DENY"
    assert subject.state.history[-1]["reason"] == "MEMBRANE_VIOLATION"
    assert not (tmp_path.parent / "README.md").exists()
    assert list(tmp_path.iterdir()) == []
