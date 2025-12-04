// Configuración del frontend para Docker
// Este archivo puede ser sobrescrito o usado para configurar la URL de la API

// Detectar si estamos en Docker o en desarrollo local
const hostname = window.location.hostname;
const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:';

// Función para obtener la URL de la API
function getApiUrl() {
    // Si ya está configurado, usarlo
    if (window.CHAT_CONFIG && window.CHAT_CONFIG.apiUrl) {
        return window.CHAT_CONFIG.apiUrl;
    }
    
    // Si estamos en localhost o 127.0.0.1, usar localhost:8000
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
        return 'http://localhost:8000/api/chat';
    }
    
    // En otros casos (Docker, producción), usar el mismo hostname con puerto 8000
    return `${protocol}//${hostname}:8000/api/chat`;
}

// Configuración por defecto
window.CHAT_CONFIG = window.CHAT_CONFIG || {
    apiUrl: getApiUrl(),
    sessionId: 'chat-session-' + Date.now(),
    typingDelay: 500
};

// Log para debug
console.log('Chat Config:', window.CHAT_CONFIG);

