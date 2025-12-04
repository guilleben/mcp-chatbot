# 🐳 Inicio Rápido con Docker

## Pasos para levantar todo con Docker

### 1. Configurar variables de entorno

Crea un archivo `.env` en la raíz del proyecto:

```env
GROQ_API_KEY=tu_api_key_aqui
```

### 2. Levantar los servicios

```bash
docker-compose up -d
```

### 3. Acceder a los servicios

- **Frontend**: http://localhost:8080
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

### 4. Ver logs

```bash
docker-compose logs -f
```

### 5. Detener servicios

```bash
docker-compose down
```

## Estructura

- **`api`**: Servicio de la API FastAPI (puerto 8000)
- **`frontend`**: Servicio Nginx sirviendo el widget (puerto 8080)

Para más detalles, ver [DOCKER.md](DOCKER.md)


