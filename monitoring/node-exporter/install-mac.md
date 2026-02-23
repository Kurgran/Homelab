# Installation Node Exporter — Mac Mini Pro (macOS)

> **Pourquoi natif et pas Docker ?** Node Exporter dans un conteneur Docker remonte les métriques de la VM Linux interne à Docker Desktop, pas celles du hardware Mac réel. L'installation native via Homebrew garantit l'accès aux vraies métriques CPU, RAM et disques.

## Prérequis

- Homebrew installé (`brew --version` pour vérifier)
- Docker Desktop en cours d'exécution

---

## Installation

```bash
# Installer Node Exporter via Homebrew
brew install node_exporter

# Démarrer le service et l'activer au démarrage
brew services start node_exporter
```

## Vérification

```bash
# Vérifier que le service est actif
brew services list | grep node_exporter
# Attendu : node_exporter  started

# Vérifier que les métriques sont accessibles
curl http://localhost:9100/metrics | head -20

# Vérifier depuis Docker (test de connectivité host.docker.internal)
curl http://host.docker.internal:9100/metrics | grep node_cpu | head -5
```

## Configuration dans prometheus.yml

Le job correspondant dans `stack/prometheus/prometheus.yml` utilise `host.docker.internal` pour sortir du réseau Docker et atteindre le service natif :

```yaml
- job_name: 'mac-m4-pro'
  static_configs:
    - targets: ['host.docker.internal:9100']
```

## Mise à jour

```bash
brew upgrade node_exporter
brew services restart node_exporter
```