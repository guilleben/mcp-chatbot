"""Gestor de contexto para el chat del IPECD.

Este módulo maneja el contexto de las conversaciones para evitar que el LLM
mezcle temas de diferentes consultas.
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

# Categorías principales del chat
CATEGORIES = {
    "precios": ["ipc", "inflacion", "inflación", "precios", "canasta"],
    "dolar": ["dolar", "dólar", "blue", "mep", "ccl", "oficial", "divisa", "cambio"],
    "empleo": ["empleo", "trabajo", "desempleo", "desocupacion", "desocupación", "sipa", "eph", "laboral"],
    "semaforo": ["semaforo", "semáforo", "indicadores", "economia", "economía"],
    "censo": ["censo", "poblacion", "población", "habitantes", "demografía", "municipio", "departamento"],
    "general": ["ayuda", "menu", "menú", "hola", "inicio"]
}


def detect_category(text: str) -> Optional[str]:
    """Detecta la categoría de una consulta basándose en palabras clave.
    
    Args:
        text: Texto de la consulta del usuario
        
    Returns:
        Categoría detectada o None si no se detecta ninguna
    """
    text_lower = text.lower()
    
    best_category = None
    best_score = 0
    
    for category, keywords in CATEGORIES.items():
        score = sum(1 for keyword in keywords if keyword in text_lower)
        if score > best_score:
            best_score = score
            best_category = category
    
    return best_category if best_score > 0 else None


def should_reset_context(current_category: Optional[str], new_category: Optional[str], 
                         menu_navigation: bool = False) -> bool:
    """Determina si se debe resetear el contexto del chat.
    
    Args:
        current_category: Categoría actual del chat
        new_category: Nueva categoría detectada
        menu_navigation: Si el usuario está navegando el menú
        
    Returns:
        True si se debe resetear el contexto
    """
    # Si es navegación de menú, siempre resetear
    if menu_navigation:
        return True
    
    # Si cambió de categoría, resetear
    if current_category and new_category and current_category != new_category:
        logging.info(f"Category change detected: {current_category} -> {new_category}")
        return True
    
    # Si es una categoría general (ayuda, menu), resetear
    if new_category == "general":
        return True
    
    return False


def create_context_aware_messages(
    system_message: str,
    user_message: str,
    previous_messages: List[Dict[str, str]],
    current_category: Optional[str] = None,
    max_context_messages: int = 4
) -> List[Dict[str, str]]:
    """Crea una lista de mensajes con contexto optimizado.
    
    Mantiene solo los mensajes relevantes para evitar confusión del LLM.
    
    Args:
        system_message: Mensaje del sistema con instrucciones
        user_message: Mensaje actual del usuario
        previous_messages: Mensajes anteriores de la conversación
        current_category: Categoría actual para filtrar contexto
        max_context_messages: Máximo de mensajes de contexto a mantener
        
    Returns:
        Lista de mensajes optimizada para el LLM
    """
    messages = [{"role": "system", "content": system_message}]
    
    # Filtrar mensajes relevantes
    relevant_messages = []
    
    for msg in previous_messages[-max_context_messages * 2:]:  # Ver últimos mensajes
        # Saltar mensajes del sistema
        if msg.get("role") == "system":
            continue
        
        # Si hay una categoría, filtrar por relevancia
        if current_category:
            msg_content = msg.get("content", "").lower()
            category_keywords = CATEGORIES.get(current_category, [])
            
            # Solo incluir si tiene alguna palabra clave relevante o es muy reciente
            is_relevant = any(kw in msg_content for kw in category_keywords)
            
            if is_relevant:
                relevant_messages.append(msg)
        else:
            # Sin categoría, incluir todos los recientes
            relevant_messages.append(msg)
    
    # Limitar cantidad de mensajes
    messages.extend(relevant_messages[-max_context_messages:])
    
    # Agregar mensaje actual
    messages.append({"role": "user", "content": user_message})
    
    return messages


def get_category_system_prompt(category: Optional[str]) -> str:
    """Obtiene instrucciones específicas para una categoría.
    
    Args:
        category: Categoría actual del chat
        
    Returns:
        Instrucciones adicionales para el system prompt
    """
    prompts = {
        "precios": """
