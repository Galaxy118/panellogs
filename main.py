from flask import Flask, redirect, request, url_for, render_template, jsonify, abort, make_response, Response, session, g
try:
    from flask_compress import Compress
    COMPRESS_AVAILABLE = True
except ImportError:
    COMPRESS_AVAILABLE = False
    print("[WARNING] flask-compress non installé. Installez-le avec: pip install flask-compress")

# Protection CSRF
try:
    from flask_wtf.csrf import CSRFProtect, generate_csrf
    CSRF_AVAILABLE = True
except ImportError:
    CSRF_AVAILABLE = False
    CSRFProtect = None
    generate_csrf = None
    print("[WARNING] flask-wtf non installé. Protection CSRF désactivée. Installez-le avec: pip install flask-wtf")

# Rate limiting pour protection contre les attaques
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    LIMITER_AVAILABLE = True
except ImportError:
    LIMITER_AVAILABLE = False
    Limiter = None
    print("[WARNING] flask-limiter non installé. Rate limiting désactivé. Installez-le avec: pip install flask-limiter")

from dotenv import load_dotenv
import os
import requests
import time
import json
import secrets
import ipaddress
from datetime import datetime, timezone, timedelta
import traceback
import re
from functools import wraps
import discord
from discord.ext import commands
import asyncio
import threading
import jwt
from urllib.parse import quote
from discord.errors import LoginFailure
import jinja2
from jinja2 import TemplateNotFound

from models import db, Log, check_db_connection, server_config, check_server_db_status, status_cache, log_types_cache, log_stats_cache, server_config_cache, admin_role_cache, get_server_logs, get_server_database_session, get_log_type_counts, log_counts_cache

# Décorateur pour protéger les routes avec JWT
def require_auth(server_id=None, admin_required=False):
    """Décorateur pour protéger les routes avec authentification JWT"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Récupérer le token JWT
            token = get_token_from_request()
            if not token:
                return redirect(url_for('login', server=server_id) if server_id else url_for('login'))
            
            # Vérifier le token
            payload = verify_jwt_token(token)
            if not payload:
                # Token invalide ou expiré
                response = make_response(redirect(url_for('login', server=server_id) if server_id else url_for('login')))
                response.set_cookie('auth_token', '', expires=0)
                return response
            
            # Vérifier les permissions pour un serveur spécifique
            if server_id:
                user_permissions = payload.get('server_permissions', {})
                
                # Vérifier si super admin
                if user_permissions.get('is_super_admin', False):
                    pass  # Super admin a accès à tout
                else:
                    # Vérifier l'accès au serveur
                    accessible_servers = user_permissions.get('accessible_servers', [])
                    if accessible_servers != 'all' and server_id not in accessible_servers:
                        abort(403)
                    
                    # Vérifier les permissions admin si requis
                    if admin_required:
                        admin_servers = user_permissions.get('admin_servers', [])
                        if admin_servers != 'all' and server_id not in admin_servers:
                            abort(403)
            
            # Ajouter les données utilisateur au contexte de la requête
            request.user_data = {
                'user_id': payload['user_id'],
                'username': payload['username'],
                'avatar': payload.get('avatar'),
                'discriminator': payload.get('discriminator', '0'),
                'permissions': payload.get('server_permissions', {})
            }
            # Ajouter l'URL de l'avatar
            request.user_data['avatar_url'] = get_discord_avatar_url(request.user_data)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# Cache pour les vérifications de rôles Discord
class DiscordRoleCache:
    def __init__(self, ttl=300):  # TTL de 5 minutes pour les rôles
        self.cache = {}
        self.ttl = ttl
    
    def get_key(self, user_id, server_id):
        return f"{user_id}_{server_id}"
    
    def get(self, user_id, server_id):
        key = self.get_key(user_id, server_id)
        if key in self.cache:
            timestamp, has_role = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return has_role
            else:
                del self.cache[key]
        return None
    
    def set(self, user_id, server_id, has_role):
        key = self.get_key(user_id, server_id)
        self.cache[key] = (time.time(), has_role)
    
    def invalidate(self, user_id=None, server_id=None):
        if user_id and server_id:
            key = self.get_key(user_id, server_id)
            self.cache.pop(key, None)
        else:
            self.cache.clear()

# Instance globale du cache Discord
discord_role_cache = DiscordRoleCache()

# Fonction centralisée pour obtenir le statut d'un serveur
def get_server_status(server_id, use_cache=True):
    """Fonction centralisée pour obtenir le statut d'un serveur de manière cohérente"""
    if use_cache:
        cached_status = status_cache.get(server_id)
        if cached_status is not None:
            return {
                'status': 'online' if cached_status else 'offline',
                'db_accessible': cached_status,
                'last_check': 'cached'
            }
    
    # Vérification en temps réel
    db_status = check_server_db_status(server_id, use_cache=use_cache)
    return {
        'status': 'online' if db_status else 'offline',
        'db_accessible': db_status,
        'last_check': datetime.now().isoformat()
    }

# Fonction pour obtenir tous les statuts de serveurs
def get_all_servers_status(use_cache=True):
    """Obtient le statut de tous les serveurs de manière cohérente"""
    servers = server_config.get_all_servers()
    status_data = {}
    
    for server_id, server_data in servers.items():
        server_status = get_server_status(server_id, use_cache)
        status_data[server_id] = {
            'display_name': server_data.get('display_name', server_id),
            'description': server_data.get('description', ''),
            **server_status
        }
    
    return status_data

# Load environment variables with a safe encoding fallback
try:
    load_dotenv()
except UnicodeDecodeError:
    # Fallback for .env files saved in legacy encodings (e.g., ISO-8859-1)
    try:
        load_dotenv(encoding='latin-1')
        print("[WARN] .env loaded using latin-1 encoding. Please convert the file to UTF-8.")
    except Exception as e:
        print(f"[ERROR] Failed to load .env due to encoding issues: {e}")

# Ensure Flask doesn't try to reload .env with UTF-8 later
os.environ.setdefault("FLASK_SKIP_DOTENV", "1")

app = Flask(__name__, static_folder='static', template_folder='static/html')

# SÉCURITÉ: Clé secrète Flask obligatoire en production
_flask_secret = os.getenv('FLASK_SECRET_KEY')
if not _flask_secret:
    _flask_secret = secrets.token_hex(32)
    print("[CRITICAL WARNING] FLASK_SECRET_KEY non définie! Une clé temporaire a été générée.")
    print("[CRITICAL WARNING] Définissez FLASK_SECRET_KEY dans votre fichier .env pour la production!")
app.config['SECRET_KEY'] = _flask_secret

# SÉCURITÉ: Configuration du cookie de session
app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS requis avec Cloudflare Tunnels
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'

# Configuration de compression pour améliorer les performances (optionnel)
if COMPRESS_AVAILABLE:
    Compress(app)
    print("[INFO] Compression HTTP activée")

# SÉCURITÉ: Protection CSRF
csrf = None
if CSRF_AVAILABLE:
    app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # Token valide 1 heure
    app.config['WTF_CSRF_SSL_STRICT'] = True
    app.config['WTF_CSRF_CHECK_DEFAULT'] = True
    csrf = CSRFProtect(app)
    print("[INFO] Protection CSRF activée")

def csrf_exempt_api(f):
    """Décorateur pour exempter une route de la vérification CSRF (pour les APIs avec tokens)."""
    if csrf:
        return csrf.exempt(f)
    return f

# SÉCURITÉ: Plages IP Cloudflare pour validation des proxies
# Source: https://www.cloudflare.com/ips/
CLOUDFLARE_IP_RANGES = [
    # IPv4
    '173.245.48.0/20', '103.21.244.0/22', '103.22.200.0/22', '103.31.4.0/22',
    '141.101.64.0/18', '108.162.192.0/18', '190.93.240.0/20', '188.114.96.0/20',
    '197.234.240.0/22', '198.41.128.0/17', '162.158.0.0/15', '104.16.0.0/13',
    '104.24.0.0/14', '172.64.0.0/13', '131.0.72.0/22',
    # IPv6
    '2400:cb00::/32', '2606:4700::/32', '2803:f800::/32', '2405:b500::/32',
    '2405:8100::/32', '2a06:98c0::/29', '2c0f:f248::/32'
]

def _parse_cloudflare_ranges():
    """Parse les plages IP Cloudflare une seule fois au démarrage."""
    ranges = []
    for cidr in CLOUDFLARE_IP_RANGES:
        try:
            ranges.append(ipaddress.ip_network(cidr))
        except ValueError:
            pass
    return ranges

CLOUDFLARE_NETWORKS = _parse_cloudflare_ranges()

def is_cloudflare_ip(ip_str):
    """Vérifie si une IP appartient à Cloudflare."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in network for network in CLOUDFLARE_NETWORKS)
    except ValueError:
        return False

# SÉCURITÉ: Rate limiting pour protéger contre les attaques par force brute
limiter = None

def get_real_ip_for_limiter():
    """Récupère l'IP réelle pour le rate limiter avec validation Cloudflare."""
    # Vérifier que la requête vient bien de Cloudflare
    remote_addr = request.remote_addr
    if is_cloudflare_ip(remote_addr):
        # Faire confiance au header CF-Connecting-IP
        cf_ip = request.headers.get('CF-Connecting-IP')
        if cf_ip:
            return cf_ip.strip()
    # Fallback sur remote_addr
    return remote_addr or '127.0.0.1'

if LIMITER_AVAILABLE:
    limiter = Limiter(
        key_func=get_real_ip_for_limiter,
        app=app,
        default_limits=["1000 per hour", "100 per minute"],
        storage_uri="memory://",
        strategy="fixed-window"
    )
    print("[INFO] Rate limiting activé")

def rate_limit(limit_string):
    """
    Décorateur de rate limiting conditionnel.
    Si flask-limiter n'est pas disponible, retourne un décorateur no-op.
    """
    def decorator(f):
        if limiter:
            return limiter.limit(limit_string)(f)
        return f
    return decorator

