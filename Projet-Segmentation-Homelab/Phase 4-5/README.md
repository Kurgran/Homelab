# Phase 4-5 — Migration Proxmox, mise à jour Docker et durcissement sécurité

**Description courte :** Migration des 3 hyperviseurs Proxmox et de la stack Docker vers la nouvelle architecture VLAN, puis durcissement avec Suricata IPS, pfBlockerNG et 2FA sur toutes les interfaces d'administration.

**Contexte homelab :** Proxmox ×3 (MINIFORUM MS-01, ASUS NUC 14 Pro+, Topton N305) + Docker sur Mac Mini M4 Pro + pfSense + NAS Synology DS723+

**Date :** Mars 2026

---

## Vue d'ensemble

Après la segmentation VLAN (Phase 1-3), deux pans de l'infrastructure restaient sur l'ancien réseau `192.168.0.0/24` : les hyperviseurs Proxmox et la stack Docker de monitoring. La Phase 4 migre ces composants vers les bons VLANs. La Phase 5 ajoute les couches de sécurité manquantes : détection/blocage d'intrusions, filtrage DNS/IP, et authentification forte.

Composants principaux :

* **Proxmox ×3** : Reconfiguration bridges réseau (vmbr0 VLAN-aware + vmbr0.20), migration vers VLAN_MGMT
* **Stack Docker** : Mise à jour des cibles Prometheus, Promtail vers les nouvelles IPs VLAN
* **Suricata** : Passage IDS → IPS après calibrage de 109 105 alertes sur 6 mois
* **pfBlockerNG** : Filtrage DNSBL + blocage IP (listes de menaces)
* **2FA TOTP** : Proxmox (root@pam + clement@pve) et NAS Synology via Authy

---

## Architecture

### Avant / Après migration

| Composant | Avant (Phase 1-3) | Après (Phase 4-5) |
|---|---|---|
| Proxmox ×3 | `192.168.0.x`, bridges non VLAN-aware | VLAN_MGMT `192.168.20.93-95`, `vmbr0.20` |
| VMs Proxmox | Réseau à plat | VLAN_LAB `192.168.30.x` |
| Stack Docker | Cibles Prometheus/Promtail en `192.168.0.x` | Toutes cibles UP sur nouvelles IPs VLAN |
| Suricata | IDS passif, non calibré | IPS actif, 94% bruit éliminé |
| pfBlockerNG | Absent | DNSBL + IP blocking, 3 groupes de listes |
| Squid Proxy | Installé, non configuré | Supprimé |
| 2FA | Absent partout | TOTP Authy sur Proxmox ×3 + NAS |

### Schéma couches de sécurité

```
Internet → [pfSense WAN]
               ├── Suricata IPS — analyse et bloque le trafic malveillant
               ├── pfBlockerNG — filtre IPs (listes menaces) + DNSBL (domaines malveillants)
               └── [VLANs segmentés — Phase 1-3]
                        ├── VLAN_MGMT (20) — Proxmox ×3 (2FA TOTP sur chaque noeud)
                        ├── VLAN_LAB (30) — VMs Proxmox
                        ├── VLAN_LAN (10) — Mac Mini + Docker
                        └── VLAN_SERVICES (50) — NAS Synology (2FA TOTP)
```

### Topologie bridges Proxmox après migration

```
enp87s0 (interface physique)
    └── vmbr0 (bridge sans IP — VLAN aware activé)
            ├── vmbr0.20 → IP 192.168.20.x/24 (noeud Proxmox, trafic tagué VLAN 20)
            └── VMs → tag VLAN 30 attribué par Proxmox (VLAN_LAB)
```

Infrastructure :

* **Plateforme :** 3 noeuds Proxmox (MINIFORUM 192.168.20.93, ASUS 192.168.20.94, TOPTON 192.168.20.95)
* **Docker :** Mac Mini M4 Pro (192.168.10.100) — Prometheus, Grafana, Loki, Promtail
* **Réseau :** VLAN_MGMT (20) pour les hyperviseurs, VLAN_LAB (30) pour les VMs
* **Sécurité :** Suricata sur interface WAN, pfBlockerNG sur WAN + VLANs, 2FA TOTP Authy

---

## Prérequis

Versions testées :

* Proxmox VE : 8.x
* pfSense CE : 2.8.1
* Suricata (package pfSense) : dernière version disponible
* pfBlockerNG-devel : dernière version disponible
* Docker / Docker Compose : sur Mac Mini M4 Pro
* Authy : application mobile (iOS/Android)

Accès réseau requis :

* Port 8006 : WebUI Proxmox
* Port 9090 : Prometheus
* Port 3000 : Grafana
* Port 3100 : Loki
* Port 9100 : Node Exporter (sur chaque noeud Proxmox)
* Port 161 : SNMP (pfSense, MikroTik)

