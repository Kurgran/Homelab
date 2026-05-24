variable "location" {
  description = "Région Azure où déployer les ressources"
  type        = string
  default     = "westeurope"
}

variable "prefix" {
  description = "Préfixe utilisé pour nommer toutes les ressources"
  type        = string
  default     = "lab"
}

variable "vm_size" {
  description = "Taille de la VM Azure"
  type        = string
  default     = "Standard_D2s_v6"
}

variable "address_space" {
  description = "Plage d'adresses IP du VNet (CIDR)"
  type        = list(string)
  default     = ["10.0.0.0/16"]
}

variable "subnet_prefix" {
  description = "Plage d'adresses IP du subnet (CIDR)"
  type        = list(string)
  default     = ["10.0.1.0/24"]
}

variable "admin_username" {
  description = "Nom de l'utilisateur admin de la VM Linux"
  type        = string
  default     = "azureuser"
}

variable "my_ip" {
  description = "Ton IP publique pour restreindre l'accès SSH (format x.x.x.x/32)"
  type        = string
}

variable "tags" {
  description = "Tags appliqués sur toutes les ressources Azure (gouvernance, traçabilité coûts, audit)"
  type        = map(string)
  default = {
    owner      = "clement"
    env        = "lab"
    projet     = "terraform-azure-lab"
    created-by = "sp-terraform-lab"
  }
}