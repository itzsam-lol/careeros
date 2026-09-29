# Thin wrapper around scripts/dev.py (which also works on Windows without make).
PY ?= python

.PHONY: setup dev api worker web mobile db migrate test test-unit lint typecheck format gen-types seed

setup:      ; $(PY) scripts/dev.py setup
dev:        ; $(PY) scripts/dev.py dev
api:        ; $(PY) scripts/dev.py api
worker:     ; $(PY) scripts/dev.py worker
web:        ; $(PY) scripts/dev.py web
mobile:     ; $(PY) scripts/dev.py mobile
db:         ; $(PY) scripts/dev.py db
migrate:    ; $(PY) scripts/dev.py migrate
test:       ; $(PY) scripts/dev.py test
test-unit:  ; $(PY) scripts/dev.py test --unit
lint:       ; $(PY) scripts/dev.py lint
typecheck:  ; $(PY) scripts/dev.py typecheck
format:     ; $(PY) scripts/dev.py format
gen-types:  ; $(PY) scripts/dev.py gen-types
seed:       ; $(PY) scripts/dev.py seed
