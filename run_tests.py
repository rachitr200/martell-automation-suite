"""Dependency-free test runner for the plain-assert tests in this suite.

    python run_tests.py            # run everything it can
    python run_tests.py 03         # only projects whose folder starts with 03

It exists so every project's core logic can be verified with just the Python standard library.
The same tests also run under pytest (`uv run pytest`). The FastAPI service in 01 additionally
has pytest-fixture tests that need its dependencies; this runner reports those as skipped.
"""

import importlib.util
import inspect
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).parent


def project_dirs(prefix: str | None):
    for d in sorted(ROOT.iterdir()):
        if d.is_dir() and d.name[:2].isdigit() and (not prefix or d.name.startswith(prefix)):
            yield d


def main() -> int:
    prefix = sys.argv[1] if len(sys.argv) > 1 else None
    passed = failed = skipped = 0
    for proj in project_dirs(prefix):
        for p in (proj / "src", proj):
            if p.exists():
                sys.path.insert(0, str(p))
        for path in sorted((proj / "tests").glob("test_*.py")):
            name = f"{proj.name}.{path.stem}".replace("-", "_")
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except ModuleNotFoundError as exc:
                print(f"SKIP  {proj.name}/{path.name}  (needs {exc.name})")
                skipped += 1
                continue
            for fname, fn in inspect.getmembers(module, inspect.isfunction):
                if not fname.startswith("test_") or fn.__module__ != name:
                    continue
                if inspect.signature(fn).parameters:
                    print(f"SKIP  {proj.name}/{path.name}::{fname}  (uses pytest fixtures)")
                    skipped += 1
                    continue
                try:
                    fn()
                    passed += 1
                except Exception:
                    failed += 1
                    print(f"FAIL  {proj.name}/{path.name}::{fname}")
                    traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
