"""
Router inteligente de consultas.
Mapea consultas complejas a las herramientas correctas y extrae parámetros.
"""
import re
import logging
from typing import Dict, List, Optional, Tuple

# Mapeo de palabras clave a herramientas
TOOL_MAPPINGS = {
    # Población y Censo
    'get_censo': {
        'keywords': ['poblacion', 'población', 'habitantes', 'censo', 'gente', 'personas', 'demografía', 'demografico'],
        'param_name': 'municipio',
        'description': 'datos de población'
    },
    
    # Dólar
    'get_dolar': {
        'keywords': ['dolar', 'dólar', 'cotizacion', 'cotización', 'blue', 'oficial', 'mep', 'ccl', 'tipo de cambio'],
        'param_name': 'tipo',
        'param_values': {'blue': 'blue', 'oficial': 'oficial', 'mep': 'mep', 'ccl': 'ccl'},
        'description': 'cotización del dólar'
    },
    
    # IPC / Inflación
    'get_ipc': {
        'keywords': ['ipc', 'inflacion', 'inflación', 'precios', 'indice de precios', 'índice de precios'],
        'param_name': 'region',
        'description': 'índice de precios al consumidor'
    },
    
    # Empleo
    'get_empleo': {
        'keywords': ['empleo', 'desempleo', 'trabajo', 'ocupacion', 'ocupación', 'tasa de empleo', 'eph', 'actividad'],
        'param_name': 'provincia',
        'description': 'tasas de empleo y desempleo'
    },
    
    # Semáforo económico
    'get_semaforo': {
        'keywords': ['semaforo', 'semáforo', 'indicadores economicos', 'indicadores económicos', 'variacion', 'variación'],
        'param_name': 'tipo',
        'param_values': {'interanual': 'interanual', 'mensual': 'intermensual'},
        'description': 'semáforo económico'
    },
    
    # Patentamientos
    'get_patentamientos': {
        'keywords': ['patentamiento', 'patentamientos', 'vehiculos', 'vehículos', 'autos', 'motos', '0km', 'dnrpa'],
        'param_name': 'provincia',
        'description': 'patentamientos de vehículos'
    },
    
    # Aeropuertos
    'get_aeropuertos': {
        'keywords': ['aeropuerto', 'aeropuertos', 'vuelos', 'pasajeros aereos', 'anac', 'aviacion', 'aviación'],
        'param_name': 'aeropuerto',
        'description': 'pasajeros en aeropuertos'
    },
    
    # Combustible
    'get_combustible': {
        'keywords': ['combustible', 'nafta', 'gasoil', 'diesel', 'gas', 'petroleo', 'petróleo', 'ventas de combustible'],
        'param_name': 'provincia',
        'description': 'ventas de combustible'
    },
    
    # Canasta básica
    'get_canasta_basica': {
        'keywords': ['canasta', 'canasta basica', 'canasta básica', 'alimentos', 'costo de vida'],
        'param_name': None,
        'description': 'canasta básica'
    },
    
    # Pobreza
    'get_pobreza': {
        'keywords': ['pobreza', 'indigencia', 'cbt', 'cba', 'linea de pobreza', 'línea de pobreza'],
        'param_name': 'region',
        'description': 'líneas de pobreza e indigencia'
    },
    
    # ECV
    'get_ecv': {
        'keywords': ['ecv', 'encuesta de calidad', 'calidad de vida', 'condiciones de vida'],
        'param_name': None,
        'description': 'encuesta de calidad de vida'
    },
    
    # OEDE
    'get_oede': {
        'keywords': ['oede', 'observatorio de empleo', 'dinamica empresarial', 'dinámica empresarial'],
        'param_name': 'provincia',
        'description': 'observatorio de empleo'
    },
    
    # EMAE - Actividad Económica
    'get_emae': {
        'keywords': ['emae', 'actividad economica', 'actividad económica', 'estimador mensual', 'pbi mensual'],
        'param_name': 'categoria',
        'description': 'actividad económica mensual'
    },
    
    # PBG - Producto Bruto Geográfico
    'get_pbg': {
        'keywords': ['pbg', 'producto bruto', 'pbi provincial', 'produccion provincial', 'producción provincial'],
        'param_name': 'sector',
        'description': 'producto bruto geográfico'
    },
    
    # Salarios
    'get_salarios': {
        'keywords': ['salario', 'salarios', 'sueldo', 'sueldos', 'smvm', 'minimo vital', 'mínimo vital', 'ripte', 'remuneracion', 'remuneración'],
        'param_name': 'tipo',
        'param_values': {'smvm': 'smvm', 'minimo': 'smvm', 'mínimo': 'smvm', 'ripte': 'ripte', 'indicadores': 'indicadores'},
        'description': 'salarios e índices salariales'
    },
    
    # Supermercados
    'get_supermercados': {
        'keywords': ['supermercado', 'supermercados', 'autoservicio', 'facturacion supermercados', 'ventas minoristas'],
        'param_name': 'rubro',
        'description': 'facturación de supermercados'
    },
    
    # Construcción
    'get_construccion': {
        'keywords': ['construccion', 'construcción', 'ieric', 'obras', 'edificacion', 'edificación'],
        'param_name': 'tipo',
        'param_values': {'puestos': 'puestos', 'trabajo': 'puestos', 'ingresos': 'ingresos', 'actividad': 'actividad'},
        'description': 'industria de la construcción'
    },
    
    # IPC Corrientes específico
    'get_ipc_corrientes': {
        'keywords': ['ipc corrientes', 'ipicorr', 'inflacion corrientes', 'inflación corrientes', 'precios corrientes'],
        'param_name': None,
        'description': 'IPC específico de Corrientes'
    },
}

