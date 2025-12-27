# 🆘 Guide de Dépannage

Solutions aux problèmes courants de Panel Logs Galaxy.

---

## Table des Matières

1. [Le Panel Ne Démarre Pas](#-le-panel-ne-démarre-pas)
2. [Erreurs de Connexion](#-erreurs-de-connexion)
3. [Cloudflare Tunnel](#-cloudflare-tunnel)
4. [Permissions et Fichiers](#-permissions-et-fichiers)
5. [Base de Données](#-base-de-données)
6. [Discord OAuth](#-discord-oauth)
7. [Firewall](#-firewall)
8. [Client Panel](#-client-panel)

---

## 🚫 Le Panel Ne Démarre Pas

### Symptôme

```bash
sudo systemctl status logspanel
● logspanel.service - Panel Logs Galaxy
   Loaded: loaded
   Active: failed (Result: exit-code)
```

### Diagnostic

```bash
# Voir les logs d'erreur
sudo journalctl -u logspanel -n 50 --no-pager

# Tester manuellement
cd /var/www/logspanel
source venv/bin/activate
python main.py
```

### Solutions

#### 1. Module Python manquant

**Erreur :**
```
ModuleNotFoundError: No module named 'flask'
```

**Solution :**
```bash
cd /var/www/logspanel
source venv/bin/activate
pip install -r requirements.txt
deactivate
sudo systemctl restart logspanel
```

#### 2. Fichier .env invalide

**Erreur :**
```
FileNotFoundError: [Errno 2] No such file or directory: '.env'
```

**Solution :**
```bash
cd /var/www/logspanel
sudo cp env.example .env
sudo nano .env  # Configurer
sudo systemctl restart logspanel
```

#### 3. Port 3001 déjà utilisé

**Erreur :**
```
OSError: [Errno 98] Address already in use
```

**Solution :**
```bash
# Trouver le processus
sudo lsof -i:3001

# Tuer le processus
sudo kill -9 <PID>

# Redémarrer
sudo systemctl restart logspanel
```

#### 4. Permissions /var/www/logspanel

**Solution :**
```bash
sudo chown -R www-data:www-data /var/www/logspanel
sudo chmod 755 /var/www/logspanel
sudo systemctl restart logspanel
```

---

## 🔐 Erreurs de Connexion

### "Invalid state parameter"

**Cause :** Token CSRF expiré ou session invalide

**Solution :**
1. Vider le cache du navigateur
2. Réessayer la connexion
3. Vérifier `JWT_SECRET_KEY` dans `.env`

### "Discord API error"

**Cause :** Credentials Discord invalides

**Solution :**
```bash
sudo nano /var/www/logspanel/.env
```

Vérifier :
- `DISCORD_CLIENT_ID` correct
- `DISCORD_CLIENT_SECRET` correct
- `DISCORD_BOT_TOKEN` valide
- `GLOBAL_REDIRECT_URI` correspond à Discord Developer Portal

### "Unauthorized"

**Cause :** L'utilisateur n'a pas les permissions

**Solutions :**

1. **Super Admin non configuré :**
```bash
sudo nano /var/www/logspanel/.env
# Ajouter votre ID Discord
SUPER_ADMIN_DISCORD_IDS=123456789012345678
sudo systemctl restart logspanel
```

2. **Rôles Discord mal configurés :**
- Vérifier `servers_config.json`
- Vérifier que le bot est sur le serveur Discord
- Vérifier **Server Members Intent** activé

---

## 🌐 Cloudflare Tunnel

### Erreur 502 Bad Gateway

**Cause :** Le panel n'est pas accessible

**Solutions :**

1. **Panel pas démarré :**
```bash
sudo systemctl start logspanel
sudo systemctl status logspanel
```

2. **Port incorrect :**
```bash
# Vérifier que le panel écoute sur 3001
sudo ss -tlnp | grep 3001

# Vérifier config.yml
cat /etc/cloudflared/config.yml
# Doit contenir : service: http://localhost:3001
```

3. **Tunnel pas démarré :**
```bash
sudo systemctl start cloudflared
sudo systemctl status cloudflared
```

### Erreur 1033 (Argo Tunnel error)

**Cause :** Tunnel ne peut pas se connecter

**Solutions :**

1. **Credentials invalides :**
```bash
# Vérifier le fichier existe
ls -l /etc/cloudflared/credentials.json

# Recréer le tunnel si nécessaire
cloudflared tunnel delete logspanel
cloudflared tunnel create logspanel
sudo cp ~/.cloudflared/<NEW_ID>.json /etc/cloudflared/credentials.json
# Mettre à jour config.yml avec le nouveau ID
sudo systemctl restart cloudflared
```

2. **Configuration incorrecte :**
```bash
# Vérifier config.yml
sudo nano /etc/cloudflared/config.yml
```

Doit ressembler à :
```yaml
tunnel: <TUNNEL_ID>
credentials-file: /etc/cloudflared/credentials.json

ingress:
  - hostname: votre-domaine.com
    service: http://localhost:3001
  - service: http_status:404
```

### "This site can't be reached"

**Cause :** DNS non configuré

**Solution :**
```bash
# Vérifier les routes DNS
cloudflared tunnel route dns logspanel votre-domaine.com

# Vérifier dans Cloudflare Dashboard
# DNS > Records > Doit avoir CNAME vers <tunnel-id>.cfargotunnelcom
```

### Tunnel se déconnecte souvent

**Solutions :**

1. **Mettre à jour cloudflared :**
```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
sudo systemctl stop cloudflared
sudo mv cloudflared /usr/local/bin/
sudo chmod +x /usr/local/bin/cloudflared
sudo systemctl start cloudflared
```

2. **Augmenter le timeout :**
```yaml
# /etc/cloudflared/config.yml
tunnel: <TUNNEL_ID>
credentials-file: /etc/cloudflared/credentials.json

# Ajouter :
no-autoupdate: true
grace-period: 30s

ingress:
  - hostname: votre-domaine.com
    service: http://localhost:3001
  - service: http_status:404
```

---

## 📁 Permissions et Fichiers

### "Read-only file system"

**Erreur :**
```
[ERROR] [Errno 30] Read-only file system: 'servers_config.json'
```

**Solution :**
```bash
# Remonter en lecture/écriture
sudo mount -o remount,rw /

# Vérifier
mount | grep " / "
# Ne doit PAS contenir "ro"
```

### "Permission denied" sur servers_config.json

**Solution :**
```bash
sudo chown www-data:www-data /var/www/logspanel/servers_config.json
sudo chmod 664 /var/www/logspanel/servers_config.json
```

### "Permission denied" sur .env

**Solution :**
```bash
sudo chown www-data:www-data /var/www/logspanel/.env
sudo chmod 600 /var/www/logspanel/.env
```

### Logs: "Failed to write to file"

**Diagnostic :**
```bash
# Activer le mode debug
echo "DEBUG_MODE=true" | sudo tee -a /var/www/logspanel/.env
sudo systemctl restart logspanel

# Voir les permissions détaillées
sudo journalctl -u logspanel -f | grep -E "(permissions|sauvegarde)"
```

**Solution :**
```bash
# Réparer toutes les permissions
cd /var/www/logspanel
sudo chown -R www-data:www-data .
sudo chmod 755 .
sudo chmod 600 .env
sudo chmod 664 servers_config.json
```

---

## 🗄️ Base de Données

### "Can't connect to MySQL server"

**Diagnostic :**
```bash
# Tester la connexion manuellement
mysql -h HOST -P PORT -u USER -p DATABASE
```

**Solutions :**

1. **Firewall bloque :**
```bash
# Synchroniser les règles UFW
sudo /var/www/logspanel/deploy/allow_db_egress.sh --auto

# Vérifier
sudo ufw status | grep mysql
```

2. **Credentials invalides :**
```bash
sudo nano /var/www/logspanel/servers_config.json
# Vérifier database_uri
```

3. **Host inaccessible :**
```bash
# Tester la connectivité
ping mysql.host.com
telnet mysql.host.com 3306
```

### "Access denied for user"

**Cause :** Mauvais utilisateur/mot de passe

**Solution :**
```bash
# Vérifier l'URI dans servers_config.json
sudo nano /var/www/logspanel/servers_config.json

# Format correct :
# "database_uri": "mysql+pymysql://user:password@host:3306/database"
```

**Caractères spéciaux** : Encoder avec %XX

### "Unknown database"

**Cause :** La base de données n'existe pas

**Solution :**
```bash
# Se connecter au MySQL
mysql -h HOST -u USER -p

# Créer la base
CREATE DATABASE database_name CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON database_name.* TO 'user'@'%';
FLUSH PRIVILEGES;
```

### "Too many connections"

**Cause :** Pool de connexions épuisé

**Solution :**
```bash
# Éditer gunicorn_config.py
sudo nano /var/www/logspanel/gunicorn_config.py

# Réduire workers si trop de connexions :
workers = 2  # Au lieu de 4

# Redémarrer
sudo systemctl restart logspanel
```

---

## 🤖 Discord OAuth

### "invalid_client"

**Cause :** Client ID ou Secret incorrect

**Solution :**
1. Aller sur [Discord Developer Portal](https://discord.com/developers/applications)
2. Vérifier **Client ID** et **Client Secret**
3. Mettre à jour `.env`
4. Redémarrer

### "redirect_uri_mismatch"

**Cause :** URI de redirection non configurée

**Solution :**
1. Discord Developer Portal > **OAuth2**
2. Ajouter Redirect : `https://votre-domaine.com/callback`
3. Vérifier `.env` :
```env
GLOBAL_REDIRECT_URI=https://votre-domaine.com/callback
```

### Bot ne voit pas les membres

**Cause :** Intent non activé

**Solution :**
1. Discord Developer Portal > **Bot**
2. Activer **SERVER MEMBERS INTENT**
3. Activer **PRESENCE INTENT**
4. Réinviter le bot sur le serveur avec le bon scope

**Lien d'invitation :**
```
https://discord.com/api/oauth2/authorize?client_id=VOTRE_CLIENT_ID&permissions=0&scope=bot%20applications.commands
```

### "Missing Access"

**Cause :** Bot pas sur le serveur Discord

**Solution :**
Inviter le bot avec le lien ci-dessus.

---

## 🔥 Firewall

### MySQL connection refused après ajout serveur

**Cause :** Règle UFW manquante

**Solution :**
```bash
# Synchroniser manuellement
sudo /var/www/logspanel/deploy/allow_db_egress.sh --auto

# Vérifier
sudo ufw status | grep mysql
```

### UFW bloque tout

**Symptôme :** Impossible de se connecter en SSH

**Solution de secours (Console directe) :**
```bash
# Désactiver UFW temporairement
sudo ufw disable

# Reconfigurer proprement
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw enable

# Resynchroniser MySQL
sudo /var/www/logspanel/deploy/allow_db_egress.sh --auto
```

### Règles UFW dupliquées

**Diagnostic :**
```bash
sudo ufw status numbered
# Si doublons visibles...
```

**Solution :**
```bash
# Supprimer les doublons par numéro
sudo ufw delete <numéro>

# Ou réinitialiser et reconfigurer
sudo ufw --force reset
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw enable
sudo /var/www/logspanel/deploy/allow_db_egress.sh --auto
```

---

## 🏪 Client Panel

### Client ne voit pas le bouton "Créer un serveur"

**Diagnostic :**
```bash
# Activer le mode debug
echo "DEBUG_MODE=true" | sudo tee -a /var/www/logspanel/.env
sudo systemctl restart logspanel

# Se connecter et regarder les logs
sudo journalctl -u logspanel -f | grep -E "(client|CLIENT|check_client_role)"
```

**Solutions :**

1. **Variables non configurées :**
```bash
sudo nano /var/www/logspanel/.env

# Ajouter :
CLIENT_DISCORD_GUILD_ID=1381418967306080307
CLIENT_DISCORD_ROLE_ID=1381418967306080309

sudo systemctl restart logspanel
```

2. **Mauvais ID de rôle :**
```bash
# Vérifier l'ID du rôle sur Discord
# Activer Mode Développeur
# Clic droit sur le rôle > Copier l'ID
# Mettre à jour .env
```

3. **Bot n'a pas les permissions :**
- Vérifier **Server Members Intent** activé
- Réinviter le bot

### "Vous avez déjà un serveur"

**Cause :** Le client a déjà créé 1 serveur (limite atteinte)

**Solution (si légitime) :**
```bash
# Option 1 : Supprimer le serveur existant via l'interface

# Option 2 : Retirer owner_id manuellement
sudo nano /var/www/logspanel/servers_config.json
# Trouver le serveur du client
# Changer "owner_id": "123..." à "owner_id": ""
sudo systemctl restart logspanel
```

### Client ne peut pas supprimer son serveur

**Diagnostic :**
```bash
# Vérifier owner_id
sudo cat /var/www/logspanel/servers_config.json | grep -A 10 "server_id"
```

**Solution :**
Le bouton "Supprimer" n'apparaît que si :
- Utilisateur est **Super Admin**, OU
- `owner_id` du serveur = ID Discord de l'utilisateur

Vérifier que `owner_id` est bien renseigné.

---

## 🔍 Diagnostic Général

### Activer les Logs Complets

```bash
# .env
DEBUG_MODE=true

# Redémarrer
sudo systemctl restart logspanel

# Suivre les logs
sudo journalctl -u logspanel -f --no-pager
```

### Tester les Composants Individuellement

```bash
# 1. Panel répond localement ?
curl -I http://localhost:3001

# 2. Discord Bot accessible ?
python3 << EOF
import requests
import os
from dotenv import load_dotenv
load_dotenv('/var/www/logspanel/.env')
token = os.getenv('DISCORD_BOT_TOKEN')
r = requests.get('https://discord.com/api/users/@me', headers={'Authorization': f'Bot {token}'})
print(f"Status: {r.status_code}")
print(r.json())
EOF

# 3. MySQL accessible ?
mysql -h HOST -u USER -p -e "SELECT 1;"

# 4. UFW configuré ?
sudo ufw status verbose

# 5. Tunnel actif ?
cloudflared tunnel info logspanel
```

### Réinitialisation Complète

**⚠️ Attention : supprime toute la configuration**

```bash
# Sauvegarder d'abord
cd /var/www/logspanel
sudo cp .env .env.backup
sudo cp servers_config.json servers_config.json.backup

# Arrêter les services
sudo systemctl stop logspanel cloudflared

# Réinitialiser
sudo rm .env servers_config.json

# Reconfigurer
sudo cp env.example .env
sudo cp servers_config.json.example servers_config.json
sudo nano .env
sudo nano servers_config.json

# Redémarrer
sudo systemctl start logspanel cloudflared
```

---

## 📞 Obtenir de l'Aide

Si le problème persiste :

1. **Activer le mode debug**
2. **Reproduire le problème**
3. **Exporter les logs** :
```bash
sudo journalctl -u logspanel -n 500 --no-pager > logs_error.txt
sudo journalctl -u cloudflared -n 100 --no-pager >> logs_error.txt
sudo ufw status verbose >> logs_error.txt
```
4. **Partager** `logs_error.txt` avec le support

---

## ➡️ Documentation Complète

- **[INSTALLATION.md](INSTALLATION.md)** - Guide d'installation
- **[CONFIGURATION.md](CONFIGURATION.md)** - Configuration détaillée
- **[MAINTENANCE.md](MAINTENANCE.md)** - Gestion et maintenance
- **[SECURITY.md](SECURITY.md)** - Sécurité

---

**La plupart des problèmes se résolvent en vérifiant les permissions, la configuration et les logs !**
