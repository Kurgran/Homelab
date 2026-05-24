# Lecture du Key Vault existant (infrastructure persistante, hors Terraform)
data "azurerm_key_vault" "main" {
  name                = "kv-terraform-lab-clem"
  resource_group_name = "vault-rg"
}

# Module réseau — RG, VNet, Subnet, NSG, Public IP, NIC
module "network" {
  source = "./modules/network"

  prefix        = var.prefix
  location      = var.location
  address_space = var.address_space
  subnet_prefix = var.subnet_prefix
  my_ip         = var.my_ip
  tags          = var.tags
}

# Module compute — VM Linux + Managed Identity + Role Assignment Key Vault
module "compute" {
  source = "./modules/compute"

  prefix              = var.prefix
  location            = var.location
  resource_group_name = module.network.resource_group_name
  vm_size             = var.vm_size
  admin_username      = var.admin_username
  nic_id              = module.network.nic_id
  key_vault_id        = data.azurerm_key_vault.main.id
  tags                = var.tags
}
