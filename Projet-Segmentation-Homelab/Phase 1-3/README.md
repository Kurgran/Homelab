# Phase 1-3 — Audit, configuration pfSense et MikroTik

**Description courte :** Cartographie du réseau existant, conception de l'architecture VLAN, configuration pfSense comme firewall central, puis déploiement du VLAN Filtering sur MikroTik CRS310 et migration de tous les équipements.

**Contexte homelab :** pfSense (Intel i3-1215U) + MikroTik CRS310-8G+2S+in + Synology RT6600AX (mode AP)

**Date :** Février-Mars 2026

---

## Vue d'ensemble

Refonte complète d'un réseau domestique à plat (`192.168.0.0/24`, 15 équipements sans isolation) vers une architecture segmentée en 5 zones de confiance. Le projet couvre l'audit initial, la conception de l'architecture, la configuration complète de pfSense (aliases, règles firewall, DNS interne) puis la mise en place du VLAN Filtering sur le switch MikroTik et la migration physique de chaque équipement dans son VLAN cible.

Composants principaux :

* **pfSense** : Firewall/routeur, DHCP par VLAN, DNS Unbound, règles firewall structurées en alias 3 couches
* **MikroTik CRS310-8G+2S+in** : Switch de coeur, VLAN Filtering, ports trunk/access
* **Synology RT6600AX** : Point d'accès WiFi en mode AP, 2 SSIDs sur 2 VLANs distincts

---

## Architecture

### Plan d'adressage

| VLAN | Nom | Subnet | Contenu |
|---|---|---|---|
| 10 | LAN | `192.168.10.0/24` | Postes de travail, smartphones de confiance |
| 20 | MGMT | `192.168.20.0/24` | Interfaces d'administration (pfSense, Proxmox, MikroTik, borne WiFi) |
| 30 | LAB | `192.168.30.0/24` | VMs Proxmox — formation et tests |
| 40 | IoT | `192.168.40.0/24` | Objets connectés (Ring, Netatmo, Espressif) |
| 50 | SERVICES | `192.168.50.0/24` | NAS Synology |

### Schéma réseau

```
FREEBOX (Mode Bridge)
        │
    [pfSense] ← WAN
        │ trunk VLAN 10/20/30/40/50
   [MikroTik CRS310]
    ├── ether1 : Proxmox ASUS      → Trunk (VLAN 20 + 30)
    ├── ether2 : Borne WiFi        → Trunk (VLAN 10 + 20 + 40)
    ├── ether3 : Proxmox MINIFORUM → Trunk (VLAN 20 + 30)
    ├── ether4 : Mac Mini          → Access (VLAN 10)
    ├── ether5 : pfSense           → Trunk (VLAN 10 + 20 + 30 + 40 + 50)
    ├── ether6 : PC portable       → Access (VLAN 10)
    ├── ether7 : NAS Synology      → Access (VLAN 50)
    └── ether8 : Proxmox TOPTON   → Trunk (VLAN 20 + 30)
```

### Matrice des flux inter-VLAN

| Source → Destination | LAN | MGMT | LAB | IoT | SERVICES | Internet |
|---|---|---|---|---|---|---|
| **LAN** | oui | oui (ports admin) | oui | non | oui | oui |
| **MGMT** | non | oui | non | non | non | non |
| **LAB** | non | non | oui | non | lecture seule | oui |
| **IoT** | non | non | non | oui | non | oui |
| **SERVICES** | non | non | non | non | oui | oui |

Infrastructure :

* **Plateforme :** pfSense sur appliance dédiée (Intel i3-1215U), MikroTik CRS310 switch manageable, RT6600AX en mode AP
* **Réseau :** 5 VLANs, trunk 802.1Q entre pfSense et MikroTik, ports access pour les équipements terminaux

---

## Prérequis

Versions testées :

* pfSense CE : 2.8.1
* MikroTik RouterOS : 7.x (VLAN Filtering supporté)
* Synology SRM (RT6600AX) : mode AP activé

Accès réseau requis :

* Port 443/80 : WebUI pfSense
* Port 8291 : Winbox MikroTik
* Port 8006 : WebUI Proxmox (pour vérification post-migration)
* Ports DSM Synology : port personnalisé + 6690 (Synology Drive)

