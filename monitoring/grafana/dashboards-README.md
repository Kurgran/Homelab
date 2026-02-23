# Dashboards Grafana

Ce dossier contient les exports JSON des dashboards Grafana.  
Ces fichiers permettent de recréer les dashboards sur une nouvelle instance Grafana sans repartir de zéro.

## Comment exporter un dashboard

1. Ouvrir le dashboard dans Grafana
2. Cliquer sur l'icône **Share** (en haut à droite)
3. Aller dans l'onglet **Export**
4. Activer **Export for sharing externally**
5. Cliquer sur **Save to file**
6. Placer le fichier JSON dans ce dossier

## Comment importer un dashboard

1. Dans Grafana, aller dans **Dashboards > Import**
2. Cliquer sur **Upload JSON file**
3. Sélectionner le fichier `.json` correspondant
4. Adapter les variables (datasource Prometheus ou Loki) si nécessaire

## Dashboards communautaires utilisés

Ces dashboards ont été importés directement depuis grafana.com et adaptés :

| Dashboard | ID Grafana | Usage |
|-----------|------------|-------|
| Node Exporter Full | [1860](https://grafana.com/grafana/dashboards/1860) | Métriques système Mac, NAS, pfSense |
| SNMP Interface Statistics | [11207](https://grafana.com/grafana/dashboards/11207) | Trafic réseau interfaces SNMP |

> **Note** : Les exports JSON des dashboards personnalisés sont à ajouter manuellement dans ce dossier après export depuis Grafana.