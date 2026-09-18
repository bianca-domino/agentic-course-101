#!/usr/bin/env bash
# Job command. Installs pydantic-ai, then runs the evaluation.
set -e
export PYDANTIC_AI_NO_BANNER=1
pip install -q --no-warn-conflicts -r requirements.txt
python scripts/dev_eval.py
