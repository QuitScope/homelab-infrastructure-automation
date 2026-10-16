#!/usr/bin/env bash
# Runs a command with the Vault root token in VAULT_TOKEN, taken from the Ansible Vault encrypted init file.
# Only for administration (terraform/vault, scripts/vault-seed.sh); day-to-day runs use AppRoles.
# Usage: scripts/vault-admin.sh <command> [args...]
set -euo pipefail
cd "$(dirname "$0")/.."
VAULT_TOKEN="$(ARA_API_SERVER= scripts/ansible.sh sh -c \
  'ansible-vault view playbooks/files/siem-docker/vault-init.json.vault | python3 -c "import json,sys; print(json.load(sys.stdin)[\"root_token\"])"' | tr -d '\r')"
export VAULT_TOKEN
exec "$@"