app.jinja_env.filters['loads'] = json.loads
app.jinja_env.add_extension('jinja2.ext.do')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URI")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Loader Jinja avec fallback d'encodage (UTF-8 puis latin-1)
class FallbackFileSystemLoader(jinja2.BaseLoader):
    def __init__(self, searchpath, encodings=("utf-8", "latin-1")):
        if isinstance(searchpath, str):
            self.searchpath = [searchpath]
        else:
            self.searchpath = list(searchpath)
        self.encodings = encodings

    def get_source(self, environment, template):
        import os as _os
        last_exc = None
        for base in self.searchpath:
            filename = _os.path.join(base, template)
            if not _os.path.isfile(filename):
                continue
            for enc in self.encodings:
                try:
                    with open(filename, "r", encoding=enc) as f:
                        source = f.read()
                    mtime = _os.path.getmtime(filename)
                    def uptodate():
                        try:
                            return _os.path.getmtime(filename) == mtime
                        except OSError:
                            return False
                    return source, filename, uptodate
                except UnicodeDecodeError as e:
                    last_exc = e
                    continue
                except OSError as e:
                    last_exc = e
                    continue
            # Le fichier existe mais n'a pas pu être lu avec les encodages fournis
            raise last_exc if last_exc else TemplateNotFound(template)
        # Aucun fichier correspondant trouvé dans les chemins de recherche
        raise TemplateNotFound(template)

# Activer le loader avec fallback pour les templates
app.jinja_loader = FallbackFileSystemLoader(app.template_folder)

# Configuration globale
SITE_NAME = os.getenv('GLOBAL_SITE_NAME', 'Multi-Server Logs Panel')

# Configuration Discord centralisée (uniquement depuis les variables d'environnement)
DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID')
DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
REDIRECT_URI = os.getenv('GLOBAL_REDIRECT_URI')

# Configuration JWT pour l'authentification stateless
# SÉCURITÉ: La clé JWT DOIT être définie dans .env - pas de fallback en production
_jwt_secret = os.getenv('JWT_SECRET_KEY')
if not _jwt_secret:
    import secrets
    _jwt_secret = secrets.token_hex(32)
    print("[CRITICAL WARNING] JWT_SECRET_KEY non définie! Une clé temporaire a été générée.")
    print("[CRITICAL WARNING] Définissez JWT_SECRET_KEY dans votre fichier .env pour la production!")
JWT_SECRET_KEY = _jwt_secret
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

# Configuration Cloudflare Turnstile
TURNSTILE_SITE_KEY = os.getenv('TURNSTILE_SITE_KEY')
TURNSTILE_SECRET_KEY = os.getenv('TURNSTILE_SECRET_KEY')
# Parser TURNSTILE_SESSION_TTL en gérant les commentaires inline
_turnstile_ttl_raw = os.getenv('TURNSTILE_SESSION_TTL', '600')
if '#' in _turnstile_ttl_raw:
    _turnstile_ttl_raw = _turnstile_ttl_raw.split('#')[0].strip()
try:
    TURNSTILE_SESSION_TTL = int(_turnstile_ttl_raw)
except ValueError:
    print(f"[WARNING] TURNSTILE_SESSION_TTL invalide, utilisation de 600s par défaut")
    TURNSTILE_SESSION_TTL = 600


# Configuration du bot Discord
bot_intents = discord.Intents.default()
bot_intents.members = True
bot_intents.guilds = True
bot = commands.Bot(command_prefix='!', intents=bot_intents)

# Gestion des SUPER ADMIN multiples
def _get_super_admin_ids():
    ids_raw = os.getenv('SUPER_ADMIN_DISCORD_IDS')
    if not ids_raw:
        return set()
    if isinstance(ids_raw, str):
        parts = re.split(r'[\s,]+', ids_raw.strip())
        return set(p for p in parts if p)
    return {str(ids_raw)}

def is_super_admin_id(user_id):
    return str(user_id) in _get_super_admin_ids()

# Validation et diagnostics de configuration Discord
import base64

def _decode_id_from_token(token):
    try:
        first = token.split('.')[0]
        # Ajout du padding base64 si nécessaire
        pad = '=' * ((4 - len(first) % 4) % 4)
        decoded = base64.b64decode(first + pad)
        return int(decoded)
    except Exception:
        return None

def validate_discord_config():
    issues = []
    # client_id
    if not DISCORD_CLIENT_ID or not DISCORD_CLIENT_ID.isdigit():
        issues.append("DISCORD_CLIENT_ID manquant ou invalide")
    # client_secret
    if not DISCORD_CLIENT_SECRET or len(DISCORD_CLIENT_SECRET.strip()) < 20:
        issues.append("DISCORD_CLIENT_SECRET manquant ou trop court")
    # redirect_uri
    if not REDIRECT_URI or not (REDIRECT_URI.startswith("http://") or REDIRECT_URI.startswith("https://")):
        issues.append("GLOBAL_REDIRECT_URI manquant ou invalide")
    # bot token
    if not DISCORD_BOT_TOKEN or DISCORD_BOT_TOKEN.count('.') != 2:
        issues.append("DISCORD_BOT_TOKEN manquant ou invalide (format)" )
    else:
        decoded_id = _decode_id_from_token(DISCORD_BOT_TOKEN)
        if decoded_id is None:
            issues.append("DISCORD_BOT_TOKEN illisible (base64)")
        elif DISCORD_CLIENT_ID and DISCORD_CLIENT_ID.isdigit():
            if str(decoded_id) != str(DISCORD_CLIENT_ID):
                issues.append("Le BOT token n'appartient pas à l'application DISCORD_CLIENT_ID")

    if issues:
        print("[WARNING] Problèmes de configuration Discord:")
        for i in issues:
            print(f" - {i}")
        print("[HINT] Vérifiez l'ID d'application, le secret OAuth2, le token du bot et l'URI de redirection dans le portail Discord.")
        return False
    return True

# Cache pour les informations des guildes Discord

# Fonctions utilitaires JWT
def create_jwt_token(user_data, server_permissions):
    """Crée un token JWT avec les données utilisateur et permissions"""
    now_utc = datetime.now(timezone.utc)
    payload = {
        'user_id': user_data['id'],
        'username': user_data['username'],
        'avatar': user_data.get('avatar'),
        'discriminator': user_data.get('discriminator', '0'),
        'server_permissions': server_permissions,
        'exp': now_utc + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': now_utc
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def verify_jwt_token(token):
    """Vérifie et décode un token JWT"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def is_turnstile_enabled():
    return bool(TURNSTILE_SITE_KEY and TURNSTILE_SECRET_KEY)

def get_real_ip():
    """
    Récupère l'IP réelle de l'utilisateur avec validation Cloudflare.
    
    SÉCURITÉ: On ne fait confiance aux headers X-Forwarded-For et CF-Connecting-IP
    que si la requête vient d'une IP Cloudflare connue, pour éviter le spoofing.
    """
    remote_addr = request.remote_addr or '127.0.0.1'
    
    # SÉCURITÉ: Vérifier que la requête vient bien de Cloudflare avant de faire
    # confiance aux headers de proxy
    if is_cloudflare_ip(remote_addr):
        # CF-Connecting-IP est le header le plus fiable de Cloudflare
        cf_ip = request.headers.get('CF-Connecting-IP')
        if cf_ip:
            return cf_ip.strip()
        
        # Fallback sur X-Forwarded-For (première IP)
        xff = request.headers.get('X-Forwarded-For')
        if xff:
            return xff.split(',')[0].strip()
    
    # En développement local ou si pas derrière Cloudflare
    # On peut utiliser X-Real-IP si nginx est configuré
    if remote_addr.startswith('127.') or remote_addr.startswith('10.') or remote_addr.startswith('192.168.'):
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip.strip()
        xff = request.headers.get('X-Forwarded-For')
        if xff:
            return xff.split(',')[0].strip()
    
    return remote_addr

def verify_turnstile_token(token, remote_ip=None):
    """Vérifie un jeton Turnstile via l'API Cloudflare"""
    if not is_turnstile_enabled():
        return True
    if not token:
        # SÉCURITÉ: Pas de log du token pour éviter les fuites
        return False
    try:
        payload = {
            'secret': TURNSTILE_SECRET_KEY,
            'response': token
        }
        # Ne pas envoyer l'IP si c'est une IP locale (proxy)
        if remote_ip and not remote_ip.startswith('127.') and not remote_ip.startswith('10.') and remote_ip != 'localhost':
            payload['remoteip'] = remote_ip
        
        response = requests.post(
            'https://challenges.cloudflare.com/turnstile/v0/siteverify',
            data=payload,
            timeout=10
        )
        data = response.json()
        
        # SÉCURITÉ: Log minimal sans données sensibles
        if not data.get('success'):
            error_codes = data.get('error-codes', [])
            # Filtrer les codes d'erreur pour le debug sans exposer de secrets
            app.logger.warning(f"Turnstile verification failed: {error_codes}")
            
        return data.get('success', False)
    except requests.exceptions.Timeout:
        app.logger.error("Turnstile timeout - API Cloudflare non accessible")
        return False
    except Exception as e:
        app.logger.error(f"Erreur Turnstile: {type(e).__name__}")
        return False

def is_turnstile_session_valid():
    """Vérifie si une validation Turnstile récente est stockée en session"""
    if not is_turnstile_enabled():
        return True
    verified_at = session.get('turnstile_verified_at')
    if not verified_at:
        return False
    if time.time() - verified_at > TURNSTILE_SESSION_TTL:
        session.pop('turnstile_verified_at', None)
        session.pop('turnstile_action', None)
        session.pop('turnstile_server', None)
        return False
    return True

def mark_turnstile_verified(action=None, server_id=None):
    """Enregistre la validation Turnstile dans la session utilisateur"""
    if not is_turnstile_enabled():
        return
    session['turnstile_verified_at'] = time.time()
    if action:
        session['turnstile_action'] = action
    if server_id:
        session['turnstile_server'] = server_id

def get_token_from_request():
    """Récupère le token JWT depuis les cookies ou headers"""
    # Essayer depuis les cookies
    token = request.cookies.get('auth_token')
    if token:
        return token
    
    # Essayer depuis les headers Authorization
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header.split(' ')[1]
    
    return None

def get_discord_avatar_url(user_data):
    """Génère l'URL de l'avatar Discord de l'utilisateur"""
    if not user_data:
        return None
    
    user_id = user_data.get('user_id')
    avatar = user_data.get('avatar')
    discriminator = user_data.get('discriminator', '0')
    
    if avatar and user_id:
        return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}.png?size=64"
    else:
        # Avatar par défaut basé sur le discriminator
        try:
            disc_int = int(discriminator) % 5
        except (ValueError, TypeError):
            disc_int = 0
        return f"https://cdn.discordapp.com/embed/avatars/{disc_int}.png"

