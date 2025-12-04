// Configuración del widget de chat
// Usa window.CHAT_CONFIG si está disponible (configurado en config.js o desde Laravel)
const CHAT_CONFIG = window.CHAT_CONFIG || {
    apiUrl: 'http://localhost:8000/api/chat', // Fallback por defecto
    sessionId: 'chat-session-' + Date.now(),
    typingDelay: 500, // Delay antes de mostrar "escribiendo..."
};

// Log para debug
console.log('Chat Widget Config:', CHAT_CONFIG);

// Elementos del DOM
const chatToggle = document.getElementById('chatToggle');
const chatWidget = document.getElementById('chatWidget');
const chatClose = document.getElementById('chatClose');
const chatInput = document.getElementById('chatInput');
const chatSend = document.getElementById('chatSend');
const chatMessages = document.getElementById('chatMessages');

// Estado del chat
let isOpen = false;
let isLoading = false;
let menuLoaded = false; // Flag para saber si ya se cargó el menú inicial

// Inicializar eventos
function initChat() {
    // Toggle del botón flotante
    chatToggle.addEventListener('click', () => {
        openChat();
    });

    // Cerrar chat
    chatClose.addEventListener('click', () => {
        closeChat();
    });

    // Enviar mensaje con Enter
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Enviar mensaje con botón
    chatSend.addEventListener('click', () => {
        sendMessage();
    });

    // Auto-focus en el input cuando se abre el chat
    chatWidget.addEventListener('transitionend', () => {
        if (isOpen) {
            chatInput.focus();
        }
    });
}

// Cargar menú inicial
async function loadInitialMenu() {
    if (menuLoaded) return;
    
    try {
        // Primero mostrar mensaje de bienvenida
        addMessage('¡Hola! 👋\n\nSoy el bot del IPECD (Instituto Provincial de Estadística y Censos de Corrientes). Estoy aquí para ayudarte a encontrar información estadística y datos de nuestra provincia.\n\n¿En qué puedo ayudarte?', false);
        
        // Esperar un momento antes de mostrar el menú
        await new Promise(resolve => setTimeout(resolve, 800));
        
        isLoading = true;
        showTypingIndicator();
        
        // Enviar un mensaje vacío o especial para obtener el menú inicial
        const response = await fetch(CHAT_CONFIG.apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: '', // Mensaje vacío para obtener el menú inicial
                session_id: CHAT_CONFIG.sessionId
            }),
            mode: 'cors',
            credentials: 'omit'
        });
        
        if (!response.ok) {
            throw new Error(`Error ${response.status}`);
        }
        
        const data = await response.json();
        
        hideTypingIndicator();
        
        // Agregar menú inicial
        if (data.response) {
            console.log('Response received:', data.response.substring(0, 200));
            
            // Detectar si es un menú: debe tener al menos 2 opciones numeradas consecutivas
            const menuPattern = /^\d+\.\s+\S+/gm;
            const menuMatches = data.response.match(menuPattern);
            const isMenu = menuMatches && menuMatches.length >= 2;
            
            console.log('Is menu?', isMenu, 'Menu matches:', menuMatches ? menuMatches.length : 0);
            console.log('Menu matches:', menuMatches);
            
            // Si no se detecta como menú pero tiene formato de menú, forzar detección
            if (!isMenu && menuMatches && menuMatches.length >= 1) {
                console.log('Forcing menu detection for single option');
            }
            
            addMessage(data.response, false, isMenu);
            menuLoaded = true;
        } else {
            console.error('No response received from API');
            addMessage('Error: No se pudo cargar el menú. Por favor recarga la página.', false);
        }
        
    } catch (error) {
        console.error('Error al cargar menú inicial:', error);
        hideTypingIndicator();
    } finally {
        isLoading = false;
    }
}

// Abrir el chat
function openChat() {
    if (isOpen) return;
    
    isOpen = true;
    chatWidget.classList.add('open');
    chatToggle.classList.add('hidden');
    chatInput.focus();
    
    // Cargar menú inicial cuando se abre el chat por primera vez
    // Usar un pequeño delay para asegurar que el DOM esté listo
    setTimeout(() => {
        if (!menuLoaded && chatMessages.children.length === 0) {
            loadInitialMenu();
        }
    }, 100);
}

// Cerrar el chat
function closeChat() {
    if (!isOpen) return;
    
    isOpen = false;
    chatWidget.classList.remove('open');
    chatToggle.classList.remove('hidden');
}

