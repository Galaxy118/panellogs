from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import OperationalError
from sqlalchemy import create_engine, text, func
from sqlalchemy.orm import sessionmaker
import json
import os
import time
from datetime import datetime
import threading
import logging
import sys

db = SQLAlchemy()

# Configurer le logger pour models.py
logger = logging.getLogger(__name__)

# Cache pour les connexions de base de données par serveur
server_db_connections = {}
server_db_sessions = {}
server_db_uris = {}  # Stocke l'URI utilisée pour chaque connexion
_db_lock = threading.Lock()

# JSON parsing accéléré avec fallback
try:
    import orjson as _fastjson
    def parse_json_fast(data):
        try:
            return _fastjson.loads(data)
        except Exception:
            return {}
except Exception:
    def parse_json_fast(data):
        try:
            return json.loads(data)
        except Exception:
            return {}

class Log(db.Model):
    __tablename__ = 'vlogs'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    type = db.Column(db.Text, nullable=False)  # tinytext équivalent
    data = db.Column(db.Text, nullable=False)  # stockage JSON
    date = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    
    def __repr__(self):
        return f'<Log {self.id}: {self.type}>'
    
    def get_data_json(self):
        """Retourne les données JSON parsées"""
        return parse_json_fast(self.data)


class ServerConfig:
    """Classe pour gérer la configuration des serveurs"""
    
    def __init__(self, config_file='servers_config.json'):
        self.config_file = config_file
        self._config = None
        self.load_config()
    
    def load_config(self):
        """Charge la configuration depuis le fichier JSON"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
        except FileNotFoundError:
            print(f"[ERROR] Fichier de configuration {self.config_file} non trouvé")
            self._config = {'servers': {}, 'global': {}}
        except json.JSONDecodeError as e:
            print(f"[ERROR] Erreur de parsing JSON: {e}")
            self._config = {'servers': {}, 'global': {}}
    
    def get_servers(self):
        """Retourne la liste des serveurs configurés"""
        return self._config.get('servers', {})
    
    def get_server(self, server_id):
        """Retourne la configuration d'un serveur spécifique"""
        return self._config.get('servers', {}).get(server_id)
    
    def is_valid_server(self, server_id):
        """Vérifie si un serveur existe dans la configuration"""
        return server_id in self._config.get('servers', {})
    
    def get_server_list(self):
        """Retourne la liste des IDs de serveurs"""
        return list(self._config.get('servers', {}).keys())
    
    def get_global_config(self):
        """Retourne la configuration globale"""
        return self._config.get('global', {})
    
    def save_config(self):
        """Sauvegarde la configuration dans le fichier JSON"""
        try:
            logger.debug(f"💾 Tentative de sauvegarde de {self.config_file}")
            
            # Vérifier que le fichier existe et est accessible
            file_path = os.path.abspath(self.config_file)
            logger.debug(f"📂 Chemin absolu: {file_path}")
            
            # Vérifier les permissions
            if os.path.exists(file_path):
                file_stats = os.stat(file_path)
                logger.debug(f"📋 Permissions: {oct(file_stats.st_mode)}, Owner UID: {file_stats.st_uid}")
            
            # Vérifier les permissions du dossier parent
            parent_dir = os.path.dirname(file_path)
            if os.path.exists(parent_dir):
                dir_stats = os.stat(parent_dir)
                logger.debug(f"📁 Dossier parent: {parent_dir}, Permissions: {oct(dir_stats.st_mode)}")
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Configuration sauvegardée avec succès: {self.config_file}")
        except PermissionError as e:
            logger.error(f"❌ Erreur de permissions lors de la sauvegarde: {e}")
            logger.error(f"🔐 Le processus actuel (UID: {os.getuid()}, GID: {os.getgid()}) n'a pas les droits d'écriture")
            logger.error(f"💡 Solution: sudo chown {os.getuid()}:{os.getgid()} {self.config_file}")
            print(f"[ERROR] Erreur de permissions: {e}")
        except OSError as e:
            logger.error(f"❌ Erreur système lors de la sauvegarde: {e}")
            if e.errno == 30:  # EROFS - Read-only file system
                logger.error("💿 Le système de fichiers est en lecture seule!")
                logger.error("💡 Solution: sudo mount -o remount,rw /")
            print(f"[ERROR] Erreur système: {e}")
        except Exception as e:
            logger.error(f"❌ Erreur inconnue lors de la sauvegarde: {e}")
            logger.exception(e)
            print(f"[ERROR] Erreur lors de la sauvegarde: {e}")
    
    def get_all_servers(self):
        """Retourne tous les serveurs avec leurs configurations"""
        return self._config.get('servers', {})
    
    def update_server_config(self, server_id, config_data):
        """Met à jour la configuration d'un serveur"""
        if 'servers' not in self._config:
            self._config['servers'] = {}
        
        if server_id not in self._config['servers']:
            raise ValueError(f"Serveur {server_id} non trouvé")
        
        # Mettre à jour la configuration
        self._config['servers'][server_id].update(config_data)
        
        # Sauvegarder dans le fichier
        self.save_config()
        
        return True
    
    def delete_server(self, server_id):
        """Supprime un serveur de la configuration"""
        if 'servers' not in self._config:
            return False
        
        if server_id in self._config['servers']:
            del self._config['servers'][server_id]
            self.save_config()
            return True
        
        return False
    
    def create_server(self, server_id, config_data):
        """Crée un nouveau serveur avec sa configuration"""
        if 'servers' not in self._config:
            self._config['servers'] = {}
        
        if server_id in self._config['servers']:
            raise ValueError(f"Le serveur {server_id} existe déjà")
        
        # Configuration par défaut pour un nouveau serveur
        default_config = {
            'display_name': config_data.get('display_name', server_id),
            'description': config_data.get('description', ''),
            'logo': config_data.get('logo', f'/static/logos/{server_id}.png'),
            'status': 'offline',
            'database_uri': config_data.get('database_uri', ''),
            'owner_id': config_data.get('owner_id', ''),  # ID Discord du propriétaire (pour les clients)
            'discord': {
                'client_id': config_data.get('discord', {}).get('client_id', ''),
                'client_secret': config_data.get('discord', {}).get('client_secret', ''),
                'bot_token': config_data.get('discord', {}).get('bot_token', ''),
                'guild_id': config_data.get('discord', {}).get('guild_id', ''),
                'role_id_staff': config_data.get('discord', {}).get('role_id_staff', ''),
                'role_id_admin': config_data.get('discord', {}).get('role_id_admin', ''),
                'channel_id': config_data.get('discord', {}).get('channel_id', '')
            },
            'api': {
                'tokens': config_data.get('api', {}).get('tokens', []),
                'allowed_ips': config_data.get('api', {}).get('allowed_ips', ['127.0.0.1'])
            },
            'db_accessible': False
        }
        
        # Ajouter le nouveau serveur
        self._config['servers'][server_id] = default_config
        
        # Sauvegarder dans le fichier
        self.save_config()
        
        return server_id


