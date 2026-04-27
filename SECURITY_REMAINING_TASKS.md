# 🔐 Security - Remaining Tasks

**Data**: 27 aprilie 2026  
**Status**: Analiză aspecte rămase

---

## ✅ Completat (FAZA 1)

- ✅ **mTLS pentru Flower gRPC** - Comunicare securizată între noduri
- ✅ **Payload Signing** - Semnături digitale RSA-PSS-SHA256
- ✅ **Signature Verification** - Verificare server-side
- ✅ **Security Policies** - LOG, WARN, REJECT
- ✅ **Certificate Generation** - Script automat
- ✅ **Testing** - Toate testele reușite

---

## 🚧 În Lucru / Rămase

### PRIORITATE ÎNALTĂ

#### 1. 🌐 HTTPS pentru Browser (mkcert) ⚠️ **IMPORTANT**

**Problema:**
```yaml
# Acum în docker-compose.yml
ENABLE_SSL: "false"  # Disabled for UI compatibility
```

Browser-ele nu acceptă self-signed certificates → UI nu poate accesa API-urile prin HTTPS.

**Soluție: mkcert**
- Generează certificate trusted automat de browser
- Funcționează pentru localhost și IP-uri locale
- Zero configurare în browser

**Pași:**
1. Instalare mkcert pe host
2. Generare certificate pentru:
   - `localhost`
   - `127.0.0.1`
   - `node1.local`, `node2.local`, `node3.local` (opțional)
3. Configurare FastAPI cu certificate mkcert
4. Actualizare UI pentru HTTPS URLs
5. Testing în browser

**Beneficii:**
- ✅ HTTPS în browser fără warning-uri
- ✅ Securitate end-to-end (UI → API → Flower)
- ✅ Experiență user mai bună
- ✅ Compliance cu best practices

**Estimare timp:** 2-3 ore

---

#### 2. 🔒 Differential Privacy (DP) ⚠️ **ESENȚIAL**

**De ce este critic:**
- **GDPR Compliance** - Protecție date personale
- **HIPAA Compliance** - Protecție date medicale
- **Privacy Guarantees** - Garanții formale matematice
- **Inference Attack Protection** - Prevenire atacuri

**Ce trebuie implementat:**

**A. Client-Side DP (Opacus)**
```python
# În flower_client.py
from opacus import PrivacyEngine

privacy_engine = PrivacyEngine()
model, optimizer, data_loader = privacy_engine.make_private(
    module=model,
    optimizer=optimizer,
    data_loader=train_loader,
    noise_multiplier=1.0,
    max_grad_norm=1.0,
)
```

**B. Server-Side DP (Noise Injection)**
```python
# În flower_strategy.py
def aggregate_fit_with_dp(self, results):
    # Aggregate parameters
    aggregated = super().aggregate_fit(results)
    
    # Add noise for DP
    noise = generate_gaussian_noise(
        shape=aggregated.shape,
        sensitivity=self.sensitivity,
        epsilon=self.epsilon,
        delta=self.delta
    )
    
    return aggregated + noise
```

**C. Privacy Accounting**
- Track epsilon/delta per round
- Privacy budget depletion alerts
- Compliance reporting

**Configurare recomandată pentru medical:**
```yaml
# Conservative (High Privacy)
DP_ENABLED: "true"
DP_TARGET_EPSILON: "0.5"  # per round
DP_TARGET_DELTA: "1e-6"
DP_NOISE_MULTIPLIER: "1.0"
DP_MAX_GRAD_NORM: "1.0"
DP_MAX_ROUNDS: "20"
```

**Trade-offs:**
- Accuracy loss: 2-15% (depending on ε)
- Training time: +20-40%
- Memory usage: +30-50%

**Estimare timp:** 1-2 săptămâni

---

### PRIORITATE MEDIE

#### 3. 📊 Certificate Monitoring & Renewal

**Ce lipsește:**
- [ ] Script pentru verificare expirare certificate
- [ ] Alerting pentru certificate aproape expirate
- [ ] Automated renewal pentru development
- [ ] Health checks pentru certificate validity
- [ ] Dashboard pentru certificate status

**Script necesar:**
```python
# scripts/monitor_certificates.py
def check_certificate_expiry(cert_path):
    cert = load_certificate(cert_path)
    expiry_date = cert.not_valid_after
    days_remaining = (expiry_date - datetime.now()).days
    
    if days_remaining < 30:
        alert(f"Certificate expires in {days_remaining} days!")
```