---

## Configuration

### Phase 1 — Audit du réseau existant

Inventaire réalisé avant toute modification :

```bash
# Sur chaque machine Linux
ip addr show          # IPs et interfaces
ss -tlnp              # services en écoute

# Sur pfSense
Diagnostics > ARP Table     # tous les équipements visibles
Status > DHCP Leases        # baux actifs
```

Risques identifiés à l'audit :

| Niveau | Risque |
|---|---|
| Critique | Réseau à plat — aucune isolation entre zones |
| Critique | IoT sur réseau principal — compromission = accès à toute l'infra |
| Critique | Aucun 2FA sur les interfaces d'administration |
| Critique | QuickConnect NAS — tunnel sortant non contrôlé |
| Élevé | Mac Mini sans IP statique |
| Élevé | VPN configuré mais jamais testé |

### Phase 2 — Configuration pfSense

#### Structure des alias (3 couches)

```
Couche 1 — Alias réseau :
  RFC1918          = 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
  ADMIN_HOSTS      = IP Mac Mini (poste d'administration)
  NAS_HOST         = IP NAS
  PROXMOX_HOSTS    = IPs des 3 hyperviseurs

Couche 2 — Alias ports simples :
  PORTS_DNS            = 53
  PORTS_MAIL           = 993, 587, 465, 143
  PORTS_NAS_DSM        = [port DSM personnalisé], 6690 (Synology Drive)
  PORTS_HYPERVISEUR    = 8006 (Proxmox WebUI)
  PORTS_MONITORING     = ports stack Prometheus/Grafana/Loki
  PORTS_SNMP           = 161
  PORTS_NODE_EXPORTER  = 9100

Couche 3 — Alias ports groupés :
  PORTS_ALL_ADMIN      = tous les ports d'administration regroupés
  PORTS_INTERNET_OUT   = PORTS_WEB + PORTS_DNS + PORTS_MAIL
  PORTS_SCRAPING       = PORTS_SNMP + PORTS_NODE_EXPORTER
```

> Les ports d'administration non standards (SSH, WebUI firewall, WebUI switch, NAS DSM) ne sont pas publiés ici. Adaptez à votre infrastructure.

#### Règles firewall par VLAN

Principe : tout bloqué par défaut, ouverture explicite.

**VLAN_LAN (10)**

| # | Action | Proto | Source | Destination | Port | Description |
|---|---|---|---|---|---|---|
| 1 | Block | * | LAN net | IoT net | * | Isolation totale IoT |
| 2 | Pass | TCP | LAN net | MGMT subnets | PORTS_ALL_ADMIN | Accès interfaces admin |
| 3 | Pass | TCP | LAN net | SERVICES net | ports NAS | Accès NAS |
| 4 | Pass | TCP | LAN net | LAB net | * | Accès VMs lab |
| 5 | Pass | TCP/UDP | LAN net | pfSense | 53 | DNS |
| 6 | Pass | TCP/UDP | LAN net | !RFC1918 | PORTS_INTERNET_OUT | Sortie internet |
| 7 | Pass | UDP | LAN net | NAS_HOST | 161 | SNMP scraping Prometheus |

**VLAN_MGMT (20)**

| # | Action | Proto | Source | Destination | Port | Description |
|---|---|---|---|---|---|---|
| 1 | Pass | TCP/UDP | MGMT net | pfSense | 53 | DNS |
| 2 | Pass | TCP/UDP | MGMT net | pfSense | 161 | SNMP |
| 3 | Pass | UDP | MGMT net | pfSense | syslog | Syslog |
| 4 | Pass | TCP | MGMT net | pfSense | NFS | NFS |
| 5 | Block | * | MGMT net | * | * | Tout le reste bloqué |

**VLAN_LAB (30)**

| # | Action | Proto | Source | Destination | Port | Description |
|---|---|---|---|---|---|---|
| 1 | Pass | TCP | LAB net | Loki | port Loki | Push logs Promtail (en tête de liste) |
| 2 | Pass | TCP/UDP | LAB net | pfSense | 53 | DNS |
| 3 | Pass | TCP/UDP | LAB net | !RFC1918 | ports internet | Sortie internet |
| 4 | Block | * | LAB net | MGMT net | * | Isolation MGMT |
| 5 | Block | * | LAB net | LAN net | * | Isolation LAN |

