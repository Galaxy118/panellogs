// Variables globales pour Turnstile
let widgetId = null;
let currentToken = null;
let turnstileInitialized = false;

// Fonction d'initialisation Turnstile exposée globalement
window.initTurnstile = function() {
    if (turnstileInitialized) {
        return;
    }
    
    const container = document.getElementById('turnstile-container');
    if (!container || !window.turnstile) {
        console.warn('Turnstile: container ou API non disponible');
        return;
    }
    
    const siteKey = container.dataset.sitekey;
    if (!siteKey) {
        console.warn('Turnstile: site key manquant');
        return;
    }
    
    const config = window.turnstileConfig || {};
    const messages = config.messages || {};
    const accessBtn = document.getElementById('access-btn');
    
    try {
        widgetId = window.turnstile.render(container, {
            sitekey: siteKey,
            theme: 'dark',
            callback: (token) => {
                currentToken = token;
                // Activer le bouton
                if (accessBtn) {
                    accessBtn.disabled = false;
                }
                // Effacer les messages d'erreur
                const feedbackEl = document.getElementById('turnstile-feedback');
                if (feedbackEl) {
                    feedbackEl.textContent = '';
                    feedbackEl.classList.remove('error', 'success');
                }
            },
            'expired-callback': () => {
                currentToken = null;
                // Désactiver le bouton
                if (accessBtn) {
                    accessBtn.disabled = true;
                }
                const feedbackEl = document.getElementById('turnstile-feedback');
                if (feedbackEl) {
                    feedbackEl.textContent = messages.expired || 'La vérification a expiré, veuillez recommencer.';
                    feedbackEl.classList.add('error');
                    feedbackEl.classList.remove('success');
                }
            },
            'error-callback': () => {
                currentToken = null;
                // Désactiver le bouton
                if (accessBtn) {
                    accessBtn.disabled = true;
                }
                const feedbackEl = document.getElementById('turnstile-feedback');
                if (feedbackEl) {
                    feedbackEl.textContent = messages.error || 'Erreur Turnstile, veuillez réessayer.';
                    feedbackEl.classList.add('error');
                    feedbackEl.classList.remove('success');
                }
            }
        });
        turnstileInitialized = true;
    } catch (error) {
        console.error('Erreur lors du rendu Turnstile:', error);
    }
};

document.addEventListener('DOMContentLoaded', () => {
    const accessBtn = document.getElementById('access-btn');
    const feedbackEl = document.getElementById('turnstile-feedback');
    const config = window.turnstileConfig || {};
    const verifyUrl = config.verifyUrl || '/captcha/verify';
    const redirectUrl = config.redirectUrl || '/';
    const messages = config.messages || {};
    
    const setFeedback = (message, isError = true) => {
        if (!feedbackEl) return;
        feedbackEl.textContent = message || '';
        feedbackEl.classList.remove('success', 'error');
        if (message) {
            feedbackEl.classList.add(isError ? 'error' : 'success');
        }
    };
    
    // Initialiser Turnstile si déjà chargé
    if (window.turnstile && typeof window.turnstile.render === 'function') {
        window.initTurnstile();
    }
    
    // Gestion du clic sur le bouton d'accès
    if (accessBtn) {
        accessBtn.addEventListener('click', async () => {
            if (!currentToken) {
                setFeedback(messages.missing || 'Veuillez compléter la vérification de sécurité.');
                return;
            }
            
            // Désactiver le bouton et afficher le chargement
            accessBtn.disabled = true;
            accessBtn.classList.add('loading');
            
            try {
                const response = await fetch(verifyUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({
                        token: currentToken,
                        action: 'entry'
                    })
                });
                
                const data = await response.json().catch(() => ({}));
                
                if (!response.ok || !data.success) {
                    throw new Error(data?.message || messages.error || 'Impossible de valider la vérification.');
                }
                
                // Succès - afficher le message et rediriger
                setFeedback(messages.success || 'Vérification réussie ! Redirection...', false);
                
                // Redirection après un court délai pour montrer le message de succès
                setTimeout(() => {
                    window.location.href = redirectUrl;
                }, 500);
                
            } catch (error) {
                setFeedback(error.message || messages.error || 'Une erreur est survenue.', true);
                
                // Réinitialiser le captcha en cas d'erreur
                if (window.turnstile && widgetId !== null) {
                    window.turnstile.reset(widgetId);
                }
                currentToken = null;
                accessBtn.disabled = true;
            } finally {
                accessBtn.classList.remove('loading');
            }
        });
    }
});

