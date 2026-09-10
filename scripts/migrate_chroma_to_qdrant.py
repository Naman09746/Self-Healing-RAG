#!/usr/bin/env python3
"""Thin wrapper for migrate_chroma_to_pgvector with Qdrant target."""

import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["VECTOR_STORE_PROVIDER"] = "qdrant"
import scripts.migrate_chroma_to_pgvector as m

if __name__ == "__main__":
    sys.argv.append("--to") if "--to" not in sys.argv else None
    if "--to" not in sys.argv:
        sys.argv.extend(["--to", "qdrant"])
    raise SystemExit(m.main())
