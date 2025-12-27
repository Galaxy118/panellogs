#!/bin/bash
# =============================================================================
# Script de Correction - Problème Système de Fichiers en Lecture Seule
# =============================================================================

set -e  # Arrêt en cas d'erreur

echo "🔧 Correction du problème de système de fichiers en lecture seule..."
echo ""

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Corriger immédiatement le système de fichiers
echo -e "${YELLOW}📁 Étape 1/4 - Remontage du système de fichiers en lecture-écriture${NC}"
if mount | grep "on / type" | grep -q "ro,"; then
    echo "⚠️  Système en lecture seule détecté, correction..."
    sudo mount -o remount,rw /
    echo -e "${GREEN}✅ Système remonté en lecture-écriture${NC}"
else
    echo -e "${GREEN}✅ Système déjà en lecture-écriture${NC}"
fi
echo ""

# 2. Installer le service keepfs-rw
echo -e "${YELLOW}📋 Étape 2/4 - Installation du service de surveillance keepfs-rw${NC}"
sudo cp keepfs-rw.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable keepfs-rw
sudo systemctl restart keepfs-rw
echo -e "${GREEN}✅ Service keepfs-rw installé et démarré${NC}"
echo ""

# 3. Mettre à jour le service logspanel
echo -e "${YELLOW}🔄 Étape 3/4 - Mise à jour du service logspanel${NC}"
sudo cp logspanel.service /etc/systemd/system/
sudo systemctl daemon-reload
echo -e "${GREEN}✅ Service logspanel mis à jour${NC}"
echo ""

# 4. Vérifier les permissions
echo -e "${YELLOW}🔐 Étape 4/4 - Vérification des permissions${NC}"
PANEL_DIR="/var/www/logspanel"
if [ -d "$PANEL_DIR" ]; then
    sudo chown -R www-data:www-data "$PANEL_DIR"
    sudo chmod 775 "$PANEL_DIR"
    sudo chmod 664 "$PANEL_DIR/servers_config.json" 2>/dev/null || echo "⚠️  servers_config.json n'existe pas encore"
    echo -e "${GREEN}✅ Permissions corrigées${NC}"
else
    echo -e "${RED}❌ Répertoire $PANEL_DIR introuvable${NC}"
fi
echo ""

# 5. Redémarrer les services
echo -e "${YELLOW}🔄 Redémarrage des services...${NC}"
sudo systemctl restart logspanel
echo -e "${GREEN}✅ Services redémarrés${NC}"
echo ""

# 6. Vérifier l'état
echo -e "${YELLOW}📊 État des services :${NC}"
echo ""
sudo systemctl status keepfs-rw --no-pager -l | head -n 10
echo ""
sudo systemctl status logspanel --no-pager -l | head -n 10
echo ""

echo -e "${GREEN}🎉 Correction terminée !${NC}"
echo ""
echo "📝 Pour surveiller les logs :"
echo "   sudo journalctl -u logspanel -u keepfs-rw -f --no-pager"
echo ""
echo "🧪 Testez maintenant la modification d'un serveur dans l'interface web"
