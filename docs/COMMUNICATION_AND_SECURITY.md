# Comunicare și Securitate — Fed-Med-FL

**Data**: Mai 2026  
**Scop**: Documentează protocoalele de comunicare și mecanismele de securitate între toate componentele sistemului.

---

## Arhitectura de comunicare

Sistemul are **două canale de comunicare distincte**, cu protocoale și securitate diferite:

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   Browser / Script                                              │
│        │                                                        │
│        │ HTTPS (REST)                                           │
│        ▼                                                        │
│   Node API (FastAPI)  ◄──── JWT / API Key ────────────────────  │
│        │                                                        │
│        │ Celery (Redis)                                         │
│        ▼                                                        │
│   Node Worker ──────────────────────────────────────────────── │
│        │                                                        │
│        │ gRPC + mTLS                                            │
│        ▼                                                        │
│   Flower Server (Central) ◄──── gRPC + mTLS ──────────────────  │
│                                                                 │
│   Central API (FastAPI) ◄──── HTTP (intern) ──────────────────  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Canal 1: Flower Server ↔ Flower Client (FL Training)

### Protocol: gRPC

Comunicarea pentru federated learning folosește **gRPC** (Google Remote Procedure Call), un protocol binar bazat pe HTTP/2 și Protocol Buffers.

**De ce gRPC și nu REST?**
- Binar (mai eficient decât JSON pentru transferul parametrilor modelului — zeci de MB per rundă)
- Streaming bidirecțional — serverul poate trimite parametri și primi update-uri în același timp
- Tipizare strictă prin Protocol Buffers
- Suport nativ în Flower framework

**Port**: `8080` (central container)

**Flux per rundă FL:**
```
Flower Server                          Flower Client (Node Worker)
     │                                          │
     │──── FitIns (parametri globali + config) ─►│
     │     {parameters, num_epochs, lr, ...}     │
     │                                          │ train_model()
     │◄─── FitRes (parametri actualizați) ──────│
     │     {parameters, num_samples, metrics}   │
     │                                          │
     │──── EvaluateIns (parametri) ────────────►│
     │◄─── EvaluateRes (loss, metrics) ─────────│
```

### Securitate: mTLS (Mutual TLS)

**mTLS** înseamnă că **ambele** părți (server și client) se autentifică reciproc cu certificate X.509.

**Configurare în cod:**

```python
# flower_server.py — server prezintă certificatul său
ssl_config = (
    ca_cert_bytes,      # CA pentru verificarea clientului
    server_cert_bytes,  # Certificatul serverului
    server_key_bytes,   # Cheia privată a serverului
)
fl.server.start_server(certificates=ssl_config, ...)

# flower_client.py — clientul verifică serverul cu CA
fl.client.start_numpy_client(
    root_certificates=ca_cert_bytes,  # CA pentru verificarea serverului
    ...
)
```

**Structura PKI (Public Key Infrastructure):**
```
Fed-Med-FL Root CA (10 ani)
├── central/
│   ├── server-cert.pem + server-key.pem   (TLS server)
│   ├── client-cert.pem + client-key.pem   (mTLS client)
│   └── signing-cert.pem + signing-key.pem (payload signing)
└── nodes/
    ├── node1/
    │   ├── server-cert.pem + server-key.pem
    │   ├── client-cert.pem + client-key.pem
    │   └── signing-cert.pem + signing-key.pem
    ├── node2/ ... (identic)
    └── node3/ ... (identic)
```

**Algoritmi:**
- Chei RSA 4096-bit
- Semnătură certificat: SHA-256
- TLS: 1.2+ (enforced de gRPC)

### Securitate suplimentară: Payload Signing

Pe lângă mTLS (care securizează canalul de transport), parametrii modelului sunt **semnați digital** înainte de a fi trimiși.

**De ce?** mTLS garantează că nimeni nu poate intercepta sau modifica datele în tranzit. Payload signing garantează că parametrii vin de la nodul legitim și nu au fost alterați nici înainte de trimitere.

**Algoritm: RSA-PSS cu SHA-256**

