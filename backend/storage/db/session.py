from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from backend.core.config import settings
from backend.core.logging import get_logger

# Neon DNS workaround for local resolver intermittently failing on
# ep-cold-hill-b35d4g9r.c-4.ap-southeast-1.aws.neon.tech (see diagnostics).
import socket as _socket

_orig_getaddrinfo = _socket.getaddrinfo
_NEON_IPS = ["52.76.246.190", "52.76.212.156", "3.0.27.201"]


def _patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    try:
        return _orig_getaddrinfo(host, port, family, type, proto, flags)
    except _socket.gaierror as e:
        if host and "neon.tech" in host:
            return [(_socket.AF_INET, _socket.SOCK_STREAM, 6, "", (ip, port)) for ip in _NEON_IPS[:1]]
        raise


try:
    _socket.getaddrinfo = _patched_getaddrinfo
except Exception:
    pass

logger = get_logger(__name__)

# NullPool is used for asyncpg with FastAPI/Starlette to prevent
# "Future attached to a different loop" errors across requests and lifespan background tasks.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    from backend.storage.db.models import Base, User
    from backend.core.security import get_password_hash
    from backend.core.rbac import Role
    from sqlalchemy import select
    import uuid

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed default admin user if no users exist
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(User).limit(1))
            if not result.scalar_one_or_none():
                admin_uuid = str(uuid.uuid4())
                admin_user = User(
                    email="admin@self-healing-rag.local",
                    hashed_password=get_password_hash("Admin12345!"),
                    full_name="System Administrator",
                    user_uuid=admin_uuid,
                    tenant_id="default",
                    role=Role.ADMIN.value,
                    is_active=True,
                )
                session.add(admin_user)
                await session.commit()
                logger.info("Seeded initial admin user: admin@self-healing-rag.local")
        except Exception as e:
            logger.warning("Could not seed default admin user", error=str(e))