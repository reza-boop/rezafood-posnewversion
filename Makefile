# RezaFood POS — developer convenience targets
.PHONY: run run-desktop run-web test lint backup clean

PYTHON := python3

run:
	$(PYTHON) launcher.py

run-desktop:
	$(PYTHON) launcher.py --desktop

run-web:
	$(PYTHON) launcher.py --web

test:
	$(PYTHON) -m pytest

cov:
	$(PYTHON) -m pytest --cov=. --cov-report=term-missing --cov-report=html

lint:
	$(PYTHON) -m flake8 . --max-line-length=100 --exclude=.git,__pycache__,logs,backups,exports,receipts

backup:
	$(PYTHON) -c "from utils import backup_db, ensure_dirs; ensure_dirs(); p=backup_db(); print('Backup saved to', p)"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .coverage logs
