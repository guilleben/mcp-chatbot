"""Tests para QueryRouter - enrutamiento inteligente de consultas."""
import pytest
from unittest.mock import MagicMock
from query_router import QueryRouter, LOCATION_NAMES, LOCATION_CANONICAL, TOOL_MAPPINGS


class TestLocationNames:
    """Tests para nombres de ubicaciones y variantes."""
    
    @pytest.mark.unit
    def test_location_names_includes_common_cities(self):
        """Debe incluir ciudades comunes de Corrientes."""
        assert 'goya' in LOCATION_NAMES
        assert 'corrientes' in LOCATION_NAMES
        assert 'mercedes' in LOCATION_NAMES
    
    @pytest.mark.unit
    def test_location_names_includes_typo_variants(self):
        """Debe incluir variantes con errores de tipeo."""
        assert 'corrientrs' in LOCATION_NAMES
        assert 'corientes' in LOCATION_NAMES
        assert 'ctes' in LOCATION_NAMES
    
    @pytest.mark.unit
    def test_location_canonical_maps_variants(self):
        """Debe mapear variantes a nombres canónicos."""
        assert LOCATION_CANONICAL['corrientrs'] == 'corrientes'
        assert LOCATION_CANONICAL['corientes'] == 'corrientes'
        assert LOCATION_CANONICAL['bsas'] == 'buenos aires'


class TestToolMappings:
    """Tests para mapeo de herramientas."""
    
    @pytest.mark.unit
    def test_all_expected_tools_mapped(self):
        """Todas las herramientas esperadas deben estar mapeadas."""
        expected_tools = [
            'get_censo', 'get_dolar', 'get_ipc', 'get_empleo',
            'get_semaforo', 'get_patentamientos', 'get_aeropuertos',
            'get_combustible', 'get_canasta_basica', 'get_pobreza',
            'get_ecv', 'get_oede'
        ]
        for tool in expected_tools:
            assert tool in TOOL_MAPPINGS, f"Tool {tool} not mapped"
    
    @pytest.mark.unit
    def test_tool_mapping_has_keywords(self):
        """Cada herramienta debe tener palabras clave."""
        for tool_name, config in TOOL_MAPPINGS.items():
            assert 'keywords' in config, f"{tool_name} missing keywords"
            assert len(config['keywords']) > 0, f"{tool_name} has empty keywords"


class TestQueryRouterDetection:
    """Tests para detección de herramientas."""
    
    @pytest.fixture
    def router(self):
        mock_executor = MagicMock()
        mock_executor.is_available.return_value = True
        return QueryRouter(mock_executor)
    
    @pytest.mark.unit
    @pytest.mark.parametrize("query,expected_tool", [
        ("poblacion de goya", "get_censo"),
        ("habitantes de corrientes", "get_censo"),
        ("cotizacion del dolar", "get_dolar"),
        ("dolar blue", "get_dolar"),
        ("ipc de octubre", "get_ipc"),
        ("inflacion mensual", "get_ipc"),
        ("tasa de empleo", "get_empleo"),
        ("desempleo en corrientes", "get_empleo"),
        ("semaforo economico", "get_semaforo"),
        ("patentamientos de autos", "get_patentamientos"),
        ("pasajeros aeropuerto", "get_aeropuertos"),
        ("ventas de combustible", "get_combustible"),
        ("canasta basica", "get_canasta_basica"),
        ("linea de pobreza", "get_pobreza"),
        ("encuesta calidad de vida", "get_ecv"),
        ("datos del oede", "get_oede"),  # "observatorio de empleo" detecta "empleo" primero
    ])
    def test_detect_tool_by_keywords(self, router, query, expected_tool):
        """Debe detectar la herramienta correcta por palabras clave."""
        detected = router.detect_tool(query)
        assert detected == expected_tool, f"Query '{query}' should detect {expected_tool}, got {detected}"
    
    @pytest.mark.unit
    def test_detect_tool_returns_none_for_unknown(self, router):
        """Debe retornar None para consultas sin herramienta."""
        assert router.detect_tool("que hora es") is None
        assert router.detect_tool("quien es messi") is None


