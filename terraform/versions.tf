terraform {
  required_version = ">= 1.6"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.116"
    }
    vault = {
      source  = "hashicorp/vault"
      version = "~> 5.13"
    }
  }
}

# Address from VAULT_ADDR (.env). Logs in with the "terraform" AppRole, whose policy may only read
# homelab/proxmox. skip_child_token: the AppRole token is short-lived already.
provider "vault" {
  skip_child_token = true

  auth_login {
    path = "auth/approle/login"
    parameters = {
      role_id   = var.vault_role_id
      secret_id = var.vault_secret_id
    }
  }
}

# Ephemeral: read at plan/apply time, never written to the state.
ephemeral "vault_kv_secret_v2" "proxmox" {
  mount = "homelab"
  name  = "proxmox"
}

# Endpoint and TLS setting from the environment (PROXMOX_VE_ENDPOINT, PROXMOX_VE_INSECURE),
# the API token from Vault.
provider "proxmox" {
  api_token = ephemeral.vault_kv_secret_v2.proxmox.data["api_token"]
}
