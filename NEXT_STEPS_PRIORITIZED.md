# Fed-Med-FL - Următorii Pași Prioritizați

**Data**: 27 aprilie 2026  
**Status FAZA 1**: ✅ COMPLETĂ

---

## 🎯 Rezumat Rapid

| Ce am realizat | Ce urmează | Prioritate |
|----------------|------------|------------|
| ✅ mTLS pentru Flower gRPC | Certificate Monitoring | MAXIMĂ |
| ✅ Payload Signing & Verification | Differential Privacy | ÎNALTĂ |
| ✅ Certificate Generation | Production Certificate Mgmt | MEDIE |
| ✅ E2E Testing | Security Dashboard | MEDIE |

---

## 📋 Următorii Pași - Prioritizați

### 🔴 PRIORITATE MAXIMĂ (Săptămâna 1)

#### 1. Certificate Monitoring & Management (2-3 zile)

**De ce este important:**
- Certificatele expiră după 1 an
- Fără monitoring, sistemul va eșua când certificatele expiră
- Necesar pentru producție

**Ce trebuie implementat:**

**Fișier nou**: `scripts/monitor_certificates.py`
```python
# Funcționalități:
- Check expiry dates pentru toate certificatele
- Alert când certificatele expiră în <30 zile
- Validate certificate chain
- Check file permissions
- Generate renewal recommendations
```

**Fișier nou**: `scripts/renew_certificates.py`
```python
# Funcționalități:
- Automated renewal pentru development
- Preserve existing CA
- Update only expired certificates
- Restart affected services
```

**Integration în CI/CD:**
```yaml
# .github/workflows/certificate-check.yml
- name: Check Certificates
  run: python3 scripts/monitor_certificates.py --alert-days 30
```

**Estimare**: 2-3 zile  
**Beneficiu**: Previne downtime din cauza certificatelor expirate

---

#### 2. Security Policy Configuration (1-2 zile)

**De ce este important:**
- Comportamentul actual: signature verification este informativă, nu enforced
- Pentru producție: trebuie să putem configura politica de securitate
- Flexibilitate: development vs production

**Ce trebuie implementat:**

**Modificări în `shared/python/node_core/node_core/flower_strategy.py`:**
```python
class FedMedStrategy(fl.server.strategy.FedAvg):
    def __init__(
        self,
        # ... existing params ...
        signature_policy: str = "log",  # "log", "warn", "reject"
        min_valid_signatures: float = 0.8,  # 80% must be valid
        **kwargs
    ):
        self.signature_policy = signature_policy
        self.min_valid_signatures = min_valid_signatures
```

**Politici disponibile:**
- `"log"`: Log invalid signatures, continue (CURRENT - development)
- `"warn"`: Log warnings, continue if above threshold
- `"reject"`: Reject clients with invalid signatures (production)

**Environment variables în `docker-compose.yml`:**
```yaml
environment:
  SIGNATURE_POLICY: "log"  # or "warn", "reject"
  MIN_VALID_SIGNATURES: "0.8"  # 80%
```

**Estimare**: 1-2 zile  
**Beneficiu**: Production-ready security enforcement

---

### 🟡 PRIORITATE ÎNALTĂ (Săptămânile 2-4)

#### 3. Differential Privacy - Client Side (5-7 zile)

**De ce este important:**
- **GDPR/HIPAA compliance** pentru date medicale
- Protecție împotriva inference attacks
- Formal privacy guarantees
- **ESENȚIAL pentru deployment medical**

**Ce trebuie implementat:**

**Fișier nou**: `shared/python/node_core/node_core/dp_utils.py`
```python
from opacus import PrivacyEngine
from opacus.validators import ModuleValidator

class DPTrainingEngine:
    """Differential Privacy training engine using Opacus"""
    
    def __init__(
        self,
        model,
        optimizer,
        target_epsilon: float = 1.0,
        target_delta: float = 1e-5,
        max_grad_norm: float = 1.0,
        noise_multiplier: float = 0.8
    ):
        # Initialize Opacus PrivacyEngine
        # Attach to model and optimizer
        # Configure privacy parameters
```

**Modificări în `services/node/worker/app/flower_client.py`:**
```python
class FedMedClient(fl.client.NumPyClient):
    def __init__(
        self,
        # ... existing params ...
        enable_dp: bool = False,
        dp_config: Optional[Dict] = None
    ):
        if enable_dp:
            self.dp_engine = DPTrainingEngine(
                model=self.model,
                optimizer=optimizer,
                **dp_config
            )
```

**Configurații recomandate:**
```python
# Pentru date medicale FOARTE sensibile (diagnostic cancer, HIV, etc.)
dp_config_high_privacy = {
    "target_epsilon": 0.5,
    "target_delta": 1e-6,
    "max_grad_norm": 1.0,
    "noise_multiplier": 1.2
}

# Pentru date medicale standard (X-ray classification)
dp_config_moderate = {
    "target_epsilon": 1.0,
    "target_delta": 1e-5,
    "max_grad_norm": 1.2,
    "noise_multiplier": 0.8
}
```

