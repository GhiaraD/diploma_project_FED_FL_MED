# Rezumat sesiune — Articol științific Fed-Med-FL

## Context

Lucrare de disertație despre platforma **Fed-Med-FL** — platformă de Federated Learning pentru clasificarea radiografiilor toracice (NORMAL vs. PNEUMONIE). Articolul este în **limba română**, stil academic.

Lucrarea este dezvoltată de **două persoane**:
- **P2 (autorul acestei lucrări)** — Node API securitate, ML Core antrenare locală, Dataset Management, Model Registry, UI: Datasets, Models, Audit
- **P1 (coleg)** — Docker Infrastructure, Flower Server, Flower Strategy, Flower Client, Inferență, Node UI: Dashboard, Federated, Inference, Jobs, Redis/Celery din perspectiva FL, Resource Monitor

---

## Structura capitolelor

```
Capitolul 3 — Soluția propusă
  3.1 Cerințe identificate
      3.1.1 Cerințe funcționale
      3.1.2 Cerințe non-funcționale
  3.2 Cazuri de utilizare
      3.2.1 Admin spital
      3.2.2 Medic
      3.2.3 Admin central

Capitolul 4 — Proiectarea sistemului
  4.1 Tehnologii folosite
  4.2 Arhitectura sistemului
      4.2.1 Prezentare generală și componente
      4.2.2 Relațiile dintre componente
      4.2.3 Fluxul unei sesiuni FL
  4.3 Modelul de date
  4.4 Interfața API
      4.4.1 Autentificare și autorizare (tabel roluri)
      4.4.2 Endpoint-urile platformei (tabel endpoints)
  4.5 Interfața utilizator
      4.5.1 Pagina Datasets (2 figuri: pagina + dialog register)
      4.5.2 Pagina Models (1 figură)
      4.5.3 Pagina Audit (2 figuri: pagina + dialog detalii)

Capitolul 5 — Detalii de implementare
  5.1 Node API — Securitate
      5.1.1 Autentificare JWT și gestionarea sesiunilor
      5.1.2 Redis pentru securitate
      5.1.3 RBAC și autorizare granulară
      5.1.4 Audit logging
  5.2 ML Core — Antrenarea locală
      5.2.1 Arhitecturi de modele
      5.2.2 Pipeline-ul de antrenare
      5.2.3 Generarea hărților Grad-CAM
  5.3 Gestionarea dataset-urilor
  5.4 Registrul de modele
```

---

## Îmbunătățiri de cod presupuse ca implementate în articol (neimplementate în cod)

1. **Redenumire rol** `admin` → `admin_spital` în `security.py`, `auth.py`, `schemas.py`
2. **Eliminare rol** `viewer` din `permissions_map` și din `UserCreate`
3. **Adăugare rol** `admin_central` cu permisiunea exclusivă `write:federated`
4. **Autentificare pe Central API** (`services/central/app/main.py`) — momentan fără autentificare, necesită JWT similar cu Node API
5. **Endpoint-ul** `/api/federated/train` restricționat exclusiv la `admin_central`
6. **Flag consimțământ FL** pe nod — endpoint `POST /api/federated/participation` apelat din butonul toggle din pagina Federated, setabil doar de `admin_spital`; verificat la apelul `/api/federated/train`
7. **Calcul metrica F2** 
8. **Best model sa fie luat dupa F2** 

---

## Note importante

- Grad-CAM implementat **de la zero** în PyTorch, conform paperului Selvaraju et al. 2017 (`https://arxiv.org/abs/1610.02391`), fără biblioteci externe
- Cele 3 split-uri `train/val/test` sunt obligatorii la înregistrarea unui dataset; `train` pentru antrenare, `val` pentru validare per epocă, `test` pentru evaluare finală înainte de trimiterea la Flower
- Redis folosește 2 spații logice: indexul 0 pentru Celery, indexul 1 pentru securitate (sesiuni JWT active, blacklist, rate limiting)
- Central API nu are autentificare implementată momentan — presupunem că va fi adăugată
- Figuri necesare în Overleaf (de adăugat în `pics/`):
  - `pics/datasets_page.pdf` — pagina Datasets
  - `pics/datasets_register.pdf` — dialogul de înregistrare dataset
  - `pics/models_page.pdf` — pagina Models
  - `pics/audit_page.pdf` — pagina Audit
  - `pics/audit_details.pdf` — dialogul detalii eveniment audit
  - `pics/ArchitectureDiagram.pdf` — diagrama arhitecturală (deja existentă)

---

## Extrase de cod pentru Capitolul 5