---

## Configuration

### Phase 4 — Migration Proxmox

#### Checklist pré-migration (à exécuter sur chaque noeud)

```bash
ip addr show      # inventaire de toutes les IPs présentes sur le noeud
ip route show     # détecter les routes parasites vers les sous-réseaux VLAN
bridge link show  # état des bridges
ss -tlnp          # services en écoute
```

#### Configuration `/etc/network/interfaces`

Identique sur chaque noeud, seule l'adresse IP change :

```ini
auto lo
iface lo inet loopback

auto enp87s0
iface enp87s0 inet manual

auto vmbr0
iface vmbr0 inet manual
    bridge-ports enp87s0
    bridge-stp off
    bridge-fd 0
    bridge-vlan-aware yes
    bridge-vids 2-4094

auto vmbr0.20
iface vmbr0.20 inet static
    address 192.168.20.94/24    # .93 MINIFORUM / .94 ASUS / .95 TOPTON
    gateway 192.168.20.1
    dns-nameservers 192.168.20.1
```

#### Adresses IP par noeud

| Noeud | IP VLAN_MGMT | Interface |
|---|---|---|
| MINIFORUM MS-01 | 192.168.20.93 | vmbr0.20 |
| ASUS NUC 14 Pro+ | 192.168.20.94 | vmbr0.20 |
| TOPTON N305 | 192.168.20.95 | vmbr0.20 |

#### Désactivation du firewall Proxmox

```bash
# Sur chaque noeud — le firewall natif Proxmox en superposition de pfSense
# complique le diagnostic sans apporter de valeur
pvesh set /nodes/MINIFORUM/firewall/options --enable 0
pvesh set /nodes/ASUS/firewall/options --enable 0
pvesh set /nodes/TOPTON/firewall/options --enable 0
```

#### Règle ICMP à ajouter dans pfSense

pfSense ne laisse pas passer l'ICMP par défaut. Les noeuds Proxmox en ont besoin pour valider la connectivité gateway :

```
Interface : VLAN_MGMT (20)
Action    : Pass
Protocol  : ICMP
Source    : VLAN_MGMT net
Dest      : VLAN_MGMT address (gateway)
```

#### Ordre de migration

Un noeud à la fois, vérification entre chaque :

1. **ASUS** (192.168.20.94)
2. **MINIFORUM** (192.168.20.93)
3. **TOPTON** (192.168.20.95)

Vérification après chaque noeud :

```bash
# Depuis le noeud migré
ping 192.168.20.1              # gateway pfSense
ping google.com                # résolution DNS

# Depuis le Mac Mini
curl -k https://192.168.20.94:8006   # WebUI Proxmox accessible
```

### Phase 4 — Mise à jour stack Docker

#### `prometheus.yml` — nouvelles cibles

```yaml
scrape_configs:
  - job_name: 'pfsense'
    static_configs:
      - targets: ['192.168.20.1:161']      # SNMP pfSense — VLAN_MGMT

  - job_name: 'mikrotik'
    static_configs:
      - targets: ['192.168.20.55:161']     # SNMP MikroTik — VLAN_MGMT

  - job_name: 'nas'
    static_configs:
      - targets: ['192.168.50.17:9100']    # Node Exporter NAS — VLAN_SERVICES

  - job_name: 'proxmox'
    static_configs:
      - targets:
        - '192.168.20.93:9100'             # MINIFORUM — VLAN_MGMT
        - '192.168.20.94:9100'             # ASUS — VLAN_MGMT
        - '192.168.20.95:9100'             # TOPTON — VLAN_MGMT
```

Même mise à jour pour Promtail (sources de logs).

#### Vérification post-migration

```bash
# Redémarrage de la stack
docker compose down && docker compose up -d

# Vérification Prometheus
# Accéder à http://192.168.10.100:9090 > Status > Targets
# Toutes les cibles doivent être en état UP
```

### Phase 5 — Suppression de Squid Proxy

Squid Proxy Server était installé mais jamais configuré. Sans inspection SSL (nécessite une PKI interne), il duplique ce que pfBlockerNG fait mieux via DNSBL.

Packages supprimés via pfSense Package Manager :

* Squid Proxy Server
* Squid Reverse Proxy
* SquidGuard
* ClamAV

Aucune règle firewall n'en dépendait.

### Phase 5 — pfBlockerNG

#### Listes DNSBL configurées

| Groupe | Source | Objectif |
|---|---|---|
| ADs_Basic | Liste intégrée pfBlockerNG | Blocage publicités |
| Malware_Basic | URLhaus (abuse.ch) | Domaines malveillants |
| Tracking_Basic | notracking | Domaines de tracking |

#### Application des listes IP