**Testing:**
- Privacy accounting validation
- Accuracy vs privacy trade-off
- Performance impact measurement

**Estimare**: 5-7 zile  
**Beneficiu**: GDPR/HIPAA compliance, formal privacy guarantees

---

#### 4. Differential Privacy - Server Side (3-5 zile)

**De ce este important:**
- Central DP pentru agregare securizată
- Privacy budget tracking global
- Compliance reporting

**Ce trebuie implementat:**

**Modificări în `shared/python/node_core/node_core/flower_strategy.py`:**
```python
from flwr.server.strategy import DPFedAvg

class FedMedDPStrategy(DPFedAvg):
    """Extended FedAvg with Differential Privacy"""
    
    def __init__(
        self,
        # ... existing params ...
        enable_central_dp: bool = False,
        central_dp_config: Optional[Dict] = None,
        privacy_budget: Optional[Dict] = None
    ):
        # Initialize DP aggregation
        # Setup privacy accounting
        # Configure budget tracking
```

**Privacy Budget Tracking:**
```python
class PrivacyBudgetTracker:
    def __init__(self, max_epsilon: float, max_delta: float):
        self.max_epsilon = max_epsilon
        self.max_delta = max_delta
        self.consumed_epsilon = 0.0
        self.rounds_history = []
    
    def consume(self, epsilon: float, delta: float, round_num: int):
        # Track privacy consumption per round
        # Alert when budget is depleted
        # Generate compliance reports
```

**Estimare**: 3-5 zile  
**Beneficiu**: Complete DP implementation, compliance reporting

---

### 🟢 PRIORITATE MEDIE (Săptămânile 5-8)

#### 5. Production Certificate Management (7-10 zile)

**De ce este important:**
- Self-signed certificates nu sunt acceptate în producție
- HSM pentru private key protection
- Certificate lifecycle management

**Ce trebuie implementat:**

**Option A: Let's Encrypt Integration**
```python
# scripts/letsencrypt_integration.py
- Automated certificate issuance
- DNS-01 challenge pentru internal services
- Automated renewal
- Certificate deployment
```

**Option B: HashiCorp Vault Integration**
```python
# scripts/vault_integration.py
- PKI secrets engine
- Dynamic certificate generation
- Automated rotation
- Audit logging
```

**Option C: AWS Certificate Manager**
```python
# scripts/acm_integration.py
- Private CA setup
- Certificate issuance via API
- Automated renewal
- CloudWatch monitoring
```

**Estimare**: 7-10 zile  
**Beneficiu**: Production-ready certificate management

---

#### 6. Security Monitoring Dashboard (5-7 zile)

**De ce este important:**
- Vizibilitate în real-time asupra securității
- Compliance reporting
- Incident detection

**Ce trebuie implementat:**

**UI Extensions în `services/node/ui/`:**

**Pagină nouă**: `/security-dashboard`
```typescript
// Components:
- CertificateStatusCard: Expiry dates, validity
- SignatureStatsCard: Verification statistics
- PrivacyBudgetCard: DP budget consumption (după FAZA 3)
- SecurityEventsTimeline: Recent security events
- ComplianceStatusCard: GDPR/HIPAA compliance indicators
```

**API Endpoints noi în `services/node/api/app/main.py`:**
```python
@app.get("/api/security/certificates")
async def get_certificate_status():
    # Return certificate expiry dates, validity status

@app.get("/api/security/signatures")
async def get_signature_stats():
    # Return signature verification statistics

@app.get("/api/security/privacy-budget")
async def get_privacy_budget():
    # Return DP budget consumption (FAZA 3)

@app.get("/api/security/events")
async def get_security_events():
    # Return recent security events
```

**Estimare**: 5-7 zile  
**Beneficiu**: Real-time security monitoring, compliance reporting

---

## 📊 Timeline Recomandat

```
Săptămâna 1:
├─ Certificate Monitoring (2-3 zile)
└─ Security Policy Config (1-2 zile)

Săptămâna 2-3:
├─ DP Client Side (5-7 zile)
└─ Testing și optimization

Săptămâna 4:
├─ DP Server Side (3-5 zile)
└─ Privacy accounting

Săptămâna 5-6:
└─ Production Certificate Mgmt (7-10 zile)

Săptămâna 7-8:
└─ Security Dashboard (5-7 zile)
```

**Total estimat**: 8 săptămâni pentru implementare completă

---

## 🎯 Milestone-uri

### Milestone 1: Certificate Management (Săptămâna 1) ✅
- [x] FAZA 1 completă
- [ ] Certificate monitoring
- [ ] Security policy configuration
- [ ] Documentation

