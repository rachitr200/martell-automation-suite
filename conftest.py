"""Lets `pytest` run from the repo root: puts every project's package on the import path."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent
for path in sorted(ROOT.glob("[0-9][0-9]-*/src")):
    sys.path.insert(0, str(path))
sys.path.insert(0, str(ROOT / "01-lifecycle-engine"))
