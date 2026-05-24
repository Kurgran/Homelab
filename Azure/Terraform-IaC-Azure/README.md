# Terraform IaC Azure

Lab d'apprentissage Infrastructure as Code sur Azure. Le principe : partir d'un `main.tf` basique et ajouter des contrôles de sécurité phase par phase : backend tfstate chiffré, Service Principal RBAC, Key Vault, Managed Identity, tagging, puis découpage en modules locaux.

Abonnement Pay-As-You-Go. **`terraform destroy` obligatoire en fin de session** (la VM tourne à ~0,10-0,12€/h).

---

## Ce qui est déployé

```
Azure (westeurope)
└── lab-rg
    ├── lab-vnet          (VNet 10.0.0.0/16)
    │   └── lab-subnet    (Subnet 10.0.1.0/24)
    ├── lab-nsg           (SSH restreint à l'IP source)
    ├── lab-pip           (Public IP statique Standard)
    ├── lab-nic
    └── lab-vm            (Ubuntu 22.04 LTS, Standard_D2s_v6)
        └── System Assigned Managed Identity
            └── Role : Key Vault Secrets User sur kv-terraform-lab-clem
```

Infrastructure persistante (hors Terraform, jamais détruite) :
- `tfstate-rg` / `tfstatelabclement` : backend tfstate distant
- `vault-rg` / `kv-terraform-lab-clem` : Key Vault contenant le secret du SP

---

## Structure du projet

```
.
├── main.tf              # Appels aux deux modules + bloc data Key Vault
├── variables.tf
├── outputs.tf
├── providers.tf         # Provider azurerm + backend tfstate
├── terraform.tfvars     # IP source SSH (non commité)
├── init-session.sh      # Récupère ARM_CLIENT_SECRET depuis le Key Vault
└── modules/
    ├── network/         # RG, VNet, Subnet, NSG, Public IP, NIC
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    └── compute/         # VM Linux + Managed Identity + Role Assignment
        ├── main.tf
        ├── variables.tf
        └── outputs.tf
```

---

## Prérequis

- Terraform >= 1.6.0
- Azure CLI connecté (`az login`)
- Un abonnement Azure actif
- Infrastructure persistante créée (voir section Bootstrap ci-dessous)

---

## Bootstrap (une seule fois, via Azure CLI)

Ces ressources ne sont jamais gérées par Terraform et ne sont jamais détruites par `terraform destroy`.

### Backend tfstate

```bash
az group create --name tfstate-rg --location westeurope

az storage account create \
  --name tfstatelabclement \
  --resource-group tfstate-rg \
  --location westeurope \
  --sku Standard_LRS \
  --kind StorageV2

az storage container create \
  --name tfstate \
  --account-name tfstatelabclement
```

### Service Principal

```bash
az ad sp create-for-rbac \
  --name "sp-terraform-lab" \
  --role Contributor \
  --scopes /subscriptions/<SUBSCRIPTION_ID>

# User Access Administrator scopé au Key Vault — nécessaire pour azurerm_role_assignment
az role assignment create \
  --role "User Access Administrator" \
  --assignee "<SP_APP_ID>" \
  --scope "/subscriptions/<SUBSCRIPTION_ID>/resourceGroups/vault-rg/providers/Microsoft.KeyVault/vaults/kv-terraform-lab-clem"
```

### Key Vault

```bash
az group create --name vault-rg --location westeurope

az keyvault create \
  --name kv-terraform-lab-clem \
  --resource-group vault-rg \
  --location westeurope \
  --sku standard

az role assignment create \
  --role "Key Vault Secrets Officer" \
  --assignee <OWNER_OBJECT_ID> \
  --scope /subscriptions/<SUBSCRIPTION_ID>/resourceGroups/vault-rg/providers/Microsoft.KeyVault/vaults/kv-terraform-lab-clem

az keyvault secret set \
  --vault-name kv-terraform-lab-clem \
  --name "ARM-CLIENT-SECRET" \
  --value "<SP_PASSWORD>"
```

### Clé SSH RSA

```bash
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa_terraform
```

---

## Variables à renseigner

Créer un fichier `terraform.tfvars` (non commité) :

```hcl
my_ip = "x.x.x.x/32"   # IP source autorisée en SSH sur le NSG
```

Les autres variables ont des valeurs par défaut dans `variables.tf` :

| Variable | Défaut | Description |
|---|---|---|
| `location` | `westeurope` | Région Azure |
| `prefix` | `lab` | Préfixe de nommage |
| `vm_size` | `Standard_D2s_v6` | Taille de la VM |
| `address_space` | `["10.0.0.0/16"]` | CIDR du VNet |
| `subnet_prefix` | `["10.0.1.0/24"]` | CIDR du Subnet |
| `admin_username` | `azureuser` | Utilisateur SSH |

---

## Utilisation (chaque session)

```bash
# 1. Charger les credentials SP depuis le Key Vault
source init-session.sh

# 2. Init obligatoire après tout changement de modules
terraform init

# 3. Vérifier le plan
terraform plan

# 4. Déployer
terraform apply

# 5. SSH sur la VM (IP dans les outputs)
ssh -i ~/.ssh/id_rsa_terraform azureuser@<vm_public_ip>

# 6. Détruire en fin de session
terraform destroy
```

---

## Destruction

```bash
terraform destroy
```

Vérifier dans le portail Azure que `lab-rg` est supprimé. Les RG `tfstate-rg` et `vault-rg` sont persistants, ne pas les supprimer.

---

## Sécurité

- `terraform.tfvars` et `*.tfstate` dans `.gitignore`, jamais commités
- `ARM_CLIENT_SECRET` uniquement en mémoire terminal via `init-session.sh`, jamais dans un fichier
- SP : `Contributor` sur la subscription (contrainte lab, RG éphémère) + `User Access Administrator` scopé au Key Vault uniquement
- NSG : SSH restreint à l'IP source, pas de `0.0.0.0/0`
- La VM accède au Key Vault via Managed Identity, zéro credential stocké sur la VM

---

## Avancement

| Phase | Contenu | Statut |
|---|---|---|
| Phase 1 | Fondations Terraform Azure (RG, VNet, Subnet, NSG, VM) | terminé |
| Phase 2.1 | Backend tfstate distant chiffré | terminé |
| Phase 2.2 | Service Principal + RBAC | terminé |
| Phase 2.3 | Azure Key Vault + init-session.sh | terminé |
| Phase 2.4 | Managed Identity pour la VM | terminé |
| Phase 2.5 | Tagging systématique | terminé |
| Phase 2.6 | Modules Terraform locaux | terminé |
| Phase 3 | Ansible post-déploiement (durcissement VM Azure) | à venir |

---

## Stack

- Terraform v1.x, provider `hashicorp/azurerm` v3.117.1
- Azure westeurope, abonnement Pay-As-You-Go
- Ubuntu 22.04 LTS (Canonical)
- Auth via Service Principal, variables d'environnement ARM_*
