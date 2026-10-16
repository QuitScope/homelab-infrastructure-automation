output "role_ids" {
  description = "AppRole role IDs per consumer (identifiers, not secrets)."
  value       = { for k, r in vault_approle_auth_backend_role.consumer : k => r.role_id }
}

output "secret_ids" {
  description = "AppRole secret IDs per consumer; scripts/vault-seed.sh writes them into .env."
  value       = { for k, s in vault_approle_auth_backend_role_secret_id.consumer : k => s.secret_id }
  sensitive   = true
}
