"""Tests para el ejecutor de herramientas."""
import pytest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tool_executor import ToolExecutor


class TestToolExecutorBasic:
    """Tests básicos del ToolExecutor."""
    
    @pytest.fixture
    def mock_db_tools(self):
        """Mock de DatabaseTools."""
        mock = MagicMock()
        mock.get_ipc.return_value = "## IPC\n| Region | Valor |\n|--------|-------|\n| NEA | 2.5% |"
        mock.get_dolar.return_value = "## Dólar Blue\n| Compra | Venta |\n|--------|-------|\n| $1100 | $1150 |"
        mock.get_empleo.return_value = "## Empleo\n| Tasa | Valor |\n|------|-------|\n| Actividad | 41% |"
        mock.get_censo.return_value = "## Censo\n| Municipio | Población |\n|-----------|----------|\n| Corrientes | 409000 |"
        mock.get_censo_departamentos.return_value = "## Censo por Depto\n| Depto | Pob |\n|-------|-----|\n| Capital | 409000 |"
        mock.get_semaforo.return_value = "## Semáforo\n🟢 Positivo"
        mock.get_canasta_basica.return_value = "## Canasta Básica\n| CBT | CBA |\n|-----|-----|\n| $500k | $250k |"
        mock.get_ecv.return_value = "## ECV\n| Indicador | Valor |\n|-----------|-------|\n| Empleo | 60% |"
        mock.get_combustible.return_value = "## Combustible\n| Provincia | Ventas |\n|-----------|--------|\n| Corrientes | 1000 |"
        mock.search_database.return_value = "Resultados de búsqueda..."
        return mock
    
    @pytest.fixture
    def executor(self, mock_db_tools):
        """Crea ToolExecutor con mock de DB."""
        return ToolExecutor(mock_db_tools)
    
    @pytest.fixture
    def executor_without_db(self):
        """Crea ToolExecutor sin DB."""
        return ToolExecutor(None)
    
    # ==================== AVAILABILITY TESTS ====================
    
    @pytest.mark.unit
    def test_is_available_with_db_tools(self, executor):
        """is_available retorna True con db_tools."""
        assert executor.is_available() is True
    
    @pytest.mark.unit
    def test_is_available_without_db_tools(self, executor_without_db):
        """is_available retorna False sin db_tools."""
        assert executor_without_db.is_available() is False
    
    @pytest.mark.unit
    def test_get_available_tools(self, executor):
        """get_available_tools retorna lista de herramientas."""
        tools = executor.get_available_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0
        assert "get_ipc" in tools
        assert "get_dolar" in tools
        assert "get_censo" in tools


class TestToolExecutorExecution:
    """Tests de ejecución de herramientas."""
    
    @pytest.fixture
    def mock_db_tools(self):
        """Mock de DatabaseTools."""
        mock = MagicMock()
        mock.get_ipc.return_value = "## IPC Data"
        mock.get_dolar.return_value = "## Dólar Data"
        mock.get_empleo.return_value = "## Empleo Data"
        mock.get_censo.return_value = "## Censo Data"
        mock.get_censo_departamentos.return_value = "## Censo Deptos Data"
        mock.get_semaforo.return_value = "## Semáforo Data"
        mock.get_canasta_basica.return_value = "## Canasta Data"
        mock.get_ecv.return_value = "## ECV Data"
        mock.get_combustible.return_value = "## Combustible Data"
        mock.get_patentamientos.return_value = "## Patentamientos Data"
        mock.get_aeropuertos.return_value = "## Aeropuertos Data"
        mock.get_oede.return_value = "## OEDE Data"
        mock.get_pobreza.return_value = "## Pobreza Data"
        mock.search_database.return_value = "## Search Results"
        return mock
    
    @pytest.fixture
    def executor(self, mock_db_tools):
        """Crea ToolExecutor con mock de DB."""
        return ToolExecutor(mock_db_tools)
    
    @pytest.mark.unit
    def test_execute_get_ipc(self, executor, mock_db_tools):
        """Ejecuta get_ipc correctamente."""
        result = executor.execute("get_ipc", {})
        assert result == "## IPC Data"
        mock_db_tools.get_ipc.assert_called_once()
    
    @pytest.mark.unit
    def test_execute_get_dolar(self, executor, mock_db_tools):
        """Ejecuta get_dolar correctamente."""
        result = executor.execute("get_dolar", {"tipo": "blue"})
        assert result == "## Dólar Data"
        mock_db_tools.get_dolar.assert_called_once_with(tipo="blue")
    
    @pytest.mark.unit
    def test_execute_get_empleo(self, executor, mock_db_tools):
        """Ejecuta get_empleo correctamente."""
        result = executor.execute("get_empleo", {"tipo": "eph"})
        assert result == "## Empleo Data"
        mock_db_tools.get_empleo.assert_called_once_with(tipo="eph")
    
    @pytest.mark.unit
    def test_execute_get_censo(self, executor, mock_db_tools):
        """Ejecuta get_censo correctamente."""
        result = executor.execute("get_censo", {})
        assert result == "## Censo Data"
        mock_db_tools.get_censo.assert_called_once()
    
    @pytest.mark.unit
    def test_execute_get_censo_departamentos(self, executor, mock_db_tools):
        """Ejecuta get_censo_departamentos correctamente."""
        result = executor.execute("get_censo_departamentos", {})
        assert result == "## Censo Deptos Data"
        mock_db_tools.get_censo_departamentos.assert_called_once()
    
    @pytest.mark.unit
    def test_execute_get_semaforo(self, executor, mock_db_tools):
        """Ejecuta get_semaforo correctamente."""
        result = executor.execute("get_semaforo", {})
        assert result == "## Semáforo Data"
        mock_db_tools.get_semaforo.assert_called_once()
    
    @pytest.mark.unit
    def test_execute_get_canasta_basica(self, executor, mock_db_tools):
        """Ejecuta get_canasta_basica correctamente."""
        result = executor.execute("get_canasta_basica", {})
        assert result == "## Canasta Data"
        mock_db_tools.get_canasta_basica.assert_called_once()
    
    @pytest.mark.unit
    def test_execute_get_ecv(self, executor, mock_db_tools):
        """Ejecuta get_ecv correctamente."""
        result = executor.execute("get_ecv", {})
        assert result == "## ECV Data"
        mock_db_tools.get_ecv.assert_called_once()
    
    @pytest.mark.unit
    def test_execute_get_patentamientos(self, executor, mock_db_tools):
        """Ejecuta get_patentamientos correctamente."""
        result = executor.execute("get_patentamientos", {})
        assert result == "## Patentamientos Data"
        mock_db_tools.get_patentamientos.assert_called_once()
    
    @pytest.mark.unit
    def test_execute_get_aeropuertos(self, executor, mock_db_tools):
        """Ejecuta get_aeropuertos correctamente."""
        result = executor.execute("get_aeropuertos", {})
        assert result == "## Aeropuertos Data"
        mock_db_tools.get_aeropuertos.assert_called_once()
    
    @pytest.mark.unit
    def test_execute_get_oede(self, executor, mock_db_tools):
        """Ejecuta get_oede correctamente."""
        result = executor.execute("get_oede", {})
        assert result == "## OEDE Data"
        mock_db_tools.get_oede.assert_called_once()
    
    @pytest.mark.unit
    def test_execute_get_pobreza(self, executor, mock_db_tools):
        """Ejecuta get_pobreza correctamente."""
        result = executor.execute("get_pobreza", {})
        assert result == "## Pobreza Data"
        mock_db_tools.get_pobreza.assert_called_once()


