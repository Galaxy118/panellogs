#!/bin/bash
# =============================================================================
# Script d'autorisation des connexions sortantes MySQL
# Lit servers_config.json et autorise les connexions vers les bases de données
# =============================================================================

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Chemin par défaut
SERVERS_CONFIG="/var/www/logspanel/servers_config.json"
AUTO_MODE=false

# Parse des arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --config)
            SERVERS_CONFIG="$2"
            shift 2
            ;;
        --auto)
            AUTO_MODE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --config PATH    Chemin vers servers_config.json (défaut: /var/www/logspanel/servers_config.json)"
            echo "  --auto           Mode automatique, sans confirmation"
            echo "  --help           Afficher cette aide"
            echo ""
            echo "Ce script autorise automatiquement les connexions sortantes (EGRESS)"
            echo "vers tous les serveurs MySQL configurés dans servers_config.json"
            exit 0
            ;;
        *)
            shift
            ;;
    esac
done

print_header() {
    echo ""
    printf "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}\n"
    printf "${CYAN}║${NC}    ${BLUE}🔓 Configuration Firewall MySQL (EGRESS)${NC}                  ${CYAN}║${NC}\n"
    printf "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}\n"
    echo ""
}

print_success() {
    printf "${GREEN}  ✓ $1${NC}\n"
}

print_error() {
    printf "${RED}  ✗ $1${NC}\n"
}

print_info() {
    printf "${CYAN}  ℹ $1${NC}\n"
}

print_warning() {
    printf "${YELLOW}  ⚠ $1${NC}\n"
}

# Vérification root
if [[ $EUID -ne 0 ]]; then
    print_error "Ce script doit être exécuté en tant que root"
    echo "Utilisez: sudo $0"
    exit 1
fi

print_header

# Vérifier si le fichier existe
if [[ ! -f "$SERVERS_CONFIG" ]]; then
    print_error "Fichier non trouvé: $SERVERS_CONFIG"
    exit 1
fi

print_info "Lecture de: $SERVERS_CONFIG"

# Vérifier si python3 est installé
if ! command -v python3 &> /dev/null; then
    print_error "python3 n'est pas installé"
    exit 1
fi

# Extraire les hôtes et ports MySQL avec Python
DB_HOSTS=$(python3 -c "
import json
import re
import sys

config_file = '$SERVERS_CONFIG'

try:
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    servers = config.get('servers', {})
    db_connections = []
    
    # Pattern pour parser les URIs MySQL
    # Format: mysql://user:password@host:port/database
    pattern = r'mysql(?:\+\w+)?://[^@]+@([^:/]+):(\d+)/'
    
    for server_name, server_config in servers.items():
        db_uri = server_config.get('database_uri', '')
        
        if not db_uri or db_uri.startswith('sqlite'):
            continue
        
        match = re.search(pattern, db_uri)
        if match:
            host = match.group(1)
            port = match.group(2)
            db_connections.append(f"{host}:{port}")
    
    # Dédupliquer
    db_connections = list(set(db_connections))
    
    # Afficher au format: host:port (un par ligne)
    for conn in sorted(db_connections):
        print(conn)
        
except Exception as e:
    print(f'ERREUR: {e}', file=sys.stderr)
    sys.exit(1)
")

if [[ -z "$DB_HOSTS" ]]; then
    print_warning "Aucun serveur MySQL trouvé dans la configuration"
    exit 0
fi

echo ""
printf "${BLUE}Serveurs MySQL détectés:${NC}\n"
echo "$DB_HOSTS" | while read line; do
    if [[ -n "$line" ]]; then
        printf "  • $line\n"
    fi
done

echo ""

if [[ "$AUTO_MODE" == false ]]; then
    read -p "Autoriser ces connexions sortantes dans UFW? (o/n) [o]: " CONFIRM
    CONFIRM=${CONFIRM:-o}
    
    if [[ "$CONFIRM" != "o" && "$CONFIRM" != "O" ]]; then
        print_info "Opération annulée"
        exit 0
    fi
else
    print_info "Mode automatique activé"
fi

echo ""
print_info "Configuration des règles UFW..."

# Compteurs
ADDED=0
SKIPPED=0
FAILED=0

# Traiter chaque hôte
while IFS= read -r line; do
    if [[ -z "$line" ]]; then
        continue
    fi
    
    HOST=$(echo "$line" | cut -d':' -f1)
    PORT=$(echo "$line" | cut -d':' -f2)
    
    # Vérifier si la règle existe déjà
    if ufw status | grep -q "$PORT.*ALLOW OUT.*Anywhere"; then
        print_warning "Règle déjà existante pour le port $PORT"
        ((SKIPPED++))
        continue
    fi
    
    # Ajouter la règle UFW
    if ufw allow out to any port "$PORT" proto tcp comment "MySQL $HOST" > /dev/null 2>&1; then
        print_success "Autorisé: $HOST:$PORT"
        ((ADDED++))
    else
        print_error "Échec: $HOST:$PORT"
        ((FAILED++))
    fi
done <<< "$DB_HOSTS"

# Recharger UFW
print_info "Rechargement de UFW..."
ufw reload > /dev/null 2>&1

echo ""
printf "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}\n"
printf "${CYAN}║${NC}    ${GREEN}✓ Configuration terminée${NC}                                   ${CYAN}║${NC}\n"
printf "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}\n"
echo ""

print_success "Règles ajoutées: $ADDED"
[[ $SKIPPED -gt 0 ]] && print_warning "Règles ignorées: $SKIPPED"
[[ $FAILED -gt 0 ]] && print_error "Règles échouées: $FAILED"

echo ""
print_info "Vérification des règles UFW:"
ufw status | grep -E "^[0-9]+.*ALLOW OUT" | head -10

echo ""
print_warning "N'oubliez pas de configurer les règles INGRESS sur les serveurs MySQL"
print_info "IP publique de ce serveur: $(curl -s ifconfig.me)"
echo ""
