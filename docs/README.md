# 📚 Documentation Panel Logs Galaxy

Bienvenue dans la documentation complète de Panel Logs Galaxy.

---

## 📖 Guides Disponibles

### 🚀 [Installation](INSTALLATION.md)
Guide complet pour installer le panel sur Ubuntu 24.04 LTS.

**Contenu :**
- Prérequis système
- Installation automatique et manuelle
- Configuration Cloudflare Tunnel
- Vérification et tests

**Pour qui ?** Nouveaux utilisateurs, premiers déploiements

---

### ⚙️ [Configuration](CONFIGURATION.md)
Configuration détaillée de tous les fichiers et variables.

**Contenu :**
- Fichier `.env` (secrets, Discord, Turnstile)
- Fichier `servers_config.json` (serveurs, bases de données)
- Panel Client
- Variables avancées

**Pour qui ?** Tous les utilisateurs après installation

---

### 🔐 [Sécurité](SECURITY.md)
Mesures de sécurité et bonnes pratiques.

**Contenu :**
- Checklist pré-déploiement
- Fichiers sensibles
- Protections implémentées (CSRF, XSS, SQL injection, rate limiting)
- Configuration Cloudflare WAF
- Firewall UFW
- Procédure en cas d'incident

**Pour qui ?** **OBLIGATOIRE avant mise en production**

---

### 🔧 [Maintenance](MAINTENANCE.md)
Gestion quotidienne, debug et monitoring.

**Contenu :**
- Gestion des services systemd
- Mode debug
- Synchronisation firewall
- Mises à jour
- Monitoring
- Sauvegardes

**Pour qui ?** Administrateurs système, utilisateurs avancés

---

### 🆘 [Dépannage](TROUBLESHOOTING.md)
Solutions aux problèmes courants.

**Contenu :**
- Le panel ne démarre pas
- Erreurs de connexion
- Problèmes Cloudflare Tunnel
- Permissions et fichiers
- Base de données
- Discord OAuth
- Firewall
- Client Panel

**Pour qui ?** Tous les utilisateurs rencontrant des problèmes

---

## 🗺️ Parcours Recommandé

### 1️⃣ Première Installation

```
Installation → Configuration → Sécurité → Test
```

1. Suivez **[INSTALLATION.md](INSTALLATION.md)**
2. Configurez avec **[CONFIGURATION.md](CONFIGURATION.md)**
3. Sécurisez avec **[SECURITY.md](SECURITY.md)**
4. Testez l'accès

### 2️⃣ Utilisation Quotidienne

```
Maintenance → Monitoring → Backups
```

Consultez régulièrement **[MAINTENANCE.md](MAINTENANCE.md)**

### 3️⃣ En Cas de Problème

```
Dépannage → Debug → Support
```

1. Cherchez dans **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)**
2. Activez le mode debug ([MAINTENANCE.md](MAINTENANCE.md#-mode-debug))
3. Contactez le support avec les logs

---

## 🔗 Liens Rapides

### Configuration Rapide

| Fichier | Description | Lien |
|---------|-------------|------|
| `.env` | Variables d'environnement | [Configuration > .env](CONFIGURATION.md#-fichier-env) |
| `servers_config.json` | Configuration serveurs | [Configuration > servers_config.json](CONFIGURATION.md#-fichier-servers_configjson) |

### Problèmes Fréquents

| Problème | Solution | Lien |
|----------|----------|------|
| Panel ne démarre pas | Vérifier logs, permissions | [Dépannage](TROUBLESHOOTING.md#-le-panel-ne-démarre-pas) |
| Erreur 502 | Vérifier services, tunnel | [Dépannage](TROUBLESHOOTING.md#erreur-502-bad-gateway) |
| Permission denied | Réparer permissions | [Dépannage](TROUBLESHOOTING.md#permission-denied-sur-servers_configjson) |
| Client ne peut pas créer | Vérifier rôle Discord | [Dépannage](TROUBLESHOOTING.md#client-ne-voit-pas-le-bouton-créer-un-serveur) |

### Commandes Fréquentes

| Action | Commande |
|--------|----------|
| Redémarrer | `sudo systemctl restart logspanel` |
| Voir les logs | `sudo journalctl -u logspanel -f` |
| Mode debug | Voir [MAINTENANCE.md](MAINTENANCE.md#-mode-debug) |
| Synchroniser firewall | `sudo /var/www/logspanel/deploy/allow_db_egress.sh --auto` |

---

## 🎯 Par Profil d'Utilisateur

### 👤 Nouvel Utilisateur

1. **[INSTALLATION.md](INSTALLATION.md)** - Commencez ici
2. **[CONFIGURATION.md](CONFIGURATION.md)** - Configurez votre panel
3. **[SECURITY.md](SECURITY.md)** - Sécurisez avant mise en production

### 🔧 Administrateur Système

1. **[MAINTENANCE.md](MAINTENANCE.md)** - Gestion quotidienne
2. **[SECURITY.md](SECURITY.md)** - Bonnes pratiques
3. **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Résolution de problèmes

### 🏪 Client (Panel Client)

1. **[CONFIGURATION.md > Panel Client](CONFIGURATION.md#-panel-client)** - Comprendre vos permissions
2. **[TROUBLESHOOTING.md > Client Panel](TROUBLESHOOTING.md#-client-panel)** - Résoudre vos problèmes

### 🛡️ Responsable Sécurité

1. **[SECURITY.md](SECURITY.md)** - Mesures complètes
2. **[CONFIGURATION.md](CONFIGURATION.md)** - Configuration sécurisée
3. **[MAINTENANCE.md > Monitoring](MAINTENANCE.md#-monitoring)** - Surveillance

---

## 📋 Checklist Globale

### Avant Production

- [ ] Installation terminée ([INSTALLATION.md](INSTALLATION.md))
- [ ] `.env` configuré avec clés uniques ([CONFIGURATION.md](CONFIGURATION.md))
- [ ] `servers_config.json` configuré ([CONFIGURATION.md](CONFIGURATION.md))
- [ ] Cloudflare Tunnel fonctionnel ([INSTALLATION.md](INSTALLATION.md))
- [ ] Checklist sécurité validée ([SECURITY.md](SECURITY.md))
- [ ] Test d'accès réussi
- [ ] Backups configurés ([MAINTENANCE.md](MAINTENANCE.md))
- [ ] Mode debug désactivé

### Maintenance Régulière

- [ ] Vérifier les logs hebdomadairement ([MAINTENANCE.md](MAINTENANCE.md))
- [ ] Mises à jour mensuelles ([MAINTENANCE.md](MAINTENANCE.md))
- [ ] Backups réguliers ([MAINTENANCE.md](MAINTENANCE.md))
- [ ] Audit sécurité trimestriel ([SECURITY.md](SECURITY.md))

---

## 📞 Support

En cas de problème non résolu par la documentation :

1. **Activer le mode debug** - [MAINTENANCE.md > Mode Debug](MAINTENANCE.md#-mode-debug)
2. **Exporter les logs** - [TROUBLESHOOTING.md](TROUBLESHOOTING.md#-obtenir-de-laide)
3. **Contacter le support** avec les logs

---

## 🔄 Mises à Jour de la Documentation

Cette documentation est maintenue à jour avec chaque version du panel.

**Dernière mise à jour :** Décembre 2024  
**Version :** 1.0

---

**Retour à la [documentation principale](../README.md)**