def sync_firewall_rules():
    """
    Synchronise automatiquement les règles UFW avec les serveurs MySQL configurés.
    Appelé après chaque création/modification/suppression de serveur.
    """
    try:
        import subprocess
        import re
        
        # Chemin du fichier de configuration
        config_file = os.path.join(os.path.dirname(__file__), 'servers_config.json')
        
        if not os.path.exists(config_file):
            return
        
        # Charger la configuration
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        servers = config.get('servers', {})
        db_hosts = set()
        
        # Pattern pour parser les URIs MySQL
        pattern = r'mysql(?:\+\w+)?://[^@]+@([^:/]+):(\d+)/'
        
        # Extraire tous les hôtes:ports MySQL
        for server_name, server_config in servers.items():
            db_uri = server_config.get('database_uri', '')
            
            if not db_uri or db_uri.startswith('sqlite'):
                continue
            
            match = re.search(pattern, db_uri)
            if match:
                host = match.group(1)
                port = match.group(2)
                db_hosts.add(f"{host}:{port}")
        
        # Obtenir les règles UFW actuelles pour MySQL
        try:
            result = subprocess.run(
                ['ufw', 'status', 'numbered'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                # UFW non installé ou non activé, ignorer silencieusement
                return
            
            current_rules = result.stdout
            
            # Ajouter les règles manquantes
            for host_port in db_hosts:
                host, port = host_port.split(':')
                
                # Vérifier si la règle existe déjà
                if f'{port}/tcp' in current_rules and 'ALLOW OUT' in current_rules:
                    continue
                
                # Ajouter la règle UFW (silencieusement, sans interaction)
                subprocess.run(
                    ['ufw', 'allow', 'out', 'to', 'any', 'port', port, 'proto', 'tcp', 
                     'comment', f'MySQL {host}'],
                    capture_output=True,
                    timeout=5
                )
            
            # Recharger UFW
            subprocess.run(['ufw', 'reload'], capture_output=True, timeout=5)
            
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            # Erreur silencieuse - ne pas bloquer l'application
            pass
            
    except Exception as e:
        # Log l'erreur mais ne pas propager
        app.logger.warning(f"Erreur lors de la synchronisation firewall: {e}")

# Fonctions de vérification des rôles Discord
async def check_discord_role_async(user_id, server_id, required_role='staff'):
    """Vérifie les rôles Discord de manière asynchrone"""
    try:
        server_conf = get_server_config(server_id)
        if not server_conf:
            return False
        
        discord_config = server_conf.get('discord', {})
        guild_id = discord_config.get('guild_id')
        
        if required_role == 'admin':
            role_id = discord_config.get('role_id_admin')
        else:
            role_id = discord_config.get('role_id_staff')
        
        if not guild_id or not role_id:
            return False
        
        guild = bot.get_guild(int(guild_id))
        if not guild:
            return False
        
        member = guild.get_member(int(user_id))
        if not member:
            return False
        
        target_role = guild.get_role(int(role_id))
        if not target_role:
            return False
        
        return target_role in member.roles
    except Exception as e:
        print(f"[ERROR] Erreur lors de la vérification du rôle Discord: {e}")
        return False

def get_discord_member_roles(server_conf, user_id):
    """Retourne la liste des rôles Discord (IDs) pour un utilisateur sur un serveur donné."""
    if not server_conf:
        return []
    
    discord_config = server_conf.get('discord', {})
    guild_id = discord_config.get('guild_id')
    
    if not guild_id or not DISCORD_BOT_TOKEN:
        return []
    
    # Essayer via le bot Discord s'il est connecté
    try:
        if bot and bot.is_ready():
            guild = bot.get_guild(int(guild_id))
            if guild:
                member = guild.get_member(int(user_id))
                if member and getattr(member, 'roles', None):
                    return [str(role.id) for role in member.roles if hasattr(role, 'id')]
    except Exception as e:
        print(f"[DEBUG] Erreur lors de la vérification des rôles via bot pour {guild_id}: {e}")
    
    # Fallback via l'API HTTP Discord
    try:
        url = f"https://discord.com/api/guilds/{guild_id}/members/{user_id}"
        headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
        res = requests.get(url, headers=headers, timeout=10)
        
        if res.status_code == 200:
            member = res.json()
            return [str(role_id) for role_id in member.get('roles', [])]
        elif res.status_code == 404:
            return []
        else:
            print(f"[WARNING] Discord API a renvoyé {res.status_code} pour guild {guild_id} / user {user_id}")
    except Exception as e:
        print(f"[ERROR] Erreur lors de la récupération des rôles Discord via API: {e}")
    
    return []


def check_discord_role_sync(user_id, server_id, required_role='staff'):
    """Vérification hybride (bot + API HTTP) des rôles Discord"""
    try:
        server_conf = get_server_config(server_id)
        roles = get_discord_member_roles(server_conf, user_id)
        if not roles:
            return False
        
        discord_config = server_conf.get('discord', {}) if server_conf else {}
        target_role = discord_config.get('role_id_admin') if required_role == 'admin' else discord_config.get('role_id_staff')
        if not target_role:
            return False
        
        return str(target_role) in roles
    except Exception as e:
        print(f"[ERROR] Erreur dans check_discord_role_sync: {e}")
        return False

def get_user_server_permissions(user_id):
    """Récupère les permissions de l'utilisateur pour tous les serveurs"""
    permissions = {
        'accessible_servers': [],
        'admin_servers': [],
        'is_super_admin': False
    }
    
    # Vérifier si super admin
    if is_super_admin_id(user_id):
        permissions['is_super_admin'] = True
        permissions['accessible_servers'] = 'all'
        permissions['admin_servers'] = 'all'
        return permissions
    
    # Vérifier les permissions pour chaque serveur
    for server_id in server_config.get_server_list():
        server_conf = get_server_config(server_id)
        if not server_conf:
            continue
        
        roles = get_discord_member_roles(server_conf, user_id)
        if not roles:
            continue
        
        discord_config = server_conf.get('discord', {})
        staff_role = str(discord_config.get('role_id_staff', '') or '')
        admin_role = str(discord_config.get('role_id_admin', '') or '')
        
        if staff_role and staff_role in roles:
            permissions['accessible_servers'].append(server_id)
        
        if admin_role and admin_role in roles:
            permissions['admin_servers'].append(server_id)
    
    return permissions
guild_cache = {}
last_guild_update = 0
GUILD_CACHE_TTL = 300  # 5 minutes

# Cache pour les icônes Discord (TTL plus long car elles changent rarement)
discord_icon_cache = {}
DISCORD_ICON_CACHE_TTL = 3600  # 1 heure
ASSET_VERSION = os.getenv('ASSET_VERSION', str(int(time.time())))

# Fonctions pour la gestion des rôles Discord
def get_discord_servers_config():
    """Récupère la configuration des serveurs Discord depuis servers_config.json"""
    try:
        with open('servers_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config.get('discord_servers', {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def update_guild_cache():
    """Met à jour le cache des guildes Discord"""
    global guild_cache, last_guild_update
    current_time = time.time()
    
    if current_time - last_guild_update < GUILD_CACHE_TTL:
        return guild_cache
    
    try:
        # Récupérer les guildes depuis la configuration
        discord_servers = get_discord_servers_config()
        guild_cache = discord_servers
        last_guild_update = current_time
    except Exception as e:
        print(f"Erreur lors de la mise à jour du cache des guildes: {e}")
    
    return guild_cache

async def check_user_role_in_guild(user_id, guild_id, role_id):
    """Vérifie si un utilisateur a un rôle spécifique dans une guilde"""
    try:
        if not bot.is_ready():
            return False
            
        guild = bot.get_guild(int(guild_id))
        if not guild:
            return False
            
        member = guild.get_member(int(user_id))
        if not member:
            return False
            
        role = guild.get_role(int(role_id))
        if not role:
            return False
            
        return role in member.roles
    except Exception as e:
        print(f"Erreur lors de la vérification du rôle: {e}")
        return False

def check_user_permissions(user_id, requested_servers=None):
    """Vérifie les permissions d'un utilisateur pour les serveurs demandés"""
    # Vérifier si c'est le SUPER_ADMIN
    if is_super_admin_id(user_id):
        return {
            'is_super_admin': True,
            'accessible_servers': 'all',
            'admin_servers': 'all'
        }
    
    # Mettre à jour le cache des guildes
    discord_servers = update_guild_cache()
    accessible_servers = []
    admin_servers = []
    
    # Vérifier les permissions pour chaque serveur Discord configuré
    for guild_id, guild_config in discord_servers.items():
        if not guild_config.get('enabled', True):
            continue
            
        try:
            # Vérifier les rôles de manière synchrone (à améliorer avec async)
            user_role_id = guild_config.get('user_role_id')
            admin_role_id = guild_config.get('admin_role_id')
            log_servers = guild_config.get('log_servers', [])
            
            # Pour l'instant, on utilise une vérification simplifiée
            # En production, il faudrait utiliser les appels async au bot
            
            # Si l'utilisateur a accès à ce serveur Discord, il a accès aux serveurs de logs associés
            if requested_servers:
                for server in requested_servers:
                    if server in log_servers:
                        accessible_servers.extend(log_servers)
                        # Si admin role, ajouter aux serveurs admin
                        admin_servers.extend(log_servers)
                        
        except Exception as e:
            print(f"Erreur lors de la vérification des permissions pour {guild_id}: {e}")
            continue
    
    return {
        'is_super_admin': False,
        'accessible_servers': list(set(accessible_servers)),
        'admin_servers': list(set(admin_servers))
    }

# Fonctions utilitaires pour la configuration par serveur
def get_server_config(server_id):
    """Retourne la configuration d'un serveur avec cache"""
    # Vérifier le cache d'abord
    cached_config = server_config_cache.get(server_id)
    if cached_config is not None:
        return cached_config
    
    # Récupérer depuis la source et mettre en cache
    config = server_config.get_server(server_id)
    if config:
        server_config_cache.set(server_id, config)
    return config

def get_discord_config(server_id):
    """Retourne la configuration Discord d'un serveur avec cache"""
    server_conf = get_server_config(server_id)
    return server_conf.get('discord', {}) if server_conf else {}

def get_api_config(server_id):
    """Retourne la configuration API d'un serveur"""
    server_conf = get_server_config(server_id)
    return server_conf.get('api', {}) if server_conf else {}

def get_discord_guild_icon(server_id):
    """Récupère l'icône du serveur Discord via l'API Discord avec cache optimisé"""
    # Vérifier le cache d'abord
    if server_id in discord_icon_cache:
        timestamp, icon_url = discord_icon_cache[server_id]
        if time.time() - timestamp < DISCORD_ICON_CACHE_TTL:
            return icon_url
        else:
            del discord_icon_cache[server_id]
    
    try:
        discord_config = get_discord_config(server_id)
        guild_id = discord_config.get('guild_id')
        
        if not guild_id or not DISCORD_BOT_TOKEN:
            return None
        
        # Utiliser l'API Discord pour récupérer les informations de la guilde
        url = f"https://discord.com/api/guilds/{guild_id}"
        headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
        
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            guild_data = response.json()
            icon_hash = guild_data.get('icon')
            
            if icon_hash:
                # Construire l'URL de l'icône Discord
                # Format: https://cdn.discordapp.com/icons/{guild_id}/{icon_hash}.png
                # On peut aussi utiliser .webp ou .gif selon le format original
                icon_url = f"https://cdn.discordapp.com/icons/{guild_id}/{icon_hash}.png?size=256"
                # Mettre en cache
                discord_icon_cache[server_id] = (time.time(), icon_url)
                return icon_url
        
        return None
    except Exception as e:
        print(f"[ERROR] Erreur lors de la récupération du logo Discord pour {server_id}: {e}")
        return None

def send_discord_log(server_id, message, embed=None):
    """Envoie un message de log dans le salon Discord configuré pour le serveur"""
    try:
        if not DISCORD_BOT_TOKEN:
            return False
        
        server_conf = server_config.get_server(server_id)
        if not server_conf:
            return False
        
        discord_config = server_conf.get('discord', {})
        channel_id = discord_config.get('channel_id')
        
        if not channel_id:
            return False
        
        # Utiliser l'API HTTP Discord pour envoyer le message
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        headers = {
            "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
            "Content-Type": "application/json"
        }
        
        payload = {"content": message}
        if embed:
            payload["embeds"] = [{
                "title": embed.get('title', ''),
                "description": embed.get('description', ''),
                "color": embed.get('color', 0x8D12AB),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "fields": embed.get('fields', [])
            }]
        
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        return response.status_code == 200
    except Exception as e:
        print(f"[ERROR] Erreur lors de l'envoi du log Discord pour {server_id}: {e}")
        return False




def safe_loads(s):
    try:
        return json.loads(s)
    except Exception:
        return None

app.jinja_env.filters['safe_loads'] = safe_loads

@app.context_processor
def inject_global_context():
    context = {'ASSET_VERSION': ASSET_VERSION}
    # Ajouter csrf_token si disponible
    if CSRF_AVAILABLE and generate_csrf:
        context['csrf_token'] = generate_csrf
    return context







@app.template_filter('mask_access_token')
def mask_access_token(session_str):
    try:
        data = json.loads(session_str)
        if 'access_token' in data:
            data['access_token'] = '***CENSORED***'
        return json.dumps(data, indent=2)
    except Exception:
        # Si ce n'est pas JSON, retourne brut
        return session_str

@app.before_request
def check_ip_whitelist():
    if request.path.startswith('/api/'):
        # Exception spéciale pour /api/servers/status - toujours accessible
        if request.path == '/api/servers/status':
            return  # Autoriser l'accès à tous pour cette route
        
        # Vérifier l'IP pour tous les serveurs configurés
        ip = request.remote_addr
        allowed = False
        servers = server_config.get_servers()
        
        # Si aucun serveur n'est configuré, autoriser l'accès (pour éviter le 403)
        if not servers:
            return
            
        for server_id, server_conf in servers.items():
            api_conf = server_conf.get('api', {})
            allowed_ips = api_conf.get('allowed_ips', [])
            if ip in allowed_ips:
                allowed = True
                break
        
        if not allowed:
            return jsonify({"error": "Unauthorized IP"}), 403


# SÉCURITÉ: Limites pour les données d'entrée de l'API
MAX_LOG_TYPE_LENGTH = 100
MAX_LOG_MESSAGE_LENGTH = 10000
MAX_LOG_NAME_LENGTH = 500
MAX_LOG_TITLE_LENGTH = 500
MAX_IDUNIQUE_LENGTH = 100

def sanitize_string(value, max_length, default=''):
    """Sanitise et tronque une chaîne de caractères."""
    if value is None:
        return default
    if not isinstance(value, str):
        value = str(value)
    # Supprimer les caractères de contrôle dangereux
    value = ''.join(char for char in value if ord(char) >= 32 or char in '\n\r\t')
    return value[:max_length]

# SÉCURITÉ: Route API exemptée de CSRF (utilise des tokens d'authentification)
@app.route('/api/logs', methods=['POST'])
@app.route('/api/logs/<server_id>', methods=['POST'])
@csrf_exempt_api
@rate_limit("100 per minute")
def add_log(server_id=None):
    token = request.headers.get('Authorization')
    
    # Si aucun server_id dans l'URL, essayer de le récupérer depuis les données
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400
    
    # SÉCURITÉ: Valider le server_id
    if not server_id:
        server_id = data.get('server_id', 'default')
    
    # Validation stricte du server_id (alphanumeric + underscore seulement)
    if not server_id or not re.match(r'^[a-zA-Z0-9_-]+$', server_id):
        return jsonify({"error": "Invalid server_id format"}), 400
    
    if not server_config.is_valid_server(server_id):
        return jsonify({"error": "Unknown server"}), 400
    
    # Vérifier le token pour ce serveur
    api_conf = get_api_config(server_id)
    valid_tokens = api_conf.get('tokens', [])
    
    # SÉCURITÉ: Comparaison en temps constant pour éviter les attaques timing
    token_valid = False
    for valid_token in valid_tokens:
        if secrets.compare_digest(str(token or ''), str(valid_token)):
            token_valid = True
            break
    
    if not token_valid:
        return jsonify({"error": "Invalid token"}), 401

    # Utiliser la session de base de données spécifique au serveur
    session = None
    try:
        # SÉCURITÉ: Extraire et valider le type
        log_type = data.get('type')
        if not log_type:
            return jsonify({"error": "Missing 'type' field"}), 400
        log_type = sanitize_string(log_type, MAX_LOG_TYPE_LENGTH)
        
        # SÉCURITÉ: Préparer les données JSON avec sanitisation
        log_data = {
            "logs_message": sanitize_string(data.get('message'), MAX_LOG_MESSAGE_LENGTH),
            "name": sanitize_string(data.get('name'), MAX_LOG_NAME_LENGTH),
            "logs_title": sanitize_string(data.get('title', 'Logs'), MAX_LOG_TITLE_LENGTH),
            "idunique": sanitize_string(data.get('idunique'), MAX_IDUNIQUE_LENGTH) if data.get('idunique') else None
        }
        
        # Ajouter des champs spécifiques selon le type (avec sanitisation)
        if 'name_cible' in data:
            log_data['name_cible'] = sanitize_string(data['name_cible'], MAX_LOG_NAME_LENGTH)
        if 'idunique_cible' in data:
            log_data['idunique_cible'] = sanitize_string(data['idunique_cible'], MAX_IDUNIQUE_LENGTH)
        
        # Valider et parser la date
        log_date = datetime.now()
        if data.get('date'):
            try:
                log_date = datetime.strptime(str(data.get('date'))[:19], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass  # Utiliser la date actuelle si format invalide
        
        # Créer le log
        log = Log(
            type=log_type,
            data=json.dumps(log_data, ensure_ascii=False),
            date=log_date
        )
        
        # Obtenir la session de base de données spécifique au serveur
        session = get_server_database_session(server_id)
        session.add(log)
        session.commit()
        
        # Récupérer l'ID du log avant de fermer la session
        log_id = log.id
        
        # Invalider les caches pour ce serveur
        log_types_cache.invalidate(server_id)
        log_stats_cache.invalidate(server_id)
        log_counts_cache.invalidate(server_id)
        
        return jsonify({"success": True, "id": log_id, "server": server_id}), 201
    except Exception as e:
        app.logger.error(f"Erreur ajout log {server_id}: {type(e).__name__}")
        if session:
            session.rollback()
        return jsonify({"error": "Internal server error"}), 500
    finally:
        if session:
            session.close()


@app.after_request
def add_security_headers(response):
    """
    SÉCURITÉ: Ajoute les headers de sécurité à toutes les réponses.
    Ces headers protègent contre XSS, clickjacking, et autres attaques.
    """
    # Protection contre le clickjacking
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    
    # Empêcher le sniffing MIME
    response.headers['X-Content-Type-Options'] = 'nosniff'
    
    # Protection XSS (navigateurs anciens)
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # Politique de référent
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    # Permissions Policy (remplace Feature-Policy)
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=(), payment=()'
    
    # Content-Security-Policy
    # Note: Ajustez selon vos besoins (CDNs utilisés, etc.)
    csp_directives = [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://challenges.cloudflare.com",
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com",
        "img-src 'self' data: https://cdn.discordapp.com https://discord.com",
        "connect-src 'self' https://challenges.cloudflare.com",
        "frame-src https://challenges.cloudflare.com",
        "form-action 'self' https://discord.com",
        "base-uri 'self'",
        "object-src 'none'"
    ]
    response.headers['Content-Security-Policy'] = "; ".join(csp_directives)
    
    # Ajouter le token CSRF au contexte pour les templates si disponible
    if CSRF_AVAILABLE and generate_csrf:
        try:
            response.headers['X-CSRF-Token'] = generate_csrf()
        except Exception:
            pass
    
    return response

@app.before_request
def before_request():
    """Hook exécuté avant chaque requête avec optimisations"""
    # Stocker l'IP réelle dans g pour utilisation ultérieure
    g.real_ip = get_real_ip()
    
    # Nettoyer périodiquement les caches expirés (toutes les 50 requêtes environ)
    import random
    if random.randint(1, 50) == 1:
        status_cache.cleanup_expired()
        log_types_cache.cleanup_expired() if hasattr(log_types_cache, 'cleanup_expired') else None
        log_stats_cache.cleanup_expired() if hasattr(log_stats_cache, 'cleanup_expired') else None
        server_config_cache.cleanup_expired()
        admin_role_cache.cleanup_expired()
        log_counts_cache.cleanup_expired() if hasattr(log_counts_cache, 'cleanup_expired') else None
        # Nettoyer le cache des icônes Discord expirées
        current_time = time.time()
        expired_icons = [k for k, (ts, _) in discord_icon_cache.items() if current_time - ts >= DISCORD_ICON_CACHE_TTL]
        for key in expired_icons:
            discord_icon_cache.pop(key, None)


def check_role_http(user_id, server_id=None, use_cache=True):
    """Vérifie si un utilisateur a le rôle user pour un serveur donné via le système centralisé"""
    # Vérifier si c'est le SUPER_ADMIN
    if is_super_admin_id(user_id):
        return True
    
    if not server_id:
        server_id = session.get('selected_server')
    
    if not server_id or not server_config.is_valid_server(server_id):
        return False
    
    # Vérifier le cache d'abord si activé
    if use_cache:
        cached_result = discord_role_cache.get(user_id, server_id)
        if cached_result is not None:
            return cached_result
    
    # Utiliser le nouveau système centralisé
    discord_servers = get_discord_servers_config()
    result = False
    
    # Vérifier dans tous les serveurs Discord configurés
    for guild_id, guild_config in discord_servers.items():
        if not guild_config.get('enabled', True):
            continue
            
        log_servers = guild_config.get('log_servers', [])
        if server_id in log_servers:
            # Ce serveur de logs est associé à ce serveur Discord
            try:
                user_role_id = guild_config.get('user_role_id')
                if user_role_id:
                    # Vérifier le rôle via l'API Discord
                    url = f"https://discord.com/api/guilds/{guild_id}/members/{user_id}"
                    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
                    res = requests.get(url, headers=headers, timeout=10)
                    
                    if res.status_code == 200:
                        member = res.json()
                        roles = member.get('roles', [])
                        if user_role_id in roles:
                            result = True
                            break
            except Exception as e:
                print(f"[DEBUG] Erreur lors de la vérification des rôles Discord pour {guild_id}: {e}")
                continue
    
    # Mettre à jour le cache
    if use_cache:
        discord_role_cache.set(user_id, server_id, result)
    
    return result


def is_admin(user_id, server_id=None):
    """Vérifie si un utilisateur a le rôle admin pour un serveur donné via le système centralisé"""
    # Vérifier si l'utilisateur est super-admin
    if is_super_admin_id(user_id):
        return True
    
    if not server_id:
        server_id = session.get('selected_server')
    
    if not server_id or not server_config.is_valid_server(server_id):
        return False
    
    # Vérifier le cache d'abord
    cached_result = admin_role_cache.get(user_id, server_id)
    if cached_result is not None:
        return cached_result
    
    # Utiliser le nouveau système centralisé
    discord_servers = get_discord_servers_config()
    is_admin_user = False
    
    # Vérifier dans tous les serveurs Discord configurés
    for guild_id, guild_config in discord_servers.items():
        if not guild_config.get('enabled', True):
            continue
            
        log_servers = guild_config.get('log_servers', [])
        if server_id in log_servers:
            # Ce serveur de logs est associé à ce serveur Discord
            try:
                admin_role_id = guild_config.get('admin_role_id')
                if admin_role_id:
                    # Vérifier le rôle via l'API Discord
                    url = f"https://discord.com/api/guilds/{guild_id}/members/{user_id}"
                    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
                    res = requests.get(url, headers=headers, timeout=10)
                    
                    if res.status_code == 200:
                        member = res.json()
                        roles = member.get('roles', [])
                        if admin_role_id in roles:
                            is_admin_user = True
                            break
            except Exception as e:
                print(f"[DEBUG] Erreur lors de la vérification des rôles admin Discord pour {guild_id}: {e}")
                continue
    
    # Mettre en cache le résultat
    admin_role_cache.set(user_id, server_id, is_admin_user)
    return is_admin_user


@app.route('/admin_panel')
@require_auth(admin_required=True)
def admin_panel():
    """Panel d'administration pour les logs de session (désactivé car plus de sessions)"""
    # Cette route est maintenant obsolète car nous n'utilisons plus de sessions
    # Rediriger vers l'administration des serveurs
    return redirect(url_for('admin_servers'))





def parse_int_env(name, default):
    """Parse une variable d'environnement en int, en ignorant les commentaires inline"""
    value = os.getenv(name, str(default))
    # Supprimer les commentaires inline (tout après #)
    if '#' in value:
        value = value.split('#')[0].strip()
    try:
        return int(value)
    except ValueError:
        print(f"[WARNING] Variable {name} invalide: '{value}', utilisation de la valeur par défaut: {default}")
        return default

def is_entry_captcha_valid():
    """Vérifie si le captcha d'entrée a été validé dans la session"""
    if not is_turnstile_enabled():
        return True
    verified_at = session.get('entry_captcha_verified_at')
    if not verified_at:
        return False
    # Le captcha d'entrée est valide pendant 24 heures (ou jusqu'à fermeture du navigateur)
    entry_captcha_ttl = parse_int_env('ENTRY_CAPTCHA_TTL', 86400)  # 24h par défaut
    if time.time() - verified_at > entry_captcha_ttl:
        session.pop('entry_captcha_verified_at', None)
        return False
    return True

def mark_entry_captcha_verified():
    """Marque le captcha d'entrée comme validé dans la session"""
    session['entry_captcha_verified_at'] = time.time()

@app.route('/captcha')
def captcha_page():
    """Page de captcha d'entrée - première page du site"""
    # Si le captcha n'est pas activé, rediriger directement vers l'index
    if not is_turnstile_enabled():
        return redirect(url_for('index'))
    
    # Si le captcha est déjà validé, rediriger vers l'index
    if is_entry_captcha_valid():
        return redirect(url_for('index'))
    
    return render_template('captcha.html',
                         site_name=SITE_NAME,
                         turnstile_site_key=TURNSTILE_SITE_KEY)

@app.route('/api/turnstile/debug')
def turnstile_debug():
    """Route de debug pour vérifier la configuration Turnstile (SUPER_ADMIN uniquement)"""
    # Vérifier si l'utilisateur est super admin
    token = get_token_from_request()
    if token:
        payload = verify_jwt_token(token)
        if payload:
            permissions = payload.get('server_permissions', {})
            if permissions.get('is_super_admin', False):
                return jsonify({
                    'enabled': is_turnstile_enabled(),
                    'site_key_configured': bool(TURNSTILE_SITE_KEY),
                    'site_key_preview': TURNSTILE_SITE_KEY[:10] + '...' if TURNSTILE_SITE_KEY and len(TURNSTILE_SITE_KEY) > 10 else 'N/A',
                    'secret_key_configured': bool(TURNSTILE_SECRET_KEY),
                    'secret_key_length': len(TURNSTILE_SECRET_KEY) if TURNSTILE_SECRET_KEY else 0,
                    'session_ttl': TURNSTILE_SESSION_TTL,
                    'your_ip': get_real_ip(),
                    'remote_addr': request.remote_addr,
                    'x_forwarded_for': request.headers.get('X-Forwarded-For'),
                    'x_real_ip': request.headers.get('X-Real-IP'),
                    'cf_connecting_ip': request.headers.get('CF-Connecting-IP'),
                    'entry_captcha_valid': is_entry_captcha_valid()
                })
    
    return jsonify({'error': 'Unauthorized - Super Admin only'}), 403

# SÉCURITÉ: Rate limiting sur la vérification captcha
# Exempt de CSRF car protégé par Turnstile
@app.route('/captcha/verify', methods=['POST'])
@csrf_exempt_api
@rate_limit("30 per minute")
def verify_turnstile_entry():
    """Endpoint pour vérifier le captcha d'entrée du site"""
    if not is_turnstile_enabled():
        return jsonify({'success': True})
    
    data = request.get_json(silent=True) or {}
    token = data.get('token')
    
    if not token:
        return jsonify({'success': False, 'message': "Jeton de vérification manquant."}), 400
    
    # Utiliser la vraie IP (gestion des proxys)
    real_ip = get_real_ip()
    
    if verify_turnstile_token(token, real_ip):
        mark_entry_captcha_verified()
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'message': "Vérification échouée. Veuillez réessayer."}), 400

@app.route('/')
def index():
    # Vérifier si le captcha d'entrée est requis et validé
    if is_turnstile_enabled() and not is_entry_captcha_valid():
        return redirect(url_for('captcha_page'))
    
    # Afficher la page de sélection de serveurs avec informations d'authentification
    servers = get_all_servers_status(use_cache=True)
    
    # Ajouter les logos Discord pour chaque serveur
    for server_id in servers.keys():
        discord_icon = get_discord_guild_icon(server_id)
        if discord_icon:
            servers[server_id]['discord_icon'] = discord_icon
    
    # Vérifier si l'utilisateur est connecté
    user_data = None
    is_super_admin = False
    token = get_token_from_request()
    
    if token:
        payload = verify_jwt_token(token)
        if payload:
            user_data = {
                'user_id': payload['user_id'],
                'username': payload['username'],
                'avatar': payload.get('avatar'),
                'discriminator': payload.get('discriminator', '0'),
                'permissions': payload.get('server_permissions', {})
            }
            # Ajouter l'URL de l'avatar
            user_data['avatar_url'] = get_discord_avatar_url(user_data)
            is_super_admin = user_data['permissions'].get('is_super_admin', False)
    
    # Récupérer le message d'erreur depuis les paramètres URL si présent
    error_message = None
    error_code = request.args.get('error')
    if error_code == 'access_denied':
        server_id = request.args.get('server')
        server_name = request.args.get('server_name', server_id)
        if server_name:
            # Décoder le nom du serveur si encodé
            try:
                from urllib.parse import unquote
                server_name = unquote(server_name)
            except:
                pass
            error_message = f"Vous n'avez pas accès au serveur {server_name}."
        else:
            error_message = "Vous n'avez pas accès à ce serveur."
    
    return render_template('server_selection.html', 
                         servers=servers, 
                         site_name=SITE_NAME,
                         is_super_admin=is_super_admin,
                         user_data=user_data,
                         is_authenticated=user_data is not None,
                         error_message=error_message)

@app.route('/auth/<server>')
def auth_page(server):
    """Page intermédiaire avant la connexion Discord"""
    # Vérifier si le captcha d'entrée a été validé
    if is_turnstile_enabled() and not is_entry_captcha_valid():
        return redirect(url_for('captcha_page'))
    
    # Valider le serveur
    if not server_config.is_valid_server(server):
        return redirect(url_for('index'))
    
    # Récupérer la configuration du serveur
    server_conf = get_server_config(server)
    server_name = server_conf.get('display_name', server) if server_conf else server
    
    # Récupérer le logo Discord du serveur
    discord_icon = get_discord_guild_icon(server)
    
    # Vérifier le statut de la base de données du serveur
    if not check_server_db_status(server):
        # Rediriger vers la page de maintenance si le serveur est hors ligne
        return render_template('maintenance.html', 
                             server=server, 
                             site_name=SITE_NAME)
    
    return render_template('auth.html',
                         server=server,
                         server_name=server_name,
                         server_config=server_conf,
                         site_name=SITE_NAME,
                         discord_icon=discord_icon)

# SÉCURITÉ: Rate limiting sur l'API Turnstile
# Exempt de CSRF car protégé par Turnstile
@app.route('/api/turnstile/verify', methods=['POST'])
@csrf_exempt_api
@rate_limit("30 per minute")
def verify_turnstile_api():
    """Endpoint pour vérifier un jeton Turnstile côté serveur"""
    if not is_turnstile_enabled():
        return jsonify({'success': False, 'message': "Turnstile n'est pas configuré."}), 400
    
    data = request.get_json(silent=True) or {}
    token = data.get('token')
    action = data.get('action', 'login')
    server_id = data.get('server')
    
    if not token:
        return jsonify({'success': False, 'message': "Jeton Turnstile manquant."}), 400
    
    # Utiliser la vraie IP (gestion des proxys)
    real_ip = get_real_ip()
    
    if verify_turnstile_token(token, real_ip):
        mark_turnstile_verified(action=action, server_id=server_id)
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'message': "Validation Turnstile échouée."}), 400

