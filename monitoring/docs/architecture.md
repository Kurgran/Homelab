# Architecture — Homelab Monitoring Stack

## Vue d'ensemble

La stack de monitoring repose sur deux pipelines parallèles hébergés sur le Mac Mini Pro via Docker Compose :

- **Pipeline métriques** : collecte de données quantitatives (CPU, RAM, trafic réseau) via Prometheus + Node Exporter + SNMP Exporter
- **Pipeline logs** : centralisation des journaux système (syslog) via Loki + Promtail

Les deux pipelines sont visualisés dans une interface unique : **Grafana**.

---

## Schéma d'architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                      MAC MINI PRO (Docker Host)                     │
│                                                                      │
│  ┌────────────────── MÉTRIQUES (Time-Series) ──────────────────┐   │
│  │                                                              │   │
│  │  ┌─────────────┐   scrape    ┌──────────────┐              │   │
│  │  │  Prometheus │◄────────────│ SNMP Exporter│              │   │
│  │  │   :9090     │             │   :9116      │              │   │
│  │  └──────┬──────┘             └──────▲───────┘              │   │
│  │         │ PromQL                    │ SNMP UDP:161          │   │
│  │         ▼                    NAS / pfSense / MikroTik       │   │
│  │  ┌─────────────┐                                            │   │
│  │  │   Grafana   │  Node Exporter :9100 (natif)               │   │
│  │  │   :3000     │◄── Mac / NAS / pfSense                     │   │
│  │  └──────▲──────┘                                            │   │
│  └─────────┼────────────────────────────────────────────────── ┘   │
│            │                                                         │
│  ┌─────────┼──────────── LOGS (Syslog) ────────────────────────┐   │
│  │         │ LogQL                                              │   │
│  │  ┌──────┴──────┐   push API  ┌──────────────┐              │   │
│  │  │    Loki     │◄────────────│   Promtail   │              │   │
│  │  │   :3100     │             │ :1514/udp    │              │   │
│  │  └─────────────┘             └──────▲───────┘              │   │
│  │                                     │ Syslog UDP:1514        │   │
│  │                              pfSense / NAS / /var/log        │   │
│  └────────────────────────────────────────────────────────────── ┘   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Détail des flux

### Flux métriques (modèle Pull)

Prometheus interroge activement chaque cible toutes les 15 à 30 secondes :

| Source | Agent | Port | Métriques |
|--------|-------|------|-----------|
| Mac Mini Pro | Node Exporter (Homebrew) | `9100` | CPU, RAM, disques, réseau |
| NAS Synology DS723+ | Node Exporter (natif) | `9100` | CPU, RAM, disques |
| NAS Synology DS723+ | SNMP via SNMP Exporter | `161/udp` → `9116` | Interfaces réseau (13) |
| pfSense VP6630 | Node Exporter (natif) | `9100` | CPU, RAM, disques |
| pfSense VP6630 | SNMP via SNMP Exporter | `161/udp` → `9116` | Interfaces réseau (13) |
| MikroTik CRS310 | SNMP via SNMP Exporter | `161/udp` → `9116` | Interfaces réseau (14) |

### Flux logs (modèle Push)

Les équipements envoient leurs logs vers Promtail, qui les transmet à Loki :

| Source | Protocole | Destination |
|--------|-----------|-------------|
| pfSense VP6630 | Syslog UDP | `<IP_MAC>:1514` |
| NAS Synology DS723+ | Syslog UDP | `<IP_MAC>:1514` |
| Mac (système) | Volume Docker monté | `/var/log` |

---

## Ports exposés

| Service | Port | Protocole | Usage |
|---------|------|-----------|-------|
| Prometheus | `9090` | TCP | UI web + API PromQL |
| Grafana | `3000` | TCP | Interface de visualisation |
| SNMP Exporter | `9116` | TCP | Endpoint de collecte SNMP |
| Loki | `3100` | TCP | API de stockage des logs |
| Promtail | `1514` | **UDP** | Réception Syslog |
| Promtail | `9080` | TCP | Interface de diagnostic |
| Node Exporter | `9100` | TCP | Exposition des métriques système |

---

## Choix techniques clés

Voir [decisions.md](./decisions.md) pour le détail de chaque décision.

- **Node Exporter natif** (pas dans Docker) : accès aux vraies métriques hardware
- **Approche hybride** Node Exporter + SNMP : nécessaire depuis SNMP Exporter v0.29.0+
- **snmp.yml hybride** : auth custom + module `if_mib` officiel, seul fichier universel compatible avec les 3 équipements réseau
- **UDP pour Syslog** : aucun impact sur les performances de pfSense