import asyncio
from pathlib import Path
from typing import Dict, List
from backend.core.logging import get_logger
from backend.ingestion.chunker import Chunker
from backend.storage.vector.chroma import ChromaStore

logger = get_logger(__name__)

VARIANTS = {
    "c500_o50": {"chunk_size": 500, "chunk_overlap": 50, "collection": "rag_collection_c500_o50"},
    "c700_o100": {"chunk_size": 700, "chunk_overlap": 100, "collection": "rag_collection_c700_o100"},
    "c1500_o300": {"chunk_size": 1500, "chunk_overlap": 300, "collection": "rag_collection_c1500_o300"},
}


def load_sample_documents(docs_dir: Path) -> List[Dict[str, str]]:
    docs = []
    if docs_dir.exists():
        for md_file in docs_dir.rglob("*.md"):
            try:
                text = md_file.read_text(encoding="utf-8")
                if text.strip():
                    docs.append({"id": md_file.stem, "text": text, "source": str(md_file)})
            except Exception as e:
                logger.warning("Could not read document file", file=str(md_file), error=str(e))

    # Fallback seed text if docs dir is sparse
    if not docs:
        docs.append({
            "id": "seed_architecture",
            "text": "The Self-Healing RAG pipeline leverages LangGraph state orchestration with eight modular nodes: routing, hybrid search fusing dense vectors and BM25, cross-encoder reranking, context-grounded generation, automated critique, query rewriting, and offline evaluation.",
            "source": "seed",
        })
    return docs


async def precompute_variant_collections(docs_path: Path = Path("docs")):
    docs = load_sample_documents(docs_path)
    logger.info("Loaded documents for chunking precomputation", total_docs=len(docs))

    for variant_name, config in VARIANTS.items():
        collection_name = config["collection"]
        chunker = Chunker(chunk_size=config["chunk_size"], chunk_overlap=config["chunk_overlap"])
        store = ChromaStore(collection_name=collection_name)

        all_chunks = []
        for doc in docs:
            chunks = chunker.split_text(doc["text"])
            for c in chunks:
                all_chunks.append({
                    "chunk_id": f"{doc['id']}_{c.chunk_id}",
                    "text": c.text,
                    "metadata": {
                        "document_id": doc["id"],
                        "source": doc["source"],
                        "chunk_variant": variant_name,
                        "tenant_id": "default",
                    }
                })

        logger.info(
            "Precomputed chunks for variant",
            variant=variant_name,
            collection=collection_name,
            total_chunks=len(all_chunks),
        )

        # Store into ChromaDB collection
        try:
            texts = [c["text"] for c in all_chunks]
            metadatas = [c["metadata"] for c in all_chunks]
            ids = [c["chunk_id"] for c in all_chunks]

            # Upsert into collection
            store.collection.upsert(
                documents=texts,
                metadatas=metadatas,
                ids=ids,
            )
            logger.info("Successfully populated collection", collection=collection_name, count=len(ids))
        except Exception as e:
            logger.warning("Failed to populate ChromaDB collection directly", collection=collection_name, error=str(e))


if __name__ == "__main__":
    asyncio.run(precompute_variant_collections())
