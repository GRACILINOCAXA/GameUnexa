(() => {
    class BackgroundEngine {
        constructor() {
            this.host = document.querySelector('[data-gamelink-background]');
            this.canvas = document.createElement('canvas');
            this.canvas.className = 'gamelink-background-canvas';
            this.host?.appendChild(this.canvas);
            this.context = this.canvas.getContext('2d');
            this.media = null;
            this.mediaCleanup = null;
            this.timerIds = new Set();
            this.animationId = null;
            this.config = { type: 'default', effect: 'NET', color1: '#38bdf8', color2: '#0f172a', speed: 1, opacity: 1, fps: 60 };
            this.particles = [];
            this.resize = this.resize.bind(this);
            window.addEventListener('resize', this.resize);
            this.resize();
        }

        resize() {
            if (!this.canvas) return;
            const ratio = Math.min(window.devicePixelRatio || 1, 2);
            this.canvas.width = Math.floor(window.innerWidth * ratio);
            this.canvas.height = Math.floor(window.innerHeight * ratio);
            this.canvas.style.width = `${window.innerWidth}px`;
            this.canvas.style.height = `${window.innerHeight}px`;
            this.context?.setTransform(ratio, 0, 0, ratio, 0, 0);
        }

        async apply(config = {}) {
            this.config = { ...this.config, ...config };
            this.stop();
            this.clearMedia();
            this.clearTimers();
            this.host?.classList.add('is-transitioning');
            this.setTimer(() => this.host?.classList.remove('is-transitioning'), Number(this.config.transition || 500));
            if (this.config.type === 'default') {
                this.host?.classList.add('is-default');
                this.drawDefault();
                return;
            }
            this.host?.classList.remove('is-default');
            if (['image', 'gif', 'video', 'slideshow', 'random-videos', 'random-gifs', 'online'].includes(this.config.type)) {
                this.showMedia();
            } else {
                this.canvas.hidden = false;
                this.startCanvas();
            }
        }

        drawDefault() {
            this.canvas.hidden = false;
            const { width, height } = this.canvas;
            const gradient = this.context.createLinearGradient(0, 0, width, height);
            gradient.addColorStop(0, '#07111f');
            gradient.addColorStop(1, '#0b1528');
            this.context.fillStyle = gradient;
            this.context.fillRect(0, 0, width, height);
        }

        startCanvas() {
            const isParticlePreset = this.config.type === 'particles';
            const count = Math.max(12, Math.min(240, Number(this.config.amount || (isParticlePreset ? 80 : 45))));
            this.particles = Array.from({ length: count }, (_, index) => ({
                x: Math.random() * window.innerWidth,
                y: Math.random() * window.innerHeight,
                vx: (Math.random() - 0.5) * (0.25 + Number(this.config.speed || 1)),
                vy: (Math.random() - 0.5) * (0.25 + Number(this.config.speed || 1)),
                radius: 1 + Math.random() * Math.max(1, Number(this.config.size || 3)),
                phase: index * 0.37,
            }));
            let lastFrame = 0;
            const frame = (time) => {
                const fps = Number(this.config.fps || 60);
                if (!lastFrame || time - lastFrame >= 1000 / fps) {
                    lastFrame = time;
                    this.drawFrame(time, isParticlePreset);
                }
                this.animationId = window.requestAnimationFrame(frame);
            };
            this.animationId = window.requestAnimationFrame(frame);
        }

        drawFrame(time, particlesMode) {
            const context = this.context;
            const width = window.innerWidth;
            const height = window.innerHeight;
            context.clearRect(0, 0, width, height);
            const glow = context.createRadialGradient(width * 0.5, height * 0.45, 0, width * 0.5, height * 0.45, Math.max(width, height));
            glow.addColorStop(0, this.config.color2 || '#0f172a');
            glow.addColorStop(1, '#020617');
            context.fillStyle = glow;
            context.fillRect(0, 0, width, height);
            const effect = String(this.config.effect || '').toUpperCase();
            const connect = particlesMode || ['NET', 'TOPOLOGY', 'CELLS', 'GLOBE'].includes(effect);
            const color = this.config.color1 || '#38bdf8';
            this.particles.forEach((particle, index) => {
                const movement = Number(this.config.speed || 1);
                particle.x += particle.vx * movement;
                particle.y += particle.vy * movement;
                if (effect === 'WAVES' || effect === 'FOG' || effect === 'CLOUDS') {
                    particle.y += Math.sin(time / 900 + particle.phase) * 0.35;
                }
                if (particle.x < -10) particle.x = width + 10;
                if (particle.x > width + 10) particle.x = -10;
                if (particle.y < -10) particle.y = height + 10;
                if (particle.y > height + 10) particle.y = -10;
                context.beginPath();
                context.globalAlpha = Math.max(0.12, Number(this.config.opacity || 1) * (effect === 'FOG' ? 0.3 : 0.9));
                context.fillStyle = color;
                context.arc(particle.x, particle.y, particle.radius, 0, Math.PI * 2);
                context.fill();
                if (connect) {
                    for (let next = index + 1; next < this.particles.length; next += 1) {
                        const other = this.particles[next];
                        const distance = Math.hypot(particle.x - other.x, particle.y - other.y);
                        if (distance < 125) {
                            context.beginPath();
                            context.globalAlpha = (1 - distance / 125) * 0.22 * Number(this.config.opacity || 1);
                            context.strokeStyle = color;
                            context.moveTo(particle.x, particle.y);
                            context.lineTo(other.x, other.y);
                            context.stroke();
                        }
                    }
                }
            });
            context.globalAlpha = 1;
        }

        normalizeEntries(file) {
            if (Array.isArray(file)) return file.filter(Boolean).map(String);
            if (!file) return [];
            try {
                const parsed = JSON.parse(file);
                return Array.isArray(parsed) ? parsed.filter(Boolean).map(String) : [String(file)];
            } catch (_) {
                return [String(file)];
            }
        }

        showMedia() {
            const entries = this.parseFiles();
            if (!entries.length) return this.startCanvas();
            this.canvas.hidden = true;
            const isVideo = ['video', 'random-videos'].includes(this.config.type) || entries.some((entry) => /\.(mp4|webm|mov|m4v)$/i.test(entry));
            if (isVideo) return entries.length > 1 ? this.showRandomVideos(entries) : this.showVideo(entries[0]);
            return this.showImage(entries[0]);
        }

        showImage(file) {
            const media = document.createElement('img');
            media.className = 'gamelink-background-media';
            media.setAttribute('aria-hidden', 'true');
            media.alt = '';
            media.src = this.toUrl(file);
            this.host.appendChild(media);
            this.media = media;
        }

        showVideo(file, options = {}) {
            const media = document.createElement('video');
            media.className = 'gamelink-background-media';
            media.setAttribute('aria-hidden', 'true');
            media.autoplay = true;
            media.muted = true;
            media.defaultMuted = true;
            media.loop = options.loop !== false;
            media.playsInline = true;
            media.preload = 'auto';
            media.src = this.toUrl(file);
            const play = () => {
                const playPromise = media.play();
                if (playPromise?.catch) {
                    playPromise.catch((error) => console.warn('Não foi possível iniciar o wallpaper de vídeo:', error));
                }
            };
            const onError = () => {
                console.warn('[GameUnexa Background] Vídeo indisponível:', media.src);
                media.classList.add('is-fading');
                this.host?.classList.add('is-default');
                this.canvas.hidden = false;
                this.drawDefault();
            };
            media.addEventListener('loadedmetadata', play, { once: true });
            media.addEventListener('canplay', play, { once: true });
            media.addEventListener('error', onError, { once: true });
            this.host.appendChild(media);
            this.media = media;
            this.mediaCleanup = () => {
                media.pause();
                media.removeAttribute('src');
                media.load();
                media.removeEventListener('loadedmetadata', play);
                media.removeEventListener('canplay', play);
                media.removeEventListener('error', onError);
            };
            play();
        }

        showRandomVideos(entries) {
            const order = this.config.shuffle ? [...entries].sort(() => Math.random() - 0.5) : [...entries];
            let index = 0;
            const media = document.createElement('video');
            media.className = 'gamelink-background-media';
            media.setAttribute('aria-hidden', 'true');
            media.autoplay = true;
            media.muted = true;
            media.defaultMuted = true;
            media.loop = false;
            media.playsInline = true;
            media.preload = 'auto';
            const play = () => {
                const playPromise = media.play();
                playPromise?.catch?.((error) => console.warn('Não foi possível iniciar o wallpaper de vídeo:', error));
            };
            const next = () => {
                index = (index + 1) % order.length;
                media.classList.add('is-fading');
                this.setTimer(() => {
                    media.src = this.toUrl(order[index]);
                    media.load();
                    media.addEventListener('canplay', () => {
                        media.classList.remove('is-fading');
                        play();
                    }, { once: true });
                }, 250);
            };
            const onError = () => console.warn('[GameUnexa Background] Vídeo aleatório indisponível:', media.src);
            media.addEventListener('ended', next);
            media.addEventListener('error', onError);
            media.src = this.toUrl(order[0]);
            this.host.appendChild(media);
            this.media = media;
            this.mediaCleanup = () => {
                media.pause();
                media.removeAttribute('src');
                media.load();
                media.removeEventListener('ended', next);
                media.removeEventListener('error', onError);
            };
            play();
        }

        parseFiles() {
            return this.normalizeEntries(this.config.file);
        }

        toUrl(file) {
            const value = String(file || '').trim();
            if (/^https?:\/\//i.test(value)) return value;
            const relative = value.replace(/^\/+/, '').replace(/^userdata[\\/]backgrounds[\\/]/i, '').replace(/^backgrounds[\\/]?/i, '');
            return `/userdata/backgrounds/${relative.split('\\').join('/')}`;
        }

        clearMedia() {
            this.mediaCleanup?.();
            this.mediaCleanup = null;
            this.media?.remove();
            this.media = null;
        }

        setTimer(callback, delay) {
            const timerId = window.setTimeout(() => {
                this.timerIds.delete(timerId);
                callback();
            }, delay);
            this.timerIds.add(timerId);
            return timerId;
        }

        clearTimers() {
            this.timerIds.forEach((timerId) => window.clearTimeout(timerId));
            this.timerIds.clear();
        }

        stop() { if (this.animationId) window.cancelAnimationFrame(this.animationId); this.animationId = null; }
    }
    window.BackgroundEngine = BackgroundEngine;
})();
