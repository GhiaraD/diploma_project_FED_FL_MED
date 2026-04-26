"""
Authentication endpoints for Fed-Med-FL Node API.

Provides login, logout, user management, and API key management.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List
import hashlib
import secrets
import json

from .database import get_db, User, ApiKey, AuditLog
from .schemas import (
    Token, UserCreate, UserResponse, PasswordChange,
    ApiKeyCreate, ApiKeyResponse, ApiKeyCreateResponse,
    AuditLogResponse, SecurityMetrics
)
from .security import security_manager, get_current_user, require_role, audit_log_middleware, ACCESS_TOKEN_EXPIRE_MINUTES
from .config import settings

router = APIRouter(prefix="/api/auth", tags=["authentication"])


# ============================================================================
# Authentication Endpoints
# ============================================================================

@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT token.
    
    **Security Features:**
    - Account lockout after 5 failed attempts
    - Password strength validation
    - Audit logging
    - Rate limiting
    """
    import time
    start_time = time.time()
    
    # Find user by email
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user:
        # Log failed login attempt
        await security_manager.log_audit_event(
            event_type="login_failed",
            user_id="unknown",
            request=request,
            additional_data={"reason": "user_not_found", "email": form_data.username},
            db=db,
            response_status=401,
            start_time=start_time
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Check if account is locked
    if user.locked_until and user.locked_until > datetime.utcnow():
        await security_manager.log_audit_event(
            event_type="login_blocked",
            user_id=user.id,
            request=request,
            additional_data={"reason": "account_locked", "locked_until": user.locked_until.isoformat()},
            db=db,
            response_status=423,
            start_time=start_time
        )
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked until {user.locked_until.isoformat()}"
        )
    
    # Verify password
    if not security_manager.verify_password(form_data.password, user.password_hash):
        # Increment failed login attempts
        user.failed_login_attempts += 1
        
        # Lock account after 5 failed attempts for 30 minutes
        if user.failed_login_attempts >= 5:
            user.locked_until = datetime.utcnow() + timedelta(minutes=30)
            
        db.commit()
        
        await security_manager.log_audit_event(
            event_type="login_failed",
            user_id=user.id,
            request=request,
            additional_data={
                "reason": "invalid_password",
                "failed_attempts": user.failed_login_attempts,
                "locked": user.locked_until is not None
            },
            db=db,
            response_status=401,
            start_time=start_time
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Check if user is active
    if not user.is_active:
        await security_manager.log_audit_event(
            event_type="login_blocked",
            user_id=user.id,
            request=request,
            additional_data={"reason": "user_inactive"},
            db=db,
            response_status=401,
            start_time=start_time
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled"
        )
    
    # Successful login - reset failed attempts and update last login
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Create JWT token
    access_token = security_manager.create_access_token(
        data={
            "sub": user.id,
            "email": user.email,
            "role": user.role,
            "node_id": user.node_id,
            "permissions": security_manager.get_user_permissions(user.role)
        }
    )
    
    # Log successful login
    await security_manager.log_audit_event(
        event_type="login_success",
        user_id=user.id,
        request=request,
        additional_data={"role": user.role, "node_id": user.node_id},
        db=db,
        response_status=200,
        start_time=start_time
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert minutes to seconds
        "user": UserResponse.from_orm(user)
    }


@router.post("/logout")
async def logout(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout user and revoke JWT token.
    """
    import time
    start_time = time.time()
    
    # Extract JWT ID from token for blacklisting
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            import jwt
            payload = jwt.decode(token, options={"verify_signature": False})
            jti = payload.get("jti")
            
            if jti:
                security_manager.revoke_token(jti)
        except:
            pass  # Token might be malformed, but we still log the logout
    
    # Log logout event
    await security_manager.log_audit_event(
        event_type="logout",
        user_id=current_user["id"],
        request=request,
        db=db,
        response_status=200,
        start_time=start_time
    )
    
    return {"message": "Successfully logged out"}


@router.post("/change-password")
async def change_password(
    request: Request,
    password_data: PasswordChange,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change user password.
    """
    import time
    start_time = time.time()
    user = db.query(User).filter(User.id == current_user["id"]).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify current password
    if not security_manager.verify_password(password_data.current_password, user.password_hash):
        await security_manager.log_audit_event(
            event_type="password_change_failed",
            user_id=user.id,
            request=request,
            additional_data={"reason": "invalid_current_password"},
            db=db,
            response_status=400,
            start_time=start_time
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Validate new password strength
    is_valid, error_message = security_manager.validate_password_strength(password_data.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message
        )
    
    # Update password
    user.password_hash = security_manager.get_password_hash(password_data.new_password)
    user.password_changed_at = datetime.utcnow()
    db.commit()
    
    # Log password change
    await security_manager.log_audit_event(
        event_type="password_changed",
        user_id=user.id,
        request=request,
        db=db,
        response_status=200,
        start_time=start_time
    )
    
    return {"message": "Password changed successfully"}


# ============================================================================
# User Management (Admin Only)
# ============================================================================

@router.post("/users", response_model=UserResponse)
async def create_user(
    request: Request,
    user_data: UserCreate,
    current_user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """
    Create new user (admin only).
    """
    import time
    start_time = time.time()
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Validate password strength
    is_valid, error_message = security_manager.validate_password_strength(user_data.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message
        )
    
    # Create user
    hashed_password = security_manager.get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        password_hash=hashed_password,
        role=user_data.role,
        node_id=user_data.node_id
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Log user creation
    await security_manager.log_audit_event(
        event_type="user_created",
        user_id=current_user["id"],
        request=request,
        additional_data={
            "created_user_id": user.id,
            "created_user_email": user.email,
            "created_user_role": user.role
        },
        db=db,
        response_status=200,
        start_time=start_time
    )
    
    return UserResponse.from_orm(user)


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    current_user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """
    List all users (admin only).
    """
    users = db.query(User).all()
    return [UserResponse.from_orm(user) for user in users]


@router.put("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    request: Request,
    current_user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """
    Deactivate user account (admin only).
    """
    import time
    start_time = time.time()
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = False
    db.commit()
    
    # Log user deactivation
    await security_manager.log_audit_event(
        event_type="user_deactivated",
        user_id=current_user["id"],
        request=request,
        additional_data={
            "deactivated_user_id": user.id,
            "deactivated_user_email": user.email
        },
        db=db,
        response_status=200,
        start_time=start_time
    )
    
    return {"message": f"User {user.email} deactivated successfully"}


# ============================================================================
# API Key Management
# ============================================================================

@router.post("/api-keys", response_model=ApiKeyCreateResponse)
async def create_api_key(
    request: Request,
    api_key_data: ApiKeyCreate,
    current_user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """
    Create new API key for inter-node communication (admin only).
    """
    import time
    start_time = time.time()
    # Generate secure random API key
    api_key = f"fed_med_fl_{api_key_data.node_id}_{secrets.token_urlsafe(32)}"
    
    # Hash the key for storage
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    # Calculate expiry date
    expires_at = datetime.utcnow() + timedelta(days=api_key_data.expires_days)
    
    # Create API key record
    api_key_record = ApiKey(
        key_hash=key_hash,
        node_id=api_key_data.node_id,
        permissions=json.dumps(api_key_data.permissions),
        expires_at=expires_at,
        created_by=current_user["id"]
    )
    
    db.add(api_key_record)
    db.commit()
    db.refresh(api_key_record)
    
    # Log API key creation
    await security_manager.log_audit_event(
        event_type="api_key_created",
        user_id=current_user["id"],
        request=request,
        additional_data={
            "api_key_id": api_key_record.id,
            "target_node_id": api_key_data.node_id,
            "permissions": api_key_data.permissions,
            "expires_at": expires_at.isoformat()
        },
        db=db,
        response_status=200,
        start_time=start_time
    )
    
    return ApiKeyCreateResponse(
        api_key=api_key,  # Only returned once!
        key_info=ApiKeyResponse.from_orm(api_key_record)
    )


@router.get("/api-keys", response_model=List[ApiKeyResponse])
async def list_api_keys(
    current_user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """
    List all API keys (admin only).
    """
    api_keys = db.query(ApiKey).all()
    return [ApiKeyResponse.from_orm(key) for key in api_keys]


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    request: Request,
    current_user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """
    Revoke API key (admin only).
    """
    import time
    start_time = time.time()
    api_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    api_key.is_active = False
    db.commit()
    
    # Log API key revocation
    await security_manager.log_audit_event(
        event_type="api_key_revoked",
        user_id=current_user["id"],
        request=request,
        additional_data={
            "api_key_id": key_id,
            "target_node_id": api_key.node_id
        },
        db=db,
        response_status=200,
        start_time=start_time
    )
    
    return {"message": "API key revoked successfully"}


# ============================================================================
# Audit & Monitoring
# ============================================================================

@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    limit: int = 100,
    offset: int = 0,
    event_type: str = None,
    user_id: str = None,
    current_user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """
    Get audit logs (admin only).
    """
    query = db.query(AuditLog).order_by(AuditLog.timestamp.desc())
    
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)
    
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    
    logs = query.offset(offset).limit(limit).all()
    
    return [AuditLogResponse.from_orm(log) for log in logs]


@router.get("/security-metrics", response_model=SecurityMetrics)
async def get_security_metrics(
    current_user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """
    Get security metrics for monitoring dashboard (admin only).
    """
    # Calculate metrics from audit logs
    now = datetime.utcnow()
    hour_ago = now - timedelta(hours=1)
    day_ago = now - timedelta(days=1)
    
    # Authentication metrics
    successful_logins = db.query(AuditLog).filter(
        AuditLog.event_type == "login_success",
        AuditLog.timestamp >= day_ago
    ).count()
    
    failed_logins = db.query(AuditLog).filter(
        AuditLog.event_type == "login_failed",
        AuditLog.timestamp >= day_ago
    ).count()
    
    failed_logins_last_hour = db.query(AuditLog).filter(
        AuditLog.event_type == "login_failed",
        AuditLog.timestamp >= hour_ago
    ).count()
    
    # Authorization metrics
    permission_denials = db.query(AuditLog).filter(
        AuditLog.event_type == "permission_denied",
        AuditLog.timestamp >= day_ago
    ).count()
    
    # Active users
    active_users = db.query(User).filter(User.is_active == True).count()
    
    return SecurityMetrics(
        authentication={
            "successful_logins": successful_logins,
            "failed_logins": failed_logins,
            "active_users": active_users
        },
        authorization={
            "permission_denials": permission_denials
        },
        rate_limiting={
            "blocked_requests": 0  # Would need Redis metrics
        },
        audit={
            "total_events": db.query(AuditLog).filter(AuditLog.timestamp >= day_ago).count()
        },
        active_sessions=0,  # Would need Redis session count
        failed_logins_last_hour=failed_logins_last_hour
    )


# ============================================================================
# User Profile
# ============================================================================

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user profile.
    """
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse.from_orm(user)