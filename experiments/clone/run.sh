#!/bin/bash
# Thin launcher: picks the right reused venv for each step. Everything stays local and CPU-only.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"; avatar="$here/../avatar"
export CUDA_VISIBLE_DEVICES="" HF_HOME="$avatar/voice/hf" OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"
case "${1:-}" in
 voice) shift; exec "$avatar/voice/.venv/bin/python" "$here/clone_voice.py" "$@" ;;
 roi)   shift; exec "$avatar/.venv/bin/python" "$here/pick_roi.py" "$@" ;;
 face)  shift; exec "$avatar/voice/.venv/bin/python" "$here/render_face.py" "$@" ;;
 compose) shift; exec "$avatar/.venv/bin/python" "$here/compose.py" "$@" ;;
 *) echo "usage: run.sh voice|roi|face|compose ARGS" >&2; exit 2 ;;
esac
