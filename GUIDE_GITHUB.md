# 🚀 Guide Complet : Publier sur GitHub en Sécurité

## ⚠️ SÉCURITÉ CRITIQUE

Votre projet contient des **fichiers sensibles** qui ne doivent **JAMAIS** être publiés :

### ❌ NE JAMAIS PUBLIER
- `.env` - Contient vos tokens Discord, clés JWT, secrets Flask
- `servers_config.json` - Contient vos mots de passe MySQL, IPs de serveurs

### ✅ CES FICHIERS SONT DÉJÀ PROTÉGÉS
Ils sont dans `.gitignore` et ne seront pas publiés automatiquement.

---

# 📋 Publication sur GitHub (Méthode Simple)

## Étape 1 : Créer le dépôt GitHub

1. Allez sur : **https://github.com/new**
2. Configurez :
   - **Nom** : `panellogs`
   - **Description** : `Panel de gestion des logs multi-serveurs pour FiveM`
   - **Public** ✅
   - **NE PAS cocher** "Add README" ou "Add .gitignore"
3. Cliquez sur **"Create repository"**
4. **Copiez l'URL** qui s'affiche (ex: `https://github.com/USERNAME/panellogs.git`)

---

## Étape 2 : Publier le code

Ouvrez votre terminal et exécutez ces commandes :

```bash
# 1. Aller dans le dossier du projet
cd /Users/arielnoteris/Desktop/Projet/panellogs

# 2. Initialiser Git
git init
git branch -M main

# 3. Ajouter tous les fichiers
git add .

# 4. VÉRIFICATION DE SÉCURITÉ - Très important !
git status

# Vérifiez que vous NE voyez PAS :
# ❌ .env
# ❌ servers_config.json
# Si vous les voyez, exécutez :
# git rm --cached .env servers_config.json

# 5. Créer le commit
git commit -m "🎉 Initial commit - Panel Logs Multi-Server"

# 6. Lier au dépôt GitHub (remplacez USERNAME)
git remote add origin https://github.com/USERNAME/panellogs.git

# 7. Pousser vers GitHub
git push -u origin main
```

---

## Étape 3 : Vérification finale

1. Allez sur : `https://github.com/USERNAME/panellogs`
2. **Vérifiez que vous VOYEZ** :
   - ✅ `README.md`
   - ✅ `main.py`
   - ✅ `env.example`
   - ✅ `servers_config.json.example`
3. **Vérifiez que vous NE voyez PAS** :
   - ❌ `.env`
   - ❌ `servers_config.json`

---

# 🆘 En cas de problème

## Problème : Git demande un mot de passe

GitHub n'accepte plus les mots de passe. Créez un **Personal Access Token** :

1. Allez sur : https://github.com/settings/tokens
2. Cliquez sur : `Generate new token (classic)`
3. Nom : `panellogs-deploy`
4. Cochez : `repo`
5. Cliquez sur : `Generate token`
6. **Copiez le token** (vous ne le reverrez plus !)
7. Utilisez ce token comme mot de passe

## Problème : Les fichiers sensibles sont publiés

🚨 **URGENCE** - Exécutez immédiatement :

```bash
# Retirer les fichiers
git rm --cached .env servers_config.json
git commit -m "🔒 Retrait fichiers sensibles"
git push origin main --force

# Changer TOUS vos secrets (MySQL, Discord, JWT)
```

## Problème : Erreur "Permission denied"

Configurez vos identifiants Git :

```bash
git config --global user.name "Votre Nom"
git config --global user.email "votre@email.com"
```

---

# 🔄 Mettre à jour après publication

Pour ajouter des modifications après la publication :

```bash
# Modifier vos fichiers
nano main.py

# Ajouter et commiter
git add .
git commit -m "fix: correction du bug XYZ"

# Pousser
git push origin main
```

---

# 📝 Conventions de commit

Utilisez ces préfixes :

- `feat:` Nouvelle fonctionnalité
- `fix:` Correction de bug
- `docs:` Documentation
- `refactor:` Refactoring
- `style:` Formatage CSS/code
- `chore:` Maintenance

**Exemples** :
```bash
git commit -m "feat: ajout export CSV des logs"
git commit -m "fix: correction authentification Discord"
git commit -m "docs: mise à jour du README"
```

---

# 🎨 Personnaliser le dépôt

Sur GitHub, ajoutez :

