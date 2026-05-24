output "vm_principal_id" {
  description = "Principal ID de la Managed Identity de la VM — utile pour attribuer des rôles supplémentaires"
  value       = azurerm_linux_virtual_machine.main.identity[0].principal_id
}