* **WAN entrée** : listes de blocage IP actives
* **VLANs sortie** : listes actives sur tous les VLANs sauf VLAN_MGMT (les équipements d'administration n'initient pas de connexions internet, les exclure évite tout blocage accidentel)

#### Whitelist (à configurer AVANT le premier Force Reload)

Domaines à whitelister pour éviter les pannes silencieuses :

```
# Services homelab
*.synology.com
*.docker.io
*.docker.com
*.github.com
*.githubusercontent.com

# Services Apple (Mac Mini)
*.apple.com
*.icloud.com

# IoT
*.ring.com
*.netatmo.com

# Proxmox
*.proxmox.com
```

### Phase 5 — Suricata IDS → IPS

#### Analyse des alertes avant passage IPS

109 105 alertes accumulées sur 6 mois en mode IDS :

| Catégorie | Volume | % total | Décision |
|---|---|---|---|
| Checksum offload (bruit hardware NIC) | ~102 046 | 94% | Désactivé via SID Mgmt (`disable.conf`) |
| ET COMPROMISED (IPs malveillantes connues) | ~3 900 | 3.6% | Conservé |
| CVE-2021-35394 Realtek | 186 | <1% | Conservé |
| CVE-2022-27255 Realtek | 109 | <1% | Conservé |
| CVE-2023-28771 Zyxel | 20 | <1% | Conservé |

#### SID Mgmt vs Suppress

| Outil | Fichier | Portée | Usage |
|---|---|---|---|
| SID Mgmt | `disable.conf` | Désactive une règle globalement | Bruit permanent et structurel (ex: checksum offload) |
| Suppress | `suppress.conf` | Désactive pour une IP/réseau spécifique | Faux positifs contextuels (règle pertinente en général, pas pour un hôte donné) |

#### Configuration IPS

```
Mode                     : Legacy Mode (Suricata détecte → pfSense bloque via table firewall)
Interface                : WAN
Block Offenders          : activé
Kill States              : activé (ferme les connexions TCP existantes de l'IP bannie)
Which IP to Block        : SRC (sur WAN, l'attaquant est toujours en source)
Remove Blocked Hosts     : 1 heure (évite les bans indéfinis sur faux positifs)
EVE JSON Log             : activé (format standard pour ingestion SIEM — Wazuh prévu)
```

#### Vérification post-activation

```bash
# Dans pfSense
Services > Suricata > Blocks   # IPs actuellement bloquées
Status > System Logs > Firewall # Vérifier qu'aucun trafic légitime n'est bloqué

# Tester la connectivité depuis chaque VLAN
ping google.com                 # depuis un poste LAN
curl -k https://proxmox1.homelab.local:8006  # depuis le Mac Mini
```

### Phase 5 — 2FA TOTP

#### Application retenue : Authy

Authy plutôt que self-hosted (2FAuth, Ente Auth) : l'appli TOTP self-hosted tourne dans une VM, et on a besoin du TOTP pour accéder à la VM. Dépendance circulaire.

#### Proxmox (×3 noeuds)

Proxmox a deux types de comptes avec des realms distincts :

| Compte | Realm | Type |
|---|---|---|
| `root@pam` | PAM | Compte Linux système |
| `clement@pve` | PVE | Compte Proxmox uniquement |

Les deux nécessitent une configuration 2FA séparée.

Procédure par noeud :

```
1. Créer un compte clement@pve avec rôle Administrator
   → Datacenter > Permissions > Users > Add
   → Realm : Proxmox VE authentication server

2. Activer TOTP sur clement@pve
   → Datacenter > Permissions > Two Factor Authentication > Add > TOTP

3. Activer TOTP sur root@pam
   → Même procédure, en sélectionnant root@pam

4. Scanner le QR code dans Authy
   → Sauvegarder les codes de secours dans le gestionnaire de mots de passe

5. Valider en fenêtre privée AVANT de fermer la session principale
   → Sélectionner le bon realm au login (PAM vs PVE)
```

> Le realm doit être sélectionné correctement à la connexion. Se tromper de realm génère des messages d'erreur qui ne mentionnent pas le realm comme cause.

#### NAS Synology

```
DSM > Sécurité > Compte > Connexion à 2 facteurs
Méthode : TOTP (via Secure SignIn, option "Application d'authentification")
→ Pas de mode push (dépendance serveurs Synology)
→ Scanner QR dans Authy, sauvegarder codes de secours
```

#### pfSense — Pourquoi pas de 2FA à ce stade

pfSense CE 2.8.1 ne supporte pas le TOTP nativement (pfSense Plus le fait). La solution FreeRADIUS impose de remplacer le mot de passe fort (40 caractères) par un PIN à 4 chiffres. C'est une régression de sécurité.

