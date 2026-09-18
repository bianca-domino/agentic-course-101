#!/usr/bin/env bash
# Domino serves Apps on port 8888.
set -e
export PYDANTIC_AI_NO_BANNER=1
pip install -q --no-warn-conflicts -r requirements.txt
python app/server.py