# Nombres de lugares conocidos (con variantes de tipeo comunes)
LOCATION_NAMES = {
    'goya', 'corrientes', 'corientes', 'corrientrs', 'ctes',  # Corrientes y variantes
    'paso de los libres', 'mercedes', 'curuzú cuatiá', 'curuzu cuatia',
    'bella vista', 'esquina', 'monte caseros', 'santo tomé', 'santo tome',
    'virasoro', 'ituzaingó', 'ituzaingo', 'saladas', 'empedrado',
    'san roque', 'concepción', 'concepcion', 'lavalle', 'santa lucia',
    'mocoretá', 'mocoreta', 'alvear', 'san cosme', 'itatí', 'itati',
    'buenos aires', 'bsas', 'bs as', 'caba', 'capital federal',
    'córdoba', 'cordoba', 'rosario', 'mendoza', 'tucumán', 'tucuman',
    'santa fe', 'salta', 'chaco', 'misiones', 'entre ríos', 'entre rios',
    'formosa', 'jujuy', 'san juan', 'san luis', 'la rioja', 'catamarca',
    'santiago del estero', 'neuquén', 'neuquen', 'río negro', 'rio negro',
    'chubut', 'santa cruz', 'tierra del fuego', 'la pampa',
    'capital', 'gba', 'nea', 'noa', 'cuyo', 'patagonia', 'pampeana'
}

# Mapeo de variantes a nombres canónicos
LOCATION_CANONICAL = {
    'corrientrs': 'corrientes', 'corientes': 'corrientes', 'ctes': 'corrientes',
    'bsas': 'buenos aires', 'bs as': 'buenos aires', 'capital federal': 'caba',
    'curuzu cuatia': 'curuzú cuatiá', 'santo tome': 'santo tomé',
    'ituzaingo': 'ituzaingó', 'concepcion': 'concepción',
    'mocoreta': 'mocoretá', 'itati': 'itatí',
    'cordoba': 'córdoba', 'tucuman': 'tucumán',
    'entre rios': 'entre ríos', 'neuquen': 'neuquén', 'rio negro': 'río negro'
}


