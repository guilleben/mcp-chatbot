# Usar imagen oficial de Python 3.10
FROM python:3.10-slim

# Establecer variables de entorno
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Instalar Node.js y npm (necesario para npx)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends \
    nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Instalar uv (necesario para uvx) usando pip
# Instalar como root para que esté disponible globalmente
RUN pip install --no-cache-dir uv && \
    uv --version

# Crear wrapper para uvx en /usr/local/bin para que esté disponible globalmente
# uvx puede no estar disponible directamente, así que creamos un wrapper
RUN echo '#!/bin/sh' > /usr/local/bin/uvx && \
    echo 'exec uv tool run "$@"' >> /usr/local/bin/uvx && \
    chmod +x /usr/local/bin/uvx && \
    # Verificar que el wrapper se creó correctamente
    test -f /usr/local/bin/uvx && echo "uvx wrapper creado exitosamente"

# Asegurar que /usr/local/bin esté en el PATH (ya debería estar, pero por si acaso)
ENV PATH="/usr/local/bin:/usr/local/sbin:${PATH}"

# Verificar que ambos comandos estén disponibles
RUN uv --version && \
    /usr/local/bin/uvx --version 2>&1 | head -1 || echo "Verificando uvx..."

# Crear usuario no-root para seguridad
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app && \
    chown -R appuser:appuser /app && \
    # Asegurar que el wrapper uvx sea accesible para el usuario no-root
    chmod 755 /usr/local/bin/uvx

# Establecer directorio de trabajo
WORKDIR /app

# Copiar archivos de dependencias primero (para aprovechar cache de Docker)
COPY --chown=appuser:appuser requirements.txt /app/

# Instalar dependencias de Python
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install git+https://github.com/modelcontextprotocol/python-sdk.git@main || \
    echo "Warning: MCP SDK installation failed, continuing without it..."

# Copiar el resto de los archivos de la aplicación
COPY --chown=appuser:appuser . /app/

# Cambiar al usuario no-root
USER appuser

# Exponer puerto de la API
EXPOSE 8000

# Comando por defecto (ejecutar API)
CMD ["python", "run_api.py"]

