"""
Clasificador de intenciones usando LLM.
Más flexible y escalable que listas de palabras hardcodeadas.
"""
import logging
from typing import Dict, Optional, Tuple, Any
import os

# Import opcional de OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OpenAI = None  # type: ignore
    OPENAI_AVAILABLE = False
    logging.warning("OpenAI module not available. LLM classification will use basic fallback.")

# Prompt del sistema para clasificación
CLASSIFICATION_PROMPT = """Eres un clasificador de intenciones para un chatbot de estadísticas del IPECD (Instituto Provincial de Estadística y Censos de Corrientes, Argentina).

Tu trabajo es analizar el mensaje del usuario y clasificarlo en UNA de estas categorías:

1. **saludo**: Saludos como "hola", "buenos días", "qué tal", etc. (SIN preguntas adicionales)
2. **despedida**: Despedidas o agradecimientos como "gracias", "chau", "hasta luego", etc.
3. **ayuda**: Solicitudes de ayuda o información sobre qué puede hacer el bot:
   - "qué podés hacer", "qué haces", "qué sabes", "opciones", "menu"
   - "para qué servís", "cómo funciona esto"
4. **consulta_datos**: Consultas sobre datos estadísticos específicos:
   - "dame el dólar", "cuál es la inflación", "último IPC"
   - "población de Goya", "tasa de desempleo"
   - Cualquier pregunta que pida DATOS NUMÉRICOS
5. **pregunta_conceptual**: Preguntas sobre qué es algo o cómo funciona:
   - "qué es el IPC", "cómo se calcula la inflación"
   - "qué es el EMAE", "para qué sirve el semáforo económico"
6. **fuera_de_dominio**: Preguntas que NO tienen nada que ver con:
   - Estadísticas, economía, demografía, empleo, precios, población
   - Ejemplos: fútbol, clima, recetas, política, farándula, salud general

TEMAS VÁLIDOS DEL IPECD (usar estos exactamente):
- dolar (cotización dólar blue, oficial, mep, ccl)
- ipc (índice de precios, inflación nacional)
- ipc_corrientes (inflación específica de Corrientes, IPICorr)
- empleo (EPH, tasas de empleo/desempleo)
- ecv (Encuesta de Calidad de Vida)
- oede (Observatorio de Empleo)
- sipa (empleo registrado)
- censo (población por municipio/departamento)
- semaforo (semáforo económico de indicadores)
- canasta (canasta básica alimentaria)
- pobreza (líneas de pobreza e indigencia)
- patentamientos (vehículos 0km)
- aeropuertos (pasajeros)
- combustible (ventas de nafta/gasoil)
- emae (actividad económica mensual)
- pbg (producto bruto geográfico)
- salarios (SMVM, RIPTE, índices salariales)
- supermercados (facturación)
- construccion (industria de la construcción, IERIC)

También debes extraer:
- **tema**: El tema principal de la lista anterior (o null si no aplica)
- **entidades**: Lugares mencionados (goya, corrientes, mercedes, buenos aires, etc.)
- **es_comparacion**: true si pide comparar ("comparar X con Y", "diferencia entre", "vs")

IMPORTANTE: Si el mensaje contiene saludo + pregunta (ej: "hola, qué es el IPC"), clasifica según la PREGUNTA, no el saludo.

Responde SOLO en formato JSON:
{
  "intencion": "categoria",
  "tema": "tema_principal o null",
  "entidades": ["lista", "de", "lugares"],
  "es_comparacion": false,
  "confianza": 0.95
}
"""


