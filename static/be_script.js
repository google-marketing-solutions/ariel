if ('serviceWorker' in navigator) {
    console.log('Service Worker is supported');
    window.addEventListener('load', () => {
        console.log('Window loaded, registering service worker...');
        navigator.serviceWorker.register('/static/sw.js').then(registration => {
            console.log('ServiceWorker registration successful with scope: ', registration.scope);
        }, err => {
            console.log('ServiceWorker registration failed: ', err);
        });
    });
} else {
    console.log('Service Worker is not supported');
}