Solution prévue : Authelia comme reverse proxy d'authentification (Phase 6).

---

## Troubleshooting

### Proxmox : pfSense ping le noeud mais le noeud ne ping pas pfSense

**Cause :** route parasite créée par un ancien bridge avec une IP résiduelle. Linux crée automatiquement une route directe vers le sous-réseau de chaque IP configurée.

**Diagnostic :**

```bash
ip route show
# Chercher une route vers 192.168.10.0/24 (ou autre) via un bridge inattendu
# Exemple : 192.168.10.0/24 dev vmbr2 proto kernel scope link src 192.168.10.1

tcpdump -i any -n port 8006
# SYN entrant sur vmbr0.20, SYN-ACK sortant sur vmbr2 → routage asymétrique
```

**Solution :**

```bash
# Retirer l'IP du bridge parasite dans /etc/network/interfaces
nano /etc/network/interfaces
# Supprimer ou commenter la section du bridge concerné

# Redémarrer le networking
systemctl restart networking

# Vérifier que la route a disparu
ip route show
```

### Prometheus : cibles en DOWN après migration

**Cause :** les IPs dans `prometheus.yml` et `promtail` pointent encore vers l'ancien réseau `192.168.0.x`.

**Solution :** mettre à jour toutes les IPs dans les fichiers de config Docker, puis `docker compose down && docker compose up -d`.

### pfBlockerNG : panne silencieuse après activation

**Cause :** un domaine critique (Synology, Docker Hub, GitHub...) est bloqué par une liste DNSBL.

**Diagnostic :**

```bash
# Dans pfSense
Firewall > pfBlockerNG > Reports > DNSBL Activity
# Filtrer sur le domaine suspecté

# Ou via la ligne de commande
pfctl -t pfB_DNSBLIP -T show | grep [IP]
```

**Solution :** ajouter le domaine dans la whitelist pfBlockerNG, puis Force Reload.

### Suricata : blocage massif d'IPs légitimes après passage IPS

**Cause :** règles non calibrées, typiquement les alertes checksum offload (bruit hardware NIC).

**Solution :**

```bash
# Identifier les SIDs responsables
Services > Suricata > Alerts > trier par fréquence

# Ajouter les SIDs de bruit dans disable.conf via SID Mgmt
# NE PAS utiliser Suppress pour du bruit structurel (Suppress = faux positifs contextuels)

# Vider la table de blocage
Services > Suricata > Blocks > Clear
```

### Proxmox 2FA : "authentication failure" alors que le code TOTP est correct

**Cause :** mauvais realm sélectionné à l'écran de login (PAM au lieu de PVE ou inversement).

**Solution :** vérifier le sélecteur de realm en bas du formulaire de login Proxmox. `root` → Linux PAM, `clement` → Proxmox VE authentication server.

---

## Notes

Points d'amélioration prévus (Phase 6+) :

* **Authelia + LLDAP** : authentification centralisée SSO + 2FA devant toutes les interfaces web (pfSense, Proxmox, Grafana)
* **WireGuard VPN** : remplacement de QuickConnect Synology par un accès distant maîtrisé
* **Wazuh SIEM** : centralisation des logs (Suricata EVE JSON déjà configuré pour l'ingestion)
* **Greenbone/OpenVAS** : scan de vulnérabilités interne

Ressources :

* [Proxmox Wiki — Network Configuration](https://pve.proxmox.com/wiki/Network_Configuration)
* [Proxmox Wiki — Two-Factor Authentication](https://pve.proxmox.com/wiki/Two-Factor_Authentication)
* [pfSense — Suricata Package](https://docs.netgate.com/pfsense/en/latest/packages/suricata/index.html)
* [pfSense — pfBlockerNG](https://docs.netgate.com/pfsense/en/latest/packages/pfblocker.html)
* [Article blog — Phases 4 & 5](https://appercel-clement.netlify.app/posts/homelab--phases-4--5--migration-proxmox-mise-%C3%A0-jour-docker-et-durcissement-s%C3%A9curit%C3%A9/)

Homelab context :

* Les bridges Proxmox `vmbr0` sont configurés en VLAN-aware, les VMs reçoivent leur tag VLAN via l'interface Proxmox (pas besoin de configurer le VLAN dans chaque VM)
* Le firewall natif Proxmox est désactivé sur les 3 noeuds, pfSense gère tout le filtrage
* Suricata tourne uniquement sur WAN, pas sur les interfaces VLAN internes
* Les codes de secours 2FA sont stockés dans le gestionnaire de mots de passe, pas sur les machines elles-mêmes

---

## Licence

MIT

Projet réalisé dans le cadre de ma reconversion cybersécurité — Portfolio complet : [appercel-clement.netlify.app](https://appercel-clement.netlify.app)
