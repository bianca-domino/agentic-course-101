#!/usr/bin/env bash
# Job command. Installs pydantic-ai, then runs the evaluation.
set -e
pip install -q -r requirements.txt
python scripts/dev_eval.py
