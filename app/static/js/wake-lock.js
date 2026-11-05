document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('wake-lock-toggle');
    if (!toggle) return;
    let wakeLock = null;

    async function requestWakeLock() {
        if (!('wakeLock' in navigator) || wakeLock) return;
        try {
            wakeLock = await navigator.wakeLock.request('screen');
            wakeLock.addEventListener('release', () => { wakeLock = null; });
        } catch (error) {
            console.error('Failed to acquire wake lock:', error);
            wakeLock = null;
        }
    }

    async function releaseWakeLock() {
        if (!wakeLock) return;
        try { await wakeLock.release(); } catch (error) { console.error('Failed to release wake lock:', error); }
        wakeLock = null;
    }

    toggle.addEventListener('change', () => toggle.checked ? requestWakeLock() : releaseWakeLock());
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible' && toggle.checked) requestWakeLock();
    });
});