# 🔒 Differential Privacy - Implementation Guide

**Ghid complet pentru implementarea Differential Privacy în Fed-Med-FL**

---

## 📚 Table of Contents

1. [Ce este Differential Privacy?](#ce-este-differential-privacy)
2. [De ce avem nevoie de DP?](#de-ce-avem-nevoie-de-dp)
3. [Arhitectura DP în Fed-Med-FL](#arhitectura-dp)
4. [Modificări Necesare](#modificări-necesare)
5. [Implementation Step-by-Step](#implementation-step-by-step)
6. [Testing & Validation](#testing--validation)
7. [Trade-offs & Tuning](#trade-offs--tuning)

---

## 🎯 Ce este Differential Privacy?

**Differential Privacy (DP)** oferă garanții matematice formale că participarea unui individ într-un dataset nu poate fi detectată din rezultatele algoritmului.

### Definiție Formală

Un algoritm M satisface **(ε, δ)-differential privacy** dacă pentru orice două dataset-uri D₁ și D₂ care diferă prin exact un record:

```
Pr[M(D₁) ∈ S] ≤ e^ε × Pr[M(D₂) ∈ S] + δ
```

Unde:
- **ε (epsilon)**: Privacy budget - cât de mult "privacy" pierdem
  - ε mic (0.1-1.0) = privacy înalt, accuracy scăzut
  - ε mare (>10) = privacy scăzut, accuracy înalt
- **δ (delta)**: Probabilitate de failure (de obicei 10⁻⁵ sau 10⁻⁶)

### Cum Funcționează?

**Adăugăm zgomot calibrat** la:
1. **Gradienți** (client-side) - înainte de a-i trimite la server
2. **Parametri agregați** (server-side) - după agregare

Zgomotul este **Gaussian** sau **Laplacian**, calibrat astfel încât să garanteze (ε, δ)-DP.

---

## 🏥 De ce avem nevoie de DP?

### 1. Compliance Legal
- **GDPR** (EU) - Articolul 25: "Privacy by Design"
- **HIPAA** (US) - Protecție date medicale
- **CCPA** (California) - Drepturi privacy consumatori

### 2. Protecție Împotriva Atacurilor

**Membership Inference Attack:**
```
Atacator: "Pacientul X este în dataset-ul Node1?"
Fără DP: Poate deduce cu 80-90% acuratețe
Cu DP: Maxim 50% + ε (aproape random guessing)
```

**Model Inversion Attack:**
```
Atacator: "Cum arată datele pacientului X?"
Fără DP: Poate reconstrui parțial datele
Cu DP: Reconstrucție imposibilă (zgomot >> signal)
```

### 3. Trust & Adoption
- Spitale/Clinici sunt mai dispuse să participe
- Pacienți au mai multă încredere
- Publicare rezultate fără risc

---

## 🏗️ Arhitectura DP în Fed-Med-FL

### Două Niveluri de Protecție

```
┌─────────────────────────────────────────────────────────────┐
│                    FEDERATED LEARNING                        │
│                                                              │
│  ┌──────────┐         ┌──────────┐         ┌──────────┐   │
│  │  Node 1  │         │  Node 2  │         │  Node 3  │   │
│  │          │         │          │         │          │   │
│  │ Training │         │ Training │         │ Training │   │
│  │    ↓     │         │    ↓     │         │    ↓     │   │
│  │ DP-SGD   │◄────────┤ DP-SGD   │────────►│ DP-SGD   │   │
│  │ (Opacus) │         │ (Opacus) │         │ (Opacus) │   │
│  │    ↓     │         │    ↓     │         │    ↓     │   │
│  │ Gradient │         │ Gradient │         │ Gradient │   │
│  │ Clipping │         │ Clipping │         │ Clipping │   │
│  │    ↓     │         │    ↓     │         │    ↓     │   │
│  │  + Noise │         │  + Noise │         │  + Noise │   │
│  └────┬─────┘         └────┬─────┘         └────┬─────┘   │
│       │                    │                    │          │
│       └────────────────────┼────────────────────┘          │
│                            ↓                                │
│                   ┌─────────────────┐                       │
│                   │  Central Server │                       │
│                   │                 │                       │
│                   │   Aggregation   │                       │
│                   │        ↓        │                       │
│                   │   + DP Noise    │ ◄─── Server-side DP  │
│                   │        ↓        │                       │
│                   │  Global Model   │                       │
│                   └─────────────────┘                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘

CLIENT-SIDE DP (Opacus):
  • Gradient clipping per sample
  • Gaussian noise addition
  • Privacy accounting per client

SERVER-SIDE DP (Optional):
  • Additional noise on aggregated parameters
  • Global privacy budget tracking
  • Adaptive noise scaling
```

---

## 🔧 Modificări Necesare

### 1. Dependencies (requirements.txt)

**Fișier:** `shared/python/node_core/requirements.txt`

```python
# Existing dependencies
torch>=2.0.0
flwr>=1.8.0
cryptography>=41.0.0

# NEW: Differential Privacy
opacus>=1.4.0           # PyTorch DP library
dp-accounting>=0.4.0    # Privacy accounting
```

---

### 2. Client-Side: Flower Client cu Opacus

**Fișier:** `services/node/worker/app/flower_client.py`

**Modificări necesare:**

#### A. Import Opacus
```python
# La început de fișier, adaugă:
from opacus import PrivacyEngine
from opacus.validators import ModuleValidator
from opacus.utils.batch_memory_manager import BatchMemoryManager
```

#### B. Configurare DP în `__init__`
```python
class FedMedFlowerClient(fl.client.NumPyClient):
    def __init__(
        self,
        model,
        train_loader,
        val_loader,
        device,
        node_id,
        # NEW: DP parameters
        enable_dp: bool = False,
        dp_target_epsilon: float = 1.0,
        dp_target_delta: float = 1e-5,
        dp_noise_multiplier: float = 1.0,
        dp_max_grad_norm: float = 1.0,
        dp_max_epochs: int = 10,
        **kwargs
    ):
        self.model = model
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.device = device
        self.node_id = node_id
        
        # NEW: DP configuration
        self.enable_dp = enable_dp
        self.dp_target_epsilon = dp_target_epsilon
        self.dp_target_delta = dp_target_delta
        self.dp_noise_multiplier = dp_noise_multiplier
        self.dp_max_grad_norm = dp_max_grad_norm
        self.dp_max_epochs = dp_max_epochs
        self.privacy_engine = None
        
        # Initialize DP if enabled
        if self.enable_dp:
            self._initialize_dp()
```

#### C. Funcție de Inițializare DP
```python
def _initialize_dp(self):
    """Initialize Differential Privacy with Opacus."""
    print(f"[{self.node_id}] 🔒 Initializing Differential Privacy...")
    
    # Validate model is compatible with Opacus
    errors = ModuleValidator.validate(self.model, strict=False)
    if errors:
        print(f"[{self.node_id}] ⚠️  Model has compatibility issues:")
        for error in errors:
            print(f"  - {error}")
        
        # Try to fix automatically
        self.model = ModuleValidator.fix(self.model)
        print(f"[{self.node_id}] ✓ Model fixed for DP compatibility")
    
    print(f"[{self.node_id}] DP Configuration:")
    print(f"  • Target ε: {self.dp_target_epsilon}")
    print(f"  • Target δ: {self.dp_target_delta}")
    print(f"  • Noise multiplier: {self.dp_noise_multiplier}")
    print(f"  • Max grad norm: {self.dp_max_grad_norm}")
    print(f"  • Max epochs: {self.dp_max_epochs}")
```

#### D. Modificare `fit()` pentru DP
```python
def fit(self, parameters, config):
    """Train model with Differential Privacy."""
    
    # Set parameters
    self.set_parameters(parameters)
    
    # Get hyperparameters
    num_epochs = config.get("num_epochs", 5)
    learning_rate = config.get("learning_rate", 0.001)
    
    # Setup optimizer
    optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
    criterion = nn.CrossEntropyLoss()
    
    # NEW: Setup DP if enabled
    if self.enable_dp:
        privacy_engine = PrivacyEngine()
        
        self.model, optimizer, train_loader = privacy_engine.make_private(
            module=self.model,
            optimizer=optimizer,
            data_loader=self.train_loader,
            noise_multiplier=self.dp_noise_multiplier,
            max_grad_norm=self.dp_max_grad_norm,
        )
        
        print(f"[{self.node_id}] 🔒 DP-SGD enabled")
    else:
        train_loader = self.train_loader
    
    # Training loop
    self.model.train()
    total_loss = 0.0
    
    for epoch in range(num_epochs):
        epoch_loss = 0.0
        
        # NEW: Use BatchMemoryManager for DP
        if self.enable_dp:
            with BatchMemoryManager(
                data_loader=train_loader,
                max_physical_batch_size=32,
                optimizer=optimizer
            ) as memory_safe_loader:
                for batch_idx, (data, target) in enumerate(memory_safe_loader):
                    data, target = data.to(self.device), target.to(self.device)
                    
                    optimizer.zero_grad()
                    output = self.model(data)
                    loss = criterion(output, target)
                    loss.backward()
                    optimizer.step()
                    
                    epoch_loss += loss.item()
        else:
            # Regular training (no DP)
            for batch_idx, (data, target) in enumerate(train_loader):
                data, target = data.to(self.device), target.to(self.device)
                
                optimizer.zero_grad()
                output = self.model(data)
                loss = criterion(output, target)
                loss.backward()
                optimizer.step()
                
                epoch_loss += loss.item()
        
        avg_loss = epoch_loss / len(train_loader)
        total_loss += avg_loss
        
        # NEW: Log privacy spent
        if self.enable_dp:
            epsilon = privacy_engine.get_epsilon(delta=self.dp_target_delta)
            print(f"[{self.node_id}] Epoch {epoch+1}/{num_epochs} - "
                  f"Loss: {avg_loss:.4f}, ε: {epsilon:.2f}")
        else:
            print(f"[{self.node_id}] Epoch {epoch+1}/{num_epochs} - "
                  f"Loss: {avg_loss:.4f}")
    
    # Validation
    val_loss, accuracy = self._validate()
    
    # Get final privacy spent
    final_epsilon = None
    if self.enable_dp:
        final_epsilon = privacy_engine.get_epsilon(delta=self.dp_target_delta)
        print(f"[{self.node_id}] 🔒 Final privacy spent: ε = {final_epsilon:.2f}")
    
    # Return results
    metrics = {
        "train_loss": total_loss / num_epochs,
        "val_loss": val_loss,
        "accuracy": accuracy,
        "num_samples": len(self.train_loader.dataset),
    }
    
    # NEW: Add DP metrics
    if self.enable_dp:
        metrics["dp_epsilon"] = final_epsilon
        metrics["dp_delta"] = self.dp_target_delta
        metrics["dp_enabled"] = True
    
    return self.get_parameters({}), len(self.train_loader.dataset), metrics
```

---

### 3. Server-Side: Strategy cu DP

**Fișier:** `shared/python/node_core/node_core/flower_strategy.py`

**Modificări necesare:**

#### A. Import pentru DP
```python
import numpy as np
from typing import Optional
```

#### B. Adaugă parametri DP în `__init__`
```python
def __init__(
    self,
    # ... existing parameters ...
    
    # NEW: Server-side DP parameters
    enable_server_dp: bool = False,
    server_dp_noise_multiplier: float = 0.1,
    server_dp_sensitivity: float = 1.0,
    **kwargs
):
    super().__init__(**kwargs)
    
    # ... existing initialization ...
    
    # NEW: Server-side DP configuration
    self.enable_server_dp = enable_server_dp
    self.server_dp_noise_multiplier = server_dp_noise_multiplier
    self.server_dp_sensitivity = server_dp_sensitivity
    
    if enable_server_dp:
        print(f"[FedMedStrategy] 🔒 Server-side DP enabled")
        print(f"[FedMedStrategy]   Noise multiplier: {server_dp_noise_multiplier}")
        print(f"[FedMedStrategy]   Sensitivity: {server_dp_sensitivity}")
```

#### C. Adaugă funcție pentru zgomot DP
```python
def _add_dp_noise(self, parameters: List[np.ndarray]) -> List[np.ndarray]:
    """
    Add Gaussian noise to aggregated parameters for server-side DP.
    
    Args:
        parameters: List of parameter arrays
        
    Returns:
        Parameters with added noise
    """
    if not self.enable_server_dp:
        return parameters
    
    noisy_parameters = []
    total_noise_norm = 0.0
    
    for param in parameters:
        # Calculate noise scale
        noise_scale = (
            self.server_dp_noise_multiplier * 
            self.server_dp_sensitivity
        )
        
        # Generate Gaussian noise
        noise = np.random.normal(
            loc=0.0,
            scale=noise_scale,
            size=param.shape
        )
        
        # Add noise to parameters
        noisy_param = param + noise
        noisy_parameters.append(noisy_param)
        
        # Track noise magnitude
        total_noise_norm += np.linalg.norm(noise)
    
    print(f"[FedMedStrategy] 🔒 Added DP noise (total norm: {total_noise_norm:.4f})")
    
    return noisy_parameters
```

#### D. Modifică `aggregate_fit()` pentru DP
```python
def aggregate_fit(
    self,
    server_round: int,
    results: List[Tuple[fl.server.client_proxy.ClientProxy, fl.common.FitRes]],
    failures: List[...],
):
    """Aggregate with optional server-side DP."""
    
    # ... existing aggregation logic ...
    
    # Call parent aggregation
    aggregated_parameters, aggregated_metrics = super().aggregate_fit(
        server_round, results, failures
    )
    
    if aggregated_parameters is not None:
        # NEW: Add server-side DP noise
        if self.enable_server_dp:
            parameters_list = fl.common.parameters_to_ndarrays(aggregated_parameters)
            noisy_parameters = self._add_dp_noise(parameters_list)
            aggregated_parameters = fl.common.ndarrays_to_parameters(noisy_parameters)
        
        # Save model
        if self.save_models:
            parameters_list = fl.common.parameters_to_ndarrays(aggregated_parameters)
            self._save_global_model(parameters_list, server_round)
        
        # NEW: Log DP metrics
        if self.enable_server_dp or any(
            r[1].metrics.get("dp_enabled", False) for r in results
        ):
            print(f"\n  🔒 Differential Privacy Stats:")
            
            # Client-side DP
            client_epsilons = [
                r[1].metrics.get("dp_epsilon", 0) 
                for r in results 
                if r[1].metrics.get("dp_enabled", False)
            ]
            
            if client_epsilons:
                avg_epsilon = sum(client_epsilons) / len(client_epsilons)
                max_epsilon = max(client_epsilons)
                print(f"    • Client-side ε (avg): {avg_epsilon:.2f}")
                print(f"    • Client-side ε (max): {max_epsilon:.2f}")
            
            # Server-side DP
            if self.enable_server_dp:
                print(f"    • Server-side noise: {self.server_dp_noise_multiplier}")
    
    return aggregated_parameters, aggregated_metrics
```

---

### 4. Configuration: Docker Compose

**Fișier:** `docker-compose.yml`

**Adaugă environment variables pentru DP:**

```yaml
services:
  central:
    environment:
      # ... existing variables ...
      
      # NEW: Server-side DP Configuration
      ENABLE_SERVER_DP: "false"  # Enable server-side DP
      SERVER_DP_NOISE_MULTIPLIER: "0.1"
      SERVER_DP_SENSITIVITY: "1.0"
  
  node1-worker:
    environment:
      # ... existing variables ...
      
      # NEW: Client-side DP Configuration
      ENABLE_DP: "true"  # Enable client-side DP
      DP_TARGET_EPSILON: "1.0"  # Privacy budget per round
      DP_TARGET_DELTA: "1e-5"  # Failure probability
      DP_NOISE_MULTIPLIER: "1.0"  # Noise scale
      DP_MAX_GRAD_NORM: "1.0"  # Gradient clipping threshold
      DP_MAX_EPOCHS: "10"  # Maximum epochs for privacy accounting
  
  node2-worker:
    environment:
      # Same as node1-worker
      ENABLE_DP: "true"
      DP_TARGET_EPSILON: "1.0"
      DP_TARGET_DELTA: "1e-5"
      DP_NOISE_MULTIPLIER: "1.0"
      DP_MAX_GRAD_NORM: "1.0"
      DP_MAX_EPOCHS: "10"
  
  node3-worker:
    environment:
      # Same as node1-worker
      ENABLE_DP: "true"
      DP_TARGET_EPSILON: "1.0"
      DP_TARGET_DELTA: "1e-5"
      DP_NOISE_MULTIPLIER: "1.0"
      DP_MAX_GRAD_NORM: "1.0"
      DP_MAX_EPOCHS: "10"
```

---

### 5. Flower Server: Configurare DP

**Fișier:** `services/central/app/flower_server.py`

**Modifică funcția `start_flower_server()`:**

```python
def start_flower_server(
    # ... existing parameters ...
    
    # NEW: DP parameters
    enable_server_dp: bool = False,
    server_dp_noise_multiplier: float = 0.1,
    server_dp_sensitivity: float = 1.0,
):
    """Start Flower server with optional DP."""
    
    print("=" * 70)
    print("FED-MED-FL FLOWER SERVER")
    print("=" * 70)
    # ... existing prints ...
    
    # NEW: Print DP configuration
    if enable_server_dp:
        print(f"Server-side DP: Enabled")
        print(f"  Noise multiplier: {server_dp_noise_multiplier}")
        print(f"  Sensitivity: {server_dp_sensitivity}")
    else:
        print(f"Server-side DP: Disabled")
    
    print("=" * 70)
    
    # Create strategy with DP
    strategy = create_fedmed_strategy(
        # ... existing parameters ...
        
        # NEW: DP parameters
        enable_server_dp=enable_server_dp,
        server_dp_noise_multiplier=server_dp_noise_multiplier,
        server_dp_sensitivity=server_dp_sensitivity,
    )
    
    # ... rest of function ...
```

**Modifică `main()` pentru a citi DP config:**

```python
def main():
    """Main entry point."""
    # ... existing config ...
    
    # NEW: DP configuration
    enable_server_dp = os.getenv("ENABLE_SERVER_DP", "false").lower() == "true"
    server_dp_noise_multiplier = float(os.getenv("SERVER_DP_NOISE_MULTIPLIER", "0.1"))
    server_dp_sensitivity = float(os.getenv("SERVER_DP_SENSITIVITY", "1.0"))
    
    # Start server
    start_flower_server(
        # ... existing parameters ...
        
        # NEW: DP parameters
        enable_server_dp=enable_server_dp,
        server_dp_noise_multiplier=server_dp_noise_multiplier,
        server_dp_sensitivity=server_dp_sensitivity,
    )
```

---

### 6. Task Runner: Configurare DP pentru Client

**Fișier:** `services/node/api/app/tasks.py`

**Modifică funcția `run_federated_training()`:**

```python
@celery_app.task(bind=True)
def run_federated_training(
    self,
    # ... existing parameters ...
):
    """Run federated training with optional DP."""
    
    # ... existing setup ...
    
    # NEW: Read DP configuration from environment
    enable_dp = os.getenv("ENABLE_DP", "false").lower() == "true"
    dp_config = {}
    
    if enable_dp:
        dp_config = {
            "enable_dp": True,
            "dp_target_epsilon": float(os.getenv("DP_TARGET_EPSILON", "1.0")),
            "dp_target_delta": float(os.getenv("DP_TARGET_DELTA", "1e-5")),
            "dp_noise_multiplier": float(os.getenv("DP_NOISE_MULTIPLIER", "1.0")),
            "dp_max_grad_norm": float(os.getenv("DP_MAX_GRAD_NORM", "1.0")),
            "dp_max_epochs": int(os.getenv("DP_MAX_EPOCHS", "10")),
        }
        
        print(f"[Task] 🔒 DP enabled with ε={dp_config['dp_target_epsilon']}")
    
    # Create client with DP config
    client = FedMedFlowerClient(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        device=device,
        node_id=node_id,
        **dp_config,  # NEW: Pass DP configuration
    )
    
    # ... rest of function ...
```

---

## 📊 Configurații Recomandate

### Development (Testing DP)
```yaml
ENABLE_DP: "true"
DP_TARGET_EPSILON: "10.0"  # Relaxed for testing
DP_TARGET_DELTA: "1e-5"
DP_NOISE_MULTIPLIER: "0.5"  # Less noise
DP_MAX_GRAD_NORM: "1.5"
```

### Staging (Balanced)
```yaml
ENABLE_DP: "true"
DP_TARGET_EPSILON: "3.0"  # Moderate privacy
DP_TARGET_DELTA: "1e-5"
DP_NOISE_MULTIPLIER: "0.8"
DP_MAX_GRAD_NORM: "1.0"
```

### Production (High Privacy)
```yaml
ENABLE_DP: "true"
DP_TARGET_EPSILON: "1.0"  # Strong privacy
DP_TARGET_DELTA: "1e-6"
DP_NOISE_MULTIPLIER: "1.0"
DP_MAX_GRAD_NORM: "1.0"
```

### Medical (Maximum Privacy)
```yaml
ENABLE_DP: "true"
DP_TARGET_EPSILON: "0.5"  # Very strong privacy
DP_TARGET_DELTA: "1e-6"
DP_NOISE_MULTIPLIER: "1.2"
DP_MAX_GRAD_NORM: "0.8"
```

---

## 🧪 Testing

### Test 1: Verificare DP este activ
```bash
# Start services cu DP
docker compose up -d

# Check logs
docker compose logs node1-worker | grep "DP-SGD enabled"
docker compose logs central | grep "Differential Privacy"
```

### Test 2: Verificare epsilon tracking
```bash
# Run training
./scripts/test_single_fl.sh

# Check epsilon values
docker compose logs node1-worker | grep "ε:"
```

### Test 3: Comparație cu/fără DP
```bash
# Test fără DP
ENABLE_DP=false ./scripts/test_single_fl.sh > results_no_dp.txt

# Test cu DP
ENABLE_DP=true ./scripts/test_single_fl.sh > results_with_dp.txt

# Compare accuracy
diff results_no_dp.txt results_with_dp.txt
```

---

## 📈 Trade-offs & Tuning

### Accuracy vs Privacy

| ε | Privacy Level | Expected Accuracy Loss |
|---|---------------|------------------------|
| 0.1 | Maximum | 15-25% |
| 0.5 | Very High | 10-15% |
| 1.0 | High | 5-10% |
| 3.0 | Moderate | 2-5% |
| 10.0 | Low | 0-2% |

### Tuning Guidelines

**Dacă accuracy este prea scăzut:**
1. Crește `DP_TARGET_EPSILON` (ex: 1.0 → 3.0)
2. Reduce `DP_NOISE_MULTIPLIER` (ex: 1.0 → 0.8)
3. Crește `DP_MAX_GRAD_NORM` (ex: 1.0 → 1.5)
4. Crește numărul de epochs
5. Crește batch size

**Dacă vrei mai mult privacy:**
1. Reduce `DP_TARGET_EPSILON` (ex: 3.0 → 1.0)
2. Crește `DP_NOISE_MULTIPLIER` (ex: 0.8 → 1.2)
3. Reduce `DP_MAX_GRAD_NORM` (ex: 1.5 → 1.0)

---

## ✅ Checklist Implementare

- [ ] Adaugă `opacus` și `dp-accounting` în requirements.txt
- [ ] Modifică `flower_client.py` cu Opacus
- [ ] Modifică `flower_strategy.py` cu server-side DP
- [ ] Adaugă DP config în `docker-compose.yml`
- [ ] Modifică `flower_server.py` pentru DP
- [ ] Modifică `tasks.py` pentru DP config
- [ ] Rebuild Docker images
- [ ] Test cu DP disabled
- [ ] Test cu DP enabled
- [ ] Tune parametrii DP
- [ ] Documentare rezultate

---

*Ghid generat: 27 aprilie 2026*  
*Versiune: 1.0*  
*Status: READY FOR IMPLEMENTATION*
