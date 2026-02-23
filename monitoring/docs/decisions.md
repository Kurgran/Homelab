# Journal des Décisions Techniques (ADR)

> **ADR** = Architecture Decision Record — document qui capture *pourquoi* un choix a été fait, pas seulement *ce qui* a été fait. Essentiel pour comprendre le projet 6 mois plus tard ou pour le reproduire.

---

## ADR-001 — Node Exporter natif plutôt que conteneurisé

**Date** : Octobre 2025  
**Statut** : ✅ Actif

### Problème
Node Exporter déployé dans un conteneur Docker remonte les métriques de la VM Linux interne à Docker Desktop (noyau Linux virtualisé), pas celles du hardware réel du Mac.

### Décision
Installer Node Exporter **nativement** via Homebrew sur macOS, et via les gestionnaires de paquets natifs sur le NAS Synology et pfSense.

### Conséquences
- ✅ Métriques CPU, RAM, disques et réseau fidèles au hardware réel
- ✅ Pas de couche de virtualisation parasite
- ⚠️ Gestion manuelle des mises à jour (hors cycle Docker)
- ⚠️ Installation différente sur chaque OS (Homebrew / apt / pfSense pkg)

---

## ADR-002 — Approche hybride Node Exporter + SNMP

**Date** : Décembre 2025  
**Statut** : ✅ Actif

### Problème
SNMP Exporter v0.29.0+ a supprimé le module `host_resources_mib` qui permettait de collecter CPU, RAM et disques via SNMP. Utiliser uniquement SNMP ne couvre donc plus les métriques système.

### Décision
Approche **hybride** :
- **Node Exporter** → métriques système (CPU, RAM, disques, charge)
- **SNMP Exporter** → métriques réseau (interfaces, trafic, erreurs)

### Conséquences
- ✅ Couverture complète sans modules SNMP complexes
- ✅ Métriques système plus riches qu'avec SNMP seul
- ⚠️ Deux agents à maintenir par équipement (sauf MikroTik : SNMP uniquement)

---

## ADR-003 — Fichier snmp.yml hybride (auth custom + module officiel)

**Date** : Janvier 2026  
**Statut** : ✅ Actif

### Problème
Le fichier `snmp.yml` officiel Prometheus (~150 modules) utilisait des noms d'authentification différents, cassant les configs NAS/pfSense existantes lors de son déploiement. Rollback immédiat nécessaire.

### Décision
Créer un fichier `snmp.yml` **hybride** qui combine :
- Une section `auths` personnalisée (`public_v2` avec community `public` en SNMPv2c)
- Le module `if_mib` extrait du fichier officiel (~1250 lignes), seul module nécessaire

### Conséquences
- ✅ Un seul fichier snmp.yml universel pour les 3 équipements
- ✅ Compatibilité validée : NAS (13 interfaces), pfSense (13), MikroTik (14)
- ⚠️ Mise à jour manuelle si le module officiel if_mib évolue
- ⚠️ Community string `public` en clair — acceptable en homelab, à migrer vers SNMPv3 en environnement sensible

---

## ADR-004 — Loki + Promtail pour la centralisation des logs

**Date** : Janvier 2026  
**Statut** : ✅ Actif

### Problème
La stack ne collectait que des métriques (Prometheus). Pas de logs centralisés = impossible de corréler un pic de CPU avec un événement système, ni d'avoir une vision SOC complète.

### Décision
Ajouter **Loki** (stockage/indexation des logs) et **Promtail** (collecteur Syslog UDP) à la stack Docker existante.

### Conséquences
- ✅ Corrélation métriques + logs dans une même interface Grafana
- ✅ Vision SOC : pfSense, NAS et Mac centralisés
- ✅ Requêtes LogQL disponibles pour l'analyse et la détection

---

## ADR-005 — UDP plutôt que TCP pour Syslog

**Date** : Janvier 2026  
**Statut** : ✅ Actif

### Problème
Choix du protocole de transport pour la réception des logs Syslog.

### Décision
UDP (User Datagram Protocol) plutôt que TCP.

### Raisonnement
UDP est "fire and forget" : si Promtail est surchargé ou temporairement indisponible, l'équipement source (pfSense, NAS) ne ralentit pas. On préfère perdre quelques événements de log plutôt que d'impacter les performances du firewall avec des confirmations TCP.

### Conséquences
- ✅ Zéro impact sur les performances de pfSense
- ✅ Compatible nativement avec pfSense et Synology
- ⚠️ Perte possible de logs si Promtail est indisponible (acceptable en homelab)