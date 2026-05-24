variable "prefix" {
  type        = string
  description = "Préfixe de nommage des ressources"
}

variable "location" {
  type        = string
  description = "Région Azure cible"
}

variable "address_space" {
  type        = list(string)
  description = "Plage CIDR du VNet"
}

variable "subnet_prefix" {
  type        = list(string)
  description = "Plage CIDR du Subnet"
}

variable "my_ip" {
  type        = string
  description = "IP source autorisée en SSH sur le NSG"
}

variable "tags" {
  type        = map(string)
  description = "Tags appliqués sur toutes les ressources"
}