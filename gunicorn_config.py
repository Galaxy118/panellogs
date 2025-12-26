# =============================================================================
# Configuration Gunicorn optimisée pour le Panel Logs Galaxy
# Optimisé pour Ubuntu 24.04 avec Cloudflare Tunnels
# Utilisation: gunicorn -c gunicorn_config.py main:app
# =============================================================================

import multiprocessing
import os

# =============================================================================
# WORKERS
# =============================================================================

# Nombre de workers (recommandé: 2-4 x nombre de CPU)
# Pour haute performance avec Cloudflare Tunnels: (2 x CPU cores) + 1
workers = multiprocessing.cpu_count() * 2 + 1

# Nombre de threads par worker (pour I/O bound - Discord API, DB)
threads = 4

# Nombre de connexions simultanées par worker
worker_connections = 1000

# Classe de worker
# 'gthread' est recommandé pour les apps avec I/O (API Discord, DB)
worker_class = 'gthread'

# =============================================================================
# TIMEOUTS
# =============================================================================

# Timeout pour les workers (en secondes)
timeout = 120  # Réduit pour éviter les workers zombies

# Keep-alive timeout (Cloudflare timeout est de 100s)
keepalive = 65

# Graceful timeout pour l'arrêt propre
graceful_timeout = 30

# =============================================================================
# PERFORMANCE
# =============================================================================

# Nombre de requêtes après lesquelles un worker est recyclé
# (prévention des fuites mémoire)
max_requests = 1000
max_requests_jitter = 100

# Préchargement de l'application (améliore les performances)
preload_app = True

# Worker temp directory (utilise la RAM pour meilleures performances)
# Ubuntu 24.04 a /dev/shm disponible par défaut
worker_tmp_dir = '/dev/shm'

# =============================================================================
# BINDING (Cloudflare Tunnels)
# =============================================================================

# Binding localhost uniquement - Cloudflare Tunnel gère l'exposition externe
bind = f"127.0.0.1:{os.getenv('PORT', '3001')}"

# =============================================================================
# SÉCURITÉ
# =============================================================================

# Limite la taille des headers (protection contre les attaques)
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# User/Group (décommentez pour production)
# user = 'www-data'
# group = 'www-data'

# =============================================================================
# LOGGING
# =============================================================================

# Logs
accesslog = '-'
errorlog = '-'
loglevel = 'warning'  # 'info' pour debug, 'warning' pour production

# Format de log (compatible avec les parsers standard)
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# =============================================================================
# PROCESSUS
# =============================================================================

# Process naming
proc_name = 'logspanel'

# PID file
pidfile = '/tmp/gunicorn_logspanel.pid'

# =============================================================================
# HEADERS FORWARDING (Cloudflare)
# =============================================================================

# Faire confiance aux headers de proxy (Cloudflare)
forwarded_allow_ips = '*'  # Cloudflare IPs sont validées dans l'application
