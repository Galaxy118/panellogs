// SÉCURITÉ: Récupère le token CSRF depuis le formulaire ou les meta tags
function getCsrfToken() {
  const csrfInput = document.querySelector('input[name="csrf_token"]');
  if (csrfInput) return csrfInput.value;
  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  if (csrfMeta) return csrfMeta.content;
  return '';
}

document.addEventListener('DOMContentLoaded', () => {
  const refreshBtn = document.getElementById('refresh-logo-btn');
  if (!refreshBtn) return;

  const feedbackEl = document.getElementById('refresh-logo-feedback');
  const previewContainer = document.getElementById('logo-preview');
  let previewImg = document.getElementById('current-logo-img');
  const defaultLabel = refreshBtn.innerHTML;
  const placeholder = document.getElementById('logo-placeholder');

  const setFeedback = (message, type) => {
    if (!feedbackEl) return;
    feedbackEl.textContent = message || '';
    feedbackEl.classList.remove('success', 'error');
    if (type) {
      feedbackEl.classList.add(type);
    }
  };

  const ensurePreviewImage = () => {
    if (previewImg && previewContainer && previewContainer.contains(previewImg)) {
      return previewImg;
    }

    if (!previewContainer) {
      return null;
    }

    previewContainer.innerHTML = '';
    const img = document.createElement('img');
    img.id = 'current-logo-img';
    img.alt = 'Logo Discord';
    previewContainer.appendChild(img);
    previewImg = img;
    return img;
  };

  refreshBtn.addEventListener('click', async () => {
    const refreshUrl = refreshBtn.dataset.refreshUrl;
    if (!refreshUrl || refreshBtn.disabled) return;

    refreshBtn.disabled = true;
    refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Rafraîchissement...';
    setFeedback('', null);

    try {
      const response = await fetch(refreshUrl, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        credentials: 'same-origin',
        body: JSON.stringify({})
      });

      let data = null;
      try {
        data = await response.json();
      } catch (_) {
        // Ignore parsing errors, handled below
      }

      if (!response.ok || !data?.success) {
        const message = data?.message || 'Impossible de rafraîchir le logo.';
        throw new Error(message);
      }

      const img = ensurePreviewImage();
      if (img) {
        const cacheBuster = `_=${Date.now()}`;
        img.src = data.logo.includes('?') ? `${data.logo}&${cacheBuster}` : `${data.logo}?${cacheBuster}`;
        img.style.opacity = '0';
        img.onload = () => {
          img.style.transition = 'opacity 0.2s ease-in-out';
          img.style.opacity = '1';
        };
      }

      if (placeholder && placeholder.parentNode) {
        placeholder.remove();
      }

      setFeedback('Logo mis à jour avec succès.', 'success');
    } catch (error) {
      console.error('Erreur lors du rafraîchissement du logo:', error);
      setFeedback(error.message || 'Impossible de rafraîchir le logo.', 'error');
    } finally {
      refreshBtn.disabled = false;
      refreshBtn.innerHTML = defaultLabel;
    }
  });
});
