"""Chat session management module - Simplified."""
import asyncio
import json
import logging
from typing import Dict, List, Optional

from database import DatabaseClient
from llm_clients import LLMClient, OpenAIClient
from mcp_server import Server
from friendly_names import get_friendly_name


class ChatSession:
    """Orchestrates the interaction between user, LLM, and MCP tools."""

    def __init__(
        self, 
        servers: List[Server], 
        llm_client: LLMClient, 
        openai_client: Optional[OpenAIClient] = None,
        db_client: Optional[DatabaseClient] = None
    ) -> None:
        self.servers = servers
        self.llm_client = llm_client
        self.openai_client = openai_client
        self.db_client = db_client

    async def cleanup_servers(self) -> None:
        """Clean up all server connections."""
        cleanup_tasks = [
            asyncio.create_task(server.cleanup()) 
            for server in self.servers
        ]
        
        if cleanup_tasks:
            try:
                await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            except Exception as e:
                logging.warning(f"Warning during cleanup: {e}")

    def format_database_results(self, results: List[Dict], max_records: int = 10) -> str:
        """
        Formatea resultados de BD de manera amigable.
        
        Args:
            results: Lista de diccionarios con datos
            max_records: Máximo de registros a mostrar
            
        Returns:
            String formateado para el usuario
        """
        if not results:
            return ""
        
        formatted_entries = []
        
        for result in results[:max_records]:
            # Remover metadatos técnicos
            for key in ['_source_db', '_source_table', '_is_sample']:
                result.pop(key, None)
            
            entry_lines = []
            for key, value in list(result.items())[:8]:
                if value is None or str(value).strip() in ('', 'None'):
                    continue
                    
                friendly_key = get_friendly_name(key)
                formatted_value = self._format_value(value)
                entry_lines.append(f"**{friendly_key}**: {formatted_value}")
            
            if entry_lines:
                formatted_entries.append("\n".join(entry_lines))
        
        result_str = "\n\n".join(formatted_entries)
        
        if len(results) > max_records:
            result_str += f"\n\n_... y {len(results) - max_records} registros más disponibles._"
        
        return result_str

    def _format_value(self, value) -> str:
        """Formatea un valor para mostrar al usuario."""
        if isinstance(value, float):
            if abs(value) < 1000:
                return f"{value:.2f}".rstrip('0').rstrip('.')
            return f"{value:,.0f}".replace(',', '.')
        if isinstance(value, int):
            return f"{value:,}".replace(',', '.')
        return str(value)

    async def search_in_database(self, query: str) -> Optional[str]:
        """
        Busca información en la base de datos.
        
        Args:
            query: Consulta del usuario
            
        Returns:
            Resultados formateados o None si no hay resultados
        """
        if not self.db_client:
            return None
        
        # Ignorar consultas generales
        query_lower = query.lower().strip()
        general_keywords = [
            'hola', 'hello', 'hi', 'buenos días', 'buenas tardes',
            'ayuda', 'help', 'gracias', 'thanks', 'adios', 'bye',
            'quien eres', 'que eres', 'que puedes hacer'
        ]
        
        if any(kw in query_lower for kw in general_keywords):
            return None
        
        try:
            logging.info(f"Searching database for: {query}")
            results = self.db_client.search_with_fallback(query, limit=3, max_results=12, timeout=3)
            
            if results:
                return self.format_database_results(results)
            return None
        except Exception as e:
            logging.error(f"Error searching database: {e}")
            return None

    async def get_llm_response(
        self, 
        messages: List[Dict], 
        db_context: Optional[str] = None
    ) -> Optional[str]:
        """
        Obtiene respuesta del LLM con contexto opcional de BD.
        
        Args:
            messages: Historial de mensajes
            db_context: Contexto de datos de BD (opcional)
            
        Returns:
            Respuesta del LLM o None si falla
        """
        current_messages = messages.copy()
        
        if db_context:
            current_messages.append({
                "role": "system", 
                "content": f"DATOS ENCONTRADOS:\n{db_context}\n\nResponde usando estos datos de forma directa y amigable."
            })
        
        response = self.llm_client.get_response(
            current_messages, 
            fallback_client=self.openai_client
        )
        
        if not response and self.openai_client:
            response = self.openai_client.get_response(current_messages)
        
        return response

    async def process_llm_response(self, llm_response: str) -> str:
        """
        Procesa la respuesta del LLM y ejecuta herramientas MCP si es necesario.
        
        Args:
            llm_response: Respuesta del LLM
            
        Returns:
            Resultado procesado o la respuesta original
        """
        try:
            tool_call = json.loads(llm_response)
            if "tool" in tool_call and "arguments" in tool_call:
                logging.info(f"Executing MCP tool: {tool_call['tool']}")
                for server in self.servers:
                    tools = await server.list_tools()
                    if any(tool.name == tool_call["tool"] for tool in tools):
                        try:
                            result = await server.execute_tool(tool_call["tool"], tool_call["arguments"])
                            return f"Resultado: {result}"
                        except Exception as e:
                            logging.error(f"Error executing tool: {e}")
                            return f"Error al ejecutar herramienta: {str(e)}"
                return f"Herramienta no encontrada: {tool_call['tool']}"
            return llm_response
        except json.JSONDecodeError:
            # No es JSON, devolver respuesta original
            return llm_response
