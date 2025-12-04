"""Tests para las herramientas de base de datos."""
import pytest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_tools_server import DatabaseTools


class TestDatabaseToolsInit:
    """Tests para inicialización de DatabaseTools."""
    
    @pytest.fixture
    def tools_with_env(self, monkeypatch):
        """Crea DatabaseTools con variables de entorno mockeadas."""
        monkeypatch.setenv('HOST_DBB', 'localhost')
        monkeypatch.setenv('DB_PORT', '3306')
        monkeypatch.setenv('USER_DBB', 'test')
        monkeypatch.setenv('PASSWORD_DBB', 'test')
        monkeypatch.setenv('NAME_DBB_DATALAKE_ECONOMICO', 'datalake-economico')
        monkeypatch.setenv('NAME_DBB_DWH_ECONOMICO', 'dhw_economico')
        monkeypatch.setenv('NAME_DBB_DWH_SOCIO', 'dhw_sociodemografico')
        return DatabaseTools()
    
    @pytest.mark.unit
    def test_init_sets_databases(self, tools_with_env):
        """Inicialización configura las bases de datos."""
        assert tools_with_env.databases['datalake_economico'] == 'datalake-economico'
        assert tools_with_env.databases['dwh_economico'] == 'dhw_economico'
        assert tools_with_env.databases['dwh_socio'] == 'dhw_sociodemografico'
    
    @pytest.mark.unit
    def test_init_sets_connection_config(self, tools_with_env):
        """Inicialización configura la conexión."""
        assert tools_with_env.host == 'localhost'
        assert tools_with_env.port == 3306
        assert tools_with_env.user == 'test'


class TestDatabaseToolsFormatting:
    """Tests para formateo de datos."""
    
    @pytest.fixture
    def tools(self, monkeypatch):
        """Crea DatabaseTools con configuración de prueba."""
        monkeypatch.setenv('HOST_DBB', 'localhost')
        monkeypatch.setenv('DB_PORT', '3306')
        monkeypatch.setenv('USER_DBB', 'test')
        monkeypatch.setenv('PASSWORD_DBB', 'test')
        return DatabaseTools()
    
    @pytest.mark.unit
    def test_format_number_with_thousands(self, tools):
        """Formatea números con separador de miles."""
        result = tools._format_number(1234567)
        assert "1" in result
        # Debe tener algún tipo de separador
        assert len(result) > 6
    
    @pytest.mark.unit
    def test_format_number_with_none(self, tools):
        """Maneja None en formato de número."""
        result = tools._format_number(None)
        # Puede ser N/A, 0, -, s/d u otro valor por defecto
        assert result is not None
    
    @pytest.mark.unit
    def test_format_number_with_zero(self, tools):
        """Formatea cero correctamente."""
        result = tools._format_number(0)
        assert "0" in result


class TestDatabaseToolsGetIPC:
    """Tests para get_ipc."""
    
    @pytest.fixture
    def tools_with_mock_db(self, monkeypatch):
        """Crea DatabaseTools con mock de base de datos."""
        monkeypatch.setenv('HOST_DBB', 'localhost')
        monkeypatch.setenv('DB_PORT', '3306')
        monkeypatch.setenv('USER_DBB', 'test')
        monkeypatch.setenv('PASSWORD_DBB', 'test')
        tools = DatabaseTools()
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        # Datos de prueba para IPC
        mock_cursor.fetchall.return_value = [
            {'region': 'NEA', 'fecha': '2025-10-01', 'variacion_mensual': 0.025, 'variacion_interanual': 0.30},
            {'region': 'GBA', 'fecha': '2025-10-01', 'variacion_mensual': 0.027, 'variacion_interanual': 0.32}
        ]
        
        tools._get_connection = MagicMock(return_value=mock_conn)
        return tools
    
    @pytest.mark.unit
    def test_get_ipc_returns_string(self, tools_with_mock_db):
        """get_ipc retorna string formateado."""
        result = tools_with_mock_db.get_ipc()
        assert isinstance(result, str)
    
    @pytest.mark.unit
    def test_get_ipc_contains_header(self, tools_with_mock_db):
        """get_ipc contiene header."""
        result = tools_with_mock_db.get_ipc()
        assert "IPC" in result or "Precios" in result or "##" in result


