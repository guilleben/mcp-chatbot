# Frontend - Widget de Chat

Widget de chat simple y moderno similar al MuniBot de la Municipalidad de Corrientes.

## 🚀 Inicio Rápido

### 1. Ejecutar la API

```bash
# Instalar dependencias si aún no lo has hecho
pip install -r requirements.txt

# Ejecutar la API
python run_api.py
```

La API estará disponible en `http://localhost:8000`

### 2. Probar el Widget

Abre `frontend/chat-widget-standalone.html` en tu navegador para ver el widget en acción.

O puedes usar un servidor local:

```bash
cd frontend
python -m http.server 8080
```

Luego abre `http://localhost:8080/chat-widget-standalone.html`

## 📁 Estructura de Archivos

```
frontend/
├── chat-widget.html          # HTML del widget (ejemplo)
├── chat-widget.css           # Estilos del widget
├── chat-widget.js            # Lógica del widget
├── chat-widget-standalone.html  # Ejemplo completo funcional
└── README.md                 # Documentación detallada
```

## 🎨 Características

- ✅ Botón flotante animado en la esquina inferior derecha
- ✅ Widget de chat que se abre/cierra con animaciones suaves
- ✅ Diseño moderno y responsive
- ✅ Indicador de "escribiendo..." mientras procesa la respuesta
- ✅ Scroll automático a los nuevos mensajes
- ✅ Fácil integración en Laravel o cualquier página web

## 🔧 Integración en Laravel

### Paso 1: Copiar archivos

Copia los archivos CSS y JS a tu proyecto Laravel:

```bash
# Desde la raíz del proyecto Laravel
mkdir -p public/css public/js
cp frontend/chat-widget.css public/css/
cp frontend/chat-widget.js public/js/
```

### Paso 2: Crear componente Blade

Crea `resources/views/components/chat-widget.blade.php`:

```blade
<!-- Botón flotante -->
<button id="chatToggle" class="chat-toggle" aria-label="Abrir chat">
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M20 2H4C2.9 2 2 2.9 2 4V22L6 18H20C21.1 18 22 17.1 22 16V4C22 2.9 21.1 2 20 2ZM20 16H6L4 18V4H20V16Z" fill="currentColor"/>
        <path d="M7 9H17V11H7V9ZM7 12H15V14H7V12Z" fill="currentColor"/>
    </svg>
</button>

<!-- Widget de chat -->
<div id="chatWidget" class="chat-widget">
    <div class="chat-header">
        <div class="chat-header-content">
            <div class="chat-avatar">
                <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="16" cy="16" r="15" fill="#4A90E2" stroke="#fff" stroke-width="2"/>
                    <path d="M16 10C17.1 10 18 10.9 18 12C18 13.1 17.1 14 16 14C14.9 14 14 13.1 14 12C14 10.9 14.9 10 16 10ZM16 16C18.2 16 20 17.8 20 20H12C12 17.8 13.8 16 16 16Z" fill="white"/>
                </svg>
            </div>
            <div class="chat-header-text">
                <h3>ChatBot</h3>
                <span class="chat-status">En línea</span>
            </div>
        </div>
        <button id="chatClose" class="chat-close" aria-label="Cerrar chat">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M15 5L5 15M5 5L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
        </button>
    </div>

    <div id="chatMessages" class="chat-messages">
        <div class="chat-message bot">
            <div class="message-content">
                <p>¡Hola! 👋 ¿En qué puedo ayudarte hoy?</p>
            </div>
        </div>
    </div>

    <div class="chat-input-container">
        <div class="chat-input-wrapper">
            <input 
                type="text" 
                id="chatInput" 
                class="chat-input" 
                placeholder="Escribí tu mensaje..." 
                autocomplete="off"
            />
            <div class="chat-input-actions">
                <button id="chatSend" class="chat-send" aria-label="Enviar mensaje">
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M18 2L9 11M18 2L12 18L9 11M18 2L2 8L9 11" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </button>
            </div>
        </div>
    </div>
</div>

<script>
    // Configurar la URL de la API antes de cargar el script
    window.CHAT_CONFIG = {
        apiUrl: '{{ config('app.url') }}/api/chat', // Ajusta según tu configuración
        sessionId: 'chat-session-{{ uniqid() }}',
        typingDelay: 500
    };
</script>
<script src="{{ asset('js/chat-widget.js') }}"></script>
```

### Paso 3: Incluir en tu layout

En `resources/views/layouts/app.blade.php` (o tu layout principal):

```blade
<!DOCTYPE html>
<html>
<head>
    <!-- otros head -->
    <link rel="stylesheet" href="{{ asset('css/chat-widget.css') }}">
</head>
<body>
    <!-- Tu contenido -->
    
    <!-- Widget de chat -->
    @include('components.chat-widget')
</body>
</html>
```

### Paso 4: Configurar la URL de la API

Edita `public/js/chat-widget.js` y actualiza la URL:

```javascript
const CHAT_CONFIG = {
    apiUrl: 'http://localhost:8000/api/chat', // URL de tu API
    // ...
};
```

O mejor aún, configura la URL dinámicamente desde Blade (como se muestra en el componente).

## 🎨 Personalización

### Cambiar colores

Edita `chat-widget.css` y modifica las variables CSS:

```css
:root {
    --chat-primary: #4A90E2;        /* Color principal */
    --chat-primary-dark: #357ABD;   /* Color principal oscuro */
    --chat-bg: #ffffff;              /* Fondo del widget */
    --chat-user-bg: #4A90E2;        /* Fondo de mensajes del usuario */
    --chat-bot-bg: #f0f0f0;         /* Fondo de mensajes del bot */
}
```

### Cambiar tamaño

```css
.chat-widget {
    width: 380px;   /* Ancho */
    height: 600px; /* Alto */
}
```

### Cambiar posición del botón

```css
.chat-toggle {
    bottom: 24px;  /* Distancia desde abajo */
    right: 24px;  /* Distancia desde la derecha */
}
```

## 📡 API

El widget espera una API REST con el siguiente formato:

**Endpoint:** `POST /api/chat`

**Request:**
```json
{
    "message": "Hola",
    "session_id": "chat-session-123"
}
```

**Response:**
```json
{
    "response": "¡Hola! ¿En qué puedo ayudarte?",
    "session_id": "chat-session-123"
}
```

## 🐛 Solución de Problemas

### El widget no se conecta a la API

1. Verifica que la API esté corriendo: `http://localhost:8000/api/health`
2. Verifica la URL en `chat-widget.js` o en la configuración de Blade
3. Revisa la consola del navegador para errores de CORS

### Errores de CORS

Si ves errores de CORS, asegúrate de que la API tenga configurado CORS correctamente. En `api.py` ya está configurado para permitir todos los orígenes en desarrollo.

Para producción, actualiza:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://tu-dominio.com"],  # Tu dominio
    # ...
)
```

## 📝 Notas

- El widget es completamente independiente y no requiere frameworks adicionales
- Funciona en todos los navegadores modernos
- Es responsive y se adapta a móviles
- Las sesiones se mantienen en el servidor (una por sesión del navegador)


