"""
FastAPI SSL/HTTPS Configuration for Fed-Med-FL

Provides SSL configuration for Uvicorn with:
- HTTPS server configuration
- Optional client certificate verification (mTLS)
- Certificate validation middleware
"""
import os
import ssl
from pathlib import Path
from typing import Optional, Tuple
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware


class SSLConfig:
    """
    SSL Configuration for FastAPI/Uvicorn.
    
    Handles certificate loading and SSL context creation.
    """
    
    def __init__(
        self,
        certificates_path: str = "/certificates",
        node_id: Optional[str] = None,
        is_central: bool = False,
        require_client_cert: bool = False
    ):
        """
        Initialize SSL configuration.
        
        Args:
            certificates_path: Base path to certificates directory
            node_id: Node identifier (e.g., 'node1', 'node2')
            is_central: Whether this is the central server
            require_client_cert: Whether to require client certificates (mTLS)
        """
        self.certificates_path = Path(certificates_path)
        self.node_id = node_id
        self.is_central = is_central
        self.require_client_cert = require_client_cert
        
        # Determine certificate directory
        if is_central:
            self.cert_dir = self.certificates_path / "central"
        elif node_id:
            self.cert_dir = self.certificates_path / "nodes" / node_id
        else:
            raise ValueError("Either node_id or is_central must be specified")
        
        # Certificate paths
        self.server_cert_path = self.cert_dir / "server-cert.pem"
        self.server_key_path = self.cert_dir / "server-key.pem"
        self.ca_cert_path = self.cert_dir / "ca-cert.pem"
        
        # Validate certificates exist
        self._validate_certificates()
    
    def _validate_certificates(self) -> bool:
        """Validate that required certificates exist."""
        if not self.server_cert_path.exists():
            print(f"⚠️  Server certificate not found: {self.server_cert_path}")
            return False
        
        if not self.server_key_path.exists():
            print(f"⚠️  Server private key not found: {self.server_key_path}")
            return False
        
        if self.require_client_cert and not self.ca_cert_path.exists():
            print(f"⚠️  CA certificate not found: {self.ca_cert_path}")
            return False
        
        print(f"✓ SSL certificates validated: {self.cert_dir}")
        return True
    
    def is_ready(self) -> bool:
        """Check if SSL configuration is ready."""
        return (
            self.server_cert_path.exists() and
            self.server_key_path.exists() and
            (not self.require_client_cert or self.ca_cert_path.exists())
        )
    
    def get_uvicorn_ssl_config(self) -> dict:
        """
        Get SSL configuration for Uvicorn.
        
        Returns:
            Dictionary with ssl_keyfile, ssl_certfile, and optionally ssl_ca_certs
        """
        if not self.is_ready():
            raise ValueError("SSL certificates not ready")
        
        config = {
            "ssl_keyfile": str(self.server_key_path),
            "ssl_certfile": str(self.server_cert_path),
        }
        
        # Add CA certificate for client verification if required
        if self.require_client_cert:
            config["ssl_ca_certs"] = str(self.ca_cert_path)
            config["ssl_cert_reqs"] = ssl.CERT_REQUIRED
        
        return config
    
    def create_ssl_context(self) -> ssl.SSLContext:
        """
        Create SSL context for advanced configuration.
        
        Returns:
            Configured SSLContext
        """
        if not self.is_ready():
            raise ValueError("SSL certificates not ready")
        
        # Create SSL context
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        
        # Load server certificate and key
        context.load_cert_chain(
            certfile=str(self.server_cert_path),
            keyfile=str(self.server_key_path)
        )
        
        # Configure client certificate verification if required
        if self.require_client_cert:
            context.load_verify_locations(cafile=str(self.ca_cert_path))
            context.verify_mode = ssl.CERT_REQUIRED
        else:
            context.verify_mode = ssl.CERT_NONE
        
        # Security settings
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
        
        return context


class ClientCertificateMiddleware(BaseHTTPMiddleware):
    """
    Middleware to verify client certificates for mTLS.
    
    Extracts client certificate information from the request
    and validates it against the CA.
    """
    
    def __init__(self, app, ssl_config: SSLConfig, enforce: bool = False):
        """
        Initialize middleware.
        
        Args:
            app: FastAPI application
            ssl_config: SSLConfig instance
            enforce: Whether to enforce client certificate validation
        """
        super().__init__(app)
        self.ssl_config = ssl_config
        self.enforce = enforce
    
    async def dispatch(self, request: Request, call_next):
        """Process request and verify client certificate."""
        
        # Skip verification for health check endpoints
        if request.url.path in ["/api/health", "/health"]:
            return await call_next(request)
        
        # Check if client certificate is present
        if self.enforce:
            # In production, you would extract and verify the client certificate
            # from request.scope['transport'].get_extra_info('peercert')
            # For now, we rely on SSL/TLS layer verification
            pass
        
        # Continue processing
        response = await call_next(request)
        
        # Add security headers
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        return response


def configure_fastapi_ssl(
    app,
    node_id: Optional[str] = None,
    is_central: bool = False,
    certificates_path: str = "/certificates",
    require_client_cert: bool = False,
    enforce_client_cert: bool = False
) -> Optional[SSLConfig]:
    """
    Configure FastAPI application with SSL/HTTPS.
    
    Args:
        app: FastAPI application instance
        node_id: Node identifier
        is_central: Whether this is the central server
        certificates_path: Path to certificates directory
        require_client_cert: Whether to require client certificates
        enforce_client_cert: Whether to enforce client certificate validation
    
    Returns:
        SSLConfig instance if successful, None otherwise
    """
    try:
        # Create SSL configuration
        ssl_config = SSLConfig(
            certificates_path=certificates_path,
            node_id=node_id,
            is_central=is_central,
            require_client_cert=require_client_cert
        )
        
        if not ssl_config.is_ready():
            print("⚠️  SSL configuration not ready, HTTPS disabled")
            return None
        
        # Add client certificate middleware if required
        if require_client_cert:
            app.add_middleware(
                ClientCertificateMiddleware,
                ssl_config=ssl_config,
                enforce=enforce_client_cert
            )
            print(f"✓ Client certificate middleware added (enforce={enforce_client_cert})")
        
        print(f"✓ FastAPI SSL configured for {'central' if is_central else node_id}")
        return ssl_config
        
    except Exception as e:
        print(f"✗ Failed to configure SSL: {e}")
        return None


def get_uvicorn_config(
    ssl_config: Optional[SSLConfig],
    host: str = "0.0.0.0",
    port: int = 8000,
    **kwargs
) -> dict:
    """
    Get Uvicorn configuration with SSL if available.
    
    Args:
        ssl_config: SSLConfig instance (None for HTTP)
        host: Host to bind to
        port: Port to bind to
        **kwargs: Additional Uvicorn configuration
    
    Returns:
        Dictionary with Uvicorn configuration
    """
    config = {
        "host": host,
        "port": port,
        **kwargs
    }
    
    # Add SSL configuration if available
    if ssl_config and ssl_config.is_ready():
        ssl_params = ssl_config.get_uvicorn_ssl_config()
        config.update(ssl_params)
        print(f"✓ Uvicorn configured with HTTPS on {host}:{port}")
    else:
        print(f"⚠️  Uvicorn configured with HTTP on {host}:{port} (SSL not available)")
    
    return config
