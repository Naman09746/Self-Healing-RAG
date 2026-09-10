from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import Annotated
from backend.ingestion.pipeline import IngestionPipeline
from backend.core.logging import get_logger
from backend.api.routers.auth import get_current_user, DBUser
import shutil
import os
from pathlib import Path

router = APIRouter(prefix="/ingest", tags=["ingestion"])
logger = get_logger(__name__)
# Lazy factory so tests can patch VECTOR_STORE_PROVIDER without import-time Chroma init
def _get_pipeline() -> IngestionPipeline:
    return IngestionPipeline()

pipeline = _get_pipeline()

from backend.storage.db.session import get_db
from backend.storage.db.models import Document as DBDocument
from sqlalchemy.ext.asyncio import AsyncSession

TEMP_DIR = Path("temp_uploads")
TEMP_DIR.mkdir(exist_ok=True)

@router.post("")
@router.post("/file")
async def ingest_file(
    file: UploadFile = File(...),
    current_user: Annotated[DBUser, Depends(get_current_user)] = None,
    db: AsyncSession = Depends(get_db),
):
    """Upload and ingest a file into hybrid, sparse, and graph storage.

    Tenant identity is derived from the authenticated user's JWT, **not**
    from the request body. This prevents cross-tenant data injection.
    Authentication is **required** — unauthenticated requests are rejected
    by the ``get_current_user`` dependency.
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    file_path = TEMP_DIR / file.filename
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        tenant_id = current_user.tenant_id or current_user.user_uuid
        result = await pipeline.ingest_file(str(file_path), tenant_id=tenant_id)

        # Persist document metadata in relational storage for document management
        try:
            db_doc = DBDocument(
                document_id=result["document_id"],
                tenant_id=tenant_id,
                filename=file.filename,
                chunk_count=result.get("chunk_count", 0),
            )
            db.add(db_doc)
            await db.commit()
        except Exception as db_err:
            logger.warning("Could not persist DBDocument record", error=str(db_err))

        logger.info("Ingestion complete", file_name=file.filename, tenant_id=tenant_id, user_uuid=current_user.user_uuid)
        return result
    except Exception as e:
        logger.error("Ingestion failed", error=str(e), user_uuid=current_user.user_uuid)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if file_path.exists():
            os.remove(file_path)
