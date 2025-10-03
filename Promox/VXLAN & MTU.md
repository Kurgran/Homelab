# Problème MTU et VXLAN - Diagnostic et Résolution

## 📋 Contexte du Projet

Petite mésaventure de découverte sur le VXLAN, suite à la création de différentes VLAN dans la partie SDN de Proxmox, où j'ai découvert malgré moi que cela réduit le MTU de 50 au niveau des VLAN créés. 
Je n'arrivais plus à accéder graphiquement à l'interface de PFSense, et le téléchargement depuis d'autres sites était assez laborieux. 
Ce n'est qu'après une analyse assez approfondie que j'ai découvert le décalage au niveau du MTU, et tout ce qu'il en découle. 

**Projet** : Infrastructure Multi-sites - Raccordement d'une entité distante  
**Environnement** : Proxmox avec SDN VXLAN  
**Sites** : Site Principal et Site Distant  
**Infrastructure** : Windows Server 2019, PFSense, machines virtuelles Linux

## 🔴 Problème Rencontré

### Symptômes

- ✅ **Ping fonctionne** : Les VMs peuvent pinguer PFSense (10.0.1.1) et Internet (8.8.8.8)
- ✅ **Navigation Internet fonctionne** : Les VMs peuvent accéder aux sites web externes
- ✅ **Connexion TCP établie** : Le port 80 de PFSense est accessible (`nc -zv 10.0.1.1 80` réussit)
- ❌ **Interface web PFSense inaccessible** : Impossible d'accéder à http://10.0.1.1 via navigateur
- ❌ **Timeout sur requêtes HTTP GET** : `curl -v http://10.0.1.1` timeout après connexion

### Comportement Observé

```bash
# HEAD request (petits paquets) : ✅ FONCTIONNE
curl -I http://10.0.1.1
HTTP/1.1 200 OK
Server: nginx
Content-Type: text/html

# GET request (gros paquets) : ❌ TIMEOUT
curl -v http://10.0.1.1
* Connected to 10.0.1.1 port 80
> GET / HTTP/1.1
* Operation timed out after 15002 milliseconds with 0 bytes received
```

## 🎯 Cause du Problème : Mismatch de MTU

### Diagnostic

Le problème vient d'une **incompatibilité de MTU** (Maximum Transmission Unit) entre les VMs et le réseau VXLAN :

| Composant | MTU Configuré | Problème |
|-----------|---------------|----------|
| VM Linux (ens18) | 1500 bytes | ❌ Trop élevé |
| VM Windows Server | 1500 bytes | ❌ Trop élevé |
| Bridge VXLAN (SITE-PRINCIPAL, SITE-DISTANT) | 1450 bytes | ✅ Correct |
| Interface physique Proxmox | 1500 bytes | ✅ Correct |

### Explication Technique

#### Qu'est-ce que le MTU ?

**MTU (Maximum Transmission Unit)** : Taille maximale d'un paquet réseau pouvant être transmis sans fragmentation.