Fiecare cod are un număr de placeholder folosit în LaTeX ca `<PLACEHOLDER COD X>`.

---

### COD 1 — Generarea token-ului JWT (`security.py`)

```python
def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    jti = str(uuid.uuid4())  # JWT ID unic pentru blacklisting
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": jti,
        "iss": f"fed-med-fl-{settings.NODE_ID}",
        "aud": "fed-med-fl-api"
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    # Stocăm sesiunea în Redis cu TTL egal cu durata token-ului
    if redis_client:
        session_data = {"user_id": data.get("sub"), "node_id": data.get("node_id")}
        redis_client.setex(f"session:{jti}", ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                           json.dumps(session_data))
    return encoded_jwt
```

**Caption LaTeX:** Generarea token-ului JWT cu claims standard și stocare sesiune în Redis

---

### COD 2 — Verificarea token-ului cu blacklist check (`security.py`)

```python
def verify_token(self, token: str) -> dict:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM],
                         options={"verify_aud": False})
    
    jti = payload.get("jti")
    if jti and redis_client and redis_client.get(f"blacklist:{jti}"):
        raise HTTPException(status_code=401, detail="Token has been revoked")
    
    return payload
```

**Caption LaTeX:** Verificarea token-ului JWT cu consultarea blacklist-ului Redis

---

### COD 3 — Revocarea token-ului la logout (`security.py`)

```python
def revoke_token(self, jti: str) -> bool:
    session_key = f"session:{jti}"
    session_data = redis_client.get(session_key)
    
    if session_data:
        ttl = redis_client.ttl(session_key)
        if ttl > 0:
            redis_client.setex(f"blacklist:{jti}", ttl, "revoked")
            redis_client.delete(session_key)
            return True
    return False
```

**Caption LaTeX:** Revocarea token-ului la logout — mecanismul blacklist cu TTL automat

---

### COD 4 — Configurarea conexiunilor Redis cu izolarea bazelor de date logice

```python
# DB 0 — broker Celery (definit în config.py)
REDIS_URL = "redis://node1-redis:6379/0"
CELERY_BROKER_URL = REDIS_URL

# DB 1 — securitate (definit în security.py)
redis_client = redis.Redis(
    host=getattr(settings, 'REDIS_HOST', 'node1-redis'),
    port=getattr(settings, 'REDIS_PORT', 6379),
    db=1,  # Use DB 1 for security (DB 0 is for Celery)
    decode_responses=True
)
```

**Caption LaTeX:** Configurarea conexiunilor Redis cu izolarea bazelor de date logice

---

### COD 5 — Rate limiting cu Redis pipeline (`security.py`)

```python
def check_rate_limit(self, user_id: str, role: str, endpoint: str = None) -> tuple[bool, dict]:
    current_time = datetime.utcnow()
    minute_key = current_time.strftime("%Y-%m-%d-%H-%M")
    
    # Cheie per utilizator per minut
    general_key = f"rate_limit:user:{user_id}:{minute_key}"
    general_limit = self.rate_limits.get(role, 30)
    
    current_general = redis_client.get(general_key)
    if current_general and int(current_general) >= general_limit:
        return False, {"limit_type": "general", "limit": general_limit}
    
    # Cheie per endpoint per minut (pentru endpoint-uri sensibile)
    endpoint_key = f"rate_limit:endpoint:{user_id}:{endpoint}:{minute_key}"
    endpoint_limit = self.endpoint_limits.get(endpoint)
    if endpoint_limit:
        current_endpoint = redis_client.get(endpoint_key)
        if current_endpoint and int(current_endpoint) >= endpoint_limit:
            return False, {"limit_type": "endpoint", "limit": endpoint_limit}
    
    # Incrementare atomică cu pipeline
    pipe = redis_client.pipeline()
    pipe.incr(general_key)
    pipe.expire(general_key, 60)
    if endpoint_limit:
        pipe.incr(endpoint_key)
        pipe.expire(endpoint_key, 60)
    pipe.execute()
    
    return True, {}
```

**Caption LaTeX:** Implementarea rate limiting-ului cu Redis pipeline și fereastră per minut

---

### COD 6 — Permission map și verificarea permisiunilor (`security.py`)

