(() => {
    if (window.__gameLinkCoverLoader) return;

    const pendingIds = new Set();
    const requestedIds = new Set();
    const retryCounts = new Map();
    let flushTimer = null;

    function coverImages() {
        return Array.from(document.querySelectorAll('[data-lazy-cover][data-cover-game-id]'));
    }

    function updateImages(gameId, cover) {
        coverImages()
            .filter((image) => image.dataset.coverGameId === String(gameId))
            .forEach((image) => {
                image.src = cover.url;
                image.dataset.coverState = cover.status;
                image.removeAttribute('data-src');
            });
    }

    function installFallback(image) {
        image.addEventListener('error', () => {
            if (image.dataset.coverState === 'fallback') return;
            image.dataset.coverState = 'fallback';
            image.removeAttribute('data-src');
            image.src = image.dataset.coverFallback || '';
        }, { once: true });
    }

    async function loadBatch(ids) {
        ids.forEach((id) => requestedIds.add(id));
        const response = await fetch(`/api/library/covers?ids=${encodeURIComponent(ids.join(','))}`, {
            credentials: 'same-origin',
            headers: { 'X-Requested-With': 'GameUnexa-Cover-Loader' },
        });
        if (!response.ok) return;
        const payload = await response.json();
        const covers = payload.covers || {};
        Object.entries(covers).forEach(([gameId, cover]) => {
            if (cover.status === 'cached' && cover.url) {
                updateImages(gameId, cover);
                return;
            }

            const retries = retryCounts.get(gameId) || 0;
            if (retries < 10) {
                retryCounts.set(gameId, retries + 1);
                window.setTimeout(() => queueIds([gameId], true), 1500);
            } else {
                updateImages(gameId, { url: cover.url, status: 'unavailable' });
            }
        });
    }

    function flush() {
        flushTimer = null;
        if (!pendingIds.size) return;
        const ids = Array.from(pendingIds);
        pendingIds.clear();
        loadBatch(ids).catch(() => {});
    }

    function queueIds(ids, force = false) {
        ids.filter((id) => id && (force || !requestedIds.has(id))).forEach((id) => pendingIds.add(id));
        if (!flushTimer) flushTimer = window.setTimeout(flush, 80);
    }

    function observeImages() {
        const images = coverImages();
        if (!images.length) return;
        const observer = 'IntersectionObserver' in window
            ? new IntersectionObserver((entries) => {
                const visibleIds = entries
                    .filter((entry) => entry.isIntersecting)
                    .map((entry) => entry.target.dataset.coverGameId);
                queueIds(visibleIds);
            }, { rootMargin: '300px 0px' })
            : null;

        images.forEach((image) => {
            installFallback(image);
            if (observer) observer.observe(image);
            else queueIds([image.dataset.coverGameId]);
        });
    }

    window.__gameLinkCoverLoader = { queueIds, observeImages };
    document.addEventListener('DOMContentLoaded', observeImages, { once: true });
})();
