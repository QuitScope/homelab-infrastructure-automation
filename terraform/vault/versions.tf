terraform {
  required_version = ">= 1.6"

  required_providers {
    vault = {
      source  = "hashicorp/vault"
      version = "~> 5.13"
    }
  }
}

# Address from VAULT_ADDR (.env), token from VAULT_TOKEN (scripts/vault-admin.sh).
provider "vault" {}
