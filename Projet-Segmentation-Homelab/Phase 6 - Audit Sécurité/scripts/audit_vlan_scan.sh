#!/bin/bash
# audit_vlan_scan.sh
# Scan nmap multi-phases pour audit d'un VLAN
# Usage : ./audit_vlan_scan.sh
# Résultats dans : /tmp/audit_VLANxx_YYYYMMDD_HHMM/
#
# Prérequis : nmap installé (apt install nmap -y)
# Lancer depuis la machine de scan (ex: Kali Linux sur VLAN_MGMT)

set -e

# --- Auto-détection du subnet ---
INTERFACE=$(ip route | grep default | awk '{print $5}' | head -1)
SUBNET=$(ip -o -f inet addr show "$INTERFACE" | awk '{print $4}')
VLAN_ID=$(echo "$SUBNET" | cut -d'.' -f3)
TIMESTAMP=$(date +%Y%m%d_%H%M)
OUTPUT_DIR="/tmp/audit_VLAN${VLAN_ID}_${TIMESTAMP}"

mkdir -p "$OUTPUT_DIR"

echo "[*] Interface : $INTERFACE"
echo "[*] Subnet    : $SUBNET"
echo "[*] Output    : $OUTPUT_DIR"
echo ""

# --- Phase 1 : découverte des hôtes ---
echo "[Phase 1] Découverte des hôtes..."
nmap -sn "$SUBNET" -oN "$OUTPUT_DIR/phase1_discovery.txt"
echo "[Phase 1] Terminé. Résultats : $OUTPUT_DIR/phase1_discovery.txt"
echo ""

# --- Phase 2 : scan TCP complet sur les hôtes actifs ---
echo "[Phase 2] Scan TCP complet (-p-)..."
# Extraction des IPs découvertes en Phase 1
HOSTS=$(grep "Nmap scan report" "$OUTPUT_DIR/phase1_discovery.txt" | awk '{print $NF}')
nmap -p- -sV --open -T4 $HOSTS -oN "$OUTPUT_DIR/phase2_tcp_full.txt"
echo "[Phase 2] Terminé. Résultats : $OUTPUT_DIR/phase2_tcp_full.txt"
echo ""

# --- Phase 3 : scan UDP ports courants ---
echo "[Phase 3] Scan UDP ports courants..."
nmap -sU --top-ports 20 -T4 $HOSTS -oN "$OUTPUT_DIR/phase3_udp.txt"
echo "[Phase 3] Terminé. Résultats : $OUTPUT_DIR/phase3_udp.txt"
echo ""

echo "[*] Audit terminé. Tous les résultats dans : $OUTPUT_DIR"
echo "[*] Récapitulatif des ports ouverts (TCP) :"
grep "open" "$OUTPUT_DIR/phase2_tcp_full.txt" | grep -v "^#" || echo "  Aucun port ouvert trouvé"
