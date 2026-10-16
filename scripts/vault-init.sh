#!/usr/bin/env bash
# One-time bootstrap: initialises Vault and stores the unseal key and root token Ansible Vault encrypted.
# The plaintext only travels through this pipe; it is never written to disk or shown.
# Afterwards run: scripts/ansible.sh ansible-playbook playbooks/vault.yml   (unseals Vault)
set -euo pipefail
cd "$(dirname "$0")/.."
host="${VAULT_HOST:-192.168.178.91}"
out=playbooks/files/siem-docker/vault-init.json.vault
[ -f .vault_pass ] || { echo "Missing .vault_pass (Ansible Vault password)." >&2; exit 1; }
[ ! -e "ansible/$out" ] || { echo "ansible/$out exists already; Vault was initialised before." >&2; exit 1; }
# 1 key share keeps the homelab simple; production would use e.g. 5 shares with a threshold of 3.
ssh -o BatchMode=yes "root@$host" \
  'docker exec vault-vault-1 vault operator init -address=http://127.0.0.1:8200 -key-shares=1 -key-threshold=1 -format=json' |
  ARA_API_SERVER= scripts/ansible.sh ansible-vault encrypt --output "$out"
echo "Stored Vault init output in ansible/$out"
