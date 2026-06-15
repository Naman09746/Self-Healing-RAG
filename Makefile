# Self-Healing RAG Pipeline - Command Center

.PHONY: setup run-backend run-frontend run test lint clean
.PHONY: db-migrate db-check db-history db-upgrade db-rollback

# Default: setup and run everything
all: setup run

setup:
	@echo "🚀 Setting up the environment..."
	python3 -m venv .venv
	. .venv/bin/activate && pip install -e ".[dev]"
	cd frontend && npm install

run-backend:
	@echo "🔥 Starting Backend API..."
	. .venv/bin/activate && uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8001

run-frontend:
	@echo "🎨 Starting Frontend Dashboard..."
	cd frontend && npm run dev

# Run both backend and frontend (requires tmux or parallel execution, or just instructions)
run:
	@echo "💡 To run the full system, please start backend and frontend in separate terminals:"
	@echo "👉 Terminal 1: make run-backend"
	@echo "👉 Terminal 2: make run-frontend"

test:
	@echo "🧪 Running tests..."
	. .venv/bin/activate && export PYTHONPATH=$$PYTHONPATH:. && pytest backend/tests

lint:
	@echo "🧹 Linting code..."
	. .venv/bin/activate && ruff check .
	. .venv/bin/activate && mypy backend

clean:
	@echo "🧹 Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	rm -rf build/ dist/ *.egg-info

## ------ Phase 2A: Database (PostgreSQL) ------

db-migrate:  ## [Phase 2A] Create a new migration revision (autogenerate)
	PYTHONPATH=. alembic revision --autogenerate -m "$(filter-out $@,$(MAKECMDGOALS))"

db-check:  ## [Phase 2A] Show current migration status
	PYTHONPATH=. alembic current

db-history:  ## [Phase 2A] Show migration history
	PYTHONPATH=. alembic history --verbose

db-upgrade:  ## [Phase 2A] Run Alembic migrations to latest revision
	PYTHONPATH=. alembic upgrade head

db-rollback:  ## [Phase 2A] Roll back the last migration
	PYTHONPATH=. alembic downgrade -1

downgrade: db-rollback  ## Alias for db-rollback

db-fresh:  ## [Phase 2A] Drop all tables and re-migrate (dev only!)
	PYTHONPATH=. alembic downgrade base && PYTHONPATH=. alembic upgrade head

db-migrate-sqlite:  ## [Phase 2A] Copy SQLite data to Postgres
	PYTHONPATH=. python scripts/migrate_sqlite_to_postgres.py

## ------ Phase 6: Security ------

test-security:  ## [Phase 6] Run all security unit tests
	. .venv/bin/activate && export PYTHONPATH=$$PYTHONPATH:. && pytest backend/tests/unit/test_security_jwt.py backend/tests/unit/test_security_audit.py backend/tests/unit/test_security_prompt_injection.py backend/tests/unit/test_security_rate_limit.py backend/tests/unit/test_security_rbac.py -v

test-security-quick:  ## [Phase 6] Run a quick security smoke test
	. .venv/bin/activate && export PYTHONPATH=$$PYTHONPATH:. && pytest backend/tests/unit/test_security_jwt.py backend/tests/unit/test_security_rate_limit.py -v

## ------ Phase 5: Evaluation Framework ------

eval-run:  ## [Phase 5] Run full offline evaluation
	PYTHONPATH=. python scripts/run_eval.py

eval-quick:  ## [Phase 5] Quick smoke-test evaluation (limit=2)
	PYTHONPATH=. python scripts/run_eval.py --limit 2

eval-queue:  ## [Phase 5] Enqueue evaluation via Redis queue
	PYTHONPATH=. python scripts/run_eval.py --queue

eval-custom:  ## [Phase 5] Run evaluation on a custom dataset
	PYTHONPATH=. python scripts/run_eval.py --dataset $(D)

eval-report:  ## [Phase 5] Show the latest JSON report
	@echo "Latest report: $$(ls -t eval_results/*.json 2>/dev/null | head -1)"
	@cat $$(ls -t eval_results/*.json 2>/dev/null | head -1) 2>/dev/null || echo "No reports found"

eval-clean:  ## [Phase 5] Remove all evaluation results
	rm -rf eval_results

test-eval:  ## [Phase 5] Run all evaluation tests (unit + integration + e2e)
	. .venv/bin/activate && export PYTHONPATH=$$PYTHONPATH:. && pytest backend/tests/unit/test_evaluation_agent.py backend/tests/unit/test_evaluation_runner.py backend/tests/unit/test_evaluation_queue.py -v

test-eval-integration:  ## [Phase 5] Run integration tests for evaluation
	. .venv/bin/activate && export PYTHONPATH=$$PYTHONPATH:. && pytest backend/tests/integration/test_evaluation_pipeline.py -v

test-eval-e2e:  ## [Phase 5] Run end-to-end tests for evaluation
	. .venv/bin/activate && export PYTHONPATH=$$PYTHONPATH:. && pytest backend/tests/e2e/test_evaluation_e2e.py -v --e2e