1. **Description** :
   - `Panel de gestion des logs multi-serveurs pour FiveM avec authentification Discord`

2. **Topics** (tags) :
   - `fivem`, `logs`, `panel`, `discord`, `python`, `flask`, `cloudflare`

3. **Website** :
   - URL de votre panel si public

---

# 🔒 Règles de sécurité à respecter

### ✅ À FAIRE
- Utiliser `.env` pour tous les secrets
- Toujours vérifier avec `git status` avant de commiter
- Utiliser des variables d'environnement dans le code
- Partager les secrets via un canal sécurisé (pas Git)

### ❌ NE JAMAIS FAIRE
- Commiter `.env` ou `servers_config.json`
- Hardcoder des mots de passe dans le code
- Partager des secrets en clair dans les issues/PR
- Publier des tokens Discord ou clés API

---

# 📊 Structure du projet GitHub

Votre dépôt contiendra :

```
panellogs/
├── .gitignore                    # Fichiers à ignorer
├── README.md                     # Documentation principale
├── SECURITY.md                   # Guide de sécurité
├── LICENSE                       # Licence MIT
├── requirements.txt              # Dépendances Python
├── main.py                       # Application Flask
├── models.py                     # Modèles de données
├── gunicorn_config.py           # Config Gunicorn
├── env.example                   # Template .env (public)
├── servers_config.json.example   # Template config (public)
├── install.sh                    # Script d'installation
├── manage.sh                     # Script de gestion
├── static/                       # Assets (CSS, JS, HTML)
└── deploy/                       # Scripts de déploiement
```

**Ne seront PAS publiés** :
- `.env`
- `servers_config.json`
- `__pycache__/`
- `venv/`
- `*.log`
- `.DS_Store`

---

# 🤝 Travailler en équipe

## Cloner le projet

```bash
# Cloner le dépôt
git clone https://github.com/USERNAME/panellogs.git
cd panellogs

# Créer les fichiers de configuration (demandez-les à votre équipe)
cp env.example .env
cp servers_config.json.example servers_config.json

# Éditer avec vos vraies valeurs
nano .env
nano servers_config.json

# Installer et lancer
./install.sh
```

## Partager les secrets avec l'équipe

**Ne partagez JAMAIS via GitHub** (même en privé) !

Utilisez :
- ✅ 1Password / Bitwarden
- ✅ Discord DM / Signal
- ✅ Service de notes sécurisées (privnote.com)

## Contribuer au projet

```bash
# Créer une branche
git checkout -b feature/ma-fonctionnalite

# Faire vos modifications
git add .
git commit -m "feat: ajout de la fonctionnalité X"

# Pousser la branche
git push origin feature/ma-fonctionnalite

# Créer une Pull Request sur GitHub
```

---

# ✅ Checklist complète

Avant de considérer que c'est terminé :

- [ ] Dépôt créé sur GitHub
- [ ] Fichiers poussés (visibles sur GitHub)
- [ ] `.env` n'est PAS visible sur GitHub
- [ ] `servers_config.json` n'est PAS visible sur GitHub
- [ ] `env.example` EST visible sur GitHub
- [ ] `servers_config.json.example` EST visible sur GitHub
- [ ] README s'affiche correctement
- [ ] Aucun mot de passe visible dans les fichiers
- [ ] Description et topics ajoutés
- [ ] Secrets partagés avec l'équipe (hors Git)

---

# 🎓 Commandes Git essentielles

```bash
# Voir le statut
git status

# Voir les différences
git diff

# Voir l'historique
git log --oneline

# Annuler les modifications locales
git reset --hard HEAD

# Retirer un fichier du staging
git rm --cached fichier.txt

# Mettre à jour depuis GitHub
git pull origin main

# Voir les branches
git branch -a

# Changer de branche
git checkout nom-branche
```

---

# 📞 Support

En cas de problème :

1. Consultez le `README.md` pour l'installation
2. Consultez le `SECURITY.md` pour la sécurité
3. Vérifiez les logs : `sudo journalctl -u logspanel -n 100`
4. Créez une issue sur GitHub (sans secrets !)

---

# 🎉 C'est terminé !

Votre projet est maintenant sur GitHub de manière sécurisée !

**URL** : `https://github.com/USERNAME/panellogs`

Partagez ce lien avec votre équipe et commencez à collaborer ! 🚀

---

**⚠️ RAPPEL FINAL** : Ne commitez JAMAIS `.env` ou `servers_config.json` !
