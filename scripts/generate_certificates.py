#!/usr/bin/env python3
"""
Certificate Generation Script for Fed-Med-FL

Generates a complete PKI infrastructure:
- Root CA
- Server certificates for Central and Nodes
- Client certificates for mTLS authentication
- Signing certificates for payload verification

Usage:
    python scripts/generate_certificates.py
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend


class CertificateAuthority:
    """Certificate Authority for Fed-Med-FL"""
    
    def __init__(self, base_path: str = "./certificates"):
        self.base_path = Path(base_path)
        self.ca_path = self.base_path / "ca"
        self.central_path = self.base_path / "central"
        self.nodes_path = self.base_path / "nodes"
        
        # Create directory structure
        self.ca_path.mkdir(parents=True, exist_ok=True)
        self.central_path.mkdir(parents=True, exist_ok=True)
        self.nodes_path.mkdir(parents=True, exist_ok=True)
        
        self.ca_key = None
        self.ca_cert = None
    
    def generate_private_key(self, key_size: int = 4096) -> rsa.RSAPrivateKey:
        """Generate RSA private key"""
        return rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend()
        )
    
    def save_private_key(self, key: rsa.RSAPrivateKey, path: Path, password: bytes = None):
        """Save private key to file with proper permissions"""
        encryption = serialization.BestAvailableEncryption(password) if password else serialization.NoEncryption()
        
        pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=encryption
        )
        
        path.write_bytes(pem)
        # Set restrictive permissions (600)
        os.chmod(path, 0o600)
        print(f"✓ Private key saved: {path} (permissions: 600)")
    
    def save_certificate(self, cert: x509.Certificate, path: Path):
        """Save certificate to file"""
        pem = cert.public_bytes(serialization.Encoding.PEM)
        path.write_bytes(pem)
        os.chmod(path, 0o644)
        print(f"✓ Certificate saved: {path} (permissions: 644)")
    
    def create_root_ca(self, validity_days: int = 3650):
        """Create Root CA certificate"""
        print("\n" + "="*70)
        print("Creating Root Certificate Authority")
        print("="*70)
        
        # Generate CA private key
        self.ca_key = self.generate_private_key()
        
        # Create CA certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "RO"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Bucharest"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Bucharest"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Fed-Med-FL"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Security"),
            x509.NameAttribute(NameOID.COMMON_NAME, "Fed-Med-FL Root CA"),
        ])
        
        self.ca_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(self.ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=validity_days))
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=0),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_cert_sign=True,
                    crl_sign=True,
                    key_encipherment=False,
                    content_commitment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(self.ca_key.public_key()),
                critical=False,
            )
            .sign(self.ca_key, hashes.SHA256(), default_backend())
        )
        
        # Save CA key and certificate
        self.save_private_key(self.ca_key, self.ca_path / "ca-key.pem")
        self.save_certificate(self.ca_cert, self.ca_path / "ca-cert.pem")
        
        print(f"\n✅ Root CA created successfully")
        print(f"   Valid until: {self.ca_cert.not_valid_after}")
        print(f"   Serial: {self.ca_cert.serial_number}")
    
    def create_server_certificate(
        self,
        common_name: str,
        dns_names: list,
        output_path: Path,
        validity_days: int = 365
    ):
        """Create server certificate for TLS"""
        print(f"\n📜 Creating server certificate: {common_name}")
        
        # Generate private key
        private_key = self.generate_private_key()
        
        # Create certificate
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "RO"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Fed-Med-FL"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])
        
        # Subject Alternative Names
        san_list = [x509.DNSName(name) for name in dns_names]
        
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(self.ca_cert.subject)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=validity_days))
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_encipherment=True,
                    key_cert_sign=False,
                    crl_sign=False,
                    content_commitment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([
                    ExtendedKeyUsageOID.SERVER_AUTH,
                    ExtendedKeyUsageOID.CLIENT_AUTH,
                ]),
                critical=True,
            )
            .add_extension(
                x509.SubjectAlternativeName(san_list),
                critical=False,
            )
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
                critical=False,
            )
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(self.ca_key.public_key()),
                critical=False,
            )
            .sign(self.ca_key, hashes.SHA256(), default_backend())
        )
        
        # Save certificate and key
        output_path.mkdir(parents=True, exist_ok=True)
        self.save_private_key(private_key, output_path / "server-key.pem")
        self.save_certificate(cert, output_path / "server-cert.pem")
        
        print(f"   ✓ Server certificate created for: {', '.join(dns_names)}")
    
    def create_client_certificate(
        self,
        common_name: str,
        output_path: Path,
        validity_days: int = 365
    ):
        """Create client certificate for mTLS authentication"""
        print(f"\n📜 Creating client certificate: {common_name}")
        
        # Generate private key
        private_key = self.generate_private_key()
        
        # Create certificate
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "RO"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Fed-Med-FL"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])
        
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(self.ca_cert.subject)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=validity_days))
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_encipherment=True,
                    key_cert_sign=False,
                    crl_sign=False,
                    content_commitment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([
                    ExtendedKeyUsageOID.CLIENT_AUTH,
                ]),
                critical=True,
            )
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
                critical=False,
            )
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(self.ca_key.public_key()),
                critical=False,
            )
            .sign(self.ca_key, hashes.SHA256(), default_backend())
        )
        
        # Save certificate and key
        output_path.mkdir(parents=True, exist_ok=True)
        self.save_private_key(private_key, output_path / "client-key.pem")
        self.save_certificate(cert, output_path / "client-cert.pem")
        
        print(f"   ✓ Client certificate created")
    
    def create_signing_certificate(
        self,
        common_name: str,
        output_path: Path,
        validity_days: int = 365
    ):
        """Create certificate for payload signing"""
        print(f"\n📜 Creating signing certificate: {common_name}")
        
        # Generate private key
        private_key = self.generate_private_key()
        
        # Create certificate
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "RO"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Fed-Med-FL"),
            x509.NameAttribute(NameOID.COMMON_NAME, f"{common_name} Signing"),
        ])
        
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(self.ca_cert.subject)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=validity_days))
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_encipherment=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    content_commitment=True,
                    data_encipherment=False,
                    key_agreement=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
                critical=False,
            )
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(self.ca_key.public_key()),
                critical=False,
            )
            .sign(self.ca_key, hashes.SHA256(), default_backend())
        )
        
        # Save certificate and key
        output_path.mkdir(parents=True, exist_ok=True)
        self.save_private_key(private_key, output_path / "signing-key.pem")
        self.save_certificate(cert, output_path / "signing-cert.pem")
        
        print(f"   ✓ Signing certificate created")
    
    def generate_all_certificates(self):
        """Generate complete PKI infrastructure"""
        print("\n" + "="*70)
        print("FED-MED-FL CERTIFICATE GENERATION")
        print("="*70)
        
        # Create Root CA
        self.create_root_ca(validity_days=3650)  # 10 years
        
        # Central Server
        print("\n" + "-"*70)
        print("CENTRAL SERVER CERTIFICATES")
        print("-"*70)
        self.create_server_certificate(
            common_name="central.fed-med-fl.local",
            dns_names=["central", "central.fed-med-fl.local", "localhost"],
            output_path=self.central_path,
            validity_days=365
        )
        self.create_client_certificate(
            common_name="central-client",
            output_path=self.central_path,
            validity_days=365
        )
        self.create_signing_certificate(
            common_name="central",
            output_path=self.central_path,
            validity_days=365
        )
        
        # Node Certificates
        for node_id in ["node1", "node2", "node3", "node4", "node5"]:
            print("\n" + "-"*70)
            print(f"{node_id.upper()} CERTIFICATES")
            print("-"*70)
            
            node_path = self.nodes_path / node_id
            
            # Server certificate (for API)
            self.create_server_certificate(
                common_name=f"{node_id}.fed-med-fl.local",
                dns_names=[
                    node_id,
                    f"{node_id}.fed-med-fl.local",
                    f"{node_id}-api",
                    f"{node_id}-worker",
                    "localhost"
                ],
                output_path=node_path,
                validity_days=365
            )
            
            # Client certificate (for Flower)
            self.create_client_certificate(
                common_name=f"{node_id}-client",
                output_path=node_path,
                validity_days=365
            )
            
            # Signing certificate (for payload)
            self.create_signing_certificate(
                common_name=node_id,
                output_path=node_path,
                validity_days=365
            )
        
        # Copy CA certificate to all locations for easy access
        print("\n" + "-"*70)
        print("DISTRIBUTING CA CERTIFICATE")
        print("-"*70)
        
        ca_cert_content = (self.ca_path / "ca-cert.pem").read_bytes()

        (self.central_path / "ca-cert.pem").write_bytes(ca_cert_content)
        print(f"✓ CA cert copied to: {self.central_path}")

        for node_id in ["node1", "node2", "node3", "node4", "node5"]:
            node_path = self.nodes_path / node_id
            (node_path / "ca-cert.pem").write_bytes(ca_cert_content)
            print(f"✓ CA cert copied to: {node_path}")
        
        # Summary
        print("\n" + "="*70)
        print("✅ CERTIFICATE GENERATION COMPLETE")
        print("="*70)
        print(f"\nCertificate structure created in: {self.base_path}")
        print("\nDirectory structure:")
        print(f"  {self.base_path}/")
        print(f"  ├── ca/")
        print(f"  │   ├── ca-cert.pem (Root CA)")
        print(f"  │   └── ca-key.pem (Root CA private key)")
        print(f"  ├── central/")
        print(f"  │   ├── server-cert.pem, server-key.pem")
        print(f"  │   ├── client-cert.pem, client-key.pem")
        print(f"  │   ├── signing-cert.pem, signing-key.pem")
        print(f"  │   └── ca-cert.pem")
        print(f"  └── nodes/")
        print(f"      ├── node1/ (same structure)")
        print(f"      ├── node2/ (same structure)")
        print(f"      ├── node3/ (same structure)")
        print(f"      ├── node4/ (same structure)")
        print(f"      └── node5/ (same structure)")
        
        print("\n⚠️  SECURITY NOTES:")
        print("  • Private keys have 600 permissions (owner read/write only)")
        print("  • Certificates have 644 permissions (world readable)")
        print("  • Keep ca-key.pem secure - it can sign new certificates")
        print("  • Certificates valid for 1 year (365 days)")
        print("  • Root CA valid for 10 years")
        
        print("\n📋 NEXT STEPS:")
        print("  1. Review generated certificates")
        print("  2. Update docker-compose.yml with certificate volumes")
        print("  3. Configure Flower server/client with SSL")
        print("  4. Configure FastAPI with HTTPS")
        print("  5. Test mTLS connections")
        print("\n" + "="*70 + "\n")


def main():
    """Main entry point"""
    try:
        ca = CertificateAuthority(base_path="./certificates")
        ca.generate_all_certificates()
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
