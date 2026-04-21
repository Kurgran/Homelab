# Phase 6 — Audit sécurité post-segmentation VLAN

**Description courte :** Audit complet de l'infrastructure segmentée en 4 blocs : validation isolation VLAN (nmap), scan de vulnérabilités (Greenbone CE), durcissement CIS Benchmarks sur Proxmox (Wazuh SCA), et revue des règles firewall pfSense.

**Contexte homelab :** Proxmox ×3 (MINIFORUM 192.168.20.93, ASUS 192.168.20.94, TOPTON 192.168.20.95) + pfSense + MikroTik CRS310 + NAS Synology DS723+ + Mac Mini M4 Pro

**Date :** Avril 2026

---

## Vue d'ensemble

Après la segmentation VLAN (Phases 1-5), l'architecture existait sur le papier mais n'avait jamais été auditée. Cette phase vérifie que l'isolation fonctionne réellement, identifie les vulnérabilités, applique un durcissement CIS sur les hyperviseurs, et assainit les règles pfSense.

Blocs d'audit :

* **Bloc 1** — Scan nmap + validation isolation VLAN (scripts dans `/scripts/`)
* **Bloc 2** — Greenbone CE : scan de vulnérabilités sur 5 cibles
* **Bloc 3** — CIS Benchmarks Debian 12 via Wazuh SCA sur Proxmox ASUS (192.168.20.94)
* **Bloc 4** — Revue et assainissement des règles firewall pfSense

---

## Architecture de l'audit

```
Kali Linux (192.168.20.200, VLAN_MGMT)
    └── nmap — scan de tous les VLANs (Bloc 1)

Greenbone CE VM (192.168.30.106, VLAN_LAB)
    └── scan authentifié SSH — 5 cibles (Bloc 2)
        ├── Proxmox ×3 + Wazuh (VLAN_MGMT)
        ├── MikroTik CRS310 (VLAN_MGMT)
        ├── pfSense (VLAN_MGMT)
        ├── NAS Synology DS723+ (VLAN_SERVICES)
        └── Mac Mini M4 Pro (VLAN_LAN)

Proxmox ASUS NUC (192.168.20.94)
    └── Wazuh SCA — CIS Debian Linux 12 Benchmark v1.1.0 (Bloc 3)
```

---

## Résultats des scans

### Bloc 1 — Validation isolation VLAN

Isolation inter-VLAN confirmée : aucun trafic ne passe entre VLANs sans passer par pfSense.

Findings notables :

| Host | Finding | Action |
|---|---|---|
| MikroTik CRS310 (192.168.20.55) | Telnet (23) + FTP (21) ouverts | Désactivés |
| NAS Synology (192.168.50.17) | SSH port 22 ouvert en plus du port custom | À traiter |
| Inconnu (192.168.40.110) | MAC aléatoire, 0 port ouvert | Smartphone, accepté |

### Bloc 2 — Greenbone CE

| Cible | Critical | High | Medium | Low |
|---|---|---|---|---|
| Proxmox + Wazuh (.93/.94/.95/.100) | 4 | 12 | 21 | 12 |
| MikroTik CRS310 | 0 | 2 | 8 | 3 |
| pfSense | 0 | 1 | 4 | 2 |
| NAS Synology DS723+ | 0 | 1 | 1 | 2 |
| Mac Mini M4 Pro | 0 | 0 | 0 | 1 |

Les 4 Critical (CVSS 9.8) sur Proxmox étaient uniquement des packages Debian non mis à jour (libxml2, libxml-parser-perl, libnss3). Correction : `apt update && apt upgrade -y` + installation de `unattended-upgrades`.

### Bloc 3 — CIS Benchmarks Proxmox ASUS

Score initial : **38%** (72/207 checks) — CIS Debian Linux 12 Benchmark v1.1.0
Score cible : **~68%** après corrections (45 checks documentés comme exceptions)

| Catégorie | Checks | Résultat |
|---|---|---|
| SSH hardening | 9 checks | Appliqué |
| Permissions cron + fichiers | 11 checks | Appliqué |
| Services inutiles | telnet, chrony, rpcbind | Appliqué (rpcbind = exception) |
| PAM / politique mots de passe | 14 checks | Appliqué |
| Sudo / accès privilèges | 6 checks | Appliqué |
| Auditd | 22 checks | Appliqué |
| Bannières MOTD | 2 checks | Skippé volontairement |

