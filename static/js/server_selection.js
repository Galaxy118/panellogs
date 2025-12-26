// Mise à jour des statuts des serveurs et interactions
let lastServerStatus = {};
let isUpdating = false;

function findServerCard(serverId) {
  return document.querySelector(`[data-server-id="${serverId}"]`);
}

function updateServerCard(serverId, serverData) {
  const serverCard = findServerCard(serverId);
  if (!serverCard) {
    console.warn(`Carte serveur non trouvée pour: ${serverId}`);
    return;
  }

  const statusIndicator = serverCard.querySelector('.status-indicator');
  const serverStatus = serverCard.querySelector('.server-status');

  setTimeout(() => {
    if (statusIndicator) {
      statusIndicator.className = `status-indicator ${serverData.status === 'offline' ? 'offline' : ''}`;
    }
    if (serverStatus) {
      serverStatus.className = `server-status ${serverData.status === 'online' ? 'status-online' : 'status-offline'}`;
      serverStatus.innerHTML = `<i class="fas fa-circle"></i> ${serverData.status === 'online' ? 'En ligne' : 'Hors ligne'}`;
    }
  }, 50);
}

function refreshServerStatuses() {
  if (isUpdating) return;
  isUpdating = true;
  fetch('/api/servers/status')
    .then(res => res.json())
    .then(data => {
      Object.keys(data).forEach(serverId => {
        const serverData = data[serverId];
        const prev = lastServerStatus[serverId];
        if (!prev || prev.status !== serverData.status) {
          updateServerCard(serverId, serverData);
        }
        lastServerStatus[serverId] = serverData;
      });
    })
    .catch(err => console.error('Erreur lors de la mise à jour du statut:', err))
    .finally(() => { isUpdating = false; });
}

document.addEventListener('DOMContentLoaded', () => {
  refreshServerStatuses();
  setInterval(refreshServerStatuses, 30000);

  // Gérer l'alerte d'erreur - fermeture automatique après 8 secondes
  const errorAlert = document.getElementById('errorAlert');
  if (errorAlert) {
    setTimeout(() => {
      errorAlert.style.opacity = '0';
      errorAlert.style.transform = 'translateX(-50%) translateY(-20px)';
      setTimeout(() => {
        errorAlert.style.display = 'none';
      }, 500);
    }, 8000);
  }

  // Appliquer l'animation delay depuis les data-attributes et gérer le clic carte
  document.querySelectorAll('.server-item').forEach((card) => {
    const delay = card.getAttribute('data-animation-delay');
    if (delay) {
      card.style.animationDelay = `${delay}s`;
    }

    const isOffline = card.classList.contains('server-offline');
    if (!isOffline) {
      // Pour les serveurs en ligne, rendre toute la carte cliquable
      const targetHref = card.getAttribute('data-href') || (card.querySelector('.server-action')?.href);
      if (targetHref) {
        card.style.cursor = 'pointer';
        card.addEventListener('click', (e) => {
          // Ne pas rediriger si on clique sur le bouton d'action (éviter double redirection)
          if (!e.target.closest('.server-action')) {
            window.location.href = targetHref;
          }
        });
      }
    } else {
      // Pour les serveurs hors ligne, s'assurer que le lien de maintenance est toujours cliquable
      const maintenanceLink = card.querySelector('.server-action.maintenance');
      if (maintenanceLink) {
        // Forcer les styles pour garantir que le lien est cliquable
        maintenanceLink.style.pointerEvents = 'auto';
        maintenanceLink.style.cursor = 'pointer';
        maintenanceLink.style.position = 'relative';
        maintenanceLink.style.zIndex = '10';
        maintenanceLink.style.opacity = '1';
        
        // Empêcher la propagation du clic sur la carte pour les serveurs hors ligne
        // mais permettre le clic sur le lien de maintenance
        card.addEventListener('click', (e) => {
          // Si on clique sur le lien de maintenance, permettre le comportement par défaut
          if (e.target === maintenanceLink || e.target.closest('.server-action.maintenance')) {
            // Ne rien faire, laisser le lien fonctionner
            return;
          }
          // Sinon, empêcher tout autre clic sur la carte
          e.stopPropagation();
          e.preventDefault();
        }, true); // Utiliser capture phase pour intercepter avant
        
        // S'assurer que le clic sur le lien fonctionne même si la carte bloque
        maintenanceLink.addEventListener('click', (e) => {
          // Forcer la navigation si le href existe
          const href = maintenanceLink.getAttribute('href');
          if (href) {
            e.stopPropagation(); // Empêcher la propagation vers la carte
            window.location.href = href;
          }
        }, true);
      }
    }
  });
});