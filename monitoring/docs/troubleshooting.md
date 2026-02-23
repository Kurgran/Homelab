# Troubleshooting — Erreurs connues et solutions

---

## 1. Node Exporter dans Docker remonte de fausses métriques Mac

**Symptôme** : Les métriques CPU/RAM affichées dans Grafana ne correspondent pas aux valeurs réelles observées dans le Moniteur d'activité macOS.

**Cause** : Node Exporter conteneurisé accède au noyau Linux de la VM Docker Desktop, pas au hardware macOS réel.

**Solution** : Installer Node Exporter en natif via Homebrew.
```bash
brew install node_exporter
brew services start node_exporter
```
Vérification :
```bash
curl http://localhost:9100/metrics | grep node_cpu
```

---

## 2. Targets SNMP DOWN après mise à jour vers snmp.yml officiel

**Symptôme** : Après avoir remplacé `snmp.yml` par le fichier officiel Prometheus, les jobs `synology-nas-snmp` et `pfsense-router-snmp` passent en `DOWN`.

**Cause** : Le fichier officiel utilise des noms d'authentification différents de ceux référencés dans `prometheus.yml` (`public_v2`).

**Solution** : Revenir au fichier `snmp.yml` hybride (auth custom `public_v2` + module `if_mib` extrait de l'officiel). Ne pas utiliser le fichier officiel complet.

Rollback :
```bash
cd monitoring/stack/snmp
# Restaurer le snmp.yml hybride depuis le backup ou ce repo
docker compose restart snmp-exporter
```

---

## 3. Rechargement Prometheus sans redémarrage

**Symptôme** : Modification de `prometheus.yml` non prise en compte sans `docker compose restart`.

**Solution** : Utiliser l'API de reload (activée par `--web.enable-lifecycle` dans le docker-compose) :
```bash
curl -X POST http://localhost:9090/-/reload
```
Attendre 15 secondes puis vérifier http://localhost:9090/targets.

---

## 4. Promtail ne reçoit pas les logs Syslog de pfSense ou du NAS

**Symptôme** : Aucun log n'apparaît dans Grafana / Loki pour pfSense ou le NAS.

**Checklist** :
1. Vérifier que Promtail écoute bien sur le port 1514/UDP :
```bash
docker compose ps promtail
# STATUS doit indiquer "Up" et le port 1514/udp exposé
```
2. Vérifier la configuration Syslog sur pfSense : **Status > System Logs > Settings > Enable Remote Logging** vers `<IP_MAC>:1514`
3. Vérifier la configuration sur le NAS : **Centre de journaux > Paramètres** vers `<IP_MAC>:1514` en UDP
4. Tester la réception UDP depuis le Mac :
```bash
# Ouvrir un listener temporaire
nc -ul 1514
# Depuis pfSense ou NAS, envoyer un log test
```
5. Vérifier les logs Promtail pour détecter des erreurs de parsing :
```bash
docker compose logs --tail=50 promtail
```

---

## 5. Dossiers vides non poussés sur GitHub

**Symptôme** : Après `git push`, certains dossiers vides (ex: `grafana/dashboards/`, `prometheus/rules/`) n'apparaissent pas sur GitHub.

**Cause** : Git ne versionne pas les dossiers vides.

**Solution** : Placer un fichier `.gitkeep` vide dans chaque dossier à préserver :
```bash
touch monitoring/grafana/dashboards/.gitkeep
touch monitoring/stack/prometheus/rules/.gitkeep
git add .
git commit -m "chore: add .gitkeep for empty directories"
git push
```

---

## 6. Commandes de diagnostic rapide

```bash
# État de tous les conteneurs
docker compose ps

# Logs d'un conteneur en temps réel
docker compose logs -f <service>   # prometheus | grafana | snmp-exporter | loki | promtail

# Targets Prometheus via API
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, state: .health}'

# Loki prêt ?
curl http://localhost:3100/ready

# Hosts qui envoient des logs à Loki
curl -G -s "http://localhost:3100/loki/api/v1/label/host/values" | jq

# Test SNMP sur un équipement
snmpwalk -v2c -c public <IP_EQUIPEMENT> system

# Test endpoint SNMP Exporter
curl "http://localhost:9116/snmp?target=<IP_EQUIPEMENT>&module=if_mib&auth=public_v2" | grep "ifInOctets" | head -5
```