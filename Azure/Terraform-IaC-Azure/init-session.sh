#!/usr/bin/env bash
# =============================================================================
# init-session.sh — Initialisation de session Terraform Azure
# =============================================================================
# Usage : source init-session.sh   (PAS ./init-session.sh — voir note plus bas)
# Prérequis : az login actif (compte Owner)
# =============================================================================

set -euo pipefail
# set -e  : stoppe le script dès qu'une commande échoue (pas de silent failure)
# set -u  : erreur si une variable non définie est utilisée
# set -o pipefail : si une commande dans un pipe échoue, le pipe entier échoue

VAULT_NAME="kv-terraform-lab-clem"
# Nom du Key Vault Azure — centralisé ici pour ne modifier qu'un seul endroit si changement

echo "🔐 Récupération des credentials Terraform depuis Key Vault..."

# --- ARM_CLIENT_SECRET : seul secret stocké dans Key Vault ---
# az keyvault secret show → lit le secret dans Azure
# --query value → extrait uniquement le champ "value" du JSON retourné
# -o tsv → format texte brut (pas de guillemets, pas de mise en forme JSON)
# $() → command substitution : capture l'output de la commande dans la variable
export ARM_CLIENT_SECRET=$(az keyvault secret show \
  --vault-name "$VAULT_NAME" \
  --name "ARM-CLIENT-SECRET" \
  --query value \
  -o tsv)

# --- Les 3 autres variables : non sensibles, définies en dur dans le script ---
# ARM_CLIENT_ID     : l'appId du Service Principal sp-terraform-lab (pas un secret)
# ARM_TENANT_ID     : l'ID du tenant Azure AD (pas un secret)
# ARM_SUBSCRIPTION_ID : l'ID de la subscription (pas un secret)
export ARM_CLIENT_ID="5edbef96-c215-4441-a148-6660d0f047ca"
export ARM_TENANT_ID="28387a45-64c4-44f1-b700-6be137854365"
export ARM_SUBSCRIPTION_ID="53dd11b0-148d-4875-ac92-9c690e8d9d9e"

echo "✅ Variables ARM_* exportées en mémoire terminal."
echo "   → ARM_CLIENT_ID       : $ARM_CLIENT_ID"
echo "   → ARM_CLIENT_SECRET   : [masqué]"
echo "   → ARM_TENANT_ID       : $ARM_TENANT_ID"
echo "   → ARM_SUBSCRIPTION_ID : $ARM_SUBSCRIPTION_ID"
echo ""
echo "🚀 Terraform est prêt. Lance : terraform plan"

# Restauration des options shell — indispensable quand le script est sourcé
# set -euo pipefail modifie les options du shell COURANT via source.
# Sans cette ligne, zsh reste en mode "exit on error" après le script,
# ce qui tue le terminal dès qu'une fonction du prompt retourne non-zéro.
set +euo pipefail

# =============================================================================
# POURQUOI "source init-session.sh" ET PAS "./init-session.sh" ?
# =============================================================================
# "./init-session.sh" lance le script dans un SOUS-SHELL (processus enfant).
# Les variables exportées dans ce sous-shell disparaissent quand il se termine.
# Terraform ne les voit pas.
#
# "source init-session.sh" (ou ". init-session.sh") exécute le script dans le
# SHELL COURANT. Les variables exportées restent en mémoire dans ton terminal.
# Terraform les voit quand tu le lances ensuite.
# =============================================================================
