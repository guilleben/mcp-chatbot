"""Pytest configuration and shared fixtures."""
import os
import sys
import pytest
from unittest.mock import MagicMock, AsyncMock

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ==================== FIXTURES BÁSICOS ====================

@pytest.fixture
def sample_menu_config():
    """Configuración de menú de ejemplo para tests."""
    return {
        "id": "root",
        "title": "Menú Principal",
        "description": "Menú principal del chatbot",
        "action": "menu",
        "children": ["cat_precios", "cat_censo"],
        "keywords": [],
        "nodes": [
            {
                "id": "root",
                "title": "Menú Principal",
                "action": "menu",
                "children": ["cat_precios", "cat_censo"],
                "keywords": []
            },
            {
                "id": "cat_precios",
                "title": "💰 Precios e Inflación",
                "description": "Datos de IPC y precios",
                "action": "menu",
                "children": ["ipc_ultimo"],
                "keywords": ["ipc", "inflacion", "precios"]
            },
            {
                "id": "ipc_ultimo",
                "title": "📊 Último IPC",
                "description": "Índice de Precios al Consumidor más reciente",
                "action": "tool",
                "tool": "get_ipc",
                "tool_args": {},
                "children": [],
                "keywords": ["ipc", "ultimo", "inflacion"]
            },
            {
                "id": "cat_censo",
                "title": "👥 Población y Censo",
                "description": "Datos demográficos",
                "action": "menu",
                "children": ["censo_municipios"],
                "keywords": ["censo", "poblacion"]
            },
            {
                "id": "censo_municipios",
                "title": "🏘️ Población por Municipio",
                "description": "Población de cada municipio",
                "action": "tool",
                "tool": "get_censo",
                "tool_args": {},
                "children": [],
                "keywords": ["municipio", "poblacion"]
            }
        ]
    }


@pytest.fixture
def mock_db_connection():
    """Mock de conexión a base de datos."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = None
    return conn, cursor


@pytest.fixture
def mock_llm_client():
    """Mock del cliente LLM."""
    client = MagicMock()
    client.get_response = MagicMock(return_value="Respuesta de prueba del LLM")
    return client


@pytest.fixture
def sample_chat_messages():
    """Mensajes de chat de ejemplo."""
    return [
        {"role": "system", "content": "Eres un asistente del IPECD."},
        {"role": "user", "content": "¿Qué es el IPC?"},
        {"role": "assistant", "content": "El IPC es el Índice de Precios al Consumidor..."}
    ]


@pytest.fixture
def sample_ipc_data():
    """Datos de IPC de ejemplo."""
    return [
        {"region": "NEA", "fecha": "2025-10-01", "valor": 120.5, "variacion_mensual": 2.5},
        {"region": "GBA", "fecha": "2025-10-01", "valor": 122.3, "variacion_mensual": 2.7},
        {"region": "Nacion", "fecha": "2025-10-01", "valor": 121.0, "variacion_mensual": 2.6}
    ]


@pytest.fixture
def sample_censo_data():
    """Datos de censo de ejemplo."""
    return [
        {"municipio": "Corrientes", "pob_2010": 358223, "pob_2022": 409000, "var_relativa": 14.2},
        {"municipio": "Goya", "pob_2010": 88427, "pob_2022": 102000, "var_relativa": 15.4},
        {"municipio": "Paso de los Libres", "pob_2010": 43251, "pob_2022": 48000, "var_relativa": 11.0}
    ]


@pytest.fixture
def sample_empleo_data():
    """Datos de empleo de ejemplo."""
    return [
        {
            "Aglomerado": "Corrientes",
            "Año": 2025,
            "Trimestre": 2,
            "Tasa de Actividad": 0.41,
            "Tasa de Empleo": 0.38,
            "Tasa de desocupación": 0.067
        }
    ]


# ==================== FIXTURES DE ENTORNO ====================

@pytest.fixture
def env_vars(monkeypatch):
    """Configura variables de entorno para tests."""
    monkeypatch.setenv("HOST_DBB", "localhost")
    monkeypatch.setenv("PORT_DBB", "3307")
    monkeypatch.setenv("USER_DBB", "test_user")
    monkeypatch.setenv("PASSWORD_DBB", "test_password")
    monkeypatch.setenv("NAME_DBB_DATALAKE_ECONOMICO", "datalake-economico")
    monkeypatch.setenv("NAME_DBB_DWH_ECONOMICO", "dhw_economico")
    monkeypatch.setenv("NAME_DBB_DWH_SOCIO", "dhw_sociodemografico")


# ==================== FIXTURES ASYNC ====================

@pytest.fixture
def async_mock():
    """Crea un mock asíncrono."""
    return AsyncMock()


# ==================== HELPERS ====================

def create_mock_cursor_with_data(data):
    """Crea un cursor mock con datos específicos."""
    cursor = MagicMock()
    cursor.fetchall.return_value = data
    cursor.fetchone.return_value = data[0] if data else None
    return cursor