class SimpleCache:
    def __init__(self, ttl=300):
        self.cache = {}
        self.ttl = ttl
    
    def get(self, key):
        if key in self.cache:
            timestamp, value = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            else:
                # Cache expiré, supprimer l'entrée
                del self.cache[key]
        return None
    
    def set(self, key, value):
        """Met à jour le cache avec une nouvelle valeur"""
        self.cache[key] = (time.time(), value)
    
    def invalidate(self, key=None):
        """Invalide le cache pour une clé spécifique ou tout"""
        if key:
            self.cache.pop(key, None)
        else:
            self.cache.clear()
    
    def cleanup_expired(self):
        """Nettoie les entrées expirées du cache"""
        current_time = time.time()
        expired_keys = [
            key for key, (timestamp, _) in self.cache.items()
            if current_time - timestamp >= self.ttl
        ]
        for key in expired_keys:
            del self.cache[key]


class ServerCache:
    def __init__(self, ttl=300):
        self.cache = {}
        self.ttl = ttl
    
    def get(self, server_id, filters=None):
        cache_key = self._get_cache_key(server_id, filters)
        if cache_key in self.cache:
            timestamp, value = self.cache[cache_key]
            if time.time() - timestamp < self.ttl:
                return value
            else:
                del self.cache[cache_key]
        return None
    
    def set(self, server_id, value, filters=None):
        cache_key = self._get_cache_key(server_id, filters)
        self.cache[cache_key] = (time.time(), value)
    
    def _get_cache_key(self, server_id, filters):
        if filters:
            filter_str = '_'.join([f"{k}:{v}" for k, v in sorted(filters.items()) if v])
            return f"{server_id}_{filter_str}"
        return server_id
    
    def invalidate(self, server_id=None):
        if server_id:
            keys_to_remove = [key for key in self.cache.keys() if key.startswith(f"{server_id}_")]
            for key in keys_to_remove:
                del self.cache[key]
        else:
            self.cache.clear()
    
    def cleanup_expired(self):
        """Nettoie les entrées expirées du cache"""
        current_time = time.time()
        expired_keys = [
            key for key, (timestamp, _) in self.cache.items()
            if current_time - timestamp >= self.ttl
        ]
        for key in expired_keys:
            del self.cache[key]


