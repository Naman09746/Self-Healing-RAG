from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import Annotated
from backend.ingestion.pipeline import IngestionPipeline
from backend.core.logging import get_logger
from backend.api.routers.auth import get_current_user, DBUser
from backend.core.rbac import Role, ROLE_PERMISSIONS, Permission, has_db_permission_for_user
import shutil
import os
from pathlib import Path

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB — ChatGPT/Gemini level (up to 50MB per file)
# Production allowlist — all formats handled by DocumentLoader with zero-mistake guarantee
ALLOWED_EXTS = {
    ".pdf",  # PDF (text + scanned OCR + tables)
    ".txt", ".md", ".markdown", ".rst", ".json", ".jsonl", ".ndjson", ".yaml", ".yml", ".xml", ".html", ".htm", ".xhtml",
    ".csv", ".tsv", ".psv", ".log", ".ini", ".cfg", ".sql", ".py", ".js", ".java", ".cpp", ".c", ".go", ".rs", ".php", ".rb", ".sh", ".toml",
    ".docx", ".doc", ".odt", ".rtf",  # Word
    ".pptx", ".ppt",  # PowerPoint
    ".xlsx", ".xls", ".ods",  # Excel
    ".epub",  # eBook
    ".png", ".jpg", ".jpeg", ".webp", ".tiff", ".tif", ".bmp", ".gif", ".heic", ".heif",  # Images via OCR
}
# Extensions that require OCR (images + scanned PDFs handled inside loader)
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tiff", ".tif", ".bmp", ".gif", ".heic", ".heif"}

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
    """Upload and ingest a file into hybrid, sparse, and graph storage — permissive, tenant-isolated.

    Tenant identity is derived from the authenticated user's DB record (`current_user.tenant_id`),
    **not** from request body, JWT, or query param. Any authenticated role with `ingest:document`
    (viewer/editor/admin) can ingest **only into their own tenant**. Cross-tenant spoofing is rejected.
    DB role is canonical; stale JWT role is ignored (self-healing).
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Centralized RBAC via DB role (not JWT) — viewer now has ingest:document (permissive, tenant-isolated)
    if not has_db_permission_for_user(current_user, Permission.INGEST_DOCUMENT):
        raise HTTPException(status_code=403, detail=f"Not enough permissions: role '{getattr(current_user, 'role', 'viewer')}' cannot ingest. Requires ingest:document")

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

        # Compute file hash for dedup (SHA256 of bytes) — production dedup like ChatGPT
        import hashlib
        file_hash = ""
        try:
            h = hashlib.sha256()
            with open(file_path, "rb") as fh:
                for blk in iter(lambda: fh.read(8192), b""):
                    h.update(blk)
            file_hash = h.hexdigest()
            # Check if same file already ingested for this tenant (idempotent)
            from sqlalchemy import select
            existing_q = await db.execute(
                select(DBDocument).where(DBDocument.tenant_id == tenant_id, DBDocument.content_hash == file_hash).limit(1)
            )
            existing = existing_q.scalar_one_or_none()
            if existing:
                logger.info("Duplicate file detected, returning existing", file_name=safe_name, tenant_id=tenant_id, existing_id=existing.document_id, file_hash=file_hash[:12])
                return {
                    "document_id": existing.document_id,
                    "file_name": existing.filename,
                    "chunk_count": existing.chunk_count or 0,
                    "file_hash": file_hash,
                    "status": "duplicate",
                    "message": "File already ingested (dedup by content hash)",
                }
        except HTTPException:
            raise
        except Exception as e:
            logger.debug("Dedup check failed, proceeding with ingest", error=str(e))

        result = await pipeline.ingest_file(str(file_path), tenant_id=tenant_id)
        # Pipeline already computed file_hash, but use our precomputed for DB
        result_file_hash = result.get("file_hash") or file_hash

        # Persist document metadata in relational storage for document management
        try:
            db_doc = DBDocument(
                document_id=result["document_id"],
                tenant_id=tenant_id,
                filename=safe_name,
                chunk_count=result.get("chunk_count", 0),
                content_hash=result_file_hash,
            )
            db.add(db_doc)
            await db.commit()
            await db.refresh(db_doc)
        except Exception as db_err:
            logger.warning("Could not persist DBDocument record", error=str(db_err))
            try:
                await db.rollback()
            except Exception:
                pass

        logger.info("Ingestion complete", file_name=safe_name, tenant_id=tenant_id, user_uuid=current_user.user_uuid, file_hash=result_file_hash[:12], chunks=result.get("chunk_count", 0), mime_type=result.get("mime_type"))
        # Return enriched result with file metadata
        return {
            "document_id": result["document_id"],
            "file_name": safe_name,
            "chunk_count": result.get("chunk_count", 0),
            "file_hash": result_file_hash,
            "mime_type": result.get("mime_type"),
            "file_size": bytes_written,
            "storage": result.get("storage", ["vector", "sparse", "graph"]),
            "status": "ingested",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Ingestion failed", error=str(e), user_uuid=current_user.user_uuid if current_user else None)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if file_path.exists():
            try:
                os.remove(file_path)
            except Exception:
                pass


@router.post("/batch")
async def ingest_batch(
    files: list[UploadFile] = File(...),
    current_user: Annotated[DBUser, Depends(get_current_user)] = None,
    db: AsyncSession = Depends(get_db),
):
    """Batch ingest — upload up to 10 files at once (ChatGPT/Gemini style), tenant-isolated.

    Each file is validated, deduped (by content hash per tenant), and ingested independently.
    Tenant is always `current_user.tenant_id` (DB canonical); stale JWT and cross-tenant spoofing rejected.
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not has_db_permission_for_user(current_user, Permission.INGEST_DOCUMENT):
        raise HTTPException(status_code=403, detail="Not enough permissions: requires ingest:document")

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Batch limit is 10 files per request")
    tenant_id = current_user.tenant_id or current_user.user_uuid
    results = []
    for f in files:
        try:
            # Reuse single-file logic via internal call (avoid code dup by calling pipeline directly)
            # We create a temp file per upload and ingest
            raw_name = f.filename or "upload.bin"
            safe_name = Path(raw_name).name.replace("\x00", "").strip()
            if not safe_name or safe_name in {".", ".."}:
                results.append({"file_name": raw_name, "status": "failed", "error": "Invalid filename"})
                continue
            ext = Path(safe_name).suffix.lower()
            if ext and ext not in ALLOWED_EXTS:
                logger.warning("Batch upload unusual extension", filename=safe_name, ext=ext)
            # Write temp
            import uuid, hashlib
            temp_name = f"{uuid.uuid4().hex}_{safe_name}"
            file_path = TEMP_DIR / temp_name
            bytes_written = 0
            with file_path.open("wb") as buf:
                while True:
                    chunk = await f.read(1024*1024)
                    if not chunk:
                        break
                    bytes_written += len(chunk)
                    if bytes_written > MAX_FILE_SIZE:
                        raise HTTPException(status_code=413, detail=f"{safe_name} too large")
                    buf.write(chunk)
            if bytes_written == 0:
                results.append({"file_name": safe_name, "status": "failed", "error": "Empty file"})
                try:
                    file_path.unlink(missing_ok=True)
                except Exception:
                    pass
                continue
            # Dedup check
            h = hashlib.sha256()
            with open(file_path, "rb") as fh:
                for blk in iter(lambda: fh.read(8192), b""):
                    h.update(blk)
            file_hash = h.hexdigest()
            from sqlalchemy import select
            existing_q = await db.execute(select(DBDocument).where(DBDocument.tenant_id == tenant_id, DBDocument.content_hash == file_hash).limit(1))
            existing = existing_q.scalar_one_or_none()
            if existing:
                results.append({"file_name": safe_name, "document_id": existing.document_id, "status": "duplicate", "file_hash": file_hash})
                try:
                    file_path.unlink(missing_ok=True)
                except Exception:
                    pass
                continue
            # Ingest
            res = await pipeline.ingest_file(str(file_path), tenant_id=tenant_id)
            db_doc = DBDocument(document_id=res["document_id"], tenant_id=tenant_id, filename=safe_name, chunk_count=res.get("chunk_count",0), content_hash=file_hash)
            db.add(db_doc)
            await db.commit()
            await db.refresh(db_doc)
            results.append({"file_name": safe_name, "document_id": res["document_id"], "chunk_count": res.get("chunk_count",0), "file_hash": file_hash, "mime_type": res.get("mime_type"), "status": "ingested"})
            try:
                file_path.unlink(missing_ok=True)
            except Exception:
                pass
        except HTTPException as he:
            results.append({"file_name": getattr(f, 'filename', 'unknown'), "status": "failed", "error": he.detail})
        except Exception as e:
            logger.error("Batch ingest failed for file", error=str(e), file_name=getattr(f, 'filename', 'unknown'))
            results.append({"file_name": getattr(f, 'filename', 'unknown'), "status": "failed", "error": "Ingestion failed"})
            try:
                await db.rollback()
            except Exception:
                pass
            try:
                if 'file_path' in locals() and file_path.exists():
                    file_path.unlink(missing_ok=True)
            except Exception:
                pass
    return {"results": results, "total": len(files), "ingested": sum(1 for r in results if r.get("status")=="ingested"), "duplicates": sum(1 for r in results if r.get("status")=="duplicate")}
