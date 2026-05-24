output "resource_group_name" {
  description = "Nom du Resource Group créé"
  value       = module.network.resource_group_name
}

output "vm_public_ip" {
  description = "Adresse IP publique de la VM — utiliser pour SSH et inventaire Ansible"
  value       = module.network.public_ip_address
}
