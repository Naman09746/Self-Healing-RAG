#!/usr/bin/env python3
"""
Migration: Chroma -> pgvector (or any VectorStore provider)

Reads all chunks from Chroma PersistentClient and re-ingests into the configured
VECTOR_STORE_PROVIDER (default pgvector). Idempotent via deterministic IDs.

Usage:
    VECTOR_STORE_PROVIDER=pgvector python scripts/migrate_chroma_to_pgvector.py [--dry-run] [--verify-parity] [--tenant default]
    python scripts/migrate_chroma_to_pgvector.py --from chroma --to pgvector --batch 100

Requires: chromadb, pgvector table already migrated (alembic upgrade head).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# Ensure project root on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.core.config import settings
from backend.core.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


def fetch_chroma_all(collection_name: str, chroma_path: str = "./chroma_data", tenant: str | None = None):
    try:
        import chromadb
    except Exception as e:
        logger.error("chromadb not installed", error=str(e))
        raise SystemExit(1)
    client = chromadb.PersistentClient(path=chroma_path)
    try:
        coll = client.get_collection(name=collection_name)
    except Exception:
        try:
            coll = client.get_or_create_collection(name=collection_name)
        except Exception as e:
            logger.error("Could not get Chroma collection", error=str(e), collection=collection_name)
            return [], [], []
    # Fetch all — chroma requires get with no filter
    data = coll.get(include=["documents", "metadatas", "embeddings"])
    docs = data.get("documents") or []
    metas = data.get("metadatas") or []
    ids = data.get("ids") or []
    if tenant:
        # Filter by tenant if requested
        filtered = [(d, m, i) for d, m, i in zip(docs, metas, ids) if (m or {}).get("tenant_id") == tenant]
        if filtered:
            docs, metas, ids = zip(*filtered)
            docs, metas, ids = list(docs), list(metas), list(ids)
        else:
            docs, metas, ids = [], [], []
    return docs, metas, ids


def main():
    parser = argparse.ArgumentParser(description="Migrate Chroma -> pgvector/Qdrant/Pinecone")
    parser.add_argument("--from", dest="from_store", default="chroma", help="source store (chroma)")
    parser.add_argument("--to", dest="to_store", default=None, help="target provider (pgvector/qdrant/pinecone), default from settings")
    parser.add_argument("--collection", default=None, help="Chroma collection name, default from settings")
    parser.add_argument("--chroma-path", default="./chroma_data", help="Chroma persistent path")
    parser.add_argument("--batch", type=int, default=100, help="batch size for upsert")
    parser.add_argument("--dry-run", action="store_true", help="do not write, only count")
    parser.add_argument("--verify-parity", action="store_true", help="after migrate, verify query parity for sample query")
    parser.add_argument("--tenant", default=None, help="only migrate this tenant_id")
    parser.add_argument("--sample-query", default="what is this document about?", help="sample query for parity check")
    args = parser.parse_args()

    collection = args.collection or settings.CHROMA_COLLECTION_NAME
    target_provider = args.to_store or getattr(settings, "VECTOR_STORE_PROVIDER", "pgvector")
    # Temporarily set provider for factory
    os.environ["VECTOR_STORE_PROVIDER"] = target_provider
    # Need to reload settings override? factory reads settings directly, so mutate
    try:
        settings.VECTOR_STORE_PROVIDER = target_provider  # type: ignore[attr-defined]
    except Exception:
        pass

    logger.info("Migration start", source="chroma", target=target_provider, collection=collection, dry_run=args.dry_run)

    docs, metas, ids = fetch_chroma_all(collection, args.chroma_path, args.tenant)
    total = len(docs)
    logger.info("Fetched from Chroma", count=total, collection=collection)
    if total == 0:
        print("No documents found in Chroma — nothing to migrate.")
        return 0

    if args.dry_run:
        print(f"[dry-run] Would migrate {total} chunks from Chroma[{collection}] -> {target_provider}")
        for i in range(min(3, total)):
            print(f"  sample {i}: id={ids[i]} tenant={(metas[i] or {}).get('tenant_id')} doc={(metas[i] or {}).get('document_id')} text={docs[i][:80]}...")
        return 0

    from backend.storage.vector.factory import get_vector_store

    target_store = get_vector_store(collection_name=collection if target_provider == "chroma" else None)
    # Ensure target distinguishes cache vs main — we migrate main collection only
    if hasattr(target_store, "table") and target_provider == "pgvector":
        # For pgvector, the main table is vector_chunks; ensure it exists
        pass

    # Batch upsert
    migrated = 0
    for start in range(0, total, args.batch):
        batch_docs = docs[start : start + args.batch]
        batch_metas = metas[start : start + args.batch]
        batch_ids = ids[start : start + args.batch]
        # Ensure tenant_id present
        tenants = set((m or {}).get("tenant_id", "default") for m in batch_metas)
        if len(tenants) > 1:
            # Group by tenant for correct scoping
            for tid in tenants:
                idxs = [i for i, m in enumerate(batch_metas) if (m or {}).get("tenant_id", "default") == tid]
                sub_docs = [batch_docs[i] for i in idxs]
                sub_metas = [batch_metas[i] for i in idxs]
                sub_ids = [batch_ids[i] for i in idxs]
                target_store.add_chunks(sub_docs, sub_metas, sub_ids, tenant_id=tid)
                migrated += len(sub_docs)
        else:
            tid = next(iter(tenants)) if tenants else "default"
            target_store.add_chunks(batch_docs, batch_metas, batch_ids, tenant_id=tid)
            migrated += len(batch_docs)
        print(f"Migrated {migrated}/{total}...")

    print(f"Done. Migrated {migrated} chunks to {target_provider}.")

    if args.verify_parity:
        print(f"\nParity check: query='{args.sample_query}' (n=3)")
        # Source query (Chroma)
        try:
            import chromadb

            client = chromadb.PersistentClient(path=args.chroma_path)
            coll = client.get_collection(name=collection)
            src_res = coll.query(query_texts=[args.sample_query], n_results=3)
            src_docs = src_res.get("documents", [[]])[0]
            print(f"  Chroma top 3: {[d[:60] for d in src_docs]}")
        except Exception as e:
            print(f"  Chroma query failed: {e}")
            src_docs = []

        try:
            tgt_res = target_store.query(args.sample_query, n_results=3, tenant_id=args.tenant or "default")
            tgt_docs = tgt_res.get("documents", [[]])[0]
            print(f"  {target_provider} top 3: {[d[:60] for d in tgt_docs]}")
            # Simple overlap check
            overlap = len(set(src_docs) & set(tgt_docs))
            print(f"  Overlap: {overlap}/3 (hash-fallback may differ — check embeddings)")
        except Exception as e:
            print(f"  {target_provider} query failed: {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
