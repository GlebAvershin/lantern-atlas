#!/usr/bin/env bash
# Ubuntu CI worker. All downloaded model tools and inputs use fixed content digests.
set -euo pipefail
game=$(cd "$1" && pwd)
out=$2
studio=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d)
pid=
cleanup() {
  if [[ -n "$pid" ]]; then kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; fi
  rm -rf "$work"
}
trap cleanup EXIT
cd "$work"
python -m venv env
py="$work/env/bin/python"
"$py" -m pip -q install -r "$studio/requirements.txt"
"$py" "$studio/check_routes.py"
"$py" -m playwright install --with-deps chromium >browser-install.log
curl -fsSL --retry 3 https://github.com/ggml-org/llama.cpp/releases/download/b12578/llama-b12578-bin-ubuntu-x64.tar.gz -o llama.tgz
curl -fsSL --retry 3 https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf -o qwen.gguf
sha256sum -c <<'SUMS'
95db6800c6321c2c64360850e8fa5ea848c65ef3850205d2aea57eb0de001ca1  llama.tgz
74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db  qwen.gguf
SUMS
tar -xzf llama.tgz
binary=$(find "$work" -name llama-server -type f -print -quit)
export LD_LIBRARY_PATH="$(dirname "$binary")"
"$binary" -m qwen.gguf --alias qwen --port 18490 --host 127.0.0.1 -c 2048 -np 1 -t 2 >model.log 2>&1 &
pid=$!
curl -fsS --retry 45 --retry-all-errors --retry-delay 1 http://127.0.0.1:18490/health
"$py" "$studio/author.py" "$game" "$out" --model qwen
"$py" "$studio/measure.py" "$game" "$out"
# Package the same read-only app for local review or Databricks Apps.
app="$work/review-app"
mkdir -p "$app/proof"
cp "$studio/desk/"{app.yaml,desk.py,requirements.txt} "$app/"
cp "$out/"{authoring.json,geometry.json,screen.html} "$app/proof/"
"$py" -m pip -q install -r "$app/requirements.txt"
DATABRICKS_APP_PORT=18491 "$py" "$app/desk.py" >desk.log 2>&1 &
desk_pid=$!
trap 'kill "$desk_pid" 2>/dev/null || true; cleanup' EXIT
curl -fsS --retry 10 --retry-all-errors --retry-delay 1 http://127.0.0.1:18491/metrics
go run "$studio/probe.go" http://127.0.0.1:18491 "$(git -C "$game" rev-parse HEAD)" >"$out/desk-probe.json"
node "$studio/summary.mjs" "$out" "$game/docs/evidence/hud"
tar -czf "$out/review-app.tgz" -C "$app" app.yaml desk.py requirements.txt proof