```python
self.permissions_map = {
    "admin": ["*"],  # Full access
    "doctor": [
        "read:models", "write:models", "write:inference", "read:inference",
        "read:datasets", "read:jobs", "read:inference_history"
    ],
    "viewer": [
        "read:models", "read:inference",
        "read:inference_history", "read:jobs"
    ]
}

def has_permission(self, user_permissions: List[str], required_permission: str) -> bool:
    if "*" in user_permissions:
        return True
    if required_permission in user_permissions:
        return True
    # Suport wildcard: "read:*" acoperă "read:models", "read:datasets" etc.
    for perm in user_permissions:
        if perm.endswith(":*"):
            prefix = perm[:-1]
            if required_permission.startswith(prefix):
                return True
    return False
```

**Caption LaTeX:** Harta de permisiuni per rol și algoritmul de verificare cu suport wildcard

---

### COD 7 — Dependency factories FastAPI (`security.py`)

```python
def require_permission(permission: str):
    def permission_checker(
        current_user: dict = Depends(get_current_user)
    ) -> dict:
        if not security_manager.has_permission(
            current_user["permissions"], permission
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {permission}"
            )
        return current_user
    return permission_checker

def require_role(role: str):
    def role_checker(
        current_user: dict = Depends(get_current_user)
    ) -> dict:
        if current_user["role"] != role and current_user["role"] != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient role. Required: {role}"
            )
        return current_user
    return role_checker
```

**Caption LaTeX:** Funcțiile factory `require_permission` și `require_role` ca dependențe FastAPI

---

### COD 8 — Utilizarea dependențelor de autorizare în endpoint-uri (`main.py`)

```python
@app.post("/api/federated/train", response_model=JobCreateResponse)
async def start_federated_training(
    dataset_id: str,
    current_user: dict = Depends(require_permission("write:federated")),
    db: Session = Depends(get_db)
):
    ...

@app.get("/api/auth/audit-logs")
async def get_audit_logs(
    current_user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    ...
```

**Caption LaTeX:** Utilizarea dependențelor de autorizare în definițiile endpoint-urilor

---

### COD 9 — Nucleul `log_audit_event` (`security.py`)

```python
async def log_audit_event(self, event_type: str, user_id: str, request: Request,
                           additional_data: dict = None, db: Session = None,
                           response_status: int = None, start_time: float = None):
    duration_ms = int((time.time() - start_time) * 1000) if start_time else None

    request_body = None
    try:
        body_bytes = await request.body()
        if body_bytes:
            request_body = json.loads(body_bytes.decode('utf-8'))
    except Exception:
        pass

    enhanced_details = {
        **(additional_data or {}),
        "request_details": {
            "method": request.method,
            "url": str(request.url),
            "query_params": dict(request.query_params),
            "request_body": request_body,
            "headers": {
                "user-agent": request.headers.get("user-agent"),
                "content-type": request.headers.get("content-type"),
            }
        }
    }

    audit_log = AuditLog(
        timestamp=datetime.utcnow(),
        event_type=event_type,
        user_id=user_id,
        node_id=settings.NODE_ID,
        endpoint=f"{request.method} {request.url.path}",
        ip_address=request.client.host if request.client else None,
        response_status=response_status,
        duration_ms=duration_ms,
        details=json.dumps(enhanced_details)
    )
    db.add(audit_log)
    db.commit()
```

**Caption LaTeX:** Implementarea nucleului de audit logging cu captarea completă a contextului HTTP

---

### COD 10 — Helper function audit pentru dataset-uri (`audit_helper.py`)

```python
async def log_dataset_action(
    action: str, user_id: str, request: Request, db: Session,
    dataset_id: str = None, dataset_name: str = None,
    details: dict = None, response_status: int = 200,
    start_time: float = None
):
    event_data = {
        "action": action,
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        **(details or {})
    }
    await security_manager.log_audit_event(
        event_type=f"dataset_{action}",
        user_id=user_id,
        request=request,
        additional_data=event_data,
        db=db,
        response_status=response_status,
        start_time=start_time
    )

# Utilizare în endpoint:
await log_dataset_action(
    action="registered",
    user_id=current_user["id"],
    request=request,
    db=db,
    dataset_id=dataset_id,
    dataset_name=request_data.name,
    details={"num_samples": num_samples},
    response_status=200,
    start_time=start_time
)
```

**Caption LaTeX:** Helper function de audit pentru dataset-uri și utilizarea sa în endpoint

---

### COD 11 — Validarea structurii dataset-ului (`main.py`)

