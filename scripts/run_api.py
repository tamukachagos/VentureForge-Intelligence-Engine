from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

log_path = ROOT / "server.out.log"
err_path = ROOT / "server.err.log"
sys.stdout = log_path.open("a", encoding="utf-8", buffering=1)
sys.stderr = err_path.open("a", encoding="utf-8", buffering=1)

import uvicorn  # noqa: E402

uvicorn.run("ai_research_stack.api:app", host="127.0.0.1", port=8000)
