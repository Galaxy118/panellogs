# 🔐 Guide de Sécurité - Panel Logs VOLTRE

Ce document résume les mesures de sécurité implémentées et les bonnes pratiques à suivre.

## ⚠️ Configuration Obligatoire Avant Déploiement

### 1. Fichiers Sensibles

**NE JAMAIS COMMITER ces fichiers :**
- `.env` - Contient les secrets (clés API, tokens Discord, etc.)
- `servers_config.json` - Contient les credentials des bases de données

Ces fichiers sont listés dans `.gitignore`.

### 2. Variables d'Environnement Obligatoires

Copiez `env.example` vers `.env` et configurez :

```bash
# Générez des clés secrètes uniques (ne réutilisez JAMAIS ces valeurs) :
python -c "import secrets; print(secrets.token_hex(32))"

# Obligatoire :
FLASK_SECRET_KEY=<clé_générée>
JWT_SECRET_KEY=<autre_clé_générée>
DISCORD_CLIENT_ID=<votre_id>
DISCORD_CLIENT_SECRET=<votre_secret>
DISCORD_BOT_TOKEN=<votre_token>
GLOBAL_REDIRECT_URI=https://votre-domaine.com/callback
SUPER_ADMIN_DISCORD_IDS=<vos_ids>
```

### 3. Installation des Dépendances de Sécurité

```bash
pip install -r requirements.txt

# Dépendances de sécurité incluses :
# - Flask-WTF (protection CSRF)
# - Flask-Limiter (rate limiting)
# - cryptography (génération de tokens sécurisés)
```

---

## 🛡️ Mesures de Sécurité Implémentées

### Protection contre les Injections SQL
- ✅ Tous les filtres de recherche sont sanitisés
- ✅ Caractères spéciaux LIKE (%, _, \) échappés
- ✅ Longueur des entrées limitée
- ✅ SQLAlchemy ORM avec requêtes paramétrées

### Protection CSRF (Cross-Site Request Forgery)
- ✅ Flask-WTF intégré
- ✅ Tokens CSRF dans tous les formulaires
- ✅ Vérification automatique sur les requêtes POST
- ✅ Routes API exemptées (utilisent des tokens d'auth)

### Protection XSS (Cross-Site Scripting)
- ✅ Content-Security-Policy headers
- ✅ X-XSS-Protection headers
- ✅ Jinja2 échappement automatique
- ✅ Sanitisation des données utilisateur

### Rate Limiting
- ✅ Limite globale : 1000 req/heure, 100 req/minute
- ✅ Login : 10 req/minute
- ✅ Callback OAuth : 20 req/minute
- ✅ Captcha : 30 req/minute
- ✅ API logs : 100 req/minute

### Authentification Sécurisée
- ✅ JWT avec expiration (24h)
- ✅ Cookies HttpOnly, Secure, SameSite=Strict
- ✅ Comparaison de tokens en temps constant
- ✅ Pas de secrets par défaut en production

### Headers de Sécurité HTTP
- ✅ `Strict-Transport-Security` (HSTS)
- ✅ `X-Frame-Options: SAMEORIGIN`
- ✅ `X-Content-Type-Options: nosniff`
- ✅ `X-XSS-Protection: 1; mode=block`
- ✅ `Referrer-Policy: strict-origin-when-cross-origin`
- ✅ `Permissions-Policy`
- ✅ `Content-Security-Policy`

### Protection Cloudflare
- ✅ Validation des IPs Cloudflare
- ✅ Trust uniquement `CF-Connecting-IP` si IP source Cloudflare
- ✅ Protection contre le spoofing de headers

---

## 🚀 Déploiement Ubuntu 24.04 + Cloudflare Tunnels

### 1. Configuration Cloudflare Tunnel

```bash
# Installer cloudflared
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared
sudo mv cloudflared /usr/local/bin/

# Authentifier et créer le tunnel
cloudflared tunnel login
cloudflared tunnel create panellogs
```

### 2. Configuration du Tunnel

Créez `/etc/cloudflared/config.yml` :
```yaml
tunnel: <VOTRE_TUNNEL_ID>
credentials-file: /etc/cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: votre-domaine.com
    service: http://localhost:3001
  - service: http_status:404
```

### 3. Service Systemd

```bash
# Installer le service
sudo cp logspanel.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable logspanel
sudo systemctl start logspanel

# Service Cloudflare
sudo cloudflared service install
```

### 4. Firewall (UFW)

```bash
# Bloquer l'accès direct - seul Cloudflare peut accéder
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
# NE PAS ouvrir le port 3001 - Cloudflare Tunnel l'utilise en local
sudo ufw enable
```

---

## 📋 Checklist Pré-Déploiement

- [ ] `.env` configuré avec des clés uniques
- [ ] `servers_config.json` configuré sans credentials par défaut
- [ ] Les fichiers sensibles sont dans `.gitignore`
- [ ] `pip install -r requirements.txt` exécuté
- [ ] Cloudflare Tunnel configuré
- [ ] Service systemd activé
- [ ] Firewall configuré
- [ ] SSL/TLS forcé via Cloudflare
- [ ] Turnstile configuré (optionnel mais recommandé)

---

## 🔍 Monitoring Recommandé

1. **Logs Gunicorn** : `journalctl -u logspanel -f`
2. **Logs Cloudflare** : Dashboard Cloudflare > Analytics
3. **Rate Limiting** : Surveiller les 429 dans les logs
4. **Erreurs** : Configurer des alertes sur les erreurs 500

---

## 📞 En Cas d'Incident de Sécurité

1. **Désactiver immédiatement** : `sudo systemctl stop logspanel`
2. **Révoquer les tokens Discord** : Discord Developer Portal
3. **Changer les secrets** : `.env` - tous les tokens/clés
4. **Vérifier les logs** : `journalctl -u logspanel --since "1 hour ago"`
5. **Analyser** : Identifier la faille et corriger
6. **Redéployer** : Après correction
