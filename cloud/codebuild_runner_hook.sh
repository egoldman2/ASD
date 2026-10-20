#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "$0")" && pwd)
exec /usr/bin/python3 -I "$script_dir/codebuild_runner.py" guard