def _normalize_db_uri(database_uri: str) -> str:
    """Normalise l'URI MySQL pour des drivers plus performants et compatibles."""
    if not database_uri:
        return database_uri
    # Essayez en priorité PyMySQL (souvent plus rapide que mysqlconnector sur Windows)
    if database_uri.startswith('mysql://'):
        return database_uri.replace('mysql://', 'mysql+pymysql://', 1)
    if database_uri.startswith('mariadb://'):
        return database_uri.replace('mariadb://', 'mysql+pymysql://', 1)
    return database_uri

def invalidate_server_db_cache(server_id: str):
    """Invalide le cache de connexion pour un serveur spécifique"""
    with _db_lock:
        # Fermer les connexions existantes si elles existent
        if server_id in server_db_connections:
            try:
                server_db_connections[server_id].dispose()
            except Exception:
                pass
            del server_db_connections[server_id]
        if server_id in server_db_sessions:
            del server_db_sessions[server_id]
        if server_id in server_db_uris:
            del server_db_uris[server_id]
        # Nettoyer aussi les variantes avec __mysqlconnector
        mysqlconnector_key = server_id + "__mysqlconnector"
        if mysqlconnector_key in server_db_connections:
            try:
                server_db_connections[mysqlconnector_key].dispose()
            except Exception:
                pass
            del server_db_connections[mysqlconnector_key]
        if mysqlconnector_key in server_db_sessions:
            del server_db_sessions[mysqlconnector_key]

def _get_or_create_engine_and_sessionmaker(server_id: str, database_uri: str):
    """Récupère un engine et un sessionmaker mis en cache par serveur."""
    # Vérifier si l'URI a changé et invalider le cache si nécessaire
    if server_id in server_db_uris and server_db_uris[server_id] != database_uri:
        print(f"[DEBUG] URI de base de données changée pour {server_id}, invalidation du cache")
        invalidate_server_db_cache(server_id)
    
    # Double-checked locking
    if server_id in server_db_connections and server_id in server_db_sessions:
        return server_db_connections[server_id], server_db_sessions[server_id]
    with _db_lock:
        if server_id in server_db_connections and server_id in server_db_sessions:
            return server_db_connections[server_id], server_db_sessions[server_id]
        # Créer l'engine avec un pooling optimisé pour haute performance
        engine = create_engine(
            database_uri,
            pool_size=20,  # Augmenté pour supporter plus de connexions simultanées
            max_overflow=40,  # Augmenté pour les pics de charge
            pool_timeout=10,
            pool_recycle=1800,
            pool_pre_ping=True,  # Vérifie les connexions avant utilisation
            echo=False,  # Désactiver les logs SQL en production
            connect_args={
                'connect_timeout': 10,
                'charset': 'utf8mb4',
                'use_unicode': True
            } if database_uri.startswith('mysql') else {}
        )
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        server_db_connections[server_id] = engine
        server_db_sessions[server_id] = SessionLocal
        server_db_uris[server_id] = database_uri  # Stocker l'URI utilisée
        return engine, SessionLocal

