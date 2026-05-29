"""
Security module for Fed-Med-FL Node API

Provides JWT authentication, RBAC, rate limiting, and audit logging.
"""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import redis
import json
import uuid
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db

# Security configuration
SECRET_KEY = getattr(settings, 'JWT_SECRET_KEY', 'fed-med-fl-secret-key-2026-change-in-production')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = getattr(settings, 'JWT_ACCESS_TOKEN_EXPIRE_MINUTES', 1440)  # 24 hours

# Security instances
security = HTTPBearer()

# Redis for rate limiting and session management
try:
    redis_client = redis.Redis(
        host=getattr(settings, 'REDIS_HOST', 'node1-redis'),
        port=getattr(settings, 'REDIS_PORT', 6379),
        db=1,  # Use DB 1 for security (DB 0 is for Celery)
        decode_responses=True
    )
    redis_client.ping()  # Test connection
except Exception as e:
    print(f"Warning: Redis connection failed: {e}")
    redis_client = None


class SecurityManager:
    """Central security manager for authentication, authorization, and auditing."""
    
    def __init__(self):
        self.rate_limits = {
            "admin": 1000,      # 1000 req/min
            "doctor": 100,      # 100 req/min
            "viewer": 30,       # 30 req/min
            "api_key": 500      # 500 req/min for inter-node
        }
        
        self.endpoint_limits = {
            "POST /api/inference": 10,          # 10 req/min
            "POST /api/models/train": 2,        # 2 req/hour
            "POST /api/datasets/upload": 5,     # 5 req/hour
            "POST /api/federated/train": 1      # 1 req/10min
        }
        
        self.permissions_map = {
            "admin": ["*"],  # Full access
            "doctor": [
                "read:models", "write:models", "write:inference", "read:inference",
                "read:datasets", "read:jobs", "read:inference_history"
            ],
            "viewer": [
                "read:models", "read:inference",
                "read:inference_history", "read:jobs"
            ]
        }
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against its hash using bcrypt directly."""
        try:
            # Ensure password is bytes and truncate to 72 bytes if needed
            password_bytes = plain_password.encode('utf-8')
            if len(password_bytes) > 72:
                password_bytes = password_bytes[:72]
            
            # Ensure hash is bytes
            if isinstance(hashed_password, str):
                hash_bytes = hashed_password.encode('utf-8')
            else:
                hash_bytes = hashed_password
            
            return bcrypt.checkpw(password_bytes, hash_bytes)
        except Exception as e:
            print(f"Password verification error: {e}")
            return False
    
    def get_password_hash(self, password: str) -> str:
        """Generate password hash using bcrypt directly."""
        try:
            # Ensure password is bytes and truncate to 72 bytes if needed
            password_bytes = password.encode('utf-8')
            if len(password_bytes) > 72:
                password_bytes = password_bytes[:72]
            
            # Generate salt and hash
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(password_bytes, salt)
            
            # Return as string
            return hashed.decode('utf-8')
        except Exception as e:
            print(f"Password hashing error: {e}")
            raise
    
    def validate_password_strength(self, password: str) -> tuple[bool, str]:
        """
        Validate password strength according to medical security standards.
        
        Returns:
            (is_valid, error_message)
        """
        if len(password) < 12:
            return False, "Password must be at least 12 characters long"
        
        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"
        
        if not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"
        
        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one number"
        
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            return False, "Password must contain at least one special character"
        
        return True, ""
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token."""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        # Add standard JWT claims
        jti = str(uuid.uuid4())  # JWT ID for blacklisting
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": jti,
            "iss": f"fed-med-fl-{settings.NODE_ID}",  # Issuer
            "aud": "fed-med-fl-api"  # Audience
        })
        
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        
        # Store session info in Redis for blacklisting
        if redis_client:
            session_data = {
                "user_id": data.get("sub"),
                "node_id": data.get("node_id"),
                "created_at": datetime.utcnow().isoformat()
            }
            redis_client.setex(
                f"session:{jti}", 
                int(expires_delta.total_seconds()) if expires_delta else ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                json.dumps(session_data)
            )
        
        return encoded_jwt
    
    def verify_token(self, token: str) -> dict:
        """Verify and decode JWT token."""
        try:
            # Decode without audience verification for now (can be added later)
            payload = jwt.decode(
                token, 
                SECRET_KEY, 
                algorithms=[ALGORITHM],
                options={"verify_aud": False}  # Disable audience verification
            )
            
            # Check if token is blacklisted
            jti = payload.get("jti")
            if jti and redis_client and redis_client.get(f"blacklist:{jti}"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked"
                )
            
            return payload
            
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Could not validate credentials: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    def revoke_token(self, jti: str) -> bool:
        """Add token to blacklist."""
        if not redis_client:
            return False
        
        # Add to blacklist with same expiry as original token
        session_key = f"session:{jti}"
        session_data = redis_client.get(session_key)
        
        if session_data:
            ttl = redis_client.ttl(session_key)
            if ttl > 0:
                redis_client.setex(f"blacklist:{jti}", ttl, "revoked")
                redis_client.delete(session_key)
                return True
        
        return False
    
    def check_rate_limit(self, user_id: str, role: str, endpoint: str = None, request_ip: str = None) -> tuple[bool, dict]:
        """
        Check rate limits for user and endpoint.
        
        Returns:
            (is_allowed, limit_info)
        """
        if not redis_client:
            return True, {}
        
        current_time = datetime.utcnow()
        minute_key = current_time.strftime("%Y-%m-%d-%H-%M")
        
        # General rate limit per role
        general_key = f"rate_limit:user:{user_id}:{minute_key}"
        general_limit = self.rate_limits.get(role, 30)
        
        # Endpoint-specific rate limit
        endpoint_key = f"rate_limit:endpoint:{user_id}:{endpoint}:{minute_key}"
        endpoint_limit = self.endpoint_limits.get(endpoint)
        
        # Check general limit
        current_general = redis_client.get(general_key)
        if current_general and int(current_general) >= general_limit:
            return False, {
                "limit_type": "general",
                "limit": general_limit,
                "current": int(current_general),
                "reset_time": (current_time.replace(second=0, microsecond=0) + timedelta(minutes=1)).isoformat()
            }
        
        # Check endpoint-specific limit
        if endpoint_limit:
            current_endpoint = redis_client.get(endpoint_key)
            if current_endpoint and int(current_endpoint) >= endpoint_limit:
                return False, {
                    "limit_type": "endpoint",
                    "limit": endpoint_limit,
                    "current": int(current_endpoint),
                    "reset_time": (current_time.replace(second=0, microsecond=0) + timedelta(minutes=1)).isoformat()
                }
        
        # Increment counters
        pipe = redis_client.pipeline()
        pipe.incr(general_key)
        pipe.expire(general_key, 60)  # Expire after 1 minute
        
        if endpoint_limit:
            pipe.incr(endpoint_key)
            pipe.expire(endpoint_key, 60)
        
        pipe.execute()
        
        return True, {
            "limit_type": "allowed",
            "general_limit": general_limit,
            "endpoint_limit": endpoint_limit
        }
    
    def get_user_permissions(self, role: str) -> List[str]:
        """Get permissions for a role."""
        return self.permissions_map.get(role, [])
    
    def has_permission(self, user_permissions: List[str], required_permission: str) -> bool:
        """Check if user has required permission."""
        if "*" in user_permissions:
            return True
        
        # Check exact match
        if required_permission in user_permissions:
            return True
        
        # Check wildcard permissions (e.g., "read:*" matches "read:models")
        for perm in user_permissions:
            if perm.endswith(":*"):
                prefix = perm[:-1]  # Remove "*"
                if required_permission.startswith(prefix):
                    return True
        
        return False
    
    async def log_audit_event(self, event_type: str, user_id: str, request: Request, 
                       additional_data: dict = None, db: Session = None, 
                       response_status: int = None, start_time: float = None):
        """Log security audit event with enhanced details."""
        try:
            from .database import AuditLog
            import time
            
            if not db:
                return
            
            # Calculate duration if start_time provided
            duration_ms = None
            if start_time:
                duration_ms = int((time.time() - start_time) * 1000)
            
            # Capture request body (safely)
            request_body = None
            try:
                if hasattr(request, '_body'):
                    body_bytes = request._body
                elif hasattr(request, 'body'):
                    body_bytes = await request.body()
                else:
                    body_bytes = b''
                
                if body_bytes:
                    body_text = body_bytes.decode('utf-8')
                    # Parse JSON if possible
                    try:
                        request_body = json.loads(body_text)
                    except:
                        request_body = body_text[:500]  # Limit to 500 chars
            except Exception:
                request_body = None
            
            # Capture query parameters
            query_params = dict(request.query_params) if request.query_params else {}
            
            # Enhanced details
            enhanced_details = {
                **(additional_data or {}),
                "request_details": {
                    "method": request.method,
                    "url": str(request.url),
                    "query_params": query_params,
                    "request_body": request_body,
                    "headers": {
                        "user-agent": request.headers.get("user-agent"),
                        "content-type": request.headers.get("content-type"),
                        "content-length": request.headers.get("content-length"),
                        "referer": request.headers.get("referer")
                    }
                }
            }
            
            audit_data = {
                "timestamp": datetime.utcnow(),
                "event_type": event_type,
                "user_id": user_id,
                "node_id": settings.NODE_ID,
                "endpoint": f"{request.method} {request.url.path}",
                "ip_address": request.client.host if request.client else None,
                "response_status": response_status,
                "duration_ms": duration_ms,
                "details": json.dumps(enhanced_details)
            }
            
            audit_log = AuditLog(**audit_data)
            db.add(audit_log)
            db.commit()
            
        except Exception as e:
            print(f"Failed to log audit event: {e}")


