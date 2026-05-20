#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
docker build -t brogrammer/sandbox:latest -f Dockerfile.sandbox .
echo "Built brogrammer/sandbox:latest"
