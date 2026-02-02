#  Stack IA Local - Homelab

> Projet de formation en cybersécurité - Déploiement d'une solution d'intelligence artificielle 100% locale et souveraine dans un environnement homelab, démontrant la maîtrise de l'infrastructure IA, Docker, et des principes de souveraineté des données.

## 📋 Table des matières

- [Contexte et justification](#-contexte-et-justification-du-projet)
- [Architecture technique](#-architecture-technique)
- [Installation](#-installation)
- [Configuration RAG](#-configuration-rag-avec-chromadb)
- [Utilisation](#-utilisation)
- [Cas d'usage](#-cas-dusage)
- [Troubleshooting](#-troubleshooting)
- [Performances](#-performances)
- [Sécurité & Conformité](#-sécurité--conformité)
- [Évolutions futures](#-évolutions-futures)

---

## 🎯 Contexte et justification du projet

### Pourquoi une IA en local ?

Ce projet explore le déploiement d'un modèle de langage (LLM) en local dans un homelab.
L'idée est de pouvoir interroger un modèle d'IA sur des documents personnels ou non

**Problématiques adressées :**
- **Souveraineté des données** : Aucune donnée envoyée à l'étranger 
- **Conformité RGPD** : 100% on-premise, audit trail complet, droit d'effacement
- **Coût maîtrisé** : Pas d'abonnement cloud, infrastructure existante valorisée
- **Performance** : Latence minimale (local), pas de dépendance internet
- **Sécurité** : Contrôle total de la stack, logs internes, isolation réseau

### Objectif de ce projet

Démontrer la capacité à déployer et sécuriser une **stack IA complète** (type ChatGPT) dans un environnement homelab professionnel, en combinant :
- **Compétences Data/BI** : RAG, embeddings, préparation datasets
- **Compétences Cyber** : Sécurisation infra, audit
- **Compétences Infrastructure** : Docker, monitoring, architecture hybride


### Technologies utilisées

- **Mac M4 Pro** 
- **Docker Compose** - Orchestration conteneurs
- **Ollama** - Runtime LLM local avec optimisations Apple Silicon
- **OpenWebUI** - Interface ChatGPT-like, authentification multi-users
- **ChromaDB** - Base vectorielle pour RAG (Retrieval Augmented Generation)
- **Python 3.x** - Scripts d'automatisation et ingestion RAG

---

## 🏗️ Architecture technique

### Vue d'ensemble

```
┌──────────────────────────────────────────────┐
│  Utilisateur (Navigateur Web)                │
└──────────────────┬───────────────────────────┘
                   │
                   ▼ http://192.168.1.50:3001
┌──────────────────────────────────────────────┐
│          OpenWebUI (Port 3001)               │
│  - Interface ChatGPT-like                    │
│  - Authentification                          │
│  - Gestion conversations                     │
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

**Plateforme** : Mac M4 Pro 

**Ressources allouées** :
- Docker Desktop 
- Ollama : Accès GPU via Metal
- ChromaDB : 2 Go RAM
- OpenWebUI : 1 Go RAM

**Réseau** :
- IP statique homelab : `192.168.1.50` (exemple)
- Ports exposés : 
  - `3001` : OpenWebUI (interface web)
  - `11434` : Ollama API (compatible OpenAI)
  - `8000` : ChromaDB (localhost uniquement)

**Stockage** :
- Volumes Docker persistants
- Modèles LLM : ~20-50 Go selon modèles
- ChromaDB embeddings : ~100 Mo - 5 Go selon corpus
- Backups : NAS Synology (rsync quotidien recommandé)

---

## 🚀 Installation

### Prérequis

**Versions testées :**
- Docker Desktop : 4.26+ (pour Mac Apple Silicon)
- Ollama : latest (image officielle)
- OpenWebUI : main branch
- ChromaDB : latest
- macOS : Sonoma 14.0+ ou Sequoia 15.0+

**Installation Docker Desktop :**

```bash
# Via Homebrew (recommandé)
brew install --cask docker

# Vérification
docker --version
docker-compose --version
```

### Étape 1 : Préparation de l'environnement

```bash
# Créer le dossier projet
mkdir -p ~/ai-sovereign-stack
cd ~/ai-sovereign-stack

# Créer les sous-dossiers
mkdir -p documents scripts
```

### Étape 2 : Déploiement de la stack

**Créer le fichier `docker-compose.yml`** (voir fichier dans ce repo)

```bash
# Lancer tous les services
docker-compose up -d

# Vérifier que tout tourne
docker-compose ps

# Consulter les logs
docker-compose logs -f
```

**Sortie attendue :**
```
[+] Running 4/4
 ✔ Network ai-sovereign-stack_default    Running
 ✔ Container ollama                      Running
 ✔ Container chromadb                    Started
 ✔ Container openwebui                   Running
```

### Étape 3 : Téléchargement du premier modèle

```bash
# Télécharger Mistral 7B (modèle français optimisé)
docker exec ollama ollama pull mistral

# Vérifier les modèles disponibles
docker exec ollama ollama list
```

**Durée** : 5-10 minutes selon connexion internet (~4 Go à télécharger)

### Étape 4 : Configuration initiale OpenWebUI

1. Ouvrir navigateur : `http://localhost:3001` (ou IP Mac)
2. **Premier accès** : Créer compte admin
   - Email : votre email
   - Username : votre username
   - Password : mot de passe sécurisé (min 8 caractères)
3. **Connexion automatique** après création
4. **Sélectionner modèle** : `mistral:latest` dans le menu déroulant

**Test rapide** :
```
Prompt : "Bonjour ! Explique-moi en 2 phrases ce qu'est l'IA souveraine."
```

✅ Si la réponse arrive en français et est cohérente → Installation réussie !

---

## 🔧 Configuration RAG avec ChromaDB

### Connexion OpenWebUI → ChromaDB

**Dans OpenWebUI** :
1. Cliquer sur avatar/nom (haut droite)
2. **Admin Panel** > **Documents**
3. **Add Vector Database** :
   - Type : `ChromaDB`
   - URL : `http://chromadb:8000`
   - Collection : `homelab_docs` (sera créée automatiquement)
4. **Save**

⚠️ **Important** : Utiliser `http://chromadb:8000` (nom du service Docker), pas `localhost:8000`

### Script d'ingestion automatique

**Installation des dépendances Python** :

```bash
# Créer environnement virtuel
cd ~/ai-sovereign-stack
python3 -m venv venv
source venv/bin/activate

# Installer dépendances
pip install -r scripts/requirements.txt
```

**Créer des documents test** :

```bash
# Exemple : Documentation ports homelab
cat > documents/homelab-ports.txt << 'EOF'
# Configuration Ports Homelab

## Projet monitoring-stack
- Grafana : port 3000 (dashboards visualisation)
- Prometheus : port 9090 (collecte métriques)
- Node Exporter : port 9100 (métriques système)

## Projet ai-sovereign-stack
- Ollama API : port 11434 (API LLM local)
- OpenWebUI : port 3001 (interface ChatGPT-like)
- ChromaDB : port 8000 (base vectorielle)

## Infrastructure
- pfSense : 192.168.1.1 (routeur/firewall)
- NAS Synology : 192.168.1.10 (stockage)
- NUC Proxmox : 192.168.1.20 (virtualisation)
EOF
```

**Lancer l'ingestion** :

```bash
cd ~/ai-sovereign-stack
source venv/bin/activate
python3 scripts/ingest_docs.py
```

**Sortie attendue :**
```
============================================================
🚀 INGESTION DOCUMENTS - RAG ChromaDB
============================================================

📡 Connexion à ChromaDB...
✅ Connexion ChromaDB OK

📚 Gestion collection 'homelab_docs'...
✅ Collection 'homelab_docs' prête

📄 Traitement : homelab-ports.txt
   ✂️  Découpé en 3 morceaux
   ✅ Indexé : 3 morceaux

============================================================
📊 RÉSUMÉ DE L'INGESTION
============================================================
✅ Documents traités : 1
✅ Morceaux indexés : 3
```

---

## 📊 Utilisation

### Accès aux services

| Service | URL | Credentials |
|---------|-----|-------------|
| **Interface OpenWebUI** | `http://192.168.1.50:3001` | Définis lors du premier accès |
| **API Ollama** | `http://192.168.1.50:11434` | Aucun (accès local) |
| **API ChromaDB** | `http://localhost:8000` | Aucun (localhost uniquement) |

### Commandes utiles

```bash
# Vérifier le statut de tous les services
docker-compose ps

# Consulter les logs en temps réel
docker-compose logs -f

# Redémarrer un service
docker-compose restart ollama

# Arrêter la stack complète
docker-compose down

# Lister les modèles Ollama disponibles
docker exec ollama ollama list

# Supprimer un modèle
docker exec ollama ollama rm [nom_modele]
```

---

## 🎯 Cas d'usage

### Cas d'usage 1 : Conversation simple

1. Accéder à OpenWebUI : `http://192.168.1.50:3001`
2. Sélectionner modèle : `mistral:latest`
3. Poser question dans l'interface

### Cas d'usage 2 : RAG - Questions sur vos documents

**Activer RAG dans OpenWebUI** :
1. Toggle "Use Documents" ou icône 📚
2. Sélectionner collection : `homelab_docs`
3. Poser question sur vos documents indexés

**Exemple** :
```
Prompt : "Quels sont les ports utilisés dans mon homelab ?"

Réponse (avec RAG) :
"Selon ta documentation homelab, voici les ports utilisés :
- Grafana : port 3000 (monitoring)
- Prometheus : port 9090 (métriques)
- Ollama API : port 11434 (IA locale)
- OpenWebUI : port 3001 (interface web)
[...]"
```

**Sans RAG**, l'IA donnerait une réponse générique sur les ports courants en homelab, pas TES ports spécifiques.

### Cas d'usage 3 : Utilisation de l'API Ollama

```bash
# Génération de texte via API
curl http://localhost:11434/api/generate -d '{
  "model": "mistral",
  "prompt": "Explique la souveraineté numérique en 2 phrases",
  "stream": false
}'

# Chat conversation
curl http://localhost:11434/api/chat -d '{
  "model": "mistral",
  "messages": [
    {"role": "user", "content": "Bonjour!"}
  ]
}'
```

---

## 🛠 Troubleshooting

### Erreur : "Connection refused" sur port 11434

**Cause** : Container Ollama pas démarré ou pas prêt

**Solution** :
```bash
# Vérifier statut
docker ps | grep ollama

# Si absent, redémarrer
docker-compose restart ollama

# Consulter logs
docker logs ollama
```

### Erreur : OpenWebUI ne se connecte pas à Ollama

**Cause** : Variable `OLLAMA_BASE_URL` incorrecte

**Solution** :
```bash
# Vérifier configuration
docker exec openwebui env | grep OLLAMA

# Doit afficher : OLLAMA_BASE_URL=http://ollama:11434
```

### Erreur : ChromaDB "Collection not found"

**Cause** : Collection pas encore créée

**Solution** :
```bash
# Vérifier collections existantes
python3 -c "
import chromadb
client = chromadb.HttpClient(host='localhost', port=8000)
print(client.list_collections())
"

# Si vide, lancer ingestion
python3 scripts/ingest_docs.py
```

### Performance : Génération de texte lente

**Cause** : Modèle trop gros pour la RAM disponible

**Solution** :
```bash
# Vérifier usage mémoire
docker stats

# Passer à un modèle plus léger si nécessaire
docker exec ollama ollama pull mistral  # 7B au lieu de 13B+
```

---

## 📈 Performances

### Metrics observées (Mac M4 Pro, 64 Go RAM)

| Modèle | Taille | Tokens/sec | Latence première réponse | RAM utilisée |
|--------|--------|------------|--------------------------|--------------|
| Mistral 7B | 4.1 GB | ~40 tok/s | <100 ms | ~8 GB |
| Llama 3.2 8B | 4.7 GB | ~35 tok/s | <150 ms | ~9 GB |
| Qwen 2.5 Coder 32B | 19 GB | ~15 tok/s | <300 ms | ~24 GB |

**Consommation énergétique** : ~50W en charge (vs 150-200W serveur x86 classique)

**Benchmark RAG (ChromaDB)** :
- Recherche sémantique : <100 ms (corpus 1000 documents)
- Indexation : ~2-5 sec par document (selon taille)

---

## 🔒 Sécurité & Conformité

### Souveraineté des données

- ✅ **100% on-premise** : Aucune donnée envoyée à OpenAI, Google ou autre cloud US
- ✅ **RGPD by design** : 
  - Données hébergées localement
  - Droit d'effacement : `docker-compose down -v`
  - Chiffrement au repos : Volumes Docker chiffrés (FileVault macOS)
  
### Authentification

- OpenWebUI : Authentification par email/password
- API Ollama : Accès localhost uniquement (ou via reverse proxy avec auth)
- ChromaDB : Accès restreint au réseau Docker

### Backups recommandés

```bash
#!/bin/bash
# Script backup automatique (à planifier via cron)
BACKUP_DIR="/Volumes/NAS/backups/ai-stack"
DATE=$(date +%Y%m%d-%H%M%S)

# Arrêter services
docker-compose -f ~/ai-sovereign-stack/docker-compose.yml down

# Backup volumes
sudo rsync -avz /var/lib/docker/volumes/ $BACKUP_DIR/volumes-$DATE/

# Backup configuration
tar -czf $BACKUP_DIR/config-$DATE.tar.gz ~/ai-sovereign-stack/

# Redémarrer services
docker-compose -f ~/ai-sovereign-stack/docker-compose.yml up -d
```

### Recommandations production

- Reverse proxy HTTPS (Nginx/Traefik) pour OpenWebUI
- Segmentation réseau VLAN
- Monitoring Prometheus + alertes
- Rate limiting API Ollama

---

## Idées d'évolutions futures

**Phase 3 - Monitoring & Sécurité** (prévu) :
- [ ] Intégration Prometheus + Node Exporter
- [ ] Dashboards Grafana personnalisés
- [ ] Logs centralisés vers Wazuh SIEM
- [ ] Alerting automatique (service down, RAM saturée)

**Phase 4 - Cas d'usage avancés** :
- [ ] Chatbot support IT basé sur documentation interne
- [ ] Analyse automatique logs pfSense avec IA
- [ ] Génération rapports conformité ISO 27001
- [ ] Assistant troubleshooting avec base de connaissances

**Phase 5 - Scalabilité** :
- [ ] Load balancing Ollama (plusieurs instances)
- [ ] Migration vers Kubernetes (K3s)
- [ ] Haute disponibilité ChromaDB

---

## 📚 Ressources

**Documentation officielle :**
- [Ollama](https://ollama.ai/docs)
- [OpenWebUI](https://docs.openwebui.com)
- [ChromaDB](https://docs.trychroma.com)

**Communauté :**
- [Discord Ollama](https://discord.gg/ollama)
- [Reddit r/LocalLLaMA](https://reddit.com/r/LocalLLaMA)
- [Reddit r/selfhosted](https://reddit.com/r/selfhosted)




---

##  Conclusion


- Déployer une infrastructure IA complète et sécurisée
- Maîtriser l'architecture conteneurisée (Docker)
- Comprendre les enjeux de conformité 
- Automatiser les processus critiques
- Documenter de manière professionnelle

La mise en place de cette stack IA souveraine s'inscrit dans une démarche de **reconversion professionnelle en cybersécurité**, démontrant un positionnement unique combinant expertise data, infrastructure et sécurité.

---


*Dernière mise à jour : Janvier 2026*  
*Version : 1.0*  
*Projet réalisé dans le cadre d'une reconversion en cybersécurité*