```python
# Validare structură: train/val/test × NORMAL/PNEUMONIA
for split in ("train", "val", "test"):
    for cls in ("NORMAL", "PNEUMONIA"):
        cls_path = os.path.join(request_data.path, split, cls)
        if not os.path.exists(cls_path):
            raise HTTPException(
                status_code=400,
                detail=f"Dataset must contain {split}/{cls} folder at {cls_path}"
            )

# Numărare sample-uri prin toate split-urile
num_normal = 0
num_pneumonia = 0
for split in ("train", "val", "test"):
    n_path = os.path.join(request_data.path, split, "NORMAL")
    p_path = os.path.join(request_data.path, split, "PNEUMONIA")
    num_normal += len([f for f in os.listdir(n_path)
                       if os.path.isfile(os.path.join(n_path, f))])
    num_pneumonia += len([f for f in os.listdir(p_path)
                          if os.path.isfile(os.path.join(p_path, f))])
```

**Caption LaTeX:** Validarea structurii dataset-ului și numărarea distribuției claselor

---

### COD 12 — Activarea exclusivă a unui dataset (`main.py`)

```python
@app.post("/api/data/set-active/{dataset_id}")
async def set_active_dataset(dataset_id: str, ...):
    dataset = db.query(Dataset).filter(Dataset.dataset_id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Dezactivare globală — garantează că exact un dataset e activ
    db.query(Dataset).update({"is_active": False})
    
    # Activare selectivă
    dataset.is_active = True
    db.commit()
```

**Caption LaTeX:** Mecanismul de activare exclusivă prin dezactivare globală urmată de activare selectivă

---

### COD 13 — `compute_model_labels()` (`main.py`)

```python
def compute_model_labels(models_list, db: Session):
    # Identifică modelul deployed
    deployed_model_id = None
    for m in models_list:
        if m.type == "deployed":
            deployed_model_id = m.model_id
            break
    
    # Identifică modelul cu cea mai bună acuratețe
    best_model_id = None
    best_accuracy = -1
    for m in models_list:
        if m.metrics and "accuracy" in m.metrics:
            if m.metrics["accuracy"] > best_accuracy:
                best_accuracy = m.metrics["accuracy"]
                best_model_id = m.model_id
    
    # Atribuie etichete
    for m in models_list:
        labels = []
        if m.model_id == deployed_model_id:
            labels.append("active")
        if m.model_id == best_model_id:
            labels.append("global")
        if not labels:
            labels.append("candidate")
        
        if m.labels != labels:
            m.labels = labels
    
    db.commit()
    return models_list
```

**Caption LaTeX:** Algoritmul de calcul dinamic al etichetelor modelelor

---

### COD 14 — Promovarea modelului cu mutarea fișierelor (`main.py`)

```python
async def promote_model(request_data: ModelPromoteRequest, ...):
    # Demotează modelul curent deployed
    current_deployed = db.query(Model).filter(Model.type == "deployed").first()
    if current_deployed:
        current_deployed.type = "candidate"
        new_path = old_path.replace("/deployed/", "/candidate/")
        if os.path.exists(old_path):
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            shutil.move(old_path, new_path)
        current_deployed.file_path = new_path
    
    # Promovează modelul selectat
    model_to_promote.type = "deployed"
    model_to_promote.promoted_at = datetime.utcnow()
    new_path = old_path.replace("/candidate/", "/deployed/")
    if os.path.exists(old_path):
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        shutil.move(old_path, new_path)
    model_to_promote.file_path = new_path
    
    db.commit()
    
    # Recalculează etichetele pentru toți modelii
    all_models = db.query(Model).all()
    compute_model_labels(all_models, db)
```

**Caption LaTeX:** Fluxul de promovare a unui model cu mutarea fișierelor pe disc

---

### COD 15 — `get_model()` — adaptarea arhitecturilor pretrained (`ml_models.py`)

```python
def get_model(model_name: str, num_classes: int = 2, pretrained: bool = True) -> nn.Module:
    if model_name == "resnet18":
        weights = ResNet18_Weights.IMAGENET1K_V1 if pretrained else None
        model = resnet18(weights=weights)
        in_features = model.fc.in_features          # 512
        model.fc = nn.Linear(in_features, num_classes)

    elif model_name == "densenet121":
        weights = DenseNet121_Weights.IMAGENET1K_V1 if pretrained else None
        model = densenet121(weights=weights)
        in_features = model.classifier.in_features  # 1024
        model.classifier = nn.Linear(in_features, num_classes)

    elif model_name == "efficientnet_b0":
        weights = EfficientNet_B0_Weights.IMAGENET1K_V1 if pretrained else None
        model = efficientnet_b0(weights=weights)
        in_features = model.classifier[1].in_features  # 1280
        model.classifier[1] = nn.Linear(in_features, num_classes)

    return model
```

**Caption LaTeX:** Adaptarea celor trei arhitecturi pretrained pentru clasificare binară

