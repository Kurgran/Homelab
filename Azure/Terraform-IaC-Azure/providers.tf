terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
  required_version = ">= 1.6.0"

  backend "azurerm" {
    resource_group_name  = "tfstate-rg"
    storage_account_name = "tfstatelabclement"
    container_name       = "tfstate"
    key                  = "lab-azure.tfstate"
  }
}

provider "azurerm" {
  features {}
}