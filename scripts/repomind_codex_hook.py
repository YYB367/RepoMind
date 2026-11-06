"""Run a generated repo-local hook with the current RepoMind checkout."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from repomind.cli import main

raise SystemExit(main())
