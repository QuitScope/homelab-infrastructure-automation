# Operations

*[Deutsche Version](operations.md)*

## One-time setup

### Proxmox role, user and token

Role and user can be created over SSH on the host. No password is set; the user only signs in
through tokens:

```bash
pveum role add TerraformProv -privs "VM.Allocate VM.Clone VM.Audit VM.PowerMgmt VM.GuestAgent.Audit VM.Config.CDROM VM.Config.CPU VM.Config.Cloudinit VM.Config.Disk VM.Config.HWType VM.Config.Memory VM.Config.Network VM.Config.Options Datastore.AllocateSpace Datastore.Audit SDN.Use Sys.Audit"
pveum user add terraform@pve --comment "Terraform IaC"
```

Create the token in the UI so the secret is only shown there: **Datacenter → Permissions → API Tokens →
Add**, user `terraform@pve`, token ID `iac`. Then give the role to the token directly:

```bash
pveum acl modify / -token 'terraform@pve!iac' -role TerraformProv
```

> A token with *privilege separation* has no permissions until an ACL points at the token itself.
> It does not inherit the user's permissions in that case, and the result is
> `403 Permission check failed (/vms/900, VM.Clone)` (see test protocol).

Then put the secret into `.env` once (template: `.env.example`); `scripts/vault-seed.sh` stores it in
HashiCorp Vault (see [HashiCorp Vault](#hashicorp-vault)):

```
PROXMOX_VE_API_TOKEN=terraform@pve!iac=<secret>
```

### Tools

```bash
scripts/tf.sh init        # downloads the bpg/proxmox provider as pinned in .terraform.lock.hcl
scripts/ansible.sh true   # builds the homelab-ansible image (ansible-core, collections)
```

## Day-to-day operations

| Task | Command |
|---|---|
| Review changes | `scripts/tf.sh plan` |
| Create/update the VM | `scripts/tf.sh apply` |
| VM IP address | `scripts/vm-ip.sh` (or `scripts/vm-ip.sh <MAC>`) |
| Configure the VM | `LAB_VM_IP=<ip> scripts/ansible.sh ansible-playbook playbooks/site.yml` |
| Check only, change nothing | `... ansible-playbook playbooks/site.yml --check --diff` |
| Run the CI lints locally | `scripts/ansible.sh sh -c 'cd /work && yamllint --strict . && cd ansible && ansible-lint'` |
| Remove the VM | `scripts/tf.sh destroy` |

After `destroy` and another `apply` the VM has new host keys. The Ansible container starts with an
empty `known_hosts` every time, so that is no problem there. For your own SSH sessions run
`ssh-keygen -R <ip>` first. The FritzBox does not necessarily hand out the same IP despite the fixed
MAC, so look the IP up again with `vm-ip.sh` after every `apply`.

## Deploying the SOC portal

```bash
scripts/ansible.sh ansible-playbook playbooks/soc-portal.yml                                 # state of main
scripts/ansible.sh ansible-playbook playbooks/soc-portal.yml -e soc_portal_version=<commit> # fixed commit / rollback
```

Role `soc_portal` checks out `QuitScope/homelab-soc-portal` into `/opt/homelab-soc-portal`, places the
`.env` from HashiCorp Vault (`homelab/soc-portal`) and starts the compose project
`homelab-soc-portal`. The image is only rebuilt when the checkout changed. The SQLite database lives in the
volume `homelab-soc-portal_portal-data` and survives every redeployment.

One-time prerequisites:

1. HashiCorp Vault is running and `.env` holds `VAULT_ADDR` and the `ansible` AppRole
   (`ANSIBLE_HASHI_VAULT_ROLE_ID`/`_SECRET_ID`); `scripts/ansible.sh` passes them to Ansible.
2. Deploy key: the role creates `/root/.ssh/homelab-soc-portal-deploy` on siem-docker on the first run.
   Add the public key once as a read-only deploy key to the portal repository:
   ```bash
   ssh root@192.168.178.91 cat /root/.ssh/homelab-soc-portal-deploy.pub > deploy.pub
   gh repo deploy-key add deploy.pub --repo QuitScope/homelab-soc-portal --title "siem-docker (Ansible, read-only)"
   ```

Changing the portal configuration:

Write the new `.env` to `homelab/soc-portal` (field `env`), see [HashiCorp Vault](#hashicorp-vault), then:

```bash
scripts/ansible.sh ansible-playbook playbooks/soc-portal.yml     # recreates the container with the new .env
```

The switch from the old deployment, copied with `git archive`, happens once and automatically: the old
directory is moved to `/opt/homelab-soc-portal.pre-ansible`. It can be deleted after a check.

## ARA dashboard

[ARA Records Ansible](https://ara.recordsansible.org/) records every playbook run: hosts, tasks,
`changed`/`ok`/`failed`, diffs, duration and the playbook files used. Web UI and API:
http://192.168.178.91:8091 (LAN only).

```bash
scripts/ansible.sh ansible-playbook playbooks/ara.yml           # deploy/update the server
ARA_API_SERVER= scripts/ansible.sh ansible-playbook ...         # do not record a single run
```

- Server: role `ara`, compose project `ara` in `/opt/ara` on siem-docker. The image is pinned by digest
  (ARA 1.8.0) because upstream only publishes rolling tags. SQLite and the `settings.yaml` generated on first
  start live in the volume `ara_ara-data`.
- Client: `scripts/ansible.sh` enables the ARA callback plugin and sets `ARA_API_SERVER`. If the server
  is unreachable the playbook still runs; ARA then only prints `[WARNING]: Callback dispatch ... failed` (tested, exit code 0).
- What is not stored: results of tasks with `no_log` (e.g. the portal `.env`) only show up as "censored".
  ARA ignores `extra_vars` and vault password files by default.
- Limit: the dashboard has no login and is only bound to the LAN address. Anyone on the LAN can read and
  write runs. Next step: `ARA_READ_LOGIN_REQUIRED`/`ARA_WRITE_LOGIN_REQUIRED` with a user whose password lives
  in the vault.
- Clean up: `ssh root@192.168.178.91 docker exec ara-ara-1 ara playbook prune --days 30 --confirm`.

## HashiCorp Vault

Vault (2.2.0, Raft storage) runs on siem-docker at http://192.168.178.91:8200 (LAN only, HTTP). It holds
the secrets that Terraform and Ansible fetch at runtime:

| Path (KV v2, mount `homelab`) | Field | Reader (AppRole → policy) |
|---|---|---|
| `homelab/proxmox` | `api_token` | `terraform` → `terraform-proxmox` |
| `homelab/soc-portal` | `env` (the whole portal `.env`) | `ansible` → `ansible-soc-portal` |

Each AppRole may read exactly its own secret; tokens live 15 minutes. Terraform reads the Proxmox token
as an ephemeral resource, so it never lands in the state. Every access is in the audit log
(`/vault/logs/audit.log` inside the container).

Setup in four steps (one-time, done exactly like this, see test protocol):

```bash
scripts/ansible.sh ansible-playbook playbooks/vault.yml                       # 1. deploy the server
scripts/vault-init.sh                                                          # 2. init, unseal key + root token → Ansible Vault
scripts/ansible.sh ansible-playbook playbooks/vault.yml                       #    unseal
TF_DIR=terraform/vault scripts/tf.sh init
TF_DIR=terraform/vault scripts/vault-admin.sh scripts/tf.sh apply              # 3. mount, audit, policies, AppRoles
scripts/vault-admin.sh scripts/vault-seed.sh                                   # 4. secrets + AppRole IDs into .env
```

`vault-seed.sh` reads the Proxmox token from `.env` and the portal `.env` from siem-docker and pipes both
into Vault. Afterwards `PROXMOX_VE_API_TOKEN` can be removed from `.env`.

Operations:

| Task | Procedure |
|---|---|
| After a restart of siem-docker or Vault | Vault starts sealed: `scripts/ansible.sh ansible-playbook playbooks/vault.yml` unseals it |
| Change the portal configuration | Write the new `.env` with `vault kv put` or re-run `vault-seed.sh`, then `playbooks/soc-portal.yml` |
| Rotate the Proxmox token | Create a new token (see above), write it to `homelab/proxmox`. `.env` stays unchanged |
| Rotate an AppRole secret ID | `TF_DIR=terraform/vault scripts/vault-admin.sh scripts/tf.sh apply -replace='vault_approle_auth_backend_role_secret_id.consumer["ansible"]'`, then `vault-seed.sh` |
| Who read what? | `ssh root@192.168.178.91 docker exec vault-vault-1 cat /vault/logs/audit.log` (JSON, values HMAC'd) |
| Backup | `docker exec vault-vault-1 vault operator raft snapshot save /vault/file/backup.snap` (with the root token) |

Important: the unseal key and root token only live in `playbooks/files/siem-docker/vault-init.json.vault`,
encrypted with the password from `.vault_pass`. If `.vault_pass` is lost, Vault cannot be unsealed after the
next restart and its data is gone. Keep `.vault_pass` in a password manager as well.

## Updates

| What | Procedure |
|---|---|
| Packages on the VMs | Re-run the playbook (role `base` runs `apt upgrade safe`). `unattended-upgrades` also installs security updates daily |
| Terraform provider | Raise `version` in `terraform/versions.tf`, `scripts/tf.sh init -upgrade`, review `plan`, commit the lock file |
| Terraform itself | Change the image tag in `scripts/tf.sh` and `terraform_version` in `.github/workflows/ci.yml` together |
| Ansible / linters / collections | Raise versions in `ansible/requirements.txt` and `ansible/requirements.yml`; the image is rebuilt on the next `scripts/ansible.sh`, CI uses the same files |
| Template 900 | Build a new template, set `template_id`, `apply` replaces the VM. Then run the playbook |

Every change goes through a push; CI must be green before it runs against the lab.

## Recovery

| Situation | Procedure |
|---|---|
| VM broken or misconfigured | `scripts/tf.sh apply -replace=proxmox_virtual_environment_vm.lab`, then the playbook. The VM holds no data of its own, everything is rebuilt from the repository (tested, see test protocol) |
| Configuration drift | Re-run the playbook, it restores the desired state. `--check --diff` shows the differences first |
| Locked out by SSH hardening | Proxmox console (`qm terminal 220`, serial console) or replace the VM. `sshd -t` validates every change before it is written, which makes this unlikely |
| Terraform state lost | `scripts/tf.sh import proxmox_virtual_environment_vm.lab pve/220`, then `plan` |
| Token compromised | Delete it in the UI (or `pveum user token remove terraform@pve iac`), create a new one, set the ACL, replace the value in Vault `homelab/proxmox` |
| Broken portal update | Redeploy with `-e soc_portal_version=<last good commit>`; the database in the volume is not touched |
| Vault sealed | `scripts/ansible.sh ansible-playbook playbooks/vault.yml` (tested after `docker restart`) |
| Vault data lost | Restore a Raft snapshot (`vault operator raft snapshot restore`) or rebuild: apply `terraform/vault` and run `vault-seed.sh`; the sources of the secrets (Proxmox, portal `.env` on siem-docker) remain |
| `.vault_pass` lost | The unseal key can no longer be read. While Vault still runs unsealed: take a snapshot and re-initialise. Otherwise rebuild Vault (row above) |
| Template 900 gone | Linked clones depend on the template's base disk; Proxmox refuses to delete it while clones exist. Rebuild the template from the Ubuntu cloud image and update `template_id` |

## Secrets

| Secret | Where it lives |
|---|---|
| Proxmox API token | HashiCorp Vault `homelab/proxmox`, read by Terraform at runtime (ephemeral, not in the state) |
| Portal configuration (Splunk/Cribl access, session secret, admin hash) | HashiCorp Vault `homelab/soc-portal`, read by Ansible at runtime |
| AppRole role/secret IDs | `.env` (git-ignored); secret IDs also in the local state of `terraform/vault` |
| Unseal key and root token | `playbooks/files/siem-docker/vault-init.json.vault`, Ansible Vault AES256, committed |
| Ansible Vault password | `.vault_pass` (git-ignored), mode 0600 inside the container |
| Admin PC SSH key | stays in `~/.ssh`, mounted read-only into the container |
| Deploy key for the portal repository | only on siem-docker, read-only and limited to one repository |

Ansible Vault now only protects the bootstrap material Vault itself needs to start. Everything else lives
in HashiCorp Vault.

Deliberate limits and next steps:

- Vault speaks HTTP on the LAN. Next step: a TLS listener with an own CA; clients then need `VAULT_CACERT`.
- One unseal key share (1 of 1) instead of e.g. 3 of 5, and no auto-unseal.
- The root token is used for administration (`terraform/vault`, `vault-seed.sh`). In production it would be
  revoked after setup and regenerated with `vault operator generate-root` when needed.
- CI: GitHub OIDC (JWT auth) instead of stored secret IDs once pipelines run against the lab.
- SSH secrets engine for short-lived SSH certificates instead of static keys.