def get_server_database_session(server_id):
    """Obtient une session de base de données pour un serveur spécifique avec pooling et cache."""
    # Récupérer la configuration du serveur
    server_conf = server_config.get_server(server_id)
    if not server_conf:
        raise ValueError(f"Serveur {server_id} non trouvé")

    database_uri = server_conf.get('database_uri')
    if not database_uri:
        raise ValueError(f"URI de base de données non configurée pour le serveur {server_id}")

    database_uri = _normalize_db_uri(database_uri)

    try:
        engine, SessionLocal = _get_or_create_engine_and_sessionmaker(server_id, database_uri)
        session = SessionLocal()
        # Ping rapide
        session.execute(text('SELECT 1'))
        return session
    except Exception as e:
        # Fallback: essayer mysqlconnector si PyMySQL échoue
        if database_uri.startswith('mysql+pymysql://'):
            try:
                alt_uri = database_uri.replace('mysql+pymysql://', 'mysql+mysqlconnector://', 1)
                engine, SessionLocal = _get_or_create_engine_and_sessionmaker(server_id + "__mysqlconnector", alt_uri)
                session = SessionLocal()
                session.execute(text('SELECT 1'))
                # Miroir sous la clé canonique pour les prochains appels
                with _db_lock:
                    server_db_connections[server_id] = server_db_connections.get(server_id + "__mysqlconnector", engine)
                    server_db_sessions[server_id] = server_db_sessions.get(server_id + "__mysqlconnector", SessionLocal)
                return session
            except Exception:
                pass
        # Si c'est une erreur d'authentification, invalider le cache
        error_str = str(e).lower()
        if 'access denied' in error_str or 'authentication' in error_str or '1045' in error_str:
            print(f"[DEBUG] Erreur d'authentification détectée dans get_server_database_session, invalidation du cache pour {server_id}")
            invalidate_server_db_cache(server_id)
        print(f"[ERROR] Impossible de se connecter à la base de données du serveur {server_id}: {e}")
        raise


def _sanitize_like_input(value):
    """
    Échappe les caractères spéciaux SQL LIKE pour prévenir les injections.
    SÉCURITÉ: Cette fonction est critique pour la prévention des injections SQL.
    """
    if not value:
        return ''
    # Échapper les caractères spéciaux LIKE: %, _, \
    value = str(value)
    value = value.replace('\\', '\\\\')
    value = value.replace('%', '\\%')
    value = value.replace('_', '\\_')
    # Limiter la longueur pour prévenir les attaques par déni de service
    return value[:500]

