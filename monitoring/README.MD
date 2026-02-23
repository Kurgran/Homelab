# 📊 Homelab Monitoring Stack — v2.0

Stack de monitoring complète déployée sur Mac M4 Pro via Docker Compose.  
Couvre la collecte de **métriques système et réseau** ainsi que la **centralisation des logs** pour l'ensemble du homelab.

> **Statut** : ✅ Opérationnel — Dernière mise à jour : Février 2026

---

## 🏗️ Architecture

### Infrastructure physique monitorée

| Équipement | Modèle | IP | Rôle |
|------------|--------|----|------|
| Mac Mini Pro | Mac Mini Pro M4 | `<IP_MAC>` | Hôte Docker — héberge toute la stack |
| NAS Synology | DS723+ | `<IP_NAS>` | Stockage centralisé |
| Routeur pfSense | VP6630 | `<IP_PFSENSE>` | Routeur / Firewall |
| Switch MikroTik | CRS310-8G+2S+ | `<IP_MIKROTIK>` | Switch manageable |

### Vue d'ensemble logique

```
┌──────────────────────────────────────────────────────────────────┐
│                    MAC M4 PRO (Docker Host)                       │
│                                                                    │
│  ┌─────────────────── MÉTRIQUES ────────────────────────────┐    │
│  │                                                           │    │
│  │  Prometheus :9090 ◄── SNMP Exporter :9116               │    │
│  │       │                      ▲                           │    │
│  │       │                      │ SNMP (UDP 161)            │    │
│  │       ▼                      │                           │    │
│  │  Grafana :3000        NAS / pfSense / MikroTik           │    │
│  │                                                           │    │
│  └───────────────────────────────────────────────────────────┘    │
│                                                                    │
│  ┌─────────────────── LOGS ─────────────────────────────────┐    │
│  │                                                           │    │
│  │  Promtail :1514/udp ──► Loki :3100 ◄── Grafana :3000    │    │
│  │       ▲                                                   │    │
│  │       │ Syslog UDP                                       │    │
│  │  pfSense / NAS / Mac (/var/log monté)                    │    │
│  │                                                           │    │
│  └───────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

### Flux de données

- **Métriques** : Prometheus scrape les targets toutes les 15–30s (modèle *pull*)
- **Logs** : Les équipements envoient leurs logs vers Promtail en Syslog UDP sur le port 1514 (modèle *push*)
- **Visualisation** : Grafana interroge Prometheus en PromQL et Loki en LogQL

---

## 🐳 Services Docker

| Service | Image | Port | Rôle |
|---------|-------|------|------|
| Prometheus | `prom/prometheus:latest` | `9090` | Collecte et stockage des métriques (TSDB) |
| Grafana | `grafana/grafana:latest` | `3000` | Visualisation — dashboards métriques et logs |
| SNMP Exporter | `prom/snmp-exporter:latest` | `9116` | Traduction SNMP → Prometheus pour les équipements réseau |
| Loki | `grafana/loki:latest` | `3100` | Stockage et indexation des logs |
| Promtail | `grafana/promtail:latest` | `1514/udp`, `9080` | Collecte des logs Syslog UDP depuis les équipements |

---

## 🎯 Jobs Prometheus

8 jobs actifs assurant une couverture complète de l'infrastructure :

| # | Job | Type | Target | Métriques |
|---|-----|------|--------|-----------|
| 1 | `prometheus` | Auto-monitoring | `localhost:9090` | Santé de Prometheus |
| 2 | `grafana` | Auto-monitoring | `grafana:3000` | Santé de Grafana |
| 3 | `mac-m4-pro` | Node Exporter | `host.docker.internal:9100` | CPU, RAM, disques, réseau Mac |
| 4 | `synology-node` | Node Exporter | `<IP_NAS>:9100` | CPU, RAM, disques NAS |
| 5 | `synology-nas-snmp` | SNMP (`if_mib`) | `<IP_NAS>` via SNMP Exporter | Interfaces réseau NAS (13 interfaces) |
| 6 | `pfsense-node` | Node Exporter | `<IP_PFSENSE>:9100` | CPU, RAM, disques pfSense |
| 7 | `pfsense-router-snmp` | SNMP (`if_mib`) | `<IP_PFSENSE>` via SNMP Exporter | Interfaces réseau pfSense (13 interfaces) |
| 8 | `mikrotik-switch-snmp` | SNMP (`if_mib`) | `<IP_MIKROTIK>` via SNMP Exporter | Interfaces switch (14 interfaces) |

---

## 📋 Sources de logs centralisées

| Source | Protocole | Statut | Label Grafana |
|--------|-----------|--------|---------------|
| pfSense | Syslog UDP → `<IP_MAC>:1514` | ✅ Actif | `host=pfsense` |
| NAS Synology | Syslog UDP → `<IP_MAC>:1514` | ✅ Actif | `host=synology` |
| Mac (système) | Volume `/var/log` monté en lecture seule | ✅ Actif | `host=mac` |
| MikroTik | — | ❌ Non configuré | — |
| Proxmox x3 | — | ❌ Non configuré | — |

---

## 📁 Structure du projet

```
monitoring/
├── README.md
│
├── docs/
│   ├── architecture.md          # Schéma détaillé et explications
│   ├── decisions.md             # Journal des décisions techniques (ADR)
│   └── troubleshooting.md       # Erreurs connues et solutions
│
├── stack/
│   ├── docker-compose.yml       # Orchestration des 5 services
│   │
│   ├── prometheus/
│   │   ├── prometheus.yml       # 8 jobs de scraping
│   │   └── rules/               # Règles d'alerting
│   │
│   ├── snmp/
│   │   └── snmp.yml             # Config hybride (~1250 lignes annotées)
│   │
│   └── loki/
│       └── promtail-config.yaml # Collecte Syslog UDP
│
├── node-exporter/
│   ├── install-mac.md           # Installation Homebrew — Mac M4 Pro
│   ├── install-nas.md           # Installation — Synology DS723+
│   └── install-pfsense.md      # Installation — pfSense VP6630
│
└── grafana/
    └── dashboards/
        ├── system-overview.json
        ├── network-snmp.json
        └── logs-loki.json
