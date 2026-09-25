.PHONY: up down test demo

up:
	docker compose up --build

down:
	docker compose down -v

test:
	cd services/platform-api && python -m pytest

demo:
	cd simulator && python simulator.py --once --high

