#!/usr/bin/env python3
"""
Fix SSL configuration: 
- APIs (central, node1-api, node2-api, node3-api): ENABLE_SSL="false"
- Workers (node1-worker, node2-worker, node3-worker): ENABLE_SSL="true"
"""

with open('docker-compose.yml', 'r') as f:
    lines = f.readlines()

in_api_section = False
in_worker_section = False
current_service = None

for i, line in enumerate(lines):
    # Detect service sections
    if line.strip().startswith('central:') or \
       line.strip().startswith('node1-api:') or \
       line.strip().startswith('node2-api:') or \
       line.strip().startswith('node3-api:'):
        in_api_section = True
        in_worker_section = False
        current_service = line.strip().rstrip(':')
        print(f"Found API service: {current_service}")
    elif line.strip().startswith('node1-worker:') or \
         line.strip().startswith('node2-worker:') or \
         line.strip().startswith('node3-worker:'):
        in_worker_section = True
        in_api_section = False
        current_service = line.strip().rstrip(':')
        print(f"Found Worker service: {current_service}")
    elif line.strip() and not line.strip().startswith(' ') and ':' in line:
        # New top-level service
        in_api_section = False
        in_worker_section = False
    
    # Fix ENABLE_SSL
    if 'ENABLE_SSL:' in line:
        if in_api_section:
            lines[i] = line.replace('ENABLE_SSL: "true"', 'ENABLE_SSL: "false"')
            print(f"  → Set ENABLE_SSL=false for {current_service}")
        elif in_worker_section:
            lines[i] = line.replace('ENABLE_SSL: "false"', 'ENABLE_SSL: "true"')
            print(f"  → Set ENABLE_SSL=true for {current_service}")

with open('docker-compose.yml', 'w') as f:
    f.writelines(lines)

print("\n✅ SSL configuration fixed!")
print("   APIs: ENABLE_SSL=false (HTTP)")
print("   Workers: ENABLE_SSL=true (mTLS for Flower)")