class TestDatabaseToolsGetDolar:
    """Tests para get_dolar."""
    
    @pytest.fixture
    def tools_with_mock_db(self, monkeypatch):
        """Crea DatabaseTools con mock de base de datos."""
        monkeypatch.setenv('HOST_DBB', 'localhost')
        monkeypatch.setenv('DB_PORT', '3306')
        monkeypatch.setenv('USER_DBB', 'test')
        monkeypatch.setenv('PASSWORD_DBB', 'test')
        tools = DatabaseTools()
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        mock_cursor.fetchall.return_value = [
            {'fecha': '2025-10-01', 'compra': 1100.0, 'venta': 1150.0}
        ]
        
        tools._get_connection = MagicMock(return_value=mock_conn)
        return tools
    
    @pytest.mark.unit
    def test_get_dolar_blue(self, tools_with_mock_db):
        """get_dolar con tipo blue."""
        result = tools_with_mock_db.get_dolar(tipo="blue")
        assert isinstance(result, str)
    
    @pytest.mark.unit
    def test_get_dolar_oficial(self, tools_with_mock_db):
        """get_dolar con tipo oficial."""
        result = tools_with_mock_db.get_dolar(tipo="oficial")
        assert isinstance(result, str)
    
    @pytest.mark.unit
    def test_get_dolar_mep(self, tools_with_mock_db):
        """get_dolar con tipo mep."""
        result = tools_with_mock_db.get_dolar(tipo="mep")
        assert isinstance(result, str)


class TestDatabaseToolsGetEmpleo:
    """Tests para get_empleo."""
    
    @pytest.fixture
    def tools_with_mock_db(self, monkeypatch):
        """Crea DatabaseTools con mock de base de datos."""
        monkeypatch.setenv('HOST_DBB', 'localhost')
        monkeypatch.setenv('DB_PORT', '3306')
        monkeypatch.setenv('USER_DBB', 'test')
        monkeypatch.setenv('PASSWORD_DBB', 'test')
        tools = DatabaseTools()
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        mock_cursor.fetchall.return_value = [
            {
                'Aglomerado': 'Corrientes',
                'Año': 2025,
                'Trimestre': 2,
                'Tasa de Actividad': 0.41,
                'Tasa de Empleo': 0.38,
                'Tasa de desocupación': 0.067
            }
        ]
        
        tools._get_connection = MagicMock(return_value=mock_conn)
        return tools
    
    @pytest.mark.unit
    def test_get_empleo_eph(self, tools_with_mock_db):
        """get_empleo con tipo eph."""
        result = tools_with_mock_db.get_empleo(tipo="eph")
        assert isinstance(result, str)
    
    @pytest.mark.unit
    def test_get_empleo_sipa(self, tools_with_mock_db):
        """get_empleo con tipo sipa."""
        result = tools_with_mock_db.get_empleo(tipo="sipa")
        assert isinstance(result, str)


class TestDatabaseToolsGetCenso:
    """Tests para get_censo."""
    
    @pytest.fixture
    def tools_with_mock_db(self, monkeypatch):
        """Crea DatabaseTools con mock de base de datos."""
        monkeypatch.setenv('HOST_DBB', 'localhost')
        monkeypatch.setenv('DB_PORT', '3306')
        monkeypatch.setenv('USER_DBB', 'test')
        monkeypatch.setenv('PASSWORD_DBB', 'test')
        tools = DatabaseTools()
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        mock_cursor.fetchall.return_value = [
            {'municipio': 'Corrientes', 'pob_2010': 358223, 'pob_2022': 409000, 'var_relativa': 14.2},
            {'municipio': 'Goya', 'pob_2010': 88427, 'pob_2022': 102000, 'var_relativa': 15.4}
        ]
        
        tools._get_connection = MagicMock(return_value=mock_conn)
        return tools
    
    @pytest.mark.unit
    def test_get_censo_returns_string(self, tools_with_mock_db):
        """get_censo retorna string formateado."""
        result = tools_with_mock_db.get_censo()
        assert isinstance(result, str)
    
    @pytest.mark.unit
    def test_get_censo_with_municipio(self, tools_with_mock_db):
        """get_censo con filtro de municipio."""
        result = tools_with_mock_db.get_censo(municipio="Corrientes")
        assert isinstance(result, str)
    
    @pytest.mark.unit
    def test_get_censo_contains_table(self, tools_with_mock_db):
        """get_censo contiene tabla markdown."""
        result = tools_with_mock_db.get_censo()
        assert "|" in result  # Separador de tabla markdown


