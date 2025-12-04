#!/usr/bin/env python3
"""Script para ejecutar la API del chatbot."""
import uvicorn
import os

if __name__ == "__main__":
    # Desactivar reload por defecto para evitar interrupciones y problemas de conexión
    # Activar solo si se especifica explícitamente API_RELOAD=true
    reload_enabled = os.getenv("API_RELOAD", "false").lower() == "true"
    
    print(f"Starting API server on http://0.0.0.0:8000")
    print(f"Auto-reload: {'enabled' if reload_enabled else 'disabled'}")
    
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=reload_enabled,
        log_level="info",
        access_log=True
    )
