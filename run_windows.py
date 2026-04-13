from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent
    game_file = root / "calculator_rpg.py"

    if not game_file.exists():
        print("Error: calculator_rpg.py was not found in this folder.")
        return 1

    python_exe = sys.executable or "python"
    try:
        result = subprocess.run([python_exe, str(game_file)])
    except OSError as exc:
        print(f"Error: Failed to start the game: {exc}")
        return 1

    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
