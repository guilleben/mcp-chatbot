"""Centralized tool execution module."""
import logging
from typing import Any, Dict, Optional

from mcp_tools_server import DatabaseTools


class ToolExecutor:
    """Ejecuta herramientas de base de datos de forma centralizada."""
    
    def __init__(self, db_tools: Optional[DatabaseTools] = None):
        self.db_tools = db_tools
        self._tool_handlers = {
            "get_ipc": self._exec_get_ipc,
            "get_dolar": self._exec_get_dolar,
            "get_empleo": self._exec_get_empleo,
            "get_semaforo": self._exec_get_semaforo,
            "get_censo": self._exec_get_censo,
            "get_censo_departamentos": self._exec_get_censo_departamentos,
            "get_combustible": self._exec_get_combustible,
            "get_canasta_basica": self._exec_get_canasta_basica,
            "get_ecv": self._exec_get_ecv,
            "get_patentamientos": self._exec_get_patentamientos,
            "get_aeropuertos": self._exec_get_aeropuertos,
            "get_oede": self._exec_get_oede,
            "get_pobreza": self._exec_get_pobreza,
            "search_database": self._exec_search_database,
            # Nuevas herramientas
            "get_emae": self._exec_get_emae,
            "get_pbg": self._exec_get_pbg,
            "get_salarios": self._exec_get_salarios,
            "get_supermercados": self._exec_get_supermercados,
            "get_construccion": self._exec_get_construccion,
            "get_ipc_corrientes": self._exec_get_ipc_corrientes,
        }
    
    def execute(self, tool_name: str, tool_args: Optional[Dict[str, Any]] = None) -> str:
        """
        Ejecuta una herramienta por nombre.
        
        Args:
            tool_name: Nombre de la herramienta
            tool_args: Argumentos opcionales
            
        Returns:
            Resultado de la herramienta o mensaje de error
        """
        if not self.db_tools:
            return "Error: Herramientas de base de datos no disponibles"
        
        tool_args = tool_args or {}
        handler = self._tool_handlers.get(tool_name)
        
        if not handler:
            logging.warning(f"Tool not found: {tool_name}")
            return f"Herramienta {tool_name} no disponible"
        
        try:
            logging.info(f"Executing tool {tool_name} with args {tool_args}")
            return handler(tool_args)
        except Exception as e:
            logging.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            return "Lo siento, hubo un error al obtener los datos. Por favor intenta de nuevo."
    
    def _exec_get_ipc(self, args: Dict) -> str:
        return self.db_tools.get_ipc(**args)
    
    def _exec_get_dolar(self, args: Dict) -> str:
        return self.db_tools.get_dolar(**args)
    
    def _exec_get_empleo(self, args: Dict) -> str:
        return self.db_tools.get_empleo(**args)
    
    def _exec_get_semaforo(self, args: Dict) -> str:
        return self.db_tools.get_semaforo(**args)
    
    def _exec_get_censo(self, args: Dict) -> str:
        return self.db_tools.get_censo(**args)
    
    def _exec_get_censo_departamentos(self, args: Dict) -> str:
        return self.db_tools.get_censo_departamentos(**args)
    
    def _exec_get_combustible(self, args: Dict) -> str:
        return self.db_tools.get_combustible(**args)
    
    def _exec_get_canasta_basica(self, args: Dict) -> str:
        return self.db_tools.get_canasta_basica()
    
    def _exec_get_ecv(self, args: Dict) -> str:
        return self.db_tools.get_ecv(**args)
    
    def _exec_get_patentamientos(self, args: Dict) -> str:
        return self.db_tools.get_patentamientos(**args)
    
    def _exec_get_aeropuertos(self, args: Dict) -> str:
        return self.db_tools.get_aeropuertos(**args)
    
    def _exec_get_oede(self, args: Dict) -> str:
        return self.db_tools.get_oede(**args)
    
    def _exec_get_pobreza(self, args: Dict) -> str:
        return self.db_tools.get_pobreza(**args)
    
    def _exec_search_database(self, args: Dict) -> str:
        return self.db_tools.search_database(**args)
    
    def _exec_get_emae(self, args: Dict) -> str:
        return self.db_tools.get_emae(**args)
    
    def _exec_get_pbg(self, args: Dict) -> str:
        return self.db_tools.get_pbg(**args)
    
    def _exec_get_salarios(self, args: Dict) -> str:
        return self.db_tools.get_salarios(**args)
    
    def _exec_get_supermercados(self, args: Dict) -> str:
        return self.db_tools.get_supermercados(**args)
    
    def _exec_get_construccion(self, args: Dict) -> str:
        return self.db_tools.get_construccion(**args)
    
    def _exec_get_ipc_corrientes(self, args: Dict) -> str:
        return self.db_tools.get_ipc_corrientes()
    
    def is_available(self) -> bool:
        """Verifica si las herramientas están disponibles."""
        return self.db_tools is not None
    
    def get_available_tools(self) -> list:
        """Retorna lista de herramientas disponibles."""
        return list(self._tool_handlers.keys())

