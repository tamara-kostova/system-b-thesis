SHELL := /bin/bash
.PHONY: start stop restart status logs db test expire build-spe load-vocab

start:
	@bash start.sh

stop:
	@bash stop.sh

restart: stop start

db:
	docker compose up -d postgres
	@echo "Postgres is up on port 5433"

status:
	@echo "Service status:"; \
	shopt -s nullglob; \
	files=(logs/*.pid); \
	if [ $${#files[@]} -eq 0 ]; then echo "  no services started"; exit 0; fi; \
	for f in "$${files[@]}"; do \
		name=$$(basename "$$f" .pid); \
		pid=$$(cat "$$f"); \
		if kill -0 "$$pid" 2>/dev/null; then \
			echo "  running  $$name (pid $$pid)"; \
		else \
			echo "  stopped  $$name (stale pid $$pid)"; \
		fi; \
	done

logs:
	@tail -f logs/*.log

test:
	.venv/bin/python -m pytest tests/ -v

expire:
	curl -sf -X POST http://localhost:8002/permits/expire-due | python3 -m json.tool

build-spe:
	docker build -t system-b-spe:latest -f Dockerfile.spe .

load-vocab:
	.venv/bin/python sql/load_vocab.py --vocab synthea/vocab/
	.venv/bin/python sql/load_vocab.py --remap
