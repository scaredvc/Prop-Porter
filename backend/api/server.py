try:
    from . import app
except ImportError:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from backend.api import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
