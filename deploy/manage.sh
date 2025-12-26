#!/bin/bash
# =============================================================================
# Script de gestion - Panel Logs VOLTRE
# Ubuntu 24.04 + Cloudflare Tunnels
# =============================================================================
#
# Usage:
#   sudo ./manage.sh status      # Afficher le statut
#   sudo ./manage.sh start       # Démarrer tous les services
#   sudo ./manage.sh stop        # Arrêter tous les services
#   sudo ./manage.sh restart     # Redémarrer tous les services
#   sudo ./manage.sh logs        # Afficher les logs en temps réel
#   sudo ./manage.sh update      # Mettre à jour les dépendances
#   sudo ./manage.sh tunnel      # Configurer Cloudflare Tunnel
#
# =============================================================================

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Détecter le répertoire du projet
detect_project_dir() {
    if [[ -f "/etc/systemd/system/logspanel.service" ]]; then
        grep "^WorkingDirectory=" /etc/systemd/system/logspanel.service | cut -d'=' -f2-
    else
        dirname "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    fi
}

PROJECT_DIR=$(detect_project_dir)

# Fonctions d'affichage
print_header() {
    printf "\n${CYAN}╔════════════════════════════════════════════════════════╗${NC}\n"
    printf "${CYAN}║${NC}  ${BLUE}$1${NC}\n"
    printf "${CYAN}╚════════════════════════════════════════════════════════╝${NC}\n\n"
}

print_success() { printf "${GREEN}  ✓ $1${NC}\n"; }
print_error() { printf "${RED}  ✗ $1${NC}\n"; }
print_warning() { printf "${YELLOW}  ⚠ $1${NC}\n"; }
print_info() { printf "${CYAN}  ℹ $1${NC}\n"; }

# Vérification root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "Ce script doit être exécuté en tant que root"
        exit 1
    fi
}

# Afficher le statut
cmd_status() {
    print_header "Statut des services"
    
    # Panel
    printf "${BLUE}Panel Logs (logspanel):${NC}\n"
    if systemctl is-active --quiet logspanel; then
        print_success "Actif"
        UPTIME=$(systemctl show logspanel --property=ActiveEnterTimestamp | cut -d'=' -f2)
        print_info "Démarré: $UPTIME"
    else
        print_error "Inactif"
    fi
    echo ""
    
    # Cloudflare Tunnel
    printf "${BLUE}Cloudflare Tunnel (cloudflared):${NC}\n"
    
    # Vérifier si cloudflared est installé
    if ! command -v cloudflared &>/dev/null; then
        print_warning "cloudflared non installé"
        print_info "Installez avec: curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared"
    else
        print_info "Version: $(cloudflared --version 2>&1 | head -1)"
        
        # Vérifier le service
        if systemctl is-active --quiet cloudflared; then
            print_success "Service actif"
            
            # Récupérer les infos du tunnel
            if [[ -f /etc/cloudflared/config.yml ]]; then
                HOSTNAME=$(grep -E "^\s*-?\s*hostname:" /etc/cloudflared/config.yml 2>/dev/null | head -1 | awk '{print $2}' | tr -d '"')
                TUNNEL_ID=$(grep -E "^tunnel:" /etc/cloudflared/config.yml 2>/dev/null | awk '{print $2}' | tr -d '"')
                
                [[ -n "$HOSTNAME" ]] && print_info "Domaine: https://$HOSTNAME"
                [[ -n "$TUNNEL_ID" && "$TUNNEL_ID" != "VOTRE_TUNNEL_ID" ]] && print_info "Tunnel ID: ${TUNNEL_ID:0:8}..."
                
                # Tester la connexion externe
                if [[ -n "$HOSTNAME" ]]; then
                    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "https://$HOSTNAME" 2>/dev/null || echo "000")
                    if [[ "$HTTP_CODE" == "200" || "$HTTP_CODE" == "302" ]]; then
                        print_success "Accessible depuis Internet (HTTP $HTTP_CODE)"
                    elif [[ "$HTTP_CODE" == "503" ]]; then
                        print_warning "Tunnel actif mais panel non accessible (503)"
                    else
                        print_warning "Test externe: HTTP $HTTP_CODE"
                    fi
                fi
            fi
        elif systemctl is-enabled --quiet cloudflared 2>/dev/null; then
            print_warning "Service installé mais inactif"
            print_info "Démarrez avec: sudo systemctl start cloudflared"
        else
            # Vérifier si une configuration existe
            if [[ -f /etc/cloudflared/config.yml ]]; then
                print_warning "Configuré mais service non installé"
                print_info "Installez le service: sudo cloudflared service install"
            else
                print_warning "Non configuré"
                print_info "Configurez avec: sudo ./manage.sh tunnel"
            fi
        fi
    fi
    echo ""
    
    # Test local
    printf "${BLUE}Test de connectivité locale:${NC}\n"
    PORT=$(grep "^Environment=\"PORT=" /etc/systemd/system/logspanel.service 2>/dev/null | cut -d'"' -f2 | cut -d'=' -f2)
    PORT=${PORT:-3001}
    
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT" 2>/dev/null || echo "000")
    if [[ "$HTTP_CODE" == "200" || "$HTTP_CODE" == "302" ]]; then
        print_success "Panel accessible sur localhost:$PORT (HTTP $HTTP_CODE)"
    else
        print_warning "Panel non accessible localement (HTTP $HTTP_CODE)"
    fi
    echo ""
    
    # Firewall
    printf "${BLUE}Firewall (UFW):${NC}\n"
    if command -v ufw &>/dev/null; then
        UFW_STATUS=$(ufw status | head -1)
        print_info "$UFW_STATUS"
        
        # Vérifier si des ports web sont ouverts (ce qui serait une erreur de config)
        if ufw status | grep -qE "80|443|$PORT.*ALLOW"; then
            print_warning "Des ports web sont ouverts - ils ne devraient pas l'être avec Cloudflare Tunnel"
        else
            print_success "Aucun port web exposé (sécurisé)"
        fi
    else
        print_warning "UFW non installé"
    fi
}

