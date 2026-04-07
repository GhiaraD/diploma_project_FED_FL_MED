.PHONY: up down logs build

up:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f --tail=200

build:
	docker compose build --no-cache