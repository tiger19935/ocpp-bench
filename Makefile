.PHONY: install lint typecheck test test-unit test-integration coverage load sim up down logs clean

PY := uv run

install:
	uv python install 3.12
	uv sync --all-groups

lint:
	$(PY) ruff check src tests
	$(PY) ruff format --check src tests

fmt:
	$(PY) ruff format src tests
	$(PY) ruff check --fix src tests

typecheck:
	$(PY) mypy

test-unit:
	$(PY) pytest tests/unit

test-integration:
	$(PY) pytest tests/integration -m "not slow"

test:
	$(PY) pytest --cov --cov-report=term

coverage:
	$(PY) pytest --cov --cov-report=term-missing --cov-report=xml

load:
	$(PY) ocpp-bench sim --target ws://localhost:9000/ocpp --stations 1000 --scenario soak --protocol 1.6 --duration 60

sim:
	$(PY) ocpp-bench sim --target ws://localhost:9000/ocpp --stations 50 --scenario normal --protocol 1.6

up:
	docker compose up -d --build

down:
	docker compose down -v

logs:
	docker compose logs -f csms

clean:
	rm -rf .venv .mypy_cache .ruff_cache .pytest_cache .coverage htmlcov coverage.xml dist build
