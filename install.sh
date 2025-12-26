#!/bin/bash
# =============================================================================
# Panel Logs Galaxy - Script d'installation
# Redirige vers le script principal dans deploy/
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "$SCRIPT_DIR/deploy/install.sh" ]]; then
    exec "$SCRIPT_DIR/deploy/install.sh" "$@"
else
    echo "Erreur: Script d'installation non trouvé"
    echo "Vérifiez que le dossier deploy/ existe"
    exit 1
fi