**Criteriu de succes**: Sistem de alerting funcțional pentru certificate

---

### Milestone 2: Differential Privacy (Săptămâna 4) ⏳
- [ ] Client-side DP implementation
- [ ] Server-side DP implementation
- [ ] Privacy accounting
- [ ] Testing și validation

**Criteriu de succes**: DP funcțional cu formal privacy guarantees (ε, δ)

---

### Milestone 3: Production Ready (Săptămâna 6) ⏳
- [ ] Production certificate management
- [ ] External CA integration
- [ ] HSM support (optional)
- [ ] Automated renewal

**Criteriu de succes**: Sistem production-ready cu certificate management complet

---

### Milestone 4: Monitoring & Compliance (Săptămâna 8) ⏳
- [ ] Security dashboard
- [ ] Real-time monitoring
- [ ] Compliance reporting
- [ ] Automated alerting

**Criteriu de succes**: Dashboard funcțional cu compliance reporting

---

## 🔍 Întrebări Frecvente

### Q: De ce Differential Privacy este prioritate înaltă?

**A**: Pentru aplicații medicale, DP este **esențial** pentru:
- **GDPR compliance**: Protecție date personale
- **HIPAA compliance**: Protected Health Information (PHI)
- **Formal guarantees**: Demonstrabil că privacy este protejat
- **Inference attack protection**: Previne extragerea datelor individuale

Fără DP, sistemul **NU poate fi folosit** pentru date medicale reale în producție.

---

### Q: Cum afectează DP acuratețea modelului?

**A**: Trade-off tipic:
- **ε = 0.5** (high privacy): -10-15% accuracy
- **ε = 1.0** (moderate): -5-10% accuracy
- **ε = 2.0** (low privacy): -2-5% accuracy

Pentru medical imaging (X-ray classification), **ε = 1.0** este un compromis bun:
- Accuracy loss acceptabil (~5-8%)
- Privacy guarantees solide
- GDPR/HIPAA compliant

---

### Q: Certificate monitoring este cu adevărat necesar?

**A**: **DA, CRITIC!** Fără monitoring:
- Certificatele expiră după 1 an
- Sistemul va eșua complet când certificatele expiră
- Debugging va fi dificil (erori SSL cryptice)
- Downtime în producție

Cu monitoring:
- Alerting cu 30 zile înainte
- Automated renewal în development
- Planned maintenance în producție
- Zero downtime

---

### Q: Care este diferența între development și production certificate management?

**A**:

**Development** (CURRENT):
- Self-signed certificates
- Automated generation
- 1 an validitate
- Manual renewal
- Stored în repository (gitignored)

**Production** (NEXT):
- CA-signed certificates (Let's Encrypt, Vault, ACM)
- Automated issuance și renewal
- Shorter validity (90 days)
- HSM pentru private keys
- Centralized management
- Audit logging

---

## 📚 Resurse și Documentație

### Documentație Existentă
- `SECURITY_IMPLEMENTATION_STATUS.md` - Status complet implementare
- `NEXT_SECURITY_STEPS.md` - Plan detaliat original
- `MTLS_IMPLEMENTATION.md` - Detalii mTLS (dacă există)
- `PAYLOAD_SIGNING_IMPLEMENTATION.md` - Detalii signing (dacă există)

### Resurse Externe
- **Flower DP**: https://flower.dev/docs/framework/how-to-use-differential-privacy.html
- **Opacus**: https://opacus.ai/
- **GDPR**: https://gdpr.eu/
- **HIPAA**: https://www.hhs.gov/hipaa/
- **Let's Encrypt**: https://letsencrypt.org/
- **HashiCorp Vault**: https://www.vaultproject.io/

---

## 🚀 Cum să Începi

### Pentru Certificate Monitoring (Prioritate MAXIMĂ):

1. **Creează scriptul de monitoring:**
```bash
touch scripts/monitor_certificates.py
chmod +x scripts/monitor_certificates.py
```

2. **Implementează funcționalitățile de bază:**
```python
# Check expiry dates
# Validate certificate chain
# Check file permissions
# Generate alerts
```

3. **Testează:**
```bash
python3 scripts/monitor_certificates.py
```

4. **Integrează în CI/CD**

---

### Pentru Differential Privacy (Prioritate ÎNALTĂ):

1. **Instalează dependencies:**
```bash
pip install opacus dp-accounting
```

2. **Creează DP utilities:**
```bash
touch shared/python/node_core/node_core/dp_utils.py
```

3. **Implementează DPTrainingEngine**

4. **Testează cu date dummy:**
```python
# Test privacy accounting
# Measure accuracy impact
# Validate ε, δ guarantees
```

5. **Integrează în Flower client**

---

*Document creat: 27 aprilie 2026*  
*Versiune: 1.0*  
*Pentru întrebări: Review SECURITY_IMPLEMENTATION_STATUS.md*