# Démarrer les services
cmd_start() {
    print_header "Démarrage des services"
    
    # Panel
    printf "${BLUE}Démarrage du panel...${NC}\n"
    if systemctl start logspanel; then
        sleep 2
        if systemctl is-active --quiet logspanel; then
            print_success "Panel démarré"
        else
            print_error "Échec du démarrage du panel"
        fi
    else
        print_error "Impossible de démarrer le panel"
    fi
    
    # Cloudflare Tunnel
    printf "${BLUE}Démarrage de Cloudflare Tunnel...${NC}\n"
    if systemctl is-enabled cloudflared &>/dev/null; then
        if systemctl start cloudflared; then
            sleep 2
            if systemctl is-active --quiet cloudflared; then
                print_success "Cloudflare Tunnel démarré"
            else
                print_error "Échec du démarrage du tunnel"
            fi
        fi
    else
        print_warning "Cloudflare Tunnel non configuré"
    fi
}

# Arrêter les services
cmd_stop() {
    print_header "Arrêt des services"
    
    printf "${BLUE}Arrêt du panel...${NC}\n"
    systemctl stop logspanel && print_success "Panel arrêté" || print_warning "Panel déjà arrêté"
    
    printf "${BLUE}Arrêt de Cloudflare Tunnel...${NC}\n"
    systemctl stop cloudflared 2>/dev/null && print_success "Tunnel arrêté" || print_warning "Tunnel déjà arrêté"
}

# Redémarrer les services
cmd_restart() {
    print_header "Redémarrage des services"
    
    # Mettre à jour la version des assets
    if [[ -f "$PROJECT_DIR/.env" ]]; then
        NEW_VERSION=$(date +%s)
        if grep -q "^ASSET_VERSION=" "$PROJECT_DIR/.env"; then
            sed -i "s/^ASSET_VERSION=.*/ASSET_VERSION=$NEW_VERSION/" "$PROJECT_DIR/.env"
        else
            echo "ASSET_VERSION=$NEW_VERSION" >> "$PROJECT_DIR/.env"
        fi
        print_info "Version des assets: $NEW_VERSION"
    fi
    
    # Recharger systemd
    systemctl daemon-reload
    
    # Redémarrer le panel
    printf "${BLUE}Redémarrage du panel...${NC}\n"
    if systemctl restart logspanel; then
        sleep 2
        if systemctl is-active --quiet logspanel; then
            print_success "Panel redémarré"
        else
            print_error "Échec du redémarrage"
            print_info "Vérifiez: journalctl -u logspanel -n 50"
        fi
    fi
    
    # Redémarrer le tunnel si actif
    if systemctl is-active --quiet cloudflared; then
        printf "${BLUE}Redémarrage de Cloudflare Tunnel...${NC}\n"
        systemctl restart cloudflared && print_success "Tunnel redémarré"
    fi
}

