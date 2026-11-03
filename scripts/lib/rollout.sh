#!/usr/bin/env bash
# scripts/lib/rollout.sh — Shared helpers for rolling Deployments when their mounted code changes.
#
# Python services in Argus load their source from a ConfigMap at process start. Updating the
# ConfigMap refreshes the file on disk (eventually) but NOT the running interpreter, and since the
# Deployment spec is unchanged Kubernetes never rolls a new pod. This leaves stale (potentially
# pre-security-fix) code running indefinitely — see GitHub issue #10.
#
# roll_on_code_change stamps a content checksum of the source files onto the pod template as
# `argus.io/code-checksum`. Kubernetes rolls the Deployment only when the checksum actually changes,
# so re-running an apply script with unchanged code is a no-op.
#
# Usage (source this file, then):
#   roll_on_code_change <namespace> <deployment> <file> [<file>...]

_argus_sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    cat "$@" | sha256sum | awk '{print $1}'
  else
    cat "$@" | shasum -a 256 | awk '{print $1}'
  fi
}

roll_on_code_change() {
  local namespace="$1" deployment="$2"
  shift 2
  if [ "$#" -eq 0 ]; then
    echo "roll_on_code_change: no source files given for ${deployment}" >&2
    return 1
  fi

  local checksum current
  checksum="$(_argus_sha256 "$@")"
  current="$(kubectl get "deployment/${deployment}" -n "${namespace}" \
    -o jsonpath='{.spec.template.metadata.annotations.argus\.io/code-checksum}' 2>/dev/null || true)"

  if [ "${current}" = "${checksum}" ]; then
    echo "    [=] ${deployment}: code unchanged (checksum ${checksum:0:12}), no rollout needed"
    return 0
  fi

  echo "    [~] ${deployment}: code checksum ${current:0:12}${current:+ -> }${checksum:0:12}, rolling pods..."
  kubectl patch "deployment/${deployment}" -n "${namespace}" --type=merge \
    -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"argus.io/code-checksum\":\"${checksum}\"}}}}}" >/dev/null
}
