#!/usr/bin/env bash
# Four independent game briefs share a single temporary CPU inference process.
set -euo pipefail
platform=$GITHUB_WORKSPACE
out="$RUNNER_TEMP/game-benchmark"
mkdir -p "$out"
work=$(mktemp -d)
cd "$work"
python -m pip -q install "mcp==1.26.0" "httpx==0.28.1" "pillow==12.1.1"
curl -fLsS --retry 3 https://github.com/ggml-org/llama.cpp/releases/download/b12578/llama-b12578-bin-ubuntu-x64.tar.gz -o llama.tgz
curl -fLsS --retry 3 https://huggingface.co/mradermacher/Kimi-VL-A3B-Instruct-GGUF/resolve/main/Kimi-VL-A3B-Instruct.Q3_K_S.gguf -o model.gguf
sha=ac24c61aa01cee11cb0cfab8b497bd0f14276ec9b16601022a7b581ca8c4516a
echo "$sha  model.gguf" | sha256sum -c -
echo '95db6800c6321c2c64360850e8fa5ea848c65ef3850205d2aea57eb0de001ca1  llama.tgz' | sha256sum -c -
tar -xzf llama.tgz
binary=$(find "$work" -name llama-server -type f -print -quit)
export LD_LIBRARY_PATH="$(dirname "$binary")"
export HUD_LLAMA_PORT=18490
model=Kimi-VL-A3B-Instruct.Q3_K_S
"$binary" -m model.gguf --alias "$model" --port "$HUD_LLAMA_PORT" --host 127.0.0.1 -c 4096 -np 2 -t 4 --reasoning-budget 0 >model.log 2>&1 &
pid=$!
trap 'kill "$pid" 2>/dev/null || true' EXIT
curl -fsS --retry 90 --retry-all-errors --retry-delay 1 "http://127.0.0.1:$HUD_LLAMA_PORT/health" || { tail -30 model.log; exit 1; }
review() {
  local slug=$1 game=$2
  local dest="$out/$slug"
  mkdir -p "$dest"
  python "$platform/studio/hud/compare.py" "$game" "$dest/kimi.json" --model "$model" --weights-sha256 "$sha"
  python "$platform/studio/hud/author.py" "$game" "$dest" --model "$model"
}
pids=()
for slug in atlas freight soccer mosaic; do
  game="$platform/games/$slug"
  if [[ "$slug" == atlas ]]; then game=$platform; fi
  review "$slug" "$game" &
  pids+=($!)
done
failed=0
for worker in "${pids[@]}"; do wait "$worker" || failed=1; done
exit "$failed"