**Estimare timp:** 1-2 zile

---

#### 4. 🔐 Production Certificate Management

**Pentru deployment în producție:**
- [ ] Integration cu CA externă (Let's Encrypt, HashiCorp Vault)
- [ ] HSM support pentru private keys
- [ ] Certificate Revocation List (CRL)
- [ ] OCSP responder pentru certificate validation
- [ ] Manual approval workflows

**Estimare timp:** 1 săptămână

---

#### 5. 📈 Security Monitoring Dashboard

**Extensii necesare pentru UI:**
- [ ] Certificate status și expiry dates
- [ ] Privacy budget consumption (după DP)
- [ ] Security events timeline
- [ ] Signature verification statistics
- [ ] Compliance status indicators
- [ ] Real-time security alerts

**Estimare timp:** 3-5 zile

---

### PRIORITATE SCĂZUTĂ (Nice to Have)

#### 6. 🔍 Security Audit Logging

**Îmbunătățiri:**
- [ ] Centralized security event logging
- [ ] Audit trail pentru toate operațiile critice
- [ ] Integration cu SIEM systems
- [ ] Compliance reporting automation
- [ ] Forensic analysis tools

**Estimare timp:** 1 săptămână

---

#### 7. 🛡️ Advanced Security Features

**Opțional, pentru viitor:**
- [ ] **Secure Multi-Party Computation (SMPC)** - Calcule pe date criptate
- [ ] **Homomorphic Encryption** - Training pe date criptate
- [ ] **Trusted Execution Environments (TEE)** - Intel SGX, AMD SEV
- [ ] **Blockchain pentru Audit Trail** - Immutable audit log
- [ ] **Zero-Knowledge Proofs** - Verificare fără dezvăluire

**Estimare timp:** Luni/Ani (research-level)

---

## 📋 Prioritizare Recomandată

### Săptămâna 1-2: HTTPS cu mkcert ⚠️
**De ce acum:**
- Rapid de implementat (2-3 ore)
- Impact mare pe UX
- Necesar pentru demo/prezentare
- Completează securitatea end-to-end

**Pași:**
1. Instalare mkcert
2. Generare certificate
3. Configurare FastAPI
4. Update UI URLs
5. Testing

---

### Săptămâna 3-4: Differential Privacy (Partea 1) ⚠️
**De ce acum:**
- Esențial pentru compliance medical
- Cerință GDPR/HIPAA
- Diferențiator major al proiectului

**Pași:**
1. Opacus integration (client-side)
2. Basic DP configuration
3. Testing cu ε diferite
4. Documentation

---

### Săptămâna 5-6: Differential Privacy (Partea 2)
**Continuare:**
1. Server-side DP aggregation
2. Privacy accounting
3. Compliance reporting
4. Optimization

---

### Săptămâna 7-8: Certificate Monitoring
**Consolidare:**
1. Monitoring tools
2. Automated renewal (dev)
3. Dashboard integration
4. Alerting

---

### Luna 2+: Production Readiness
**Opțional:**
1. External CA integration
2. HSM support
3. Security dashboard
4. Advanced features

---

## 🎯 Minimum Viable Security (MVS)

**Pentru deployment în producție, TREBUIE:**
1. ✅ mTLS (Flower) - **COMPLETAT**
2. ✅ Payload Signing - **COMPLETAT**
3. ✅ Security Policies - **COMPLETAT**
4. ⚠️ **HTTPS (Browser)** - **NECESAR**
5. ⚠️ **Differential Privacy** - **NECESAR**
6. ⚠️ Certificate Monitoring - **RECOMANDAT**

**Pentru demo/prezentare, TREBUIE:**
1. ✅ mTLS - **COMPLETAT**
2. ✅ Payload Signing - **COMPLETAT**
3. ⚠️ **HTTPS (Browser)** - **NECESAR**
4. ⚠️ Differential Privacy (basic) - **RECOMANDAT**

---

## 📊 Comparație: Self-Signed vs mkcert

| Aspect | Self-Signed Certificates | mkcert Certificates |
|--------|-------------------------|---------------------|
| **Browser Trust** | ❌ Warning-uri | ✅ Trusted automat |
| **Setup Complexity** | 🟢 Simplu | 🟢 Simplu |
| **Development** | 🟡 OK cu warning-uri | ✅ Perfect |
| **Production** | ❌ NU | ❌ NU (doar dev) |
| **User Experience** | ❌ Rău | ✅ Excelent |
| **Security** | ✅ Bună | ✅ Bună |

**Concluzie:** Pentru development și demo, **mkcert este superior**.

---

## 🔧 Implementation Plan: HTTPS cu mkcert

### Pas 1: Instalare mkcert (5 min)
```bash
# Linux
sudo apt install mkcert

# Sau
wget https://github.com/FiloSottile/mkcert/releases/download/v1.4.4/mkcert-v1.4.4-linux-amd64
chmod +x mkcert-v1.4.4-linux-amd64
sudo mv mkcert-v1.4.4-linux-amd64 /usr/local/bin/mkcert

# Install CA
mkcert -install
```

### Pas 2: Generare Certificate (5 min)
```bash
# Create directory
mkdir -p certificates/mkcert

# Generate certificates
cd certificates/mkcert

# Pentru localhost
mkcert localhost 127.0.0.1 ::1

# Pentru noduri (opțional)
mkcert node1.local node2.local node3.local

# Rezultat:
# - localhost+2.pem (certificate)
# - localhost+2-key.pem (private key)
```

### Pas 3: Configurare Docker (10 min)
```yaml
# docker-compose.yml
services:
  node1-api:
    environment:
      ENABLE_SSL: "true"
      CERTIFICATES_PATH: /certificates/mkcert
      SSL_CERT_FILE: localhost+2.pem
      SSL_KEY_FILE: localhost+2-key.pem
    volumes:
      - ./certificates/mkcert:/certificates/mkcert:ro
```

### Pas 4: Update UI (10 min)
```javascript
// services/node/ui/.env.local
NEXT_PUBLIC_API_BASE=https://localhost:8001
```

### Pas 5: Testing (15 min)
```bash
# Restart services
docker compose down -v
docker compose up -d

# Test în browser
# https://localhost:3001 - UI Node1
# https://localhost:8001 - API Node1

# Ar trebui să funcționeze fără warning-uri!
```

**Total timp:** ~45 minute

---

## ✅ Checklist Final pentru Securitate

### Must Have (Production)
- [x] mTLS pentru Flower gRPC
- [x] Payload Signing & Verification
- [x] Security Policies (LOG/WARN/REJECT)
- [ ] **HTTPS pentru Browser (mkcert)** ⚠️
- [ ] **Differential Privacy** ⚠️
- [ ] Certificate Monitoring

### Should Have (Production)
- [ ] External CA integration
- [ ] HSM support
- [ ] Security Dashboard
- [ ] Automated certificate renewal
- [ ] Compliance reporting

### Nice to Have (Future)
- [ ] SMPC
- [ ] Homomorphic Encryption
- [ ] TEE support
- [ ] Blockchain audit trail
- [ ] Zero-Knowledge Proofs

---

## 🎯 Recomandare Finală

**Pentru următoarele 2 săptămâni:**

### Săptămâna 1:
1. **Ziua 1**: HTTPS cu mkcert (2-3 ore)
2. **Ziua 2-3**: Differential Privacy - Client-side (Opacus)
3. **Ziua 4-5**: Differential Privacy - Testing & Tuning

### Săptămâna 2:
1. **Ziua 1-2**: Differential Privacy - Server-side
2. **Ziua 3**: Privacy Accounting
3. **Ziua 4**: Certificate Monitoring
4. **Ziua 5**: Documentation & Testing

**După aceasta, vei avea:**
- ✅ Securitate completă end-to-end
- ✅ HTTPS funcțional în browser
- ✅ Differential Privacy pentru compliance
- ✅ Monitoring pentru certificate
- ✅ Production-ready security stack

---

## 📞 Next Steps

**Imediat:**
1. Implementare HTTPS cu mkcert (rapid, impact mare)
2. Differential Privacy (esențial pentru medical)

**Apoi:**
3. Certificate monitoring
4. Security dashboard
5. Production hardening

---

*Document generat: 27 aprilie 2026*  
*Versiune: 1.0*  
*Status: ANALIZĂ COMPLETĂ*
