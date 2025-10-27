#!/usr/bin/env bash
set -euo pipefail

NET=literev-legal_literev
BR="br-$(docker network inspect -f '{{.Id}}' "$NET" | cut -c1-12)"

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  if sudo -n true 2>/dev/null; then SUDO="sudo -n"
  elif [ -n "${SUDO_PASSWORD:-}" ]; then SUDO="sudo -S"
  else
    echo "WARNING: skipping iptables update (no root and no SUDO_PASSWORD)." >&2
    exit 0
  fi
fi
run_ipt() {
  if [ -z "$SUDO" ]; then iptables "$@"
  elif [[ "$SUDO" == *"-S"* ]]; then printf '%s\n' "$SUDO_PASSWORD" | $SUDO iptables "$@"
  else $SUDO iptables "$@"; fi
}

run_ipt -n -L DOCKER-USER >/dev/null 2>&1 || { run_ipt -N DOCKER-USER; run_ipt -I FORWARD 1 -j DOCKER-USER; }

run_ipt -C DOCKER-USER -i "$BR" -o "$BR" -p tcp --dport 6379 -j ACCEPT 2>/dev/null \
  || run_ipt -I DOCKER-USER 1 -i "$BR" -o "$BR" -p tcp --dport 6379 -j ACCEPT