@app.route('/login_page')
def login_page():
    """Redirection vers la connexion Discord directe"""
    return redirect(url_for('login'))

@app.route('/home')
@require_auth()
def home():
    # Page obsolète: rediriger vers la nouvelle page Mon Compte
    return redirect(url_for('account'))

@app.route('/account')
@require_auth()
def account():
    """Page Mon Compte pour les utilisateurs connectés"""
    # Statuts et infos serveurs
    servers_status = get_all_servers_status(use_cache=True)

    user = request.user_data
    perms = user.get('permissions', {})

    # Déterminer les serveurs accessibles
    if perms.get('accessible_servers') == 'all':
        accessible_servers = list(servers_status.keys())
    else:
        accessible_servers = [sid for sid in perms.get('accessible_servers', []) if sid in servers_status]

    admin_servers = perms.get('admin_servers', [])
    is_super_admin = perms.get('is_super_admin', False)

    return render_template(
        'account.html',
        site_name=SITE_NAME,
        user_data=user,
        servers_status=servers_status,
        accessible_servers=accessible_servers,
        admin_servers=admin_servers,
        is_super_admin=is_super_admin
    )

from urllib.parse import quote

# SÉCURITÉ: Rate limiting sur la route login
@app.route('/login')
@rate_limit("10 per minute")
def login():
    """Route d'authentification Discord avec JWT"""
    # Vérifier si le captcha d'entrée a été validé
    if is_turnstile_enabled() and not is_entry_captcha_valid():
        return redirect(url_for('captcha_page'))
    
    # Récupérer le serveur sélectionné depuis les paramètres URL
    selected_server = request.args.get('server')
    
    # Valider le serveur avec la configuration
    if selected_server and server_config.is_valid_server(selected_server):
        # Stocker le serveur dans l'URL de callback
        callback_state = selected_server
    else:
        callback_state = 'general'
    
    # Vérifier le statut de la base de données du serveur AVANT la connexion Discord
    if selected_server and not check_server_db_status(selected_server):
        # Rediriger directement vers la page de maintenance si le serveur est hors ligne
        return render_template('maintenance.html', 
                             server=selected_server, 
                             site_name=SITE_NAME)
    
    # Utiliser l'application Discord centralisée
    redirect_uri = quote(REDIRECT_URI)
    discord_oauth_url = (
        f"https://discord.com/oauth2/authorize"
        f"?client_id={DISCORD_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&scope=identify+guilds+guilds.members.read"
        f"&state={callback_state}"
    )
    return redirect(discord_oauth_url)

