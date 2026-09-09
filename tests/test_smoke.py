import subprocess
import sys


def test_root_entrypoint():
    result = subprocess.run(
        [sys.executable, "scribe", "--version"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "0.1.0"
    assert result.stderr == ""
