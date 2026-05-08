# Legacy FL Code Analysis - Pre-Flower Remnants

**Date**: May 8, 2026  
**Status**: 🔍 **ANALYSIS COMPLETE**

---

## Executive Summary

Identified **legacy code from manual FL implementation** that is no longer used after migration to Flower framework. This code exists but is **completely bypassed** in the current Flower-based workflow.

---

## Background

Before Flower integration, the system used a **manual FL workflow**:
1. Central server managed rounds manually
2. Nodes submitted model deltas (not full parameters)
3. Central server aggregated deltas using custom FedAvg
4. Nodes pulled updated global model

**Current Flower workflow** bypasses all of this:
- Flower handles round management internally
- Flower handles parameter aggregation (FedAvg)
- No manual delta submission/aggregation needed

---

## Legacy Code Identified

### 1. **Central Server - `services/central/app/main.py`**

#### A. `UpdateSubmitRequest` Schema (UNUSED) 🔴

**Location**: Lines 78-86

```python
class UpdateSubmitRequest(BaseModel):
    node_id: str
    round_id: str
    base_model_hash: str
    n_samples: int
    metrics: Dict[str, Any]
    delta: str  # Base64 encoded delta state dict
    delta_hash: str
```

**Status**: ❌ **DEAD CODE**
- No endpoint uses this schema
- Was for manual delta submission (pre-Flower)
- Flower sends full parameters, not deltas

---

#### B. Round Management Endpoints (PARTIALLY LEGACY) 🟡

**Endpoints:**
1. `POST /round/create` - ✅ **STILL USED** (by test_e2e_efficientnet.py)
2. `POST /round/{round_id}/join` - ✅ **STILL USED** (by test_e2e_efficientnet.py)
3. `GET /round/{round_id}/status` - ✅ **STILL USED** (by Node API)

**Analysis:**
- These endpoints are **informational only** now
- They don't actually control Flower (Flower is started manually)
- `rounds_db` stores metadata but Flower doesn't read it
- **Purpose**: Allow E2E tests and Node API to track rounds

**Current behavior:**
```python
# POST /round/create
rounds_db[request.round_id] = {
    "round_id": request.round_id,
    "model_name": request.model_name,
    "status": "created",  # ⚠️ Never updated!
    ...
}
# Returns: "Start Flower server manually"
```

**Problem**: `status` field is set to "created" but **never updated** to "training", "completed", etc.

---

#### C. `rounds_db` Dictionary (PARTIALLY USED) 🟡

**Location**: Line 54

```python
rounds_db = {}
```

**Status**: ⚠️ **PARTIALLY LEGACY**

**Used by:**
- `create_round()` - writes to it
- `get_round_status()` - reads from it (called by Node API)

