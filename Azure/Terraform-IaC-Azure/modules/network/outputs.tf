output "resource_group_name" {
  description = "Nom du Resource Group — transmis au module compute"
  value       = azurerm_resource_group.main.name
}

output "nic_id" {
  description = "ID de la Network Interface Card — transmis au module compute pour attacher la VM"
  value       = azurerm_network_interface.main.id
}

output "public_ip_address" {
  description = "Adresse IP publique de la VM — affichée en output final par la racine"
  value       = azurerm_public_ip.main.ip_address
}
