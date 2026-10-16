# Vault's own configuration as code. Secret values are not managed here (they would end up in the
# state); scripts/vault-seed.sh writes them.

resource "vault_mount" "homelab" {
  path        = "homelab"
  type        = "kv"
  options     = { version = "2" }
  description = "Homelab secrets (KV v2)"
}

# Every request (paths, accessors, HMAC'd values) is logged inside the container's log volume.
resource "vault_audit" "file" {
  type = "file"
  options = {
    file_path = "/vault/logs/audit.log"
  }
}

resource "vault_policy" "terraform_proxmox" {
  name   = "terraform-proxmox"
  policy = <<-EOT
    path "${vault_mount.homelab.path}/data/proxmox" {
      capabilities = ["read"]
    }
  EOT
}

resource "vault_policy" "ansible_soc_portal" {
  name   = "ansible-soc-portal"
  policy = <<-EOT
    path "${vault_mount.homelab.path}/data/soc-portal" {
      capabilities = ["read"]
    }
  EOT
}

resource "vault_auth_backend" "approle" {
  type = "approle"
}

# One AppRole per consumer, each limited to its own secret; tokens live 15 minutes.
resource "vault_approle_auth_backend_role" "consumer" {
  for_each = {
    terraform = vault_policy.terraform_proxmox.name
    ansible   = vault_policy.ansible_soc_portal.name
  }

  backend        = vault_auth_backend.approle.path
  role_name      = each.key
  token_policies = [each.value]
  token_ttl      = 900
  token_max_ttl  = 3600
}

# Lands in the local state (git-ignored); rotate with: terraform apply -replace='vault_approle_auth_backend_role_secret_id.consumer["<name>"]'
resource "vault_approle_auth_backend_role_secret_id" "consumer" {
  for_each = vault_approle_auth_backend_role.consumer

  backend   = vault_auth_backend.approle.path
  role_name = each.value.role_name
}
