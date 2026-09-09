(function () {
    'use strict';

    let jitsiApi = null;
    let jitsiParticipantCount = 0;

    function log(message, details) {
        if (details) {
            console.info('[GameLink Jitsi] ' + message, details);
        } else {
            console.info('[GameLink Jitsi] ' + message);
        }
    }

    function status(message, kind) {
        const node = document.querySelector('[data-jitsi-status]');
        if (!node) {
            return;
        }
        node.innerHTML = '';
        if (!message) {
            return;
        }
        const alert = document.createElement('div');
        alert.className = 'alert alert-' + (kind || 'info') + ' py-2 px-3 mb-0';
        alert.textContent = message;
        node.appendChild(alert);
    }

    function updateJitsiParticipantCount() {
        const node = document.querySelector('[data-jitsi-participant-count]');
        if (node) {
            node.textContent = String(jitsiParticipantCount);
        }
    }

    function addFallback() {
        const node = document.querySelector('[data-jitsi-status]');
        if (!node || node.querySelector('[data-jitsi-fallback]')) {
            return;
        }
        const link = document.createElement('a');
        link.href = window.gameLinkCallConfig.fallbackUrl;
        link.target = '_blank';
        link.rel = 'noopener';
        link.className = 'btn btn-outline-light btn-sm mt-2';
        link.dataset.jitsiFallback = 'true';
        link.textContent = 'Abrir chamada em nova aba';
        node.appendChild(link);
    }

    function bindJitsiEvents() {
        jitsiApi.addListener('videoConferenceJoined', function (event) {
            log('Entrada na reunião', event);
            jitsiParticipantCount = 1;
            updateJitsiParticipantCount();
            status('', 'info');
        });
        jitsiApi.addListener('videoConferenceLeft', function () {
            log('Saída da reunião');
            jitsiParticipantCount = 0;
            updateJitsiParticipantCount();
        });
        jitsiApi.addListener('participantJoined', function (event) {
            log('Participante Jitsi entrou', event);
            jitsiParticipantCount += 1;
            updateJitsiParticipantCount();
        });
        jitsiApi.addListener('participantLeft', function (event) {
            log('Participante Jitsi saiu', event);
            jitsiParticipantCount = Math.max(0, jitsiParticipantCount - 1);
            updateJitsiParticipantCount();
        });
        jitsiApi.addListener('cameraError', function (event) {
            console.error('[GameLink Jitsi] Erro de câmera:', event);
            status('Não foi possível acessar sua câmera. Verifique as permissões do navegador.', 'warning');
        });
        jitsiApi.addListener('microphoneError', function (event) {
            console.error('[GameLink Jitsi] Erro de microfone:', event);
            status('Não foi possível acessar seu microfone. Verifique as permissões do navegador.', 'warning');
        });
        jitsiApi.addListener('readyToClose', function () {
            log('Jitsi pronto para fechar');
        });
    }

    function destroyJitsi() {
        if (jitsiApi) {
            jitsiApi.dispose();
            jitsiApi = null;
            log('Instância encerrada');
        }
    }

    function initializeJitsi() {
        const config = window.gameLinkCallConfig;
        const container = document.getElementById('jitsi-meet');
        if (!config || !container || jitsiApi) {
            return;
        }
        if (typeof window.JitsiMeetExternalAPI !== 'function') {
            console.error('[GameLink Jitsi] API não carregada');
            status('Não foi possível carregar a sala de vídeo. Tente novamente.', 'danger');
            addFallback();
            return;
        }

        log('API carregada');
        try {
            jitsiApi = new window.JitsiMeetExternalAPI('meet.jit.si', {
                roomName: config.roomName,
                parentNode: container,
                width: '100%',
                height: '100%',
                userInfo: {
                    displayName: config.displayName,
                    email: config.email
                },
                configOverwrite: {
                    prejoinPageEnabled: false,
                    disableDeepLinking: true
                },
                interfaceConfigOverwrite: {
                    TOOLBAR_BUTTONS: [
                        'microphone', 'camera', 'desktop', 'chat', 'raisehand',
                        'tileview', 'fullscreen', 'settings', 'hangup'
                    ]
                },
                devices: {
                    audioInput: '',
                    audioOutput: '',
                    videoInput: ''
                }
            });
            const jitsiFrame = container.querySelector('iframe');
            if (jitsiFrame) {
                jitsiFrame.setAttribute('allow', 'camera; microphone; display-capture; fullscreen; autoplay; clipboard-read; clipboard-write');
                jitsiFrame.setAttribute('allowfullscreen', 'true');
            }
            bindJitsiEvents();
            log('Sala inicializada: ' + config.roomName);
        } catch (error) {
            jitsiApi = null;
            console.error('[GameLink Jitsi] Erro ao inicializar sala:', error);
            status('Não foi possível carregar a sala de vídeo. Tente novamente.', 'danger');
            addFallback();
        }
    }

    window.addEventListener('beforeunload', destroyJitsi);
    window.addEventListener('pagehide', destroyJitsi);
    document.addEventListener('DOMContentLoaded', function () {
        initializeJitsi();
    });
})();
