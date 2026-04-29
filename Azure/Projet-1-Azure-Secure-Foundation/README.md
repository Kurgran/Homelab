# Projet 1 — Azure Secure Foundation

Mise en place d'une base réseau sécurisée sur Azure : Virtual Network, Network Security Groups, VM de test, et Azure Policy baseline.

Compte Azure PAYG · Région : France Central · Durée : 2 sessions

---

## Architecture

```
Subscription
└── Resource Group : Projet-Azure-1 (France Central)
    ├── VNet : vnet-azure-security-lab (10.0.0.0/8*)
    │   ├── subnet-mgmt      → 10.0.1.0/24  [privé]
    │   ├── subnet-app       → 10.0.2.0/24  [privé + NAT Gateway]
    │   └── AzureBastionSubnet → 10.0.3.0/26
    ├── NSG : nsg-mgmt       → subnet-mgmt
    ├── NSG : nsg-app        → subnet-app
    ├── VM : m-test-app      → subnet-app (Ubuntu 24.04, B2ats_v2)
    └── Azure Policy (x2)   → scope Projet-Azure-1
```

> ⚠️ *Note : les 3 subnets ont des espaces d'adressage séparés au lieu d'un seul /16. Convention non standard — à corriger sur le prochain projet.*

---

## Ressources créées

| Ressource | Nom | Détails |
|-----------|-----|---------|
| Resource Group | `Projet-Azure-1` | France Central |
| Virtual Network | `vnet-azure-security-lab` | 3 subnets |
| NSG | `nsg-mgmt` | Associé à subnet-mgmt |
| NSG | `nsg-app` | Associé à subnet-app |
| NAT Gateway | `nat-app` + `nat-pip` | Associé à subnet-app — **supprimer entre sessions** |
| VM | `m-test-app` | Ubuntu 24.04 LTS, B2ats_v2, IP privée 10.0.2.4 |

---

## Règles NSG

### nsg-mgmt

| Direction | Nom | Priorité | Source | Destination | Port | Action |
|-----------|-----|----------|--------|-------------|------|--------|
| Inbound | Deny-App-To-Mgmt | 100 | 10.0.2.0/24 | Any | Any | Deny |
| Outbound | Deny-Mgmt-Internet-Out | 100 | Any | Internet | Any | Deny |

### nsg-app

| Direction | Nom | Priorité | Source | Destination | Port | Action |
|-----------|-----|----------|--------|-------------|------|--------|
| Inbound | Allow-Bastion-To-App | 100 | 10.0.3.0/26 | Any | 22, 3389 | Allow |
| Inbound | Allow-MyIP-SSH | 120 | `<ton-ip>/32` | Any | 22, 3389 | Allow |
| Outbound | Deny-App-To-Mgmt | 100 | Any | 10.0.1.0/24 | Any | Deny |

---

## Azure Policy

| Politique | Effet | Identité managée | Scope |
|-----------|-------|-----------------|-------|
| Hériter d'une étiquette du groupe de ressources (`environnement`) | Modify | ✅ Système | Projet-Azure-1 |
| Emplacements autorisés (France Central) | Deny | ❌ Non nécessaire | Projet-Azure-1 |

> Deny bloque à la porte avant que la ressource existe : rien à modifier, pas d'identité nécessaire. Modify agit sur des ressources existantes : il faut des droits d'écriture, donc identité managée obligatoire.

---

## Connexion SSH

```bash
# Déplacer la clé et corriger les permissions
mv ~/Desktop/"Clé m-test-app.PEM" ~/.ssh/
chmod 400 ~/.ssh/"Clé m-test-app.PEM"

# Connexion
ssh -i ~/.ssh/"Clé m-test-app.PEM" azureuser@<ip-publique-vm>
```

> L'IP publique change si la VM est arrêtée/démarrée. Vérifier dans le portail avant chaque session.

---

## Tests validés

- ✅ Accès internet depuis `subnet-app` via NAT Gateway (`curl google.com` → 301)
- ✅ Blocage `subnet-app` → `subnet-mgmt` (ping 10.0.1.1 → 100% packet loss)
- ✅ Connexion SSH depuis IP personnelle uniquement

---

## Hygiène des coûts

La NAT Gateway génère un coût fixe (~€0.043/h) même quand toutes les VMs sont éteintes. Procédure entre sessions :

1. **Fin de session** : dissocier la NAT Gateway de `subnet-app` → supprimer `nat-app` et `nat-pip`
2. **Début de session** : recréer `nat-pip` (IP publique) + `nat-app` (NAT Gateway) → associer à `subnet-app`

Temps de recréation : ~5 minutes.

---

## Étiquettes appliquées

```
Projet       : azure-security-lab
environnement: lab
```

---

## Prochaines étapes

- Tester Azure Bastion (tier Developer, gratuit)
- Projet 2 : Identity & Zero Trust (Entra ID, RBAC, PIM, Conditional Access)
