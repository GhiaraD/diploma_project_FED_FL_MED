# 🔐 Security Policies - Quick Guide

**Ghid rapid pentru configurarea și utilizarea politicilor de securitate**

---

## 🚀 Quick Start

### 1. Alege politica potrivită

```bash
# Development - Permisivă
SIGNATURE_POLICY="log"

# Staging - Balansat
SIGNATURE_POLICY="warn"

# Production - Strictă
SIGNATURE_POLICY="reject"
```

### 2. Configurează în `docker-compose.yml`

```yaml
services:
  central:
    environment:
      SIGNATURE_POLICY: "log"  # sau "warn" sau "reject"
      MIN_VALID_SIGNATURES: "0.8"  # 80%
```

### 3. Repornește serviciile

```bash
docker compose down -v
docker compose up -d
```

---

## 📋 Politici Disponibile

### 🟢 LOG - Permisivă
**Când să folosești**: Development, debugging, testing inițial

**Ce face:**
- ✅ Verifică semnăturile
- ✅ Loghează rezultatele
- ❌ NU exclude clienți
- ❌ NU verifică threshold

**Exemplu log:**
```
🔐 Signature: ✓ Valid
🔐 Signature: ✗ Invalid - Certificate verification failed
ℹ️  Policy: LOG - Invalid signature logged
```

**Configurare:**
```yaml
SIGNATURE_POLICY: "log"
MIN_VALID_SIGNATURES: "0.5"  # Nu e folosit
```

---

### 🟡 WARN - Balansat
**Când să folosești**: Staging, pre-production, monitorizare

**Ce face:**
- ✅ Verifică semnăturile
- ✅ Loghează rezultatele
- ✅ Verifică threshold (ex: 80%)
- ✅ Afișează WARNING dacă < threshold
- ❌ NU exclude clienți

**Exemplu log:**
```
🔐 Signature: ✓ Valid
🔐 Signature: ✗ Invalid - Hash mismatch
⚠️  Policy: WARN - Invalid signature detected but continuing

⚠️  WARNING: Only 50.0% signatures are valid (threshold: 80.0%)
⚠️  Consider investigating signature failures or switching to 'reject' policy
```

**Configurare:**
```yaml
SIGNATURE_POLICY: "warn"
MIN_VALID_SIGNATURES: "0.8"  # 80% threshold
```

---

### 🔴 REJECT - Strictă
**Când să folosești**: Production, date sensibile, compliance

**Ce face:**
- ✅ Verifică semnăturile
- ✅ Loghează rezultatele
- ✅ Exclude clienți cu semnături invalide
- ✅ Continuă doar cu clienți valizi

**Exemplu log:**
```
🔐 Signature: ✓ Valid
🔐 Signature: ✗ Invalid - Certificate expired
⚠️  Policy: REJECT - Client will be excluded from aggregation

🚫 Rejecting 1 client(s) due to invalid signatures
```

**Configurare:**
```yaml
SIGNATURE_POLICY: "reject"
MIN_VALID_SIGNATURES: "1.0"  # Nu e folosit (exclude automat)
```

---

## 🎯 Scenarii de Utilizare

### Scenario 1: Dezvoltare Nouă Feature
```yaml
# Vrei să testezi rapid fără blocaje
SIGNATURE_POLICY: "log"
MIN_VALID_SIGNATURES: "0.0"
```

### Scenario 2: Testing Înainte de Release
```yaml
# Vrei să vezi dacă apar probleme
SIGNATURE_POLICY: "warn"
MIN_VALID_SIGNATURES: "0.9"  # 90% threshold strict
```

### Scenario 3: Production cu Date Medicale
```yaml
# Zero toleranță pentru probleme
SIGNATURE_POLICY: "reject"
MIN_VALID_SIGNATURES: "1.0"
```

### Scenario 4: Debugging Probleme de Semnare
```yaml
# Vrei să vezi exact ce se întâmplă
SIGNATURE_POLICY: "log"
MIN_VALID_SIGNATURES: "0.0"

# Apoi verifică logurile:
docker compose logs central | grep "Signature"
```

---

## 🔧 Comenzi Utile

### Verifică politica curentă
```bash
docker compose exec central env | grep SIGNATURE
```

### Schimbă politica rapid
```bash
# Editează docker-compose.yml
vim docker-compose.yml

# Sau folosește scriptul
./scripts/test_policy_manual.sh warn 0.8

# Repornește
docker compose restart central
```

### Testează o politică
```bash
# Cleanup
./scripts/cleanup_all.sh

# Test
./scripts/test_one_policy.sh log
./scripts/test_one_policy.sh warn
./scripts/test_one_policy.sh reject
```

