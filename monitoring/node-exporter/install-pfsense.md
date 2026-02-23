# Installation Node Exporter — pfSense VP6630

## Méthode : Gestionnaire de paquets pfSense

### Étapes

1. Ouvrir l'interface web pfSense
2. Aller dans **System > Package Manager > Available Packages**
3. Rechercher **node_exporter**
4. Cliquer sur **Install**
5. Confirmer l'installation

### Vérification

```bash
# Tester l'accès aux métriques depuis le Mac
curl http://<IP_PFSENSE>:9100/metrics | head -20

# Vérifier dans Prometheus
curl -s http://localhost:9090/api/v1/targets \
  | jq '.data.activeTargets[] | select(.labels.job=="pfsense-node") | .health'
# Attendu : "up"
```

### Règle firewall requise

pfSense bloque par défaut les connexions entrantes vers lui-même. Il faut créer une règle pour autoriser Prometheus à scraper Node Exporter :

1. Aller dans **Firewall > Rules > LAN**
2. Ajouter une règle :
   - **Action** : Pass
   - **Interface** : LAN
   - **Source** : `<IP_MAC>` (hôte Docker)
   - **Destination** : `This Firewall (self)`
   - **Destination Port** : `9100`
   - **Description** : `Allow Prometheus Node Exporter scraping`
3. Sauvegarder et appliquer les règles

### Configuration Syslog (pour Loki)

Pour envoyer les logs pfSense vers Promtail :

1. Aller dans **Status > System Logs > Settings**
2. Cocher **Enable Remote Logging**
3. Renseigner :
   - **Remote log servers** : `<IP_MAC>:1514`
   - **Remote Syslog Contents** : sélectionner les catégories souhaitées (Everything, Firewall, etc.)
4. Cliquer sur **Save**

### Notes

- Port Node Exporter exposé : `9100`
- SNMP activé via **Services > SNMP** avec community `public`
- Les métriques pfSense spécifiques (interfaces WAN/LAN, états de connexion, ZFS) sont remontées par Node Exporter