def _apply_filters(session, query, filters):
    """
    Applique les filtres avec optimisation JSON_EXTRACT si disponible.
    SÉCURITÉ: Tous les filtres sont sanitisés pour prévenir les injections SQL.
    """
    if not filters:
        return query
    dialect = session.get_bind().dialect.name if session is not None else 'default'
    use_json_extract = dialect in ('mysql', 'mariadb')

    # SÉCURITÉ: Sanitiser tous les inputs avant utilisation dans les requêtes
    if filters.get('name'):
        safe_name = _sanitize_like_input(filters['name'])
        if use_json_extract:
            query = query.filter(func.json_extract(Log.data, '$.name').like(f"%{safe_name}%", escape='\\'))
        else:
            query = query.filter(Log.data.like(f'%"name":"%{safe_name}%"%', escape='\\'))
    
    if filters.get('idunique'):
        safe_idunique = _sanitize_like_input(filters['idunique'])
        if use_json_extract:
            query = query.filter(func.json_extract(Log.data, '$.idunique').like(f"%{safe_idunique}%", escape='\\'))
        else:
            query = query.filter(Log.data.like(f'%"idunique":%{safe_idunique}%', escape='\\'))
    
    if filters.get('message'):
        safe_message = _sanitize_like_input(filters['message'])
        if use_json_extract:
            query = query.filter(func.json_extract(Log.data, '$.logs_message').like(f"%{safe_message}%", escape='\\'))
        else:
            query = query.filter(Log.data.like(f'%"logs_message":"%{safe_message}%"%', escape='\\'))
    
    if filters.get('title'):
        safe_title = _sanitize_like_input(filters['title'])
        if use_json_extract:
            query = query.filter(func.json_extract(Log.data, '$.logs_title').like(f"%{safe_title}%", escape='\\'))
        else:
            query = query.filter(Log.data.like(f'%"logs_title":"%{safe_title}%"%', escape='\\'))
    
    if filters.get('author_id'):
        safe_author = _sanitize_like_input(filters['author_id'])
        if use_json_extract:
            query = query.filter(func.json_extract(Log.data, '$.discord_id').like(f"%{safe_author}%", escape='\\'))
        else:
            query = query.filter(Log.data.like(f'%"discord_id"%{safe_author}%', escape='\\'))
    
    # Filtres de date sur la colonne réelle
    date_start = filters.get('date_start')
    date_end = filters.get('date_end')
    if date_start:
        try:
            # Accepte ISO date (YYYY-MM-DD) ou ISO datetime
            dt = datetime.fromisoformat(str(date_start))
            query = query.filter(Log.date >= dt)
        except Exception:
            pass
    if date_end:
        try:
            dt = datetime.fromisoformat(str(date_end))
            query = query.filter(Log.date <= dt)
        except Exception:
            pass
    
    if filters.get('type'):
        # Le type est comparé directement, SQLAlchemy paramétrise automatiquement
        query = query.filter(Log.type == filters['type'])
    
    return query

def get_server_logs(server_id, page=1, filters=None, rows_per_page=10):
    """Récupère les logs d'un serveur spécifique depuis sa base de données avec optimisations."""
    session = None
    try:
        session = get_server_database_session(server_id)
        # Requête de base (utiliser Log complet pour compatibilité avec _apply_filters)
        base_query = session.query(Log)
        base_query = _apply_filters(session, base_query, filters)

        # Compter le total rapidement avec optimisation
        # Utiliser COUNT(*) au lieu de COUNT(id) pour de meilleures performances
        total_logs_query = session.query(func.count(Log.id))
        total_logs_query = _apply_filters(session, total_logs_query, filters)
        # Éviter tout ORDER BY dans le count
        total_logs = total_logs_query.order_by(None).scalar()

        # Récupérer les logs paginés avec index suggéré sur date
        # Note: Assurez-vous d'avoir un index sur la colonne date pour de meilleures performances
        # CREATE INDEX idx_logs_date ON vlogs(date DESC);
        logs = base_query.order_by(Log.date.desc()).offset((page - 1) * rows_per_page).limit(rows_per_page).all()

        # Parser les données JSON pour chaque log (utiliser parse_json_fast pour performance)
        for log in logs:
            log.parsed_data = parse_json_fast(log.data)
        
        return logs, total_logs
    except Exception as e:
        print(f"[ERROR] Erreur lors de la récupération des logs pour le serveur {server_id}: {e}")
        raise
    finally:
        if session:
            session.close()