**VLAN_IoT (40)**

| # | Action | Proto | Source | Destination | Port | Description |
|---|---|---|---|---|---|---|
| 1 | Pass | TCP/UDP | IoT net | pfSense | 53 | DNS |
| 2 | Block | * | IoT net | RFC1918 | * | Isolation totale réseaux internes |
| 3 | Pass | TCP/UDP | IoT net | !RFC1918 | * | Sortie internet tous ports |

> Les appareils IoT utilisent des ports dynamiques et variables. La sécurité repose sur l'isolation des réseaux internes, pas sur le filtrage des ports sortants.

**VLAN_SERVICES (50)**

| # | Action | Proto | Source | Destination | Port | Description |
|---|---|---|---|---|---|---|
| 1 | Pass | TCP/UDP | SERVICES net | pfSense | 53 | DNS (première position — conditionne QuickConnect, DDNS) |
| 2 | Pass | TCP/UDP | SERVICES net | !RFC1918 | * | Sortie internet (mises à jour DSM, NTP, cloud Synology) |
| 3 | Pass | UDP | SERVICES net | Loki | port Loki | Push logs |
| 4 | Block | * | SERVICES net | * | * | Tout le reste bloqué |

#### Règle Floating — mises à jour pfSense

pfSense doit pouvoir se mettre à jour lui-même, son trafic sort directement par WAN :

```
Action    : Pass | Interface : WAN | Direction : out
Protocol  : TCP  | Source : WAN address | Dest : !RFC1918 | Port : 80, 443
```

#### DNS interne — Unbound Host Overrides

```
pfsense.homelab.local      → 192.168.20.1
switch.homelab.local       → 192.168.20.55
wifi.homelab.local         → 192.168.20.84
proxmox1.homelab.local     → 192.168.20.93
proxmox2.homelab.local     → 192.168.20.94
proxmox3.homelab.local     → 192.168.20.95
nas.homelab.local          → 192.168.50.17
grafana.homelab.local      → 192.168.10.100
prometheus.homelab.local   → 192.168.10.100
loki.homelab.local         → 192.168.10.100
```

### Phase 3 — Configuration MikroTik et migration

#### Bridge VLAN Filtering

Sur MikroTik RouterOS, la gestion des VLANs passe par le Bridge avec VLAN Filtering. Le bridge pilote la puce switch matérielle : activer le VLAN Filtering lui dit d'appliquer les règles VLAN sur chaque port.

> **Une fois le VLAN Filtering activé, il s'applique immédiatement.** Toute configuration incorrecte au moment de l'activation = perte d'accès au switch.

#### Checklist avant activation

```
[ ] VLANs créés avec les bons ports Tagged/Untagged
[ ] PVID configurés sur les ports access (ether4=10, ether6=10, ether7=50)
[ ] IP de management configurée sur vlan20-mgmt (192.168.20.55/24)
[ ] bridge ajouté en Tagged dans VLAN 20 (sinon SVI injoignable)
[ ] Borne WiFi configurée avec SSIDs et VLAN IDs AVANT l'activation
```

#### IP de management (SVI)

```
Interface : vlan20-mgmt (VLAN ID 20, sur bridge)
IP        : 192.168.20.55/24
Gateway   : 192.168.20.1
```

#### PVID des ports access

| Port | PVID | Équipement |
|---|---|---|
| ether4 | 10 | Mac Mini |
| ether6 | 10 | PC portable |
| ether7 | 50 | NAS Synology |

#### Ordre de migration des équipements

| Ordre | Port | Équipement | VLAN | IP cible |
|---|---|---|---|---|
| 1 | ether4 | Mac Mini | LAN (10) | 192.168.10.100 |
| 2 | ether7 | NAS Synology | SERVICES (50) | 192.168.50.17 |
| 3 | ether3 | Proxmox MINIFORUM | MGMT (20) | 192.168.20.93 |
| 4 | ether1 | Proxmox ASUS | MGMT (20) | 192.168.20.94 |
| 5 | ether8 | Proxmox TOPTON | MGMT (20) | 192.168.20.95 |
| 6 | ether2 | Borne WiFi RT6600AX | MGMT (20) | 192.168.20.84 |
| 7 | ether6 | PC portable | LAN (10) | DHCP |

