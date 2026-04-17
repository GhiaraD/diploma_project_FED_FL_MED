.PHONY: up down logs build restart status test-api test-central clean help

# Start all services
up:
	docker compose up -d

# Start all services with build
up-build:
	docker compose up -d --build

# Stop all services
down:
	docker compose down

# Stop and remove volumes
down-clean:
	docker compose down -v

# View logs (all services)
logs:
	docker compose logs -f --tail=200

# View logs for specific service
logs-central:
	docker compose logs -f central --tail=100

logs-node1:
	docker compose logs -f node1-api node1-worker --tail=100

logs-node2:
	docker compose logs -f node2-api node2-worker --tail=100

logs-node3:
	docker compose logs -f node3-api node3-worker --tail=100

# Build all services
build:
	docker compose build

# Build specific services
build-central:
	docker compose build central

build-nodes:
	docker compose build node1-api node1-worker node2-api node2-worker node3-api node3-worker

build-ui:
	docker compose build node1-ui node2-ui node3-ui

# Restart services
restart:
	docker compose restart

restart-central:
	docker compose restart central

restart-node1:
	docker compose restart node1-api node1-worker

# Check status
status:
	docker compose ps

# Test APIs
test-api:
	@echo "Testing Node1 API..."
	@curl -s http://localhost:8001/api/health | python3 -m json.tool || echo "Node1 API not responding"
	@echo ""
	@echo "Testing Node2 API..."
	@curl -s http://localhost:8002/api/health | python3 -m json.tool || echo "Node2 API not responding"
	@echo ""
	@echo "Testing Node3 API..."
	@curl -s http://localhost:8003/api/health | python3 -m json.tool || echo "Node3 API not responding"

test-central:
	@echo "Testing Central Server..."
	@curl -s http://localhost:8080/health | python3 -m json.tool || echo "Central not responding"

test-ui:
	@echo "Testing Node1 UI..."
	@curl -s http://localhost:3001 > /dev/null && echo "✓ Node1 UI is running" || echo "✗ Node1 UI not responding"
	@echo "Testing Node2 UI..."
	@curl -s http://localhost:3002 > /dev/null && echo "✓ Node2 UI is running" || echo "✗ Node2 UI not responding"
	@echo "Testing Node3 UI..."
	@curl -s http://localhost:3003 > /dev/null && echo "✓ Node3 UI is running" || echo "✗ Node3 UI not responding"

# Test all
test-all: test-central test-api test-ui

# Clean up
clean:
	docker compose down -v
	docker system prune -f

# Demo FL workflow
demo:
	./scripts/demo_fl_workflow.sh

# Create test datasets
create-datasets:
	python3 scripts/create_test_dataset.py

# Run automated E2E test
test-e2e:
	python3 scripts/automated_fl_test.py

# Run manual E2E test (with user interaction)
test-e2e-manual:
	./scripts/test_e2e_fl_workflow.sh

# Help
help:
	@echo "Fed-Med-FL - Makefile Commands"
	@echo ""
	@echo "Starting Services:"
	@echo "  make up              - Start all services"
	@echo "  make up-build        - Start all services with build"
	@echo "  make down            - Stop all services"
	@echo "  make down-clean      - Stop and remove volumes"
	@echo ""
	@echo "Logs:"
	@echo "  make logs            - View all logs"
	@echo "  make logs-central    - View central server logs"
	@echo "  make logs-node1      - View node1 logs"
	@echo "  make logs-node2      - View node2 logs"
	@echo "  make logs-node3      - View node3 logs"
	@echo ""
	@echo "Building:"
	@echo "  make build           - Build all services"
	@echo "  make build-central   - Build central server"
	@echo "  make build-nodes     - Build all node services"
	@echo "  make build-ui        - Build all UI services"
	@echo ""
	@echo "Testing:"
	@echo "  make test-all        - Test all services"
	@echo "  make test-central    - Test central server"
	@echo "  make test-api        - Test node APIs"
	@echo "  make test-ui         - Test node UIs"
	@echo "  make test-e2e        - Run automated end-to-end FL test"
	@echo "  make test-e2e-manual - Run manual end-to-end FL test"
	@echo "  make status          - Check service status"
	@echo ""
	@echo "Other:"
	@echo "  make restart         - Restart all services"
	@echo "  make clean           - Clean up containers and volumes"
	@echo "  make demo            - Run FL workflow demo"
	@echo "  make create-datasets - Create synthetic test datasets"
	@echo "  make help            - Show this help message"