```python
# crypto_utils.py — semnare pe client
signature = private_key.sign(
    payload_bytes,          # JSON cu hash-ul parametrilor
    padding.PSS(
        mgf=padding.MGF1(hashes.SHA256()),
        salt_length=padding.PSS.MAX_LENGTH
    ),
    hashes.SHA256()
)
```

**Fluxul de semnare:**
```
Node Worker (fit())
    1. Calculează SHA-256 hash al tuturor parametrilor modelului
    2. Creează payload JSON: {parameters_hash, shapes, metadata}
    3. Semnează payload cu signing-key.pem (RSA-PSS)
    4. Atașează semnătura + certificatul în metrics dict
    5. Trimite parametrii + semnătura la server

Flower Server (aggregate_fit())
    1. Primește parametrii + semnătura de la fiecare client
    2. Extrage certificatul din pachetul de semnătură
    3. Verifică că certificatul e semnat de Root CA
    4. Verifică semnătura RSA-PSS
    5. Recalculează hash-ul parametrilor și compară
    6. Aplică politica configurată (log/warn/reject)
```

**Politici de semnătură** (configurabile în `docker-compose.yml`):

| Politică | Comportament |
|----------|-------------|
| `log` | Loghează semnăturile invalide, continuă agregarea |
| `warn` | Avertizează dacă sub X% semnături sunt valide |
| `reject` | Exclude clienții cu semnături invalide din agregare |

**Cache de verificare**: Rezultatele verificărilor sunt cached în `SignatureCache` pentru a evita re-verificarea acelorași semnături în runde consecutive.

---

## Canal 2: Node API ↔ Central API (Management)

### Protocol: HTTP REST

Comunicarea de management (nu FL) folosește **HTTP REST** cu JSON.

**Endpoint-uri relevante:**
- `GET http://central:8081/health` — health check
- `POST http://central:8081/api/fl/start` — pornire Flower Server

**Port**: `8081` (central container)

**Notă**: HTTPS este implementat în cod (`fastapi_ssl.py`) dar **dezactivat** în configurația curentă (`ENABLE_SSL: "false"`) pentru compatibilitate cu UI-ul. Poate fi activat în producție.

---

## Canal 3: Browser / Client ↔ Node API (User Interface)

### Protocol: HTTP REST (cu CORS)

UI-ul Next.js și scripturile externe comunică cu Node API prin HTTP REST.

**Port-uri**: `8001` (node1), `8002` (node2), `8003` (node3)

**CORS**: Configurat să accepte request-uri de la `localhost:3001-3003`.

### Securitate: JWT (JSON Web Tokens)

**Algoritm**: HS256 (HMAC-SHA256)  
**Expirare**: 24 ore (configurabil prin `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`)  
**Secret**: `JWT_SECRET_KEY` din environment

**Structura token-ului:**
```json
{
  "sub": "user_id",
  "email": "admin@node1.fed-med-fl.com",
  "role": "admin",
  "node_id": "node1",
  "permissions": ["*"],
  "exp": 1234567890,
  "iat": 1234567890,
  "jti": "uuid-for-blacklisting",
  "iss": "fed-med-fl-node1",
  "aud": "fed-med-fl-api"
}
```

**Blacklisting**: Token-urile revocate (logout) sunt stocate în Redis cu TTL egal cu timpul rămas până la expirare. La fiecare request se verifică dacă `jti` e în blacklist.

**Flux de autentificare:**
```
Client                          Node API                    Redis
  │                                │                          │
  │── POST /api/auth/login ────────►│                          │
  │   {username, password}         │                          │
  │                                │── verify bcrypt hash     │
  │                                │── create JWT             │
  │                                │── store session ─────────►│
  │◄── {access_token, ...} ────────│                          │
  │                                │                          │
  │── GET /api/models/registry ────►│                          │
  │   Authorization: Bearer <jwt>  │                          │
  │                                │── verify JWT signature   │
  │                                │── check blacklist ───────►│
  │                                │── check permissions      │
  │◄── {models: [...]} ────────────│                          │
```

### RBAC (Role-Based Access Control)

Patru roluri cu permisiuni diferite:

