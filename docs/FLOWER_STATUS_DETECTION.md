# Flower Server Status Detection

**Date**: May 8, 2026  
**Feature**: Automatic Flower Server status detection

---

## Overview

Central Server can now automatically detect if Flower Server is running by checking if the gRPC port (8080) is accepting connections.

---

## Implementation

### **Method: Port Check**

```python
def check_flower_server_running() -> bool:
    """
    Check if Flower Server is running by attempting to connect to gRPC port.
    
    Returns:
        True if Flower Server is running, False otherwise
    """
    import socket
    
    flower_host = "0.0.0.0"
    flower_port = 8080  # Flower gRPC port
    
    try:
        # Try to connect to Flower gRPC port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)  # 1 second timeout
        result = sock.connect_ex((flower_host, flower_port))
        sock.close()
        return result == 0  # 0 means port is open (server is running)
    except Exception:
        return False
```

**How it works:**
1. Creates a TCP socket
2. Attempts to connect to `0.0.0.0:8080` (Flower gRPC port)
3. Returns `True` if connection succeeds (port is open)
4. Returns `False` if connection fails (port is closed/server not running)
5. 1 second timeout to avoid blocking

---

## API Endpoints

### **1. Health Check** (Updated)

**Endpoint:** `GET /health`

**Response:**
```json
{
  "ok": true,
  "service": "central-fl-management",
  "timestamp": "2026-05-08T10:30:00.000000",
  "storage_path": "/storage",
  "using_flower": true,
  "flower_server_running": true  // ← Now dynamic!
}
```

**Before:** Always returned `false`  
**Now:** Returns actual status based on port check

---

### **2. Flower Status** (New)

**Endpoint:** `GET /flower/status`

**Response when running:**
```json
{
  "flower_server_running": true,
  "flower_server_address": "0.0.0.0:8080",
  "protocol": "gRPC",
  "ssl_enabled": true,
  "status": "running",
  "message": "Flower Server is running and accepting connections"
}
```

**Response when stopped:**
```json
{
  "flower_server_running": false,
  "flower_server_address": "0.0.0.0:8080",
  "protocol": "gRPC",
  "ssl_enabled": true,
  "status": "stopped",
  "message": "Flower Server is not running. Start it with: ./scripts/start_flower_server.sh"
}
```

---

## Usage Examples

### **Check from Command Line**

```bash
# Check health (includes Flower status)
curl http://localhost:8081/health

# Check Flower status specifically
curl http://localhost:8081/flower/status
```

---

### **Check from Python**

```python
import requests

# Check if Flower Server is running
response = requests.get("http://localhost:8081/flower/status")
data = response.json()

if data["flower_server_running"]:
    print("✓ Flower Server is running")
else:
    print("✗ Flower Server is not running")
    print(f"  {data['message']}")
```

---

### **Check from Node API**

```python
import requests
from .config import settings

def is_flower_server_available():
    """Check if Flower Server is available."""
    try:
        response = requests.get(
            f"{settings.CENTRAL_URL}/flower/status",
            timeout=2
        )
        if response.ok:
            data = response.json()
            return data.get("flower_server_running", False)
    except:
        pass
    return False

# Usage
if is_flower_server_available():
    # Start federated training
    pass
else:
    # Show error: "Flower Server is not running"
    pass
```

---

## Benefits

### **1. Better User Experience** ✅
- Users can see if Flower Server is running before starting training
- Clear error messages when server is not available
- No confusing "connection refused" errors

### **2. Automated Monitoring** ✅
- Health checks now include Flower status
- Monitoring tools can detect when Flower Server goes down
- Easier debugging

### **3. Validation** ✅
- Can validate Flower Server is running before starting training
- Prevents wasted time trying to connect to stopped server
- Better error handling

---

## Limitations

### **1. Port-Based Detection**
- Only checks if port 8080 is open
- Doesn't verify Flower Server is actually responding correctly
- Could give false positive if another service uses port 8080

### **2. Local Only**
- Currently checks `0.0.0.0:8080` (local)
- Doesn't work if Flower Server is on different host
- Would need configuration for remote Flower Server

