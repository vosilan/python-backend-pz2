PYTHON ?= .venv/bin/python
XZPACK = $(PYTHON) src/xzpack.py

.PHONY: install examples server demo test lint

install:
	python3 -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt

examples:
	$(XZPACK) results/text.xz < examples/text.txt
	$(XZPACK) results/profiles.xz < examples/profiles.json
	$(XZPACK) results/access.xz < examples/access.csv
	head -c 4096 /dev/urandom | $(XZPACK) results/random.xz
	$(XZPACK) results/empty.xz < /dev/null

server:
	$(PYTHON) src/app.py

demo:
	$(PYTHON) src/demo.py

test:
	$(PYTHON) -m coverage run -m pytest
	$(PYTHON) -m coverage report

lint:
	$(PYTHON) -m flake8 src tests
