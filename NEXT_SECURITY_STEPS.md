# Fed-Med-FL - Next Security Implementation Steps

## 📋 Document Overview

Acest document conține planul detaliat pentru următoarele îmbunătățiri de securitate în Fed-Med-FL, bazat pe analiza arhitecturii existente și cerințele specifice pentru aplicații medicale.

**Data creării**: 26 aprilie 2026  
**Status actual**: Planificare - NU implementat încă  
**Prioritate**: Critică pentru deployment în producție

---

## 🎯 Obiective Principale

1. **mTLS/TLS Implementation**: Securizarea completă a comunicării Flower gRPC și FastAPI
2. **Payload Signing & Verification**: Integritatea și autenticitatea datelor
3. **Differential Privacy**: Protecția privacy-ului pacienților conform GDPR/HIPAA
4. **Certificate Management**: Infrastructură PKI robustă pentru mediul medical

---

## 🔒 FAZA 1: mTLS/TLS și Payload Signing

### Prioritate: **MAXIMĂ** - Implementare imediată

### 1.1 Flower gRPC mTLS (CRITIC)

**Fișiere de modificat:**
- `services/central/app/flower_server.py`
- `services/node/worker/app/flower_client.py`
- `shared/python/node_core/node_core/flower_strategy.py`

**Implementări necesare:**
- Configurarea `fl.server.start_server()` cu parametri SSL
- Configurarea `fl.client.start_numpy_client()` cu certificate client
- Validarea certificatelor în `FedMedStrategy`
- Certificate-based node authentication

**Beneficii:**
- Comunicarea FL complet securizată
- Autentificarea nodurilor la nivel de protocol
- Prevenirea man-in-the-middle attacks

### 1.2 Payload Signing în Flower

**Puncte de implementare:**
- **Client-side**: Semnarea parametrilor înainte de `fit()` return
- **Server-side**: Verificarea semnăturilor în `aggregate_fit()`
- **Strategy**: Semnarea parametrilor globali înainte de distribuire

**Algoritmi recomandați:**
- RSA-PSS cu SHA-256 pentru semnături
- ECDSA P-256 pentru performanță îmbunătățită
- Ed25519 pentru securitate maximă

### 1.3 FastAPI HTTPS

**Fișiere de modificat:**
- `services/node/api/app/main.py`
- `services/central/app/main.py`
- `docker-compose.yml` (configurare SSL)

**Implementări:**
- Configurarea Uvicorn cu SSL certificates
- Middleware pentru verificarea certificatelor client
- Request/response signing middleware

---

## 🏗️ FAZA 2: Certificate Management Infrastructure

### Prioritate: **ÎNALTĂ** - Necesară pentru FAZA 1

### 2.1 Certificate Authority Structure

```
Fed-Med-FL Root CA
├── Central Server Certificate (server + client)
├── Node1 Certificate (client + server + signing)
├── Node2 Certificate (client + server + signing)
└── Node3 Certificate (client + server + signing)
```

### 2.2 Certificate Generation Script

**Fișier nou**: `scripts/generate_certificates.py`

**Funcționalități:**
- Generare Root CA automată
- Crearea certificatelor pentru fiecare nod
- Configurarea extensiilor certificate (SAN, Key Usage)
- Setarea permisiunilor corecte (600 pentru private keys)

### 2.3 Certificate Storage Structure

```
/certificates/
├── ca/
│   ├── ca-cert.pem (Root CA public)
│   └── ca-key.pem (Root CA private - 600 permissions)
├── central/
│   ├── server-cert.pem
│   ├── server-key.pem (600 permissions)
│   ├── client-cert.pem
│   └── signing-key.pem (600 permissions)
└── nodes/
    ├── node1/
    │   ├── cert.pem
    │   ├── key.pem (600 permissions)
    │   └── signing-key.pem (600 permissions)
    ├── node2/...
    └── node3/...
```

### 2.4 Docker Integration

**Modificări în `docker-compose.yml`:**
- Volume mounts pentru certificate
- Environment variables pentru SSL paths
- Health checks pentru certificate validity

---

## 🔐 FAZA 3: Differential Privacy Implementation

### Prioritate: **ÎNALTĂ** - Esențială pentru compliance medical

### 3.1 Flower DP Integration

**Flower DP Support disponibil:**
- `flwr.common.dp` module
- Integration cu Opacus (PyTorch DP)
- DP-FedAvg Strategy pre-built
- Client-side și server-side DP

### 3.2 Client-Side DP

**Modificări în `services/node/worker/app/flower_client.py`:**
- Integration cu Opacus DPEngine
- Gradient clipping automat
- Noise injection pe parametri
- Privacy accounting per client

**Configurații recomandate pentru medical:**
```python
# Conservative (High Privacy)
dp_config = {
    "target_epsilon": 0.5,  # per round
    "target_delta": 1e-6,
    "noise_multiplier": 1.0,
    "max_grad_norm": 1.0,
    "max_rounds": 20
}

# Moderate (Balanced)
dp_config = {
    "target_epsilon": 1.0,  # per round
    "target_delta": 1e-5,
    "noise_multiplier": 0.8,
    "max_grad_norm": 1.2,
    "max_rounds": 50
}
```

### 3.3 Server-Side DP

**Modificări în `shared/python/node_core/node_core/flower_strategy.py`:**
- Extinderea `FedMedStrategy` cu DP capabilities
- Central noise injection în `aggregate_fit()`
- Privacy budget tracking global
- Adaptive clipping pentru aggregation

### 3.4 Privacy Accounting

**Funcționalități necesare:**
- Tracking epsilon/delta per round
- Privacy budget depletion alerts
- Privacy loss visualization
- Compliance reporting pentru audit

---

