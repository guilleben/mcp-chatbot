"""
Enriquecedor de respuestas usando LLM.
Agrega contexto y explicaciones a los datos de la base de datos.
"""
import logging
from typing import Optional, Any

ENRICHMENT_PROMPT = """Eres un asistente del IPECD (Instituto Provincial de Estadística y Censos de Corrientes).

Tu rol es contextualizar y enriquecer la respuesta de datos estadísticos que el sistema ya tiene.

REGLAS CRÍTICAS:
1. NUNCA inventes datos o números - usa SOLO los datos que te proporciono
2. Si los datos incluyen múltiples provincias, PRIORIZA mencionar datos de CORRIENTES
3. No mezcles información de consultas anteriores - SOLO responde sobre los datos actuales
4. Agrega contexto útil y explicaciones claras
5. Si los datos muestran tendencias, mencionalas brevemente
6. Usa un tono amigable y accesible
7. Mantén la respuesta CONCISA (máximo 3-4 párrafos)
8. Si no hay datos de Corrientes específicamente, menciona que son datos generales

CONTEXTO: Esta es una consulta INDEPENDIENTE. No mezcles con preguntas anteriores.

DATOS DISPONIBLES:
{data}

PREGUNTA DEL USUARIO:
{question}

Genera una respuesta corta que contextualice estos datos de forma clara y amigable.
Si hay una tabla de datos, puedes resumir los puntos clave sin repetir toda la tabla.
"""


class ResponseEnricher:
    """Enriquece respuestas de datos con contexto usando LLM."""
    
    def __init__(self, openai_client: Optional[Any] = None):
        self.client = openai_client
    
    def set_client(self, client: Any):
        """Configura el cliente OpenAI."""
        self.client = client
    
    def enrich(self, data_response: str, user_question: str) -> str:
        """
        Enriquece una respuesta de datos con contexto.
        
        Args:
            data_response: Respuesta de datos del sistema (tablas, valores)
            user_question: Pregunta original del usuario
            
        Returns:
            Respuesta enriquecida con contexto
        """
        if not self.client:
            # Sin LLM, devolver datos tal cual
            return data_response
        
        # Si la respuesta es muy corta o es un error, no enriquecer
        if len(data_response) < 50 or "Error" in data_response or "Lo siento" in data_response:
            return data_response
        
        try:
            prompt = ENRICHMENT_PROMPT.format(
                data=data_response,
                question=user_question
            )
            
            messages = [
                {"role": "system", "content": "Eres un asistente estadístico amigable."},
                {"role": "user", "content": prompt}
            ]
            
            # Usar el cliente (OpenAIClient del proyecto usa get_response)
            if hasattr(self.client, 'get_response'):
                enriched = self.client.get_response(messages)
                if enriched:
                    logging.info(f"Response enriched for: {user_question[:30]}...")
                    return enriched
            
            return data_response
            
        except Exception as e:
            logging.error(f"Error enriching response: {e}")
            return data_response


# Instancia global
_enricher: Optional[ResponseEnricher] = None


def get_response_enricher() -> ResponseEnricher:
    """Obtiene la instancia global del enriquecedor."""
    global _enricher
    if _enricher is None:
        _enricher = ResponseEnricher()
    return _enricher


def enrich_data_response(data: str, question: str, client: Optional[Any] = None) -> str:
    """
    Función de conveniencia para enriquecer respuestas.
    
    Args:
        data: Datos del sistema
        question: Pregunta del usuario
        client: Cliente OpenAI opcional
        
    Returns:
        Respuesta enriquecida
    """
    enricher = get_response_enricher()
    if client:
        enricher.set_client(client)
    return enricher.enrich(data, question)