# Global security manager instance
security_manager = SecurityManager()


# FastAPI Dependencies
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> dict:
    """Get current authenticated user from JWT token."""
    token = credentials.credentials
    payload = security_manager.verify_token(token)
    
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing user ID"
        )
    
    # Get user from database to ensure they still exist and are active
    from .database import User
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled"
        )
    
    # Check account lockout
    if user.locked_until and user.locked_until > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked until {user.locked_until.isoformat()}"
        )
    
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "node_id": user.node_id,
        "permissions": security_manager.get_user_permissions(user.role),
        "is_active": user.is_active,
        "last_login": user.last_login
    }


def require_permission(permission: str):
    """Dependency factory for permission-based access control."""
    def permission_checker(
        current_user: dict = Depends(get_current_user)
    ) -> dict:
        if not security_manager.has_permission(current_user["permissions"], permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {permission}"
            )
        return current_user
    
    return permission_checker


def require_role(role: str):
    """Dependency factory for role-based access control."""
    def role_checker(
        current_user: dict = Depends(get_current_user)
    ) -> dict:
        if current_user["role"] != role and current_user["role"] != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient role. Required: {role}"
            )
        return current_user
    
    return role_checker


async def rate_limit_check(
    request: Request,
    current_user: dict = Depends(get_current_user)
) -> dict:
    """Check rate limits for current user and endpoint."""
    endpoint = f"{request.method} {request.url.path}"
    ip_address = request.client.host if request.client else None
    
    is_allowed, limit_info = security_manager.check_rate_limit(
        user_id=current_user["id"],
        role=current_user["role"],
        endpoint=endpoint,
        request_ip=ip_address
    )
    
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(limit_info.get("limit", 0)),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": limit_info.get("reset_time", ""),
                "Retry-After": "60"
            }
        )
    
    return current_user


