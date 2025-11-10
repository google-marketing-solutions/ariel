#!/bin/bash

if [ -f "configuration.yaml" ]; then
  eval $(python3 -c 'import yaml, sys;
config = yaml.safe_load(sys.stdin);
if config:
  for k, v in config.items():
    print(f"export {k}=\"{v}\"")' < configuration.yaml)
fi

python3 -m debugpy --listen 0.0.0.0:5678 -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload
