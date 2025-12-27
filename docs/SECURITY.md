# 🔐 Guide de Sécurité

Mesures de sécurité implémentées et bonnes pratiques pour Panel Logs Galaxy.

---

## Table des Matières

1. [Checklist Pré-Déploiement](#-checklist-pré-déploiement)
2. [Fichiers Sensibles](#-fichiers-sensibles)
3. [Mesures de Sécurité Implémentées](#️-mesures-de-sécurité-implémentées)
4. [Configuration Cloudflare](#-configuration-cloudflare)
5. [Firewall UFW](#-firewall-ufw)
6. [Bonnes Pratiques](#-bonnes-pratiques)
7. [En Cas d'Incident](#-en-cas-dincident)

---

## ✅ Checklist Pré-Déploiement

Avant de mettre en production, vérifiez :

### Fichiers de Configuration

- [ ] `.env` créé avec des clés **uniques** (jamais de valeurs par défaut)
- [ ] `servers_config.json` sans credentials de test
- [ ] `.gitignore` inclut `.env` et `servers_config.json`
- [ ] Permissions fichiers : `.env` (600), `servers_config.json` (664)
- [ ] Propriétaire : `www-data:www-data`

### Services

- [ ] Cloudflare Tunnel configuré (pas d'accès direct au serveur)
- [ ] Service `logspanel` activé et démarré
- [ ] Service `cloudflared` activé et démarré
- [ ] UFW activé et configuré
- [ ] Seul le port SSH ouvert (22)

### Variables d'Environnement

- [ ] `FLASK_SECRET_KEY` unique (32+ caractères)
- [ ] `JWT_SECRET_KEY` unique (différente de FLASK_SECRET_KEY)
- [ ] `DISCORD_BOT_TOKEN` valide et sécurisé
- [ ] `DEBUG_MODE=false` en production
- [ ] `GLOBAL_REDIRECT_URI` correct (https)

### Cloudflare

- [ ] SSL/TLS : **Full (strict)** ou **Full**
- [ ] Turnstile activé (optionnel mais recommandé)
- [ ] WAF activé (Web Application Firewall)
- [ ] Rate Limiting configuré

---

## 📁 Fichiers Sensibles

### ⚠️ NE JAMAIS COMMITER

Ces fichiers contiennent des secrets et **ne doivent JAMAIS être versionnés** :

| Fichier | Contenu Sensible | Protection |
|---------|------------------|------------|
| `.env` | Clés API, tokens Discord, secrets | `.gitignore` |
| `servers_config.json` | Credentials MySQL, tokens | `.gitignore` |
| `/etc/cloudflared/credentials.json` | Token Cloudflare Tunnel | Système |

### Vérifier `.gitignore`

```bash
cat .gitignore | grep -E "\.env|servers_config\.json"
```

Doit contenir :
```
.env
servers_config.json
```

### Permissions Fichiers

```bash
# .env - Lecture seule pour propriétaire uniquement
sudo chmod 600 /var/www/logspanel/.env
sudo chown www-data:www-data /var/www/logspanel/.env

# servers_config.json - Lecture/écriture propriétaire, lecture groupe
sudo chmod 664 /var/www/logspanel/servers_config.json
sudo chown www-data:www-data /var/www/logspanel/servers_config.json
```

---

## 🛡️ Mesures de Sécurité Implémentées

### 1. Protection Injection SQL

✅ **SQLAlchemy ORM** - Requêtes paramétrées
- Tous les filtres utilisent des requêtes préparées
- Échappement automatique des caractères spéciaux
- Longueur des entrées limitée

✅ **Sanitisation des recherches LIKE**
- Caractères `%`, `_`, `\` échappés
- Validation des entrées utilisateur

**Exemple :**
```python
# ❌ DANGEREUX (SQL brut)
query = f"SELECT * FROM logs WHERE message LIKE '%{user_input}%'"

# ✅ SÉCURISÉ (SQLAlchemy + échappement)
Log.query.filter(Log.message.like(f"%{sanitize_like(user_input)}%"))
```

### 2. Protection CSRF

✅ **Flask-WTF** intégré
- Token CSRF dans tous les formulaires
- Vérification automatique sur POST/PUT/DELETE
- Routes API exemptées (utilisent JWT)

**Implémentation :**
```python
# Template HTML
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">

# Backend
@csrf.exempt  # Pour les API uniquement
@app.route('/api/logs', methods=['POST'])
```

### 3. Protection XSS

✅ **Headers de sécurité**
- `Content-Security-Policy` strict
- `X-XSS-Protection: 1; mode=block`
- `X-Content-Type-Options: nosniff`

✅ **Jinja2** - Échappement automatique
- Toutes les variables sont échappées
- `{{ user_input }}` → sécurisé automatiquement

### 4. Rate Limiting

✅ **Flask-Limiter** - Protection brute force

| Route | Limite | Description |
|-------|--------|-------------|
| Global | 1000/heure, 100/min | Toutes les requêtes |
| `/login` | 10/min | Connexion Discord |
| `/callback` | 20/min | Callback OAuth |
| `/api/turnstile` | 30/min | Vérification captcha |
| `/api/logs` | 100/min | Récupération logs |

**Réponse en cas de dépassement :**
```json
{
  "error": "Rate limit exceeded",
  "retry_after": 60
}
```
HTTP 429 Too Many Requests

### 5. Authentification JWT

✅ **Tokens sécurisés**
- Signature HMAC-SHA256
- Expiration : 24 heures
- Cookies HttpOnly, Secure, SameSite=Strict

**Configuration :**
```python
response.set_cookie(
    'auth_token',
    token,
    httponly=True,      # JavaScript ne peut pas y accéder
    secure=True,        # HTTPS uniquement
    samesite='Strict',  # Pas de requêtes cross-site
    max_age=86400       # 24 heures
)
```

### 6. Headers de Sécurité HTTP

✅ **Configuration complète**

```python
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Frame-Options: SAMEORIGIN
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' cdn.jsdelivr.net cdnjs.cloudflare.com challenges.cloudflare.com; style-src 'self' 'unsafe-inline' cdn.jsdelivr.net cdnjs.cloudflare.com fonts.googleapis.com; font-src 'self' fonts.gstatic.com cdnjs.cloudflare.com; img-src 'self' data: cdn.discordapp.com; connect-src 'self' challenges.cloudflare.com; frame-src 'self' challenges.cloudflare.com
```

### 7. Protection Cloudflare

✅ **Validation des IPs Cloudflare**
- Liste des plages IP Cloudflare mise en cache
- Vérification de l'origine des requêtes
- Trust du header `CF-Connecting-IP` uniquement si IP source Cloudflare

**Implémentation :**
```python
def is_cloudflare_ip(ip):
    # Vérifie que l'IP est dans les ranges Cloudflare
    # Évite le spoofing de headers
    pass
```

---

## ☁️ Configuration Cloudflare

### SSL/TLS

**Mode recommandé : Full (strict)**

1. Dashboard Cloudflare > **SSL/TLS**
2. Mode : **Full (strict)**
3. ✅ **Always Use HTTPS** : ON
4. ✅ **Automatic HTTPS Rewrites** : ON
5. ✅ **Minimum TLS Version** : TLS 1.2

### Web Application Firewall (WAF)

1. **Security** > **WAF**
2. Activer les règles managées :
   - ✅ Cloudflare Managed Ruleset
   - ✅ OWASP Core Ruleset
3. Créer une règle custom :
   - **If** : `Country not in [FR, BE, CA, etc.]`
   - **Then** : Challenge (CAPTCHA)

### Rate Limiting

1. **Security** > **Rate Limiting Rules**
2. Créer une règle :
   - **When incoming requests match** : `URI Path contains /login`
   - **Then** : Block for 1 minute
   - **Rate** : 10 requests per minute

### Turnstile (Captcha)

1. **Turnstile** > **Add Site**
2. Mode : **Managed** (recommandé)
3. Copier les clés dans `.env`

**Voir [CONFIGURATION.md](CONFIGURATION.md) pour les détails.**

---

## 🔥 Firewall UFW

### Configuration Sécurisée

```bash
# Politique par défaut
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Autoriser SSH uniquement
sudo ufw allow ssh

# Activer
sudo ufw --force enable
```

### Vérifier

```bash
sudo ufw status verbose
```

**Sortie attendue :**
```
Status: active

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW IN    Anywhere
22/tcp (v6)                ALLOW IN    Anywhere (v6)
```

### ⚠️ Important

**NE PAS ouvrir :**
- Port 80 (HTTP)
- Port 443 (HTTPS)
- Port 3001 (Panel)

L'accès se fait **uniquement via Cloudflare Tunnel**.

### Connexions MySQL Sortantes

Les connexions vers les bases de données MySQL sont automatiquement autorisées :

```bash
# Voir les règles MySQL
sudo ufw status | grep mysql

# Synchroniser manuellement
sudo /var/www/logspanel/deploy/allow_db_egress.sh --auto
```

---

## 📖 Bonnes Pratiques

### 1. Génération de Secrets

**❌ Mauvais :**
```env
FLASK_SECRET_KEY=supersecret123
JWT_SECRET_KEY=mykey
```

**✅ Bon :**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Mots de Passe MySQL

- ✅ Minimum 16 caractères
- ✅ Mélange majuscules, minuscules, chiffres, symboles
- ✅ Différent pour chaque serveur
- ✅ Échapper les caractères spéciaux dans l'URI

**Exemple :**
```python
# Mot de passe : P@ss!2024#Secure
# URI encodée :
"mysql+pymysql://user:P%40ss%212024%23Secure@host:3306/db"
```

### 3. Discord Bot Token

- ✅ Ne jamais partager le token
- ✅ Régénérer si compromis (Discord Developer Portal)
- ✅ Activer **Server Members Intent** et **Presence Intent**

### 4. Rotation des Secrets

**Fréquence recommandée :**
- `FLASK_SECRET_KEY` : Tous les 6 mois
- `JWT_SECRET_KEY` : Tous les 6 mois
- `DISCORD_BOT_TOKEN` : En cas de suspicion de compromission
- Mots de passe MySQL : Tous les 3 mois

**Procédure :**
1. Générer nouveau secret
2. Mettre à jour `.env`
3. Redémarrer : `sudo systemctl restart logspanel`

### 5. Logs et Monitoring

```bash
# Surveiller les tentatives d'authentification
sudo journalctl -u logspanel -f | grep -i "login\|auth"

# Surveiller les erreurs
sudo journalctl -u logspanel -f | grep -i "error\|warn"

# Surveiller les 429 (rate limit)
sudo journalctl -u logspanel -f | grep "429"
```

### 6. Sauvegardes

**Fichiers à sauvegarder régulièrement :**
- `.env` (chiffré !)
- `servers_config.json`
- Bases de données MySQL

```bash
# Backup chiffré avec GPG
tar czf - /var/www/logspanel/{.env,servers_config.json} | \
    gpg --symmetric --cipher-algo AES256 > backup_$(date +%Y%m%d).tar.gz.gpg
```

### 7. Mises à Jour

```bash
# Mettre à jour le système
sudo apt update && sudo apt upgrade -y

# Mettre à jour Python packages
cd /var/www/logspanel
source venv/bin/activate
pip install --upgrade -r requirements.txt
sudo systemctl restart logspanel
```

---

## 🚨 En Cas d'Incident

### 1. Désactiver Immédiatement

```bash
# Arrêter le panel
sudo systemctl stop logspanel

# Arrêter le tunnel (si nécessaire)
sudo systemctl stop cloudflared
```

### 2. Analyser les Logs

```bash
# Logs des dernières heures
sudo journalctl -u logspanel --since "2 hours ago" > incident_logs.txt

# Rechercher les anomalies
grep -i "error\|fail\|unauthorized" incident_logs.txt
```

### 3. Révoquer les Accès

- **Discord Bot** : Régénérer le token (Developer Portal)
- **Cloudflare** : Régénérer le tunnel si nécessaire
- **MySQL** : Changer les mots de passe

### 4. Changer les Secrets

```bash
# Générer de nouveaux secrets
python3 -c "import secrets; print('FLASK:', secrets.token_hex(32))"
python3 -c "import secrets; print('JWT:', secrets.token_hex(32))"

# Éditer .env
sudo nano /var/www/logspanel/.env
```

### 5. Vérifier l'Intégrité

```bash
# Vérifier les fichiers modifiés récemment
find /var/www/logspanel -type f -mtime -1 -ls

# Comparer avec le dépôt Git
cd /var/www/logspanel
git diff
```

### 6. Redéployer

```bash
# Pull la dernière version propre
git reset --hard origin/main
git pull

# Redémarrer
sudo systemctl start logspanel
sudo systemctl start cloudflared
```

### 7. Monitoring Renforcé

```bash
# Activer le debug temporairement
echo "DEBUG_MODE=true" | sudo tee -a /var/www/logspanel/.env
sudo systemctl restart logspanel

# Surveiller en temps réel
sudo journalctl -u logspanel -f
```

---

## 📋 Checklist de Sécurité Mensuelle

- [ ] Vérifier les logs pour anomalies
- [ ] Vérifier UFW status
- [ ] Mettre à jour le système (`apt upgrade`)
- [ ] Mettre à jour Python packages
- [ ] Vérifier les permissions fichiers
- [ ] Sauvegarder `.env` et `servers_config.json`
- [ ] Tester l'accès avec un compte non-admin
- [ ] Vérifier Cloudflare WAF logs
- [ ] Vérifier les certificats SSL

---

## ➡️ En Savoir Plus

- **[INSTALLATION.md](INSTALLATION.md)** - Installation sécurisée
- **[CONFIGURATION.md](CONFIGURATION.md)** - Configuration des secrets
- **[MAINTENANCE.md](MAINTENANCE.md)** - Gestion et surveillance
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Résolution de problèmes

---

**La sécurité est un processus continu, pas un état final.**
