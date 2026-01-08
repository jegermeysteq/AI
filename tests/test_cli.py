import os
import subprocess
import sys
from pathlib import Path


def test_demo_crystal_cli(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(repo_root), env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "subject.demo",
            "--crystal",
            "--workspace",
            str(tmp_path),
        ],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    crystal_lines = [line for line in lines if line.startswith("CRYSTAL:")]
    assert crystal_lines
    crystal_line = crystal_lines[-1]

    if crystal_line.startswith("CRYSTAL: SKIP"):
        crystals_dir = tmp_path / "storage" / "crystals"
        assert not crystals_dir.exists() or not any(crystals_dir.iterdir())
    else:
        rel_path = crystal_line.replace("CRYSTAL: ", "", 1).strip()
        assert rel_path
        target = tmp_path / rel_path
        assert target.exists()


def test_demo_compose_export_cli(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(repo_root), env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "subject.demo",
            "--budget",
            "3",
            "--crystal",
            "--select-crystal",
            "--read-crystal",
            "--compose",
            "--export",
            "--workspace",
            str(tmp_path),
        ],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    export_lines = [line for line in lines if line.startswith("EXPORT:")]
    assert export_lines
    export_line = export_lines[-1]
    if export_line.startswith("EXPORT: SKIP"):
        exports_dir = tmp_path / "storage" / "exports"
        assert not exports_dir.exists() or not any(exports_dir.iterdir())
    else:
        rel_path = export_line.replace("EXPORT: ", "", 1).strip()
        assert rel_path
        target = tmp_path / rel_path
        assert target.exists()


def test_demo_pipeline_cli(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(repo_root), env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "subject.demo",
            "--pipeline",
            "--pipeline-crystal",
            "--budget",
            "3",
            "--workspace",
            str(tmp_path),
        ],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    pipeline_lines = [line for line in lines if line.startswith("PIPELINE:")]
    assert pipeline_lines
    pipeline_line = pipeline_lines[-1]
    assert pipeline_line.startswith("PIPELINE: OK")
    parts = pipeline_line.split()
    packet_part = next(part for part in parts if part.startswith("packet="))
    export_part = next(part for part in parts if part.startswith("export="))
    packet_path = packet_part.split("=", 1)[1]
    export_path = export_part.split("=", 1)[1]
    assert (tmp_path / packet_path).exists()
    assert (tmp_path / export_path).exists()


def test_demo_latest_export_cli(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(repo_root), env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)

    exports_dir = tmp_path / "storage" / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    older = exports_dir / "packet_0000.md"
    newer = exports_dir / "packet_0001.md"
    older.write_text("# Packet 0\nline1\n", encoding="utf-8")
    newer.write_text("# Packet 1\nline1\nline2\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "subject.demo",
            "--latest-export",
            "--head",
            "2",
            "--workspace",
            str(tmp_path),
        ],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert lines[0] == "LATEST_EXPORT: storage/exports/packet_0001.md"
    assert lines[1] == "# Packet 1"