Exceptions documentées (45 checks) : partitionnement séparé /tmp /home /var (nécessite réinstall), AppArmor (risqué sur hyperviseur Proxmox), firewall local ufw/nftables (pfSense couvre ce besoin), rpcbind (dépendance Proxmox VE — suppression impossible sans casser l'hyperviseur), AIDE/FIM (Wazuh FIM remplace AIDE), rsyslog/journal-remote (Wazuh centralise les logs), bootloader password (homelab, redémarrages automatiques).

### Bloc 4 — Revue firewall pfSense

Findings et actions :

| Finding | Action |
|---|---|
| Règles orphelines 192.168.0.x | Supprimées |
| Node Exporter port 9100 accessible sans restriction depuis VLAN_MGMT | Règle Block créée |
| Règle temporaire [TEMP] Greenbone scanner | Supprimée après audit |

---

## Configuration

### Bloc 3 — SSH hardening (Proxmox Debian 12)

Backup à faire avant modification :

```bash
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak.$(date +%Y%m%d)
```

Paramètres ajoutés dans `/etc/ssh/sshd_config` (voir `configs/sshd_config.hardening`) :

```bash
# Vérification que les paramètres sont bien pris en compte
sshd -T | grep -E 'permitrootlogin|maxauthtries|maxstartups|logingracetime|clientaliveinterval|disableforwarding|banner|allowusers'
```

### Bloc 3 — PAM (politique mots de passe)

Installation des modules nécessaires :

```bash
apt install libpam-pwquality -y
```

Fichiers modifiés (voir `configs/`) :

* `/etc/security/pwquality.conf` — complexité mot de passe (minlen=14, minclass=4)
* `/etc/security/faillock.conf` — verrouillage après 5 échecs (unlock_time=900)
* `/etc/login.defs` — durée de vie (PASS_MAX_DAYS=365, PASS_MIN_DAYS=1)
* `/etc/pam.d/common-password` — activation pam_pwquality et pam_pwhistory

### Bloc 3 — Sudo

```bash
apt install sudo -y

# Restriction de su au groupe sudo
# Dans /etc/pam.d/su, décommenter et adapter :
# auth required pam_wheel.so group=sudo
sed -i 's/^# auth       required   pam_wheel.so$/auth       required   pam_wheel.so group=sudo/' /etc/pam.d/su
```

### Bloc 3 — Auditd

Installation :

```bash
apt install auditd audispd-plugins -y
systemctl enable auditd
```

Les règles CIS sont dans `configs/99-cis.rules`. Les déployer :

```bash
cp configs/99-cis.rules /etc/audit/rules.d/99-cis.rules
augenrules --load
```

> **Important :** les commentaires inline (après une règle sur la même ligne) ne sont pas supportés par auditd. Les commentaires doivent être sur des lignes séparées précédées de `#`. Un commentaire inline fait silencieusement rejeter toute la règle.

Vérification après chargement :

```bash
auditctl -l        # liste les règles actives en mémoire noyau
auditctl -s        # vérifie que enabled=2 (mode immutable actif)
```

---

## Scripts

### `scripts/audit_vlan_scan.sh`

Script nmap multi-phases pour l'audit d'un VLAN. Auto-détecte le subnet de l'interface active, enchaîne 3 phases de scan et stocke les résultats horodatés dans `/tmp/`.

Usage :

```bash
chmod +x scripts/audit_vlan_scan.sh
./audit_vlan_scan.sh
# Les résultats sont dans /tmp/audit_VLANxx_YYYYMMDD_HHMM/
```

---

## Troubleshooting

### augenrules --load affiche "No rules"

**Cause :** commentaires inline dans le fichier `.rules` (après la règle sur la même ligne).

**Diagnostic :**

```bash
cat /etc/audit/rules.d/99-cis.rules | grep "#"
# Si des lignes contiennent à la fois une règle (-w ou -a) et un # après, c'est le problème
```

**Solution :** déplacer tous les commentaires sur leurs propres lignes. Puis relancer `augenrules --load`.

### rpcbind signalé comme service inutile par Wazuh SCA

**Cause :** rpcbind est une dépendance de `proxmox-ve`, `qemu-server` et `pve-manager`. Sa suppression désinstallerait l'hyperviseur.

**Solution :** documenter comme exception dans le rapport CIS. Maintenir rpcbind, restreindre son accès réseau via pfSense (pas exposé hors VLAN_MGMT).

### Greenbone : scan bloqué sur le NAS Synology

**Cause :** le mécanisme de protection SSH du DSM bloque automatiquement toute IP après un nombre d'échecs configurable. Le scanner Greenbone déclenche ce mécanisme.

**Solution :**

```
DSM > Panneau de configuration > Sécurité > Protection
→ Débloquer l'IP du scanner
→ Passer la durée de blocage de "infinie" à "1 jour"
→ Corriger les permissions SSH si StrictModes bloque l'authentification par clé :
  chmod 700 ~/.ssh
  chmod 600 ~/.ssh/authorized_keys
```

### sshd -T montre une valeur différente de celle dans sshd_config

**Cause :** sshd_config applique le premier occurrence d'un paramètre. Si le fichier contient déjà `PermitRootLogin yes` avant votre ajout, l'ancien paramètre prend la priorité.

**Solution :**

```bash
# Modifier la ligne existante plutôt qu'en ajouter une nouvelle
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
sshd -T | grep permitrootlogin   # vérification
```

---

## Notes

* Le hardening Proxmox ASUS (192.168.20.94) est la référence. Appliquer la même `sshd_config` et les règles auditd sur MINIFORUM (.93) et TOPTON (.95) quand ils sont allumés.
* La communauté SNMP "public" sur MikroTik, NAS et pfSense reste en l'état : à traiter lors d'une refonte du monitoring SNMP Exporter.
* `unattended-upgrades` installé sur les 3 nœuds Proxmox + VM Wazuh pour éviter la récurrence des packages outdated.

Ressources :

* [CIS Debian Linux 12 Benchmark](https://www.cisecurity.org/benchmark/debian_linux)
* [Greenbone Community Edition](https://greenbone.github.io/docs/latest/)
* [Wazuh SCA Documentation](https://documentation.wazuh.com/current/user-manual/capabilities/sec-config-assessment/)
* [Article blog — Audit sécurité homelab](https://appercel-clement.netlify.app)

---

## Licence

MIT

Projet réalisé dans le cadre de ma reconversion cybersécurité — Portfolio complet : [appercel-clement.netlify.app](https://appercel-clement.netlify.app)
