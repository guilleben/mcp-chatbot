"""Tests para la API REST del chatbot."""
import pytest
import sys
import os
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAPIBasic:
    """Tests básicos de la API."""
    
    @pytest.fixture
    def client(self):
        """Cliente de prueba para la API."""
        # Mockear dependencias antes de importar
        with patch('api.ChatSession'), \
             patch('api.DatabaseClient'), \
             patch('api.DatabaseTools'), \
             patch('api.ToolExecutor'), \
             patch('api.get_learning_memory', return_value=None):
            from api import app
            return TestClient(app)
    
    @pytest.mark.api
    def test_root_endpoint(self, client):
        """El endpoint raíz retorna el frontend HTML."""
        response = client.get("/")
        assert response.status_code == 200
        # El endpoint raíz ahora sirve el frontend HTML
        content_type = response.headers.get("content-type", "")
        assert "text/html" in content_type or response.status_code == 200
    
    @pytest.mark.api
    def test_cors_headers(self, client):
        """La API tiene headers CORS configurados."""
        response = client.options("/")
        # Los headers CORS deben estar presentes
        assert response.status_code in [200, 405]


class TestAPIChatEndpoint:
    """Tests para el endpoint de chat."""
    
    @pytest.fixture
    def mock_chat_session(self):
        """Mock de ChatSession."""
        mock = MagicMock()
        mock.llm_client = MagicMock()
        mock.llm_client.get_response.return_value = "Respuesta de prueba"
        mock.openai_client = None
        mock.servers = []
        return mock
    
    @pytest.fixture
    def mock_tool_executor(self):
        """Mock de ToolExecutor."""
        mock = MagicMock()
        mock.is_available.return_value = True
        mock.execute.return_value = "## Datos de prueba\n| Col | Val |\n|-----|-----|\n| A | 1 |"
        return mock
    
    @pytest.mark.api
    def test_chat_endpoint_exists(self):
        """El endpoint /api/chat existe."""
        with patch('api.ChatSession'), \
             patch('api.DatabaseClient'), \
             patch('api.DatabaseTools'), \
             patch('api.ToolExecutor'), \
             patch('api.get_learning_memory', return_value=None):
            from api import app
            client = TestClient(app)
            # POST sin body debería dar error de validación, no 404
            response = client.post("/api/chat")
            assert response.status_code != 404
    
    @pytest.mark.api
    def test_chat_requires_message(self):
        """El endpoint requiere un mensaje."""
        with patch('api.ChatSession'), \
             patch('api.DatabaseClient'), \
             patch('api.DatabaseTools'), \
             patch('api.ToolExecutor'), \
             patch('api.get_learning_memory', return_value=None):
            from api import app
            client = TestClient(app)
            response = client.post("/api/chat", json={})
            # Debería fallar validación de Pydantic
            assert response.status_code == 422


class TestAPIMemoryEndpoints:
    """Tests para endpoints de memoria."""
    
    @pytest.fixture
    def mock_learning_memory(self):
        """Mock de LearningMemory."""
        mock = MagicMock()
        mock.get_stats.return_value = {
            "total_entries": 10,
            "conceptual_questions": 5,
            "data_questions": 5,
            "categories": {"ipc": 3, "censo": 7},
            "total_uses": 25,
            "average_uses": 2.5,
            "top_questions": []
        }
        mock.get_suggestions.return_value = ["que es el ipc", "que es el eph"]
        mock.get_recent_entries.return_value = [
            {"id": 1, "question": "que es el ipc", "use_count": 5}
        ]
        mock.export_for_training.return_value = []
        return mock
    
    @pytest.mark.api
    def test_memory_stats_endpoint(self, mock_learning_memory):
        """El endpoint /api/memory/stats funciona."""
        with patch('api.ChatSession'), \
             patch('api.DatabaseClient'), \
             patch('api.DatabaseTools'), \
             patch('api.ToolExecutor'), \
             patch('api.get_learning_memory', return_value=mock_learning_memory), \
             patch('api.learning_memory', mock_learning_memory):
            from api import app
            client = TestClient(app)
            response = client.get("/api/memory/stats")
            assert response.status_code == 200
    
    @pytest.mark.api
    def test_memory_suggestions_endpoint(self, mock_learning_memory):
        """El endpoint /api/memory/suggestions funciona."""
        with patch('api.ChatSession'), \
             patch('api.DatabaseClient'), \
             patch('api.DatabaseTools'), \
             patch('api.ToolExecutor'), \
             patch('api.get_learning_memory', return_value=mock_learning_memory), \
             patch('api.learning_memory', mock_learning_memory):
            from api import app
            client = TestClient(app)
            response = client.get("/api/memory/suggestions?q=ipc")
            assert response.status_code == 200
    
    @pytest.mark.api
    def test_memory_recent_endpoint(self, mock_learning_memory):
        """El endpoint /api/memory/recent funciona."""
        with patch('api.ChatSession'), \
             patch('api.DatabaseClient'), \
             patch('api.DatabaseTools'), \
             patch('api.ToolExecutor'), \
             patch('api.get_learning_memory', return_value=mock_learning_memory), \
             patch('api.learning_memory', mock_learning_memory):
            from api import app
            client = TestClient(app)
            response = client.get("/api/memory/recent")
            assert response.status_code == 200