def check_db_connection():
    try:
        db.session.execute(text('SELECT 1'))
        print("[DEBUG] Connexion à la base de données réussie!")
    except OperationalError as e:
        print("[DEBUG] Erreur de connexion à la base de données:", e)
    except Exception as e:
        print("[DEBUG] Erreur inconnue lors de la connexion à la base de données:", e)


def check_server_db_status(server_id, use_cache=True):
    """Vérifie si la base de données d'un serveur est accessible"""
    # Vérifier le cache d'abord si activé
    if use_cache:
        cached_status = status_cache.get(server_id)
        if cached_status is not None:
            return cached_status
    
    try:
        # Récupérer la configuration du serveur
        server_conf = server_config.get_server(server_id)
        if not server_conf:
            status = False
        else:
            database_uri = server_conf.get('database_uri')
            if not database_uri:
                status = False
            else:
                # Remplacer mysql:// par mysql+mysqlconnector:// pour utiliser mysql-connector-python
                if database_uri.startswith('mysql://'):
                    database_uri = database_uri.replace('mysql://', 'mysql+mysqlconnector://', 1)
                
                # Créer/utiliser une connexion temporaire via engine en cache
                database_uri = _normalize_db_uri(database_uri)
                engine, _ = _get_or_create_engine_and_sessionmaker(server_id, database_uri)
                with engine.connect() as connection:
                    # Tester la connexion et vérifier que la table vlogs existe
                    connection.execute(text('SELECT 1 FROM vlogs LIMIT 1'))
                
                status = True
    except Exception as e:
        print(f"[DEBUG] Erreur de connexion pour le serveur {server_id}: {e}")
        # Si c'est une erreur d'authentification, invalider le cache de connexion
        error_str = str(e).lower()
        if 'access denied' in error_str or 'authentication' in error_str or '1045' in error_str:
            print(f"[DEBUG] Erreur d'authentification détectée, invalidation du cache pour {server_id}")
            invalidate_server_db_cache(server_id)
            # Invalider aussi le cache de statut pour forcer une nouvelle vérification
            status_cache.invalidate(server_id)
        status = False
    
    # Mettre à jour le cache
    if use_cache:
        status_cache.set(server_id, status)
    
    return status


# Instance globale de la configuration des serveurs
server_config = ServerConfig()

# Cache pour les statuts de serveurs
status_cache = SimpleCache(ttl=30)  # Cache de 30 secondes pour les statuts

# Cache pour les types de logs par serveur
log_types_cache = ServerCache(ttl=300)  # Cache de 5 minutes

# Cache pour les statistiques de logs par serveur
log_stats_cache = ServerCache(ttl=60)  # Cache de 1 minute

# Cache pour les configurations de serveurs
server_config_cache = SimpleCache(ttl=300)  # Cache de 5 minutes

# Cache pour les rôles d'admin
admin_role_cache = SimpleCache(ttl=300)  # Cache de 5 minutes

# Cache pour les comptes par type de log
log_counts_cache = ServerCache(ttl=120)

def get_log_type_counts(server_id):
    """Retourne un dict {type: count} et la liste des types, optimisé en une seule requête."""
    # Cache par serveur
    cached = log_counts_cache.get(server_id)
    if cached is not None:
        return cached
    session = None
    try:
        session = get_server_database_session(server_id)
        # Optimisation : utiliser COUNT(*) au lieu de COUNT(id) et index suggéré sur type
        # Note: Assurez-vous d'avoir un index sur la colonne type pour de meilleures performances
        # CREATE INDEX idx_logs_type ON vlogs(type);
        rows = session.query(Log.type, func.count(Log.id)).filter(Log.type != None).group_by(Log.type).all()
        counts = {t: c for t, c in rows}
        types = list(counts.keys())
        result = {'counts': counts, 'types': types}
        log_counts_cache.set(server_id, result)
        return result
    except Exception as e:
        print(f"[ERROR] Erreur lors de la récupération des comptages par type pour {server_id}: {e}")
        return {'counts': {}, 'types': []}
    finally:
        if session:
            session.close()
