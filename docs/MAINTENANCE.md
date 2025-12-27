# 🔧 Guide de Maintenance

Guide de gestion, maintenance et debug de Panel Logs Galaxy.

---

## Table des Matières

1. [Gestion des Services](#-gestion-des-services)
2. [Mode Debug](#-mode-debug)
3. [Synchronisation Firewall](#-synchronisation-firewall)
4. [Mises à Jour](#-mises-à-jour)
5. [Monitoring](#-monitoring)
6. [Sauveg

ardes](#-sauvegardes)

---

## 🚀 Gestion des Services

### Services Systemd

Le panel utilise deux services systemd :
- **logspanel** - L'application Flask/Gunicorn
- **cloudflared** - Le tunnel Cloudflare

### Commandes Logspanel

```bash
# Démarrer
sudo systemctl start logspanel

# Arrêter
sudo systemctl stop logspanel

# Redémarrer
sudo systemctl restart logspanel

# Recharger la configuration (sans couper les connexions)
sudo systemctl reload logspanel

# Statut
sudo systemctl status logspanel

# Activer au démarrage
sudo systemctl enable logspanel

# Désactiver au démarrage
sudo systemctl disable logspanel

# Voir les logs
sudo journalctl -u logspanel -f

# Logs des dernières 100 lignes
sudo journalctl -u logspanel -n 100 --no-pager
```

### Commandes Cloudflared

```bash
# Démarrer
sudo systemctl start cloudflared

# Arrêter
sudo systemctl stop cloudflared

# Redémarrer
sudo systemctl restart cloudflared

# Statut
sudo systemctl status cloudflared

# Voir les logs
sudo journalctl -u cloudflared -f

# Informations du tunnel
cloudflared tunnel info logspanel
```

### Script de Gestion (Optionnel)

Si vous avez installé le script `manage.sh` :

```bash
# Statut de tous les services
sudo ./deploy/manage.sh status

# Démarrer tous les services
sudo ./deploy/manage.sh start

# Arrêter tous les services
sudo ./deploy/manage.sh stop

# Redémarrer avec cache bust
sudo ./deploy/manage.sh restart

# Logs en temps réel
sudo ./deploy/manage.sh logs

# Mettre à jour les dépendances
sudo ./deploy/manage.sh update
```

---

## 🐛 Mode Debug

Le mode debug affiche des logs détaillés pour diagnostiquer les problèmes.

### ⚠️ Important

- **Ne JAMAIS activer en production** (performance)
- Activer uniquement pour diagnostiquer un problème
- Désactiver après résolution

### Activer le Mode Debug

```bash
# Éditer .env
sudo nano /var/www/logspanel/.env

# Ajouter ou modifier
DEBUG_MODE=true

# Redémarrer
sudo systemctl restart logspanel
```

### Désactiver le Mode Debug

```bash
# Éditer .env
sudo nano /var/www/logspanel/.env

# Modifier
DEBUG_MODE=false

# Redémarrer
sudo systemctl restart logspanel
```

### Consulter les Logs

```bash
# En temps réel
sudo journalctl -u logspanel -f --no-pager

# Dernières 100 lignes
sudo journalctl -u logspanel -n 100 --no-pager

# Depuis une date
sudo journalctl -u logspanel --since "2024-12-27 10:00:00"

# Entre deux dates
sudo journalctl -u logspanel --since "2024-12-27 10:00" --until "2024-12-27 11:00"
```

### Filtrer les Logs

```bash
# Seulement les erreurs
sudo journalctl -u logspanel -f | grep ERROR

# Seulement les warnings
sudo journalctl -u logspanel -f | grep WARNING

# Seulement les debug
sudo journalctl -u logspanel -f | grep DEBUG

# Client panel
sudo journalctl -u logspanel -f | grep -E "(client|CLIENT|Client)"

# Authentification
sudo journalctl -u logspanel -f | grep -E "(auth|login|LOGIN)"

# Création de serveur
sudo journalctl -u logspanel -f | grep -E "(création|create_server)"

# Permissions
sudo journalctl -u logspanel -f | grep -E "(permissions|role)"
```

### Types de Logs

#### 🔐 Authentification & Rôles

```
[DEBUG] 🔍 check_client_role appelé | user_id=123...
[DEBUG] 🔍 Configuration Client Panel | guild_id=..., role_id=...
[DEBUG] 🌐 Appel API Discord | url=https://discord.com/api/...
[DEBUG] 📡 Réponse API Discord | status=200
[DEBUG] 👤 Rôles de l'utilisateur | roles=['123...', '456...']
[DEBUG] ✅ Résultat vérification rôle | has_role=True
```

#### 📝 Création de Serveur

```
[INFO] 📝 Tentative de création de serveur | user_id=123...
[DEBUG] 🔑 Vérification des permissions | is_super_admin=False, is_client=True
[DEBUG] 🔍 Vérification limite client | owned_count=0
[DEBUG] 📋 Données du formulaire récupérées | server_id=test
[DEBUG] 💾 Création du serveur en cours... | server_id=test
[INFO] ✅ Serveur créé avec succès | server_id=test
```

#### 💾 Sauvegarde Configuration

```
[DEBUG] 💾 Tentative de sauvegarde de servers_config.json
[DEBUG] 📂 Chemin absolu: /var/www/logspanel/servers_config.json
[DEBUG] 📋 Permissions: 0o100664, Owner UID: 33
[INFO] ✅ Configuration sauvegardée avec succès
```

#### ❌ Erreurs

```
[ERROR] ❌ Erreur de permissions lors de la sauvegarde: Permission denied
[ERROR] 🔐 Le processus actuel (UID: 33, GID: 33) n'a pas les droits
[ERROR] 💡 Solution: sudo chown www-data:www-data servers_config.json
```

### Exporter les Logs

```bash
# Sauvegarder les logs dans un fichier
sudo journalctl -u logspanel -n 500 --no-pager > debug_logs.txt

# Avec horodatage
sudo journalctl -u logspanel -n 500 --no-pager > debug_$(date +%Y%m%d_%H%M%S).txt
```

---

## 🔥 Synchronisation Firewall

Le panel synchronise automatiquement les règles UFW pour les connexions MySQL.

### Synchronisation Automatique

✅ **Déjà intégré** - La synchronisation se fait automatiquement :
- Lors de la **création** d'un serveur
- Lors de la **modification** d'une `database_uri`
- Lors de la **suppression** d'un serveur

### Synchronisation Manuelle

```bash
# Mode interactif (demande confirmation)
sudo /var/www/logspanel/deploy/allow_db_egress.sh

# Mode automatique (sans confirmation)
sudo /var/www/logspanel/deploy/allow_db_egress.sh --auto
```

### Vérifier les Règles

```bash
# Voir toutes les règles UFW
sudo ufw status numbered

# Voir seulement les règles MySQL
sudo ufw status | grep -i mysql

# Règles sortantes (egress)
sudo ufw status | grep -i "ALLOW OUT"
```

### Supprimer une Règle

```bash
# Lister avec numéros
sudo ufw status numbered

# Supprimer par numéro
sudo ufw delete <numéro>

# Recharger
sudo ufw reload
```

### Logs Firewall

```bash
# Activer les logs UFW
sudo ufw logging on

# Voir les logs
sudo tail -f /var/log/ufw.log

# Filtrer connexions MySQL
sudo tail -f /var/log/ufw.log | grep 3306
```

---

## 🔄 Mises à Jour

### Mettre à Jour le Code

```bash
cd /var/www/logspanel

# Récupérer les derniers commits
sudo git fetch origin

# Voir les changements
sudo git log HEAD..origin/main --oneline

# Appliquer les mises à jour
sudo git pull origin main

# Redémarrer
sudo systemctl restart logspanel
```

### Mettre à Jour Python Packages

```bash
cd /var/www/logspanel
source venv/bin/activate

# Mettre à jour pip
pip install --upgrade pip

# Mettre à jour les packages
pip install --upgrade -r requirements.txt

# Désactiver le venv
deactivate

# Redémarrer
sudo systemctl restart logspanel
```

### Mettre à Jour le Système

```bash
# Mettre à jour les packages système
sudo apt update
sudo apt upgrade -y

# Redémarrer si kernel mis à jour
sudo reboot
```

### Mettre à Jour cloudflared

```bash
# Télécharger la dernière version
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared

# Remplacer
sudo systemctl stop cloudflared
sudo mv cloudflared /usr/local/bin/
sudo chmod +x /usr/local/bin/cloudflared
sudo systemctl start cloudflared

# Vérifier la version
cloudflared --version
```

---

## 📊 Monitoring

### Vérifier l'État des Services

```bash
# Services actifs ?
sudo systemctl is-active logspanel cloudflared

# Services activés au démarrage ?
sudo systemctl is-enabled logspanel cloudflared

# Statut détaillé
sudo systemctl status logspanel cloudflared
```

### Surveiller les Ressources

```bash
# CPU et RAM utilisés par logspanel
ps aux | grep gunicorn

# Statistiques détaillées
sudo systemctl status logspanel | grep -E "Memory|CPU"

# htop (à installer : sudo apt install htop)
htop -p $(pgrep -f gunicorn | tr '\n' ',' | sed 's/,$//')
```

### Surveillance Continue

```bash
# Logs en temps réel avec filtre erreurs
sudo journalctl -u logspanel -f | grep -E "ERROR|WARN"

# Alertes sur les 429 (rate limit atteint)
sudo journalctl -u logspanel -f | grep "429"

# Connexions échouées
sudo journalctl -u logspanel -f | grep -i "fail"
```

### Tester la Disponibilité

```bash
# Test local
curl -I http://localhost:3001

# Test via Cloudflare
curl -I https://votre-domaine.com

# Test complet avec temps de réponse
time curl https://votre-domaine.com > /dev/null
```

### Monitoring Externe

Outils recommandés :
- **Uptime Robot** (gratuit) - Monitoring de disponibilité
- **Grafana + Prometheus** - Métriques avancées
- **Cloudflare Analytics** - Stats intégrées

---

## 💾 Sauvegardes

### Fichiers à Sauvegarder

| Fichier | Importance | Chiffrer |
|---------|------------|----------|
| `.env` | 🔴 Critique | ✅ Oui |
| `servers_config.json` | 🔴 Critique | ✅ Oui |
| Bases MySQL | 🔴 Critique | ✅ Oui |
| `/etc/cloudflared/` | 🟡 Important | ✅ Oui |
| `static/` (customs) | 🟢 Optionnel | ❌ Non |

### Backup Chiffré

```bash
# Créer un backup chiffré avec GPG
cd /var/www/logspanel
sudo tar czf - .env servers_config.json | \
    gpg --symmetric --cipher-algo AES256 \
    -o ~/backup_panel_$(date +%Y%m%d).tar.gz.gpg

# Restaurer
gpg --decrypt ~/backup_panel_20241227.tar.gz.gpg | sudo tar xzf - -C /var/www/logspanel
```

### Backup MySQL

```bash
# Backup d'une base
mysqldump -u user -p database_name > backup_db.sql

# Backup de toutes les bases
for db in $(mysql -u user -ppassword -e "SHOW DATABASES;" | grep -v Database | grep -v information_schema | grep -v performance_schema | grep -v mysql); do
    mysqldump -u user -ppassword $db > backup_${db}_$(date +%Y%m%d).sql
done

# Chiffrer
gpg --symmetric --cipher-algo AES256 backup_db.sql
```

### Automatiser les Backups

Créer un script `/root/backup_panel.sh` :

```bash
#!/bin/bash
BACKUP_DIR="/root/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup fichiers config
cd /var/www/logspanel
tar czf - .env servers_config.json | \
    gpg --batch --yes --passphrase-file /root/.backup_passphrase \
    --symmetric --cipher-algo AES256 \
    -o $BACKUP_DIR/panel_$DATE.tar.gz.gpg

# Garder seulement les 30 derniers backups
find $BACKUP_DIR -name "panel_*.tar.gz.gpg" -mtime +30 -delete

echo "Backup terminé: panel_$DATE.tar.gz.gpg"
```

Ajouter au cron :

```bash
sudo crontab -e

# Backup quotidien à 3h du matin
0 3 * * * /root/backup_panel.sh >> /var/log/backup_panel.log 2>&1
```

---

## 🔧 Commandes Utiles

### Redémarrage Propre

```bash
# Arrêter tous les services
sudo systemctl stop logspanel cloudflared

# Attendre 5 secondes
sleep 5

# Redémarrer
sudo systemctl start cloudflared logspanel

# Vérifier
sudo systemctl status logspanel cloudflared
```

### Cache Bust Assets

Après modification de CSS/JS :

```bash
# Générer nouvelle version
NEW_VERSION=$(date +%s)

# Mettre à jour .env
sudo sed -i "s/ASSET_VERSION=.*/ASSET_VERSION=$NEW_VERSION/" /var/www/logspanel/.env

# Redémarrer
sudo systemctl restart logspanel

echo "Nouvelle version: $NEW_VERSION"
```

### Nettoyer les Logs

```bash
# Voir la taille des logs
sudo journalctl --disk-usage

# Garder seulement 7 jours
sudo journalctl --vacuum-time=7d

# Garder seulement 500M
sudo journalctl --vacuum-size=500M

# Rotation manuelle
sudo journalctl --rotate
```

### Permissions Rapides

```bash
# Réparer toutes les permissions
cd /var/www/logspanel
sudo chown -R www-data:www-data .
sudo chmod 600 .env
sudo chmod 664 servers_config.json
sudo chmod 755 deploy/*.sh
```

---

## ➡️ En Savoir Plus

- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Résolution de problèmes
- **[SECURITY.md](SECURITY.md)** - Bonnes pratiques de sécurité
- **[CONFIGURATION.md](CONFIGURATION.md)** - Configuration avancée

---

**Maintenance régulière = Panel stable et performant !**
