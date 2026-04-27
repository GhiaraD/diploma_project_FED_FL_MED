#!/usr/bin/env python3
"""
Simple signature performance profiling without heavy dependencies.
"""
import time
import json
import hashlib
import numpy as np
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from cryptography import x509


def generate_mock_parameters(size_mb: float = 10.0):
    """Generate mock model parameters."""
    num_values = int((size_mb * 1_048_576) / 4)
    layer_sizes = [
        num_values // 10,
        num_values // 20,
        num_values // 20,
        num_values // 5,
        num_values // 4,
    ]
    layer_sizes[-1] = num_values - sum(layer_sizes[:-1])
    parameters = [np.random.randn(size).astype(np.float32) for size in layer_sizes]
    actual_size_mb = sum(p.nbytes for p in parameters) / 1_048_576
    print(f"Generated {len(parameters)} arrays, total: {actual_size_mb:.2f} MB")
    return parameters


def profile_signing(parameters, private_key_path, cert_path):
    """Profile the signing process."""
    print("\n" + "="*70)
    print("SIGNING WORKFLOW")
    print("="*70)
    
    timings = {}
    
    # Load private key
    print("\n1. Loading private key...")
    start = time.time()
    with open(private_key_path, 'rb') as f:
        private_key = serialization.load_pem_private_key(
            f.read(), password=None, backend=default_backend()
        )
    timings['load_key'] = time.time() - start
    print(f"   ✓ {timings['load_key']:.6f}s")
    
    # Serialize parameters
    print("\n2. Serializing parameters...")
    start = time.time()
    serialized = [p.tobytes() for p in parameters]
    combined = b''.join(serialized)
    timings['serialize'] = time.time() - start
    size_mb = len(combined) / 1_048_576
    print(f"   ✓ {timings['serialize']:.3f}s ({size_mb:.2f} MB)")
    
    # Hash parameters
    print("\n3. Hashing parameters (SHA-256)...")
    start = time.time()
    hash_digest = hashlib.sha256(combined).digest()
    param_hash = hash_digest.hex()
    timings['hash'] = time.time() - start
    throughput = size_mb / timings['hash']
    print(f"   ✓ {timings['hash']:.3f}s ({throughput:.1f} MB/s)")
    print(f"   Hash: {param_hash[:32]}...")
    
    # Sign hash
    print("\n4. Signing hash (RSA-PSS 4096-bit)...")
    start = time.time()
    signature = private_key.sign(
        hash_digest,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    timings['sign'] = time.time() - start
    print(f"   ✓ {timings['sign']:.3f}s")
    print(f"   Signature: {len(signature)} bytes")
    
    # Load certificate
    print("\n5. Loading certificate...")
    start = time.time()
    with open(cert_path, 'r') as f:
        cert_pem = f.read()
    timings['load_cert'] = time.time() - start
    print(f"   ✓ {timings['load_cert']:.6f}s")
    
    # Create signature package
    print("\n6. Creating signature package...")
    start = time.time()
    signature_package = {
        'signed': True,
        'signature': signature.hex(),
        'hash': param_hash,
        'metadata': {
            'node_id': 'test_node',
            'round': 1,
            'timestamp': time.time(),
        },
        'certificate': cert_pem,
    }
    timings['package'] = time.time() - start
    print(f"   ✓ {timings['package']:.6f}s")
    
    # Serialize to JSON
    print("\n7. Serializing to JSON...")
    start = time.time()
    json_str = json.dumps(signature_package)
    timings['json'] = time.time() - start
    json_size_kb = len(json_str) / 1024
    print(f"   ✓ {timings['json']:.3f}s ({json_size_kb:.1f} KB)")
    
    timings['total'] = sum(timings.values())
    
    return timings, signature_package


def profile_verification(parameters, signature_package):
    """Profile the verification process."""
    print("\n" + "="*70)
    print("VERIFICATION WORKFLOW")
    print("="*70)
    
    timings = {}
    
    # Deserialize JSON
    print("\n1. Deserializing JSON...")
    start = time.time()
    json_str = json.dumps(signature_package)
    pkg = json.loads(json_str)
    timings['json'] = time.time() - start
    print(f"   ✓ {timings['json']:.6f}s")
    
    # Parse certificate
    print("\n2. Parsing certificate...")
    start = time.time()
    cert_pem = pkg['certificate']
    certificate = x509.load_pem_x509_certificate(cert_pem.encode(), default_backend())
    public_key = certificate.public_key()
    timings['parse_cert'] = time.time() - start
    print(f"   ✓ {timings['parse_cert']:.6f}s")
    
    # Recompute hash
    print("\n3. Recomputing hash...")
    start = time.time()
    serialized = [p.tobytes() for p in parameters]
    combined = b''.join(serialized)
    computed_hash = hashlib.sha256(combined).digest()
    timings['hash'] = time.time() - start
    size_mb = len(combined) / 1_048_576
    throughput = size_mb / timings['hash']
    print(f"   ✓ {timings['hash']:.3f}s ({throughput:.1f} MB/s)")
    
    # Verify signature
    print("\n4. Verifying signature (RSA-PSS)...")
    start = time.time()
    signature_bytes = bytes.fromhex(pkg['signature'])
    try:
        public_key.verify(
            signature_bytes,
            computed_hash,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        is_valid = True
    except Exception:
        is_valid = False
    timings['verify'] = time.time() - start
    print(f"   ✓ {timings['verify']:.3f}s (Valid: {is_valid})")
    
    timings['total'] = sum(timings.values())
    
    return timings


def main():
    """Main profiling routine."""
    print("="*70)
    print("SIGNATURE PERFORMANCE PROFILING")
    print("="*70)
    
    # Paths
    private_key_path = Path("certificates/nodes/node1/signing-key.pem")
    cert_path = Path("certificates/nodes/node1/signing-cert.pem")
    
    if not private_key_path.exists():
        print(f"✗ Private key not found: {private_key_path}")
        return 1
    
    if not cert_path.exists():
        print(f"✗ Certificate not found: {cert_path}")
        return 1
    
    # Test sizes (MB)
    test_sizes = [5.0, 10.0, 50.0]
    
    all_results = []
    
    for size_mb in test_sizes:
        print("\n" + "="*70)
        print(f"TESTING {size_mb} MB PARAMETERS")
        print("="*70)
        
        # Generate parameters
        parameters = generate_mock_parameters(size_mb)
        
        # Profile signing
        sign_timings, signature_package = profile_signing(
            parameters, private_key_path, cert_path
        )
        
        # Profile verification
        verify_timings = profile_verification(parameters, signature_package)
        
        # Store results
        all_results.append({
            'size_mb': size_mb,
            'signing': sign_timings,
            'verification': verify_timings,
        })
        
        # Summary
        print("\n" + "="*70)
        print(f"SUMMARY FOR {size_mb} MB")
        print("="*70)
        print(f"\nSigning:       {sign_timings['total']:.3f}s")
        print(f"  Serialize:   {sign_timings['serialize']:.3f}s ({sign_timings['serialize']/sign_timings['total']*100:.1f}%)")
        print(f"  Hash:        {sign_timings['hash']:.3f}s ({sign_timings['hash']/sign_timings['total']*100:.1f}%)")
        print(f"  RSA Sign:    {sign_timings['sign']:.3f}s ({sign_timings['sign']/sign_timings['total']*100:.1f}%)")
        print(f"  JSON:        {sign_timings['json']:.3f}s ({sign_timings['json']/sign_timings['total']*100:.1f}%)")
        
        print(f"\nVerification:  {verify_timings['total']:.3f}s")
        print(f"  Hash:        {verify_timings['hash']:.3f}s ({verify_timings['hash']/verify_timings['total']*100:.1f}%)")
        print(f"  RSA Verify:  {verify_timings['verify']:.3f}s ({verify_timings['verify']/verify_timings['total']*100:.1f}%)")
    
    # Final summary
    print("\n" + "="*70)
    print("OVERALL SUMMARY")
    print("="*70)
    
    print("\nSigning Performance:")
    print(f"{'Size':<8} {'Total':<10} {'Serialize':<12} {'Hash':<10} {'Sign':<10} {'JSON':<10}")
    print("-" * 60)
    for r in all_results:
        s = r['signing']
        print(f"{r['size_mb']:<8.1f} {s['total']:<10.3f} {s['serialize']:<12.3f} {s['hash']:<10.3f} {s['sign']:<10.3f} {s['json']:<10.3f}")
    
    print("\nVerification Performance:")
    print(f"{'Size':<8} {'Total':<10} {'Hash':<10} {'Verify':<10}")
    print("-" * 38)
    for r in all_results:
        v = r['verification']
        print(f"{r['size_mb']:<8.1f} {v['total']:<10.3f} {v['hash']:<10.3f} {v['verify']:<10.3f}")
    
    # Bottleneck analysis
    print("\n" + "="*70)
    print("BOTTLENECK ANALYSIS (50 MB model)")
    print("="*70)
    
    largest = all_results[-1]
    s = largest['signing']
    v = largest['verification']
    
    print("\nSigning bottlenecks:")
    ops = [
        ('Serialization', s['serialize']),
        ('Hashing', s['hash']),
        ('RSA Signing', s['sign']),
        ('JSON', s['json']),
    ]
    ops.sort(key=lambda x: x[1], reverse=True)
    for i, (op, t) in enumerate(ops, 1):
        pct = t / s['total'] * 100
        print(f"  {i}. {op:<15} {t:>6.3f}s ({pct:>5.1f}%)")
    
    print("\nVerification bottlenecks:")
    ops = [
        ('Hashing', v['hash']),
        ('RSA Verify', v['verify']),
    ]
    ops.sort(key=lambda x: x[1], reverse=True)
    for i, (op, t) in enumerate(ops, 1):
        pct = t / v['total'] * 100
        print(f"  {i}. {op:<15} {t:>6.3f}s ({pct:>5.1f}%)")
    
    # Recommendations
    print("\n" + "="*70)
    print("OPTIMIZATION RECOMMENDATIONS")
    print("="*70)
    
    if s['hash'] > s['sign']:
        print("\n✓ HASHING is the main bottleneck")
        print("  Recommendations:")
        print("  1. Use BLAKE2b (2-3x faster than SHA-256)")
        print("  2. Implement parallel hashing for large models")
        print("  3. Consider incremental hashing during training")
    else:
        print("\n✓ RSA SIGNING is the main bottleneck")
        print("  Recommendations:")
        print("  1. Use ECDSA instead of RSA (10-100x faster)")
        print("  2. Reduce key size to 2048-bit (2x faster)")
        print("  3. Implement async signing (don't block)")
    
    if s['json'] > 0.1:
        print("\n✓ JSON SERIALIZATION is significant")
        print("  Recommendations:")
        print("  1. Use binary format (MessagePack, CBOR)")
        print("  2. Compress signature package")
        print("  3. Send signature separately")
    
    print("\n✓ GENERAL OPTIMIZATIONS")
    print("  1. Cache signatures for unchanged parameters")
    print("  2. Sign only parameter deltas")
    print("  3. Use hardware acceleration")
    print("  4. Batch signature operations")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
