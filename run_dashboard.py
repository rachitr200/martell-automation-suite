"""Run the local operations demo from the repository root."""
from pathlib import Path
import sys

if __name__ == '__main__':
    try:
        import uvicorn
    except ImportError:
        raise SystemExit('Install dependencies: python -m pip install -r 09-dashboard/requirements.txt')
    sys.path.insert(0, str(Path(__file__).parent / '09-dashboard'))
    uvicorn.run('dashboard:app', host='127.0.0.1', port=8000)
