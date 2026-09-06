(function () {
    'use strict';

    const state = { page: 1, perPage: 24, search: '', category: '', favorites: false, recent: false, totalPages: 1, effects: [] };
    const activeAudio = new Map();
    const MAX_ACTIVE_AUDIO = 12;
    const soundboardPeers = new Map();
    const soundEffectCache = new Map();
    let soundboardSocket = null;
    let soundboardAudioContext = null;
    let soundboardDestination = null;
    let soundboardTrack = null;
    let soundboardSelfId = '';
    let soundboardReady = false;
    let searchTimer = null;

    const root = () => document.querySelector('[data-soundboard]');
    const api = (path, options = {}) => {
        const method = (options.method || 'GET').toUpperCase();
        const headers = new Headers(options.headers || {});
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        if (csrfToken && method !== 'GET' && method !== 'HEAD') {
            headers.set('X-CSRF-Token', csrfToken);
        }
        return fetch(path, { ...options, headers }).then(async (response) => {
        const body = await response.text();
        let data;
        try {
            data = body ? JSON.parse(body) : {};
        } catch (error) {
            data = { ok: false, error: response.status === 413 ? 'Arquivo muito grande.' : 'Resposta inválida do servidor.' };
        }
        if (!response.ok && !data.error) {
            data.error = `Erro do servidor (${response.status}).`;
        }
            return { response, data };
        });
    };

    function soundboardLog(message, details) {
        if (details) console.info('[Soundboard] ' + message, details);
        else console.info('[Soundboard] ' + message);
    }

    async function ensureSoundboardAudio() {
        if (!soundboardAudioContext) {
            soundboardAudioContext = new AudioContext();
            soundboardDestination = soundboardAudioContext.createMediaStreamDestination();
            soundboardTrack = soundboardDestination.stream.getAudioTracks()[0];
        }
        if (soundboardAudioContext.state === 'suspended') await soundboardAudioContext.resume();
        return soundboardAudioContext;
    }

    function sendSoundboardSignal(payload) {
        if (soundboardSocket?.readyState === WebSocket.OPEN) soundboardSocket.send(JSON.stringify(payload));
    }

    function createSoundboardPeer(peerId, initiator) {
        if (soundboardPeers.has(peerId)) return soundboardPeers.get(peerId);
        const pc = new RTCPeerConnection({
            iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
        });
        if (soundboardTrack) pc.addTrack(soundboardTrack, soundboardDestination.stream);
        pc.onicecandidate = (event) => {
            if (event.candidate) sendSoundboardSignal({ type: 'ice-candidate', roomId: window.gameLinkCallConfig.roomSlug, to: peerId, candidate: event.candidate });
        };
        pc.ontrack = (event) => {
            const manager = window.SoundboardRemoteAudioManager;
            manager?.attach(peerId, event.streams[0]);
            soundboardLog('remote audio received', { peerId });
        };
        pc.onconnectionstatechange = () => {
            soundboardLog('peer state', { peerId, state: pc.connectionState, ice: pc.iceConnectionState, signaling: pc.signalingState });
            if (['failed', 'closed', 'disconnected'].includes(pc.connectionState)) {
                window.SoundboardRemoteAudioManager?.remove(peerId);
                soundboardPeers.delete(peerId);
            }
        };
        soundboardPeers.set(peerId, pc);
        soundboardLog('peer created', { peerId, initiator });
        if (initiator) {
            pc.createOffer().then((offer) => pc.setLocalDescription(offer).then(() => {
                sendSoundboardSignal({ type: 'offer', roomId: window.gameLinkCallConfig.roomSlug, to: peerId, description: pc.localDescription });
                soundboardLog('offer created', { peerId });
            }));
        }
        return pc;
    }

    async function initializeSoundboardWebRTC() {
        if (soundboardSocket || !window.gameLinkCallConfig) return;
        try {
            await ensureSoundboardAudio();
            window.SoundboardRemoteAudioManager = window.SoundboardRemoteAudioManager || (() => {
                const audios = new Map();
                return {
                    attach(peerId, stream) {
                        let audio = audios.get(peerId);
                        if (!audio) { audio = new Audio(); audio.autoplay = true; audio.setAttribute('playsinline', ''); audios.set(peerId, audio); }
                        audio.srcObject = stream;
                        audio.play().catch(() => setStatus('Ative o áudio para ouvir efeitos da sala.', true));
                    },
                    remove(peerId) {
                        const audio = audios.get(peerId);
                        if (!audio) return;
                        audio.pause(); audio.srcObject?.getTracks().forEach((track) => track.stop()); audio.srcObject = null; audios.delete(peerId);
                    },
                    clear() { for (const peerId of audios.keys()) this.remove(peerId); }
                };
            })();
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            soundboardSocket = new WebSocket(`${protocol}//${window.location.host}/ws/soundboard`);
            soundboardSocket.onopen = () => { soundboardReady = true; soundboardLog('joining room'); };
            soundboardSocket.onmessage = async (event) => {
                const message = JSON.parse(event.data);
                if (message.type === 'room-state') {
                    soundboardSelfId = message.selfId;
                    message.peers.forEach((peerId) => createSoundboardPeer(peerId, true));
                } else if (message.type === 'peer-joined') {
                    createSoundboardPeer(message.peerId, false);
                } else if (message.type === 'offer') {
                    const pc = createSoundboardPeer(message.from, false);
                    await pc.setRemoteDescription(message.description);
                    const answer = await pc.createAnswer();
                    await pc.setLocalDescription(answer);
                    sendSoundboardSignal({ type: 'answer', roomId: window.gameLinkCallConfig.roomSlug, to: message.from, description: pc.localDescription });
                    soundboardLog('answer received', { peerId: message.from });
                } else if (message.type === 'answer') {
                    const pc = soundboardPeers.get(message.from);
                    if (pc) await pc.setRemoteDescription(message.description);
                } else if (message.type === 'ice-candidate') {
                    const pc = soundboardPeers.get(message.from);
                    if (pc && message.candidate) await pc.addIceCandidate(message.candidate);
                } else if (message.type === 'peer-left') {
                    soundboardPeers.get(message.peerId)?.close(); soundboardPeers.delete(message.peerId); window.SoundboardRemoteAudioManager?.remove(message.peerId);
                }
            };
            soundboardSocket.onclose = () => { soundboardReady = false; soundboardSocket = null; soundboardLog('WebRTC signaling closed'); };
            soundboardLog('initializing');
        } catch (error) {
            console.error('[Soundboard] WebRTC connection failed', error);
            setStatus('Não foi possível conectar o áudio do Soundboard.', true);
        }
    }

    async function preloadEffect(effect) {
        if (soundEffectCache.has(effect.id)) return soundEffectCache.get(effect.id);
        try {
            const response = await fetch(effect.url);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const buffer = await (await ensureSoundboardAudio()).decodeAudioData(await response.arrayBuffer());
            soundEffectCache.set(effect.id, buffer);
            return buffer;
        } catch (error) {
            console.warn('[Soundboard] preload failed', effect.id, error);
            return null;
        }
    }

    function setStatus(message, error) {
        const node = root()?.querySelector('[data-soundboard-status]');
        if (node) {
            node.textContent = message || '';
            node.className = 'small mt-2 ' + (error ? 'text-danger' : 'text-info');
        }
    }

    function escapeText(value) {
        return String(value || '');
    }

    function formatDuration(seconds) {
        const duration = Number(seconds || 0);
        return duration < 10 ? duration.toFixed(1) + 's' : Math.round(duration) + 's';
    }

    function setMoreVisibility() {
        root()?.querySelector('[data-soundboard-more-wrap]')?.classList.toggle('d-none', state.page >= state.totalPages);
    }

    function renderEffects() {
        const list = root()?.querySelector('[data-soundboard-list]');
        if (!list) return;
        if (!state.effects.length) {
            list.innerHTML = '<p class="text-white-50 small mb-0">Nenhum efeito encontrado.</p>';
            setMoreVisibility();
            return;
        }
        list.innerHTML = '';
        state.effects.forEach((effect) => {
            const card = document.createElement('div');
            card.className = 'soundboard-effect';
            card.title = `${effect.name} - ${formatDuration(effect.duration)}`;
            card.dataset.effectId = effect.id;

            const play = document.createElement('button');
            play.type = 'button';
            play.className = 'w-100 border-0 bg-transparent text-start text-white p-0';
            play.innerHTML = `<span class="me-1">${escapeText(effect.icon || '🔊')}</span><span class="soundboard-effect-name"></span><span class="soundboard-effect-meta"><span></span><span></span></span>`;
            play.querySelector('.soundboard-effect-name').textContent = effect.name;
            play.querySelector('.soundboard-effect-meta span:first-child').textContent = effect.category?.name || 'Geral';
            play.querySelector('.soundboard-effect-meta span:last-child').textContent = formatDuration(effect.duration);
            play.addEventListener('click', () => playEffect(effect, card));

            const favorite = document.createElement('button');
            favorite.type = 'button';
            favorite.className = 'soundboard-favorite position-absolute top-0 end-0 m-1';
            favorite.textContent = effect.favorite ? '★' : '☆';
            favorite.title = effect.favorite ? 'Remover favorito' : 'Adicionar favorito';
            favorite.addEventListener('click', (event) => {
                event.stopPropagation();
                toggleFavorite(effect, favorite);
            });

            const volume = document.createElement('input');
            volume.type = 'range';
            volume.min = '0';
            volume.max = '100';
            volume.value = String(Math.round(Number(effect.volume ?? 1) * 100));
            volume.className = 'form-range mt-2 mb-0';
            volume.title = 'Volume do efeito';
            volume.setAttribute('aria-label', `Volume de ${effect.name}`);
            volume.addEventListener('click', (event) => event.stopPropagation());
            volume.addEventListener('change', () => saveVolume(effect, Number(volume.value) / 100));

            card.append(play, favorite, volume);
            list.appendChild(card);
        });
        setMoreVisibility();
    }

    async function loadCategories() {
        const result = await api('/api/soundboard/categories');
        if (!result.data.ok) return;
        const container = root()?.querySelector('[data-soundboard-categories]');
        if (!container) return;
        container.querySelectorAll('[data-soundboard-category]:not([data-soundboard-category=""])').forEach((node) => node.remove());
        result.data.categories.forEach((category) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'btn btn-sm btn-outline-info';
            button.dataset.soundboardCategory = category.slug;
            button.textContent = `${category.icon || '🎵'} ${category.name}`;
            button.addEventListener('click', () => selectCategory(category.slug, button));
            container.appendChild(button);
        });
    }

    async function loadEffects(reset) {
        if (reset) {
            state.page = 1;
            state.effects = [];
        }
        const params = new URLSearchParams({ page: state.page, per_page: state.perPage });
        if (state.search) params.set('search', state.search);
        if (state.category) params.set('category', state.category);
        if (state.favorites) params.set('favorites', '1');
        if (state.recent) params.set('recent', '1');
        try {
            const result = await api('/api/soundboard?' + params.toString());
            if (!result.data.ok) throw new Error('Não foi possível carregar os efeitos.');
            state.totalPages = result.data.total_pages || 1;
            state.effects = reset ? result.data.effects : state.effects.concat(result.data.effects);
            renderEffects();
            state.effects.slice(0, 5).forEach((effect) => preloadEffect(effect));
            setStatus('');
        } catch (error) {
            setStatus(error.message, true);
        }
    }

    function selectCategory(category, button) {
        state.category = category;
        root()?.querySelectorAll('[data-soundboard-category]').forEach((node) => node.classList.toggle('active', node === button || node.dataset.soundboardCategory === category && node === button));
        loadEffects(true);
    }

    async function playEffect(effect, card) {
        const previous = activeAudio.get(effect.id);
        if (previous) {
            try { previous.stop(); } catch (error) { /* source already ended */ }
        }
        while (activeAudio.size >= MAX_ACTIVE_AUDIO) {
            const oldest = activeAudio.keys().next().value;
            const audioToStop = activeAudio.get(oldest);
            try { audioToStop?.stop(); } catch (error) { /* source already ended */ }
            activeAudio.delete(oldest);
            document.querySelector(`[data-effect-id="${oldest}"]`)?.classList.remove('is-playing');
        }
        const audioContext = await ensureSoundboardAudio();
        const audioBuffer = await preloadEffect(effect);
        if (!audioBuffer) {
            setStatus('Não foi possível carregar este efeito.', true);
            return;
        }
        const source = audioContext.createBufferSource();
        const gain = audioContext.createGain();
        gain.gain.value = Math.max(0, Math.min(1, Number(effect.volume ?? 1)));
        source.buffer = audioBuffer;
        source.connect(gain);
        gain.connect(audioContext.destination);
        gain.connect(soundboardDestination);
        activeAudio.set(effect.id, source);
        card.classList.add('is-playing');
        setStatus(`🔊 Tocando: ${effect.name}`);
        source.addEventListener('ended', () => {
            card.classList.remove('is-playing');
            activeAudio.delete(effect.id);
            setStatus('');
        }, { once: true });
        try {
            source.start();
            sendSoundboardSignal({ type: 'play', roomId: window.gameLinkCallConfig.roomSlug, effectId: effect.id, timestamp: Date.now() });
            api(`/api/soundboard/${effect.id}/play`, { method: 'POST', keepalive: true }).catch(() => {});
        } catch (error) {
            card.classList.remove('is-playing');
            activeAudio.delete(effect.id);
            setStatus('O navegador bloqueou a reprodução deste áudio.', true);
        }
    }

    async function toggleFavorite(effect, button) {
        const method = effect.favorite ? 'DELETE' : 'POST';
        const result = await api(`/api/soundboard/${effect.id}/favorite`, { method });
        if (!result.data.ok) return;
        effect.favorite = result.data.favorite;
        button.textContent = effect.favorite ? '★' : '☆';
        button.title = effect.favorite ? 'Remover favorito' : 'Adicionar favorito';
        if (state.favorites && !effect.favorite) loadEffects(true);
    }

    async function saveVolume(effect, volume) {
        const result = await api(`/api/soundboard/${effect.id}/volume`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ volume })
        });
        if (result.data.ok) effect.volume = result.data.volume;
    }

    function bindForm() {
        const modalElement = document.getElementById('soundboardAddModal');
        const form = root()?.parentElement?.querySelector('[data-soundboard-form]') || document.querySelector('[data-soundboard-form]');
        const addButton = root()?.querySelector('[data-soundboard-add]');
        const submitButton = form?.querySelector('[data-soundboard-submit]');
        const fileInput = form?.querySelector('[name="file"]');
        const fileName = form?.querySelector('[data-soundboard-file-name]');
        if (!form || !addButton || !modalElement) return;
        const modal = bootstrap.Modal.getOrCreateInstance(modalElement);
        addButton.addEventListener('click', () => { form.reset(); if (fileName) fileName.textContent = ''; modal.show(); });
        fileInput?.addEventListener('change', () => {
            if (fileName) fileName.textContent = fileInput.files[0] ? `Arquivo selecionado: ${fileInput.files[0].name}` : '';
        });
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const status = form.querySelector('[data-soundboard-form-status]');
            const file = form.querySelector('[name="file"]')?.files[0];
            status.textContent = '';
            if (!form.reportValidity()) return;
            if (!file) {
                status.textContent = 'Selecione um arquivo de áudio.';
                return;
            }
            if (file.size > 15 * 1024 * 1024) {
                status.textContent = 'Arquivo de áudio muito grande. Máximo de 15 MB.';
                return;
            }
            if (submitButton) {
                submitButton.disabled = true;
                submitButton.textContent = 'Adicionando efeito...';
            }
            try {
                const result = await api('/api/soundboard', { method: 'POST', body: new FormData(form) });
                if (!result.data.ok) {
                    status.textContent = result.data.error || 'Não foi possível adicionar o efeito.';
                    return;
                }
                state.effects.unshift(result.data.effect);
                renderEffects();
                modal.hide();
                setStatus('Efeito adicionado.');
            } catch (error) {
                status.textContent = 'Não foi possível concluir o upload. Verifique sua conexão e tente novamente.';
            } finally {
                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.textContent = 'Adicionar efeito';
                }
            }
        });
    }

    function bindControls() {
        const container = root();
        const search = container?.querySelector('[data-soundboard-search]');
        const favorites = container?.querySelector('[data-soundboard-favorites]');
        const recent = container?.querySelector('[data-soundboard-recent]');
        const more = container?.querySelector('[data-soundboard-more]');
        const all = container?.querySelector('[data-soundboard-category=""]');
        search?.addEventListener('input', (event) => {
            window.clearTimeout(searchTimer);
            searchTimer = window.setTimeout(() => { state.search = event.target.value.trim(); loadEffects(true); }, 250);
        });
        favorites?.addEventListener('click', () => {
            state.favorites = !state.favorites;
            state.recent = false;
            favorites.classList.toggle('active', state.favorites);
            recent?.classList.remove('active');
            loadEffects(true);
        });
        recent?.addEventListener('click', () => {
            state.recent = !state.recent;
            state.favorites = false;
            recent.classList.toggle('active', state.recent);
            favorites?.classList.remove('active');
            loadEffects(true);
        });
        all?.addEventListener('click', () => {
            state.category = '';
            state.favorites = false;
            state.recent = false;
            favorites?.classList.remove('active');
            recent?.classList.remove('active');
            container.querySelectorAll('[data-soundboard-category]').forEach((node) => node.classList.toggle('active', node === all));
            loadEffects(true);
        });
        more?.addEventListener('click', () => { state.page += 1; loadEffects(false); });
    }

    document.addEventListener('DOMContentLoaded', () => {
        if (!root()) return;
        bindControls();
        bindForm();
        initializeSoundboardWebRTC();
        loadCategories();
        loadEffects(true);
    });

    window.addEventListener('pagehide', () => {
        for (const peer of soundboardPeers.values()) peer.close();
        soundboardPeers.clear();
        window.SoundboardRemoteAudioManager?.clear();
        soundboardSocket?.close();
        soundboardAudioContext?.close();
    });
})();