# SÉCURITÉ: Rate limiting sur le callback OAuth
@app.route('/callback')
@rate_limit("20 per minute")
def callback():
    """Callback Discord avec création de token JWT"""
    code = request.args.get('code')
    state = request.args.get('state', 'general')
    
    if not code:
        return redirect(url_for('index'))
    
    try:
        # Échanger le code contre un token d'accès
        token_data = {
            'client_id': DISCORD_CLIENT_ID,
            'client_secret': DISCORD_CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': REDIRECT_URI
        }
        
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        token_response = requests.post('https://discord.com/api/oauth2/token', data=token_data, headers=headers)
        
        if token_response.status_code != 200:
            # SÉCURITÉ: Ne pas logger la réponse complète qui peut contenir des infos sensibles
            app.logger.error(f"Erreur échange token Discord - Status: {token_response.status_code}")
            try:
                err_json = token_response.json()
                if err_json.get('error') == 'invalid_client':
                    app.logger.error("invalid_client: Vérifiez DISCORD_CLIENT_ID/SECRET et l'URI de redirection")
            except Exception:
                pass
            return redirect(url_for('index'))
        
        token_json = token_response.json()
        access_token = token_json['access_token']
        
        # Récupérer les informations de l'utilisateur
        user_headers = {'Authorization': f'Bearer {access_token}'}
        user_response = requests.get('https://discord.com/api/users/@me', headers=user_headers)
        
        if user_response.status_code != 200:
            # SÉCURITÉ: Ne pas logger les détails de la réponse utilisateur
            app.logger.error(f"Erreur récupération utilisateur Discord - Status: {user_response.status_code}")
            return redirect(url_for('index'))
        
        user_data = user_response.json()
        user_id = user_data['id']
        
        # Récupérer les permissions de l'utilisateur pour tous les serveurs
        server_permissions = get_user_server_permissions(user_id)
        
        # Créer le token JWT
        jwt_token = create_jwt_token(user_data, server_permissions)
        
        # Déterminer la redirection
        if state != 'general' and server_config.is_valid_server(state):
            # Vérifier l'accès au serveur spécifique
            if (server_permissions.get('is_super_admin', False) or 
                server_permissions.get('accessible_servers') == 'all' or 
                state in server_permissions.get('accessible_servers', [])):
                redirect_url = url_for('dashboard', server=state)
            else:
                # Pas d'accès à ce serveur, rediriger vers l'accueil avec message d'erreur
                server_conf = get_server_config(state)
                server_name = server_conf.get('display_name', state) if server_conf else state
                redirect_url = url_for('index', error='access_denied', server=state, server_name=quote(server_name))
        else:
            # Redirection générale
            redirect_url = url_for('index')
        
        # Créer la réponse avec le cookie JWT
        # SÉCURITÉ: secure=True obligatoire avec Cloudflare Tunnels (HTTPS)
        response = make_response(redirect(redirect_url))
        response.set_cookie(
            'auth_token', 
            jwt_token, 
            max_age=JWT_EXPIRATION_HOURS * 3600,
            httponly=True,
            secure=True,  # HTTPS requis avec Cloudflare Tunnels
            samesite='Strict'  # Protection CSRF renforcée
        )
        
        return response
        
    except Exception as e:
        print(f"[ERROR] Erreur dans le callback Discord: {e}")
        traceback.print_exc()
        return redirect(url_for('index'))

