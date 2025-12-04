# 🐳 Guía de Docker

Esta guía explica cómo ejecutar el proyecto completo (API + Frontend) usando Docker.

## 📋 Requisitos Previos

- Docker instalado
- Docker Compose instalado
- Archivo `.env` con las variables de entorno necesarias

## 🚀 Inicio Rápido

### 1. Configurar variables de entorno

Crea un archivo `.env` en la raíz del proyecto con tus credenciales:

```env
# API Keys
GROQ_API_KEY=tu_groq_api_key
OPENAI_API_KEY=tu_openai_api_key  # Opcional
SERP_API_KEY=tu_serp_api_key       # Opcional

# Base de datos (opcional)
HOST_DBB=tu_host_db
DB_PORT=3306
USER_DBB=tu_usuario_db
PASSWORD_DBB=tu_password_db
NAME_DBB_DATALAKE_ECONOMICO=nombre_db
NAME_DBB_DWH_ECONOMICO=nombre_db
NAME_DBB_DATALAKE_SOCIO=nombre_db
NAME_DBB_DWH_SOCIO=nombre_db
```

### 2. Construir y levantar los servicios

```bash
# Construir las imágenes
docker-compose build

# Levantar los servicios
docker-compose up -d

# Ver los logs
docker-compose logs -f
```

### 3. Acceder a los servicios

- **Frontend**: http://localhost:8080
- **API**: http://localhost:8000
- **API Health Check**: http://localhost:8000/api/health
- **Documentación de la API**: http://localhost:8000/docs

## 📁 Estructura de Servicios

El `docker-compose.yml` define dos servicios:

### 1. API (`api`)
- **Puerto**: 8000
- **Imagen**: `mcp-chatbot-api:latest`
- **Comando**: Ejecuta `python run_api.py`
- **Healthcheck**: Verifica que la API responda en `/api/health`

### 2. Frontend (`frontend`)
- **Puerto**: 8080
- **Imagen**: `mcp-chatbot-frontend:latest`
- **Servidor**: Nginx Alpine
- **Healthcheck**: Verifica que Nginx sirva el HTML correctamente

## 🔧 Comandos Útiles

### Ver logs
```bash
# Todos los servicios
docker-compose logs -f

# Solo la API
docker-compose logs -f api

# Solo el frontend
docker-compose logs -f frontend
```

### Detener servicios
```bash
# Detener sin eliminar contenedores
docker-compose stop

# Detener y eliminar contenedores
docker-compose down

# Detener y eliminar volúmenes también
docker-compose down -v
```

### Reconstruir después de cambios
```bash
# Reconstruir solo la API
docker-compose build api
docker-compose up -d api

# Reconstruir solo el frontend
docker-compose build frontend
docker-compose up -d frontend

# Reconstruir todo
docker-compose build
docker-compose up -d
```

### Ejecutar comandos dentro de los contenedores
```bash
# En la API
docker-compose exec api python -c "print('Hello')"

# En el frontend
docker-compose exec frontend sh
```

## 🌐 Configuración de Red

Los servicios están en la misma red de Docker, por lo que pueden comunicarse usando los nombres de servicio:

- Desde el frontend a la API: `http://api:8000/api/chat`
- Desde fuera de Docker: `http://localhost:8000/api/chat`

El frontend está configurado para usar `localhost:8000` cuando se accede desde el navegador, ya que el navegador está fuera de la red de Docker.

## 🔒 Producción

Para producción, considera:

1. **Actualizar CORS en `api.py`**:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://tu-dominio.com"],  # Tu dominio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

2. **Usar variables de entorno para la URL de la API**:
   - Actualiza `frontend/config.js` o configura `window.CHAT_CONFIG` desde tu aplicación

3. **Usar HTTPS**:
   - Configura un proxy reverso (nginx/traefik) con SSL
   - O usa Docker con certificados SSL

4. **No montar volúmenes en producción**:
   - Comenta las líneas `volumes` en `docker-compose.yml` para producción
   - Los archivos se copiarán en la imagen durante el build

## 🐛 Solución de Problemas

### La API no responde

1. Verifica que el contenedor esté corriendo:
```bash
docker-compose ps
```

2. Revisa los logs:
```bash
docker-compose logs api
```

3. Verifica el healthcheck:
```bash
curl http://localhost:8000/api/health
```

### El frontend no se conecta a la API

1. Verifica que la API esté accesible:
```bash
curl http://localhost:8000/api/health
```

2. Revisa la consola del navegador (F12) para errores de CORS

3. Verifica la configuración en `frontend/config.js` o `chat-widget.js`

### Error de permisos

Si tienes problemas de permisos con los volúmenes:

```bash
# En Linux/Mac
sudo chown -R $USER:$USER .

# O ajusta los permisos del volumen
docker-compose down
docker volume rm mcp-chatbot_chatbot-data
docker-compose up -d
```

### Reconstruir desde cero

```bash
# Eliminar todo
docker-compose down -v
docker-compose rm -f

# Eliminar imágenes
docker rmi mcp-chatbot-api mcp-chatbot-frontend

# Reconstruir
docker-compose build --no-cache
docker-compose up -d
```

## 📝 Notas

- Los volúmenes están montados para desarrollo. En producción, comenta las líneas `volumes` en `docker-compose.yml`
- El frontend detecta automáticamente si está en Docker y ajusta la URL de la API
- Los healthchecks verifican que los servicios estén funcionando correctamente
- Los logs se pueden ver en tiempo real con `docker-compose logs -f`

## 🔗 Enlaces Útiles

- [Documentación de Docker Compose](https://docs.docker.com/compose/)
- [Documentación de FastAPI](https://fastapi.tiangolo.com/)
- [Documentación de Nginx](https://nginx.org/en/docs/)


