# 📦 Guide d'Installation

Guide complet pour installer Panel Logs Galaxy sur Ubuntu 24.04 LTS.

---

## Table des Matières

1. [Prérequis](#-prérequis)
2. [Installation Automatique](#-installation-automatique)
3. [Installation Manuelle](#-installation-manuelle)
4. [Configuration Cloudflare Tunnel](#-configuration-cloudflare-tunnel)
5. [Vérification](#-vérification)

---

## 📋 Prérequis

### Système d'exploitation
- **Ubuntu 24.04 LTS** (recommandé)
- Autres distributions Linux compatibles systemd

### Accès
- Accès **root** ou **sudo**
- Connexion SSH au serveur

### Services externes
- **Compte Cloudflare** (gratuit) - [Créer un compte](https://dash.cloudflare.com/sign-up)
- **Application Discord** configurée - [Discord Developer Portal](https://discord.com/developers/applications)
- **Bot Discord** avec le token

### Ressources recommandées
- **RAM** : 2 GB minimum, 4 GB recommandé
- **CPU** : 2 cores minimum
- **Disque** : 10 GB minimum
- **Bande passante** : Illimitée recommandée

---

## ⚡ Installation Automatique

L'installation automatique configure tout en une seule commande.

### Étape 1 : Cloner le projet

```bash
# Cloner dans /var/www/logspanel
sudo git clone <votre-repo> /var/www/logspanel
cd /var/www/logspanel
```

### Étape 2 : Lancer l'installation

```bash
# Rendre le script exécutable
sudo chmod +x deploy/install.sh

# Lancer l'installation
sudo ./deploy/install.sh
```

### Ce que fait le script

Le script d'installation automatise :

1. ✅ **Mise à jour du système**
   ```bash
   apt update && apt upgrade -y
   ```

2. ✅ **Installation des dépendances**
   - Python 3.12+
   - pip, venv
   - UFW (firewall)
   - cloudflared

3. ✅ **Environnement Python**
   - Création du venv
   - Installation des packages Python
   - Configuration Gunicorn

4. ✅ **Service systemd**
   - Installation de `logspanel.service`
   - Activation au démarrage

5. ✅ **Firewall UFW**
   - Configuration sécurisée
   - SSH autorisé uniquement
   - Ports web fermés (accès via Tunnel uniquement)

6. ✅ **Permissions**
   - Propriétaire : `www-data`
   - Permissions appropriées

### Étape 3 : Configuration

Après l'installation, configurez les fichiers :

```bash
# Copier les templates
sudo cp env.example .env
sudo cp servers_config.json.example servers_config.json

# Éditer .env
sudo nano .env

# Éditer servers_config.json
sudo nano servers_config.json
```

Consultez [CONFIGURATION.md](CONFIGURATION.md) pour les détails.

---

## 🔧 Installation Manuelle

Si vous préférez installer manuellement chaque composant :

### 1. Préparer le système

```bash
# Mettre à jour
sudo apt update && sudo apt upgrade -y

# Installer les dépendances système
sudo apt install -y \
    python3.12 \
    python3.12-venv \
    python3-pip \
    git \
    ufw \
    mysql-client \
    curl \
    wget
```

### 2. Cloner le projet

```bash
sudo mkdir -p /var/www
sudo git clone <votre-repo> /var/www/logspanel
cd /var/www/logspanel
```

### 3. Environnement Python

```bash
# Créer l'environnement virtuel
sudo python3.12 -m venv venv

# Activer l'environnement
source venv/bin/activate

# Mettre à jour pip
pip install --upgrade pip

# Installer les dépendances
pip install -r requirements.txt
```

### 4. Configuration

```bash
# Copier les templates
sudo cp env.example .env
sudo cp servers_config.json.example servers_config.json

# Éditer les fichiers
sudo nano .env
sudo nano servers_config.json
```

### 5. Service systemd

```bash
# Copier le fichier de service
sudo cp deploy/logspanel.service /etc/systemd/system/

# Recharger systemd
sudo systemctl daemon-reload

# Activer le service
sudo systemctl enable logspanel

# Démarrer le service
sudo systemctl start logspanel

# Vérifier le statut
sudo systemctl status logspanel
```

### 6. Permissions

```bash
# Changer le propriétaire
sudo chown -R www-data:www-data /var/www/logspanel

# Permissions des fichiers sensibles
sudo chmod 600 /var/www/logspanel/.env
sudo chmod 664 /var/www/logspanel/servers_config.json
```

### 7. Firewall UFW

```bash
# Activer UFW
sudo ufw --force enable

# Politique par défaut
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Autoriser SSH
sudo ufw allow ssh

# NE PAS ouvrir les ports 80, 443, 3001
# L'accès se fait via Cloudflare Tunnel

# Vérifier
sudo ufw status verbose
```

---

## 🌐 Configuration Cloudflare Tunnel

Cloudflare Tunnel permet d'exposer votre panel **sans ouvrir de ports**.

### Avantages

- 🔒 **Aucun port ouvert** - Sécurité maximale
- 🛡️ **Protection DDoS** - Automatique via Cloudflare
- 📜 **SSL gratuit** - Certificats gérés par Cloudflare
- ⚡ **CDN** - Assets servis depuis le edge
- 🚀 **Performances** - Optimisation globale

### Étape 1 : Installer cloudflared

```bash
# Télécharger la dernière version
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared

# Rendre exécutable
chmod +x cloudflared

# Déplacer vers /usr/local/bin
sudo mv cloudflared /usr/local/bin/

# Vérifier l'installation
cloudflared --version
```

### Étape 2 : Authentification Cloudflare

```bash
# Se connecter à Cloudflare
cloudflared tunnel login
```

Cela ouvre un navigateur pour vous authentifier. Une fois connecté, un fichier `cert.pem` est créé dans `~/.cloudflared/`.

### Étape 3 : Créer le tunnel

```bash
# Créer un tunnel nommé "logspanel"
cloudflared tunnel create logspanel
```

**Important** : Notez l'**ID du tunnel** affiché (format UUID).

### Étape 4 : Configurer le DNS

```bash
# Remplacez par votre domaine
cloudflared tunnel route dns logspanel votre-domaine.com
cloudflared tunnel route dns logspanel www.votre-domaine.com
```

Cela crée automatiquement les enregistrements CNAME dans Cloudflare.

### Étape 5 : Configuration du tunnel

```bash
# Créer le dossier de configuration
sudo mkdir -p /etc/cloudflared

# Copier le fichier de credentials
sudo cp ~/.cloudflared/<TUNNEL_ID>.json /etc/cloudflared/credentials.json

# Créer le fichier de configuration
sudo nano /etc/cloudflared/config.yml
```

**Contenu de `/etc/cloudflared/config.yml` :**

```yaml
tunnel: VOTRE_TUNNEL_ID
credentials-file: /etc/cloudflared/credentials.json

ingress:
  - hostname: votre-domaine.com
    service: http://localhost:3001
  - hostname: www.votre-domaine.com
    service: http://localhost:3001
  - service: http_status:404
```

**Remplacez :**
- `VOTRE_TUNNEL_ID` par l'ID du tunnel
- `votre-domaine.com` par votre domaine

### Étape 6 : Installer le service cloudflared

```bash
# Installer en tant que service systemd
sudo cloudflared service install

# Activer au démarrage
sudo systemctl enable cloudflared

# Démarrer le service
sudo systemctl start cloudflared

# Vérifier le statut
sudo systemctl status cloudflared
```

### Étape 7 : Mettre à jour .env

```bash
sudo nano /var/www/logspanel/.env
```

Modifiez la variable `GLOBAL_REDIRECT_URI` :

```env
GLOBAL_REDIRECT_URI=https://votre-domaine.com/callback
```

Redémarrez le panel :

```bash
sudo systemctl restart logspanel
```

---

## ✅ Vérification

### 1. Vérifier le service panel

```bash
# Statut
sudo systemctl status logspanel

# Logs en temps réel
sudo journalctl -u logspanel -f

# Vérifier que le port écoute
sudo ss -tlnp | grep 3001
```

Vous devriez voir :
```
LISTEN  0  511  127.0.0.1:3001  *:*  users:(("gunicorn",pid=...))
```

### 2. Vérifier le tunnel Cloudflare

```bash
# Statut
sudo systemctl status cloudflared

# Logs
sudo journalctl -u cloudflared -f

# Informations du tunnel
cloudflared tunnel info logspanel
```

### 3. Test local

```bash
# Tester que le panel répond localement
curl http://localhost:3001
```

Vous devriez recevoir du HTML.

### 4. Test public

```bash
# Tester via le domaine
curl https://votre-domaine.com
```

Ou ouvrez simplement dans votre navigateur : `https://votre-domaine.com`

### 5. Vérifier le firewall

```bash
sudo ufw status verbose
```

Vous devriez voir :
```
Status: active

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW IN    Anywhere
22/tcp (v6)                ALLOW IN    Anywhere (v6)
```

**Important** : Les ports 80, 443, 3001 ne doivent **PAS** apparaître.

---

## 🚨 Résolution de Problèmes

### Le panel ne démarre pas

```bash
# Voir les erreurs
sudo journalctl -u logspanel -n 50 --no-pager

# Tester manuellement
cd /var/www/logspanel
source venv/bin/activate
python main.py
```

### Le tunnel ne fonctionne pas

```bash
# Vérifier la connexion locale
curl http://localhost:3001

# Vérifier la configuration
cat /etc/cloudflared/config.yml

# Redémarrer le tunnel
sudo systemctl restart cloudflared
```

### Erreur 502 Bad Gateway

Le panel n'est pas accessible :

1. Vérifier que logspanel tourne : `systemctl status logspanel`
2. Vérifier le port : `ss -tlnp | grep 3001`
3. Redémarrer : `systemctl restart logspanel`

### Permission denied sur servers_config.json

```bash
sudo chown www-data:www-data /var/www/logspanel/servers_config.json
sudo chmod 664 /var/www/logspanel/servers_config.json
```

---

## 📋 Checklist d'Installation

- [ ] Ubuntu 24.04 installé et à jour
- [ ] Projet cloné dans `/var/www/logspanel`
- [ ] Dépendances système installées
- [ ] Environnement Python créé
- [ ] Packages Python installés
- [ ] `.env` configuré
- [ ] `servers_config.json` configuré
- [ ] Service logspanel installé et démarré
- [ ] cloudflared installé
- [ ] Tunnel Cloudflare créé
- [ ] DNS configuré
- [ ] Service cloudflared démarré
- [ ] Firewall UFW activé
- [ ] Test d'accès réussi via https://votre-domaine.com
- [ ] Mode debug désactivé (production)

---

## ➡️ Étape Suivante

Une fois l'installation terminée, consultez :
- **[CONFIGURATION.md](CONFIGURATION.md)** - Configuration détaillée
- **[SECURITY.md](SECURITY.md)** - Sécuriser votre installation

---

**Besoin d'aide ?** Consultez [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
