# Fed-Med-FL Security Architecture

**Data**: 2026-04-26  
**Versiune**: 1.0  
**Status**: Design & Implementation

---

## 🎯 Obiective Securitate

### Principii de Bază
1. **Authentication**: Verificarea identității utilizatorilor și nodurilor
2. **Authorization**: Control granular al accesului la resurse
3. **Confidentiality**: Protecția datelor medicale sensibile
4. **Integrity**: Verificarea integrității modelelor și datelor
5. **Auditability**: Logging complet pentru compliance medical
6. **Non-repudiation**: Dovezi criptografice pentru acțiuni

### Compliance
- **GDPR**: Protecția datelor personale
- **HIPAA**: Securitatea datelor medicale (US)
- **ISO 27001**: Management securității informației

---

## 🏗️ Arhitectură Securitate

```
┌─────────────────────────────────────────────────────────────┐
│                    Security Layer                           │
├─────────────────────────────────────────────────────────────┤
│  JWT Auth │ RBAC │ API Keys │ Rate Limit │ Audit │ mTLS    │
├─────────────────────────────────────────────────────────────┤
│                   Application Layer                         │
├─────────────────────────────────────────────────────────────┤
│   Node APIs   │   Central API   │   Flower gRPC   │   UI    │
├─────────────────────────────────────────────────────────────┤
│                   Infrastructure                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔐 Componente Securitate

### 1. Authentication & Authorization

#### JWT Authentication
```python
# User authentication cu JWT tokens
{
  "sub": "user_id",
  "email": "doctor@hospital1.com",
  "role": "doctor",
  "node_id": "node1",
  "permissions": ["read:models", "write:inference", "read:datasets"],
  "exp": 1640995200,
  "iat": 1640908800
}
```

#### Role-Based Access Control (RBAC)
```yaml
Roles:
  admin:
    description: "Hospital Administrator"
    permissions:
      - "*"  # Full access
  
  doctor:
    description: "Medical Doctor"
    permissions:
      - "read:models"
      - "write:inference"
      - "read:datasets"
      - "read:jobs"
  
  researcher:
    description: "Medical Researcher"
    permissions:
      - "read:models"
      - "write:training"
      - "write:federated"
      - "read:datasets"
      - "write:datasets"
  
  viewer:
    description: "Read-only Access"
    permissions:
      - "read:*"

Node-specific permissions:
  - Users can only access their assigned node
  - Cross-node access requires special permissions
```

#### API Key Authentication (Inter-node)
```python
# Pentru comunicarea între noduri și central
{
  "api_key": "fed_med_fl_node1_abc123...",
  "node_id": "node1",
  "permissions": ["federated:participate", "central:register"],
  "expires": "2026-12-31T23:59:59Z"
}
```

### 2. Endpoint Security Matrix

| Endpoint | Admin | Doctor | Researcher | Viewer | API Key |
|----------|-------|--------|------------|--------|---------|
| `GET /api/health` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `GET /api/models` | ✅ | ✅ | ✅ | ✅ | ❌ |
| `POST /api/models/train` | ✅ | ❌ | ✅ | ❌ | ❌ |
| `POST /api/inference` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `POST /api/datasets/upload` | ✅ | ❌ | ✅ | ❌ | ❌ |
| `POST /api/federated/train` | ✅ | ❌ | ✅ | ❌ | ✅ |
| `GET /api/jobs` | ✅ | ✅ | ✅ | ✅ | ❌ |
| `DELETE /api/models/{id}` | ✅ | ❌ | ❌ | ❌ | ❌ |

### 3. Rate Limiting

```python
Rate Limits per Role:
  admin: 1000 req/min
  doctor: 100 req/min (inference heavy)
  researcher: 50 req/min (training heavy)
  viewer: 30 req/min
  api_key: 500 req/min (inter-node)

