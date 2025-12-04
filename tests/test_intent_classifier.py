"""Tests para el clasificador de intenciones."""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intent_classifier import (
    classify_intent,
    is_conceptual_question,
    get_topic_from_query,
    is_domain_relevant,
    is_complex_query,
    LOCATION_NAMES
)


class TestClassifyIntent:
    """Tests para la función classify_intent."""
    
    # ==================== PREGUNTAS CONCEPTUALES ====================
    
    @pytest.mark.unit
    def test_que_es_returns_conceptual(self):
        """'¿Qué es X?' debe clasificarse como conceptual."""
        intent, confidence = classify_intent("que es el IPC?")
        assert intent == "conceptual"
        assert confidence >= 0.4
    
    @pytest.mark.unit
    def test_que_significa_returns_conceptual(self):
        """'¿Qué significa X?' debe clasificarse como conceptual."""
        intent, confidence = classify_intent("que significa EPH?")
        assert intent == "conceptual"
        assert confidence >= 0.4
    
    @pytest.mark.unit
    def test_como_funciona_returns_conceptual(self):
        """'¿Cómo funciona X?' debe clasificarse como conceptual."""
        intent, confidence = classify_intent("como funciona el semaforo economico?")
        assert intent == "conceptual"
        assert confidence >= 0.4
    
    @pytest.mark.unit
    def test_para_que_sirve_returns_conceptual(self):
        """'¿Para qué sirve X?' debe clasificarse como conceptual."""
        intent, confidence = classify_intent("para que sirve el IPC")
        assert intent == "conceptual"
        assert confidence >= 0.4
    
    @pytest.mark.unit
    def test_explicame_returns_conceptual(self):
        """'Explícame X' debe clasificarse como conceptual."""
        intent, confidence = classify_intent("explicame el censo")
        assert intent == "conceptual"
        assert confidence >= 0.4
    
    # ==================== SOLICITUDES DE DATOS ====================
    
    @pytest.mark.unit
    def test_dame_returns_data(self):
        """'Dame X' debe clasificarse como data."""
        intent, confidence = classify_intent("dame datos del IPC")
        assert intent == "data"
        assert confidence >= 0.4
    
    @pytest.mark.unit
    def test_ultimo_returns_data(self):
        """'Último X' debe clasificarse como data."""
        intent, confidence = classify_intent("ultimo valor del dolar")
        assert intent == "data"
        assert confidence >= 0.4
    
    @pytest.mark.unit
    def test_muestrame_returns_data(self):
        """'Muéstrame X' debe clasificarse como data."""
        intent, confidence = classify_intent("muestrame la cotizacion del dolar")
        assert intent == "data"
        assert confidence >= 0.4
    
    @pytest.mark.unit
    def test_cuanto_returns_data(self):
        """'¿Cuánto X?' debe clasificarse como data."""
        intent, confidence = classify_intent("cuanto esta el dolar blue")
        assert intent == "data"
        assert confidence >= 0.4
    
    @pytest.mark.unit
    def test_tasa_returns_data(self):
        """Consultas sobre 'tasa' deben clasificarse como data."""
        intent, confidence = classify_intent("tasa de desempleo")
        assert intent == "data"
        assert confidence >= 0.4
    
    # ==================== CASOS AMBIGUOS ====================
    
    @pytest.mark.unit
    def test_single_word_returns_ambiguous(self):
        """Una palabra sola debe ser ambigua."""
        intent, confidence = classify_intent("IPC")
        assert intent == "ambiguous"
        assert confidence == 0.5
    
    @pytest.mark.unit
    def test_empty_string_returns_ambiguous(self):
        """String vacío debe ser ambiguo."""
        intent, confidence = classify_intent("")
        assert intent == "ambiguous"
        assert confidence == 0.5


