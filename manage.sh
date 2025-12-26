#!/bin/bash
# =============================================================================
# Panel Logs Galaxy - Script de gestion
# Redirige vers le script principal dans deploy/
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "$SCRIPT_DIR/deploy/manage.sh" ]]; then
    exec "$SCRIPT_DIR/deploy/manage.sh" "$@"
else
    echo "Erreur: Script de gestion non trouvé"
    echo "Vérifiez que le dossier deploy/ existe"
    exit 1
fi
