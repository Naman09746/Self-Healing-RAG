import asyncio
import logging
from backend.core.config import settings
from backend.storage.vector.embeddings import EmbeddingProvider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def reset_vector_db():
    provider = getattr(settings, "VECTOR_STORE_PROVIDER", "pgvector").lower()
    logger.info(f"Resetting vector database for provider: {provider}")

    if provider == "pgvector":
        from backend.storage.vector.pgvector import PgVectorStore
        from sqlalchemy import text
        
        # We need to truncate both document_chunks and query_cache_chunks
        tables = ["vector_chunks", "query_cache_chunks", "document_chunks"]
        
        # Use any instance to get the sessionmaker
        store = PgVectorStore(table="vector_chunks")
        sess_maker = store._get_sessionmaker()
        
        async with sess_maker() as session:
            for table in tables:
                try:
                    await session.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE;"))
                    logger.info(f"Successfully dropped table: {table}")
                except Exception as e:
                    logger.error(f"Failed to drop {table}: {e}")
            await session.commit()
            
    elif provider == "qdrant":
        from backend.storage.vector.qdrant import QdrantStore
        
        # Initialize instances to get access to client
        doc_store = QdrantStore(collection_name="document_chunks")
        cache_store = QdrantStore(collection_name="query_cache", is_cache=True)
        
        collections = ["document_chunks", "query_cache"]
        client = doc_store._client
        for coll in collections:
            try:
                if client.collection_exists(coll):
                    client.delete_collection(coll)
                    logger.info(f"Successfully deleted collection: {coll}")
                else:
                    logger.info(f"Collection {coll} does not exist, skipping.")
            except Exception as e:
                logger.error(f"Failed to delete Qdrant collection {coll}: {e}")
                
    elif provider == "pinecone":
        from backend.storage.vector.pinecone import PineconeStore
        import pinecone
        
        doc_store = PineconeStore()
        index = doc_store._index
        
        if index:
            try:
                logger.warning("To fully reset Pinecone, please delete all vectors in your index manually or via the Pinecone console, as namespace enumeration is not strictly supported without tracking.")
            except Exception as e:
                logger.error(f"Failed to interact with Pinecone: {e}")
    else:
        logger.error(f"Unknown vector store provider: {provider}")

if __name__ == "__main__":
    asyncio.run(reset_vector_db())