class TestIsConceptualQuestion:
    """Tests para la función is_conceptual_question."""
    
    @pytest.mark.unit
    def test_que_es_is_conceptual(self):
        """'¿Qué es?' es conceptual."""
        assert is_conceptual_question("que es el IPC?") is True
    
    @pytest.mark.unit
    def test_dame_datos_not_conceptual(self):
        """'Dame datos' NO es conceptual."""
        assert is_conceptual_question("dame datos del IPC") is False
    
    @pytest.mark.unit
    def test_ultimo_valor_not_conceptual(self):
        """'Último valor' NO es conceptual."""
        assert is_conceptual_question("ultimo valor del dolar") is False
    
    @pytest.mark.unit
    def test_como_se_calcula_is_conceptual(self):
        """'¿Cómo se calcula?' es conceptual."""
        assert is_conceptual_question("como se calcula el IPC") is True


class TestGetTopicFromQuery:
    """Tests para la función get_topic_from_query."""
    
    @pytest.mark.unit
    def test_extracts_topic_from_que_es(self):
        """Extrae el tema de '¿Qué es X?'."""
        topic = get_topic_from_query("que es el IPC?")
        assert "ipc" in topic.lower()
    
    @pytest.mark.unit
    def test_extracts_topic_from_que_significa(self):
        """Extrae el tema de '¿Qué significa X?'."""
        topic = get_topic_from_query("que significa EPH?")
        assert "eph" in topic.lower()
    
    @pytest.mark.unit
    def test_removes_question_mark(self):
        """Remueve el signo de interrogación."""
        topic = get_topic_from_query("que es el dolar?")
        assert "?" not in topic


class TestEdgeCases:
    """Tests para casos extremos."""
    
    @pytest.mark.unit
    def test_mixed_case_que_es(self):
        """Funciona con mayúsculas/minúsculas mezcladas."""
        intent, _ = classify_intent("QUE ES el IPC?")
        assert intent == "conceptual"
    
    @pytest.mark.unit
    def test_with_accents(self):
        """Funciona con acentos."""
        intent, _ = classify_intent("qué es el IPC?")
        assert intent == "conceptual"
    
    @pytest.mark.unit
    def test_multiple_spaces(self):
        """Funciona con múltiples espacios."""
        intent, _ = classify_intent("que   es   el   IPC?")
        assert intent == "conceptual"
    
    @pytest.mark.unit
    def test_very_long_query(self):
        """Funciona con queries muy largas."""
        long_query = "dame todos los datos del IPC de los últimos 10 años por favor"
        intent, _ = classify_intent(long_query)
        assert intent == "data"
    
    @pytest.mark.unit
    def test_special_characters(self):
        """Funciona con caracteres especiales."""
        intent, _ = classify_intent("¿Qué es el IPC?")
        assert intent == "conceptual"


class TestDifferentIndicators:
    """Tests para diferentes indicadores económicos."""
    
    @pytest.mark.unit
    @pytest.mark.parametrize("indicator", ["IPC", "EPH", "ECV", "EMAE", "SIPA", "PBG"])
    def test_que_es_with_different_indicators(self, indicator):
        """'¿Qué es X?' funciona con diferentes indicadores."""
        intent, _ = classify_intent(f"que es el {indicator}?")
        assert intent == "conceptual"
    
    @pytest.mark.unit
    @pytest.mark.parametrize("indicator", ["IPC", "dolar", "empleo", "censo", "inflacion"])
    def test_dame_with_different_indicators(self, indicator):
        """'Dame datos de X' funciona con diferentes indicadores."""
        intent, _ = classify_intent(f"dame datos de {indicator}")
        assert intent == "data"