def audit_log_middleware(event_type: str, additional_data: dict = None):
    """Middleware factory for audit logging."""
    def audit_decorator(
        request: Request,
        current_user: dict = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        security_manager.log_audit_event(
            event_type=event_type,
            user_id=current_user["id"],
            request=request,
            additional_data=additional_data,
            db=db
        )
        return current_user
    
    return audit_decorator


# API Key authentication for inter-node communication
async def verify_api_key(
    request: Request,
    db: Session = Depends(get_db)
) -> dict:
    """Verify API key for inter-node communication."""
    api_key = request.headers.get("X-API-Key")
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    
    # Hash the provided key for comparison
    from .database import ApiKey
    import hashlib
    
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    api_key_record = db.query(ApiKey).filter(
        ApiKey.key_hash == key_hash,
        ApiKey.is_active == True,
        ApiKey.expires_at > datetime.utcnow()
    ).first()
    
    if not api_key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key"
        )
    
    # Update last used timestamp
    api_key_record.last_used = datetime.utcnow()
    db.commit()
    
    return {
        "api_key_id": api_key_record.id,
        "node_id": api_key_record.node_id,
        "permissions": json.loads(api_key_record.permissions),
        "type": "api_key"
    }


# Optional authentication (for endpoints that work with both auth types)
async def optional_auth(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[dict]:
    """Optional authentication - try JWT first, then API key, then allow anonymous."""
    try:
        # Try JWT authentication
        credentials = await security(request)
        return await get_current_user(credentials, db)
    except:
        try:
            # Try API key authentication
            return await verify_api_key(request, db)
        except:
            # Allow anonymous access
            return None