@app.errorhandler(403)
def forbidden_error(error):
    """Handler personnalisé pour les erreurs 403 (accès refusé)"""
    # Récupérer le serveur depuis les paramètres de la requête si disponible
    server_id = None
    if request.view_args:
        server_id = request.view_args.get('server')
    if not server_id:
        server_id = request.args.get('server')
    # Si toujours pas trouvé, essayer de l'extraire de l'URL
    if not server_id and request.path.startswith('/dashboard/'):
        parts = request.path.split('/')
        if len(parts) > 2:
            server_id = parts[2]
    
    # Récupérer le nom du serveur
    if server_id and server_config.is_valid_server(server_id):
        server_conf = get_server_config(server_id)
        server_name = server_conf.get('display_name', server_id) if server_conf else server_id
    else:
        server_name = None
    
    # Vérifier si l'utilisateur est connecté
    user_data = None
    token = get_token_from_request()
    if token:
        payload = verify_jwt_token(token)
        if payload:
            user_data = {
                'user_id': payload['user_id'],
                'username': payload['username'],
                'avatar': payload.get('avatar'),
                'discriminator': payload.get('discriminator', '0'),
                'permissions': payload.get('server_permissions', {})
            }
            user_data['avatar_url'] = get_discord_avatar_url(user_data)
    
    # Récupérer les serveurs avec leurs logos Discord
    servers = get_all_servers_status(use_cache=True)
    for server_id in servers.keys():
        discord_icon = get_discord_guild_icon(server_id)
        if discord_icon:
            servers[server_id]['discord_icon'] = discord_icon
    
    # Afficher la page d'erreur avec le message
    return render_template('server_selection.html',
                         servers=servers,
                         site_name=SITE_NAME,
                         is_super_admin=user_data.get('permissions', {}).get('is_super_admin', False) if user_data else False,
                         user_data=user_data,
                         is_authenticated=user_data is not None,
                         error_message=f"Vous n'avez pas accès au serveur {server_name or 'demandé'}." if server_name else "Vous n'avez pas accès à ce serveur."), 403

@app.route('/logout')
def logout():
    """Route de déconnexion - supprime le token JWT"""
    response = make_response(redirect(url_for('index')))
    response.set_cookie('auth_token', '', expires=0)
    return response

# Route de test XSS supprimée pour sécurité et propreté

@app.route('/@vite/client')
def vite_client_stub():
    return ('', 204)