| Rol | Permisiuni |
|-----|-----------|
| `admin` | `*` (acces complet) |
| `doctor` | `read:models`, `write:inference`, `read:datasets`, `read:jobs`, `read:inference_history` |
| `researcher` | `read:models`, `write:training`, `write:federated`, `read:datasets`, `write:datasets`, `read:jobs` |
| `viewer` | `read:models`, `read:datasets`, `read:jobs`, `read:inference_history` |

### Rate Limiting

Implementat cu Redis, per utilizator per minut:

| Rol | Limită generală | Endpoint specific |
|-----|----------------|-------------------|
| `admin` | 1000 req/min | — |
| `doctor` | 100 req/min | inference: 10/min |
| `researcher` | 50 req/min | training: 2/oră |
| `viewer` | 30 req/min | — |
| `api_key` | 500 req/min | federated/train: 1/10min |

### Securitate suplimentară: Account Lockout

- 5 încercări eșuate de login → cont blocat 30 minute
- Resetare automată la login reușit

### API Keys (comunicare inter-nod)

Pentru comunicarea automată între noduri (fără utilizator uman), se folosesc API keys în loc de JWT:

```
Header: X-API-Key: fed_med_fl_node1_<random_token>
```

Stocate ca SHA-256 hash în baza de date. Expiră după 10 ani (configurabil).

---

## Canal 4: Node API ↔ Node Worker (Task Queue)

### Protocol: Celery + Redis

Comunicarea internă între API și Worker folosește **Celery** cu **Redis** ca message broker.

**Nu există securitate de rețea** pe acest canal — Redis rulează în rețeaua internă Docker, inaccesibil din exterior (portul Redis este expus doar pentru debugging local).

**Flux:**
```
Node API                    Redis (broker)              Node Worker
   │                             │                           │
   │── task.delay(params) ───────►│                           │
   │                             │── task message ───────────►│
   │                             │                           │ execută
   │◄── AsyncResult(task_id) ────│                           │
   │                             │◄── result ────────────────│
```

---

## Audit Logging

Toate acțiunile semnificative sunt logate în tabela `audit_logs` din SQLite:

**Evenimente logate:**
- `login_success`, `login_failed`, `login_blocked`
- `logout`
- `password_changed`
- `user_created`, `user_deactivated`
- `api_key_created`, `api_key_revoked`
- `dataset_registered`, `dataset_activated`, `dataset_deleted`
- `model_promoted`
- `training_started`
- `inference_started`, `inference_completed`, `results_viewed`
- `federated_training_started`
- `job_viewed`

**Informații capturate per eveniment:**
- Timestamp
- Tip eveniment
- User ID
- Node ID
- Endpoint (method + path)
- IP address
- User agent
- Status HTTP răspuns
- Durată (ms)
- Detalii suplimentare (JSON)

---

## Rezumat comparativ

| Canal | Protocol | Securitate transport | Autentificare | Autorizare |
|-------|----------|---------------------|---------------|------------|
| Flower Server ↔ Client | gRPC | mTLS (TLS 1.2+, RSA 4096) | Certificate X.509 mutual | Payload signing RSA-PSS |
| Node API ↔ Central API | HTTP REST | Plaintext (HTTPS disponibil) | — | — |
| Browser ↔ Node API | HTTP REST | Plaintext (HTTPS disponibil) | JWT HS256 | RBAC + Rate limiting |
| Node API ↔ Worker | Celery/Redis | Rețea internă Docker | — | — |

---

## Configurare în docker-compose.yml

```yaml
# Flower gRPC mTLS
FLOWER_ENABLE_SSL: "true"       # activează mTLS pe Flower
CERTIFICATES_PATH: /certificates

# Payload signing
SIGNATURE_POLICY: "log"         # log / warn / reject
MIN_VALID_SIGNATURES: "0.8"     # 80% minim

# Node API JWT
JWT_SECRET_KEY: <secret>
JWT_ACCESS_TOKEN_EXPIRE_MINUTES: 1440

# Node API SSL (dezactivat momentan)
ENABLE_SSL: "false"
```

---

*Document generat: Mai 2026*  
*Fișiere analizate: `flower_server.py`, `flower_client.py`, `flower_strategy.py`, `crypto_utils.py`, `security.py`, `auth.py`, `docker-compose.yml`*