# Afficher les logs
cmd_logs() {
    print_header "Logs en temps réel"
    print_info "Ctrl+C pour quitter"
    echo ""
    
    # Suivre les logs des deux services
    journalctl -u logspanel -u cloudflared -f --no-hostname -o short-iso
}

# Mettre à jour les dépendances
cmd_update() {
    print_header "Mise à jour des dépendances"
    
    cd "$PROJECT_DIR"
    
    printf "${BLUE}Mise à jour de pip...${NC}\n"
    source venv/bin/activate
    pip install --upgrade pip -q
    print_success "pip mis à jour"
    
    printf "${BLUE}Mise à jour des dépendances...${NC}\n"
    pip install -r requirements.txt --upgrade -q
    print_success "Dépendances mises à jour"
    
    deactivate
    
    printf "${BLUE}Redémarrage du panel...${NC}\n"
    systemctl restart logspanel
    sleep 2
    if systemctl is-active --quiet logspanel; then
        print_success "Panel redémarré avec les nouvelles dépendances"
    else
        print_error "Erreur au redémarrage"
    fi
}

# Configuration du tunnel
cmd_tunnel() {
    print_header "Configuration de Cloudflare Tunnel"
    
    # Vérifier cloudflared
    if ! command -v cloudflared &>/dev/null; then
        print_error "cloudflared n'est pas installé"
        print_info "Installez-le avec: curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared"
        exit 1
    fi
    
    echo ""
    printf "${YELLOW}Étapes de configuration :${NC}\n"
    echo ""
    echo "  1. Authentification Cloudflare :"
    echo "     cloudflared tunnel login"
    echo ""
    echo "  2. Création du tunnel :"
    echo "     cloudflared tunnel create logspanel"
    echo ""
    echo "  3. Configuration DNS (remplacez par votre domaine) :"
    echo "     cloudflared tunnel route dns logspanel votre-domaine.com"
    echo ""
    echo "  4. Copiez le fichier de credentials :"
    echo "     sudo cp ~/.cloudflared/<TUNNEL_ID>.json /etc/cloudflared/credentials.json"
    echo ""
    echo "  5. Créez la configuration :"
    echo "     sudo nano /etc/cloudflared/config.yml"
    echo ""
    echo "  6. Installez le service :"
    echo "     sudo cloudflared service install"
    echo ""
    echo "  7. Démarrez le tunnel :"
    echo "     sudo systemctl start cloudflared"
    echo ""
    
    # Afficher le template
    if [[ -f /etc/cloudflared/config.yml.template ]]; then
        printf "${BLUE}Template de configuration disponible :${NC}\n"
        echo "  /etc/cloudflared/config.yml.template"
    fi
}

# Afficher l'aide
cmd_help() {
    echo ""
    printf "${CYAN}Panel Logs VOLTRE - Script de gestion${NC}\n"
    echo ""
    printf "${BLUE}Usage:${NC}\n"
    echo "  sudo $0 <commande>"
    echo ""
    printf "${BLUE}Commandes disponibles:${NC}\n"
    echo "  status    Afficher le statut des services"
    echo "  start     Démarrer tous les services"
    echo "  stop      Arrêter tous les services"
    echo "  restart   Redémarrer tous les services"
    echo "  logs      Afficher les logs en temps réel"
    echo "  update    Mettre à jour les dépendances Python"
    echo "  tunnel    Guide de configuration Cloudflare Tunnel"
    echo "  help      Afficher cette aide"
    echo ""
}

# ============================================================================
# MAIN
# ============================================================================

check_root

case "${1:-help}" in
    status)
        cmd_status
        ;;
    start)
        cmd_start
        ;;
    stop)
        cmd_stop
        ;;
    restart)
        cmd_restart
        ;;
    logs)
        cmd_logs
        ;;
    update)
        cmd_update
        ;;
    tunnel)
        cmd_tunnel
        ;;
    *)
        cmd_help
        ;;
esac