Le Mac Mini migre en premier (c'est depuis lui qu'on vérifie tout), le PC portable en dernier (accès de secours si quelque chose tourne mal).

#### Configuration WiFi — RT6600AX en mode AP

| SSID | VLAN | Usage |
|---|---|---|
| Maison | 10 (LAN) | PC portable, smartphones de confiance |
| APP (SSID existant conservé) | 40 (IoT) | Objets connectés — reconnexion automatique |

Conserver le SSID existant pour l'IoT évite de devoir reconfigurer chaque objet connecté manuellement.

---

## Troubleshooting

### `ping 8.8.8.8` fonctionne, `ping google.com` échoue

**Cause :** la règle DNS (port 53 vers pfSense) est absente dans le VLAN. pfSense évalue ses propres règles firewall même pour le trafic qui lui est destiné.

**Solution :** ajouter une règle Pass TCP/UDP vers pfSense port 53 dans le VLAN concerné.

### Switch MikroTik injoignable après activation VLAN Filtering

**Cause :** le `bridge` n'est pas ajouté en Tagged dans le VLAN 20, ou l'IP de management n'existe pas sur l'interface vlan20-mgmt.

**Solution :** reset via port série ou Netinstall, puis reconfigurer en suivant la checklist. Toujours configurer l'IP MGMT avant d'activer le VLAN Filtering.

### Synology Drive synchronise mais DSM est accessible (ou l'inverse)

**Cause :** Synology Drive utilise le port 6690, distinct du port DSM. Les deux doivent être autorisés explicitement dans l'alias.

**Solution :**
```bash
# Vérifier dans les logs firewall pfSense
Status > System Logs > Firewall > filtrer sur l'IP du NAS
# Le port bloqué apparaît immédiatement
```

### Borne WiFi RT6600AX inaccessible via le réseau

**Cause :** en mode AP/Bridge, Synology SRM restreint l'accès à l'interface web aux connexions directes sur les ports LAN de la borne.

**Solution :** accès via câble Ethernet direct sur un port LAN de la borne.

### Règles Promtail/Loki bloquées sur VLAN_LAB

**Cause :** la règle Pass vers Loki est placée après une règle Block. pfSense évalue les règles dans l'ordre.

**Solution :** placer la règle Promtail → Loki en première position dans les règles VLAN_LAB.

---

## Notes

Points d'amélioration traités en Phase 4-5 :

* Migration des bridges Proxmox vers VLAN_MGMT
* Mise à jour de la stack Docker (Prometheus, Grafana, Loki) vers les nouvelles IPs
* Déploiement 2FA sur toutes les interfaces d'administration
* Activation Suricata en mode IPS et pfBlockerNG

Ressources :

* [pfSense Documentation — VLANs](https://docs.netgate.com/pfsense/en/latest/vlan/index.html)
* [MikroTik Wiki — Bridge VLAN Filtering](https://wiki.mikrotik.com/wiki/Manual:Interface/Bridge#Bridge_VLAN_Filtering)
* [Article blog — Phases 1 à 3](https://appercel-clement.netlify.app/posts/homelab--phases-1-%C3%A0-3--segmentation-vlan-dun-r%C3%A9seau-domestique-avec-pfsense-et-mikrotik/)

Homelab context :

* Les 3 hyperviseurs Proxmox restent sur leurs anciennes IPs `192.168.0.x` à ce stade (traité en Phase 4)
* La stack Docker (Mac Mini) pointe encore vers les anciennes IPs des cibles de monitoring (traité en Phase 4)
* Suricata est installé en mode IDS passif, le calibrage et passage IPS sont prévus en Phase 5

---

## Licence

MIT

Projet réalisé dans le cadre de ma reconversion cybersécurité — Portfolio complet : [appercel-clement.netlify.app](https://appercel-clement.netlify.app)