**NOT used by:**
- Flower Server (doesn't know about it)
- Flower Strategy (has its own round tracking)

**Problems:**
1. In-memory only (lost on restart)
2. Status never updated after "created"
3. Redundant with Flower's internal round tracking
4. No synchronization with actual Flower state

---

### 2. **Node API - `services/node/api/app/main.py`**

#### A. `base_model_hash` Field in Model Table (UNUSED) 🔴

**Location**: `services/node/api/app/database.py:118`

```python
class Model(Base):
    ...
    base_model_hash = Column(String, nullable=True)  # Hash of base model for FL
```

**Status**: ❌ **DEAD CODE**

**Analysis:**
- Field exists in database schema
- **Never written to** (always `None`)
- Was for tracking base model in manual FL delta workflow
- Flower doesn't use model hashes (uses round numbers)

**Verification:**
```bash
# Search for assignments to base_model_hash
grep -r "base_model_hash\s*=" services/
# Result: Only in schema definition, never assigned
```

---

#### B. Federated Training Endpoints (ACTIVE BUT SIMPLIFIED) ✅

**Endpoints:**
1. `POST /api/federated/train/{round_id}` - ✅ **ACTIVE**
2. `GET /api/federated/status/{round_id}` - ✅ **ACTIVE**
3. `GET /api/federated/history` - ✅ **ACTIVE**

**Status**: ✅ **ACTIVE** but simplified for Flower

**Current behavior:**
- `/train/{round_id}` - Creates Celery task that starts Flower client
- `/status/{round_id}` - Returns local job status + note about Flower
- `/history` - Queries local DB + tries to get status from Central

**Legacy aspects:**
- Still calls `CENTRAL_URL/round/{round_id}/status` (which returns stale "created" status)
- Tries to determine `is_active` from central status (but status never updates)

---

### 3. **Node Core - `shared/python/node_core/`**

#### A. Flower Strategy (ACTIVE) ✅

**File**: `node_core/flower_strategy.py`

**Status**: ✅ **ACTIVE** - This is the current implementation

**Contains:**
- `FedMedStrategy` - Custom FedAvg strategy for Flower
- Model persistence
- Signature verification
- Server-side DP

**NOT legacy** - This is the new Flower-based code.

---

#### B. Example Files (DOCUMENTATION ONLY) 📚

**Files:**
- `examples/fl_simulation.py` - Shows old manual FL workflow
- `examples/flower_quickstart.py` - Shows Flower basics
- `examples/flower_simulation.py` - Shows Flower simulation

**Status**: 📚 **DOCUMENTATION/EXAMPLES**
- Not used in production
- Useful for understanding concepts
- Can be kept for reference

---

## Workflow Comparison

### **OLD (Manual FL) - DEPRECATED** ❌

```
1. Central: POST /round/create → Initialize round in rounds_db
2. Nodes: POST /round/{id}/join → Register participation
3. Nodes: GET /round/{id}/plan → Get training config
4. Nodes: Train locally → Compute delta (model_new - model_base)
5. Nodes: POST /round/{id}/submit → Send delta + hash
6. Central: POST /round/{id}/aggregate → Apply FedAvg to deltas
7. Nodes: GET /round/{id}/model → Download new global model
8. Repeat steps 4-7 for multiple rounds
```

**Key characteristics:**
- Central server orchestrates everything
- Nodes send deltas (differences), not full parameters
- Manual aggregation with custom code
- Complex state management

---

### **NEW (Flower) - CURRENT** ✅

```
1. Test: POST /round/create → Store metadata (informational)
2. Test: POST /round/{id}/join → Store metadata (informational)
3. Manual: Start Flower Server → Flower takes over
4. Nodes: POST /api/federated/train/{id} → Start Flower client
5. Flower: Handles all communication, aggregation, rounds internally
6. Nodes: Model saved automatically by Flower client
```

**Key characteristics:**
- Flower handles orchestration
- Nodes send full parameters (not deltas)
- Flower's built-in FedAvg
- Minimal state management needed

---

## What's Actually Used Now

### **Central Server (`services/central/app/main.py`)**

| Component | Status | Purpose |
|-----------|--------|---------|
| `GET /health` | ✅ ACTIVE | Health check |
| `POST /round/create` | ✅ ACTIVE | Store round metadata for tests |
| `POST /round/{round_id}/join` | ✅ ACTIVE | Store node registration for tests |
| `GET /round/{round_id}/status` | ✅ ACTIVE | Return round metadata (stale) |
| `rounds_db` | 🟡 PARTIAL | Stores metadata, never updated |
| `UpdateSubmitRequest` | ❌ DEAD | No endpoint uses it |

---

### **Node API (`services/node/api/app/main.py`)**

| Component | Status | Purpose |
|-----------|--------|---------|
| `POST /api/federated/train/{round_id}` | ✅ ACTIVE | Start Flower client |
| `GET /api/federated/status/{round_id}` | ✅ ACTIVE | Get local job status |
| `GET /api/federated/history` | ✅ ACTIVE | Get FL history from local DB |
| `base_model_hash` (DB field) | ❌ DEAD | Never written, always NULL |

---

### **Flower Components (NEW)**

| Component | Status | Purpose |
|-----------|--------|---------|
| `flower_server.py` | ✅ ACTIVE | Flower server wrapper |
| `flower_client.py` | ✅ ACTIVE | Flower client implementation |
| `flower_strategy.py` | ✅ ACTIVE | Custom FedAvg strategy |

---

## Issues with Current State

### 1. **Stale Round Status** 🔴

**Problem:**
```python
# Central creates round with status="created"
rounds_db[round_id] = {"status": "created", ...}

# Status NEVER updated to "training", "completed", etc.
# Flower doesn't update rounds_db
```

**Impact:**
- `GET /round/{round_id}/status` always returns "created"
- Node API's `/api/federated/history` tries to determine `is_active` from this stale status
- Misleading information

---

### 2. **Redundant State Management** 🟡

**Problem:**
- Central has `rounds_db` (in-memory, stale)
- Flower has internal round tracking (accurate)
- Node API has job status in DB (accurate for local state)
- **No synchronization** between these three

**Impact:**
- Confusion about source of truth
- Wasted memory/storage
- Potential inconsistencies

---

### 3. **Unused Database Fields** 🔴

**Problem:**
```python
# Model table has base_model_hash field
base_model_hash = Column(String, nullable=True)

# But it's NEVER set (always NULL)
```

**Impact:**
- Wasted database space
- Confusing schema
- Suggests functionality that doesn't exist

---

## Recommendations

### **OPTION A: Minimal Cleanup (SAFE)** ✅

**Remove only confirmed dead code:**

1. ✅ **DELETE** `UpdateSubmitRequest` schema (services/central/app/main.py:78-86)
   - Not used by any endpoint
   - Zero impact

2. ✅ **DELETE** `base_model_hash` field from Model table
   - Never written to
   - Always NULL
   - Requires database migration

3. ✅ **UPDATE** comments to clarify current behavior
   - Document that round endpoints are informational only
   - Note that Flower handles actual orchestration

**Impact**: Zero breaking changes, cleaner code

---

### **OPTION B: Full Modernization (RISKY)** ⚠️

**Redesign round management for Flower:**

1. **Remove** `rounds_db` from Central
2. **Remove** round management endpoints from Central
3. **Update** Node API to not call Central for round status
4. **Update** E2E tests to not use Central round endpoints
5. **Rely** entirely on Flower's internal state + Node's local DB

**Impact**: Breaking changes to tests, requires significant refactoring

---

### **OPTION C: Hybrid (RECOMMENDED)** 🎯

**Keep endpoints but fix status tracking:**

1. ✅ **DELETE** `UpdateSubmitRequest` (dead code)
2. ✅ **DELETE** `base_model_hash` field (dead code)
3. ✅ **ADD** status update mechanism:
   - Flower Strategy calls Central API to update round status
   - OR Node API updates Central when training completes
4. ✅ **ADD** persistence for `rounds_db` (SQLite/Redis)
5. ✅ **DOCUMENT** that Central endpoints are for monitoring only

**Impact**: Minimal breaking changes, improved accuracy

---

## Summary

### **Dead Code (Safe to Delete)** 🔴
- `UpdateSubmitRequest` schema
- `base_model_hash` database field

### **Legacy but Still Used** 🟡
- Round management endpoints (informational only)
- `rounds_db` (stale but queried)

### **Active Flower Code** ✅
- `flower_server.py`
- `flower_client.py`
- `flower_strategy.py`
- Federated training endpoints in Node API

---

## Next Steps

**Immediate (No Risk):**
1. Delete `UpdateSubmitRequest` schema
2. Add comments explaining current Flower-based workflow
3. Document that round endpoints are informational

**Short-term (Low Risk):**
4. Create database migration to remove `base_model_hash`
5. Add persistence for `rounds_db`

**Long-term (Requires Planning):**
6. Implement status synchronization between Flower and Central
7. Consider removing Central round endpoints entirely
8. Update E2E tests to work without Central round management

---

**Analysis completed by**: Kiro AI  
**Date**: May 8, 2026  
**Files analyzed**: 8  
**Dead code identified**: 2 items  
**Legacy code identified**: 3 items