TEMA ACTUAL: Precios e Inflación
- Enfócate SOLO en información del IPC, inflación y canasta básica
- NO menciones otros temas como dólar, empleo o censo
- Presenta variaciones mensuales e interanuales claramente
""",
        "dolar": """
TEMA ACTUAL: Cotización del Dólar
- Enfócate SOLO en cotizaciones del dólar (blue, oficial, MEP, CCL)
- NO menciones otros temas como IPC, empleo o censo
- Presenta precios de compra y venta claramente
""",
        "empleo": """
TEMA ACTUAL: Empleo y Trabajo
- Enfócate SOLO en datos de empleo, desempleo y trabajo
- NO menciones otros temas como dólar, IPC o censo
- Presenta tasas de actividad, empleo y desocupación
""",
        "semaforo": """
TEMA ACTUAL: Semáforo Económico
- Enfócate SOLO en los indicadores del semáforo económico
- NO menciones otros temas específicos
- Indica si cada indicador está en positivo (🟢) o negativo (🔴)
""",
        "censo": """
TEMA ACTUAL: Población y Censo
- Enfócate SOLO en datos demográficos y censales
- NO menciones otros temas como dólar, IPC o empleo
- Compara datos de 2010 vs 2022 cuando sea relevante
"""
    }
    
    return prompts.get(category, "")


class SessionContext:
    """Gestiona el contexto de una sesión de chat."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.current_category: Optional[str] = None
        self.menu_node_id: str = "root"
        self.menu_history: List[str] = ["root"]
        self.messages: List[Dict[str, str]] = []
        self.last_activity: datetime = datetime.now()
        self.tool_results: Dict[str, Any] = {}
    
    def update_category(self, text: str) -> bool:
        """Actualiza la categoría basándose en el texto.
        
        Returns:
            True si la categoría cambió
        """
        new_category = detect_category(text)
        category_changed = (new_category is not None and 
                          new_category != self.current_category and
                          new_category != "general")
        
        if new_category:
            self.current_category = new_category
        
        return category_changed
    
    def reset_for_new_topic(self):
        """Resetea el contexto para un nuevo tema."""
        self.messages = []
        self.tool_results = {}
        logging.info(f"Session {self.session_id}: Context reset for new topic")
    
    def add_message(self, role: str, content: str):
        """Agrega un mensaje al contexto."""
        self.messages.append({
            "role": role,
            "content": content
        })
        self.last_activity = datetime.now()
    
    def navigate_menu(self, node_id: str):
        """Actualiza el estado de navegación del menú."""
        self.menu_node_id = node_id
        if node_id not in self.menu_history:
            self.menu_history.append(node_id)
    
    def go_back(self) -> str:
        """Vuelve al nodo anterior del menú."""
        if len(self.menu_history) > 1:
            self.menu_history.pop()
            self.menu_node_id = self.menu_history[-1]
        else:
            self.menu_node_id = "root"
        return self.menu_node_id
    
    def store_tool_result(self, tool_name: str, result: Any):
        """Almacena el resultado de una herramienta."""
        self.tool_results[tool_name] = {
            "result": result,
            "timestamp": datetime.now()
        }


# Almacén global de contextos de sesión
session_contexts: Dict[str, SessionContext] = {}


def get_session_context(session_id: str) -> SessionContext:
    """Obtiene o crea el contexto de una sesión."""
    if session_id not in session_contexts:
        session_contexts[session_id] = SessionContext(session_id)
    return session_contexts[session_id]


def clear_session_context(session_id: str):
    """Limpia completamente el contexto de una sesión."""
    if session_id in session_contexts:
        del session_contexts[session_id]

