# Test protocol

[Deutsche Version](test-protocol.md)

All commands actually ran against the homelab on 2026-10-16 (Proxmox VE 9.2.11, node `pve`).
Output is shortened but not altered. IP addresses are replaced with placeholders (`<VM-IP>`, `<LAB-VM-IP>`, `<ADMIN-PC-IP>`, see README).

Tools: Terraform 1.16.6 (`hashicorp/terraform`), bpg/proxmox 0.116.1, ansible-core 2.21.5,
ansible-lint 26.10.1, yamllint 1.38.0, ansible.posix 2.2.2, community.general 13.5.0, community.docker 5.4.0, ara 1.8.0, community.hashi_vault 7.1.0,
hvac 2.4.0, hashicorp/vault provider 5.13.0, Vault 2.2.0.

## 1. Static checks (local and CI)

```
$ scripts/ansible.sh sh -c 'cd /work && yamllint --strict . && cd ansible && ansible-lint && ansible-playbook --syntax-check playbooks/site.yml'
Passed: 0 failure(s), 0 warning(s) in 16 files processed of 19 encountered. Last profile that met the validation criteria was 'production'.
playbook: playbooks/site.yml

$ scripts/tf.sh fmt -check -recursive && scripts/tf.sh validate
Success! The configuration is valid.
```

GitHub Actions: workflow `CI` (jobs `terraform` and `ansible`) green on `main`.

## 2. Terraform: first apply fails (finding)

```
$ scripts/tf.sh apply lab.tfplan
Error: VM clone
#1: error cloning VM: received an HTTP 403 response - Reason: Permission check failed (/vms/900, VM.Clone)

$ pveum user token list terraform@pve
│ iac     │         │      0 │ 1       │   # privsep = 1
```

Cause: the token was created with privilege separation and therefore does not inherit the user's
permissions. Fix: assign the role to the token directly; no new token needed:

```
$ pveum acl modify / -token 'terraform@pve!iac' -role TerraformProv
```

## 3. Terraform: apply, drift check

```
$ scripts/tf.sh plan -out=lab.tfplan
Plan: 1 to add, 0 to change, 0 to destroy.

$ scripts/tf.sh apply lab.tfplan
proxmox_virtual_environment_vm.lab: Creation complete after 4s [id=220]
Apply complete! Resources: 1 added, 0 changed, 0 destroyed.
mac_address = "BC:24:11:22:00:01"
vm_id = 220
vm_name = "lab-iac-01"

$ scripts/tf.sh plan -detailed-exitcode
No changes. Your infrastructure matches the configuration.        (exit 0)

$ qm config 220
agent: enabled=0,fstrim_cloned_disks=0,type=virtio
cores: 1
memory: 1024
net0: virtio=BC:24:11:22:00:01,bridge=vmbr0,firewall=0
scsi0: local-lvm:vm-220-disk-0,discard=on,iothread=1,size=32G,ssd=1

$ lvs | grep vm-220
vm-220-disk-0   pve Vwi-aotz--  32.00g data base-900-disk-0 2.79   # linked clone, origin = template disk
```

## 4. Ansible: idempotency not met (finding)

```
$ scripts/vm-ip.sh
<LAB-VM-IP>
$ LAB_VM_IP=<LAB-VM-IP> scripts/ansible.sh ansible-playbook playbooks/site.yml
lab-iac-01 : ok=25   changed=16   unreachable=0    failed=0
$ (second run)
TASK [base : Start fail2ban]
changed: [lab-iac-01]
lab-iac-01 : ok=23   changed=1    unreachable=0    failed=0

$ journalctl -u fail2ban
ERROR   Failed during configuration: Have not found any log file for sshd jail
fail2ban.service: Failed with result 'exit-code'.
```

Cause: template 900 ships without rsyslog. On the first run fail2ban starts (role `base`) before
role `rsyslog_cribl` installs rsyslog. `/var/log/auth.log` does not exist yet, fail2ban exits, and only
the second run starts it successfully. Fix: the sshd jail reads from journald with
`backend = systemd` (`/etc/fail2ban/jail.d/sshd.local`).

## 5. Full cycle on a fresh VM (proof)

