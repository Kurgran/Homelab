# Stack IA locale — Homelab

LLM 100% local sur Mac M4 Pro avec Ollama, OpenWebUI et ChromaDB. L'idée de départ est simple : interroger des documents personnels via un modèle de langage sans que les données quittent le réseau.

---

## Table des matières

- [Pourquoi en local](#pourquoi-en-local)
- [Architecture technique](#architecture-technique)
- [Installation](#installation)
- [Configuration RAG avec ChromaDB](#configuration-rag-avec-chromadb)
- [Utilisation](#utilisation)
- [Troubleshooting](#troubleshooting)
- [Performances](#performances)
- [Sécurité](#sécurité)
- [Évolutions prévues](#évolutions-prévues)

---

## Pourquoi en local ?

Les solutions cloud comme ChatGPT ou Claude fonctionnent bien, mais elles impliquent d'envoyer les données vers des serveurs tiers. Pour un usage sur des documents sensibles — ou simplement par principe de souveraineté — un LLM local a du sens.

Avantages concrets dans ce setup :

- Aucune donnée envoyée à l'extérieur (RGPD by design)
- Pas d'abonnement, infrastructure existante valorisée
- Latence minimale, pas de dépendance internet
- Contrôle total des logs et de l'isolation réseau

L'objectif secondaire est de combiner compétences data (RAG, embeddings, préparation datasets) et compétences infra (Docker, monitoring, architecture hybride) dans un même projet.

---

## Architecture technique

### Vue d'ensemble

```
┌──────────────────────────────────────────────┐
│  Utilisateur (Navigateur Web)                │
└──────────────────┬───────────────────────────┘
                   │
                   ▼ http://192.168.1.50:3001
┌──────────────────────────────────────────────┐
│          OpenWebUI (Port 3001)               │
│  Interface web, authentification,            │
│  gestion conversations                       │
└──────────┬───────────────────────────────────┘
           │
           ├──────────────┬───────────────────
           │              │
           ▼              ▼
┌───────────────────┐    ┌──────────────────┐
│   ChromaDB        │    │     Ollama       │
│  (Port 8000)      │    │  (Port 11434)    │
│  Recherche        │    │  Génération      │
│  sémantique       │    │  texte LLM       │
└───────────────────┘    └──────────────────┘
```

### Infrastructure

**Plateforme** : Mac M4 Pro, 64 Go RAM

**Ressources allouées** :
- Ollama : accès GPU via Metal
- ChromaDB : 2 Go RAM
- OpenWebUI : 1 Go RAM

**Réseau** :
- IP statique homelab : `192.168.1.50`
- `3001` : OpenWebUI
- `11434` : API Ollama (compatible OpenAI)
- `8000` : ChromaDB (localhost uniquement)

**Stockage** : volumes Docker persistants, modèles LLM entre 4 et 20 Go selon le modèle, backups vers NAS Synology (rsync quotidien recommandé)

### Stack technique

| Composant | Rôle |
|-----------|------|
| Mac M4 Pro | Plateforme — accélération GPU via Metal |
| Docker Compose | Orchestration |
| Ollama | Runtime LLM local |
| OpenWebUI | Interface web type ChatGPT, multi-utilisateurs |
| ChromaDB | Base vectorielle pour le RAG |
| Python 3.x | Scripts d'ingestion RAG |

---

## Installation

### Prérequis

Versions testées :
- Docker Desktop 4.26+ (Mac Apple Silicon)
- Ollama : latest
- OpenWebUI : main branch
- ChromaDB : latest
- macOS Sonoma 14.0+ ou Sequoia 15.0+

```bash
# Via Homebrew
brew install --cask docker
docker --version
docker-compose --version
```

### Étape 1 — Préparation de l'environnement

```bash
mkdir -p ~/ai-sovereign-stack
cd ~/ai-sovereign-stack
mkdir -p documents scripts
```

### Étape 2 — Déploiement de la stack

Créer le fichier `docker-compose.yml` (voir ce repo), puis :

```bash
docker-compose up -d
docker-compose ps
docker-compose logs -f
```

Sortie attendue :
```
[+] Running 4/4
 ✔ Network ai-sovereign-stack_default    Running
 ✔ Container ollama                      Running
 ✔ Container chromadb                    Started
 ✔ Container openwebui                   Running
```

### Étape 3 — Téléchargement du premier modèle

```bash
docker exec ollama ollama pull mistral
docker exec ollama ollama list
```

Durée : 5-10 minutes selon connexion (~4 Go à télécharger).

### Étape 4 — Configuration initiale OpenWebUI

1. Ouvrir `http://localhost:3001` (ou IP du Mac)
2. Créer le compte admin au premier accès (email, username, mot de passe sécurisé)
3. Sélectionner `mistral:latest` dans le menu déroulant

Test rapide :
```
Prompt : "Bonjour ! Explique-moi en 2 phrases ce qu'est l'IA souveraine."
```

Si la réponse arrive en français et est cohérente, l'installation est bonne.

---

## Configuration RAG avec ChromaDB

### Connexion OpenWebUI → ChromaDB

Dans OpenWebUI :
1. Avatar/nom (haut droite) > Admin Panel > Documents
2. Add Vector Database : type `ChromaDB`, URL `http://chromadb:8000`, collection `homelab_docs`
3. Save

> Utiliser `http://chromadb:8000` (nom du service Docker), pas `localhost:8000`.

### Script d'ingestion automatique

```bash
cd ~/ai-sovereign-stack
python3 -m venv venv
source venv/bin/activate
pip install -r scripts/requirements.txt
```

Exemple de document test :

```bash
cat > documents/homelab-ports.txt << 'EOF'
# Configuration Ports Homelab

## Projet monitoring-stack
- Grafana : port 3000
- Prometheus : port 9090
- Node Exporter : port 9100

## Projet ai-sovereign-stack
- Ollama API : port 11434
- OpenWebUI : port 3001
- ChromaDB : port 8000

## Infrastructure
- pfSense : 192.168.1.1
- NAS Synology : 192.168.1.10
- NUC Proxmox : 192.168.1.20
EOF
```

```bash
python3 scripts/ingest_docs.py
```

Sortie attendue :
```
============================================================
INGESTION DOCUMENTS - RAG ChromaDB
============================================================

Connexion à ChromaDB...
Connexion ChromaDB OK

Gestion collection 'homelab_docs'...
Collection 'homelab_docs' prête

Traitement : homelab-ports.txt
   Découpé en 3 morceaux
   Indexé : 3 morceaux

============================================================
RÉSUMÉ DE L'INGESTION
============================================================
Documents traités : 1
Morceaux indexés : 3
```

---

## Utilisation

### Accès aux services

| Service | URL | Auth |
|---------|-----|------|
| OpenWebUI | `http://192.168.1.50:3001` | Compte créé au premier accès |
| API Ollama | `http://192.168.1.50:11434` | Aucune (accès local) |
| ChromaDB | `http://localhost:8000` | Aucune (localhost uniquement) |

### Commandes utiles

```bash
docker-compose ps
docker-compose logs -f
docker-compose restart ollama
docker-compose down
docker exec ollama ollama list
docker exec ollama ollama rm [nom_modele]
```

### RAG — Questions sur tes documents

1. Dans OpenWebUI, activer le toggle "Use Documents"
2. Sélectionner la collection `homelab_docs`
3. Poser la question

Sans RAG, l'IA donne une réponse générique sur les ports courants. Avec RAG, elle cherche dans les documents indexés avant de répondre — la différence est visible dès le premier test.

Exemple via API directe :

```bash
curl http://localhost:11434/api/generate -d '{
  "model": "mistral",
  "prompt": "Explique la souveraineté numérique en 2 phrases",
  "stream": false
}'

curl http://localhost:11434/api/chat -d '{
  "model": "mistral",
  "messages": [
    {"role": "user", "content": "Bonjour!"}
  ]
}'
```

---

## Troubleshooting

### "Connection refused" sur port 11434

Le container Ollama n'est pas démarré ou pas encore prêt.

```bash
docker ps | grep ollama
docker-compose restart ollama
docker logs ollama
```

### OpenWebUI ne se connecte pas à Ollama

Variable `OLLAMA_BASE_URL` incorrecte. Vérifier :

```bash
docker exec openwebui env | grep OLLAMA
# Doit afficher : OLLAMA_BASE_URL=http://ollama:11434
```

### ChromaDB "Collection not found"

La collection n'existe pas encore. Vérifier d'abord :

```bash
python3 -c "
import chromadb
client = chromadb.HttpClient(host='localhost', port=8000)
print(client.list_collections())
"
# Si vide, lancer l'ingestion
python3 scripts/ingest_docs.py
```

### Génération lente

Le modèle est trop gros pour la RAM disponible. Vérifier avec `docker stats` et passer sur un modèle plus léger si nécessaire (Mistral 7B au lieu d'un 13B+).

---

## Performances (Mac M4 Pro, 64 Go RAM)

| Modèle | Taille | Tokens/sec | Latence 1re réponse | RAM |
|--------|--------|------------|---------------------|-----|
| Mistral 7B | 4.1 Go | ~40 tok/s | <100 ms | ~8 Go |
| Llama 3.2 8B | 4.7 Go | ~35 tok/s | <150 ms | ~9 Go |
| Qwen 2.5 Coder 32B | 19 Go | ~15 tok/s | <300 ms | ~24 Go |

Consommation : ~50W en charge, contre 150-200W pour un serveur x86 classique.

ChromaDB : recherche sémantique en moins de 100 ms sur un corpus de 1 000 documents, indexation ~2-5 secondes par document selon taille.

---

## Sécurité

Données hébergées localement, rien n'est envoyé vers OpenAI ou un cloud externe. Droit d'effacement : `docker-compose down -v`.

Authentification :
- OpenWebUI : email/password
- API Ollama : accès localhost uniquement (ou reverse proxy avec auth)
- ChromaDB : accès restreint au réseau Docker

Script de backup à planifier via cron :

```bash
#!/bin/bash
BACKUP_DIR="/Volumes/NAS/backups/ai-stack"
DATE=$(date +%Y%m%d-%H%M%S)

docker-compose -f ~/ai-sovereign-stack/docker-compose.yml down
sudo rsync -avz /var/lib/docker/volumes/ $BACKUP_DIR/volumes-$DATE/
tar -czf $BACKUP_DIR/config-$DATE.tar.gz ~/ai-sovereign-stack/
docker-compose -f ~/ai-sovereign-stack/docker-compose.yml up -d
```

Pour un usage plus exposé : reverse proxy HTTPS (Nginx/Traefik), segmentation VLAN, monitoring Prometheus avec alertes.

---

## Évolutions prévues

- Intégration Prometheus + Node Exporter, dashboards Grafana
- Centralisation des logs vers Wazuh SIEM
- Chatbot support IT basé sur documentation interne
- Analyse automatique des logs pfSense avec IA
- Load balancing Ollama (plusieurs instances)

---

## Ressources

- [Ollama](https://ollama.ai/docs)
- [OpenWebUI](https://docs.openwebui.com)
- [ChromaDB](https://docs.trychroma.com)
- [Discord Ollama](https://discord.gg/ollama)
- [Reddit r/LocalLLaMA](https://reddit.com/r/LocalLLaMA)

---

*Janvier 2026 — v1.0*
*Projet réalisé dans le cadre d'une reconversion en cybersécurité*