// Renderizar markdown básico
function renderMarkdown(text, container) {
    container.innerHTML = ''; // Limpiar contenido existente
    const lines = text.split('\n');
    let currentElement = null;
    let inTable = false;
    let tableRows = [];
    let inCodeBlock = false;
    let codeBlockLines = [];
    let codeBlockLanguage = '';
    
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const trimmedLine = line.trim();
        const nextLine = i + 1 < lines.length ? lines[i + 1].trim() : '';
        
        // Saltar líneas vacías al inicio
        if (!trimmedLine && container.children.length === 0 && !inCodeBlock && !inTable) continue;
        
        // Bloques de código multilínea (```language o ```)
        if (trimmedLine.startsWith('```')) {
            if (!inCodeBlock) {
                // Inicio de bloque de código
                inCodeBlock = true;
                codeBlockLines = [];
                codeBlockLanguage = trimmedLine.replace(/^```/, '').trim();
            } else {
                // Fin de bloque de código
                inCodeBlock = false;
                const codeBlock = document.createElement('pre');
                codeBlock.className = 'message-code-block';
                const code = document.createElement('code');
                code.textContent = codeBlockLines.join('\n');
                codeBlock.appendChild(code);
                container.appendChild(codeBlock);
                codeBlockLines = [];
                codeBlockLanguage = '';
            }
            continue;
        }
        
        // Si estamos dentro de un bloque de código, acumular líneas
        if (inCodeBlock) {
            codeBlockLines.push(line);
            continue;
        }
        
        // Títulos (###, ##, #)
        if (trimmedLine.startsWith('###')) {
            const h3 = document.createElement('h3');
            h3.className = 'message-h3';
            h3.textContent = trimmedLine.replace(/^###\s*/, '');
            container.appendChild(h3);
            currentElement = null;
            continue;
        }
        
        if (trimmedLine.startsWith('##')) {
            const h2 = document.createElement('h2');
            h2.className = 'message-h2';
            h2.textContent = trimmedLine.replace(/^##\s*/, '');
            container.appendChild(h2);
            currentElement = null;
            continue;
        }
        
        if (trimmedLine.startsWith('#')) {
            const h1 = document.createElement('h1');
            h1.className = 'message-h1';
            h1.textContent = trimmedLine.replace(/^#\s*/, '');
            container.appendChild(h1);
            currentElement = null;
            continue;
        }
        
        // Tablas markdown - verificar que tenga al menos 3 columnas (2 separadores |)
        if (trimmedLine.includes('|') && trimmedLine.split('|').length > 2) {
            if (!inTable) {
                inTable = true;
                tableRows = [];
            }
            tableRows.push(trimmedLine);
            
            // Si la siguiente línea es el separador de tabla, agregarla y continuar
            if (nextLine.includes('---') && nextLine.split('|').length > 2) {
                tableRows.push(nextLine);
                i++; // Saltar línea de separador
                continue;
            }
            
            // Si la siguiente línea no es parte de la tabla, procesar la tabla acumulada
            if (!nextLine || !nextLine.includes('|') || nextLine.split('|').length <= 2) {
                if (tableRows.length > 0) {
                    const table = createTableFromMarkdown(tableRows);
                    container.appendChild(table);
                }
                tableRows = [];
                inTable = false;
            }
            continue;
        } else {
            // Si estábamos en una tabla y ahora no, procesar la tabla acumulada
            if (inTable && tableRows.length > 0) {
                const table = createTableFromMarkdown(tableRows);
                container.appendChild(table);
                tableRows = [];
            }
            inTable = false;
        }
        
        // Listas con viñetas (-, *, •)
        if (line.match(/^[-*•]\s+/)) {
            if (!currentElement || currentElement.tagName !== 'UL') {
                currentElement = document.createElement('ul');
                currentElement.className = 'message-list';
                container.appendChild(currentElement);
            }
            const li = document.createElement('li');
            // Procesar formato inline dentro de las listas
            li.innerHTML = line.replace(/^[-*•]\s+/, '')
                .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.+?)\*/g, '<em>$1</em>')
                .replace(/`(.+?)`/g, '<code>$1</code>');
            currentElement.appendChild(li);
            continue;
        }
        
        // Listas numeradas
        if (line.match(/^\d+\.\s+/)) {
            if (!currentElement || currentElement.tagName !== 'OL') {
                currentElement = document.createElement('ol');
                currentElement.className = 'message-list';
                container.appendChild(currentElement);
            }
            const li = document.createElement('li');
            // Procesar formato inline dentro de las listas
            li.innerHTML = line.replace(/^\d+\.\s+/, '')
                .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.+?)\*/g, '<em>$1</em>')
                .replace(/`(.+?)`/g, '<code>$1</code>');
            currentElement.appendChild(li);
            continue;
        }
        
        // Citas (> texto)
        if (line.startsWith('>')) {
            if (!currentElement || currentElement.tagName !== 'BLOCKQUOTE') {
                currentElement = document.createElement('blockquote');
                currentElement.className = 'message-quote';
                container.appendChild(currentElement);
            }
            const p = document.createElement('p');
            p.innerHTML = line.replace(/^>\s*/, '')
                .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.+?)\*/g, '<em>$1</em>')
                .replace(/`(.+?)`/g, '<code>$1</code>');
            currentElement.appendChild(p);
            continue;
        }
        
        // Texto normal (incluye negritas, cursivas, código inline)
        if (trimmedLine) {
            const p = document.createElement('p');
            p.className = 'message-text';
            // Procesar negritas, cursivas y código inline
            p.innerHTML = trimmedLine
                .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.+?)\*/g, '<em>$1</em>')
                .replace(/`(.+?)`/g, '<code>$1</code>');
            container.appendChild(p);
            currentElement = null;
        } else if (!trimmedLine && container.children.length > 0) {
            // Línea vacía, agregar espacio solo si hay contenido previo y no es el último elemento
            const lastChild = container.lastElementChild;
            if (lastChild && lastChild.tagName !== 'BR' && lastChild.tagName !== 'P' && i < lines.length - 1) {
                const br = document.createElement('br');
                container.appendChild(br);
            }
            currentElement = null;
        }
    }
}

// Crear tabla desde markdown
function createTableFromMarkdown(rows) {
    const table = document.createElement('table');
    table.className = 'message-table';
    
    const thead = document.createElement('thead');
    const tbody = document.createElement('tbody');
    
    let headerProcessed = false;
    
    rows.forEach((row, index) => {
        const cells = row.split('|').map(c => c.trim()).filter(c => c);
        
        // Detectar línea separadora (contiene solo --- o :---:)
        if (cells.length > 0 && cells.every(c => c.match(/^:?-+:?$/))) {
            return; // Saltar línea separadora
        }
        
        const tr = document.createElement('tr');
        
        cells.forEach(cell => {
            // Procesar formato markdown en las celdas
            const processedCell = cell
                .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.+?)\*/g, '<em>$1</em>');
            
            if (!headerProcessed) {
                const th = document.createElement('th');
                th.innerHTML = processedCell;
                tr.appendChild(th);
            } else {
                const td = document.createElement('td');
                td.innerHTML = processedCell;
                tr.appendChild(td);
            }
        });
        
        if (!headerProcessed) {
            thead.appendChild(tr);
            headerProcessed = true;
        } else {
            tbody.appendChild(tr);
        }
    });
    
    if (thead.children.length > 0) {
        table.appendChild(thead);
    }
    if (tbody.children.length > 0) {
        table.appendChild(tbody);
    }
    
    return table;
}

// Parsear menú y extraer opciones (eliminando duplicados)
function parseMenuOptions(text) {
    const options = [];
    const seenTitles = new Set(); // Para evitar duplicados
    const lines = text.split('\n');
    
    for (const line of lines) {
        // Detectar opciones numeradas directamente (formato: "1. Título" o con espacios "   1. Título")
        const match = line.match(/^\s*(\d+)\.\s*(.+)$/);
        if (match) {
            const number = parseInt(match[1]);
            const title = match[2].trim();
            if (title && !seenTitles.has(title)) {  // Solo agregar si hay título y no está duplicado
                seenTitles.add(title);
                options.push({ number, title, description: '' });
            }
        } else if (line.includes('└─') && options.length > 0) {
            // Es una descripción de la opción anterior
            const description = line.replace(/.*└─\s*/, '').trim();
            if (description) {
                options[options.length - 1].description = description;
            }
        }
    }
    
    console.log('Parsed options:', options);
    return options;
}

// Agregar menú de continuación después de respuestas
function addContinuationMenu() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'chat-message bot';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content continuation-menu';
    
    const questionP = document.createElement('p');
    questionP.className = 'continuation-question';
    questionP.textContent = '¿Cómo quieres continuar? Puedes seleccionar una opción o escribir tu consulta';
    contentDiv.appendChild(questionP);
    
    const optionsContainer = document.createElement('div');
    optionsContainer.className = 'continuation-options';
    
    // Botón "Ir al menú principal"
    const menuButton = document.createElement('button');
    menuButton.className = 'continuation-button menu-button';
    menuButton.type = 'button';
    menuButton.textContent = 'Ir al menú principal';
    menuButton.addEventListener('click', async (e) => {
        e.preventDefault();
        e.stopPropagation();
        
        if (!isLoading) {
            isLoading = true;
            chatSend.disabled = true;
            showTypingIndicator();
            
            try {
                // Enviar solicitud para obtener el menú principal
                const response = await fetch(CHAT_CONFIG.apiUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        message: 'menú',
                        session_id: CHAT_CONFIG.sessionId
                    }),
                    mode: 'cors',
                    credentials: 'omit'
                });
                
                if (!response.ok) {
                    throw new Error(`Error ${response.status}`);
                }
                
                const data = await response.json();
                hideTypingIndicator();
                
                // Mostrar el menú principal (sin agregar mensaje del usuario)
                // NO agregar el mensaje "menú" del usuario, solo mostrar el menú
                if (data.response) {
                    // Detectar si es un menú: debe tener al menos 2 opciones numeradas consecutivas
                    const menuPattern = /^\d+\.\s+\S+/gm;
                    const menuMatches = data.response.match(menuPattern);
                    const isMenu = menuMatches && menuMatches.length >= 2;
                    addMessage(data.response, false, isMenu);
                }
            } catch (error) {
                console.error('Error al cargar menú principal:', error);
                hideTypingIndicator();
                addMessage('Error al cargar el menú. Por favor intenta de nuevo.', false);
            } finally {
                isLoading = false;
                chatSend.disabled = false;
            }
        }
    }, { once: false });
    optionsContainer.appendChild(menuButton);
    
    // Botón "Finalizar"
    const finishButton = document.createElement('button');
    finishButton.className = 'continuation-button finish-button';
    finishButton.type = 'button';
    finishButton.textContent = 'Finalizar';
    finishButton.addEventListener('click', () => {
        addMessage('Gracias por usar el chatbot del IPECD. ¡Hasta luego! 👋', false);
        // Opcional: cerrar el chat después de un delay
        setTimeout(() => {
            closeChat();
        }, 2000);
    });
    optionsContainer.appendChild(finishButton);
    
    contentDiv.appendChild(optionsContainer);
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    
    scrollToBottom();
}

// Agregar mensaje al chat
function addMessage(text, isUser = false, isMenu = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${isUser ? 'user' : 'bot'}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    // Si es un menú, crear botones interactivos
    if (isMenu) {
        contentDiv.className += ' menu-content';
        
        // Parsear y crear botones SOLO para las opciones (sin títulos ni descripciones)
        const options = parseMenuOptions(text);
        
        // Debug: verificar si se encontraron opciones
        console.log('Menu options parsed:', options);
        console.log('Menu text:', text);
        
        if (options.length > 0) {
            const optionsContainer = document.createElement('div');
            optionsContainer.className = 'menu-options';
            
            options.forEach(option => {
                const button = document.createElement('button');
                button.className = 'menu-button';
                button.type = 'button';
                
                const buttonContent = document.createElement('div');
                buttonContent.className = 'menu-button-content';
                
                const buttonTitle = document.createElement('span');
                buttonTitle.className = 'menu-button-title';
                buttonTitle.textContent = option.title;
                
                buttonContent.appendChild(buttonTitle);
                
                if (option.description) {
                    const buttonDesc = document.createElement('span');
                    buttonDesc.className = 'menu-button-description';
                    buttonDesc.textContent = option.description;
                    buttonContent.appendChild(buttonDesc);
                }
                
                button.appendChild(buttonContent);
                
                // Al hacer clic, enviar SOLO el texto completo (no el número)
                button.addEventListener('click', () => {
                    if (!isLoading) {
                        // Mostrar el texto completo de la opción seleccionada como mensaje del usuario
                        const selectedText = option.title;
                        
                        // Agregar mensaje del usuario con el texto completo
                        addMessage(selectedText, true);
                        
                        // Enviar el número de opción al backend (pero no mostrarlo)
                        chatInput.value = option.number.toString();
                        sendMessage();
                    }
                });
                
                optionsContainer.appendChild(button);
            });
            
            contentDiv.appendChild(optionsContainer);
        } else {
            // Si no se encontraron opciones, mostrar el texto como mensaje normal
            console.warn('No se encontraron opciones en el menú');
    const p = document.createElement('p');
    p.textContent = text;
    contentDiv.appendChild(p);
        }
    } else {
        // Mensaje normal - renderizar markdown
        renderMarkdown(text, contentDiv);
    }
    
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    
    // Scroll al final
    scrollToBottom();
    
    return messageDiv;
}

// Mostrar indicador de escritura
function showTypingIndicator() {
    const typingDiv = document.createElement('div');
    typingDiv.className = 'chat-message bot';
    typingDiv.id = 'typing-indicator';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'typing-indicator';
    
    for (let i = 0; i < 3; i++) {
        const span = document.createElement('span');
        contentDiv.appendChild(span);
    }
    
    typingDiv.appendChild(contentDiv);
    chatMessages.appendChild(typingDiv);
    scrollToBottom();
}

// Ocultar indicador de escritura
function hideTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

// Scroll al final del chat
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Enviar mensaje
async function sendMessage() {
    const message = chatInput.value.trim();
    
    if (!message || isLoading) return;
    
    // Si es un número, buscar el texto correspondiente en el último menú mostrado
    // PERO solo si no se agregó ya el mensaje desde el botón
    const lastUserMessage = chatMessages.querySelector('.chat-message.user:last-child');
    const wasButtonClick = lastUserMessage && lastUserMessage.textContent !== message;
    
    if (/^\d+$/.test(message) && !wasButtonClick) {
        const optionNumber = parseInt(message);
        const lastMenu = chatMessages.querySelector('.menu-content');
        if (lastMenu) {
            const menuText = lastMenu.textContent || '';
            const options = parseMenuOptions(menuText);
            const selectedOption = options.find(opt => opt.number === optionNumber);
            if (selectedOption) {
                // Reemplazar el mensaje del número por el texto completo
                if (lastUserMessage) {
                    lastUserMessage.remove();
                }
                addMessage(selectedOption.title, true);
            }
        }
    } else if (!wasButtonClick) {
        // Solo agregar mensaje si no fue desde un botón
    addMessage(message, true);
    }
    
    chatInput.value = '';
    chatSend.disabled = true;
    isLoading = true;
    
    // Mostrar indicador de escritura
    setTimeout(() => {
        if (isLoading) {
            showTypingIndicator();
        }
    }, CHAT_CONFIG.typingDelay);
    
    try {
        // Log para debug
        console.log('Enviando mensaje a:', CHAT_CONFIG.apiUrl);
        
        // Llamar a la API
        const response = await fetch(CHAT_CONFIG.apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                session_id: CHAT_CONFIG.sessionId
            }),
            // Agregar modo cors explícito
            mode: 'cors',
            credentials: 'omit'
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Error de respuesta:', response.status, errorText);
            throw new Error(`Error ${response.status}: ${errorText || 'Error desconocido'}`);
        }
        
        const data = await response.json();
        
        // Ocultar indicador de escritura
        hideTypingIndicator();
        
        // Agregar respuesta del bot
        if (data.response) {
            // Detectar si es un menú: debe tener al menos 2 opciones numeradas consecutivas
            const menuPattern = /^\d+\.\s+\S+/gm;
            const menuMatches = data.response.match(menuPattern);
            const isMenu = menuMatches && menuMatches.length >= 2;
            console.log('Is menu?', isMenu, 'Menu matches:', menuMatches ? menuMatches.length : 0);
            addMessage(data.response, false, isMenu);
            
            // Agregar menú de continuación después de cada respuesta (excepto si es un menú principal)
            if (!isMenu) {
                addContinuationMenu();
            }
        } else {
            addMessage('Lo siento, no pude procesar tu mensaje. Por favor intenta de nuevo.', false);
            addContinuationMenu();
        }
        
    } catch (error) {
        console.error('Error al enviar mensaje:', error);
        hideTypingIndicator();
        
        // Mensaje de error más descriptivo
        let errorMessage = 'Error de conexión. ';
        if (error.message.includes('Failed to fetch')) {
            errorMessage += 'No se pudo conectar con la API. Verifica que esté corriendo en ' + CHAT_CONFIG.apiUrl;
        } else if (error.message.includes('CORS')) {
            errorMessage += 'Error de CORS. Verifica la configuración del servidor.';
        } else {
            errorMessage += error.message || 'Por favor intenta de nuevo.';
        }
        
        addMessage(errorMessage, false);
    } finally {
        isLoading = false;
        chatSend.disabled = false;
        chatInput.focus();
    }
}

// Inicializar cuando el DOM esté listo
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        initChat();
        // Cargar menú inicial automáticamente después de un pequeño delay
        setTimeout(() => {
            if (!menuLoaded) {
                loadInitialMenu();
            }
        }, 500);
    });
} else {
    initChat();
    // Cargar menú inicial automáticamente después de un pequeño delay
    setTimeout(() => {
        if (!menuLoaded) {
            loadInitialMenu();
        }
    }, 500);
}

// Exportar funciones para uso externo si es necesario
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        openChat,
        closeChat,
        sendMessage
    };
}

