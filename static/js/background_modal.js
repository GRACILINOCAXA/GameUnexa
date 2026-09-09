(() => {
    window.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('[data-background-tab]').forEach((tab) => tab.addEventListener('click', () => {
            const target = tab.dataset.backgroundTab;
            document.querySelectorAll('[data-background-tab], [data-background-panel]').forEach((element) => element.classList.remove('active'));
            tab.classList.add('active');
            document.querySelector(`[data-background-panel="${target}"]`)?.classList.add('active');
        }));
    });
})();
