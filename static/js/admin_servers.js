function updateServerStatus() {
  fetch('/api/servers/status')
    .then(response => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then(data => {
      Object.keys(data).forEach(serverId => {
        const serverData = data[serverId];
        const statusBadge = document.querySelector(`[data-server-id="${serverId}"] .status-badge`);
        if (statusBadge) {
          statusBadge.className = `status-badge ${serverData.status === 'online' ? 'status-online' : 'status-offline'}`;
          statusBadge.innerHTML = `<i class="fas fa-circle me-1"></i>${serverData.status === 'online' ? 'Online' : 'Offline'}`;
        }
      });
    })
    .catch(error => console.error('Erreur lors de la mise à jour du statut:', error));
}

// SÉCURITÉ: Récupère le token CSRF depuis le formulaire ou les meta tags
function getCsrfToken() {
  const csrfInput = document.querySelector('input[name="csrf_token"]');
  if (csrfInput) return csrfInput.value;
  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  if (csrfMeta) return csrfMeta.content;
  return '';
}

// Gestion du formulaire de création de serveur
document.addEventListener('DOMContentLoaded', function() {
  const createServerForm = document.getElementById('createServerForm');
  if (createServerForm) {
    createServerForm.addEventListener('submit', function(e) {
      e.preventDefault();
      
      const formData = new FormData(this);
      
      fetch('/admin/servers/create', {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCsrfToken()
        },
        body: formData
      })
      .then(response => response.json())
      .then(result => {
        if (result.success) {
          alert('Serveur créé avec succès!');
          location.reload();
        } else {
          alert('Erreur: ' + result.error);
        }
      })
      .catch(error => {
        console.error('Erreur:', error);
        alert('Erreur lors de la création du serveur');
      });
    });
  }

  // Gestion de la suppression de serveur
  let serverToDelete = null;
  
  window.confirmDeleteServer = function(serverId, serverName) {
    serverToDelete = serverId;
    document.getElementById('deleteServerName').textContent = serverName;
    const deleteModal = new bootstrap.Modal(document.getElementById('deleteServerModal'));
    deleteModal.show();
  };
  
  const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
  if (confirmDeleteBtn) {
    confirmDeleteBtn.addEventListener('click', function() {
      if (serverToDelete) {
        fetch(`/admin/servers/${serverToDelete}/delete`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
          }
        })
        .then(response => response.json())
        .then(result => {
          if (result.success) {
            alert('Serveur supprimé avec succès!');
            location.reload();
          } else {
            alert('Erreur: ' + result.error);
          }
        })
        .catch(error => {
          console.error('Erreur:', error);
          alert('Erreur lors de la suppression du serveur');
        });
      }
    });
  }

  // Mettre à jour les statuts toutes les 2 minutes
  setInterval(updateServerStatus, 120000);
  
  // Première mise à jour après 3 secondes
  setTimeout(updateServerStatus, 3000);
  
  // Mise à jour lors du focus de la page
  let lastFocusUpdate = 0;
  document.addEventListener('visibilitychange', function() {
    if (!document.hidden) {
      const now = Date.now();
      if (now - lastFocusUpdate > 30000) {
        setTimeout(updateServerStatus, 1000);
        lastFocusUpdate = now;
      }
    }
  });
});