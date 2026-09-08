from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from backend.api.routers.auth import get_current_user, DBUser
from backend.core.logging import get_logger
from backend.storage.db.session import get_db
from backend.storage.db.models import Document as DBDocument

router = APIRouter(prefix="/documents", tags=["documents"])
logger = get_logger(__name__)


class DocumentResponse(BaseModel):
    id: str
    filename: str
    status: str = "indexed"
    pages: int = 1
    chunks: int = 0
    file_size: int = 0
    created_at: str
    document_type: str = "text"


@router.get("", response_model=List[DocumentResponse])
async def list_documents(
    current_user: Annotated[DBUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    """List all ingested documents for the authenticated user's tenant."""
    tenant_id = current_user.tenant_id or current_user.user_uuid
    stmt = select(DBDocument).where(DBDocument.tenant_id == tenant_id).order_by(DBDocument.created_at.desc())
    result = await db.execute(stmt)
    docs = result.scalars().all()

    return [
        DocumentResponse(
            id=doc.document_id,
            filename=doc.filename,
            status="indexed",
            pages=1,
            chunks=doc.chunk_count or 0,
            file_size=0,
            created_at=doc.created_at.isoformat() if doc.created_at else "",
            document_type=doc.filename.split(".")[-1] if "." in doc.filename else "text",
        )
        for doc in docs
    ]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    fastapi_request: Request,
    current_user: Annotated[DBUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    """Delete a document and all its chunks from relational and vector storage."""
    tenant_id = current_user.tenant_id or current_user.user_uuid
    
    # 1. Delete from ChromaDB
    svc = getattr(fastapi_request.app.state, "svc", None)
    if svc and svc.store:
        try:
            svc.store.delete_document(document_id, tenant_id=tenant_id)
        except Exception as e:
            logger.warning("Failed to delete chunks from ChromaDB", error=str(e), document_id=document_id)

    # 2. Delete from relational DB
    stmt = delete(DBDocument).where(
        DBDocument.document_id == document_id,
        DBDocument.tenant_id == tenant_id,
    )
    await db.execute(stmt)
    await db.commit()
    logger.info("Deleted document", document_id=document_id, tenant_id=tenant_id)
    return None