class LLMIntentClassifier:
    """Clasificador de intenciones usando OpenAI/LLM."""
    
    def __init__(self, openai_client: Optional[Any] = None):
        self.client = openai_client
        self._cache: Dict[str, Dict] = {}  # Cache simple para evitar llamadas repetidas
    
    def set_client(self, client: Any):
        """Configura el cliente OpenAI."""
        self.client = client
    
    def classify(self, user_message: str) -> Dict:
        """
        Clasifica la intención del mensaje del usuario.
        
        Args:
            user_message: Mensaje del usuario
            
        Returns:
            Dict con: intencion, tema, entidades, es_comparacion, confianza
        """
        if not user_message or not user_message.strip():
            return self._default_response("saludo")
        
        # Normalizar mensaje para cache
        cache_key = user_message.lower().strip()
        if cache_key in self._cache:
            logging.debug(f"Cache hit for: {cache_key[:30]}")
            return self._cache[cache_key]
        
        # Si no hay cliente LLM, usar clasificación básica
        if not self.client:
            logging.warning("No LLM client available, using basic classification")
            return self._basic_classify(user_message)
        
        try:
            result = self._llm_classify(user_message)
            self._cache[cache_key] = result
            return result
        except Exception as e:
            logging.error(f"LLM classification error: {e}")
            return self._basic_classify(user_message)
    
    def _llm_classify(self, user_message: str) -> Dict:
        """Clasificación usando LLM."""
        import json
        
        try:
            messages = [
                {"role": "system", "content": CLASSIFICATION_PROMPT},
                {"role": "user", "content": user_message}
            ]
            
            # Intentar usar el cliente (puede ser OpenAIClient del proyecto o SDK directo)
            if hasattr(self.client, 'chat') and hasattr(self.client.chat, 'completions'):
                # SDK de OpenAI
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.1,
                    max_tokens=200,
                    response_format={"type": "json_object"}
                )
                content = response.choices[0].message.content
            elif hasattr(self.client, 'get_response'):
                # OpenAIClient del proyecto (usa REST API)
                content = self.client.get_response(messages)
                if not content:
                    return self._basic_classify(user_message)
            else:
                logging.warning(f"Unknown client type: {type(self.client)}")
                return self._basic_classify(user_message)
            
            # Parsear JSON de la respuesta
            try:
                # Extraer JSON si está envuelto en markdown
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                
                result = json.loads(content.strip())
            except json.JSONDecodeError:
                logging.warning(f"Could not parse LLM response as JSON: {content[:100]}")
                return self._basic_classify(user_message)
            
            # Validar estructura
            if "intencion" not in result:
                result["intencion"] = "consulta_datos"
            if "tema" not in result:
                result["tema"] = None
            if "entidades" not in result:
                result["entidades"] = []
            if "es_comparacion" not in result:
                result["es_comparacion"] = False
            if "confianza" not in result:
                result["confianza"] = 0.8
            
            logging.info(f"LLM classified '{user_message[:30]}...' as: {result['intencion']}")
            return result
            
        except Exception as e:
            logging.error(f"LLM classify error: {e}")
            return self._basic_classify(user_message)
    
    def _basic_classify(self, user_message: str) -> Dict:
        """Clasificación básica sin LLM (fallback)."""
        msg = user_message.lower().strip()
        
        # Patrones simples
        if any(w in msg for w in ['hola', 'buenos', 'buenas', 'hey', 'hi']):
            return self._default_response("saludo")
        
        if any(w in msg for w in ['gracias', 'chau', 'adios', 'hasta']):
            return self._default_response("despedida")
        
        if any(w in msg for w in ['ayuda', 'help', 'opciones', 'que podes', 'que puedes']):
            return self._default_response("ayuda")
        
        if any(w in msg for w in ['que es', 'qué es', 'como funciona', 'cómo funciona', 'significa']):
            tema = self._extract_topic(msg)
            return {
                "intencion": "pregunta_conceptual",
                "tema": tema,
                "entidades": [],
                "es_comparacion": False,
                "confianza": 0.7
            }
        
        # Verificar si tiene temas del dominio
        domain_topics = ['dolar', 'dólar', 'ipc', 'inflacion', 'inflación', 'empleo', 'censo', 
                        'poblacion', 'población', 'semaforo', 'semáforo', 'patentamiento', 
                        'patentamientos', 'combustible', 'pobreza', 'eph', 'ecv', 'oede',
                        'observatorio', 'aeropuerto', 'aeropuertos', 'canasta', 'salario',
                        'salarios', 'trabajo', 'desempleo', 'smvm', 'ripte', 'emae', 'pbg',
                        'supermercado', 'supermercados', 'construccion', 'construcción', 'ieric',
                        'ipicorr', 'actividad economica', 'actividad económica']
        
        has_domain_topic = any(t in msg for t in domain_topics)
        
        if has_domain_topic:
            tema = self._extract_topic(msg)
            entidades = self._extract_entities(msg)
            es_comp = any(w in msg for w in ['compar', 'vs', 'entre', ' y '])
            return {
                "intencion": "consulta_datos",
                "tema": tema,
                "entidades": entidades,
                "es_comparacion": es_comp,
                "confianza": 0.7
            }
        
        # Si no tiene nada del dominio, es fuera de dominio
        return self._default_response("fuera_de_dominio")
    
    def _extract_topic(self, msg: str) -> Optional[str]:
        """Extrae el tema principal del mensaje."""
        topic_keywords = {
            'dolar': ['dolar', 'dólar', 'cotizacion', 'blue', 'oficial', 'mep', 'ccl'],
            'ipc': ['ipc', 'inflacion', 'inflación', 'precios'],
            'ipc_corrientes': ['ipicorr', 'ipc corrientes', 'inflacion corrientes'],
            'empleo': ['empleo', 'desempleo', 'trabajo', 'eph', 'ocupacion'],
            'sipa': ['sipa', 'empleo registrado'],
            'ecv': ['ecv', 'calidad de vida', 'condiciones de vida'],
            'oede': ['oede', 'observatorio de empleo', 'dinamica empresarial', 'dinámica empresarial'],
            'censo': ['censo', 'poblacion', 'población', 'habitantes', 'demografico'],
            'semaforo': ['semaforo', 'semáforo', 'indicadores economicos'],
            'patentamientos': ['patentamiento', 'vehiculos', 'autos', 'motos', '0km'],
            'combustible': ['combustible', 'nafta', 'gasoil'],
            'pobreza': ['pobreza', 'indigencia', 'cbt', 'cba'],
            'canasta': ['canasta basica', 'canasta básica'],
            'aeropuertos': ['aeropuerto', 'aeropuertos', 'anac', 'vuelos', 'pasajeros aeropuerto'],
            'emae': ['emae', 'actividad economica', 'actividad económica'],
            'pbg': ['pbg', 'producto bruto', 'produccion provincial'],
            'salarios': ['salario', 'salarios', 'smvm', 'ripte', 'sueldo', 'minimo vital'],
            'supermercados': ['supermercado', 'supermercados', 'facturacion supermercados'],
            'construccion': ['construccion', 'construcción', 'ieric', 'obras'],
        }
        
        for topic, keywords in topic_keywords.items():
            if any(kw in msg for kw in keywords):
                return topic
        return None
    
    def _extract_entities(self, msg: str) -> list:
        """Extrae entidades (lugares) del mensaje."""
        locations = [
            'goya', 'corrientes', 'mercedes', 'paso de los libres', 'bella vista',
            'esquina', 'monte caseros', 'virasoro', 'santo tome', 'saladas',
            'buenos aires', 'caba', 'cordoba', 'rosario', 'mendoza',
            'nea', 'noa', 'gba', 'patagonia'
        ]
        found = []
        msg_lower = msg.lower()
        for loc in locations:
            if loc in msg_lower:
                found.append(loc)
        return found
    
    def _default_response(self, intencion: str) -> Dict:
        """Respuesta por defecto para una intención."""
        return {
            "intencion": intencion,
            "tema": None,
            "entidades": [],
            "es_comparacion": False,
            "confianza": 0.9
        }


# Instancia global
_classifier: Optional[LLMIntentClassifier] = None


def get_intent_classifier() -> LLMIntentClassifier:
    """Obtiene la instancia global del clasificador."""
    global _classifier
    if _classifier is None:
        _classifier = LLMIntentClassifier()
    return _classifier


def classify_user_intent(message: str, openai_client: Optional[Any] = None) -> Dict:
    """
    Función de conveniencia para clasificar intención.
    
    Args:
        message: Mensaje del usuario
        openai_client: Cliente OpenAI opcional
        
    Returns:
        Dict con clasificación
    """
    classifier = get_intent_classifier()
    if openai_client and OPENAI_AVAILABLE:
        classifier.set_client(openai_client)
    return classifier.classify(message)

