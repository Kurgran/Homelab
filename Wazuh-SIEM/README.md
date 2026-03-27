# Wazuh SIEM — Homelab

Wazuh 4.14.3 déployé sur une VM Debian (Proxmox, VLAN LAB). Trois sources de logs : pfSense, un hôte Proxmox via agent, et un NAS Synology.

L'installation en elle-même est bien documentée. Ce qui a pris du temps, c'est le décodage des logs pfSense : pfSense envoie du syslog RFC 5424, que Wazuh ne parse pas nativement. Cette page documente les problèmes rencontrés et les solutions.

**Dernières mises à jour (mars 2026) :** mapping MITRE ATT&CK sur 12/19 règles (5 tactiques), rule 100039 pour silencer le bruit opérationnel Suricata, fix Vulnerability Detection (indexer-connector IP + credentials).

## Ce qui tourne

| Source | Méthode | Ce qui est décodé |
|--------|---------|-------------------|
| pfSense | Syslog UDP 514 | Filterlog (block/pass), baux DHCP, alertes IDS Suricata |
| Proxmox ASUS NUC | Agent Wazuh | Logs système, auth, événements services via journald |
| Synology DS723+ | Syslog UDP 514 | Événements auth DSM, événements système |

## Le problème RFC 5424

pfSense envoie ses logs au format RFC 5424 :

```
1 2026-03-23T10:56:43.099591+01:00 pfSense.home.arpa dhcpd 44738 - - DHCPACK on 192.168.40.103 to 9c:9e:6e:65:72:a4 via igc1.40
```

Le pré-décodeur natif de Wazuh attend du RFC 3164 (sans le `1` en tête, sans timestamp ISO). Résultat : tous les logs pfSense autres que filterlog arrivent dans `archives.log` et n'y restent, sans déclencher aucune alerte.

La solution est un décodeur parent custom qui matche l'enveloppe RFC 5424, avec des enfants spécifiques par type de log.

## Le bug PCRE2 dans Wazuh 4.14.3

Plusieurs enfants PCRE2 sous un même parent se bloquent mutuellement. Quand le premier enfant échoue à matcher, Wazuh saute tous les suivants pour ce log. Le bug touche tout décodeur avec plus d'un enfant PCRE2.

Contournement : un parent par type de log, chacun avec un seul enfant. Plus verbeux, mais ça fonctionne. Le même problème est apparu sur les décodeurs Synology (logs auth vs logs système).

## Règles custom

| ID | Description | Level |
|----|-------------|-------|
| 100010 | pfSense filterlog base | 3 |
| 100011 | pfSense trafic bloqué | 3 |
| 100012 | pfSense trafic autorisé | 3 |
| 100013 | pfSense TCP bloqué | 3 |
| 100014 | pfSense UDP bloqué | 3 |
| 100030 | pfSense DHCP ACK (bail accordé) | 3 |
| 100031 | pfSense DHCP REQUEST | 3 |
| 100032 | pfSense DHCP bail dupliqué (conflit IP) | 7 |
| 100039 | Suricata message opérationnel — silencé (level 0) | 0 |
| 100040 | Suricata IDS alerte (base) — T1071 C2 | 6 |
| 100041 | Suricata IDS critique (Priorité 1) — T1190 | 12 |
| 100042 | Suricata IDS haute (Priorité 2) — T1071 | 8 |
| 100043 | Suricata hôte compromis connu (ET COMPROMISED) — T1071, T1059 | 10 |
| 100020 | Synology événement système | 3 |
| 100025 | Synology événement auth (base) | 3 |
| 100021 | Synology connexion réussie — T1078 | 3 |
| 100022 | Synology échec d'authentification — T1110 | 5 |
| 100023 | Synology brute force (5+ échecs en 2 min, même IP) — T1110.001 | 10 |
| 100024 | Synology énumération utilisateurs (8+ échecs, comptes différents) — T1087 | 12 |

## Fichiers

```
config/
├── local_decoder.xml    # Décodeurs custom pfSense (RFC 5424) et Synology DSM
└── local_rules.xml      # Règles custom — à copier dans /var/ossec/etc/rules/
```

Les deux fichiers vont dans `/var/ossec/etc/` sur la VM Wazuh manager. Après toute modification : `systemctl restart wazuh-manager`.

Pour tester un décodeur avant de redémarrer :
```bash
echo 'la ligne de log ici' | /var/ossec/bin/wazuh-logtest
```

## Pièges à connaître

`<field name="status">` dans les règles ne fonctionne qu'avec des champs dynamiques custom, pas avec les champs statiques built-in de Wazuh (`status`, `srcip`, `protocol`...). Pour matcher sur la priorité d'une alerte Suricata, utiliser `<match>\[Priority: 2\]</match>` sur le texte brut du log.

Les décodeurs natifs de Wazuh chargent avant `local_decoder.xml`. Si un décodeur built-in (comme `web-accesslog`) matche en premier, le décodeur custom ne sera jamais testé. C'est le cas des logs nginx de pfSense : `web-accesslog` les intercepte et extrait les mauvais champs. Ces logs restent en level 0 pour l'instant.

`logall: yes` dans `ossec.conf` est indispensable pour voir tous les logs reçus dans `archives.log`, pas seulement ceux qui ont déclenché une alerte. Sans ça, déboguer un décodeur qui ne matche pas est beaucoup plus difficile.

## Vulnerability Detection

Activé sur l'agent Proxmox. La fonctionnalité utilise deux pipelines distincts :

- **Filebeat** → index `wazuh-alerts-*` : alertes temps réel
- **indexer-connector** → index `wazuh-states-vulnerabilities` : état des CVE par agent

Le second pipeline échouait silencieusement. Symptôme : onglet "Vulnerabilities" vide dans le dashboard alors que l'agent était bien configuré. Cause : l'IP dans `/etc/wazuh-indexer/wazuh-indexer.yml` était `0.0.0.0` au lieu de l'IP réelle de l'indexer (`192.168.30.100`), et les credentials OpenSearch n'étaient pas dans le keystore.

Fix :
```bash
# Corriger l'IP dans la config indexer-connector
# Puis stocker les credentials
/var/ossec/bin/wazuh-keystore -f indexer -k username -v admin
/var/ossec/bin/wazuh-keystore -f indexer -k password -v <mot_de_passe>
systemctl restart wazuh-manager
```

Résultat : 169 CVE détectées sur l'agent Proxmox, dont 26 corrigées après `apt upgrade`.

## Infrastructure

- VM Wazuh : Debian 12, 4 vCPU, 8 Go RAM, VLAN LAB (192.168.30.x)
- Hôte Proxmox : ASUS NUC 14 Pro+ (96 Go DDR5), agent Wazuh installé directement
- NAS : Synology DS723+, transfert syslog configuré dans DSM
- Firewall : pfSense CE 2.8.x, transfert syslog vers Wazuh UDP 514, format RFC 5424