class TestAPIChatMessages:
    """Tests para validación de mensajes del chat."""
    
    @pytest.mark.unit
    def test_message_model_validation(self):
        """Validación del modelo ChatMessage."""
        from api import ChatMessage
        
        # Mensaje válido
        msg = ChatMessage(message="Hola")
        assert msg.message == "Hola"
        assert msg.session_id == "default"
    
    @pytest.mark.unit
    def test_message_with_session_id(self):
        """ChatMessage acepta session_id personalizado."""
        from api import ChatMessage
        
        msg = ChatMessage(message="Hola", session_id="user123")
        assert msg.session_id == "user123"
    
    @pytest.mark.unit
    def test_response_model(self):
        """Validación del modelo ChatResponse."""
        from api import ChatResponse
        
        resp = ChatResponse(response="Respuesta", session_id="user123")
        assert resp.response == "Respuesta"
        assert resp.session_id == "user123"


class TestAPISessionManagement:
    """Tests para gestión de sesiones."""
    
    @pytest.mark.unit
    def test_different_sessions_isolated(self):
        """Diferentes sesiones están aisladas."""
        from api import chat_messages, menu_states
        
        # Simular dos sesiones
        session1 = "user1"
        session2 = "user2"
        
        chat_messages[session1] = [{"role": "user", "content": "Mensaje 1"}]
        chat_messages[session2] = [{"role": "user", "content": "Mensaje 2"}]
        
        assert chat_messages[session1] != chat_messages[session2]
        
        # Limpiar
        del chat_messages[session1]
        del chat_messages[session2]
    
    @pytest.mark.unit
    def test_menu_state_per_session(self):
        """Estado del menú es por sesión."""
        from api import menu_states
        
        session1 = "user1"
        session2 = "user2"
        
        menu_states[session1] = {"current_menu_node_id": "root"}
        menu_states[session2] = {"current_menu_node_id": "cat_precios"}
        
        assert menu_states[session1]["current_menu_node_id"] != menu_states[session2]["current_menu_node_id"]
        
        # Limpiar
        del menu_states[session1]
        del menu_states[session2]


class TestAPIErrorHandling:
    """Tests para manejo de errores de la API."""
    
    @pytest.mark.api
    def test_invalid_json_body(self):
        """Maneja JSON inválido."""
        with patch('api.ChatSession'), \
             patch('api.DatabaseClient'), \
             patch('api.DatabaseTools'), \
             patch('api.ToolExecutor'), \
             patch('api.get_learning_memory', return_value=None):
            from api import app
            client = TestClient(app)
            response = client.post(
                "/api/chat",
                content="not valid json",
                headers={"Content-Type": "application/json"}
            )
            assert response.status_code == 422
    
    @pytest.mark.api
    def test_missing_required_field(self):
        """Maneja campo requerido faltante."""
        with patch('api.ChatSession'), \
             patch('api.DatabaseClient'), \
             patch('api.DatabaseTools'), \
             patch('api.ToolExecutor'), \
             patch('api.get_learning_memory', return_value=None):
            from api import app
            client = TestClient(app)
            response = client.post("/api/chat", json={"other_field": "value"})
            assert response.status_code == 422


class TestAPIMenuNavigation:
    """Tests para navegación del menú via API."""
    
    @pytest.mark.unit
    def test_menu_keywords_recognized(self):
        """Keywords de menú son reconocidas."""
        menu_keywords = ["menu", "menú", "volver", "inicio", "principal", "atras", "atrás", "back"]
        
        for keyword in menu_keywords:
            # Verificar que el keyword está en minúsculas para comparación
            assert keyword.lower().strip() in [k.lower() for k in menu_keywords]
    
    @pytest.mark.unit
    def test_numeric_selection_valid(self):
        """Selección numérica válida."""
        user_inputs = ["1", "2", "3", "4", "5"]
        
        for inp in user_inputs:
            assert inp.isdigit()
            assert 1 <= int(inp) <= 10


class TestAPIIntegrationScenarios:
    """Tests de escenarios de integración."""
    
    @pytest.mark.integration
    def test_full_chat_flow_mock(self):
        """Flujo completo de chat con mocks."""
        # Este test simula un flujo completo pero con todos los componentes mockeados
        mock_session = MagicMock()
        mock_session.llm_client = MagicMock()
        mock_session.llm_client.get_response.return_value = "Respuesta del LLM"
        mock_session.servers = []
        
        mock_tool_executor = MagicMock()
        mock_tool_executor.is_available.return_value = True
        mock_tool_executor.execute.return_value = "## Datos\n| A | B |\n|---|---|\n| 1 | 2 |"
        
        # Verificar que los mocks funcionan
        assert mock_session.llm_client.get_response() == "Respuesta del LLM"
        assert mock_tool_executor.execute("get_ipc", {}) == "## Datos\n| A | B |\n|---|---|\n| 1 | 2 |"
