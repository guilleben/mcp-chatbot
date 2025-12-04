"""Clasificador de intención para distinguir preguntas conceptuales de solicitudes de datos."""
import re
from typing import Tuple


# Términos del dominio IPECD (estadísticas, economía, demografía)
DOMAIN_KEYWORDS = {
    # Indicadores económicos
    'ipc', 'inflacion', 'inflación', 'precios', 'canasta', 'basica', 'básica',
    'dolar', 'dólar', 'blue', 'oficial', 'mep', 'ccl', 'cotizacion', 'cotización',
    'empleo', 'desempleo', 'trabajo', 'eph', 'sipa', 'salario', 'salarios',
    'semaforo', 'semáforo', 'economico', 'económico', 'economía', 'economia',
    'censo', 'poblacion', 'población', 'habitantes', 'municipio', 'departamento',
    'ecv', 'calidad', 'vida', 'encuesta',
    'emae', 'actividad', 'pbg', 'producto', 'bruto',
    'combustible', 'nafta', 'gasoil',
    'exportacion', 'exportaciones', 'importacion', 'importaciones',
    'industria', 'produccion', 'producción', 'ipi',
    'ripte', 'remuneracion', 'remuneración', 'smvm', 'minimo', 'mínimo', 'sueldo', 'sueldos',
    # Patentamientos y transporte
    'patentamiento', 'patentamientos', 'vehiculos', 'vehículos', 'autos', 'motos', '0km', 'dnrpa',
    'aeropuerto', 'aeropuertos', 'pasajeros', 'vuelos', 'anac', 'avion', 'avión',
    # OEDE y empleo sectorial
    'oede', 'observatorio', 'empresas', 'sectores', 'dinamica', 'dinámica', 'empresarial',
    # Pobreza e indigencia
    'pobreza', 'indigencia', 'cbt', 'cba', 'linea', 'línea',
    # Nuevos indicadores
    'supermercado', 'supermercados', 'autoservicio', 'facturacion', 'facturación',
    'construccion', 'construcción', 'ieric', 'obras', 'edificacion', 'edificación',
    'ipicorr', 'corrientes',
    # Términos estadísticos
    'estadistica', 'estadísticas', 'datos', 'indicador', 'indicadores',
    'tasa', 'tasas', 'porcentaje', 'variacion', 'variación', 'interanual', 'mensual',
    'corrientes', 'argentina', 'provincia', 'region', 'región', 'nea',
    # Términos del IPECD
    'ipecd', 'instituto', 'censos'
}


# Palabras que parecen del dominio pero NO lo son (evitar falsos positivos)
OUT_OF_DOMAIN_KEYWORDS = {
    'salud', 'hospital', 'medico', 'médico', 'enfermedad', 'vacuna', 'covid',
    'educacion', 'educación', 'escuela', 'universidad', 'colegio',
    'clima', 'tiempo', 'temperatura', 'lluvia',
    'futbol', 'fútbol', 'deporte', 'messi', 'maradona',
    'politica', 'política', 'presidente', 'gobernador', 'elecciones',
    'receta', 'cocina', 'comida',
    'pelicula', 'película', 'musica', 'música', 'serie'
}

# Palabras genéricas que no cuentan como indicadores específicos
GENERIC_WORDS = {
    'datos', 'informacion', 'información', 'dame', 'quiero', 'necesito',
    'mostrar', 'ver', 'buscar', 'consultar', 'ultimo', 'último', 'actual'
}

# Indicadores específicos del IPECD (más peso que palabras genéricas)
SPECIFIC_INDICATORS = {
    'ipc', 'dolar', 'dólar', 'empleo', 'desempleo', 'censo', 'poblacion', 'población',
    'inflacion', 'inflación', 'canasta', 'semaforo', 'semáforo', 'patentamiento',
    'aeropuerto', 'combustible', 'eph', 'sipa', 'ecv', 'oede', 'pbg', 'emae',
    'salario', 'salarios', 'smvm', 'ripte', 'supermercado', 'construccion', 'construcción',
    'ieric', 'ipicorr',
    'pobreza', 'indigencia', 'salario', 'trabajo', 'economico', 'económico'
}