Endpoint-specific limits:
  POST /api/inference: 10 req/min per user
  POST /api/models/train: 2 req/hour per user
  POST /api/datasets/upload: 5 req/hour per user
  POST /api/federated/train: 1 req/10min per node
```

### 4. Audit Logging

```json
{
  "timestamp": "2026-04-26T14:30:00Z",
  "event_type": "api_request",
  "user_id": "doctor123",
  "node_id": "node1",
  "endpoint": "POST /api/inference",
  "ip_address": "192.168.1.100",
  "user_agent": "Fed-Med-FL-UI/1.0",
  "request_id": "req_abc123",
  "response_status": 200,
  "duration_ms": 1250,
  "data_accessed": {
    "model_id": "resnet18_v1",
    "dataset_samples": 1,
    "sensitive_data": true
  },
  "compliance": {
    "gdpr_consent": true,
    "hipaa_authorized": true,
    "purpose": "medical_diagnosis"
  }
}
```

---

## 🛡️ Implementare Securitate

### 1. Database Schema Extensions

```sql
-- Users table
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    node_id TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP NULL
);

-- API Keys table
CREATE TABLE api_keys (
    id TEXT PRIMARY KEY,
    key_hash TEXT UNIQUE NOT NULL,
    node_id TEXT NOT NULL,
    permissions TEXT NOT NULL, -- JSON array
    expires_at TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP
);

-- Audit logs table
CREATE TABLE audit_logs (
    id TEXT PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT NOT NULL,
    user_id TEXT,
    node_id TEXT NOT NULL,
    endpoint TEXT,
    ip_address TEXT,
    user_agent TEXT,
    request_id TEXT,
    response_status INTEGER,
    duration_ms INTEGER,
    details TEXT, -- JSON
    INDEX idx_timestamp (timestamp),
    INDEX idx_user_id (user_id),
    INDEX idx_event_type (event_type)
);

