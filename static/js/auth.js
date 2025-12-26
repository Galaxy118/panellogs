// Auth.js - Page d'authentification Discord
// Le captcha Turnstile est maintenant géré sur la page d'entrée du site

document.addEventListener('DOMContentLoaded', () => {
    // Animation au survol de la carte
    const authCard = document.querySelector('.auth-card');
    if (authCard) {
        authCard.addEventListener('mouseenter', () => {
            authCard.style.transform = 'translateY(-5px)';
        });
        authCard.addEventListener('mouseleave', () => {
            authCard.style.transform = 'translateY(0)';
        });
    }
});
