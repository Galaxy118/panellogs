# 🐛 Mode Debug - Guide d'utilisation

## Configuration

Le mode debug permet d'afficher des logs détaillés pour diagnostiquer les problèmes.

### Activer le mode debug

Ajoutez cette ligne dans votre fichier `.env` :

```env
DEBUG_MODE=true
```

### Désactiver le mode debug

```env
DEBUG_MODE=false
```

Ou supprimez simplement la ligne.

---

## Redémarrer l'application

Après modification du `.env`, redémarrez l'application :

```bash
sudo systemctl restart logspanel
```

---

## Consulter les logs

### En temps réel

```bash
sudo journalctl -u logspanel -f --no-pager
```

### Dernières 100 lignes

```bash
sudo journalctl -u logspanel -n 100 --no-pager
```

### Filtrer par niveau

```bash
# Seulement les erreurs
sudo journalctl -u logspanel -f --no-pager | grep ERROR

# Seulement les warnings
sudo journalctl -u logspanel -f --no-pager | grep WARNING

# Seulement les debug
sudo journalctl -u logspanel -f --no-pager | grep DEBUG
```

---

## Types de logs

### 🔐 Authentification & Permissions

```
[DEBUG] 🔍 check_client_role appelé | user_id=123...
[DEBUG] 🔍 Configuration Client Panel | guild_id=..., role_id=..., enabled=True
[DEBUG] 🌐 Appel API Discord | url=https://discord.com/api/guilds/...
[DEBUG] 📡 Réponse API Discord | status=200
[DEBUG] 👤 Rôles de l'utilisateur | roles=['123...', '456...']
[DEBUG] ✅ Résultat vérification rôle | has_role=True
```

```
[DEBUG] 🔐 get_user_server_permissions appelé | user_id=123...
[DEBUG] 👑 Utilisateur identifié comme SUPER_ADMIN | user_id=123...
[DEBUG] 🏪 Utilisateur identifié comme CLIENT | user_id=123...
[DEBUG] 🏠 Utilisateur propriétaire du serveur | server_id=test, owner_id=123...
```

### 📝 Création de serveur

```
[INFO] 📝 Tentative de création de serveur | user_id=123...
[DEBUG] 🔑 Vérification des permissions | is_super_admin=False, is_client=True
[DEBUG] 🔍 Vérification limite client | owned_count=0
[DEBUG] 📋 Données du formulaire récupérées | server_id=test, display_name=Test Server
[DEBUG] 💾 Création du serveur en cours... | server_id=test
[INFO] ✅ Serveur créé avec succès | server_id=test
```

### 👤 Page Mon Compte

```
[INFO] 👤 Accès page Mon Compte | user_id=123...
[DEBUG] 📊 Statuts des serveurs récupérés | server_count=3
[DEBUG] 🔐 Permissions utilisateur | is_super_admin=False, is_client=True
[DEBUG] 🏪 Client sans serveur détecté - formulaire de création disponible
```

### 💾 Sauvegarde Configuration

```
[DEBUG] 💾 Tentative de sauvegarde de servers_config.json
[DEBUG] 📂 Chemin absolu: /var/www/logspanel/servers_config.json
[DEBUG] 📋 Permissions: 0o100664, Owner UID: 33
[DEBUG] 📁 Dossier parent: /var/www/logspanel, Permissions: 0o40775
[INFO] ✅ Configuration sauvegardée avec succès: servers_config.json
```

### ❌ Erreurs

```
[ERROR] ❌ Erreur de permissions lors de la sauvegarde: [Errno 13] Permission denied
[ERROR] 🔐 Le processus actuel (UID: 33, GID: 33) n'a pas les droits d'écriture
[ERROR] 💡 Solution: sudo chown 33:33 servers_config.json
```

```
[ERROR] ❌ Erreur système lors de la sauvegarde: [Errno 30] Read-only file system
[ERROR] 💿 Le système de fichiers est en lecture seule!
[ERROR] 💡 Solution: sudo mount -o remount,rw /
```

---

## Exemples de diagnostic

### Problème : L'utilisateur n'apparaît pas comme client

1. Activer le debug :
   ```bash
   echo "DEBUG_MODE=true" >> /var/www/logspanel/.env
   sudo systemctl restart logspanel
   ```

2. Se connecter au panel et regarder les logs :
   ```bash
   sudo journalctl -u logspanel -f --no-pager | grep -E "(check_client_role|CLIENT)"
   ```

3. Analyser la sortie :
   ```
   [DEBUG] 🔍 check_client_role appelé | user_id=841996278010740736
   [DEBUG] 🔍 Configuration Client Panel | guild_id=1381418967306080307, role_id=1381418967306080309, enabled=True
   [DEBUG] 📡 Réponse API Discord | status=200
   [DEBUG] 👤 Rôles de l'utilisateur | roles=['123456', '789012']
   [DEBUG] ❌ Résultat vérification rôle | has_role=False
   ```

4. Solution : Le rôle `1381418967306080309` n'est pas dans la liste. Vérifier les IDs dans `.env`.

### Problème : Erreur "Read-only file system"

1. Regarder les logs :
   ```bash
   sudo journalctl -u logspanel -f --no-pager | grep "sauvegarde"
   ```

2. Si vous voyez :
   ```
   [ERROR] 💿 Le système de fichiers est en lecture seule!
   ```

3. Solution :
   ```bash
   sudo mount -o remount,rw /
   ```

### Problème : Permissions denied

1. Regarder les logs :
   ```bash
   sudo journalctl -u logspanel -f --no-pager | grep "permissions"
   ```

2. Si vous voyez :
   ```
   [ERROR] 🔐 Le processus actuel (UID: 33, GID: 33) n'a pas les droits d'écriture
   ```

3. Solution :
   ```bash
   sudo chown www-data:www-data /var/www/logspanel/servers_config.json
   sudo chmod 664 /var/www/logspanel/servers_config.json
   ```

---

## Performance

⚠️ **Important** : Le mode debug génère beaucoup de logs et peut ralentir l'application.

- **En développement** : Mode debug recommandé
- **En production** : Désactiver le mode debug sauf pour diagnostiquer un problème

---

## Niveaux de log

| Niveau | Emoji | Utilisation |
|--------|-------|-------------|
| DEBUG | 🔍 🔐 📋 👤 | Informations détaillées pour le débogage |
| INFO | ✅ 📝 👤 | Événements importants normaux |
| WARNING | ⚠️ ❌ | Avertissements, erreurs non critiques |
| ERROR | ❌ 💥 | Erreurs critiques |

---

## Support

Si les logs ne vous aident pas à résoudre le problème :

1. Activez le mode debug
2. Reproduisez le problème
3. Copiez les logs pertinents :
   ```bash
   sudo journalctl -u logspanel -n 500 --no-pager > debug_logs.txt
   ```
4. Partagez `debug_logs.txt` avec le support