```
$ scripts/tf.sh destroy -auto-approve
proxmox_virtual_environment_vm.lab: Destruction complete after 2s
Destroy complete! Resources: 1 destroyed.

$ qm status 220
Configuration file 'nodes/pve/qemu-server/220.conf' does not exist
$ lvs | grep -c vm-220
0   # disk and cloud-init drive removed

$ scripts/tf.sh apply -auto-approve
proxmox_virtual_environment_vm.lab: Creation complete after 4s [id=220]
Apply complete! Resources: 1 added, 0 changed, 0 destroyed.

$ scripts/vm-ip.sh
<LAB-VM-IP>   # a different address than after the first apply (new DHCP lease)

$ LAB_VM_IP=<LAB-VM-IP> scripts/ansible.sh ansible-playbook playbooks/site.yml     (140 s)
lab-iac-01 : ok=27   changed=18   unreachable=0    failed=0    skipped=0    rescued=0    ignored=0

$ LAB_VM_IP=<LAB-VM-IP> scripts/ansible.sh ansible-playbook playbooks/site.yml     (30 s)
lab-iac-01 : ok=24   changed=0    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
```

Result: the second run reports `changed=0`, the configuration is idempotent.

Space used after full configuration (Docker including the hello-world image):

```
vm-220-disk-0   base-900-disk-0   9.90%   32.00g   # about 3.2 GB actually allocated
```

## 6. VM state

```
$ ssh ops@<LAB-VM-IP> ...
lab-iac-01
Status: active
Default: deny (incoming), allow (outgoing), deny (routed)
22/tcp                     LIMIT IN    Anywhere
permitrootlogin without-password
passwordauthentication no
kbdinteractiveauthentication no
maxauthtries 3
x11forwarding no
Docker version 29.9.1, build dfc520d
Docker Compose version v5.6.0
Hello from Docker!
active active active   # fail2ban, rsyslog, docker
Status for the jail: sshd
auth,authpriv.* @<VM-IP>:9514
```

`permitrootlogin without-password` is the name `sshd -T` normalises `prohibit-password` to.

## 7. SOC portal: the VM shows up on its own

Test logins from outside; both are rejected as intended:

```
$ ssh -o PubkeyAuthentication=no iac-portal-test@<LAB-VM-IP>
iac-portal-test@<LAB-VM-IP>: Permission denied (publickey).
$ ssh -o PubkeyAuthentication=no root@<LAB-VM-IP>
root@<LAB-VM-IP>: Permission denied (publickey).
```

About a minute later, without touching the portal or Splunk:

```
$ curl -s http://<VM-IP>:8090/api/hosts
{ "host": "lab-iac-01", "events": 10, "failures": 1, "sources": 1,
  "lastSeen": "2026-10-16T12:07:20.000Z",
  "eventTypes": { "authentication": 6, "sudo": 4 }, "openIncidents": 0 }

$ curl -s http://<VM-IP>:8090/api/topology
{ "id": "host:lab-iac-01", "type": "host", "label": "lab-iac-01", "status": "active",
  "meta": { "Typ": "Linux-Host (rsyslog)", "Ereignisse": 10, ... } }
{ "id": "e:<ADMIN-PC-IP>:lab-iac-01", "source": "src:<ADMIN-PC-IP>", "target": "host:lab-iac-01", "label": "1 Fehlversuche" }
{ "id": "e:lab-iac-01:cribl", "source": "host:lab-iac-01", "target": "cribl", "label": "syslog UDP 9514" }
```

The `sudo` events come from the Ansible runs (`become`) and the verification commands as `ops`.

![Hosts view in the SOC portal](img/soc-portal-hosts.png)

## 8. Deploying the SOC portal with Ansible (replaces the running instance)

Before (deployed with `git archive`, no checkout):

```
e869a5f67875 homelab-soc-portal:latest Up About an hour (healthy) 2026-10-16 11:22:48 +0000 UTC
image sha256:d87865a4e4fb…
/api/incidents → total: 3
```

The `.env` from siem-docker was encrypted straight through a pipe, without plaintext on the admin PC.
Checked with hashes:

```
$ ssh root@<VM-IP> 'cat /opt/homelab-soc-portal/.env' | scripts/ansible.sh ansible-vault encrypt --output playbooks/files/siem-docker/soc-portal.env.vault
$ ssh root@<VM-IP> 'sha256sum < /opt/homelab-soc-portal/.env'
f34f8fbaf21353ab2ceb68b5d3d52c9a774a718bf136a5d0df8b1c3e1f1e9946  -
$ scripts/ansible.sh sh -c 'ansible-vault view playbooks/files/siem-docker/soc-portal.env.vault | sha256sum'
f34f8fbaf21353ab2ceb68b5d3d52c9a774a718bf136a5d0df8b1c3e1f1e9946  -
```