class TestToolExecutorErrors:
    """Tests de manejo de errores."""
    
    @pytest.fixture
    def executor_without_db(self):
        """Crea ToolExecutor sin DB."""
        return ToolExecutor(None)
    
    @pytest.fixture
    def executor_with_failing_tool(self):
        """Crea ToolExecutor con herramienta que falla."""
        mock = MagicMock()
        mock.get_ipc.side_effect = Exception("Database error")
        return ToolExecutor(mock)
    
    @pytest.mark.unit
    def test_execute_without_db_tools(self, executor_without_db):
        """Retorna error si no hay db_tools."""
        result = executor_without_db.execute("get_ipc", {})
        assert "Error" in result or "error" in result.lower()
    
    @pytest.mark.unit
    def test_execute_unknown_tool(self):
        """Retorna error para herramienta desconocida."""
        mock = MagicMock()
        executor = ToolExecutor(mock)
        result = executor.execute("unknown_tool", {})
        assert "no disponible" in result.lower() or "not" in result.lower()
    
    @pytest.mark.unit
    def test_execute_handles_exception(self, executor_with_failing_tool):
        """Maneja excepciones de las herramientas."""
        result = executor_with_failing_tool.execute("get_ipc", {})
        assert "error" in result.lower() or "lo siento" in result.lower()
    
    @pytest.mark.unit
    def test_execute_with_none_args(self):
        """Maneja args=None correctamente."""
        mock = MagicMock()
        mock.get_ipc.return_value = "OK"
        executor = ToolExecutor(mock)
        result = executor.execute("get_ipc", None)
        assert result == "OK"


class TestToolExecutorArgs:
    """Tests de manejo de argumentos."""
    
    @pytest.fixture
    def mock_db_tools(self):
        """Mock de DatabaseTools."""
        mock = MagicMock()
        mock.get_dolar.return_value = "Dólar"
        mock.get_empleo.return_value = "Empleo"
        mock.get_censo.return_value = "Censo"
        return mock
    
    @pytest.fixture
    def executor(self, mock_db_tools):
        """Crea ToolExecutor con mock de DB."""
        return ToolExecutor(mock_db_tools)
    
    @pytest.mark.unit
    def test_passes_args_to_tool(self, executor, mock_db_tools):
        """Pasa argumentos correctamente a la herramienta."""
        executor.execute("get_dolar", {"tipo": "blue"})
        mock_db_tools.get_dolar.assert_called_with(tipo="blue")
    
    @pytest.mark.unit
    def test_passes_multiple_args(self, executor, mock_db_tools):
        """Pasa múltiples argumentos correctamente."""
        executor.execute("get_empleo", {"tipo": "eph", "provincia": "corrientes"})
        mock_db_tools.get_empleo.assert_called_with(tipo="eph", provincia="corrientes")
    
    @pytest.mark.unit
    def test_empty_args_dict(self, executor, mock_db_tools):
        """Maneja diccionario de args vacío."""
        executor.execute("get_censo", {})
        mock_db_tools.get_censo.assert_called_with()


class TestAllRegisteredTools:
    """Tests para verificar que todas las herramientas están registradas."""
    
    @pytest.mark.unit
    def test_all_tools_registered(self):
        """Todas las herramientas esperadas están registradas."""
        mock = MagicMock()
        executor = ToolExecutor(mock)
        
        expected_tools = [
            "get_ipc",
            "get_dolar",
            "get_empleo",
            "get_semaforo",
            "get_censo",
            "get_censo_departamentos",
            "get_combustible",
            "get_canasta_basica",
            "get_ecv",
            "get_patentamientos",
            "get_aeropuertos",
            "get_oede",
            "get_pobreza",
            "search_database"
        ]
        
        available = executor.get_available_tools()
        for tool in expected_tools:
            assert tool in available, f"Tool {tool} not registered"

