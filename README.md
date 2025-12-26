# 🚀 Panel Logs Galaxy

Panel de gestion des logs multi-serveurs pour FiveM avec authentification Discord.

## 📋 Table des matières

1. [Installation rapide](#-installation-rapide)
2. [Configuration](#-configuration)
3. [Déploiement Cloudflare Tunnels](#-déploiement-cloudflare-tunnels)
4. [Gestion et maintenance](#-gestion-et-maintenance)
5. [Sécurité](#-sécurité)
6. [Dépannage](#-dépannage)

---

## ⚡ Installation rapide

### Prérequis

- Ubuntu 24.04 LTS
- Accès root ou sudo
- Compte Cloudflare (gratuit)
- Application Discord configurée

### Installation en une commande

```bash
# Cloner le projet
git clone <votre-repo> /var/www/logspanel
cd /var/www/logspanel

# Lancer l'installation
sudo chmod +x deploy/install.sh
sudo ./deploy/install.sh
```

Le script va automatiquement :
- ✅ Installer toutes les dépendances
- ✅ Configurer l'environnement Python
- ✅ Installer cloudflared
- ✅ Configurer le service systemd
- ✅ Sécuriser le firewall

---

## 🔧 Configuration

### 1. Fichier `.env`

Copiez le template et configurez vos secrets :

```bash
cp env.example .env
nano .env
```

**Variables obligatoires :**

```env
# Clés secrètes (générez avec: python -c "import secrets; print(secrets.token_hex(32))")
FLASK_SECRET_KEY=<votre_clé_unique>
JWT_SECRET_KEY=<autre_clé_unique>

# Discord OAuth2
DISCORD_CLIENT_ID=<id_application>
DISCORD_CLIENT_SECRET=<secret_oauth2>
DISCORD_BOT_TOKEN=<token_bot>
GLOBAL_REDIRECT_URI=https://votre-domaine.com/callback

# Super Admin
SUPER_ADMIN_DISCORD_IDS=<vos_ids_discord>
```

### 2. Fichier `servers_config.json`

Copiez le template et configurez vos serveurs :

```bash
cp servers_config.json.example servers_config.json
nano servers_config.json
```

**Exemple :**

```json
{
  "servers": {
    "monserveur": {
      "display_name": "Mon Serveur RP",
      "description": "Serveur FiveM",
      "database_uri": "mysql+pymysql://user:pass@host:3306/db",
      "discord": {
        "guild_id": "123456789",
        "role_id_staff": "123456789",
        "role_id_admin": "123456789"
      }
    }
  }
}
```

---

## 🌐 Déploiement Cloudflare Tunnels

Cloudflare Tunnels permet d'exposer votre panel sur Internet **sans ouvrir de ports** sur votre serveur.

### Avantages

- 🔒 **Aucun port ouvert** - Le serveur n'expose rien publiquement
- 🛡️ **Protection DDoS** - Cloudflare protège automatiquement
- 📜 **SSL automatique** - Certificats gérés par Cloudflare
- ⚡ **Cache CDN** - Assets servis depuis le edge Cloudflare

### Étape 1 : Authentification

```bash
cloudflared tunnel login
```

Cela ouvre un navigateur pour vous authentifier sur Cloudflare.

### Étape 2 : Création du tunnel

```bash
cloudflared tunnel create logspanel
```

**Important :** Notez l'ID du tunnel affiché (format: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)

### Étape 3 : Configuration DNS

```bash
# Remplacez par votre domaine
cloudflared tunnel route dns logspanel votre-domaine.com
cloudflared tunnel route dns logspanel www.votre-domaine.com
```

### Étape 4 : Configuration du tunnel

```bash
# Copier le fichier de credentials
sudo mkdir -p /etc/cloudflared
sudo cp ~/.cloudflared/<TUNNEL_ID>.json /etc/cloudflared/credentials.json

# Créer la configuration
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

### Étape 5 : Installation du service

```bash
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

### Vérification

```bash
# Statut du tunnel
sudo systemctl status cloudflared

# Logs du tunnel
sudo journalctl -u cloudflared -f

# Test
curl https://votre-domaine.com
```

---

## 🔄 Gestion et maintenance

### Script de gestion

```bash
# Afficher le statut
sudo ./deploy/manage.sh status

# Démarrer tous les services
sudo ./deploy/manage.sh start

# Arrêter tous les services
sudo ./deploy/manage.sh stop

# Redémarrer (avec cache bust)
sudo ./deploy/manage.sh restart

# Afficher les logs en temps réel
sudo ./deploy/manage.sh logs

# Mettre à jour les dépendances
sudo ./deploy/manage.sh update

# Guide Cloudflare Tunnel
sudo ./deploy/manage.sh tunnel
```

### Commandes systemd

```bash
# Panel
sudo systemctl status logspanel
sudo systemctl restart logspanel
sudo journalctl -u logspanel -f

# Tunnel Cloudflare
sudo systemctl status cloudflared
sudo systemctl restart cloudflared
sudo journalctl -u cloudflared -f
```

---

## 🔒 Sécurité

### Fichiers sensibles

Ces fichiers ne doivent **JAMAIS** être commités :

- `.env` - Secrets et tokens
- `servers_config.json` - Credentials bases de données
- `/etc/cloudflared/credentials.json` - Credentials tunnel

### Firewall (UFW)

Le script d'installation configure automatiquement UFW :

```bash
# Seul SSH est accessible depuis l'extérieur
sudo ufw status
```

**Règles par défaut :**
- ✅ SSH (port 22) : Ouvert
- ❌ HTTP (port 80) : Fermé
- ❌ HTTPS (port 443) : Fermé
- ❌ Panel (port 3001) : Fermé

Le panel est accessible **uniquement via Cloudflare Tunnel**.

### Headers de sécurité

Le panel configure automatiquement :
- Content-Security-Policy (CSP)
- X-Frame-Options
- X-XSS-Protection
- Strict-Transport-Security (HSTS)

### Rate Limiting

Protection contre les attaques par force brute :
- Login : 10 req/min
- API : 100 req/min
- Captcha : 30 req/min

Consultez `SECURITY.md` pour plus de détails.

---

## 🐛 Dépannage

### Le panel ne démarre pas

```bash
# Vérifier les logs
sudo journalctl -u logspanel -n 100

# Tester manuellement
cd /var/www/logspanel
source venv/bin/activate
python main.py
```

### Le tunnel ne fonctionne pas

```bash
# Vérifier la configuration
cloudflared tunnel info logspanel

# Tester la connexion locale
curl http://localhost:3001

# Vérifier les logs du tunnel
sudo journalctl -u cloudflared -n 100
```

### Erreur "502 Bad Gateway"

Le panel n'est pas accessible. Vérifiez :

1. Le service est démarré : `systemctl status logspanel`
2. Le port écoute : `ss -tlnp | grep 3001`
3. Les logs : `journalctl -u logspanel -n 50`

### Les styles ne se chargent pas

```bash
# Forcer le refresh des assets
sudo ./deploy/manage.sh restart
```

### Cloudflare affiche "Error 1033"

Le tunnel ne peut pas atteindre l'origine :

1. Vérifiez que le panel tourne : `systemctl status logspanel`
2. Vérifiez le port dans `config.yml`
3. Redémarrez le tunnel : `systemctl restart cloudflared`

---

## 📊 Architecture

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│                  │     │                  │     │                  │
│    Visiteur      │────▶│   Cloudflare     │────▶│  cloudflared     │
│    (HTTPS)       │     │   (CDN/WAF)      │     │  (tunnel)        │
│                  │     │                  │     │                  │
└──────────────────┘     └──────────────────┘     └────────┬─────────┘
                                                           │
                                                           ▼
                         ┌──────────────────┐     ┌──────────────────┐
                         │                  │     │                  │
                         │     MySQL        │◀───│   Gunicorn       │
                         │   (databases)    │     │   (Flask app)    │
                         │                  │     │   localhost:3001 │
                         └──────────────────┘     └──────────────────┘
```

**Flux :**
1. Le visiteur accède à `https://votre-domaine.com`
2. Cloudflare termine le SSL et applique les protections
3. La requête est envoyée au tunnel via le réseau Cloudflare
4. `cloudflared` forward vers `localhost:3001`
5. Gunicorn traite la requête Flask
6. La réponse remonte le même chemin

---

## 📁 Structure du projet

```
logspanel/
├── main.py                 # Application Flask principale
├── models.py               # Modèles SQLAlchemy et caches
├── gunicorn_config.py      # Configuration Gunicorn
├── requirements.txt        # Dépendances Python
├── .env                    # Variables d'environnement (non versionné)
├── servers_config.json     # Config serveurs (non versionné)
├── env.example             # Template .env
├── servers_config.json.example
├── SECURITY.md             # Guide de sécurité
├── static/                 # Assets statiques
│   ├── css/
│   ├── js/
│   └── html/               # Templates Jinja2
├── instance/               # Base de données SQLite locale
└── deploy/                 # Scripts de déploiement
    ├── install.sh          # Installation complète
    ├── manage.sh           # Gestion des services
    ├── cloudflared.yml     # Template config tunnel
    ├── logspanel.service   # Service systemd panel
    └── cloudflared.service # Service systemd tunnel
```

---

## ✅ Checklist de déploiement

- [ ] Ubuntu 24.04 installé
- [ ] Projet cloné dans `/var/www/logspanel`
- [ ] `sudo ./deploy/install.sh` exécuté
- [ ] `.env` configuré avec vos secrets
- [ ] `servers_config.json` configuré
- [ ] Cloudflare Tunnel créé et configuré
- [ ] DNS pointant vers le tunnel
- [ ] Service cloudflared démarré
- [ ] Test d'accès via `https://votre-domaine.com`
- [ ] Firewall vérifié (seul SSH ouvert)

---

## 📞 Support

En cas de problème :

1. Consultez les logs : `sudo ./deploy/manage.sh logs`
2. Vérifiez le statut : `sudo ./deploy/manage.sh status`
3. Consultez `SECURITY.md` pour les questions de sécurité
4. Consultez les templates dans `/deploy/` pour les configurations

---

**Made with ❤️ by Galaxy**
