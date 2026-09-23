#!/usr/bin/env bash
# Run TLC on a .tla spec. Downloads tla2tools.jar to ~/.tla2tools on first use.
# Usage: tlc.sh Spec.tla [Spec.cfg] [extra tlc args...]
set -euo pipefail

JAR_DIR="$HOME/.tla2tools"
JAR="$JAR_DIR/tla2tools.jar"

if [ ! -f "$JAR" ]; then
  mkdir -p "$JAR_DIR"
  echo "Downloading tla2tools.jar (TLC model checker) to $JAR_DIR ..." >&2
  curl -fsSL -o "$JAR" https://github.com/tlaplus/tlaplus/releases/latest/download/tla2tools.jar
fi

SPEC="${1:?usage: tlc.sh Spec.tla [Spec.cfg] [extra args...]}"
shift || true

CFG_ARG=""
if [ "${1:-}" ] && [[ "$1" == *.cfg ]]; then
  CFG_ARG="-config $1"
  shift
fi

java -XX:+UseParallelGC -cp "$JAR" tlc2.TLC $CFG_ARG "$@" "$SPEC"
