# Installation Node Exporter — NAS Synology DS723+

## Méthode : Package Center Synology

Le NAS Synology propose Node Exporter via son gestionnaire de paquets natif.

### Étapes

1. Ouvrir l'interface DSM du NAS
2. Aller dans **Gestionnaire de paquets (Package Center)**
3. Rechercher **Node Exporter**
4. Cliquer sur **Installer**
5. Une fois installé, vérifier que le service est **en cours d'exécution**

### Vérification depuis le Mac

```bash
# Tester l'accès aux métriques depuis le Mac
curl http://<IP_NAS>:9100/metrics | head -20

# Vérifier que le job remonte dans Prometheus
curl -s http://localhost:9090/api/v1/targets \
  | jq '.data.activeTargets[] | select(.labels.job=="synology-node") | .health'
# Attendu : "up"
```

### Configuration Syslog (pour Loki)

Pour envoyer les logs du NAS vers Promtail :

1. Ouvrir DSM → **Centre de journaux**
2. Aller dans **Paramètres**
3. Activer **Envoyer les journaux à un serveur syslog**
4. Renseigner :
   - **Serveur** : `<IP_MAC>`
   - **Port** : `1514`
   - **Protocole** : `UDP`
5. Cliquer sur **Appliquer**

### Notes

- Port exposé : `9100`
- Protocol SNMP activé séparément (via les paramètres réseau du DSM)
- Community string SNMP : `public` (SNMPv2c)