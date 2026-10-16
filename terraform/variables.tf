variable "node_name" {
  description = "Proxmox node that hosts the VM."
  type        = string
  default     = "pve"
}

variable "template_id" {
  description = "VMID of the cloud-init template to clone (Ubuntu 22.04)."
  type        = number
  default     = 900
}

variable "vm_id" {
  description = "VMID of the new VM. IDs from 220 upwards are reserved for IaC-managed VMs."
  type        = number
  default     = 220
}

variable "vm_name" {
  description = "VM name; cloud-init also uses it as hostname."
  type        = string
  default     = "lab-iac-01"
}

variable "mac_address" {
  description = "Fixed MAC so the FritzBox hands out the same DHCP lease after destroy/apply."
  type        = string
  default     = "BC:24:11:22:00:01"
}

variable "cores" {
  description = "vCPUs. The host has only 4 cores, so keep this small."
  type        = number
  default     = 1
}

variable "memory_mb" {
  description = "RAM in MB. The host is short on memory, so keep this small."
  type        = number
  default     = 1024
}

variable "ssh_public_key_path" {
  description = "Public key that cloud-init installs for root."
  type        = string
  default     = "~/.ssh/id_ed25519.pub"
}

variable "vault_role_id" {
  description = "AppRole role ID of the terraform consumer (TF_VAR_vault_role_id in .env)."
  type        = string
}

variable "vault_secret_id" {
  description = "AppRole secret ID of the terraform consumer (TF_VAR_vault_secret_id in .env)."
  type        = string
  sensitive   = true
}