### **3. No Round Information**
- Only detects if server is running
- Doesn't provide information about active rounds
- Doesn't show number of connected clients

---

## Future Enhancements

### **Option 1: gRPC Health Check** (More Reliable)

```python
import grpc

def check_flower_server_running_grpc():
    """Check Flower Server using gRPC health check."""
    try:
        channel = grpc.insecure_channel('localhost:8080')
        # Use gRPC health check protocol
        # More reliable than port check
        return True
    except:
        return False
```

**Benefits:**
- More reliable (actually talks to Flower)
- Can get more information (version, capabilities)
- Standard gRPC health check protocol

**Drawbacks:**
- Requires gRPC client library
- More complex implementation

---

### **Option 2: Flower API Integration** (Most Information)

```python
def get_flower_server_info():
    """Get detailed Flower Server information."""
    # If Flower exposes REST API
    response = requests.get("http://localhost:8080/api/status")
    return {
        "running": True,
        "active_rounds": response.json()["rounds"],
        "connected_clients": response.json()["clients"],
        "version": response.json()["version"]
    }
```

**Benefits:**
- Most detailed information
- Can show active rounds, connected clients
- Better monitoring

**Drawbacks:**
- Requires Flower to expose REST API
- May not be available in current Flower version

---

### **Option 3: Process Monitoring** (Most Accurate)

```python
import psutil

def check_flower_server_running_process():
    """Check if Flower Server process is running."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if 'flower_server' in cmdline:
                return True
        except:
            pass
    return False
```

**Benefits:**
- Most accurate (checks actual process)
- Works even if port is not yet open
- Can get process info (PID, memory, CPU)

**Drawbacks:**
- Requires psutil library
- Requires access to process list
- May not work in containers

---

## Testing

### **Test 1: Server Not Running**

```bash
# Ensure Flower Server is stopped
# Check status
curl http://localhost:8081/flower/status

# Expected:
{
  "flower_server_running": false,
  "status": "stopped",
  "message": "Flower Server is not running..."
}
```

---

### **Test 2: Server Running**

```bash
# Start Flower Server
./scripts/start_flower_server.sh

# Wait a few seconds for server to start
sleep 5

# Check status
curl http://localhost:8081/flower/status

# Expected:
{
  "flower_server_running": true,
  "status": "running",
  "message": "Flower Server is running and accepting connections"
}
```

---

### **Test 3: Health Check**

```bash
# Check health endpoint
curl http://localhost:8081/health

# Expected: flower_server_running should match actual state
{
  "ok": true,
  "flower_server_running": true,  // or false
  ...
}
```

---

## Configuration

### **Environment Variables**

| Variable | Default | Description |
|----------|---------|-------------|
| `FLOWER_SERVER_HOST` | `0.0.0.0` | Flower Server host to check |
| `FLOWER_SERVER_PORT` | `8080` | Flower Server gRPC port |
| `FLOWER_ENABLE_SSL` | `true` | Whether SSL is enabled |

**Note:** Currently hardcoded to `0.0.0.0:8080`. Can be made configurable if needed.

---

## Troubleshooting

### **Issue: Always returns `false` even when server is running**

**Possible causes:**
1. Flower Server is on different host
2. Firewall blocking port 8080
3. Flower Server using different port
4. Network connectivity issues

**Solution:**
```bash
# Check if port is actually open
netstat -tuln | grep 8080

# Try connecting manually
telnet localhost 8080
```

---

### **Issue: Slow response time**

**Cause:** 1 second timeout for socket connection

**Solution:**
- Reduce timeout (but may cause false negatives)
- Cache result for a few seconds
- Use async check

---

## Summary

✅ **Implemented:** Automatic Flower Server status detection  
✅ **Method:** TCP port check (simple and reliable)  
✅ **Endpoints:** `/health` (updated) and `/flower/status` (new)  
✅ **Benefits:** Better UX, monitoring, validation  
🔄 **Future:** Can enhance with gRPC health check or process monitoring

---

**Feature implemented by**: Kiro AI  
**Date**: May 8, 2026  
**Status**: ✅ Active