## 📊 FAZA 4: Monitoring și Management

### Prioritate: **MEDIE** - Necesară pentru producție

### 4.1 Certificate Monitoring

**Fișier nou**: `scripts/monitor_certificates.py`

**Funcționalități:**
- Verificarea expirării certificatelor
- Alerting pentru certificate aproape expirate
- Automated renewal (development)
- Health checks pentru certificate validity

### 4.2 Security Audit Dashboard

**Extensii pentru UI:**
- Certificate status și expiry dates
- Privacy budget consumption
- Security events timeline
- Compliance status indicators

### 4.3 Automated Certificate Renewal

**Pentru dezvoltare:**
- Self-signed certificate renewal
- Automated deployment în containers
- Grace period handling

**Pentru producție:**
- Integration cu CA externă
- HSM support pentru private keys
- Manual approval workflows

---

## ⚖️ Trade-offs și Considerații

### 4.1 Performance Impact

**mTLS/TLS:**
- Overhead: ~5-10% pentru gRPC
- Latency: +10-50ms per request
- CPU usage: +15-25% pentru crypto operations

**Differential Privacy:**
- Accuracy loss: 2-15% depending pe ε
- Training time: +20-40% pentru DP calculations
- Memory usage: +30-50% pentru Opacus

### 4.2 Operational Complexity

**Certificate Management:**
- Manual intervention pentru renewal în producție
- Backup și recovery procedures pentru CA keys
- Disaster recovery planning

**DP Configuration:**
- Hyperparameter tuning pentru ε, δ
- Privacy-utility trade-off optimization
- Regulatory compliance validation

---

## 🚀 Implementation Timeline

### Săptămâna 1-2: Certificate Infrastructure
1. Implementare `generate_certificates.py`
2. Configurare Docker volumes și permissions
3. Testing certificate generation și distribution

### Săptămâna 3-4: Flower mTLS
1. Server-side SSL configuration
2. Client-side certificate authentication
3. Payload signing implementation
4. End-to-end testing

### Săptămâna 5-6: FastAPI HTTPS
1. Uvicorn SSL configuration
2. Client certificate validation middleware
3. Request/response signing
4. API security testing

### Săptămâna 7-8: Differential Privacy
1. Opacus integration în client
2. DP strategy implementation
3. Privacy accounting system
4. DP parameter optimization

### Săptămâna 9-10: Monitoring și Production Readiness
1. Certificate monitoring tools
2. Security dashboard extensions
3. Automated renewal (dev)
4. Documentation și training

---

## 📋 Checklist pentru Implementare

### Certificate Management
- [ ] Root CA generation script
- [ ] Node certificate generation
- [ ] Docker volume configuration
- [ ] File permissions automation
- [ ] Certificate validation tools

### Flower Security
- [ ] gRPC mTLS configuration
- [ ] Client certificate authentication
- [ ] Payload signing în fit()
- [ ] Signature verification în aggregate_fit()
- [ ] Error handling pentru certificate issues

### FastAPI Security
- [ ] HTTPS configuration
- [ ] Client certificate middleware
- [ ] Request signing middleware
- [ ] Response verification
- [ ] Security headers implementation

### Differential Privacy
- [ ] Opacus integration
- [ ] Client-side DP engine
- [ ] Server-side DP aggregation
- [ ] Privacy accounting
- [ ] DP parameter configuration UI

### Monitoring
- [ ] Certificate expiry monitoring
- [ ] Privacy budget tracking
- [ ] Security event logging
- [ ] Compliance reporting
- [ ] Automated alerting

---

## 🔍 Testing Strategy

### Security Testing
1. **Penetration testing**: Certificate validation, mTLS handshake
2. **Cryptographic testing**: Signature verification, key strength
3. **Privacy testing**: DP guarantee validation, inference attack resistance
4. **Compliance testing**: GDPR, HIPAA requirement verification

### Performance Testing
1. **Latency impact**: mTLS vs plain communication
2. **Throughput testing**: DP overhead measurement
3. **Resource usage**: CPU, memory, network impact
4. **Scalability testing**: Multi-node performance

---

## 📚 Dependencies și Requirements

### Python Packages
```
# Certificate management
cryptography>=41.0.0
pyOpenSSL>=23.0.0

# Differential Privacy
opacus>=1.4.0
dp-accounting>=0.4.0

# Enhanced security
pycryptodome>=3.19.0
```

### System Requirements
- OpenSSL 1.1.1+ pentru modern crypto
- Hardware entropy source pentru key generation
- Sufficient disk space pentru certificate storage
- Network configuration pentru mTLS ports

---

## 🎯 Success Criteria

### Security Goals
1. **Zero plaintext communication** între noduri
2. **Cryptographic authentication** pentru toate operațiile
3. **Formal privacy guarantees** cu DP implementation
4. **Audit trail complet** pentru toate operațiile de securitate

### Compliance Goals
1. **GDPR compliance** prin DP și encryption
2. **HIPAA compliance** pentru medical data protection
3. **ISO 27001 alignment** pentru security management
4. **Medical device regulation** compliance preparation

### Operational Goals
1. **Automated certificate management** pentru development
2. **Monitoring și alerting** pentru security events
3. **Performance impact** sub 20% pentru normal operations
4. **Documentation completă** pentru deployment și maintenance

---

## 📞 Next Steps

1. **Review și aprobare** a planului de implementare
2. **Resource allocation** pentru development time
3. **Environment setup** pentru certificate testing
4. **Stakeholder communication** despre timeline și impact

**Contact pentru întrebări**: Continuarea implementării va fi făcută în sessiuni viitoare după rezolvarea problemelor curente.

---

*Document generat: 26 aprilie 2026*  
*Versiune: 1.0*  
*Status: Planning Phase*