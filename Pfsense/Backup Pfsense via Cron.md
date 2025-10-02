# 🔒 Automatisation de sauvegarde pfSense vers NAS Synology

> Projet de formation en cybersécurité - Mise en place d'un système de sauvegarde automatisé, fiable et testé pour garantir la résilience d'une infrastructure réseau.

## 📋 Table des matières

- [Contexte et justification](#-contexte-et-justification-du-projet)
- [Architecture technique](#-architecture-technique)
- [Problèmes rencontrés](#-problèmes-rencontrés-et-solutions)
- [Script final](#-script-final)
- [Configuration](#-configuration-étape-par-étape)
- [Tests et validation](#-tests-et-validation)
- [Maintenance](#-maintenance-et-surveillance)
- [Leçons apprises](#-leçons-apprises)

---

## 🎯 Contexte et justification du projet

### La criticité des sauvegardes de configuration firewall

Dans toute infrastructure réseau, le pare-feu constitue le point névralgique de la sécurité. Il contrôle l'ensemble des flux entrants et sortants, applique les politiques de sécurité, gère les règles de filtrage, les VPN, les VLAN et de nombreux autres aspects critiques de la sécurité réseau. La perte de la configuration d'un pare-feu représente un risque majeur qui peut paralyser complètement une infrastructure.

**Scénarios de perte de configuration :**
- Défaillance matérielle du pare-feu (panne disque, corruption mémoire)
- Mise à jour système qui échoue et corrompt la configuration
- Erreur humaine lors d'une modification (suppression accidentelle de règles critiques)
- Compromission du pare-feu par un attaquant qui modifie ou détruit la configuration
- Catastrophe physique (incendie, inondation, vol)

**Impact d'une perte de configuration sans sauvegarde :**
- Interruption totale de la connectivité réseau (plusieurs heures à plusieurs jours)
- Perte de toutes les règles de sécurité minutieusement configurées
- Reconstruction manuelle de la configuration (chronophage et source d'erreurs)
- Incapacité à prouver la conformité réglementaire (certaines normes exigent des sauvegardes)
- Coût financier important (temps d'arrêt, perte de productivité)

### Objectif de ce projet

Ce projet s'inscrit dans une démarche de **sécurité proactive** et de **résilience opérationnelle**. L'objectif est de mettre en place un système de sauvegarde automatisé, fiable et testé qui garantit la disponibilité d'une copie récente de la configuration du pare-feu à tout moment.

**Principes de sécurité appliqués :**

1. **Automatisation** : Éliminer le facteur humain (oubli, négligence) en automatisant complètement le processus
2. **Planification régulière** : Sauvegardes hebdomadaires programmées (dimanche 3h00) 
3. **Stockage externalisé** : Sauvegarde sur un système distinct du pare-feu
4. **Authentification forte** : Clés SSH RSA 2048 bits au lieu de mots de passe
5. **Traçabilité** : Logs détaillés de chaque opération pour audit
6. **Testabilité** : Validation manuelle et tests de restauration possibles

### Technologies utilisées

- **pfSense 2.8.1** (FreeBSD)
- **NAS Synology DSM**
- **Shell script** (sh)
- **SSH/SCP** avec authentification par clé publique
- **Cron** pour l'automatisation

---

## 🏗️ Architecture technique

```text
┌─────────────┐         SSH/SCP          ┌──────────────┐
│   pfSense   │ ──────────────────────>  │ NAS Synology │
│  Firewall   │   Port 2222             │   Storage    │
│             │   Clé publique RSA      │              │
│ 10.0.50.1   │                         │ 10.0.50.100  │
└─────────────┘                         └──────────────┘
      │                                         │
      │                                         │
   Cron Job                              /volume1/Backups/pfSense/
   Tous les                              pfsense-config-YYYY-MM-DD.xml
   dimanches 3h00
```

---

## ⚠️ Problèmes rencontrés et solutions

### 1️⃣ Incompatibilité bash/sh sur pfSense

**Problème :** Le script initial utilisait `#!/bin/bash` mais bash n'est pas installé sur pfSense.

**Solution :** Réécriture complète pour `/bin/sh` (POSIX standard).

```bash
# Avant (bash)
set -euo pipefail

# Après (sh compatible)
set -eu
```

---

### 2️⃣ Échec du sous-système SFTP

**Problème :** OpenSSH tente d'utiliser SFTP par défaut, mais le NAS Synology bloque ce sous-système.

```text
subsystem request failed on channel 0
scp: Connection closed
```

**Solution :** Forcer le protocole SCP legacy avec l'option `-O`.

```bash
scp -O -P "${NAS_PORT}" -i "${SSH_KEY}" [...]
```

---

### 3️⃣ Shell /sbin/nologin sur le NAS

**Problème majeur :** L'utilisateur de sauvegarde avait le shell `/sbin/nologin`, empêchant toute connexion SSH. Synology réinitialise ce paramètre à chaque redémarrage.

**Solution en deux étapes :**

**Étape 1 - Modifier le shell manuellement :**

```bash
sudo vi /etc/passwd
# Changer /sbin/nologin en /bin/sh pour l'utilisateur
```

**Étape 2 - Créer un script de démarrage persistant :**

```bash
#!/bin/sh
# /usr/local/etc/rc.d/S99fix-backup-shell.sh
sed -i "s|backup_user:x:\([0-9]*\):\([0-9]*\):\(.*\):/sbin/nologin|backup_user:x:\1:\2:\3:/bin/sh|" /etc/passwd
```

---

### 4️⃣ Problèmes d'encodage UTF-8

**Problème :** L'édition avec MobaXterm (Windows) introduisait des caractères UTF-8 invisibles cassant l'exécution.

**Solution :** Toujours éditer directement sur pfSense avec l'éditeur `ee`.

---

### 5️⃣ Environnement cron minimal

**Problème :** Le script fonctionnait en manuel mais échouait via cron (environnement minimal).

**Solution :** Export explicite des variables d'environnement.

```bash
export HOME=/root
export USER=root
export LOGNAME=root
export SHELL=/bin/sh
export PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin
```

---

## 📝 Script final

### Script de sauvegarde complet

```bash
#!/bin/sh

# Configuration de l'environnement pour compatibilité cron
export HOME=/root
export USER=root
export LOGNAME=root
export SHELL=/bin/sh
export PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin

# Variables de configuration
NAS_USER="backup_user"
NAS_IP="10.0.50.100"
NAS_PORT="2222"
NAS_DEST_PATH="/volume1/Backups/pfSense/"
SSH_KEY="/var/ssh_keys/nas_backup"
PF_CONFIG_FILE="/cf/conf/config.xml"
LOG_FILE="/var/log/pfsense_backup.log"

# Configuration de sécurité du script
set -eu

# Fonction de logging
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S'): $1" | tee -a "$LOG_FILE"
}

log_message "=== Début de sauvegarde pfSense ==="

# Vérifications préalables
if [ ! -f "$SSH_KEY" ]; then
    log_message "ERREUR: Clé SSH introuvable à $SSH_KEY"
    exit 1
fi

if [ ! -f "$PF_CONFIG_FILE" ]; then
    log_message "ERREUR: Configuration pfSense introuvable"
    exit 1
fi

# Permissions de la clé SSH
chmod 600 "$SSH_KEY" 2>/dev/null || log_message "INFO: Permissions SSH non modifiables"

# Test de connectivité réseau
log_message "Test de connectivité vers $NAS_IP:$NAS_PORT"
if ! nc -z "$NAS_IP" "$NAS_PORT" 2>/dev/null; then
    log_message "ERREUR: NAS inaccessible sur $NAS_IP:$NAS_PORT"
    exit 1
fi

# Préparation du transfert
DATE=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_FILE="pfsense-config-${DATE}.xml"
SOURCE_SIZE=$(stat -f "%z" "$PF_CONFIG_FILE")

log_message "Transfert SCP : $BACKUP_FILE ($SOURCE_SIZE octets)"

# Transfert SCP avec protocole legacy
if scp -O -P "$NAS_PORT" -i "$SSH_KEY" \
    -o ConnectTimeout=30 \
    -o BatchMode=yes \
    -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    "$PF_CONFIG_FILE" "$NAS_USER@$NAS_IP:$NAS_DEST_PATH$BACKUP_FILE" 2>> "$LOG_FILE"; then
    
    log_message "SUCCÈS: Sauvegarde terminée - $BACKUP_FILE"
    
else
    log_message "ÉCHEC: Transfert SCP échoué"
    exit 1
fi

log_message "=== Fin de sauvegarde ==="
```

---

## ⚙️ Configuration étape par étape

### Configuration sur pfSense

#### 1. Création du répertoire et génération des clés SSH

```bash
mkdir -p /var/ssh_keys
ssh-keygen -t rsa -b 2048 -f /var/ssh_keys/nas_backup -N ""
cat /var/ssh_keys/nas_backup.pub
```

#### 2. Création du script de sauvegarde

```bash
mkdir -p /var/scripts
ee /var/scripts/pfsense_backup.sh
# Coller le contenu du script ci-dessus
chmod +x /var/scripts/pfsense_backup.sh
```

#### 3. Configuration de cron

Via l'interface web pfSense :
- System > Advanced > Cron
- **Minute :** `0`
- **Hour :** `3`
- **Day of Month :** `*`
- **Month :** `*`
- **Day of Week :** `0` (dimanche)
- **User :** `root`
- **Command :** `/var/scripts/pfsense_backup.sh`

---

### Configuration sur le NAS Synology

#### 1. Création de l'utilisateur (via interface web)

- Panneau de contrôle > Utilisateur et groupe
- Créer l'utilisateur `backup_user`
- Désactiver l'accès à tous les services sauf SSH

#### 2. Configuration du groupe SSH (en ligne de commande)

```bash
# Connexion SSH avec compte admin
ssh admin@10.0.50.100 -p 2222

# Ajouter l'utilisateur au groupe SSH
sudo groupadd sshusers 2>/dev/null || true
sudo usermod -aG sshusers backup_user
```

#### 3. Configuration du shell et clé SSH

```bash
# Modifier le shell
sudo vi /etc/passwd
# Changer /sbin/nologin en /bin/sh pour backup_user

# Créer le répertoire SSH
sudo mkdir -p /var/services/homes/backup_user/.ssh

# Ajouter la clé publique
sudo bash -c 'echo "COLLER_LA_CLE_PUBLIQUE_ICI" > /var/services/homes/backup_user/.ssh/authorized_keys'

# Permissions correctes
sudo chmod 600 /var/services/homes/backup_user/.ssh/authorized_keys
sudo chown backup_user:users /var/services/homes/backup_user/.ssh/authorized_keys
```

#### 4. Script de démarrage pour persistance du shell

```bash
# Créer le script de correction automatique
sudo sh -c 'cat > /usr/local/etc/rc.d/S99fix-backup-shell.sh << "EOF"
#!/bin/sh
# Script pour corriger le shell de backup_user au démarrage
sed -i "s|backup_user:x:\([0-9]*\):\([0-9]*\):\(.*\):/sbin/nologin|backup_user:x:\1:\2:\3:/bin/sh|" /etc/passwd
EOF'

# Rendre le script exécutable
sudo chmod +x /usr/local/etc/rc.d/S99fix-backup-shell.sh
```

#### 5. Vérification des permissions du dossier de destination

```bash
ls -la /volume1/Backups/pfSense/
# Doit être accessible en écriture par backup_user
```

---

## ✅ Tests et validation

### Test manuel du script

```bash
# Test exécution normale
/var/scripts/pfsense_backup.sh

# Test environnement cron simulé
env -i SHELL=/bin/sh PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin /var/scripts/pfsense_backup.sh

# Vérifier les logs
tail -20 /var/log/pfsense_backup.log
```

### Test de la connexion SSH

```bash
# Test connexion simple
ssh -i /var/ssh_keys/nas_backup -p 2222 backup_user@10.0.50.100

# Test SCP direct
scp -O -P 2222 -i /var/ssh_keys/nas_backup /cf/conf/config.xml backup_user@10.0.50.100:/volume1/Backups/pfSense/test.xml
```

### Vérification après redémarrage du NAS

```bash
# Vérifier que le shell est toujours correct
ssh -p 2222 backup_user@10.0.50.100 "grep backup_user /etc/passwd"
# Doit afficher /bin/sh et non /sbin/nologin
```

### Vérification de l'exécution cron

```bash
# Le lendemain, vérifier les logs
tail -20 /var/log/pfsense_backup.log

# Vérifier les fichiers créés sur le NAS
ssh -p 2222 backup_user@10.0.50.100 "ls -ltr /volume1/Backups/pfSense/ | tail -5"
```

---

## 🔧 Maintenance et surveillance

### Rotation des sauvegardes

Le script accumule indéfiniment les sauvegardes. Script de nettoyage recommandé :

```bash
#!/bin/sh
# Conserver seulement les 30 dernières sauvegardes
ssh -i /var/ssh_keys/nas_backup -p 2222 backup_user@10.0.50.100 \
  "cd /volume1/Backups/pfSense && ls -t pfsense-config-*.xml | tail -n +31 | xargs rm -f"
```

### Alertes en cas d'échec

Ajouter une notification par email :

```bash
if [ $? -ne 0 ]; then
    echo "Échec sauvegarde pfSense $(date)" | mail -s "Alerte sauvegarde" admin@example.com
fi
```

### Monitoring recommandé

- **Logs :** `/var/log/pfsense_backup.log`
- **Espace disque** sur le NAS
- **Test de restauration** occasionnel

---

## 📚 Leçons apprises

### 1. Incompatibilités entre environnements Unix

Les différences entre FreeBSD (pfSense) et Linux (Synology DSM) nécessitent une attention particulière. Ce qui fonctionne sur un système peut échouer silencieusement sur l'autre.

### 2. Importance de l'environnement d'exécution

Les scripts cron s'exécutent dans un environnement minimal. Toutes les variables d'environnement nécessaires doivent être explicitement définies.

### 3. Persistance des configurations sur Synology

Synology régénère certains fichiers système au démarrage. Les modifications manuelles doivent être automatisées via des scripts de démarrage.

### 4. Encodage et outils d'édition

L'édition depuis Windows peut introduire des caractères invisibles. Toujours éditer directement sur le système cible.

### 5. Diagnostic méthodique

Une approche systématique (test de chaque composant individuellement) permet d'identifier précisément la source du problème.

### 6. Option -O cruciale pour SCP

Les versions récentes d'OpenSSH tentent d'utiliser SFTP par défaut. L'option `-O` force le protocole SCP legacy.

---

## 🔐 Aspects sécurité et conformité

### Sécurité de la solution

**Points forts :**
- ✅ Authentification par clé cryptographique (pas de mot de passe stocké)
- ✅ Transport chiffré via SSH
- ✅ Clé privée protégée par permissions 600
- ✅ Logging complet pour audit
- ✅ Séparation des privilèges (utilisateur dédié)

**Points d'attention :**
- ⚠️ Clé SSH sans passphrase (nécessaire pour l'automatisation)
- ⚠️ Option StrictHostKeyChecking désactivée (pour éviter les blocages cron)
- ⚠️ Pas de chiffrement supplémentaire des fichiers de sauvegarde

### Conformité réglementaire

Cette approche répond aux exigences de :

- **ISO 27001** : Gestion de la continuité d'activité (A.17.1.2)
- **NIST Cybersecurity Framework** : Fonction "Protect" - PR.IP-4 (Sauvegardes)
- **RGPD** : Article 32 (Mesures de sécurité appropriées)

---

## 🚀 Améliorations futures possibles

1. **Chiffrement des sauvegardes** : Ajouter GPG avant transfert
2. **Sauvegarde différentielle** : Ne sauvegarder que si la configuration a changé
3. **Sauvegardes multiples** : Vers plusieurs destinations (résilience)
4. **Validation post-transfert** : Vérifier l'intégrité avec checksum
5. **Métriques** : Statistiques sur les sauvegardes (durée, taille)
6. **Rotation intelligente** : 7 quotidiennes + 4 hebdomadaires + 12 mensuelles

---


### Compétences démontrées

- Administration système Unix/FreeBSD
- Scripting shell (sh)
- Automatisation et planification (cron)
- Sécurité SSH/SCP avec authentification par clé publique
- Diagnostic et résolution de problèmes complexes
- Persistance de configurations système
- Compréhension des enjeux de sécurité et de continuité d'activité

---

## 🎯 Conclusion

Ce projet démontre l'application concrète de principes de sécurité fondamentaux dans un contexte d'infrastructure réseau réelle. Au-delà de l'aspect technique, il illustre l'importance d'une **approche proactive de la sécurité** : anticiper les risques, automatiser les processus critiques, et documenter les procédures.

La mise en place de ce système de sauvegarde automatisé garantit la **résilience de l'infrastructure** en cas d'incident majeur et s'inscrit dans une démarche plus large de gestion des risques et de continuité d'activité.

---