def is_domain_relevant(query: str) -> bool:
    """
    Verifica si la consulta es relevante para el dominio del IPECD.
    
    Args:
        query: Texto del usuario
        
    Returns:
        True si la pregunta es sobre temas del IPECD
    """
    query_lower = query.lower()
    query_words = set(re.findall(r'\w+', query_lower))
    
    # Verificar si hay palabras explícitamente fuera del dominio
    out_of_domain_matches = query_words & OUT_OF_DOMAIN_KEYWORDS
    
    # Verificar si hay indicadores específicos del IPECD
    specific_matches = query_words & SPECIFIC_INDICATORS
    
    # Si hay palabras fuera del dominio Y NO hay indicadores específicos → rechazar
    if out_of_domain_matches and not specific_matches:
        return False
    
    # Verificar si hay palabras del dominio (incluyendo genéricas)
    domain_matches = query_words & DOMAIN_KEYWORDS
    
    # Solo palabras genéricas no es suficiente
    if domain_matches and domain_matches <= GENERIC_WORDS:
        return False
    
    return len(domain_matches) > 0


# Patrones que indican pregunta compleja que requiere LLM
COMPLEX_QUERY_PATTERNS = [
    r'compara\w*',           # comparar, comparativa, comparación
    r'diferencia\w*',        # diferencia, diferencias
    r'vs\.?',                # vs, vs.
    r'entre\s+\w+\s+y\s+',   # entre X y Y
    r'\w+\s+y\s+\w+',        # X y Y (cuando hay dos entidades)
    r'cuanto\s+\w+\s+en',    # cuanto hay en
    r'cuantos?\s+\w+\s+tiene', # cuantos tiene
    r'cual\s+es\s+(el|la)\s+\w+\s+de', # cual es el/la X de
    r'como\s+se\s+compara',  # como se compara
    r'evolucion\w*',         # evolución
    r'historico\w*',         # histórico
    r'tendencia\w*',         # tendencia
]

# Nombres de lugares que indican consulta específica (con variantes de tipeo comunes)
LOCATION_NAMES = {
    # Municipios de Corrientes (con variantes)
    'goya', 'corrientes', 'corientes', 'corrientrs', 'ctes',
    'paso de los libres', 'mercedes', 'curuzú cuatiá', 'curuzu cuatia',
    'bella vista', 'esquina', 'monte caseros', 'santo tomé', 'santo tome',
    'virasoro', 'ituzaingó', 'ituzaingo', 'saladas', 'empedrado',
    'san roque', 'concepción', 'concepcion', 'lavalle',
    # Provincias argentinas (con variantes)
    'buenos aires', 'bsas', 'caba', 'capital federal',
    'córdoba', 'cordoba', 'rosario', 'mendoza', 'tucumán', 'tucuman',
    'santa fe', 'salta', 'chaco', 'misiones', 'entre ríos', 'entre rios',
    'formosa', 'jujuy', 'san juan', 'neuquén', 'neuquen',
    # Regiones
    'nea', 'noa', 'cuyo', 'patagonia', 'pampeana', 'gba'
}


def is_complex_query(query: str) -> bool:
    """
    Detecta si la consulta es compleja y requiere procesamiento directo con herramientas.
    
    Args:
        query: Texto del usuario
        
    Returns:
        True si es una consulta que debe ser procesada por QueryRouter
    """
    query_lower = query.lower()
    query_words = set(re.findall(r'\w+', query_lower))
    
    # Verificar patrones de consulta compleja (comparaciones, etc.)
    for pattern in COMPLEX_QUERY_PATTERNS:
        if re.search(pattern, query_lower):
            return True
    
    # Verificar si menciona lugares específicos
    location_matches = query_words & LOCATION_NAMES
    
    # Si menciona 2+ lugares o 1 lugar con pregunta
    if len(location_matches) >= 2:
        return True
    
    if location_matches and ('?' in query or any(w in query_lower for w in ['cuanto', 'cuantos', 'cual', 'como', 'podes', 'puedes'])):
        return True
    
    # Patrones de consulta directa de indicadores (sin requerir ubicación)
    direct_query_patterns = [
        r'(como|cómo)\s+(esta|está)\s+(el|la)',  # como esta el/la
        r'(cual|cuál)\s+es\s+(el|la)',           # cual es el/la
        r'dame\s+(el|la|los|las)',               # dame el/la
        r'muestrame\s+(el|la|los|las)',          # muestrame el/la
        r'(cuanto|cuánto)\s+(es|esta|está)',     # cuanto es/esta
        r'(ultimo|último)\s+(valor|dato)',       # ultimo valor
        r'(cotizacion|cotización)\s+del',        # cotización del
    ]
    
    has_direct_pattern = any(re.search(p, query_lower) for p in direct_query_patterns)
    
    # Si tiene patrón de consulta directa + indicador específico, es compleja
    if has_direct_pattern:
        indicator_matches = query_words & SPECIFIC_INDICATORS
        if indicator_matches:
            return True
    
    return False