class TestDatabaseToolsGetCensoDepartamentos:
    """Tests para get_censo_departamentos."""
    
    @pytest.fixture
    def tools_with_mock_db(self, monkeypatch):
        """Crea DatabaseTools con mock de base de datos."""
        monkeypatch.setenv('HOST_DBB', 'localhost')
        monkeypatch.setenv('DB_PORT', '3306')
        monkeypatch.setenv('USER_DBB', 'test')
        monkeypatch.setenv('PASSWORD_DBB', 'test')
        tools = DatabaseTools()
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        mock_cursor.fetchall.return_value = [
            {'departamento': 'Capital', 'pob_2010': 358223, 'pob_2022': 409000},
            {'departamento': 'Goya', 'pob_2010': 88427, 'pob_2022': 102000}
        ]
        
        tools._get_connection = MagicMock(return_value=mock_conn)
        return tools
    
    @pytest.mark.unit
    def test_get_censo_departamentos_returns_string(self, tools_with_mock_db):
        """get_censo_departamentos retorna string formateado."""
        result = tools_with_mock_db.get_censo_departamentos()
        assert isinstance(result, str)
    
    @pytest.mark.unit
    def test_get_censo_departamentos_contains_header(self, tools_with_mock_db):
        """get_censo_departamentos contiene header."""
        result = tools_with_mock_db.get_censo_departamentos()
        assert "Departamento" in result or "##" in result


class TestDatabaseToolsGetSemaforo:
    """Tests para get_semaforo."""
    
    @pytest.fixture
    def tools_with_mock_db(self, monkeypatch):
        """Crea DatabaseTools con mock de base de datos."""
        monkeypatch.setenv('HOST_DBB', 'localhost')
        monkeypatch.setenv('DB_PORT', '3306')
        monkeypatch.setenv('USER_DBB', 'test')
        monkeypatch.setenv('PASSWORD_DBB', 'test')
        tools = DatabaseTools()
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        mock_cursor.fetchone.return_value = {
            'fecha': '2025-10-01',
            'combustible_vendido': 5.2,
            'patentamiento_0km_auto': -2.1,
            'empleo_sipa': 3.5
        }
        
        tools._get_connection = MagicMock(return_value=mock_conn)
        return tools
    
    @pytest.mark.unit
    def test_get_semaforo_returns_string(self, tools_with_mock_db):
        """get_semaforo retorna string formateado."""
        result = tools_with_mock_db.get_semaforo()
        assert isinstance(result, str)


class TestDatabaseToolsErrorHandling:
    """Tests para manejo de errores."""
    
    @pytest.fixture
    def tools_with_failing_db(self, monkeypatch):
        """Crea DatabaseTools con DB que falla."""
        monkeypatch.setenv('HOST_DBB', 'localhost')
        monkeypatch.setenv('DB_PORT', '3306')
        monkeypatch.setenv('USER_DBB', 'test')
        monkeypatch.setenv('PASSWORD_DBB', 'test')
        tools = DatabaseTools()
        
        tools._get_connection = MagicMock(side_effect=Exception("Connection failed"))
        return tools
    
    @pytest.mark.unit
    def test_get_ipc_handles_db_error(self, tools_with_failing_db):
        """get_ipc maneja error de conexión."""
        result = tools_with_failing_db.get_ipc()
        assert "Error" in result or "error" in result.lower()
    
    @pytest.mark.unit
    def test_get_dolar_handles_db_error(self, tools_with_failing_db):
        """get_dolar maneja error de conexión."""
        result = tools_with_failing_db.get_dolar()
        assert "Error" in result or "error" in result.lower()
    
    @pytest.mark.unit
    def test_get_censo_handles_db_error(self, tools_with_failing_db):
        """get_censo maneja error de conexión."""
        result = tools_with_failing_db.get_censo()
        assert "Error" in result or "error" in result.lower()


class TestDatabaseToolsNoData:
    """Tests para cuando no hay datos."""
    
    @pytest.fixture
    def tools_with_empty_db(self, monkeypatch):
        """Crea DatabaseTools con DB vacía."""
        monkeypatch.setenv('HOST_DBB', 'localhost')
        monkeypatch.setenv('DB_PORT', '3306')
        monkeypatch.setenv('USER_DBB', 'test')
        monkeypatch.setenv('PASSWORD_DBB', 'test')
        tools = DatabaseTools()
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = None
        
        tools._get_connection = MagicMock(return_value=mock_conn)
        return tools
    
    @pytest.mark.unit
    def test_get_ipc_no_data(self, tools_with_empty_db):
        """get_ipc maneja sin datos."""
        result = tools_with_empty_db.get_ipc()
        assert "no" in result.lower() or "encontr" in result.lower()
    
    @pytest.mark.unit
    def test_get_censo_no_data(self, tools_with_empty_db):
        """get_censo maneja sin datos."""
        result = tools_with_empty_db.get_censo()
        assert "no" in result.lower() or "encontr" in result.lower()

