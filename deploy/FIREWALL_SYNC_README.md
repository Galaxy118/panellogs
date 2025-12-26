# Synchronisation Automatique des Règles Firewall MySQL

Ce système permet de synchroniser automatiquement les règles UFW (firewall) avec les serveurs MySQL configurés dans `servers_config.json`.

## 🔄 Synchronisation Automatique

### Méthode 1 : Intégration dans l'Application (Recommandée)

✅ **Déjà implémenté** - La synchronisation se fait automatiquement quand vous :
- **Créez** un nouveau serveur via l'interface admin
- **Modifiez** la configuration database_uri d'un serveur
- **Supprimez** un serveur

La fonction `sync_firewall_rules()` est appelée automatiquement après chaque opération.

### Méthode 2 : Surveillance Fichier avec Systemd Path Unit

Pour synchroniser automatiquement même si `servers_config.json` est modifié manuellement (hors interface web), installez les services systemd :

```bash
# Copier les fichiers de service
sudo cp /var/www/logspanel/deploy/firewall-sync.service /etc/systemd/system/
sudo cp /var/www/logspanel/deploy/firewall-sync.path /etc/systemd/system/

# Recharger systemd
sudo systemctl daemon-reload

# Activer et démarrer la surveillance
sudo systemctl enable firewall-sync.path
sudo systemctl start firewall-sync.path

# Vérifier le statut
sudo systemctl status firewall-sync.path
```

**Comment ça marche ?**
- Le fichier `.path` surveille `/var/www/logspanel/servers_config.json`
- Dès qu'il est modifié, le service `firewall-sync.service` est déclenché
- Le script `allow_db_egress.sh --auto` s'exécute automatiquement
- Les règles UFW sont mises à jour sans intervention manuelle

### Méthode 3 : Manuel

Vous pouvez toujours lancer manuellement la synchronisation :

```bash
# Mode interactif (avec confirmation)
sudo /var/www/logspanel/allow_db_egress.sh

# Mode automatique (sans confirmation)
sudo /var/www/logspanel/allow_db_egress.sh --auto
```

---

## 📋 Vérification

### Voir les règles UFW actuelles

```bash
sudo ufw status numbered
```

### Voir les logs de synchronisation

```bash
# Logs du service de synchronisation
sudo journalctl -u firewall-sync.service -f

# Logs du path (surveillance fichier)
sudo journalctl -u firewall-sync.path -f
```

### Tester la synchronisation

```bash
# Modifier servers_config.json manuellement
sudo nano /var/www/logspanel/servers_config.json

# La synchronisation se déclenche automatiquement (si path unit installé)
# Sinon, lancez manuellement :
sudo /var/www/logspanel/allow_db_egress.sh --auto
```

---

## 🔧 Configuration

### Désactiver la synchronisation automatique dans l'application

Si vous ne souhaitez pas que l'application synchronise automatiquement, commentez les appels à `sync_firewall_rules()` dans `main.py` :

```python
# Ligne ~2238 (create_server)
# sync_firewall_rules()

# Ligne ~2295 (delete_server)
# sync_firewall_rules()

# Ligne ~2108 (edit_server)
# sync_firewall_rules()
```

### Désactiver la surveillance fichier systemd

```bash
sudo systemctl stop firewall-sync.path
sudo systemctl disable firewall-sync.path
```

---

## 🚨 Important

### Permissions requises

- Le script doit être exécuté avec `sudo` (root)
- L'application Flask doit avoir les permissions pour exécuter `ufw` (via subprocess)

### Sécurité

- La fonction `sync_firewall_rules()` capture toutes les exceptions
- Les erreurs n'interrompent pas l'application
- Les logs sont enregistrés dans `journalctl`
- Aucun secret n'est exposé dans les logs

### Règles créées

Le système crée des règles **EGRESS (sortantes)** uniquement :
- Format : `ufw allow out to any port 3306 proto tcp comment "MySQL host"`
- Les règles existantes ne sont pas dupliquées

### Nettoyage

Le système **n'efface pas** automatiquement les règles devenues obsolètes. Pour nettoyer manuellement :

```bash
# Lister les règles MySQL
sudo ufw status numbered | grep -i mysql

# Supprimer une règle par son numéro
sudo ufw delete <numéro>
```

---

## 📊 Exemple de flux

```
┌─────────────────────────────────────────────────────────────┐
│  Admin crée un serveur via interface web                    │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  server_config.create_server() modifie servers_config.json  │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  sync_firewall_rules() appelé automatiquement               │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  Parse servers_config.json → Extrait host:port MySQL        │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  ufw allow out to any port 3306 proto tcp                   │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  ufw reload                                                  │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  ✅ Connexion MySQL autorisée !                             │
└─────────────────────────────────────────────────────────────┘
```

---

## ❓ Dépannage

### La synchronisation ne fonctionne pas

1. Vérifiez les permissions :
```bash
ls -l /var/www/logspanel/servers_config.json
```

2. Testez manuellement :
```bash
sudo /var/www/logspanel/allow_db_egress.sh --auto
```

3. Vérifiez les logs :
```bash
sudo journalctl -u logspanel -n 100 | grep firewall
```

### Les règles ne sont pas créées

1. Vérifiez que UFW est actif :
```bash
sudo ufw status
```

2. Testez la création manuelle :
```bash
sudo ufw allow out to any port 3306 proto tcp
sudo ufw reload
```

3. Vérifiez les permissions du script :
```bash
ls -l /var/www/logspanel/deploy/allow_db_egress.sh
```

---

## 📝 Notes

- La synchronisation est **idempotente** : exécuter plusieurs fois ne crée pas de doublons
- Les règles existantes sont préservées
- Le système fonctionne pour tous les ports MySQL (3306, 3064, etc.)
- Compatible avec MySQL, MariaDB, et autres bases compatibles
