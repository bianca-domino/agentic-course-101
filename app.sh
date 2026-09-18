#!/usr/bin/env bash
# Domino serves Apps on port 8888.
set -e
pip install -q -r requirements.txt
python app/server.py
