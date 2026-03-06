# Homelab — Segmentation réseau VLAN

Refonte complète d'un réseau domestique à plat vers une architecture segmentée en zones de sécurité distinctes, proche de ce qu'on trouve dans une PME correctement sécurisée.

---

## Contexte

Réseau de départ : tout à plat sur `192.168.0.0/24` — hyperviseurs, NAS, IoT, postes de travail, interfaces d'administration. Aucune isolation, aucune règle firewall structurée, aucune authentification forte.

Objectif : concevoir et déployer une architecture segmentée avec pfSense, MikroTik, Proxmox et un stack monitoring complet — en documentant chaque étape comme on le ferait dans un environnement professionnel.

---

## Matériel

| Équipement | Rôle |
|---|---|
| pfSense (Intel i3-1215U) | Firewall / Routeur / DHCP / DNS |
| MikroTik CRS310-8G+2S+in | Switch de cœur |
| Synology RT6600AX | Point d'accès WiFi (mode AP) |
| 3× Proxmox (MINIFORUM MS-01, ASUS NUC 14, Topton N305) | Hyperviseurs |
| Synology DS723+ | NAS |
| Mac Mini M4 Pro | Administration / Docker (Prometheus, Grafana, Loki) |

---

## Architecture cible

```
FREEBOX (Mode Bridge)
        │
    [pfSense] ← WAN
        │ trunk VLAN 10/20/30/40/50
   [MikroTik CRS310]
    ├── Proxmox ×3        → VLAN_MGMT (20) + VLAN_LAB (30)
    ├── NAS Synology      → VLAN_SERVICES (50)
    ├── Mac Mini          → VLAN_LAN (10)
    └── RT6600AX
            ├── SSID "Maison" → VLAN_LAN (10)
            └── SSID "IoT"   → VLAN_IoT (40)
```

### Plan d'adressage

| VLAN | Nom | Subnet | Contenu |
|---|---|---|---|
| 10 | LAN | `192.168.10.0/24` | Postes de travail, smartphones de confiance |
| 20 | MGMT | `192.168.20.0/24` | Interfaces d'administration |
| 30 | LAB | `192.168.30.0/24` | VMs Proxmox — formation et tests |
| 40 | IoT | `192.168.40.0/24` | Objets connectés |
| 50 | SERVICES | `192.168.50.0/24` | NAS |

---

## Phases du projet

| Phase | Intitulé | Statut |
|---|---|---|
| 1 | Audit et conception architecture
| 2 | Configuration pfSense — VLANs, firewall, DNS
| 3 | MikroTik — VLAN Filtering, migration équipements
| 4 | Migration Proxmox + mise à jour stack monitoring
| 5 | Durcissement — 2FA, Suricata, pfBlockerNG

---

## Stack monitoring

Déployé sur le Mac Mini via Docker :

| Service | Rôle |
|---|---|
| Prometheus | Collecte métriques (SNMP, Node Exporter) |
| Grafana | Dashboards infrastructure |
| Loki | Centralisation des logs |
| Promtail | Agent de collecte logs |

---

## Principes appliqués

- **Moindre privilège** — chaque VLAN n'accède qu'à ce dont il a besoin
- **Alias pfSense** — architecture en 3 couches pour des règles maintenables
- **DNS interne** — tous les équipements accessibles via `*.homelab.local`
- **Documentation continue** — chaque incident est documenté et versionnée

---

