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
