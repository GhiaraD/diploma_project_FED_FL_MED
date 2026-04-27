#!/usr/bin/env python3
"""
Certificate Monitoring Script for Fed-Med-FL

Monitors certificate expiry dates, validates certificate chains,
and provides alerts for certificates that are about to expire.

Usage:
    python3 scripts/monitor_certificates.py
    python3 scripts/monitor_certificates.py --alert-days 30
    python3 scripts/monitor_certificates.py --json
"""

import os
import sys
import argparse
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes


class CertificateMonitor:
    """Monitor SSL/TLS certificates for expiry and validity"""
    
    def __init__(self, certificates_path: str = "./certificates", alert_days: int = 30):
        """
        Initialize certificate monitor.
        
        Args:
            certificates_path: Path to certificates directory
            alert_days: Alert when certificates expire in less than this many days
        """
        self.certificates_path = Path(certificates_path)
        self.alert_days = alert_days
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'certificates': [],
            'alerts': [],
            'errors': [],
            'summary': {
                'total': 0,
                'valid': 0,
                'expiring_soon': 0,
                'expired': 0,
                'invalid': 0
            }
        }
    
    def load_certificate(self, cert_path: Path) -> Optional[x509.Certificate]:
        """Load certificate from PEM file"""
        try:
            with open(cert_path, 'rb') as f:
                cert_data = f.read()
                return x509.load_pem_x509_certificate(cert_data, default_backend())
        except Exception as e:
            self.results['errors'].append({
                'file': str(cert_path),
                'error': str(e)
            })
            return None
    
    def check_certificate(self, cert_path: Path, cert_type: str, node: str) -> Dict:
        """
        Check a single certificate.
        
        Returns:
            Dictionary with certificate information and status
        """
        cert = self.load_certificate(cert_path)
        if not cert:
            return {
                'path': str(cert_path),
                'type': cert_type,
                'node': node,
                'status': 'error',
                'error': 'Failed to load certificate'
            }
        
        # Get certificate details
        subject = cert.subject.rfc4514_string()
        issuer = cert.issuer.rfc4514_string()
        not_before = cert.not_valid_before
        not_after = cert.not_valid_after
        serial_number = cert.serial_number
        
        # Calculate days until expiry
        now = datetime.now()
        days_until_expiry = (not_after - now).days
        
        # Determine status
        if now < not_before:
            status = 'not_yet_valid'
        elif now > not_after:
            status = 'expired'
            self.results['summary']['expired'] += 1
        elif days_until_expiry <= self.alert_days:
            status = 'expiring_soon'
            self.results['summary']['expiring_soon'] += 1
        else:
            status = 'valid'
            self.results['summary']['valid'] += 1
        
        # Check file permissions
        permissions = oct(cert_path.stat().st_mode)[-3:]
        
        cert_info = {
            'path': str(cert_path),
            'type': cert_type,
            'node': node,
            'status': status,
            'subject': subject,
            'issuer': issuer,
            'serial_number': str(serial_number),
            'not_before': not_before.isoformat(),
            'not_after': not_after.isoformat(),
            'days_until_expiry': days_until_expiry,
            'permissions': permissions
        }
        
        # Add alert if needed
        if status in ['expired', 'expiring_soon', 'not_yet_valid']:
            self.results['alerts'].append({
                'severity': 'critical' if status == 'expired' else 'warning',
                'message': self._get_alert_message(cert_info),
                'certificate': cert_info
            })
        
        return cert_info
    
    def _get_alert_message(self, cert_info: Dict) -> str:
        """Generate alert message for certificate"""
        status = cert_info['status']
        node = cert_info['node']
        cert_type = cert_info['type']
        days = cert_info['days_until_expiry']
        
        if status == 'expired':
            return f"🔴 CRITICAL: {node} {cert_type} certificate has EXPIRED!"
        elif status == 'expiring_soon':
            return f"⚠️  WARNING: {node} {cert_type} certificate expires in {days} days"
        elif status == 'not_yet_valid':
            return f"⚠️  WARNING: {node} {cert_type} certificate is not yet valid"
        return ""
    
    def check_key_permissions(self, key_path: Path) -> Tuple[bool, str]:
        """
        Check if private key has correct permissions (600).
        
        Returns:
            (is_correct, message) tuple
        """
        if not key_path.exists():
            return False, f"Key file not found: {key_path}"
        
        permissions = oct(key_path.stat().st_mode)[-3:]
        
        if permissions != '600':
            return False, f"Insecure permissions {permissions} (should be 600)"
        
        return True, "OK"
    
    def validate_certificate_chain(self, cert_path: Path, ca_cert_path: Path) -> Tuple[bool, str]:
        """
        Validate that certificate is signed by CA.
        
        Returns:
            (is_valid, message) tuple
        """
        cert = self.load_certificate(cert_path)
        ca_cert = self.load_certificate(ca_cert_path)
        
        if not cert or not ca_cert:
            return False, "Failed to load certificates"
        
        try:
            # Verify certificate signature
            ca_public_key = ca_cert.public_key()
            ca_public_key.verify(
                cert.signature,
                cert.tbs_certificate_bytes,
                padding=None,  # RSA signature doesn't use padding for verification
                algorithm=cert.signature_hash_algorithm
            )
            return True, "Certificate chain valid"
        except Exception as e:
            return False, f"Certificate chain validation failed: {str(e)}"
    
    def scan_certificates(self):
        """Scan all certificates in the certificates directory"""
        print(f"🔍 Scanning certificates in: {self.certificates_path}")
        print(f"📅 Alert threshold: {self.alert_days} days")
        print()
        
        # Check CA certificate
        ca_cert_path = self.certificates_path / "ca" / "ca-cert.pem"
        if ca_cert_path.exists():
            cert_info = self.check_certificate(ca_cert_path, "Root CA", "CA")
            self.results['certificates'].append(cert_info)
            self.results['summary']['total'] += 1
            
            # Check CA key permissions
            ca_key_path = self.certificates_path / "ca" / "ca-key.pem"
            is_secure, msg = self.check_key_permissions(ca_key_path)
            if not is_secure:
                self.results['alerts'].append({
                    'severity': 'warning',
                    'message': f"⚠️  CA private key: {msg}",
                    'file': str(ca_key_path)
                })
        
        # Check central server certificates
        central_dir = self.certificates_path / "central"
        if central_dir.exists():
            for cert_file in ['server-cert.pem', 'client-cert.pem', 'signing-cert.pem']:
                cert_path = central_dir / cert_file
                if cert_path.exists():
                    cert_type = cert_file.replace('-cert.pem', '').replace('-', ' ').title()
                    cert_info = self.check_certificate(cert_path, cert_type, "Central")
                    self.results['certificates'].append(cert_info)
                    self.results['summary']['total'] += 1
                    
                    # Validate chain
                    if ca_cert_path.exists():
                        is_valid, msg = self.validate_certificate_chain(cert_path, ca_cert_path)
                        cert_info['chain_valid'] = is_valid
                        if not is_valid:
                            self.results['alerts'].append({
                                'severity': 'error',
                                'message': f"❌ Central {cert_type}: {msg}",
                                'certificate': cert_info
                            })
                    
                    # Check key permissions
                    key_file = cert_file.replace('-cert.pem', '-key.pem')
                    key_path = central_dir / key_file
                    is_secure, msg = self.check_key_permissions(key_path)
                    if not is_secure:
                        self.results['alerts'].append({
                            'severity': 'warning',
                            'message': f"⚠️  Central {cert_type} key: {msg}",
                            'file': str(key_path)
                        })
        
        # Check node certificates
        nodes_dir = self.certificates_path / "nodes"
        if nodes_dir.exists():
            for node_dir in nodes_dir.iterdir():
                if node_dir.is_dir():
                    node_name = node_dir.name
                    for cert_file in ['server-cert.pem', 'client-cert.pem', 'signing-cert.pem']:
                        cert_path = node_dir / cert_file
                        if cert_path.exists():
                            cert_type = cert_file.replace('-cert.pem', '').replace('-', ' ').title()
                            cert_info = self.check_certificate(cert_path, cert_type, node_name)
                            self.results['certificates'].append(cert_info)
                            self.results['summary']['total'] += 1
                            
                            # Validate chain
                            if ca_cert_path.exists():
                                is_valid, msg = self.validate_certificate_chain(cert_path, ca_cert_path)
                                cert_info['chain_valid'] = is_valid
                                if not is_valid:
                                    self.results['alerts'].append({
                                        'severity': 'error',
                                        'message': f"❌ {node_name} {cert_type}: {msg}",
                                        'certificate': cert_info
                                    })
                            
                            # Check key permissions
                            key_file = cert_file.replace('-cert.pem', '-key.pem')
                            key_path = node_dir / key_file
                            is_secure, msg = self.check_key_permissions(key_path)
                            if not is_secure:
                                self.results['alerts'].append({
                                    'severity': 'warning',
                                    'message': f"⚠️  {node_name} {cert_type} key: {msg}",
                                    'file': str(key_path)
                                })
    
    def print_report(self):
        """Print human-readable report"""
        print("=" * 70)
        print("📜 CERTIFICATE MONITORING REPORT")
        print("=" * 70)
        print()
        
        # Summary
        summary = self.results['summary']
        print(f"📊 Summary:")
        print(f"  Total certificates: {summary['total']}")
        print(f"  ✅ Valid: {summary['valid']}")
        print(f"  ⚠️  Expiring soon: {summary['expiring_soon']}")
        print(f"  🔴 Expired: {summary['expired']}")
        print(f"  ❌ Invalid: {summary['invalid']}")
        print()
        
        # Alerts
        if self.results['alerts']:
            print(f"🚨 ALERTS ({len(self.results['alerts'])}):")
            print()
            for alert in sorted(self.results['alerts'], key=lambda x: x['severity']):
                print(f"  {alert['message']}")
            print()
        else:
            print("✅ No alerts - all certificates are valid!")
            print()
        
        # Certificate details
        print("📋 Certificate Details:")
        print()
        
        for cert in sorted(self.results['certificates'], key=lambda x: x['days_until_expiry']):
            status_icon = {
                'valid': '✅',
                'expiring_soon': '⚠️ ',
                'expired': '🔴',
                'not_yet_valid': '⚠️ ',
                'error': '❌'
            }.get(cert['status'], '❓')
            
            print(f"  {status_icon} {cert['node']} - {cert['type']}")
            print(f"     Status: {cert['status']}")
            print(f"     Expires: {cert['not_after']} ({cert['days_until_expiry']} days)")
            print(f"     Subject: {cert['subject']}")
            if 'chain_valid' in cert:
                chain_icon = '✅' if cert['chain_valid'] else '❌'
                print(f"     Chain: {chain_icon}")
            print()
        
        # Errors
        if self.results['errors']:
            print(f"❌ ERRORS ({len(self.results['errors'])}):")
            print()
            for error in self.results['errors']:
                print(f"  File: {error['file']}")
                print(f"  Error: {error['error']}")
                print()
        
        print("=" * 70)
    
    def get_exit_code(self) -> int:
        """
        Get exit code based on results.
        
        Returns:
            0: All OK
            1: Warnings (expiring soon)
            2: Critical (expired or invalid)
        """
        if self.results['summary']['expired'] > 0 or self.results['summary']['invalid'] > 0:
            return 2
        elif self.results['summary']['expiring_soon'] > 0 or self.results['alerts']:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Monitor SSL/TLS certificates for Fed-Med-FL',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic monitoring
  python3 scripts/monitor_certificates.py
  
  # Alert for certificates expiring in 60 days
  python3 scripts/monitor_certificates.py --alert-days 60
  
  # JSON output for automation
  python3 scripts/monitor_certificates.py --json
  
  # Custom certificates path
  python3 scripts/monitor_certificates.py --path /custom/path/certificates
        """
    )
    
    parser.add_argument(
        '--path',
        default='./certificates',
        help='Path to certificates directory (default: ./certificates)'
    )
    
    parser.add_argument(
        '--alert-days',
        type=int,
        default=30,
        help='Alert when certificates expire in less than N days (default: 30)'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )
    
    args = parser.parse_args()
    
    # Create monitor and scan
    monitor = CertificateMonitor(
        certificates_path=args.path,
        alert_days=args.alert_days
    )
    
    monitor.scan_certificates()
    
    # Output results
    if args.json:
        print(json.dumps(monitor.results, indent=2))
    else:
        monitor.print_report()
    
    # Exit with appropriate code
    sys.exit(monitor.get_exit_code())


if __name__ == '__main__':
    main()