### Verifică logurile
```bash
# Vezi toate verificările de semnături
docker compose logs central | grep "Signature"

# Vezi acțiunile politicii
docker compose logs central | grep "Policy:"

# Vezi statisticile
docker compose logs central | grep "Signature Verification Stats" -A 5
```

---

## 🐛 Troubleshooting

### Problema: Toate semnăturile sunt invalide

**Cauze posibile:**
1. Certificate expirate
2. Certificate generate greșit
3. Clock skew între containere

**Soluție:**
```bash
# Regenerează certificatele
python3 scripts/generate_certificates.py

# Repornește serviciile
docker compose down -v
docker compose up -d

# Testează
./scripts/test_one_policy.sh log
```

### Problema: Politica REJECT blochează toți clienții

**Cauze posibile:**
1. Probleme cu certificatele
2. Probleme cu signing-ul pe client

**Soluție:**
```bash
# Schimbă temporar la LOG pentru debugging
./scripts/test_policy_manual.sh log 0.0

# Verifică logurile
docker compose logs node1-worker | grep "Signing"
docker compose logs node2-worker | grep "Signing"

# Vezi ce erori apar
docker compose logs central | grep "Invalid"
```

### Problema: WARNING constant cu politica WARN

**Cauze posibile:**
1. Threshold prea strict
2. Probleme intermitente cu semnarea

**Soluție:**
```bash
# Verifică procentul actual de semnături valide
docker compose logs central | grep "WARNING.*signatures"

# Ajustează threshold-ul
# În docker-compose.yml:
MIN_VALID_SIGNATURES: "0.7"  # Reduce de la 0.8 la 0.7

# Sau investighează cauza
docker compose logs central | grep "Signature.*Invalid" -A 2
```

---

## 📊 Monitorizare

### Metrici Importante

**1. Rata de succes a semnăturilor**
```bash
docker compose logs central | grep "Signature Verification Stats" -A 4
```

**2. Clienți excluși (REJECT policy)**
```bash
docker compose logs central | grep "Rejecting.*clients"
```

**3. Warnings (WARN policy)**
```bash
docker compose logs central | grep "WARNING.*signatures"
```

### Dashboard Metrics (viitor)
- Total signature verifications
- Success rate (%)
- Failed verifications
- Clients rejected
- Policy violations

---

## ✅ Best Practices

### 1. Development
- ✅ Folosește **LOG** policy
- ✅ Threshold scăzut (0.5)
- ✅ Monitorizează logurile
- ✅ Fix-uiește problemele înainte de staging

### 2. Staging
- ✅ Folosește **WARN** policy
- ✅ Threshold mediu-înalt (0.8-0.9)
- ✅ Monitorizează warnings
- ✅ Investighează orice WARNING

### 3. Production
- ✅ Folosește **REJECT** policy
- ✅ Threshold maxim (1.0)
- ✅ Alerting pentru clienți excluși
- ✅ Zero toleranță pentru probleme

### 4. Debugging
- ✅ Schimbă temporar la LOG
- ✅ Verifică logurile detaliate
- ✅ Fix-uiește problema
- ✅ Testează cu WARN
- ✅ Deploy cu REJECT

---

## 🔗 Resurse

### Documentație
- `SECURITY_IMPLEMENTATION_STATUS.md` - Status complet
- `SECURITY_POLICY_TEST_RESULTS.md` - Rezultate teste
- `SECURITY_TESTING_SUMMARY.md` - Rezumat teste

### Scripturi
- `scripts/cleanup_all.sh` - Cleanup complet
- `scripts/test_one_policy.sh` - Test o politică
- `scripts/test_all_policies.sh` - Test toate
- `scripts/test_policy_manual.sh` - Configurare manuală

### Cod
- `shared/python/node_core/node_core/flower_strategy.py` - Logica politicilor
- `services/central/app/flower_server.py` - Configurare server
- `docker-compose.yml` - Configurare environment

---

## 💡 Tips & Tricks

### Tip 1: Test rapid fără rebuild
```bash
# Schimbă politica fără rebuild
docker compose exec central bash -c "
  export SIGNATURE_POLICY=warn
  export MIN_VALID_SIGNATURES=0.8
  python -m app.flower_server
"
```

### Tip 2: Monitorizare în timp real
```bash
# Vezi verificările de semnături live
docker compose logs -f central | grep --line-buffered "Signature"
```

### Tip 3: Statistici rapide
```bash
# Număr total verificări
docker compose logs central | grep "Total verifications:" | tail -1

# Rata de succes
docker compose logs central | grep "Successful:" | tail -1
```

---

*Ghid generat: 27 aprilie 2026*  
*Versiune: 1.0*  
*Pentru suport: Vezi SECURITY_TESTING_SUMMARY.md*
