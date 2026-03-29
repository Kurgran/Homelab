#!/bin/bash
# =============================================================================
# pfsense-block.sh — Active Response Wazuh -> pfSense via SSH + pfctl
# Version : 1.0
# Auteur  : Clément Appercel — https://github.com/Kurgran
#
# Ce script est exécuté par Wazuh Manager (location=local) quand une règle
# configurée dans ossec.conf dépasse le level seuil.
#
# Il se connecte à pfSense en SSH avec une clé dédiée et ajoute ou retire
# l'IP attaquante dans la table pfctl "wazuh_blocked".
#
# pfSense CE n'ayant pas d'API REST (réservée à pfSense Plus), le passage
# par SSH est la seule option disponible sur pfSense Community Edition.
#
# Prérequis (voir ossec-active-response.conf pour la config ossec.conf) :
#   1. Table pfctl "wazuh_blocked" créée sur pfSense (Firewall > Tables)
#   2. Règle BLOCK IN from <wazuh_blocked> active sur l'interface WAN
#   3. Clé SSH Ed25519 générée sur le Manager, user restreint sur pfSense
#   4. Ce fichier placé dans /var/ossec/active-response/bin/ (chmod 750)
#   5. Clé privée SSH dans /var/ossec/active-response/bin/.ssh/wazuh_ar_key
# =============================================================================

# --- Configuration -----------------------------------------------------------
PFSENSE_HOST="192.168.20.1"        # IP de pfSense sur le réseau de management
PFSENSE_USER="wazuh_ar"            # Utilisateur SSH restreint créé sur pfSense
SSH_KEY="/var/ossec/active-response/bin/.ssh/wazuh_ar_key"
PFCTL_TABLE="wazuh_blocked"        # Nom de la table pfctl dans pfSense
LOG_FILE="/var/ossec/logs/active-responses.log"

# --- Fonction de log ---------------------------------------------------------
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [pfsense-block] $1" >> "$LOG_FILE"
}

# --- Lecture du JSON Wazuh depuis stdin --------------------------------------
# Wazuh 4.x passe les paramètres en JSON sur stdin, pas en arguments CLI.
INPUT=$(cat)
log "Input reçu : $INPUT"

# --- Extraction de l'action et de l'IP ---------------------------------------
ACTION=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('command', ''))
except Exception as e:
    print('')
")

SRCIP=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    ip = d.get('parameters', {}).get('alert', {}).get('data', {}).get('srcip', '')
    print(ip)
except Exception as e:
    print('')
")

# --- Validation --------------------------------------------------------------
if [ -z "$SRCIP" ]; then
    log "ERREUR : pas d'IP source dans le payload JSON"
    exit 1
fi

# Valider le format IPv4 (protection contre injection de commande)
if ! [[ "$SRCIP" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
    log "ERREUR : format IP invalide — $SRCIP"
    exit 1
fi

if [ -z "$ACTION" ]; then
    log "ERREUR : action vide dans le payload JSON"
    exit 1
fi

log "Action : $ACTION | IP : $SRCIP"

# --- Exécution ---------------------------------------------------------------
if [ "$ACTION" = "add" ]; then
    RESULT=$(ssh -i "$SSH_KEY" \
        -o StrictHostKeyChecking=no \
        -o ConnectTimeout=5 \
        -o BatchMode=yes \
        "$PFSENSE_USER@$PFSENSE_HOST" \
        "pfctl -t $PFCTL_TABLE -T add $SRCIP" 2>&1)
    if [ $? -eq 0 ]; then
        log "BLOQUÉE : $SRCIP ajoutée à la table $PFCTL_TABLE"
    else
        log "ERREUR SSH add : $RESULT"
        exit 1
    fi

elif [ "$ACTION" = "delete" ]; then
    RESULT=$(ssh -i "$SSH_KEY" \
        -o StrictHostKeyChecking=no \
        -o ConnectTimeout=5 \
        -o BatchMode=yes \
        "$PFSENSE_USER@$PFSENSE_HOST" \
        "pfctl -t $PFCTL_TABLE -T delete $SRCIP" 2>&1)
    if [ $? -eq 0 ]; then
        log "DÉBLOQUÉE : $SRCIP retirée de la table $PFCTL_TABLE (timeout expiré)"
    else
        log "ERREUR SSH delete : $RESULT"
        exit 1
    fi

else
    log "ERREUR : action inconnue — $ACTION"
    exit 1
fi

exit 0