class TestQueryRouterLocations:
    """Tests para extracción de ubicaciones."""
    
    @pytest.fixture
    def router(self):
        mock_executor = MagicMock()
        return QueryRouter(mock_executor)
    
    @pytest.mark.unit
    def test_extract_single_location(self, router):
        """Debe extraer una ubicación."""
        locations = router.extract_locations("poblacion de goya")
        assert 'goya' in locations
    
    @pytest.mark.unit
    def test_extract_multiple_locations(self, router):
        """Debe extraer múltiples ubicaciones."""
        locations = router.extract_locations("comparar goya y corrientes")
        assert 'goya' in locations
        assert 'corrientes' in locations
    
    @pytest.mark.unit
    def test_extract_location_with_typo(self, router):
        """Debe extraer ubicación con error de tipeo y normalizarla."""
        locations = router.extract_locations("poblacion de corrientrs")
        assert 'corrientes' in locations  # Normalizado
    
    @pytest.mark.unit
    def test_extract_no_duplicates(self, router):
        """No debe duplicar ubicaciones."""
        locations = router.extract_locations("corrientes y corrientrs")
        assert locations.count('corrientes') == 1


class TestQueryRouterComparison:
    """Tests para detección de comparaciones."""
    
    @pytest.fixture
    def router(self):
        mock_executor = MagicMock()
        return QueryRouter(mock_executor)
    
    @pytest.mark.unit
    @pytest.mark.parametrize("query", [
        "comparar goya y corrientes",
        "goya vs corrientes",
        "diferencia entre goya y mercedes",
        "poblacion de goya y corrientes",
    ])
    def test_is_comparison_query_true(self, router, query):
        """Debe detectar consultas de comparación."""
        assert router.is_comparison_query(query) is True
    
    @pytest.mark.unit
    def test_is_comparison_query_false(self, router):
        """No debe detectar consultas simples como comparación."""
        assert router.is_comparison_query("poblacion de goya") is False
        assert router.is_comparison_query("cotizacion del dolar") is False


class TestQueryRouterExecution:
    """Tests para ejecución de consultas."""
    
    @pytest.fixture
    def router_with_mock(self):
        mock_executor = MagicMock()
        mock_executor.is_available.return_value = True
        mock_executor.execute.return_value = "## Datos de prueba\n| Col1 | Col2 |\n|---|---|\n| A | B |"
        return QueryRouter(mock_executor), mock_executor
    
    @pytest.mark.unit
    def test_route_and_execute_simple_query(self, router_with_mock):
        """Debe ejecutar consulta simple correctamente."""
        router, mock_exec = router_with_mock
        result = router.route_and_execute("poblacion de goya")
        
        assert result is not None
        tool_used, response = result
        assert tool_used == "get_censo"
        mock_exec.execute.assert_called()
    
    @pytest.mark.unit
    def test_route_and_execute_comparison(self, router_with_mock):
        """Debe ejecutar comparación con múltiples ubicaciones."""
        router, mock_exec = router_with_mock
        result = router.route_and_execute("comparar poblacion de goya y corrientes")
        
        assert result is not None
        tool_used, response = result
        assert tool_used == "get_censo"
        # Debe haber llamado execute múltiples veces (una por ubicación)
        assert mock_exec.execute.call_count >= 2
    
    @pytest.mark.unit
    def test_route_and_execute_no_tool(self, router_with_mock):
        """Debe retornar None si no detecta herramienta."""
        router, _ = router_with_mock
        result = router.route_and_execute("que hora es")
        assert result is None
    
    @pytest.mark.unit
    def test_route_and_execute_executor_unavailable(self):
        """Debe retornar None si executor no está disponible."""
        mock_executor = MagicMock()
        mock_executor.is_available.return_value = False
        router = QueryRouter(mock_executor)
        
        result = router.route_and_execute("poblacion de goya")
        assert result is None