- **Standard Ethernet** : 1500 bytes
- **VXLAN** : 1450 bytes (1500 - 50 bytes d'overhead)

#### Pourquoi VXLAN réduit le MTU ?

**VXLAN** (Virtual Extensible LAN) encapsule les paquets Ethernet dans des headers supplémentaires :

```
┌────────────────────────────────────────┐
│ Paquet Ethernet Original (1500b max)   │
└────────────────────────────────────────┘
              ↓ Encapsulation VXLAN
┌────────────────────────────────────────┐
│ Header Ethernet Externe (14b)          │
│ Header IP Externe (20b)                │
│ Header UDP (8b)                        │
│ Header VXLAN (8b)                      │
│ ┌────────────────────────────────────┐ │
│ │ Paquet Original (1500b)            │ │
│ └────────────────────────────────────┘ │
└────────────────────────────────────────┘
Total : 1500 + 50 = 1550 bytes
```

**Overhead VXLAN** : 50 bytes au total
- Header Ethernet : 14 bytes
- Header IP : 20 bytes
- Header UDP : 8 bytes
- Header VXLAN : 8 bytes

**Calcul du MTU VXLAN** :
```
MTU VXLAN = MTU Interface Physique - Overhead VXLAN
MTU VXLAN = 1500 - 50 = 1450 bytes
```

#### Pourquoi les petits paquets passent mais pas les gros ?

| Type de Paquet | Taille | Fragmentation | Résultat |
|----------------|--------|---------------|----------|
| ICMP Ping | ~64 bytes | Non nécessaire | ✅ Passe |
| HTTP HEAD | ~300 bytes | Non nécessaire | ✅ Passe |
| HTTP GET (HTML) | 5000+ bytes | **Nécessaire** | ❌ Échoue |

**Le problème** :
1. VM envoie un paquet de 1500 bytes (pense que c'est OK)
2. Le paquet arrive au bridge VXLAN (MTU 1450)
3. Le paquet est trop gros → doit être fragmenté
4. La fragmentation échoue ou les fragments sont perdus
5. **Résultat** : Timeout, aucune donnée reçue

### Configuration SDN Proxmox

Quand vous créez une zone VXLAN dans le SDN Proxmox, le système calcule **automatiquement** le MTU :

```bash
# Configuration SDN
cat /etc/pve/sdn/zones.cfg
```
```
vxlan: ZONE-PRINCIPALE
        peers 192.168.0.94
        ipam pve
        # MTU calculé automatiquement : 1450
```

Proxmox crée alors des bridges avec MTU 1450 :

```bash
ip addr show SITE-PRINCIPAL
126: SITE-PRINCIPAL: ... mtu 1450 ...
```

## ✅ Solutions Appliquées

### Solution 1 : Réduire le MTU des VMs à 1400 (RECOMMANDÉ)

On utilise **1400** au lieu de 1450 pour laisser une marge de sécurité pour les headers TCP/IP.

#### Sur Linux

**Test temporaire** :
```bash
# Réduire le MTU temporairement
sudo ip link set ens18 mtu 1400

# Vérifier
ip addr show ens18 | grep mtu

# Tester immédiatement
curl -v http://10.0.1.1
```

**Configuration permanente (Debian/Ubuntu classique)** :
```bash
sudo nano /etc/network/interfaces.d/ens18
```
```
auto ens18
iface ens18 inet static
    address 10.0.1.5
    netmask 255.255.255.0
    gateway 10.0.1.1
    mtu 1400
```

**Configuration permanente (Ubuntu moderne avec Netplan)** :
```bash
sudo nano /etc/netplan/01-netcfg.yaml
```
```yaml
network:
  version: 2
  ethernets:
    ens18:
      addresses: [10.0.1.5/24]
      gateway4: 10.0.1.1
      nameservers:
        addresses: [8.8.8.8, 8.8.4.4]
      mtu: 1400
```
```bash
# Appliquer
sudo netplan apply
```

#### Sur Windows Server

**Vérifier l'interface et le MTU actuel** :
```powershell
# Lister les adaptateurs
Get-NetAdapter

# Vérifier le MTU
Get-NetIPInterface | Where-Object {$_.AddressFamily -eq "IPv4"} | Select-Object InterfaceAlias, NlMtu

# OU avec netsh
netsh interface ipv4 show interfaces
```

**Modifier le MTU** :
```powershell
# Méthode PowerShell (Windows Server 2012+)
Set-NetIPInterface -InterfaceAlias "Ethernet0" -NlMtu 1400

# Vérifier
Get-NetIPInterface -InterfaceAlias "Ethernet0" | Select-Object InterfaceAlias, NlMtu

# Méthode netsh (toutes versions)
netsh interface ipv4 set subinterface "Ethernet0" mtu=1400 store=persistent

# Vérifier
netsh interface ipv4 show subinterfaces
```

**Tester la connexion** :
```powershell
# Test de port
Test-NetConnection -ComputerName 10.0.1.1 -Port 80

# Test dans le navigateur
# http://10.0.1.1
```

⚠️ **IMPORTANT** : Remplacez `"Ethernet0"` par le vrai nom de votre interface !

#### Sur PFSense

**Depuis la console PFSense (Option 8 - Shell)** :

```bash
# Identifier l'interface LAN
ifconfig | grep -B 3 "inet 10.0.1.1"
# Note le nom, par exemple : vtnet0, em0, igb0

# Modifier le MTU temporairement
ifconfig vtnet0 mtu 1400

# Vérifier
ifconfig vtnet0 | grep mtu
```

**Configuration permanente** :

Une fois l'interface web accessible :
1. **System → Advanced → Networking**
2. Section **"Network Interfaces"**
3. Modifier le MTU pour l'interface LAN

OU via shell :
```bash
# Éditer la configuration
nano /conf/config.xml

# Chercher la section <interfaces><lan>
# Ajouter : <mtu>1400</mtu>

# Reboot
reboot
```

### Solution 2 : Jumbo Frames (AVANCÉ)

Si votre matériel réseau supporte les **Jumbo Frames** (MTU > 1500), vous pouvez augmenter le MTU du réseau physique pour garder MTU 1500 dans les VMs.

#### Vérifier le support Jumbo Frames

```bash
# Depuis Proxmox
ethtool enp87s0 | grep -i "Maximum"

# Tester directement
ip link set enp87s0 mtu 9000
ip link show enp87s0 | grep mtu
```

#### Configuration Proxmox

```bash
# Éditer la configuration réseau
nano /etc/network/interfaces
```
```
auto enp87s0
iface enp87s0 inet manual
    mtu 9000

auto vmbr0
iface vmbr0 inet static
    address 192.168.0.94/24
    bridge-ports enp87s0
    bridge-stp off
    bridge-fd 0
    mtu 9000
```

#### Modifier le SDN

```bash
nano /etc/pve/sdn/zones.cfg
```
```
vxlan: ZONE-PRINCIPALE
        peers 192.168.0.94
        ipam pve
        mtu 1500
```

```bash
# Recharger le SDN
pvesh set /cluster/sdn
systemctl restart pve-cluster
```

⚠️ **Attention** : Cette solution nécessite que **TOUT** le matériel réseau (switches, routeurs, cartes réseau) supporte les Jumbo Frames.

## 🔍 Commandes de Diagnostic

### Vérifier le MTU

```bash
# === LINUX ===
ip addr show
ip link show <interface>

# === WINDOWS ===
Get-NetIPInterface | Select-Object InterfaceAlias, NlMtu
netsh interface ipv4 show interfaces

# === PFSENSE ===
ifconfig
```

### Tester la connectivité par taille de paquet

```bash
# Ping avec interdiction de fragmentation
# Format : ping -M do -s <taille_payload> <destination>

# Petits paquets (devraient passer)
ping -M do -s 100 -c 3 10.0.1.1    # 128 bytes total
ping -M do -s 500 -c 3 10.0.1.1    # 528 bytes total
ping -M do -s 1000 -c 3 10.0.1.1   # 1028 bytes total

# Paquets moyens (devraient passer avec MTU 1400)
ping -M do -s 1372 -c 3 10.0.1.1   # 1400 bytes total

# Gros paquets (échoueront si MTU trop bas)
ping -M do -s 1422 -c 3 10.0.1.1   # 1450 bytes total
ping -M do -s 1472 -c 3 10.0.1.1   # 1500 bytes total
```

**Décomposition** :
- `-M do` : "Don't Fragment" - interdit la fragmentation
- `-s 1372` : taille du payload ICMP (1372 bytes)
- Total = payload + 28 bytes (20 IP + 8 ICMP) = 1400 bytes
- `-c 3` : envoyer 3 paquets
- Si le paquet dépasse le MTU, il sera DROP (pas de réponse)

### Tester la connectivité HTTP

```bash
# Test de port TCP
nc -zv 10.0.1.1 80
nc -zv 10.0.1.1 443

# Test HTTP complet
curl -v http://10.0.1.1

# Test HTTPS en ignorant le certificat
curl -vk https://10.0.1.1

# Test avec timeout
curl -v --connect-timeout 10 --max-time 15 http://10.0.1.1

# Récupérer seulement les headers (HEAD request)
curl -I http://10.0.1.1
```

### Vérifier les services sur PFSense

```bash
# Depuis la console PFSense (Option 8)

# Vérifier que nginx écoute
ps aux | grep nginx
sockstat -4 -l | grep nginx

# Vérifier les ports en écoute
sockstat -4 -l | grep -E '(80|443)'

# Tester localement
curl -v http://127.0.0.1
curl -v http://10.0.1.1

# Logs nginx
tail -20 /var/log/nginx/error.log
tail -20 /var/log/nginx/access.log
```

## 📊 Tableau Récapitulatif des MTU

| Composant | MTU Standard | MTU VXLAN | MTU Recommandé | Action |
|-----------|--------------|-----------|----------------|--------|
| **Interface physique Proxmox** | 1500 | - | 1500 (ou 9000*) | Aucune |
| **Bridge vmbr0** | 1500 | - | 1500 (ou 9000*) | Aucune |
| **Bridge VXLAN (Sites)** | - | 1450 | 1450 | Auto Proxmox |
| **VM Linux** | 1500 | - | **1400** | ✅ Modifier |
| **VM Windows Server** | 1500 | - | **1400** | ✅ Modifier |
| **VM PFSense** | 1500 | - | **1400** | ✅ Modifier |

*Seulement si Jumbo Frames activées sur tout le réseau

## 🎓 Points Clés à Retenir

### 1. La Fragmentation est l'Ennemie

- Les petits paquets (ping, HEAD) passent toujours
- Les gros paquets (GET, POST) nécessitent souvent fragmentation
- La fragmentation IP cause : perte de performance, perte de paquets, timeouts

### 2. VXLAN = -50 bytes de MTU

- VXLAN ajoute toujours 50 bytes d'overhead
- MTU physique 1500 → MTU VXLAN 1450
- **Règle** : MTU des VMs doit être ≤ MTU du réseau sous-jacent

### 3. Toujours Laisser une Marge

- MTU VXLAN = 1450
- MTU recommandé VMs = **1400** (marge de 50 bytes)
- Cette marge couvre les headers TCP/IP et évite les edge cases

### 4. Le Diagnostic par Couches

La méthode de diagnostic :
1. **Couche 3 (ICMP)** : `ping` → teste la joignabilité réseau
2. **Couche 4 (TCP)** : `nc -zv` → teste l'ouverture des ports
3. **Couche 7 (HTTP)** : `curl -v` → teste le service applicatif
4. **Par taille** : `ping -M do -s` → identifie les problèmes MTU

### 5. Jumbo Frames = Solution Pro

- MTU > 1500 (généralement 9000)
- Meilleure performance pour les gros transferts
- **Prérequis** : TOUT le matériel doit supporter (switches, NICs, etc.)
- Configuration plus complexe mais optimale en production

## 🚨 Erreurs Courantes

### Erreur 1 : Oublier de rendre permanent

```bash
# ❌ Changement temporaire (perdu au reboot)
ip link set ens18 mtu 1400

# ✅ Configuration permanente
# Éditer /etc/network/interfaces ou /etc/netplan/
```

### Erreur 2 : Modifier seulement une VM

- ✅ **TOUTES** les VMs du réseau VXLAN doivent avoir MTU ajusté
- Sinon : certaines VMs fonctionnent, d'autres pas

### Erreur 3 : Forcer MTU 1500 dans VXLAN sans Jumbo Frames

```bash
# ❌ DANGEREUX : Force MTU 1500 alors que le réseau physique est à 1500
# Les paquets VXLAN feront 1550 bytes → fragmentation obligatoire
ip link set SITE-PRINCIPAL mtu 1500  # Si pas de Jumbo Frames

# ✅ CORRECT : Garder MTU 1450 ou activer Jumbo Frames d'abord
```

### Erreur 4 : Tester seulement avec ping

- ✅ Ping fonctionne ≠ Tout fonctionne
- Ping utilise de petits paquets (64 bytes)
- Toujours tester avec `curl` ou navigateur pour les gros paquets

## 📚 Ressources et Documentation

### Références Techniques

- **RFC 7348** : Virtual eXtensible Local Area Network (VXLAN)
- **RFC 791** : Internet Protocol - Fragmentation
- **MTU Path Discovery** : RFC 1191, RFC 4821

### Commandes Utiles

```bash
# Proxmox - Vérifier config SDN
cat /etc/pve/sdn/zones.cfg
cat /etc/pve/sdn/vnets.cfg
pvesh get /cluster/sdn

# Linux - Diagnostic réseau
ip addr show
ip link show
ip route show
ethtool <interface>
mtr <destination>

# Windows - Diagnostic réseau
Get-NetAdapter
Get-NetIPInterface
Test-NetConnection -ComputerName <IP> -Port <port>
ping -f -l <size> <destination>  # -f = Don't Fragment

# PFSense - Diagnostic
ifconfig
sockstat -4 -l
pfctl -s rules
```

## ✅ Checklist de Vérification

Après avoir modifié le MTU, vérifiez :

- [ ] MTU modifié sur **toutes** les VMs du réseau
- [ ] MTU visible avec `ip addr show` ou `Get-NetIPInterface`
- [ ] Ping fonctionne : `ping -c 3 10.0.1.1`
- [ ] Gros paquets passent : `ping -M do -s 1372 -c 3 10.0.1.1`
- [ ] Port 80 accessible : `nc -zv 10.0.1.1 80`
- [ ] HTTP fonctionne : `curl -v http://10.0.1.1`
- [ ] Interface web accessible dans navigateur
- [ ] Configuration permanente (survit au reboot)
- [ ] Documentation mise à jour

## 💡 Conclusion

Le problème de **MTU mismatch** est **très courant** en environnement de production, particulièrement avec :
- VPN (OpenVPN, WireGuard, IPsec)
- VXLAN / Overlay networks
- Tunnels (GRE, IPIP)
- SD-WAN

**La solution** : Toujours ajuster le MTU des VMs/endpoints pour correspondre au MTU du réseau sous-jacent, en laissant une marge de sécurité.

Cette compétence est **essentielle** pour tout administrateur système/réseau et sera utile tout au long de votre carrière en cybersécurité et infrastructure !

---

*Note créée le : 30/09/2025*  
*Projet : Infrastructure Multi-sites*  
*Tags : #MTU #VXLAN #Proxmox #Troubleshooting #Réseau*
