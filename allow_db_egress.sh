#!/bin/bash
# Wrapper script - redirige vers le script de déploiement

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/deploy/allow_db_egress.sh" "$@"
