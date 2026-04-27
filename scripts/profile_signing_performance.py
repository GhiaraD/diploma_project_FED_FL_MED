#!/usr/bin/env python3
"""
Profile signature signing and verification performance.

This script measures the time taken for various cryptographic operations
to identify bottlenecks in the FL parameter signing process.
"""
import time
import sys
import json
import numpy as np
from pathlib import Path
from typing import Dict, List

# Add node_core to path
sys.path.insert(0, str(Path(__file__).parent.parent / "shared/python/node_core"))

from node_core.crypto_utils import PayloadSigner, sign_model_parameters, verify_model_parameters


def generate_mock_parameters(size_mb: float = 10.0) -> List[np.ndarray]:
    """
    Generate mock model parameters of specified size.
    
    Args:
        size_mb: Total size in megabytes
    
    Returns:
        List of numpy arrays simulating model parameters
    """
    # Calculate number of float32 values needed
    # 1 MB = 1,048,576 bytes, float32 = 4 bytes
    num_values = int((size_mb * 1_048_576) / 4)
    
    # Split into multiple arrays (simulating layers)
    layer_sizes = [
        num_values // 10,  # Large layer
        num_values // 20,  # Medium layer
        num_values // 20,  # Medium layer
        num_values // 5,   # Large layer
        num_values // 4,   # Largest layer
    ]
    
    # Adjust last layer to match exact size
    layer_sizes[-1] = num_values - sum(layer_sizes[:-1])
    
    parameters = [np.random.randn(size).astype(np.float32) for size in layer_sizes]
    
    actual_size_mb = sum(p.nbytes for p in parameters) / 1_048_576
    print(f"Generated {len(parameters)} parameter arrays, total size: {actual_size_mb:.2f} MB")
    
    return parameters


def profile_operation(name: str, func, *args, **kwargs) -> float:
    """
    Profile a single operation.
    
    Args:
        name: Operation name
        func: Function to profile
        *args, **kwargs: Arguments to pass to function
    
    Returns:
        Elapsed time in seconds
    """
    print(f"\n{'='*70}")
    print(f"Profiling: {name}")
    print(f"{'='*70}")
    
    start = time.time()
    result = func(*args, **kwargs)
    elapsed = time.time() - start
    
    print(f"✓ Completed in {elapsed:.3f} seconds ({elapsed*1000:.1f} ms)")
    
    return elapsed, result


