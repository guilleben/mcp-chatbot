# Widget de Chat - Frontend

Widget de chat simple y moderno similar al MuniBot de la Municipalidad de Corrientes.

## Características

- ✅ Botón flotante para abrir/cerrar el chat
- ✅ Diseño moderno y responsive
- ✅ Animaciones suaves
- ✅ Indicador de "escribiendo..."
- ✅ Fácil integración en cualquier página web (Laravel, HTML, etc.)

## Archivos

- `chat-widget.html` - HTML del widget (ejemplo de uso)
- `chat-widget.css` - Estilos del widget
- `chat-widget.js` - Lógica del widget

## Integración en Laravel

### Opción 1: Incluir en una vista Blade

```blade
<!-- En tu layout o vista -->
<link rel="stylesheet" href="{{ asset('css/chat-widget.css') }}">

<!-- Contenido de tu página -->

<!-- Al final del body -->
@include('components.chat-widget')
<script src="{{ asset('js/chat-widget.js') }}"></script>
```

### Opción 2: Crear componente Blade

Crear `resources/views/components/chat-widget.blade.php`:

```blade
<!-- Botón flotante -->
<button id="chatToggle" class="chat-toggle" aria-label="Abrir chat">
    <!-- SVG del botón -->
</button>

<!-- Widget de chat -->
<div id="chatWidget" class="chat-widget">
    <!-- Contenido del widget -->
</div>

<script>
    // Configurar la URL de la API
    window.CHAT_CONFIG = {
        apiUrl: '{{ config('app.api_url') }}/api/chat',
        sessionId: 'chat-session-{{ uniqid() }}',
        typingDelay: 500
    };
</script>
```

### Opción 3: Integración simple (recomendada)

1. Copia los archivos CSS y JS a tu proyecto Laravel:
   - `public/css/chat-widget.css`
   - `public/js/chat-widget.js`

2. En tu layout principal (`resources/views/layouts/app.blade.php`):

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
    
    <!-- Scripts -->
    <script src="{{ asset('js/chat-widget.js') }}"></script>
</body>
</html>
```

3. Crea el componente `resources/views/components/chat-widget.blade.php` con el contenido de `chat-widget.html` (sin las etiquetas `<html>`, `<head>`, `<body>`)

## Configuración

Edita `chat-widget.js` y cambia la URL de la API:

```javascript
const CHAT_CONFIG = {
    apiUrl: 'http://tu-api.com/api/chat', // URL de tu API
    sessionId: 'chat-session-' + Date.now(),
    typingDelay: 500
};
```

## Personalización

### Colores

Edita las variables CSS en `chat-widget.css`:

```css
:root {
    --chat-primary: #4A90E2; /* Color principal */
    --chat-primary-dark: #357ABD; /* Color principal oscuro */
    --chat-bg: #ffffff; /* Fondo del widget */
    /* ... más variables */
}
```

### Tamaño

Ajusta el tamaño del widget en `chat-widget.css`:

```css
.chat-widget {
    width: 380px; /* Ancho */
    height: 600px; /* Alto */
}
```

## Uso

El widget se inicializa automáticamente cuando se carga la página. El botón flotante aparece en la esquina inferior derecha.

## API Esperada

El widget espera una API REST con el siguiente formato:

**POST** `/api/chat`

```json
{
    "message": "Hola",
    "session_id": "chat-session-123"
}
```

**Respuesta:**

```json
{
    "response": "¡Hola! ¿En qué puedo ayudarte?",
    "session_id": "chat-session-123"
}
```


