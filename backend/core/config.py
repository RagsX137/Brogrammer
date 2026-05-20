import os
from pathlib import Path
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env", override=False)


def get(name: str, default: str) -> str:
    return os.environ.get(name, default)


def get_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default