class QueryRouter:
    """Router inteligente para consultas complejas."""
    
    def __init__(self, tool_executor):
        self.tool_executor = tool_executor
    
    def detect_tool(self, query: str) -> Optional[str]:
        """
        Detecta qué herramienta usar basándose en las palabras clave.
        
        Args:
            query: Consulta del usuario
            
        Returns:
            Nombre de la herramienta o None si no se detecta
        """
        query_lower = query.lower()
        
        best_tool = None
        best_score = 0
        
        for tool_name, config in TOOL_MAPPINGS.items():
            score = 0
            for keyword in config['keywords']:
                if keyword in query_lower:
                    # Más puntos si es una coincidencia exacta de palabra
                    if re.search(rf'\b{re.escape(keyword)}\b', query_lower):
                        score += 10
                    else:
                        score += 5
            
            if score > best_score:
                best_score = score
                best_tool = tool_name
        
        return best_tool if best_score >= 5 else None
    
    def extract_locations(self, query: str) -> List[str]:
        """
        Extrae nombres de lugares de la consulta, normalizando variantes.
        
        Args:
            query: Consulta del usuario
            
        Returns:
            Lista de nombres de lugares encontrados (normalizados)
        """
        query_lower = query.lower()
        found_locations = []
        
        # Buscar ubicaciones conocidas
        for location in LOCATION_NAMES:
            if location in query_lower:
                # Normalizar a nombre canónico si existe variante
                canonical = LOCATION_CANONICAL.get(location, location)
                if canonical not in found_locations:
                    found_locations.append(canonical)
        
        return found_locations
    
    def extract_params(self, query: str, tool_name: str) -> Dict:
        """
        Extrae parámetros para la herramienta basándose en la consulta.
        
        Args:
            query: Consulta del usuario
            tool_name: Nombre de la herramienta
            
        Returns:
            Diccionario de parámetros
        """
        config = TOOL_MAPPINGS.get(tool_name, {})
        params = {}
        
        # Extraer valores de parámetros específicos
        if 'param_values' in config:
            query_lower = query.lower()
            for keyword, value in config['param_values'].items():
                if keyword in query_lower:
                    params[config['param_name']] = value
                    break
        
        return params
    
    def is_comparison_query(self, query: str) -> bool:
        """
        Detecta si es una consulta de comparación.
        """
        comparison_patterns = [
            r'compara\w*', r'diferencia\w*', r'vs\.?', r'entre\s+\w+\s+y\s+',
            r'\w+\s+y\s+\w+', r'cual.*mayor', r'cual.*menor', r'mas.*que',
            r'menos.*que'
        ]
        
        query_lower = query.lower()
        for pattern in comparison_patterns:
            if re.search(pattern, query_lower):
                return True
        
        # También es comparación si menciona 2+ lugares
        locations = self.extract_locations(query)
        return len(locations) >= 2
    
    def route_and_execute(self, query: str) -> Optional[Tuple[str, str]]:
        """
        Enruta la consulta a la herramienta correcta y la ejecuta.
        
        Args:
            query: Consulta del usuario
            
        Returns:
            Tupla (herramienta_usada, resultado) o None si no se puede procesar
        """
        if not self.tool_executor or not self.tool_executor.is_available():
            return None
        
        # Detectar herramienta
        tool_name = self.detect_tool(query)
        if not tool_name:
            logging.info(f"No tool detected for query: {query[:50]}")
            return None
        
        logging.info(f"Detected tool {tool_name} for query: {query[:50]}")
        
        # Extraer ubicaciones
        locations = self.extract_locations(query)
        
        # Extraer otros parámetros
        params = self.extract_params(query, tool_name)
        
        config = TOOL_MAPPINGS.get(tool_name, {})
        param_name = config.get('param_name')
        
        # Si es una consulta de comparación con múltiples ubicaciones
        if self.is_comparison_query(query) and locations and param_name:
            results = []
            for location in locations:
                loc_params = {param_name: location, **params}
                result = self.tool_executor.execute(tool_name, loc_params)
                if result and "No se encontraron" not in result and "Error" not in result:
                    results.append(result)
            
            if results:
                combined = self._format_comparison(results, config.get('description', 'datos'))
                return (tool_name, combined)
        
        # Consulta simple (un solo lugar o sin lugar)
        elif locations and param_name:
            params[param_name] = locations[0]
            result = self.tool_executor.execute(tool_name, params)
            if result and "No se encontraron" not in result:
                return (tool_name, result)
        
        # Sin ubicación, ejecutar con parámetros extraídos
        else:
            result = self.tool_executor.execute(tool_name, params)
            if result and "No se encontraron" not in result:
                return (tool_name, result)
        
        return None
    
    def _format_comparison(self, results: List[str], description: str) -> str:
        """
        Formatea múltiples resultados en una comparativa.
        """
        if len(results) == 1:
            return results[0]
        
        # Intentar combinar tablas
        combined = f"## 📊 Comparativa de {description.title()}\n\n"
        
        # Buscar encabezado de tabla en el primer resultado
        header_found = False
        for r in results:
            lines = r.split('\n')
            for line in lines:
                if '|' in line:
                    if '---' in line:
                        if not header_found:
                            # Encontrar línea de encabezado (anterior a los guiones)
                            idx = lines.index(line)
                            if idx > 0:
                                combined += lines[idx-1] + '\n'
                                combined += line + '\n'
                                header_found = True
                    elif header_found and line.strip() and 'Municipio' not in line and 'Fecha' not in line:
                        combined += line + '\n'
        
        if not header_found:
            # Si no se encontró formato de tabla, concatenar resultados
            combined = f"## 📊 Comparativa de {description.title()}\n\n"
            combined += "\n---\n".join(results)
        
        combined += f"\n\n> Comparativa generada automáticamente."
        return combined

