#!/usr/bin/env bash
# Writes the homelab secrets into Vault and the AppRole credentials into .env. Values only travel
# through pipes, nothing is printed. Run after terraform/vault is applied:
#   scripts/vault-admin.sh scripts/vault-seed.sh
set -euo pipefail
cd "$(dirname "$0")/.."
: "${VAULT_TOKEN:?run through scripts/vault-admin.sh}"
addr="$(grep '^VAULT_ADDR=' .env | cut -d= -f2-)"
siem="${SIEM_HOST:-192.168.178.91}"

# Python from the Ansible image, so the script does not depend on a local interpreter.
py() { ARA_API_SERVER= scripts/ansible.sh python3 -c "$1"; }
kv_put() { # kv_put <path> <field>   (value from stdin)
  py "import json,sys; print(json.dumps({'data': {'$2': sys.stdin.read()}}))" |
    curl -sf -o /dev/null -X POST -H "X-Vault-Token: $VAULT_TOKEN" --data @- "$addr/v1/homelab/data/$1"
  echo "stored homelab/$1 ($2)"
}

grep '^PROXMOX_VE_API_TOKEN=' .env | cut -d= -f2- | tr -d '\r\n' | kv_put proxmox api_token
ssh -o BatchMode=yes "root@$siem" cat /opt/homelab-soc-portal/.env | kv_put soc-portal env

# AppRole credentials for the two consumers (terraform/, Ansible lookups) into .env.
ids="$(TF_DIR=terraform/vault scripts/tf.sh output -json role_ids)"
secrets="$(TF_DIR=terraform/vault scripts/tf.sh output -json secret_ids)"
field() { printf '%s' "$1" | py "import json,sys; print(json.load(sys.stdin)['$2'], end='')"; }
keep="$(grep -v -E '^(TF_VAR_vault_role_id|TF_VAR_vault_secret_id|ANSIBLE_HASHI_VAULT_ROLE_ID|ANSIBLE_HASHI_VAULT_SECRET_ID)=' .env)"
{
  printf '%s\n' "$keep"
  printf 'TF_VAR_vault_role_id=%s\n' "$(field "$ids" terraform)"
  printf 'TF_VAR_vault_secret_id=%s\n' "$(field "$secrets" terraform)"
  printf 'ANSIBLE_HASHI_VAULT_ROLE_ID=%s\n' "$(field "$ids" ansible)"
  printf 'ANSIBLE_HASHI_VAULT_SECRET_ID=%s\n' "$(field "$secrets" ansible)"
} > .env.new && mv .env.new .env
echo "wrote AppRole credentials to .env"