-- Sessions table (pentru JWT blacklist)
CREATE TABLE sessions (
    jti TEXT PRIMARY KEY, -- JWT ID
    user_id TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2. FastAPI Security Dependencies

```python
# services/node/api/app/security.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
import redis
from typing import Optional, List

# Security configuration
SECRET_KEY = "your-secret-key-here"  # From environment
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
redis_client = redis.Redis(host="redis", port=6379, db=1)

class SecurityManager:
    def __init__(self):
        self.rate_limits = {
            "admin": 1000,
            "doctor": 100,
            "researcher": 50,
            "viewer": 30,
            "api_key": 500
        }
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        return pwd_context.hash(password)
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        
        to_encode.update({"exp": expire, "iat": datetime.utcnow()})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    def verify_token(self, token: str) -> dict:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
    
    def check_rate_limit(self, user_id: str, role: str) -> bool:
        key = f"rate_limit:{user_id}"
        current = redis_client.get(key)
        limit = self.rate_limits.get(role, 30)
        
        if current is None:
            redis_client.setex(key, 60, 1)
            return True
        
        if int(current) >= limit:
            return False
        
        redis_client.incr(key)
        return True

security_manager = SecurityManager()

# Dependencies
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = security_manager.verify_token(token)
    
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Check if token is blacklisted
    jti = payload.get("jti")
    if jti and redis_client.get(f"blacklist:{jti}"):
        raise HTTPException(status_code=401, detail="Token revoked")
    
    return {
        "id": user_id,
        "email": payload.get("email"),
        "role": payload.get("role"),
        "node_id": payload.get("node_id"),
        "permissions": payload.get("permissions", [])
    }

def require_permission(permission: str):
    def permission_checker(current_user: dict = Depends(get_current_user)):
        if "*" in current_user["permissions"] or permission in current_user["permissions"]:
            return current_user
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return permission_checker

def require_role(role: str):
    def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] == role or current_user["role"] == "admin":
            return current_user
        raise HTTPException(status_code=403, detail="Insufficient role")
    return role_checker

async def rate_limit_check(current_user: dict = Depends(get_current_user)):
    if not security_manager.check_rate_limit(current_user["id"], current_user["role"]):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    return current_user
```

### 3. Protected Endpoints Example

```python
# services/node/api/app/main.py (updated)
from .security import get_current_user, require_permission, require_role, rate_limit_check

# Protected endpoint example
@app.post("/api/inference", response_model=InferResponse)
async def create_inference(
    request: InferRequest,
    current_user: dict = Depends(require_permission("write:inference")),
    rate_limited_user: dict = Depends(rate_limit_check),
    db: Session = Depends(get_db)
):
    # Log audit event
    audit_log = {
        "event_type": "inference_request",
        "user_id": current_user["id"],
        "model_id": request.model_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Existing inference logic...
    pass

# Admin-only endpoint
@app.delete("/api/models/{model_id}")
async def delete_model(
    model_id: str,
    current_user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    # Delete model logic...
    pass

# Public health endpoint (no auth required)
@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}
```

### 4. Authentication Endpoints

```python
# services/node/api/app/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from .database import get_db, User
from .security import security_manager
from .schemas import Token, UserCreate, UserResponse

router = APIRouter(prefix="/api/auth", tags=["authentication"])

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not security_manager.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    # Check account lockout
    if user.locked_until and user.locked_until > datetime.utcnow():
        raise HTTPException(status_code=423, detail="Account temporarily locked")
    
    # Reset failed attempts on successful login
    user.failed_login_attempts = 0
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Create JWT token
    access_token = security_manager.create_access_token(
        data={
            "sub": user.id,
            "email": user.email,
            "role": user.role,
            "node_id": user.node_id,
            "permissions": get_user_permissions(user.role)
        }
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    current_user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    # Check if user exists
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
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
    
    return user

@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    # Add token to blacklist
    # Implementation depends on JWT structure
    return {"message": "Successfully logged out"}

def get_user_permissions(role: str) -> List[str]:
    permissions_map = {
        "admin": ["*"],
        "doctor": ["read:models", "write:inference", "read:datasets", "read:jobs"],
        "researcher": ["read:models", "write:training", "write:federated", "read:datasets", "write:datasets"],
        "viewer": ["read:*"]
    }
    return permissions_map.get(role, [])
```

---

## 🔒 Frontend Security

### 1. Authentication Context

```typescript
// services/node/ui/src/contexts/AuthContext.tsx
import React, { createContext, useContext, useState, useEffect } from 'react';

interface User {
  id: string;
  email: string;
  role: string;
  nodeId: string;
  permissions: string[];
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  hasPermission: (permission: string) => boolean;
  hasRole: (role: string) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    // Load token from localStorage on app start
    const savedToken = localStorage.getItem('auth_token');
    if (savedToken) {
      // Verify token and load user info
      verifyToken(savedToken);
    }
  }, []);

  const login = async (email: string, password: string) => {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ username: email, password })
    });

    if (!response.ok) {
      throw new Error('Login failed');
    }

    const data = await response.json();
    const { access_token } = data;
    
    setToken(access_token);
    localStorage.setItem('auth_token', access_token);
    
    // Decode JWT to get user info (in production, get from API)
    const payload = JSON.parse(atob(access_token.split('.')[1]));
    setUser({
      id: payload.sub,
      email: payload.email,
      role: payload.role,
      nodeId: payload.node_id,
      permissions: payload.permissions
    });
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem('auth_token');
  };

  const hasPermission = (permission: string): boolean => {
    if (!user) return false;
    return user.permissions.includes('*') || user.permissions.includes(permission);
  };

  const hasRole = (role: string): boolean => {
    if (!user) return false;
    return user.role === role || user.role === 'admin';
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout, hasPermission, hasRole }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
```

### 2. Protected Routes

```typescript
// services/node/ui/src/components/ProtectedRoute.tsx
import { useAuth } from '../contexts/AuthContext';
import { Navigate } from 'react-router-dom';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredPermission?: string;
  requiredRole?: string;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  requiredPermission,
  requiredRole
}) => {
  const { user, hasPermission, hasRole } = useAuth();

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (requiredPermission && !hasPermission(requiredPermission)) {
    return <Navigate to="/unauthorized" replace />;
  }

  if (requiredRole && !hasRole(requiredRole)) {
    return <Navigate to="/unauthorized" replace />;
  }

  return <>{children}</>;
};
```

---

## 📊 Monitoring & Compliance

### 1. Security Metrics Dashboard

```typescript
// Security metrics to track
interface SecurityMetrics {
  authentication: {
    successful_logins: number;
    failed_logins: number;
    account_lockouts: number;
    active_sessions: number;
  };
  authorization: {
    permission_denials: number;
    role_violations: number;
    api_key_usage: number;
  };
  rate_limiting: {
    rate_limit_hits: number;
    blocked_requests: number;
  };
  audit: {
    total_events: number;
    sensitive_data_access: number;
    admin_actions: number;
  };
}
```

### 2. Compliance Reports

```python
# Generate GDPR/HIPAA compliance reports
class ComplianceReporter:
    def generate_data_access_report(self, user_id: str, date_range: tuple):
        """Generate report of all data accessed by user"""
        pass
    
    def generate_consent_report(self):
        """Report on user consents for data processing"""
        pass
    
    def generate_breach_report(self, incident_id: str):
        """Generate security incident report"""
        pass
```

---

## 🚀 Implementation Plan

### Phase 1: Core Authentication (Week 1)
- [ ] Database schema pentru users, api_keys, audit_logs
- [ ] JWT authentication cu FastAPI
- [ ] Basic RBAC implementation
- [ ] Login/logout endpoints

### Phase 2: Authorization & Rate Limiting (Week 2)
- [ ] Permission-based endpoint protection
- [ ] Rate limiting cu Redis
- [ ] API key authentication pentru inter-node
- [ ] Audit logging middleware

### Phase 3: Frontend Security (Week 3)
- [ ] React authentication context
- [ ] Protected routes
- [ ] Login/logout UI
- [ ] Permission-based UI components

### Phase 4: Advanced Security (Week 4)
- [ ] mTLS pentru Flower gRPC
- [ ] Security monitoring dashboard
- [ ] Compliance reporting
- [ ] Security testing

---

## 🔧 Configuration

### Environment Variables
```bash
# Security settings
JWT_SECRET_KEY=your-super-secret-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Rate limiting
REDIS_URL=redis://redis:6379/1
RATE_LIMIT_ENABLED=true

# API Keys
API_KEY_EXPIRE_DAYS=365
INTER_NODE_API_KEY=fed_med_fl_secure_key_2026

# Audit logging
AUDIT_LOG_LEVEL=INFO
AUDIT_LOG_RETENTION_DAYS=2555  # 7 years for medical compliance

# mTLS (optional)
TLS_CERT_PATH=/certs/node.crt
TLS_KEY_PATH=/certs/node.key
TLS_CA_PATH=/certs/ca.crt
```

---

## 📚 Security Best Practices

### 1. Password Policy
- Minimum 12 characters
- Must include uppercase, lowercase, numbers, symbols
- Cannot reuse last 5 passwords
- Must change every 90 days for admin accounts

### 2. Session Management
- JWT tokens expire after 30 minutes
- Refresh tokens valid for 7 days
- Automatic logout after 1 hour of inactivity
- Token blacklisting on logout

### 3. API Security
- All endpoints require authentication (except health)
- Rate limiting per user and endpoint
- Input validation and sanitization
- SQL injection prevention with ORM

### 4. Data Protection
- Encryption at rest for sensitive data
- TLS 1.3 for data in transit
- No sensitive data in logs
- Regular security audits

---

**Status**: 📋 Design Complete - Ready for Implementation  
**Next**: Phase 1 Implementation - Core Authentication
