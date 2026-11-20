#!/usr/bin/env bash
# Build from an allowlist so model runners never receive the game checkout or local credentials.
set -euo pipefail
platform=$1
game=$2
project=$3
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
mkdir -p "$stage/platform" "$stage/game"
cp "$platform"/studio/{pyproject.toml,uv.lock} "$stage/platform/"
cp "$platform/studio/agents/gateway.py" "$stage/platform/"
case "$project" in
  atlas)
    cp "$game"/studio/{agent_review.py,chart_mcp.py,oracle.cpp} "$stage/game/"
    cp -r "$game/studio/briefs" "$stage/game/"
    ;;
  soccer)
    mkdir -p "$stage/game/scripts" "$stage/game/content"
    cp "$game"/scripts/{agent_review.py,event_studio.py} "$stage/game/scripts/"
    cp "$game/content/continental-cup.json" "$stage/game/content/"
    ;;
  freight)
    mkdir -p "$stage/game/analysis"
    cp "$game"/analysis/{agent_review.py,compass_report.py,compass_funnel.sql,synthetic_compass_counts.csv,pyproject.toml,uv.lock} "$stage/game/analysis/"
    ;;
  *) exit 2 ;;
esac
cp "$platform/studio/agents/Dockerfile" "$stage/"
docker build -t studio-review:ci "$stage"