Deploy key added read-only (`gh repo deploy-key add … --repo QuitScope/homelab-soc-portal`).

```
$ scripts/ansible.sh ansible-playbook playbooks/soc-portal.yml          (29 s)
TASK [soc_portal : Move a deployment that predates Ansible aside]   changed
TASK [soc_portal : Check out the portal]                            changed
TASK [soc_portal : Install portal configuration from Ansible Vault] changed
TASK [soc_portal : Build and start the portal]                      changed
TASK [soc_portal : Wait until the portal reports healthy]           ok
siem-docker : ok=10   changed=4    unreachable=0    failed=0    skipped=0

$ scripts/ansible.sh ansible-playbook playbooks/soc-portal.yml          (12 s)
siem-docker : ok=9    changed=0    unreachable=0    failed=0    skipped=1
```

After:

```
/opt/homelab-soc-portal   # git checkout of main
/opt/homelab-soc-portal.pre-ansible   # old directory
a918d282a8cb Up 22 seconds (healthy) 2026-10-16 12:25:27 +0000 UTC
image sha256:4653817e6b50…   # rebuilt
/api/health    → {"status":"ok"}
/api/incidents → total: 3   # data in the volume preserved
/api/hosts     → lab-linux-01, lab-iac-01
```

## 9. ARA dashboard

First deploy without recording (the server does not exist yet), then with recording:

```
$ ARA_API_SERVER= scripts/ansible.sh ansible-playbook playbooks/ara.yml      (27 s)
siem-docker : ok=5    changed=3    unreachable=0    failed=0

$ docker stats ara-ara-1
188.2MiB / 256MiB   # too tight, mem_limit raised to 384m

$ scripts/ansible.sh ansible-playbook playbooks/ara.yml                       (limit changed)
siem-docker : ok=5    changed=2    unreachable=0    failed=0
$ scripts/ansible.sh ansible-playbook playbooks/ara.yml                       (12 s)
siem-docker : ok=5    changed=0    unreachable=0    failed=0

$ docker exec ara-ara-1 pip show ara
Version: 1.8.0
```

Further runs recorded by ARA:

```
$ scripts/ansible.sh ansible-playbook playbooks/soc-portal.yml
siem-docker : ok=9    changed=0    unreachable=0    failed=0    skipped=1
$ LAB_VM_IP=<LAB-VM-IP> scripts/ansible.sh ansible-playbook playbooks/site.yml
lab-iac-01  : ok=24   changed=0    unreachable=0    failed=0

$ curl http://<VM-IP>:8091/api/v1/playbooks   (+ /hosts per playbook)
4 site.yml        lab-iac-01   changed=0  ok=24  failed=0
3 soc-portal.yml  siem-docker  changed=0  ok=9   failed=0
2 ara.yml         siem-docker  changed=0  ok=5   failed=0
1 ara.yml         siem-docker  changed=2  ok=5   failed=0
```

What ARA gets to see of secrets:

```
Task "Install portal configuration from Ansible Vault" → {"censored": "the output has been hidden due to
the fact that 'no_log: true' was specified for this result", "changed": false}
Playbook 3 arguments → extra_vars: "Not saved by ARA as configured by 'ignored_arguments'", vault_password_files: []
Playbook 3 files     → soc-portal.yml, roles/soc_portal/defaults/main.yml, roles/soc_portal/tasks/main.yml
```

Server unreachable (wrong port), the playbook still completes:

```
$ ARA_API_SERVER=http://<VM-IP>:9 scripts/ansible.sh ansible-playbook playbooks/ara.yml
[WARNING]: Callback dispatch 'v2_playbook_on_start' failed for plugin 'ara_default': … Connection refused
siem-docker : ok=5    changed=0    unreachable=0    failed=0                  (exit 0)
```

![ARA: recorded playbook runs](img/ara-playbooks.png)

## 10. HashiCorp Vault

Server and bootstrap