```

---

## 🚀 Démarrage rapide

### Prérequis

> **Note sur les adresses IP** : Ce repo utilise des placeholders à la place des IPs réelles. Remplace-les par les tiennes avant de lancer la stack :
> - `<IP_MAC>` → IP de ta machine hôte Docker
> - `<IP_NAS>` → IP de ton NAS Synology
> - `<IP_PFSENSE>` → IP de ton routeur pfSense
> - `<IP_MIKROTIK>` → IP de ton switch MikroTik

- Docker Desktop installé et démarré
- Node Exporter installé nativement sur Mac, NAS et pfSense (voir `node-exporter/`)
- SNMP activé sur NAS, pfSense et MikroTik avec la community string `public`
- Syslog UDP configuré sur pfSense et NAS vers `192.168.0.125:1514`

### Lancer la stack

```bash
# Se placer dans le dossier stack
cd monitoring/stack

# Démarrer tous les services en arrière-plan
docker compose up -d

# Vérifier que tous les conteneurs sont UP
docker compose ps
```

Résultat attendu :

```
NAME            IMAGE                       STATUS    PORTS
prometheus      prom/prometheus:latest      Up        0.0.0.0:9090->9090/tcp
grafana         grafana/grafana:latest      Up        0.0.0.0:3000->3000/tcp
snmp-exporter   prom/snmp-exporter:latest   Up        0.0.0.0:9116->9116/tcp
loki            grafana/loki:latest         Up        0.0.0.0:3100->3100/tcp
promtail        grafana/promtail:latest     Up        0.0.0.0:1514->1514/udp
```

### Accès aux interfaces

| Interface | URL |
|-----------|-----|
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| Prometheus Targets | http://localhost:9090/targets |
| SNMP Exporter | http://localhost:9116 |
| Promtail (statut) | http://localhost:9080 |

---

## 🔍 Commandes de vérification

```bash
# Vérifier les targets Prometheus (via API)
curl -s http://localhost:9090/api/v1/targets \
  | jq '.data.activeTargets[] | select(.health=="up") | .labels.job'

# Vérifier que Loki est prêt
curl -s http://localhost:3100/ready

# Tester SNMP sur un équipement
snmpwalk -v2c -c public <IP_MIKROTIK> system

# Tester la génération de métriques SNMP
curl "http://localhost:9116/snmp?target=<IP_MIKROTIK>&module=if_mib&auth=public_v2" \
  | grep "ifInOctets" | head -5

# Voir les logs d'un conteneur
docker compose logs --tail=50 prometheus
```

---

## ⚙️ Points techniques notables

### Node Exporter natif (hors Docker)

Node Exporter est installé **nativement** (via Homebrew sur Mac, via les gestionnaires de paquets sur NAS et pfSense) et non dans un conteneur Docker. Cette décision est intentionnelle : un Node Exporter conteneurisé remonte les métriques de la VM Linux interne à Docker, pas celles du hardware réel. L'installation native garantit l'accès aux vrais métriques CPU, RAM et disques de chaque machine.

### fichier `snmp.yml` hybride

Le fichier `snmp/snmp.yml` combine une section `auths` personnalisée (authentification SNMP v2c avec le community) et le module `if_mib` complet extrait du fichier officiel Prometheus . Cette approche a été adoptée car SNMP Exporter v0.29.0+ requiert des modules pré-compilés, et le fichier officiel complet entrait en conflit avec les configurations NAS/pfSense existantes.

### Choix UDP pour Syslog

Le protocole UDP est utilisé pour la collecte de logs Syslog (plutôt que TCP). Raison : UDP est "fire and forget" — en cas de surcharge du collecteur, on préfère perdre quelques événements plutôt que de ralentir pfSense avec des confirmations TCP. Dans un contexte homelab, ce compromis est acceptable.

---

## 📜 Historique des versions

| Version | Date | Changements |
|---------|------|-------------|
| v1.0 | Janvier 2026 | Stack initiale : Prometheus + Grafana + SNMP Exporter + Node Exporter |
| v2.0 | Février 2026 | Ajout Loki + Promtail — centralisation des logs Syslog UDP |



---

## 🔗 Ressources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [SNMP Exporter](https://github.com/prometheus/snmp_exporter)
- [Loki Documentation](https://grafana.com/docs/loki/)
- [Node Exporter Full — Dashboard Grafana #1860](https://grafana.com/grafana/dashboards/1860)

---

