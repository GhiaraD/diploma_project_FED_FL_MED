#!/bin/bash

# Complete cleanup script - kills all zombie processes and resets state

set -e

echo "========================================================================"
echo "🧹 COMPLETE CLEANUP"
echo "========================================================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 1. Kill all Python processes in containers
echo -e "${YELLOW}1. Killing Python processes in containers...${NC}"

for container in central node1-api node2-api node3-api node1-worker node2-worker node3-worker; do
    echo "  Checking $container..."
    docker compose exec -T $container bash -c "ps aux | grep python | grep -v grep" 2>/dev/null || true
    docker compose exec -T $container bash -c "killall -9 python python3 2>/dev/null || true" 2>/dev/null || true
done

echo -e "${GREEN}✓ Python processes killed${NC}"
echo ""

# 2. Clear Celery tasks
echo -e "${YELLOW}2. Clearing Celery tasks...${NC}"

for node in node1 node2 node3; do
    echo "  Clearing ${node} Celery queue..."
    docker compose exec -T ${node}-api bash -c "
        python3 -c \"
import redis
try:
    r = redis.Redis(host='${node}-redis', port=6379, db=0)
    # Clear all Celery queues
    for key in r.keys('celery*'):
        r.delete(key)
    for key in r.keys('_kombu*'):
        r.delete(key)
    print('  ✓ Cleared Celery queues')
except Exception as e:
    print(f'  ⚠ Error: {e}')
\" 2>/dev/null || true
    " 2>/dev/null || true
done

echo -e "${GREEN}✓ Celery queues cleared${NC}"
echo ""

# 3. Clear temp files
echo -e "${YELLOW}3. Clearing temp files...${NC}"

docker compose exec -T central bash -c "rm -f /tmp/flower*.log /tmp/flower*.pid 2>/dev/null || true" 2>/dev/null || true
echo -e "${GREEN}✓ Temp files cleared${NC}"
echo ""

# 4. Restart all services
echo -e "${YELLOW}4. Restarting all services...${NC}"

docker compose restart 2>&1 | grep -E "Restarting|Started" || true

echo -e "${GREEN}✓ Services restarted${NC}"
echo ""

# 5. Wait for services to be ready
echo -e "${YELLOW}5. Waiting for services to be ready...${NC}"

sleep 10

# Check health
for port in 8001 8002 8003; do
    if curl -s http://localhost:${port}/api/auth/login > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓ Node on port ${port} is ready${NC}"
    else
        echo -e "  ${YELLOW}⚠ Node on port ${port} may not be ready${NC}"
    fi
done

echo ""

# 6. Verify no running jobs
echo -e "${YELLOW}6. Checking for running jobs...${NC}"

TOKEN1=$(curl -s -X POST "http://localhost:8001/api/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=admin@node1.fed-med-fl.com&password=AdminNode1@2026" 2>/dev/null | \
    grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

if [ -n "$TOKEN1" ]; then
    JOBS=$(curl -s -H "Authorization: Bearer ${TOKEN1}" "http://localhost:8001/api/train/jobs" 2>/dev/null | \
        python3 -c "import sys, json; data = json.load(sys.stdin); jobs = data.get('jobs', []); running = [j for j in jobs if j.get('status') in ['pending', 'running']]; print(len(running))" 2>/dev/null || echo "0")
    
    if [ "$JOBS" = "0" ]; then
        echo -e "  ${GREEN}✓ No running jobs on Node1${NC}"
    else
        echo -e "  ${YELLOW}⚠ Found $JOBS running jobs on Node1${NC}"
    fi
else
    echo -e "  ${YELLOW}⚠ Could not authenticate to check jobs${NC}"
fi

echo ""

# 7. Show container status
echo -e "${YELLOW}7. Container status:${NC}"
docker compose ps --format "table {{.Service}}\t{{.Status}}" 2>&1 | grep -E "Service|node1-api|node2-api|node3-api|central|worker" || true

echo ""
echo "========================================================================"
echo -e "${GREEN}✅ CLEANUP COMPLETE${NC}"
echo "========================================================================"
echo ""
echo "System is ready for testing. You can now run:"
echo "  ./scripts/test_one_policy.sh log"
echo "  ./scripts/test_one_policy.sh warn"
echo "  ./scripts/test_one_policy.sh reject"
echo ""
