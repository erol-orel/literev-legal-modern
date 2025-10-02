#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ROOT_DIR="$(git -C "$BASE_DIR" rev-parse --show-toplevel 2>/dev/null)"; then :; else
  ROOT_DIR="$(cd "$BASE_DIR/../../.." && pwd)"
fi

RDIR="$ROOT_DIR/containers/redis"
CFG_DIR="$RDIR/config"
CONF="$CFG_DIR/redis.conf"
PASS_FILE="$CFG_DIR/redis.pass"
ENV_FILE="$ROOT_DIR/.env"

umask 077
mkdir -p "$CFG_DIR"

# --- Create password once if missing ---
if [ ! -s "$PASS_FILE" ]; then
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 36 | tr -d '\n' > "$PASS_FILE"
  else
    python3 - <<'PY' > "$PASS_FILE"
import base64, secrets
print(base64.b64encode(secrets.token_bytes(32)).decode(), end="")
PY
  fi
fi

PASS="$(cat "$PASS_FILE")"
[ -n "$PASS" ] || { echo "ERROR: empty password file at $PASS_FILE"; exit 1; }

# --- Write a fresh redis.conf atomically (no sed/ampersand issues) ---
TMP_CONF="$(mktemp "$CFG_DIR/.redis.conf.XXXXXX")"
cat > "$TMP_CONF" <<EOF
protected-mode yes
user default off
# NOTE: '>' is part of the ACL syntax; clients must NOT include it in REDIS_PASSWORD.
user app on >$PASS ~* &* +@all -@dangerous
rename-command FLUSHALL ""
rename-command FLUSHDB  ""
rename-command CONFIG   ""
rename-command MODULE   ""
rename-command SHUTDOWN ""
EOF
mv "$TMP_CONF" "$CONF"

chmod 0644 "$CONF"
chmod 0644 "$PASS_FILE"   # change to 0600 if only the host reads this file

# --- Update .env REDIS_PASSWORD (append if missing) ---
touch "$ENV_FILE"
cp -a "$ENV_FILE" "$ENV_FILE.bak"

awk -v val="$PASS" '
BEGIN{done=0}
# Match optional leading spaces, optional "export", then REDIS_PASSWORD=
/^[[:space:]]*(export[[:space:]]+)?REDIS_PASSWORD=/ {
  print "REDIS_PASSWORD=" val; done=1; next
}
{print}
END{
  if(!done) print "REDIS_PASSWORD=" val
}
' "$ENV_FILE.bak" > "$ENV_FILE"

# --- Minimal status (mask the secret) ---
echo "redis.conf -> $CONF"
echo "redis.pass -> $PASS_FILE"
awk '/^user[[:space:]]+app[[:space:]]+on/ {sub(/>[^ ]+/,">******"); print}' "$CONF"
echo ".env updated: REDIS_PASSWORD=********"
