from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import Annotated
from backend.ingestion.pipeline import IngestionPipeline
from backend.core.logging import get_logger
from backend.api.routers.auth import get_current_user, DBUser
from backend.core.rbac import Role, ROLE_PERMISSIONS, Permission
import shutil
import os
from pathlib import Path

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_EXTS = {".pdf", ".txt", ".md", ".markdown", ".rst", ".json", ".csv", ".html", ".docx"}

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
    by the ``get_current_user`` dependency. Ingestion also requires
    ``ingest:document`` permission (editor/admin).
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # RBAC: viewer/auditor cannot ingest
    try:
        role = Role(current_user.role or "viewer")
        perms = ROLE_PERMISSIONS.get(role, set())
        if Permission.INGEST_DOCUMENT not in perms:
            raise HTTPException(status_code=403, detail="Not enough permissions: requires ingest:document")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # Sanitize filename — prevent path traversal and null bytes
    raw_name = file.filename or "upload.bin"
    safe_name = Path(raw_name).name  # strips directory components
    safe_name = safe_name.replace("\x00", "").strip()
    if not safe_name or safe_name in {".", ".."} or "/" in raw_name or "\\" in raw_name or ".." in raw_name:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if len(safe_name) > 255:
        raise HTTPException(status_code=400, detail="Filename too long")
    # Optional extension allowlist (warn but allow fallback to text)
    ext = Path(safe_name).suffix.lower()
    if ext and ext not in ALLOWED_EXTS:
        logger.warning("Upload with unusual extension", filename=safe_name, ext=ext)

    # Enforce size limit early via Content-Length if available, then stream with cap
    if getattr(file, "size", None) is not None and file.size is not None:
        try:
            if int(file.size) > MAX_FILE_SIZE:
                raise HTTPException(status_code=413, detail=f"File too large: limit is {MAX_FILE_SIZE // (1024*1024)} MB")
        except HTTPException:
            raise
        except Exception:
            pass

    file_path = TEMP_DIR / safe_name
    # Ensure TEMP_DIR exists and file_path is inside it (defense in depth)
    try:
        file_path.resolve().relative_to(TEMP_DIR.resolve())
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid file path")

    # Generate unique temp name to avoid collisions
    import uuid
    temp_name = f"{uuid.uuid4().hex}_{safe_name}"
    file_path = TEMP_DIR / temp_name
    bytes_written = 0
    try:
        with file_path.open("wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > MAX_FILE_SIZE:
                    raise HTTPException(status_code=413, detail=f"File too large: limit is {MAX_FILE_SIZE // (1024*1024)} MB")
                buffer.write(chunk)

        if bytes_written == 0:
            raise HTTPException(status_code=400, detail="Empty file")

        tenant_id = current_user.tenant_id or current_user.user_uuid
        result = await pipeline.ingest_file(str(file_path), tenant_id=tenant_id)

        # Persist document metadata in relational storage for document management
        try:
            db_doc = DBDocument(
                document_id=result["document_id"],
                tenant_id=tenant_id,
                filename=safe_name,
                chunk_count=result.get("chunk_count", 0),
            )
            db.add(db_doc)
            await db.commit()
        except Exception as db_err:
            logger.warning("Could not persist DBDocument record", error=str(db_err))

        logger.info("Ingestion complete", file_name=safe_name, tenant_id=tenant_id, user_uuid=current_user.user_uuid)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Ingestion failed", error=str(e), user_uuid=current_user.user_uuid)
        # Do not leak internal file_path
        raise HTTPException(status_code=500, detail="Ingestion failed")
    finally:
        try:
            if file_path.exists():
                os.remove(file_path)
        except Exception:
            pass
