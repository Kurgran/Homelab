resource "azurerm_linux_virtual_machine" "main" {
  name                            = "${var.prefix}-vm"
  location                        = var.location
  resource_group_name             = var.resource_group_name
  size                            = var.vm_size
  admin_username                  = var.admin_username
  disable_password_authentication = true

  network_interface_ids = [var.nic_id]

  admin_ssh_key {
    username   = var.admin_username
    public_key = file("~/.ssh/id_rsa_terraform.pub")
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }

  identity {
    type = "SystemAssigned"
    # SystemAssigned : Azure crée automatiquement un SP dans Entra ID,
    # lié au cycle de vie de cette VM (destroy VM = destroy SP).
    # Le principal_id de ce SP sera disponible en output après apply :
    # azurerm_linux_virtual_machine.main.identity[0].principal_id
  }

  tags = var.tags
}

resource "azurerm_role_assignment" "vm_kv_secrets_user" {
  scope                = var.key_vault_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_linux_virtual_machine.main.identity[0].principal_id
}