# Patrones que indican pregunta conceptual/definitoria
CONCEPTUAL_PATTERNS = [
    r'\bqu[eé]\s+es\b',           # qué es
    r'\bqu[eé]\s+significa\b',     # qué significa
    r'\bqu[eé]\s+son\b',           # qué son
    r'\bdefinici[oó]n\b',          # definición
    r'\bdefinir\b',                # definir
    r'\bexplicar?\b',              # explicar/explica
    r'\bexpl[ií]came\b',           # explícame
    r'\bqu[eé]\s+quiere\s+decir\b', # qué quiere decir
    r'\bc[oó]mo\s+funciona\b',     # cómo funciona
    r'\bc[oó]mo\s+se\s+calcula\b', # cómo se calcula
    r'\bpara\s+qu[eé]\s+sirve\b',  # para qué sirve
    r'\bcu[aá]l\s+es\s+la\s+diferencia\b',  # cuál es la diferencia
    r'\bqu[eé]\s+mide\b',          # qué mide
    r'\bqu[eé]\s+incluye\b',       # qué incluye
    r'\bsignificado\b',            # significado
    r'\bconcepto\b',               # concepto
]

# Patrones que indican solicitud de datos
DATA_REQUEST_PATTERNS = [
    r'\bdame\b',                   # dame
    r'\bmu[eé]strame\b',           # muéstrame
    r'\bver\b',                    # ver
    r'\b[uú]ltimo[s]?\b',          # último/últimos
    r'\bactual\b',                 # actual
    r'\bdatos\s+de\b',             # datos de
    r'\bvalor\b',                  # valor
    r'\bcuanto\b',                 # cuanto
    r'\bcu[aá]nto\b',              # cuánto
    r'\bcotizaci[oó]n\b',          # cotización
    r'\bprecio\b',                 # precio
    r'\btasa\b',                   # tasa
    r'\bpoblaci[oó]n\b',           # población
    r'\bestadística\b',            # estadística
    r'\bn[uú]mero\b',              # número
    r'\bporcentaje\b',             # porcentaje
    r'\bvar[ií]aci[oó]n\b',        # variación
    r'\bcuantos?\b',               # cuanto/cuantos
    r'\bcu[aá]ntos?\b',            # cuánto/cuántos
]


def classify_intent(query: str) -> Tuple[str, float]:
    """
    Clasifica la intención del usuario.
    
    Args:
        query: Texto del usuario
        
    Returns:
        Tupla (tipo_intención, confianza)
        - tipo_intención: "conceptual", "data", "ambiguous"
        - confianza: 0.0 a 1.0
    """
    query_lower = query.lower().strip()
    
    conceptual_score = 0
    data_score = 0
    
    # Verificar patrones conceptuales
    for pattern in CONCEPTUAL_PATTERNS:
        if re.search(pattern, query_lower):
            conceptual_score += 2
    
    # Verificar patrones de datos
    for pattern in DATA_REQUEST_PATTERNS:
        if re.search(pattern, query_lower):
            data_score += 1
    
    # Preguntas con "?" al final tienden a ser conceptuales si tienen "qué"
    if query.strip().endswith('?'):
        if re.search(r'\bqu[eé]\b', query_lower):
            conceptual_score += 1
    
    # Calcular confianza
    total_score = conceptual_score + data_score
    
    if total_score == 0:
        return "ambiguous", 0.5
    
    if conceptual_score > data_score:
        confidence = min(conceptual_score / (total_score + 1), 1.0)
        return "conceptual", confidence
    elif data_score > conceptual_score:
        confidence = min(data_score / (total_score + 1), 1.0)
        return "data", confidence
    else:
        return "ambiguous", 0.5


def is_conceptual_question(query: str) -> bool:
    """
    Verifica si es una pregunta conceptual/definitoria.
    
    Args:
        query: Texto del usuario
        
    Returns:
        True si es pregunta conceptual
    """
    intent_type, confidence = classify_intent(query)
    return intent_type == "conceptual" and confidence >= 0.4


def get_topic_from_query(query: str) -> str:
    """
    Extrae el tema principal de la consulta.
    
    Args:
        query: Texto del usuario
        
    Returns:
        Tema extraído
    """
    # Remover patrones de pregunta para obtener el tema
    topic = query.lower()
    
    # Remover patrones de pregunta
    remove_patterns = [
        r'qu[eé]\s+es\s+(el|la|los|las)?\s*',
        r'qu[eé]\s+significa\s*(el|la)?\s*',
        r'qu[eé]\s+son\s+(los|las)?\s*',
        r'explicame\s+(qu[eé]\s+es)?\s*',
        r'c[oó]mo\s+funciona\s+(el|la)?\s*',
        r'para\s+qu[eé]\s+sirve\s+(el|la)?\s*',
        r'\?',
    ]
    
    for pattern in remove_patterns:
        topic = re.sub(pattern, '', topic)
    
    return topic.strip()

