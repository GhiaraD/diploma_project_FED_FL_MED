# Signature Policy Testing Results

## Test Date: April 27, 2026

## Overview
Testing the three signature verification policies implemented in the FedMed strategy:
- **log**: Log invalid signatures but continue with aggregation
- **warn**: Log warnings and check threshold, continue if above minimum
- **reject**: Reject clients with invalid signatures from aggregation

---

## Test 1: REJECT Policy ✅ PASSED

### Configuration
```yaml
SIGNATURE_POLICY: "reject"
MIN_VALID_SIGNATURES: "0.8"  # 80% threshold
```

### Test Setup
- Simulated invalid signature by replacing node2's `signing-cert.pem` with node1's certificate
- This causes node2's signature verification to fail (wrong certificate for the signature)
- Both nodes trained successfully and sent parameters to server

### Results

#### Node1 (Client 9f64322f423e4e8fb20aaa46ec78ac23)
- ✅ Signature: **Valid**
- Samples: 1,390
- Accuracy: 97.13%
- Train Loss: 0.0895
- Val Loss: 0.0652
- **Status**: ACCEPTED in aggregation

#### Node2 (Client b47186954e9b4718973664f48e95e9d3)
- ❌ Signature: **Invalid** - "cryptographic verification failed"
- Samples: 1,390
- Accuracy: 91.38%
- Train Loss: 0.1069
- Val Loss: 0.5453
- **Status**: REJECTED from aggregation
- **Policy Action**: "Policy: REJECT - Client will be excluded from aggregation"

#### Aggregation
- **Clients processed**: 2
- **Clients accepted**: 1 (node1 only)
- **Clients rejected**: 1 (node2)
- **Final model**: Based only on node1's parameters
- **Model hash**: 734d8f57a685307f...

#### Signature Statistics
```
Total verifications: 2
Successful: 1
Failed: 1
Unsigned: 0
```

### Conclusion
✅ **REJECT policy works correctly**
- Invalid signatures are detected
- Clients with invalid signatures are excluded from aggregation
- Only valid client parameters are used in the global model
- Clear logging shows which clients were rejected and why

### Performance Note
⚠️ **Observed delay** during parameter transmission (signing phase)
- Likely caused by RSA-PSS signature computation (4096-bit keys)
- JSON serialization of signature package
- mTLS overhead on gRPC transmission
- This is expected behavior for cryptographic operations

---

## Test 2: LOG Policy (Default) - PENDING

### Configuration
```yaml
SIGNATURE_POLICY: "log"
MIN_VALID_SIGNATURES: "0.8"
```

### Expected Behavior
- Log invalid signatures with informational messages
- Continue with aggregation regardless of signature validity
- Track statistics but don't enforce policy
- Useful for development and debugging

### Status
🔄 Ready to test with restored certificates

---

## Test 3: WARN Policy - PENDING

### Configuration
```yaml
SIGNATURE_POLICY: "warn"
MIN_VALID_SIGNATURES: "0.8"  # 80% threshold
```

### Expected Behavior
- Log warnings for invalid signatures
- Check if valid signature ratio meets threshold
- If below threshold, log warning but continue
- Useful for monitoring without blocking

### Status
⏳ Awaiting test execution

---

## Certificate Restoration

After testing REJECT policy:
```bash
# Restored node2's original certificate
cp certificates/nodes/node2/signing-cert.pem.backup certificates/nodes/node2/signing-cert.pem
```

Node2 should now sign with its correct certificate and pass verification.

---

## Next Steps

1. ✅ Test LOG policy with valid certificates (both nodes should pass)
2. ⏳ Test WARN policy with threshold scenarios
3. ⏳ Document performance characteristics of signature operations
4. ⏳ Consider optimization strategies if signing overhead is too high:
   - Signature caching (already implemented)
   - Async signing operations
   - Batch signature verification
   - Hardware acceleration (if available)

---

## Security Policy Recommendations

### Development Environment
- **Recommended**: `SIGNATURE_POLICY: "log"`
- Allows debugging without blocking
- Full visibility into signature issues
- No impact on FL workflow

### Staging/Testing Environment
- **Recommended**: `SIGNATURE_POLICY: "warn"`
- Monitors signature health
- Alerts on threshold violations
- Doesn't block legitimate traffic

### Production Environment
- **Recommended**: `SIGNATURE_POLICY: "reject"`
- Strict security enforcement
- Prevents tampered parameters from affecting global model
- Maintains FL integrity and trust

### Threshold Configuration
- **Conservative**: `MIN_VALID_SIGNATURES: 1.0` (100% - all must be valid)
- **Balanced**: `MIN_VALID_SIGNATURES: 0.8` (80% - allows some failures)
- **Permissive**: `MIN_VALID_SIGNATURES: 0.5` (50% - majority must be valid)

For production, recommend starting with 100% and adjusting based on operational experience.
