(() => {
    const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || '';
    const request = async (url, options = {}) => {
        const headers = { 'X-CSRF-Token': csrf(), ...(options.headers || {}) };
        const response = await fetch(url, { ...options, headers });
        const data = await response.json();
        if (!response.ok || data.ok === false) throw new Error(data.erro || 'Não foi possível salvar o fundo.');
        return data;
    };

    class BackgroundManager {
        constructor() {
            this.engine = new window.BackgroundEngine();
            this.config = {};
            this.form = document.querySelector('[data-background-form]');
            this.bind();
            request('/api/background').then((data) => { this.config = data.background; this.engine.apply(this.config); this.fill(this.config); }).catch(() => {});
        }

        bind() {
            this.form?.addEventListener('input', () => this.preview());
            this.form?.addEventListener('change', () => this.preview());
            document.querySelector('[data-background-save]')?.addEventListener('click', () => this.save());
            document.querySelector('[data-background-reset]')?.addEventListener('click', () => this.reset());
            document.querySelectorAll('[data-background-upload]').forEach((input) => input.addEventListener('change', (event) => this.upload(event.target)));
            document.querySelectorAll('[data-background-folder]').forEach((button) => button.addEventListener('click', () => this.selectFolder(button.dataset.backgroundFolder)));
            document.querySelectorAll('[data-wallpaper]').forEach((button) => button.addEventListener('click', () => this.chooseOnline(button.dataset.wallpaper)));
        }

        read() {
            const data = Object.fromEntries(new FormData(this.form).entries());
            data.opacity = Number(data.opacity || 1);
            data.speed = Number(data.speed || 1);
            data.fps = Number(data.fps || 60);
            data.shuffle = Boolean(data.shuffle);
            return { ...this.config, ...data };
        }

        fill(config) {
            if (!this.form) return;
            Object.entries(config).forEach(([key, value]) => {
                const field = this.form.elements.namedItem(key);
                if (!field) return;
                if (field.type === 'checkbox') field.checked = Boolean(value);
                else field.value = value ?? '';
            });
            this.form.querySelectorAll('[data-value-for]').forEach((output) => {
                const field = this.form.elements.namedItem(output.dataset.valueFor);
                if (field) output.textContent = field.value;
            });
        }

        preview() {
            const config = this.read();
            this.form?.querySelectorAll('[data-value-for]').forEach((output) => {
                const field = this.form.elements.namedItem(output.dataset.valueFor);
                if (field) output.textContent = field.value;
            });
            this.engine.apply(config);
        }

        async save() {
            try {
                const data = await request('/api/background', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.read()) });
                this.config = data.background;
                this.engine.apply(this.config);
                this.notify('Fundo salvo.');
            } catch (error) { this.notify(error.message, true); }
        }

        async reset() {
            try {
                const data = await request('/api/background/reset', { method: 'POST' });
                this.config = data.background;
                this.fill(this.config);
                this.engine.apply(this.config);
                this.notify('Fundo padrão restaurado.');
            } catch (error) { this.notify(error.message, true); }
        }

        async upload(input) {
            if (!input.files?.[0]) return;
            const formData = new FormData();
            formData.append('file', input.files[0]);
            try {
                const data = await request('/api/background/upload', { method: 'POST', body: formData });
                const type = input.dataset.backgroundUpload;
                this.config = { ...this.config, type, file: data.file };
                this.fill(this.config);
                this.preview();
                this.notify('Arquivo importado para userdata/backgrounds.');
            } catch (error) { this.notify(error.message, true); }
        }

        async selectFolder(kind) {
            try {
                const data = await request('/api/background/select-folder', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind }) });
                this.config = { ...this.config, type: kind, folder: data.folder, file: JSON.stringify(data.files) };
                this.fill(this.config);
                this.preview();
                this.notify(`${data.files.length} arquivo(s) importado(s).`);
            } catch (error) { this.notify(error.message, true); }
        }

        chooseOnline(url) {
            this.config = { ...this.config, type: 'online', file: url };
            this.fill(this.config);
            this.preview();
        }

        notify(message, error = false) {
            const target = document.querySelector('[data-background-status]');
            if (target) { target.textContent = message; target.className = `background-status ${error ? 'is-error' : 'is-success'}`; }
        }
    }
    window.addEventListener('DOMContentLoaded', () => {
        if (document.querySelector('[data-gamelink-background]')) {
            // FIX Issue #14: Check if instance already exists to prevent double initialization
            if (!window.backgroundManager) {
                window.backgroundManager = new BackgroundManager();
            }
        }
    });
})();
