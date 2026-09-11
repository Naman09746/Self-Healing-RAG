import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from typing import Annotated, Optional, Union
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
try:
    from email_validator import validate_email, EmailNotValidError
except ImportError:
    import re
    _EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    class EmailNotValidError(ValueError):
        pass
    def validate_email(email: str, check_deliverability: bool = False):
        if not _EMAIL_REGEX.match(email):
            raise EmailNotValidError("Invalid email address format")
        return type("ValidEmail", (), {"normalized": email})

from backend.core.security import verify_password, create_access_token, get_password_hash, decode_access_token
from backend.core.audit import log_user_login, log_user_signup, log_auth_failure
from backend.core.rbac import Role
from backend.storage.db.session import get_db
from backend.storage.db.models import User as DBUser

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"api/v1/auth/login")

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None

class RefreshRequest(BaseModel):
    refresh_token: Optional[str] = None

class UserBase(BaseModel):
    email: str
    full_name: Optional[str] = None
    name: Optional[str] = None

class UserCreate(UserBase):
    password: str
    tenant_id: Optional[str] = None

    @field_validator('email')
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        try:
            validate_email(v, check_deliverability=False)
            return v
        except EmailNotValidError as e:
            raise ValueError(str(e))

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v

class UserResponse(BaseModel):
    id: Optional[int] = None
    email: str
    full_name: Optional[str] = None
    is_active: bool = True
    user_uuid: str
    tenant_id: str
    role: str = "viewer"

    model_config = ConfigDict(from_attributes=True)

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db)
) -> DBUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception
        
    result = await db.execute(select(DBUser).where(DBUser.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    
    return user

@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
async def signup(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check if user exists
    result = await db.execute(select(DBUser).where(DBUser.email == user_in.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists"
        )
    
    # Create new user with immutable user_uuid and default role
    user_uuid = str(uuid.uuid4())
    tenant_id = user_in.tenant_id or user_uuid  # If no tenant specified, user_uuid = tenant_id
    full_name = user_in.full_name or user_in.name or ""
    db_user = DBUser(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=full_name,
        user_uuid=user_uuid,
        tenant_id=tenant_id,
        role=Role.VIEWER.value,
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    # Audit log
    log_user_signup(email=user_in.email, tenant_id=tenant_id)

    access_token = create_access_token(
        subject=db_user.email,
        tenant_id=db_user.tenant_id,
        user_uuid=db_user.user_uuid,
        role=db_user.role or Role.VIEWER.value,
    )

    return Token(access_token=access_token, token_type="bearer")

@router.post("/login", response_model=Token)
async def login(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate user and return JWT access token.
    
    Supports both application/json (frontend client) and
    application/x-www-form-urlencoded (OAuth2 / Swagger UI).
    """
    content_type = request.headers.get("content-type", "")
    username = ""
    password = ""
    client_ip = request.client.host if request.client else "unknown"

    if "application/json" in content_type:
        try:
            body = await request.json()
            username = body.get("email") or body.get("username", "")
            password = body.get("password", "")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON body",
            )
    else:
        form = await request.form()
        username = form.get("username", "")
        password = form.get("password", "")

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email/username and password are required",
        )

    result = await db.execute(select(DBUser).where(DBUser.email == username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(password, user.hashed_password):
        log_auth_failure(
            email=username,
            ip_address=client_ip,
            reason="Invalid credentials",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        subject=user.email,
        tenant_id=user.tenant_id,
        user_uuid=user.user_uuid,
        role=user.role if hasattr(user, 'role') and user.role else Role.VIEWER.value,
    )

    # Audit log login success
    log_user_login(
        email=user.email,
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent", ""),
    )

    return Token(access_token=access_token, token_type="bearer")


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Refresh an access token using an existing valid token or refresh token payload."""
    token_str = ""
    try:
        body = await request.json()
        token_str = body.get("refresh_token") or ""
    except Exception:
        pass

    if not token_str:
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token_str = auth_header.split(" ", 1)[1]

    if not token_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token required for refresh",
        )

    try:
        payload = decode_access_token(token_str)
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    result = await db.execute(select(DBUser).where(DBUser.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    new_token = create_access_token(
        subject=user.email,
        tenant_id=user.tenant_id,
        user_uuid=user.user_uuid,
        role=user.role if hasattr(user, 'role') and user.role else Role.VIEWER.value,
    )

    return Token(access_token=new_token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
async def read_users_me(
    current_user: Annotated[DBUser, Depends(get_current_user)]
):
    return current_user
