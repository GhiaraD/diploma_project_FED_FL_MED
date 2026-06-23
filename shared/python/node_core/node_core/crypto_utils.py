"""
Cryptographic utilities for Fed-Med-FL

Provides payload signing and verification for model parameters
to ensure integrity and authenticity during federated learning.
"""
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature


class PayloadSigner:
    """
    Handles signing and verification of model parameters.
    
    Uses RSA-PSS with SHA-256 for digital signatures.
    """
    
    def __init__(self, private_key_path: Optional[str] = None, 
                 certificate_path: Optional[str] = None,
                 ca_cert_path: Optional[str] = None):
        """
        Initialize payload signer.
        
        Args:
            private_key_path: Path to signing private key
            certificate_path: Path to signing certificate
            ca_cert_path: Path to CA certificate for verification
        """
        self.private_key = None
        self.certificate = None
        self.ca_cert = None
        
        if private_key_path:
            self.load_private_key(private_key_path)
        
        if certificate_path:
            self.load_certificate(certificate_path)
        
        if ca_cert_path:
            self.load_ca_certificate(ca_cert_path)
    
    def load_private_key(self, key_path: str):
        """Load private key from PEM file"""
        try:
            key_path = Path(key_path)
            if not key_path.exists():
                print(f"⚠️  Private key not found: {key_path}")
                return
            
            with open(key_path, 'rb') as f:
                self.private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,
                    backend=default_backend()
                )
            print(f"✓ Private key loaded: {key_path}")
        except Exception as e:
            print(f"✗ Failed to load private key: {e}")
            self.private_key = None
    
    def load_certificate(self, cert_path: str):
        """Load certificate from PEM file"""
        try:
            from cryptography import x509
            cert_path = Path(cert_path)
            if not cert_path.exists():
                print(f"⚠️  Certificate not found: {cert_path}")
                return
            
            with open(cert_path, 'rb') as f:
                self.certificate = x509.load_pem_x509_certificate(
                    f.read(),
                    backend=default_backend()
                )
            print(f"✓ Certificate loaded: {cert_path}")
        except Exception as e:
            print(f"✗ Failed to load certificate: {e}")
            self.certificate = None
    
    def load_ca_certificate(self, ca_cert_path: str):
        """Load CA certificate for verification"""
        try:
            from cryptography import x509
            ca_cert_path = Path(ca_cert_path)
            if not ca_cert_path.exists():
                print(f"⚠️  CA certificate not found: {ca_cert_path}")
                return
            
            with open(ca_cert_path, 'rb') as f:
                self.ca_cert = x509.load_pem_x509_certificate(
                    f.read(),
                    backend=default_backend()
                )
            print(f"✓ CA certificate loaded: {ca_cert_path}")
        except Exception as e:
            print(f"✗ Failed to load CA certificate: {e}")
            self.ca_cert = None
    
    def compute_parameters_hash(self, parameters: List[np.ndarray]) -> str:
        """
        Compute SHA-256 hash of model parameters.
        
        Args:
            parameters: List of numpy arrays (model parameters)
        
        Returns:
            Hex string of SHA-256 hash
        """
        hasher = hashlib.sha256()
        
        for param in parameters:
            # Convert to bytes and update hash
            param_bytes = param.tobytes()
            hasher.update(param_bytes)
        
        return hasher.hexdigest()
    
    def sign_parameters(self, parameters: List[np.ndarray], 
                       metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Sign model parameters with RSA-PSS.
        
        Args:
            parameters: List of numpy arrays (model parameters)
            metadata: Optional metadata to include in signature
        
        Returns:
            Dictionary with signature and metadata
        """
        if not self.private_key:
            raise ValueError("Private key not loaded. Cannot sign parameters.")
        
        # Compute hash of parameters
        params_hash = self.compute_parameters_hash(parameters)
        
        # Create signature payload
        signature_payload = {
            'parameters_hash': params_hash,
            'num_parameters': len(parameters),
            'parameter_shapes': [list(p.shape) for p in parameters],
            'metadata': metadata or {}
        }
        
        # Convert to canonical JSON for signing
        payload_bytes = json.dumps(signature_payload, sort_keys=True).encode('utf-8')
        
        # Sign with RSA-PSS
        signature = self.private_key.sign(
            payload_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        # Get certificate in PEM format for verification
        certificate_pem = None
        if self.certificate:
            certificate_pem = self.certificate.public_bytes(
                encoding=serialization.Encoding.PEM
            ).decode('utf-8')
        
        # Return signature package
        return {
            'signature': signature.hex(),
            'payload': signature_payload,
            'algorithm': 'RSA-PSS-SHA256',
            'signer': self._get_signer_info(),
            'certificate': certificate_pem  # Include certificate for verification
        }
    
    def verify_parameters(self, parameters: List[np.ndarray], 
                         signature_package: Dict[str, Any],
                         public_key=None) -> Tuple[bool, str]:
        """
        Verify signed model parameters.
        
        Args:
            parameters: List of numpy arrays (model parameters)
            signature_package: Signature package from sign_parameters()
            public_key: Optional public key (uses certificate from package if not provided)
        
        Returns:
            (is_valid, message) tuple
        """
        try:
            # Get public key
            if public_key is None:
                # Try to get certificate from signature package
                if 'certificate' in signature_package and signature_package['certificate']:
                    from cryptography import x509
                    cert_pem = signature_package['certificate']
                    if isinstance(cert_pem, str):
                        cert_pem = cert_pem.encode('utf-8')
                    cert = x509.load_pem_x509_certificate(cert_pem, backend=default_backend())
                    public_key = cert.public_key()
                elif self.certificate:
                    public_key = self.certificate.public_key()
                else:
                    return False, "No public key or certificate available for verification"
            
            # Verify parameter count and shapes
            payload = signature_package['payload']
            if len(parameters) != payload['num_parameters']:
                return False, f"Parameter count mismatch: expected {payload['num_parameters']}, got {len(parameters)}"
            
            for i, (param, expected_shape) in enumerate(zip(parameters, payload['parameter_shapes'])):
                if list(param.shape) != expected_shape:
                    return False, f"Parameter {i} shape mismatch: expected {expected_shape}, got {list(param.shape)}"
            
            # Compute hash of received parameters
            params_hash = self.compute_parameters_hash(parameters)
            
            # Verify hash matches
            if params_hash != payload['parameters_hash']:
                return False, f"Parameter hash mismatch: expected {payload['parameters_hash'][:16]}..., got {params_hash[:16]}..."
            
            # Reconstruct payload for signature verification
            payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
            
            # Verify signature
            signature_bytes = bytes.fromhex(signature_package['signature'])
            
            public_key.verify(
                signature_bytes,
                payload_bytes,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            return True, "Signature verified successfully"
            
        except InvalidSignature:
            return False, "Invalid signature: cryptographic verification failed"
        except Exception as e:
            return False, f"Verification error: {str(e)}"
    
    def _get_signer_info(self) -> Dict[str, str]:
        """Get information about the signer from certificate"""
        if not self.certificate:
            return {'identity': 'unknown'}
        
        try:
            subject = self.certificate.subject
            return {
                'common_name': subject.get_attributes_for_oid(
                    x509.oid.NameOID.COMMON_NAME
                )[0].value if subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME) else 'unknown',
                'organization': subject.get_attributes_for_oid(
                    x509.oid.NameOID.ORGANIZATION_NAME
                )[0].value if subject.get_attributes_for_oid(x509.oid.NameOID.ORGANIZATION_NAME) else 'unknown',
                'serial_number': str(self.certificate.serial_number),
                'not_valid_after': self.certificate.not_valid_after.isoformat()
            }
        except Exception as e:
            return {'identity': 'unknown', 'error': str(e)}
    
    def is_ready(self) -> bool:
        """Check if signer is ready for signing operations"""
        return self.private_key is not None and self.certificate is not None
    
    def is_verifier_ready(self) -> bool:
        """Check if signer is ready for verification operations"""
        return self.certificate is not None or self.ca_cert is not None


class SignatureCache:
    """
    Cache for signature verification results to improve performance.
    """
    
    def __init__(self, max_size: int = 100):
        self.cache: Dict[str, Tuple[bool, str]] = {}
        self.max_size = max_size
    
    def get(self, signature_hash: str) -> Optional[Tuple[bool, str]]:
        """Get cached verification result"""
        return self.cache.get(signature_hash)
    
    def put(self, signature_hash: str, result: Tuple[bool, str]):
        """Cache verification result"""
        if len(self.cache) >= self.max_size:
            # Remove oldest entry (simple FIFO)
            self.cache.pop(next(iter(self.cache)))
        
        self.cache[signature_hash] = result
    
    def clear(self):
        """Clear cache"""
        self.cache.clear()


# Global signature cache
_signature_cache = SignatureCache()


def create_payload_signer(
    node_id: str,
    certificates_path: str = "/certificates",
    is_central: bool = False
) -> PayloadSigner:
    """
    Factory function to create PayloadSigner with correct paths.
    
    Args:
        node_id: Node identifier (e.g., 'node1', 'central')
        certificates_path: Base path to certificates directory
        is_central: Whether this is the central server
    
    Returns:
        Configured PayloadSigner instance
    """
    cert_base = Path(certificates_path)
    
    if is_central:
        cert_dir = cert_base / "central"
    else:
        cert_dir = cert_base / "nodes" / node_id
    
    private_key_path = cert_dir / "signing-key.pem"
    certificate_path = cert_dir / "signing-cert.pem"
    ca_cert_path = cert_dir / "ca-cert.pem"
    
    return PayloadSigner(
        private_key_path=str(private_key_path) if private_key_path.exists() else None,
        certificate_path=str(certificate_path) if certificate_path.exists() else None,
        ca_cert_path=str(ca_cert_path) if ca_cert_path.exists() else None,
    )


def sign_model_parameters(
    parameters: List[np.ndarray],
    signer: PayloadSigner,
    metadata: Optional[Dict[str, Any]] = None
) -> Tuple[List[np.ndarray], Dict[str, Any]]:
    """
    Sign model parameters and return parameters with signature.
    
    Args:
        parameters: Model parameters to sign
        signer: PayloadSigner instance
        metadata: Optional metadata
    
    Returns:
        (parameters, signature_package) tuple
    """
    if not signer.is_ready():
        print("⚠️  Signer not ready, returning unsigned parameters")
        return parameters, {'signed': False, 'reason': 'signer_not_ready'}
    
    try:
        signature_package = signer.sign_parameters(parameters, metadata)
        signature_package['signed'] = True
        return parameters, signature_package
    except Exception as e:
        print(f"✗ Failed to sign parameters: {e}")
        return parameters, {'signed': False, 'reason': str(e)}


def verify_model_parameters(
    parameters: List[np.ndarray],
    signature_package: Dict[str, Any],
    verifier: PayloadSigner,
    use_cache: bool = True
) -> Tuple[bool, str]:
    """
    Verify signed model parameters.
    
    Args:
        parameters: Model parameters to verify
        signature_package: Signature package
        verifier: PayloadSigner instance for verification
        use_cache: Whether to use signature cache
    
    Returns:
        (is_valid, message) tuple
    """
    # Check if signing was disabled
    if not signature_package.get('signed', False):
        return True, "Signature verification skipped (unsigned parameters)"
    
    # Check cache
    if use_cache:
        signature_hash = signature_package.get('signature', '')[:32]
        cached_result = _signature_cache.get(signature_hash)
        if cached_result:
            return cached_result
    
    # Verify
    if not verifier.is_verifier_ready():
        return False, "Verifier not ready (no certificate loaded)"
    
    try:
        is_valid, message = verifier.verify_parameters(parameters, signature_package)
        
        # Cache result
        if use_cache:
            signature_hash = signature_package.get('signature', '')[:32]
            _signature_cache.put(signature_hash, (is_valid, message))
        
        return is_valid, message
    except Exception as e:
        return False, f"Verification exception: {str(e)}"