```
$ scripts/ansible.sh ansible-playbook playbooks/vault.yml
TASK [vault : Stop here until Vault is initialised]
  msg: Vault is not initialised yet. Run scripts/vault-init.sh, then this playbook again.
siem-docker : ok=8    changed=5    unreachable=0    failed=0    skipped=1

$ scripts/vault-init.sh
Stored Vault init output in ansible/playbooks/files/siem-docker/vault-init.json.vault
$ head -c 30 ansible/playbooks/files/siem-docker/vault-init.json.vault
$ANSIBLE_VAULT;1.1;AES256   # plaintext never on disk or in the terminal

$ scripts/ansible.sh ansible-playbook playbooks/vault.yml   → ok=7  changed=1   (unsealed)
$ scripts/ansible.sh ansible-playbook playbooks/vault.yml   → ok=6  changed=0
$ curl http://<VM-IP>:8200/v1/sys/seal-status
{'initialized': True, 'sealed': False, 'version': '2.2.0', 'storage_type': 'raft'}
```

Configuration as code

```
$ TF_DIR=terraform/vault scripts/vault-admin.sh scripts/tf.sh apply
vault_audit.file: Creation complete [id=file]
vault_mount.homelab: Creation complete [id=homelab]
vault_policy.terraform_proxmox / vault_policy.ansible_soc_portal: Creation complete
vault_auth_backend.approle: Creation complete [id=approle]
vault_approle_auth_backend_role.consumer["terraform"|"ansible"]: Creation complete
vault_approle_auth_backend_role_secret_id.consumer["terraform"|"ansible"]: Creation complete
Apply complete! Resources: 9 added, 0 changed, 0 destroyed.
```

Seeding secrets without showing them (checked by length and hash prefix)

```
$ scripts/vault-admin.sh scripts/vault-seed.sh
stored homelab/proxmox (api_token)
stored homelab/soc-portal (env)
wrote AppRole credentials to .env

homelab/proxmox     version 1  api_token: 54 characters
homelab/soc-portal  version 1  env: 765 characters, sha256 f34f8fbaf213…
siem-docker: sha256sum < /opt/homelab-soc-portal/.env → f34f8fbaf213…   # identical
```

Terraform reads the Proxmox token from Vault (`PROXMOX_VE_API_TOKEN` removed from `.env`)

```
$ scripts/tf.sh plan -detailed-exitcode
ephemeral.vault_kv_secret_v2.proxmox: Opening...
ephemeral.vault_kv_secret_v2.proxmox: Opening complete after 0s
ephemeral.vault_kv_secret_v2.proxmox: Closing complete after 0s
No changes. Your infrastructure matches the configuration.        (exit 0)

$ scripts/tf.sh apply -refresh-only -auto-approve && grep -c 'pve!' terraform/terraform.tfstate
0   # token not in the state
```

A first attempt with the data source `data "vault_kv_secret_v2"` worked as well, but the provider reported
it as deprecated; the ephemeral resource is its successor and keeps the value out of the state.

Ansible reads the portal `.env` from Vault (Ansible Vault file `soc-portal.env.vault` deleted)

```
$ scripts/ansible.sh ansible-playbook playbooks/soc-portal.yml
TASK [soc_portal : Install portal configuration from HashiCorp Vault]   ok
siem-docker : ok=9    changed=0    unreachable=0    failed=0    skipped=1   # content byte-identical
```

Least privilege and audit

```
$ scripts/ansible.sh ansible localhost -m debug -a "msg={{ lookup('community.hashi_vault.vault_kv2_get', 'proxmox', engine_mount_point='homelab') }}"
… Forbidden   # AppRole ansible may not read homelab/proxmox

$ docker exec vault-vault-1 cat /vault/logs/audit.log   (filtered)
13:19:05 update auth/approle/login      role=terraform  policies=['default', 'terraform-proxmox']
13:19:05 read   homelab/data/proxmox    role=terraform  policies=['default', 'terraform-proxmox']
13:21:00 update auth/approle/login      role=ansible    policies=['ansible-soc-portal', 'default']
13:21:00 read   homelab/data/soc-portal role=ansible    policies=['ansible-soc-portal', 'default']
```

Restart: Vault seals itself, the playbook unseals it

```
$ docker restart vault-vault-1          → sealed: True
$ scripts/ansible.sh ansible-playbook playbooks/vault.yml
TASK [vault : Unseal Vault]   changed
siem-docker : ok=7    changed=1    unreachable=0    failed=0    skipped=1
                                        → sealed: False
$ docker stats vault-vault-1            → 25.66MiB / 384MiB
```