class TestDomainRelevance:
    """Tests para detección de preguntas fuera del dominio."""
    
    # ==================== PREGUNTAS DEL DOMINIO IPECD ====================
    
    @pytest.mark.unit
    @pytest.mark.parametrize("query", [
        "que es el IPC",
        "cuanto esta el dolar",
        "tasa de desempleo",
        "inflacion en corrientes",
        "datos del censo",
        "poblacion de goya",
        "semaforo economico",
        "canasta basica",
        "empleo en argentina",
        "estadisticas de corrientes"
    ])
    def test_domain_relevant_queries(self, query):
        """Queries sobre temas del IPECD son relevantes."""
        assert is_domain_relevant(query) is True
    
    # ==================== PREGUNTAS FUERA DEL DOMINIO ====================
    
    @pytest.mark.unit
    @pytest.mark.parametrize("query", [
        "quien es messi",
        "como esta el clima",
        "cual es la capital de francia",
        "receta de torta",
        "quien gano el mundial",
        "pelicula recomendada",
        "mejor celular 2024",
        "como hacer ejercicio"
    ])
    def test_out_of_domain_queries(self, query):
        """Queries sobre otros temas NO son relevantes."""
        assert is_domain_relevant(query) is False
    
    # ==================== CASOS LÍMITE ====================
    
    @pytest.mark.unit
    def test_empty_query_not_relevant(self):
        """Query vacía no es relevante."""
        assert is_domain_relevant("") is False
    
    @pytest.mark.unit
    def test_single_domain_word_is_relevant(self):
        """Una sola palabra del dominio es relevante."""
        assert is_domain_relevant("dolar") is True
        assert is_domain_relevant("inflacion") is True
        assert is_domain_relevant("censo") is True
    
    @pytest.mark.unit
    def test_mixed_case_domain_words(self):
        """Funciona con mayúsculas/minúsculas."""
        assert is_domain_relevant("DOLAR") is True
        assert is_domain_relevant("IPC") is True
        assert is_domain_relevant("Corrientes") is True


class TestIsComplexQuery:
    """Tests para la función is_complex_query."""
    
    # ==================== CONSULTAS COMPLEJAS ====================
    
    @pytest.mark.unit
    @pytest.mark.parametrize("query", [
        "comparar poblacion de goya y corrientes",
        "poblacion de goya vs corrientes",
        "diferencia entre goya y mercedes",
        "cuantos habitantes tiene goya",
        "cual es la poblacion de corrientes",
        "como esta el dolar",
        "dame el ultimo ipc",
        "cual es la cotizacion del dolar",
    ])
    def test_complex_queries_detected(self, query):
        """Debe detectar consultas complejas."""
        assert is_complex_query(query) is True, f"'{query}' should be complex"
    
    @pytest.mark.unit
    @pytest.mark.parametrize("query", [
        "hola",
        "ayuda",
        "menu",
        "opciones",
        "que hora es",
    ])
    def test_simple_queries_not_complex(self, query):
        """No debe detectar consultas simples como complejas."""
        assert is_complex_query(query) is False, f"'{query}' should NOT be complex"
    
    @pytest.mark.unit
    def test_multiple_locations_is_complex(self):
        """Múltiples ubicaciones indican consulta compleja."""
        assert is_complex_query("goya y corrientes") is True
        assert is_complex_query("entre mercedes y esquina") is True
    
    @pytest.mark.unit
    def test_direct_query_patterns(self):
        """Patrones de consulta directa + indicador = compleja."""
        assert is_complex_query("como esta el semaforo economico") is True
        assert is_complex_query("cual es el ipc") is True
        assert is_complex_query("dame la cotizacion del dolar") is True


class TestLocationNames:
    """Tests para nombres de ubicaciones."""
    
    @pytest.mark.unit
    def test_includes_corrientes_municipalities(self):
        """Debe incluir municipios de Corrientes."""
        assert 'goya' in LOCATION_NAMES
        assert 'corrientes' in LOCATION_NAMES
        assert 'mercedes' in LOCATION_NAMES
        assert 'bella vista' in LOCATION_NAMES
    
    @pytest.mark.unit
    def test_includes_typo_variants(self):
        """Debe incluir variantes con errores de tipeo."""
        assert 'corrientrs' in LOCATION_NAMES
        assert 'corientes' in LOCATION_NAMES
        assert 'ctes' in LOCATION_NAMES
    
    @pytest.mark.unit
    def test_includes_provinces(self):
        """Debe incluir provincias argentinas."""
        assert 'buenos aires' in LOCATION_NAMES
        assert 'córdoba' in LOCATION_NAMES or 'cordoba' in LOCATION_NAMES
        assert 'mendoza' in LOCATION_NAMES
    
    @pytest.mark.unit
    def test_includes_regions(self):
        """Debe incluir regiones."""
        assert 'nea' in LOCATION_NAMES
        assert 'gba' in LOCATION_NAMES
        assert 'patagonia' in LOCATION_NAMES

