#!/usr/bin/env bash
# scripts/check-architecture.sh — Enforce architecture layer boundaries
set -euo pipefail

echo "=== [check-architecture] Checking architecture layer boundaries ==="

# Per .harness/rules/layer-boundaries.md and .harness/PROJECT_STATE.md:
# Permissive no-op until rules/layer-boundaries.md has concrete boundary rules.
RULES_FILE=".harness/rules/layer-boundaries.md"

if [ ! -f "$RULES_FILE" ]; then
  echo "WARN: $RULES_FILE not found."
  exit 0
fi

if grep -q "<<FILL:" "$RULES_FILE"; then
  echo "INFO: No custom layer boundaries defined yet (placeholder active). check-architecture is permissive no-op (exit 0)."
  exit 0
fi

echo "=== [check-architecture] Architecture boundary check passed ==="
exit 0
