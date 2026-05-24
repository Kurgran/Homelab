variable "prefix" {
  type        = string
  description = "Préfixe de nommage des ressources"
}

variable "location" {
  type        = string
  description = "Région Azure cible"
}

variable "resource_group_name" {
  type        = string
  description = "Nom du Resource Group — transmis depuis le module network"
}

variable "vm_size" {
  type        = string
  description = "Taille de la VM Azure (ex: Standard_D2s_v6)"
}

variable "admin_username" {
  type        = string
  description = "Nom de l'utilisateur administrateur SSH"
}

variable "nic_id" {
  type        = string
  description = "ID de la NIC — transmis depuis le module network via la racine"
}

variable "key_vault_id" {
  type        = string
  description = "ID du Key Vault — transmis depuis le bloc data à la racine"
}

variable "tags" {
  type        = map(string)
  description = "Tags appliqués sur toutes les ressources"
}