@app.route('/api/servers/status')
def get_servers_status():
    """API pour obtenir le statut de tous les serveurs avec cache optimisé"""
    # Vérifier si on force le rafraîchissement
    force_refresh = request.args.get('force', 'false').lower() == 'true'
    use_cache = not force_refresh
    
    # Nettoyer les caches expirés avant de récupérer les statuts
    status_cache.cleanup_expired()
    
    response = jsonify(get_all_servers_status(use_cache=use_cache))
    # Ajouter des headers de cache pour les API
    response.headers['Cache-Control'] = 'public, max-age=30'  # Cache de 30 secondes
    return response
    



@app.route('/dashboard')
@app.route('/dashboard/<server>')
@require_auth()
def dashboard(server=None):

    # Si aucun serveur spécifié, rediriger vers la page d'accueil
    if server is None:
        return redirect(url_for('index'))

    # Valider le serveur avec la configuration
    if not server_config.is_valid_server(server):
        return redirect(url_for('index'))
    
    # Vérifier l'accès au serveur spécifique
    user_permissions = request.user_data['permissions']
    if not user_permissions.get('is_super_admin', False):
        accessible_servers = user_permissions.get('accessible_servers', [])
        if accessible_servers != 'all' and server not in accessible_servers:
            abort(403)
    
    # Vérifier le statut de la base de données du serveur
    if not check_server_db_status(server):
        # Rediriger vers la page de maintenance si la DB n'est pas accessible
        return render_template('maintenance.html', 
                             server=server, 
                             site_name=SITE_NAME)
    
    # Récupérer la configuration du serveur
    server_conf = get_server_config(server)

    page = int(request.args.get('page', 1))
    name = request.args.get('name', '').strip()
    idunique = request.args.get('idunique', '').strip()
    message = request.args.get('message', '').strip()
    log_type = request.args.get('type', '').strip()
    title = request.args.get('title', '').strip()
    author_id = request.args.get('author_id', '').strip()
    date_start = request.args.get('date_start', '').strip()
    date_end = request.args.get('date_end', '').strip()
    show_recent = request.args.get('show_recent', '') != ''
    
    # Récupérer le nombre de logs par page (par défaut 10)
    try:
        rows_per_page = int(request.args.get('logs_per_page', 10))
        # Limiter à des valeurs raisonnables
        if rows_per_page not in [10, 25, 50, 100, 200, 500]:
            rows_per_page = 10
    except (ValueError, TypeError):
        rows_per_page = 10

    # Préparer les filtres
    # Si show_recent est activé sans date_start, prendre 7 derniers jours
    if show_recent and not date_start:
        try:
            date_start = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        except Exception:
            date_start = ''
    filters = {
        'name': name,
        'idunique': idunique,
        'message': message,
        'type': log_type,
        'title': title,
        'author_id': author_id,
        'date_start': date_start,
        'date_end': date_end
    }
    
    # Utiliser le cache pour les statistiques de logs (inclure rows_per_page dans la clé)
    cache_key = f"count_{page}_{rows_per_page}"
    cached_stats = log_stats_cache.get(server, filters)
    
    if cached_stats and cached_stats.get('page') == page and cached_stats.get('rows_per_page') == rows_per_page:
        total_logs = cached_stats['total_logs']
        logs = cached_stats['logs']
    else:
        try:
            # Utiliser la nouvelle fonction pour récupérer les logs du serveur
            logs, total_logs = get_server_logs(server, page, filters, rows_per_page)
            
            # Extraire les champs principaux pour l'affichage
            for log in logs:
                log.data_parsed = log.parsed_data
                log.name = log.data_parsed.get('name', '')
                log.idunique = log.data_parsed.get('idunique', '')
                log.logs_message = log.data_parsed.get('logs_message', '')
                log.logs_title = log.data_parsed.get('logs_title', '')
            
            # Mettre en cache les résultats
            log_stats_cache.set(server, {
                'total_logs': total_logs,
                'logs': logs,
                'page': page,
                'rows_per_page': rows_per_page
            }, filters)
        except Exception as e:
            print(f"[ERROR] Erreur lors de la récupération des logs pour {server}: {e}")
            # En cas d'erreur, rediriger vers la page de maintenance
            return render_template('maintenance.html', 
                                 server=server, 
                                 site_name=SITE_NAME)

    # S'assurer que les logs ont leurs données parsées (si pas en cache)
    if not cached_stats or cached_stats.get('page') != page or cached_stats.get('rows_per_page') != rows_per_page:
        pass  # Déjà fait dans le bloc else ci-dessus

    # Types de logs et compteurs optimisés et mis en cache
    type_counts = get_log_type_counts(server)
    log_types = type_counts.get('types', [])
    log_counts = type_counts.get('counts', {})
    # Garder log_types_cache synchronisé
    if log_types:
        log_types_cache.set(server, log_types)

    total_pages = max(1, (total_logs + rows_per_page - 1) // rows_per_page)
    start_page = max(1, page - 2)
    end_page = min(total_pages, page + 2)
    page_numbers = list(range(start_page, end_page + 1))

    args = request.args.to_dict(flat=True)
    args.pop('page', None)

    # Récupérer le logo Discord du serveur
    discord_icon = get_discord_guild_icon(server)
    
    # Envoyer un log Discord pour la connexion
    try:
        user_data = request.user_data
        username = user_data.get('username', 'Inconnu')
        user_id = user_data.get('user_id', 'Inconnu')
        server_name = server_conf.get('display_name', server)
        current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        
        embed = {
            'title': '🔐 Connexion au Panel',
            'description': f'Un utilisateur s\'est connecté au panel de logs',
            'color': 0x8D12AB,
            'fields': [
                {'name': '👤 Utilisateur', 'value': f'{username} ({user_id})', 'inline': True},
                {'name': '🖥️ Serveur', 'value': f'{server_name} ({server})', 'inline': True},
                {'name': '🕐 Heure', 'value': current_time, 'inline': False}
            ]
        }
        # Envoyer en arrière-plan pour ne pas bloquer la réponse
        threading.Thread(target=send_discord_log, args=(server, f'**Connexion au panel** - {username}', embed), daemon=True).start()
    except Exception as e:
        print(f"[ERROR] Erreur lors de l'envoi du log de connexion: {e}")

    return render_template('dashboard.html',
                           logs=logs,
                           total_logs=total_logs,
                           log_types=log_types,
                           log_counts=log_counts,
                           page=page,
                           total_pages=total_pages,
                           page_numbers=page_numbers,
                           args=args,
                           server=server,
                           server_config=server_conf,
                           site_name=SITE_NAME,
                           user_data=request.user_data,
                           discord_icon=discord_icon)

@app.route('/admin/servers')
@require_auth(admin_required=True)
def admin_servers():
    """Interface d'administration pour gérer les serveurs"""
    
    # Utiliser les permissions du token JWT
    user_permissions = request.user_data['permissions']
    user_id = request.user_data['user_id']
    
    # Vérifier si l'utilisateur est super-admin
    is_super_admin = user_permissions.get('is_super_admin', False)
    
    if is_super_admin:
        # Super-admin a accès à tous les serveurs
        user_admin_servers = server_config.get_all_servers()
    else:
        # Filtrer selon les permissions admin de l'utilisateur
        user_admin_servers = {}
        all_servers = server_config.get_all_servers()
        admin_servers = user_permissions.get('admin_servers', [])
        
        if admin_servers == 'all':
            user_admin_servers = all_servers
        elif isinstance(admin_servers, list):
            for server_id in admin_servers:
                if server_id in all_servers:
                    user_admin_servers[server_id] = all_servers[server_id]
    
    # Si l'utilisateur n'est admin d'aucun serveur, rediriger
    if not user_admin_servers and not is_super_admin:
        abort(403)
    
    # Permettre le cache mais avec option de forcer le rafraîchissement via paramètre URL
    force_refresh = request.args.get('force', 'false').lower() == 'true'
    servers_status = get_all_servers_status(use_cache=not force_refresh)
    
    # Mettre à jour les statuts des serveurs (seulement pour ceux où l'utilisateur est admin)
    for server_id in user_admin_servers:
        if server_id in servers_status:
            user_admin_servers[server_id]['status'] = servers_status[server_id]['status']
            user_admin_servers[server_id]['db_accessible'] = servers_status[server_id]['db_accessible']
    
    return render_template('admin_servers.html', 
                         servers=user_admin_servers,
                         site_name=SITE_NAME,
                         user_data=request.user_data)

@app.route('/maintenance')
@app.route('/maintenance/<server_id>')
def maintenance(server_id=None):
    """Page de maintenance générale ou spécifique à un serveur"""
    if server_id:
        # Récupérer le nom du serveur depuis la configuration
        servers = server_config.get_servers()
        server_name = servers.get(server_id, {}).get('display_name', server_id)
    else:
        server_name = 'Système'
    
    return render_template('maintenance.html', 
                         server=server_name, 
                         site_name=SITE_NAME)

@app.route('/admin/servers/<server_id>/edit', methods=['GET', 'POST'])
@require_auth(admin_required=True)
def edit_server(server_id):
    """Éditer la configuration d'un serveur"""
    
    user_id = request.user_data['user_id']
    user_permissions = request.user_data['permissions']
    
    # Vérifier les permissions admin pour ce serveur
    if not user_permissions.get('is_super_admin', False):
        admin_servers = user_permissions.get('admin_servers', [])
        if admin_servers != 'all' and server_id not in admin_servers:
            abort(403)
    
    if request.method == 'POST':
        # Traiter la mise à jour de la configuration
        try:
            config_data = {
                'name': request.form.get('name'),
                'display_name': request.form.get('display_name'),
                'description': request.form.get('description'),
                'status': request.form.get('status'),
                'database_uri': request.form.get('database_uri'),
                'discord': {
                    'guild_id': request.form.get('discord_guild_id'),
                    'role_id_staff': request.form.get('discord_role_staff'),
                    'role_id_admin': request.form.get('discord_role_admin'),
                    'channel_id': request.form.get('discord_channel_id')
                }
            }
            
            # Récupérer l'ancienne configuration pour comparer
            old_config = server_config.get_server(server_id)
            
            # Mettre à jour la configuration
            server_config.update_server_config(server_id, config_data)
            
            # Synchroniser les règles firewall automatiquement (si database_uri a changé)
            if old_config and old_config.get('database_uri') != config_data.get('database_uri'):
                sync_firewall_rules()
            
            # Envoyer un log Discord pour la modification
            try:
                username = request.user_data.get('username', 'Inconnu')
                server_name = config_data.get('display_name', server_id)
                current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
                
                # Détecter les changements
                changes = []
                if old_config:
                    if old_config.get('display_name') != config_data.get('display_name'):
                        changes.append(f"Nom: {old_config.get('display_name')} → {config_data.get('display_name')}")
                    if old_config.get('description') != config_data.get('description'):
                        changes.append("Description modifiée")
                    if old_config.get('database_uri') != config_data.get('database_uri'):
                        changes.append("URI de base de données modifiée")
                    old_discord = old_config.get('discord', {})
                    new_discord = config_data.get('discord', {})
                    if old_discord.get('channel_id') != new_discord.get('channel_id'):
                        changes.append(f"Salon Discord: {old_discord.get('channel_id', 'Aucun')} → {new_discord.get('channel_id', 'Aucun')}")
                
                changes_text = '\n'.join(changes) if changes else 'Aucun changement détecté'
                
                embed = {
                    'title': '⚙️ Modification de Serveur',
                    'description': f'Configuration du serveur modifiée',
                    'color': 0xFFA500,
                    'fields': [
                        {'name': '👤 Administrateur', 'value': f'{username} ({user_id})', 'inline': True},
                        {'name': '🖥️ Serveur', 'value': f'{server_name} ({server_id})', 'inline': True},
                        {'name': '🕐 Heure', 'value': current_time, 'inline': False},
                        {'name': '📝 Modifications', 'value': changes_text[:1024] if len(changes_text) > 1024 else changes_text, 'inline': False}
                    ]
                }
                # Envoyer le log pour chaque serveur configuré (si plusieurs serveurs partagent le même salon)
                # Pour l'instant, on envoie uniquement pour le serveur modifié
                send_discord_log(server_id, f'**Modification de serveur** - {username}', embed)
            except Exception as e:
                print(f"[ERROR] Erreur lors de l'envoi du log de modification: {e}")
            
            return redirect(url_for('admin_servers'))
        except Exception as e:
            return f"Erreur lors de la mise à jour: {str(e)}", 500
    
    # Afficher le formulaire d'édition
    server_conf = server_config.get_server(server_id)
    if not server_conf:
        return "Serveur non trouvé", 404
    
    return render_template('edit_server.html',
                         server_id=server_id,
                         server=server_conf,
                         site_name=SITE_NAME,
                         user_data=request.user_data,
                         discord_icon=get_discord_guild_icon(server_id))


@app.route('/admin/servers/<server_id>/refresh_logo', methods=['POST'])
@require_auth(admin_required=True)
def refresh_server_logo(server_id):
    """Force la récupération du logo Discord d'un serveur"""
    user_permissions = request.user_data['permissions']
    
    if not user_permissions.get('is_super_admin', False):
        admin_servers = user_permissions.get('admin_servers', [])
        if admin_servers != 'all' and server_id not in admin_servers:
            return jsonify({'error': 'Accès refusé'}), 403
    
    try:
        # Invalider le cache pour forcer un nouvel appel à l'API Discord
        discord_icon_cache.pop(server_id, None)
        new_icon = get_discord_guild_icon(server_id)
        
        if not new_icon:
            return jsonify({
                'success': False,
                'message': "Impossible de récupérer le logo Discord. Vérifiez la configuration du serveur."
            }), 400
        
        return jsonify({'success': True, 'logo': new_icon})
    except Exception as e:
        print(f"[ERROR] Erreur lors du rafraîchissement du logo pour {server_id}: {e}")
        return jsonify({
            'success': False,
            'message': "Erreur interne lors du rafraîchissement du logo."
        }), 500


@app.route('/admin/servers/create', methods=['POST'])
@require_auth(admin_required=True)
def create_server():
    """Créer un nouveau serveur (SUPER_ADMIN uniquement)"""
    
    user_id = request.user_data['user_id']
    user_permissions = request.user_data['permissions']
    
    # Vérifier que l'utilisateur est SUPER_ADMIN
    if not user_permissions.get('is_super_admin', False):
        return jsonify({'error': 'Accès refusé. Seul le SUPER_ADMIN peut créer des serveurs.'}), 403
    
    try:
        # Récupérer les données du formulaire
        server_id = request.form.get('server_id', '').strip()
        display_name = request.form.get('display_name', '').strip()
        description = request.form.get('description', '').strip()
        database_uri = request.form.get('database_uri', '').strip()
        
        if not server_id or not display_name or not database_uri:
            return jsonify({'error': 'Les champs server_id, display_name et database_uri sont requis'}), 400
        
        # Vérifier que le serveur n'existe pas déjà
        if server_config.is_valid_server(server_id):
            return jsonify({'error': f'Le serveur {server_id} existe déjà'}), 400
        
        # Créer la configuration du serveur
        config_data = {
            'name': server_id,
            'display_name': display_name,
            'description': description,
            'database_uri': database_uri,
            'discord': {
                'guild_id': request.form.get('discord_guild_id', '').strip(),
                'role_id_staff': request.form.get('discord_role_staff', '').strip(),
                'role_id_admin': request.form.get('discord_role_admin', '').strip(),
                'channel_id': request.form.get('discord_channel_id', '').strip()
            }
        }
        
        # Créer le serveur
        server_config.create_server(server_id, config_data)
        
        # Synchroniser les règles firewall automatiquement
        sync_firewall_rules()
        
        # Envoyer un log Discord pour la création
        try:
            username = request.user_data.get('username', 'Inconnu')
            current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            
            embed = {
                'title': '➕ Création de Serveur',
                'description': f'Nouveau serveur créé dans le panel',
                'color': 0x00FF00,
                'fields': [
                    {'name': '👤 Administrateur', 'value': f'{username} ({user_id})', 'inline': True},
                    {'name': '🖥️ Serveur', 'value': f'{display_name} ({server_id})', 'inline': True},
                    {'name': '🕐 Heure', 'value': current_time, 'inline': False},
                    {'name': '📝 Description', 'value': description[:1024] if description else 'Aucune description', 'inline': False}
                ]
            }
            # Envoyer le log pour le nouveau serveur
            send_discord_log(server_id, f'**Création de serveur** - {username}', embed)
        except Exception as e:
            print(f"[ERROR] Erreur lors de l'envoi du log de création: {e}")
        
        return jsonify({'success': True, 'message': f'Serveur {server_id} créé avec succès'})
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Erreur lors de la création: {str(e)}'}), 500

@app.route('/admin/servers/<server_id>/delete', methods=['POST'])
@require_auth(admin_required=True)
def delete_server(server_id):
    """Supprimer un serveur (SUPER_ADMIN uniquement)"""
    
    user_id = request.user_data['user_id']
    user_permissions = request.user_data['permissions']
    
    # Vérifier que l'utilisateur est SUPER_ADMIN
    if not user_permissions.get('is_super_admin', False):
        return jsonify({'error': 'Accès refusé. Seul le SUPER_ADMIN peut supprimer des serveurs.'}), 403
    
    try:
        # Vérifier que le serveur existe
        if not server_config.is_valid_server(server_id):
            return jsonify({'error': f'Le serveur {server_id} n\'existe pas'}), 404
        
        # Récupérer les infos du serveur avant suppression
        server_conf = server_config.get_server(server_id)
        server_name = server_conf.get('display_name', server_id) if server_conf else server_id
        channel_id = server_conf.get('discord', {}).get('channel_id') if server_conf else None
        
        # Supprimer le serveur
        server_config.delete_server(server_id)
        
        # Synchroniser les règles firewall automatiquement
        sync_firewall_rules()
        
        # Envoyer un log Discord pour la suppression (avant l'invalidation des caches)
        try:
            username = request.user_data.get('username', 'Inconnu')
            current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            
            embed = {
                'title': '🗑️ Suppression de Serveur',
                'description': f'Serveur supprimé du panel',
                'color': 0xFF0000,
                'fields': [
                    {'name': '👤 Administrateur', 'value': f'{username} ({user_id})', 'inline': True},
                    {'name': '🖥️ Serveur', 'value': f'{server_name} ({server_id})', 'inline': True},
                    {'name': '🕐 Heure', 'value': current_time, 'inline': False}
                ]
            }
            # Envoyer le log avant la suppression (on utilise le serveur lui-même)
            if channel_id:
                send_discord_log(server_id, f'**Suppression de serveur** - {username}', embed)
        except Exception as e:
            print(f"[ERROR] Erreur lors de l'envoi du log de suppression: {e}")
        
        # Invalider les caches liés à ce serveur
        status_cache.invalidate(server_id)
        server_config_cache.invalidate(server_id)
        log_types_cache.invalidate(server_id)
        log_stats_cache.invalidate(server_id)
        
        return jsonify({'success': True, 'message': f'Serveur {server_id} supprimé avec succès'})
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Erreur lors de la suppression: {str(e)}'}), 500


# Démarrer le bot Discord en arrière-plan
def start_discord_bot():
    """Démarre le bot Discord en arrière-plan"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot.start(DISCORD_BOT_TOKEN))
    except LoginFailure as e:
        print(f"[ERROR] Erreur lors du démarrage du bot Discord: {e}")
        print("[HINT] Token du bot invalide. Réinitialisez le Bot Token dans Discord Developer Portal et mettez à jour DISCORD_BOT_TOKEN.")
        print("[HINT] Assurez-vous que le token appartient à l'application (ID identique).")
    except Exception as e:
        print(f"[ERROR] Erreur lors du démarrage du bot Discord: {e}")

if __name__ == '__main__':
    # Ensure Flask application context for operations that use db.session
    with app.app_context():
        check_db_connection()
    
    # Démarrer le bot Discord dans un thread séparé
    config_ok = validate_discord_config()
    if DISCORD_BOT_TOKEN and config_ok:
        bot_thread = threading.Thread(target=start_discord_bot, daemon=True)
        bot_thread.start()
        print("[INFO] Bot Discord démarré en arrière-plan")
    else:
        print("[WARNING] Configuration Discord incomplète ou invalide - les vérifications de rôles ne fonctionneront pas")
    
    # Utilise la variable d'environnement PORT si fournie par l'hébergeur
    port = int(os.getenv('PORT', 3001))
    app.run(host='0.0.0.0', port=port)
