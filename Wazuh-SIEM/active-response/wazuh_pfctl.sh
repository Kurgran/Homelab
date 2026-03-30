#!/bin/sh
# =============================================================================
# wazuh_pfctl.sh — Wrapper de sécurité SSH pour pfSense
# Auteur  : Clément Appercel — https://github.com/Kurgran
#
# Ce script est déployé sur pfSense dans /usr/local/bin/wazuh_pfctl.sh
# et référencé dans /root/.ssh/authorized_keys via l'option command=.
#
# Il filtre les commandes SSH autorisées via la variable $SSH_ORIGINAL_COMMAND.
# Toute commande non listée est rejetée et journalisée.
#
# Contexte : pfSense CE n'a pas de sudo/doas. La connexion s'effectue en root
# avec une clé dédiée. Le wrapper compense l'absence de séparation de privilèges
# en n'autorisant que les opérations pfctl strictement nécessaires.
#
# Déploiement :
#   1. Copier ce fichier dans /usr/local/bin/wazuh_pfctl.sh sur pfSense
#   2. chmod 755 /usr/local/bin/wazuh_pfctl.sh
#   3. Dans /root/.ssh/authorized_keys, ajouter la clé avec :
#      command="/usr/local/bin/wazuh_pfctl.sh",from="<IP_WAZUH_MANAGER>",restrict ssh-ed25519 AAAA...
#
# Note : le shell par défaut de pfSense/FreeBSD est tcsh. Ce script utilise
# /bin/sh (compatible POSIX) pour éviter les problèmes d'expansion tcsh.
# =============================================================================

case "$SSH_ORIGINAL_COMMAND" in
    "pfctl -t wazuh_blocked -T add "*)
        eval "$SSH_ORIGINAL_COMMAND"
        ;;
    "pfctl -t wazuh_blocked -T delete "*)
        eval "$SSH_ORIGINAL_COMMAND"
        ;;
    "pfctl -t wazuh_blocked -T show")
        eval "$SSH_ORIGINAL_COMMAND"
        ;;
    *)
        echo "REJECTED: $SSH_ORIGINAL_COMMAND" >> /var/log/wazuh_pfctl_rejected.log
        exit 1
        ;;
esac