---

### COD 16 — Bucla de antrenare cu best model checkpoint (`ml_training.py`)

```python
def train_model(model, train_loader, val_loader, criterion, optimizer,
                device, num_epochs=10, scheduler=None, early_stopping=None):
    history = {
        'train_loss': [], 'train_acc': [],
        'val_loss': [], 'val_acc': [], 'epochs_trained': 0
    }
    best_val_acc = 0.0
    best_model_state = None

    for epoch in range(num_epochs):
        train_loss, train_acc = train_epoch(
            model, train_loader, criterion, optimizer, device, scheduler
        )
        val_loss, val_acc, _, _ = validate(model, val_loader, criterion, device)

        history['train_loss'].append(train_loss)
        history['val_loss'].append(val_loss)
        history['epochs_trained'] = epoch + 1

        # Salvare best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_model_state = model.state_dict().copy()

        # Early stopping
        if early_stopping is not None and early_stopping(val_acc):
            break

    # Restaurare weights din epoca cu best val accuracy
    if best_model_state is not None:
        model.load_state_dict(best_model_state)

    history['best_val_acc'] = best_val_acc
    return history
```

**Caption LaTeX:** Bucla de antrenare cu validare per epocă, best model checkpoint și early stopping

---

### COD 17 — Clasa `EarlyStopping` (`ml_training.py`)

```python
class EarlyStopping:
    def __init__(self, patience: int = 5, min_delta: float = 0.0, mode: str = 'max'):
        self.patience = patience
        self.min_delta = min_delta
        self.mode = mode
        self.counter = 0
        self.best_score = None

    def __call__(self, score: float) -> bool:
        if self.best_score is None:
            self.best_score = score
            return False

        if self.mode == 'max':
            improved = score > (self.best_score + self.min_delta)
        else:
            improved = score < (self.best_score - self.min_delta)

        if improved:
            self.best_score = score
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                return True  # Stop training
        return False
```

**Caption LaTeX:** Implementarea mecanismului de early stopping cu patience configurabil

---

### COD 18 — Implementarea Grad-CAM cu hooks PyTorch (`ml_inference.py`)

```python
class GradCAM:
    def __init__(self, model: nn.Module, target_layer: nn.Module):
        self.model = model
        self.target_layer = target_layer
        self.gradients = None
        self.activations = None
        
        # Înregistrare hooks pentru capturarea activărilor și gradienților
        self.forward_hook = target_layer.register_forward_hook(self._forward_hook)
        self.backward_hook = target_layer.register_full_backward_hook(self._backward_hook)
    
    def _forward_hook(self, module, input, output):
        self.activations = output.detach()  # Hărțile de activare

    def _backward_hook(self, module, grad_input, grad_output):
        self.gradients = grad_output[0].detach()  # Gradienții față de clasă

    def generate(self, input_tensor, target_class=None, device='cpu'):
        self.model.eval()
        input_batch = input_tensor.unsqueeze(0).to(device)
        
        # Forward pass
        output = self.model(input_batch)
        if target_class is None:
            target_class = output.argmax(dim=1).item()
        
        # Backward pass pentru clasa țintă
        self.model.zero_grad()
        output[0, target_class].backward()
        
        # Global Average Pooling pe gradienți → ponderi per canal
        weights = self.gradients.mean(dim=(2, 3), keepdim=True)
        
        # Combinare ponderată a hărților de activare
        cam = (weights * self.activations).sum(dim=1).squeeze()
        cam = F.relu(cam)  # Doar contribuții pozitive
        
        # Normalizare la [0, 1]
        cam = cam.cpu().numpy()
        cam = (cam - cam.min()) / (cam.max() + 1e-8)
        
        return cam, target_class
```

**Caption LaTeX:** Implementarea Grad-CAM cu hooks PyTorch pentru capturarea activărilor și gradienților

---

## Referințe bibliografice importante

- Grad-CAM paper: Selvaraju et al., https://arxiv.org/abs/1610.02391
- BibTeX key: `gradcam2017` — folosit în text ca `\cite{gradcam2017}`

```bibtex
@article{selvaraju2017gradcam,
  title={Grad-CAM: Visual Explanations from Deep Networks via Gradient-based Localization},
  author={Selvaraju, Ramprasaath R and Cogswell, Michael and Das, Abhishek and Vedantam, Ramakrishna and Parikh, Devi and Batra, Dhruv},
  journal={International Journal of Computer Vision},
  volume={128},
  pages={336--359},
  year={2020},
  publisher={Springer}
}
```