def profile_signing_workflow(
    parameters: List[np.ndarray],
    signer: PayloadSigner,
    node_id: str = "test_node",
    round_num: int = 1,
) -> Dict[str, float]:
    """
    Profile the complete signing workflow with detailed timing.
    
    Args:
        parameters: Model parameters to sign
        signer: PayloadSigner instance
        node_id: Node identifier
        round_num: Round number
    
    Returns:
        Dictionary of timing measurements
    """
    timings = {}
    
    # 1. Serialize parameters
    print("\n" + "="*70)
    print("STEP 1: Serialize Parameters")
    print("="*70)
    start = time.time()
    serialized = []
    for i, param in enumerate(parameters):
        param_bytes = param.tobytes()
        serialized.append(param_bytes)
        if i == 0:
            print(f"  Layer 0: {len(param_bytes):,} bytes ({len(param_bytes)/1024:.1f} KB)")
    total_bytes = sum(len(p) for p in serialized)
    timings['serialize'] = time.time() - start
    print(f"  Total serialized: {total_bytes:,} bytes ({total_bytes/1024/1024:.2f} MB)")
    print(f"✓ Serialization: {timings['serialize']:.3f}s")
    
    # 2. Concatenate all parameters
    print("\n" + "="*70)
    print("STEP 2: Concatenate Parameters")
    print("="*70)
    start = time.time()
    combined = b''.join(serialized)
    timings['concatenate'] = time.time() - start
    print(f"  Combined size: {len(combined):,} bytes ({len(combined)/1024/1024:.2f} MB)")
    print(f"✓ Concatenation: {timings['concatenate']:.3f}s")
    
    # 3. Compute SHA-256 hash
    print("\n" + "="*70)
    print("STEP 3: Compute SHA-256 Hash")
    print("="*70)
    start = time.time()
    import hashlib
    hash_obj = hashlib.sha256(combined)
    param_hash = hash_obj.hexdigest()
    timings['hash'] = time.time() - start
    print(f"  Hash: {param_hash[:32]}...")
    print(f"✓ Hashing: {timings['hash']:.3f}s ({len(combined)/1024/1024/timings['hash']:.1f} MB/s)")
    
    # 4. Create metadata
    print("\n" + "="*70)
    print("STEP 4: Create Metadata")
    print("="*70)
    start = time.time()
    metadata = {
        'node_id': node_id,
        'round': round_num,
        'timestamp': time.time(),
        'num_parameters': len(parameters),
    }
    timings['metadata'] = time.time() - start
    print(f"  Metadata: {metadata}")
    print(f"✓ Metadata creation: {timings['metadata']:.6f}s")
    
    # 5. Sign hash with RSA-PSS
    print("\n" + "="*70)
    print("STEP 5: Sign Hash (RSA-PSS 4096-bit)")
    print("="*70)
    start = time.time()
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    signature = signer.private_key.sign(
        hash_obj.digest(),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    timings['sign'] = time.time() - start
    print(f"  Signature size: {len(signature)} bytes")
    print(f"✓ Signing: {timings['sign']:.3f}s")
    
    # 6. Load certificate
    print("\n" + "="*70)
    print("STEP 6: Load Certificate")
    print("="*70)
    start = time.time()
    cert_pem = signer.certificate_path.read_text()
    timings['load_cert'] = time.time() - start
    print(f"  Certificate size: {len(cert_pem)} bytes")
    print(f"✓ Certificate loading: {timings['load_cert']:.6f}s")
    
    # 7. Create signature package
    print("\n" + "="*70)
    print("STEP 7: Create Signature Package")
    print("="*70)
    start = time.time()
    signature_package = {
        'signed': True,
        'signature': signature.hex(),
        'hash': param_hash,
        'metadata': metadata,
        'certificate': cert_pem,
    }
    timings['package'] = time.time() - start
    print(f"  Package keys: {list(signature_package.keys())}")
    print(f"✓ Package creation: {timings['package']:.6f}s")
    
    # 8. Serialize to JSON
    print("\n" + "="*70)
    print("STEP 8: Serialize to JSON")
    print("="*70)
    start = time.time()
    json_str = json.dumps(signature_package)
    timings['json_serialize'] = time.time() - start
    print(f"  JSON size: {len(json_str):,} bytes ({len(json_str)/1024:.1f} KB)")
    print(f"✓ JSON serialization: {timings['json_serialize']:.3f}s")
    
    # Total
    timings['total'] = sum(timings.values())
    
    return timings, signature_package


def profile_verification_workflow(
    parameters: List[np.ndarray],
    signature_package: Dict,
    verifier: PayloadSigner,
) -> Dict[str, float]:
    """
    Profile the complete verification workflow.
    
    Args:
        parameters: Model parameters to verify
        signature_package: Signature package from signing
        verifier: PayloadSigner instance for verification
    
    Returns:
        Dictionary of timing measurements
    """
    timings = {}
    
    # 1. Deserialize JSON
    print("\n" + "="*70)
    print("VERIFICATION STEP 1: Deserialize JSON")
    print("="*70)
    start = time.time()
    # Simulate receiving JSON string
    json_str = json.dumps(signature_package)
    pkg = json.loads(json_str)
    timings['json_deserialize'] = time.time() - start
    print(f"✓ JSON deserialization: {timings['json_deserialize']:.6f}s")
    
    # 2. Extract certificate
    print("\n" + "="*70)
    print("VERIFICATION STEP 2: Extract & Parse Certificate")
    print("="*70)
    start = time.time()
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    cert_pem = pkg['certificate']
    certificate = x509.load_pem_x509_certificate(cert_pem.encode(), default_backend())
    public_key = certificate.public_key()
    timings['parse_cert'] = time.time() - start
    print(f"✓ Certificate parsing: {timings['parse_cert']:.6f}s")
    
    # 3. Recompute hash
    print("\n" + "="*70)
    print("VERIFICATION STEP 3: Recompute Parameter Hash")
    print("="*70)
    start = time.time()
    serialized = [p.tobytes() for p in parameters]
    combined = b''.join(serialized)
    import hashlib
    computed_hash = hashlib.sha256(combined).hexdigest()
    timings['recompute_hash'] = time.time() - start
    print(f"  Computed hash: {computed_hash[:32]}...")
    print(f"  Expected hash: {pkg['hash'][:32]}...")
    print(f"  Match: {computed_hash == pkg['hash']}")
    print(f"✓ Hash recomputation: {timings['recompute_hash']:.3f}s")
    
    # 4. Verify signature
    print("\n" + "="*70)
    print("VERIFICATION STEP 4: Verify RSA-PSS Signature")
    print("="*70)
    start = time.time()
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    signature_bytes = bytes.fromhex(pkg['signature'])
    try:
        public_key.verify(
            signature_bytes,
            bytes.fromhex(computed_hash),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        is_valid = True
    except Exception as e:
        is_valid = False
    timings['verify'] = time.time() - start
    print(f"  Signature valid: {is_valid}")
    print(f"✓ Signature verification: {timings['verify']:.3f}s")
    
    # Total
    timings['total'] = sum(timings.values())
    
    return timings


def main():
    """Main profiling routine."""
    print("="*70)
    print("SIGNATURE PERFORMANCE PROFILING")
    print("="*70)
    
    # Configuration
    certificates_path = Path("/certificates")
    node_id = "node1"
    
    # Test with different parameter sizes
    test_sizes = [
        5.0,   # 5 MB - small model
        10.0,  # 10 MB - medium model
        50.0,  # 50 MB - large model (ResNet18 is ~45MB)
    ]
    
    # Initialize signer
    print("\nInitializing signer...")
    signer = PayloadSigner(
        node_id=node_id,
        certificates_path=str(certificates_path),
        is_central=False
    )
    
    if not signer.is_ready():
        print("✗ Signer not ready - certificates not found")
        return 1
    
    print(f"✓ Signer ready")
    print(f"  Private key: {signer.private_key_path}")
    print(f"  Certificate: {signer.certificate_path}")
    
    # Profile each size
    all_results = []
    
    for size_mb in test_sizes:
        print("\n" + "="*70)
        print(f"TESTING WITH {size_mb} MB PARAMETERS")
        print("="*70)
        
        # Generate parameters
        parameters = generate_mock_parameters(size_mb)
        
        # Profile signing
        sign_timings, signature_package = profile_signing_workflow(
            parameters, signer, node_id, round_num=1
        )
        
        # Profile verification
        verify_timings = profile_verification_workflow(
            parameters, signature_package, signer
        )
        
        # Store results
        result = {
            'size_mb': size_mb,
            'signing': sign_timings,
            'verification': verify_timings,
        }
        all_results.append(result)
        
        # Summary for this size
        print("\n" + "="*70)
        print(f"SUMMARY FOR {size_mb} MB")
        print("="*70)
        print(f"Signing total:       {sign_timings['total']:.3f}s")
        print(f"  - Serialization:   {sign_timings['serialize']:.3f}s ({sign_timings['serialize']/sign_timings['total']*100:.1f}%)")
        print(f"  - Hashing:         {sign_timings['hash']:.3f}s ({sign_timings['hash']/sign_timings['total']*100:.1f}%)")
        print(f"  - RSA signing:     {sign_timings['sign']:.3f}s ({sign_timings['sign']/sign_timings['total']*100:.1f}%)")
        print(f"  - JSON serialize:  {sign_timings['json_serialize']:.3f}s ({sign_timings['json_serialize']/sign_timings['total']*100:.1f}%)")
        print(f"  - Other:           {sign_timings['total'] - sign_timings['serialize'] - sign_timings['hash'] - sign_timings['sign'] - sign_timings['json_serialize']:.3f}s")
        print()
        print(f"Verification total:  {verify_timings['total']:.3f}s")
        print(f"  - Hash recompute:  {verify_timings['recompute_hash']:.3f}s ({verify_timings['recompute_hash']/verify_timings['total']*100:.1f}%)")
        print(f"  - RSA verify:      {verify_timings['verify']:.3f}s ({verify_timings['verify']/verify_timings['total']*100:.1f}%)")
        print(f"  - Other:           {verify_timings['total'] - verify_timings['recompute_hash'] - verify_timings['verify']:.3f}s")
    
    # Final summary
    print("\n" + "="*70)
    print("OVERALL SUMMARY")
    print("="*70)
    print("\nSigning Performance:")
    print(f"{'Size (MB)':<12} {'Total (s)':<12} {'Hash (s)':<12} {'Sign (s)':<12} {'JSON (s)':<12}")
    print("-" * 60)
    for r in all_results:
        s = r['signing']
        print(f"{r['size_mb']:<12.1f} {s['total']:<12.3f} {s['hash']:<12.3f} {s['sign']:<12.3f} {s['json_serialize']:<12.3f}")
    
    print("\nVerification Performance:")
    print(f"{'Size (MB)':<12} {'Total (s)':<12} {'Hash (s)':<12} {'Verify (s)':<12}")
    print("-" * 48)
    for r in all_results:
        v = r['verification']
        print(f"{r['size_mb']:<12.1f} {v['total']:<12.3f} {v['recompute_hash']:<12.3f} {v['verify']:<12.3f}")
    
    # Bottleneck analysis
    print("\n" + "="*70)
    print("BOTTLENECK ANALYSIS")
    print("="*70)
    
    # Analyze largest model
    largest = all_results[-1]
    sign_t = largest['signing']
    verify_t = largest['verification']
    
    print(f"\nFor {largest['size_mb']} MB model:")
    print(f"\nSigning bottlenecks:")
    sign_ops = [
        ('Serialization', sign_t['serialize']),
        ('Hashing', sign_t['hash']),
        ('RSA Signing', sign_t['sign']),
        ('JSON Serialization', sign_t['json_serialize']),
    ]
    sign_ops.sort(key=lambda x: x[1], reverse=True)
    for i, (op, time_s) in enumerate(sign_ops, 1):
        pct = time_s / sign_t['total'] * 100
        print(f"  {i}. {op:<20} {time_s:>6.3f}s ({pct:>5.1f}%)")
    
    print(f"\nVerification bottlenecks:")
    verify_ops = [
        ('Hash Recomputation', verify_t['recompute_hash']),
        ('RSA Verification', verify_t['verify']),
    ]
    verify_ops.sort(key=lambda x: x[1], reverse=True)
    for i, (op, time_s) in enumerate(verify_ops, 1):
        pct = time_s / verify_t['total'] * 100
        print(f"  {i}. {op:<20} {time_s:>6.3f}s ({pct:>5.1f}%)")
    
    # Recommendations
    print("\n" + "="*70)
    print("OPTIMIZATION RECOMMENDATIONS")
    print("="*70)
    
    if sign_t['hash'] > sign_t['sign']:
        print("\n1. HASHING is the main bottleneck")
        print("   - Consider using faster hash algorithm (BLAKE2)")
        print("   - Implement parallel hashing for large parameters")
        print("   - Use incremental hashing during training")
    else:
        print("\n1. RSA SIGNING is the main bottleneck")
        print("   - Consider using smaller key size (2048-bit)")
        print("   - Use ECDSA instead of RSA (much faster)")
        print("   - Implement async signing (don't block training)")
    
    if sign_t['json_serialize'] > 0.1:
        print("\n2. JSON SERIALIZATION is significant")
        print("   - Use binary format (MessagePack, Protocol Buffers)")
        print("   - Compress signature package")
        print("   - Send signature separately from parameters")
    
    print("\n3. GENERAL OPTIMIZATIONS")
    print("   - Cache signatures for unchanged parameters")
    print("   - Sign only parameter deltas, not full model")
    print("   - Use hardware acceleration (AES-NI, GPU)")
    print("   - Implement signature batching")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
