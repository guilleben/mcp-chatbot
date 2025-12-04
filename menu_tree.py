"""Sistema de menú con árbol de decisión para el chatbot."""
import json
import logging
import re
from typing import Dict, List, Optional, Any, Tuple

from config import Configuration


class MenuNode:
    """Representa un nodo en el árbol de menú."""
    
    def __init__(self, node_id: str, title: str, description: str = "", 
                 action: Optional[str] = None, children: Optional[List[str]] = None,
                 keywords: Optional[List[str]] = None, db_query: Optional[str] = None,
                 tool: Optional[str] = None, tool_args: Optional[Dict[str, Any]] = None,
                 info_text: Optional[str] = None):
        """Inicializar un nodo del menú.
        
        Args:
            node_id: Identificador único del nodo
            title: Título del nodo
            description: Descripción del nodo
            action: Acción a realizar (query, menu, info, tool)
            children: Lista de IDs de nodos hijos
            keywords: Palabras clave asociadas al nodo
            db_query: Consulta SQL o término de búsqueda para la base de datos
            tool: Nombre de la herramienta MCP a ejecutar (si action="tool")
            tool_args: Argumentos para la herramienta MCP
            info_text: Texto informativo a mostrar (si action="info")
        """
        self.id = node_id
        self.title = title
        self.description = description
        self.action = action or "menu"
        self.children = children or []
        self.keywords = keywords or []
        self.db_query = db_query
        self.tool = tool
        self.tool_args = tool_args or {}
        self.info_text = info_text
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertir nodo a diccionario."""
        result = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "action": self.action,
            "children": self.children,
            "keywords": self.keywords,
            "db_query": self.db_query
        }
        if self.tool:
            result["tool"] = self.tool
            result["tool_args"] = self.tool_args
        if self.info_text:
            result["info_text"] = self.info_text
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MenuNode':
        """Crear nodo desde diccionario."""
        return cls(
            node_id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            action=data.get("action", "menu"),
            children=data.get("children", []),
            keywords=data.get("keywords", []),
            db_query=data.get("db_query"),
            tool=data.get("tool"),
            tool_args=data.get("tool_args", {}),
            info_text=data.get("info_text")
        )


class MenuTree:
    """Gestiona el árbol de decisión del menú."""
    
    def __init__(self, config_path: str = "menu_config.json"):
        """Inicializar el árbol de menú.
        
        Args:
            config_path: Ruta al archivo de configuración del menú
        """
        self.config_path = config_path
        self.nodes: Dict[str, MenuNode] = {}
        self.root_node_id: Optional[str] = None
        self.load_menu()
    
    def load_menu(self) -> None:
        """Cargar la configuración del menú desde archivo JSON."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Cargar nodos
            for node_data in config.get("nodes", []):
                node = MenuNode.from_dict(node_data)
                self.nodes[node.id] = node
            
            # Establecer nodo raíz
            self.root_node_id = config.get("root_node_id", "root")
            
            # Validar que el nodo raíz existe
            if self.root_node_id not in self.nodes:
                logging.warning(f"Root node '{self.root_node_id}' not found, using first node")
                if self.nodes:
                    self.root_node_id = list(self.nodes.keys())[0]
            
            # Validar y limpiar children duplicados de TODOS los nodos
            for node_id, node in self.nodes.items():
                if node and node.children:
                    original_count = len(node.children)
                    node.children = list(dict.fromkeys(node.children))  # Eliminar duplicados manteniendo orden
                    if len(node.children) < original_count:
                        logging.info(f"Removed {original_count - len(node.children)} duplicate children from node '{node_id}'")
            
            # Validar que el nodo raíz existe después de la limpieza
            root_node = self.get_node(self.root_node_id)
            logging.info(f"Menu tree loaded: {len(self.nodes)} nodes, root: {self.root_node_id}")
            if root_node:
                logging.info(f"Root node has {len(root_node.children)} children: {root_node.children[:5]}")
            else:
                logging.error(f"Root node '{self.root_node_id}' not found after loading!")
                raise ValueError(f"Root node '{self.root_node_id}' not found")
        except FileNotFoundError:
            logging.warning(f"Menu config file '{self.config_path}' not found, creating default menu")
            self._create_default_menu()
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing menu config JSON: {e}")
            self._create_default_menu()
        except Exception as e:
            logging.error(f"Error loading menu: {e}")
            self._create_default_menu()
    
    def _create_default_menu(self) -> None:
        """Crear menú por defecto basado en las bases de datos disponibles."""
        config = Configuration()
        
        # Menú raíz
        root = MenuNode(
            node_id="root",
            title="Menú Principal",
            description="Bienvenido al chatbot de datos. Selecciona una opción:",
            action="menu",
            children=["economico", "socio", "general"]
        )
        
        # Menú económico
        economico = MenuNode(
            node_id="economico",
            title="📊 Datos Económicos",
            description="Información económica y financiera",
            action="menu",
            children=["datalake_economico", "dwh_economico"],
            keywords=["economico", "economía", "finanzas", "dinero", "presupuesto", "ingresos", "gastos"]
        )
        
        # Menú socio
        socio = MenuNode(
            node_id="socio",
            title="👥 Datos Sociales",
            description="Información social y demográfica",
            action="menu",
            children=["datalake_socio", "dwh_socio"],
            keywords=["social", "sociedad", "demografía", "población", "ciudadanos", "habitantes"]
        )
        
        # Menú general
        general = MenuNode(
            node_id="general",
            title="ℹ️ Información General",
            description="Información general y ayuda",
            action="menu",
            children=["ayuda", "estructura"],
            keywords=["ayuda", "help", "información", "info", "general"]
        )
        
        # Submenús económicos
        datalake_economico = MenuNode(
            node_id="datalake_economico",
            title="📈 Datalake Económico",
            description="Datos económicos en bruto",
            action="query",
            db_query="datalake_economico",
            keywords=["datalake", "raw", "bruto", "económico"]
        )
        
        dwh_economico = MenuNode(
            node_id="dwh_economico",
            title="📊 DWH Económico",
            description="Data Warehouse económico procesado",
            action="query",
            db_query="dwh_economico",
            keywords=["dwh", "warehouse", "procesado", "económico"]
        )
        
        # Submenús sociales
        datalake_socio = MenuNode(
            node_id="datalake_socio",
            title="👤 Datalake Social",
            description="Datos sociales en bruto",
            action="query",
            db_query="datalake_socio",
            keywords=["datalake", "raw", "bruto", "social"]
        )
        
        dwh_socio = MenuNode(
            node_id="dwh_socio",
            title="👥 DWH Social",
            description="Data Warehouse social procesado",
            action="query",
            db_query="dwh_socio",
            keywords=["dwh", "warehouse", "procesado", "social"]
        )
        
        # Ayuda
        ayuda = MenuNode(
            node_id="ayuda",
            title="❓ Ayuda",
            description="Información sobre cómo usar el chatbot",
            action="info",
            keywords=["ayuda", "help", "como usar", "instrucciones"]
        )
        
        # Estructura
        estructura = MenuNode(
            node_id="estructura",
            title="🗂️ Estructura de Datos",
            description="Ver estructura de las bases de datos disponibles",
            action="query",
            db_query="structure",
            keywords=["estructura", "tablas", "columnas", "schema", "base de datos"]
        )
        
        # Agregar todos los nodos
        for node in [root, economico, socio, general, datalake_economico, dwh_economico,
                     datalake_socio, dwh_socio, ayuda, estructura]:
            self.nodes[node.id] = node
        
        self.root_node_id = "root"
        
        # Guardar menú por defecto
        self.save_menu()
    
    def save_menu(self) -> None:
        """Guardar la configuración del menú en archivo JSON."""
        try:
            config = {
                "root_node_id": self.root_node_id,
                "nodes": [node.to_dict() for node in self.nodes.values()]
            }
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            logging.info(f"Menu saved to {self.config_path}")
        except Exception as e:
            logging.error(f"Error saving menu: {e}")
    
    def get_node(self, node_id: str) -> Optional[MenuNode]:
        """Obtener un nodo por su ID.
        
        Args:
            node_id: ID del nodo
            
        Returns:
            El nodo si existe, None en caso contrario
        """
        return self.nodes.get(node_id)
    
    def get_root(self) -> Optional[MenuNode]:
        """Obtener el nodo raíz.
        
        Returns:
            El nodo raíz si existe
        """
        if self.root_node_id:
            return self.get_node(self.root_node_id)
        return None
    
    def format_menu(self, node_id: Optional[str] = None) -> str:
        """Formatear el menú para mostrar al usuario.
        
        Args:
            node_id: ID del nodo a mostrar. Si es None, muestra el raíz.
            
        Returns:
            String formateado con el menú
        """
        try:
            if node_id is None:
                node_id = self.root_node_id
            
            if not node_id:
                logging.error("No root_node_id set, using 'root'")
                node_id = "root"
            
            node = self.get_node(node_id)
            if not node:
                logging.error(f"Node {node_id} not found in menu tree. Available nodes: {list(self.nodes.keys())[:10]}")
                # Intentar con el primer nodo disponible
                if self.nodes:
                    first_node_id = list(self.nodes.keys())[0]
                    logging.warning(f"Trying with first available node: {first_node_id}")
                    node = self.get_node(first_node_id)
                    if not node:
                        return "1. 📊 Datos Económicos\n2. 👥 Datos Sociales\n3. ℹ️ Información General"
                else:
                    return "1. 📊 Datos Económicos\n2. 👥 Datos Sociales\n3. ℹ️ Información General"
            
            # Formato simplificado - solo opciones, sin títulos ni descripciones adicionales
            menu_text = ""
            
            if node.children:
                # Eliminar duplicados de children manteniendo el orden
                seen_children = []
                unique_children = []
                for child_id in node.children:
                    if child_id not in seen_children:
                        seen_children.append(child_id)
                        unique_children.append(child_id)
                
                # Validar que los children existen
                valid_children = []
                for child_id in unique_children:
                    if self.get_node(child_id):
                        valid_children.append(child_id)
                    else:
                        logging.warning(f"Child node {child_id} not found, skipping")
                
                if not valid_children:
                    logging.error(f"No valid children found for node {node_id}")
                    return "❌ No hay opciones disponibles en este menú."
                
                # Solo mostrar las opciones numeradas (sin descripciones técnicas)
                for i, child_id in enumerate(valid_children, 1):
                    child = self.get_node(child_id)
                    if child:
                        menu_text += f"{i}. {child.title}\n"
                        # Solo mostrar descripción si no es técnica (no contiene nombres de BD o tablas)
                        if child.description and not any(tech_term in child.description.lower() 
                                                         for tech_term in ['base de datos', 'tabla', 'datalake', 'dwh']):
                            menu_text += f"   └─ {child.description}\n"
            elif node.action == "info":
                menu_text += self._get_info_content(node_id)
            elif node.action == "query":
                menu_text += f"🔍 Buscando información sobre: {node.title}"
            
            result = menu_text.strip()
            
            # Validar que el resultado no esté vacío
            if not result:
                logging.warning(f"Empty menu text for node {node_id}, using fallback")
                result = "1. 📊 Datos Económicos\n2. 👥 Datos Sociales\n3. ℹ️ Información General"
            
            return result
        except Exception as e:
            logging.error(f"Error formatting menu for node {node_id}: {e}", exc_info=True)
            # Fallback a menú básico
            return "1. 📊 Datos Económicos\n2. 👥 Datos Sociales\n3. ℹ️ Información General"
    
    def _get_info_content(self, node_id: str) -> str:
        """Obtener contenido informativo para nodos de tipo info.
        
        Args:
            node_id: ID del nodo
            
        Returns:
            Contenido informativo
        """
        if node_id == "ayuda":
            return """
═══════════════════════════════════════════════════════
  📖 CÓMO USAR EL CHATBOT
═══════════════════════════════════════════════════════

📌 NAVEGACIÓN POR MENÚ:
   • Puedes navegar seleccionando números (1, 2, 3...)
   • O escribiendo palabras clave relacionadas

📌 PREGUNTAS ABIERTAS:
   • Escribe tu pregunta directamente
   • El bot detectará palabras clave automáticamente
   • Buscará en la base de datos de forma inteligente

📌 COMANDOS ESPECIALES:
   • "menú" o "menu" → Volver al menú principal
   • "atrás" o "back" → Volver al menú anterior
   • "ayuda" → Mostrar esta ayuda

📌 EJEMPLOS DE PREGUNTAS:
   • "¿Cuál es el último valor de inflación?"
   • "Muéstrame datos económicos del año 2023"
   • "Información sobre población"
   • "Estructura de las bases de datos"

═══════════════════════════════════════════════════════
"""
        return ""
    
    def find_node_by_keyword(self, text: str) -> Optional[MenuNode]:
        """Buscar un nodo que coincida con palabras clave en el texto.
        
        Args:
            text: Texto a analizar
            
        Returns:
            El nodo que mejor coincide, o None si no hay coincidencia
        """
        text_lower = text.lower().strip()
        
        # Detectar si el usuario escribió un número para seleccionar opción del menú
        try:
            option_number = int(text_lower)
            # Si hay un nodo actual, buscar en sus hijos
            # Por ahora, buscar en el nodo raíz
            root = self.get_root()
            if root and root.children:
                if 1 <= option_number <= len(root.children):
                    child_id = root.children[option_number - 1]
                    return self.get_node(child_id)
        except ValueError:
            pass  # No es un número, continuar con búsqueda por palabras clave
        
        best_match = None
        best_score = 0
        
        # Limpiar texto de entrada una sola vez
        text_clean = re.sub(r'[^\w\s]', '', text_lower)
        
        # Detectar si es una consulta de acción (el usuario quiere datos, no navegar menú)
        action_words = ['comparar', 'comparacion', 'comparación', 'dame', 'muéstrame', 'muestrame',
                       'cual es', 'cuál es', 'cuanto', 'cuánto', 'cuantos', 'cuántos',
                       'diferencia', 'variacion', 'variación', 'crecimiento', 'evolucion', 'evolución']
        is_action_query = any(word in text_lower for word in action_words)
        
        for node in self.nodes.values():
            score = 0
            
            # Buscar en el título del nodo (más importante)
            if node.title:
                title_lower = node.title.lower()
                # Remover emojis y caracteres especiales para comparación
                title_clean = re.sub(r'[^\w\s]', '', title_lower)
                
                # Coincidencia exacta en título
                if title_clean == text_clean:
                    score += 20
                # Título contiene el texto o viceversa
                elif title_clean in text_clean or text_clean in title_clean:
                    score += 15
                # Palabras del título en el texto
                elif any(word in text_clean for word in title_clean.split() if len(word) > 3):
                    score += 10
            
            # Buscar en palabras clave
            if node.keywords:
                for keyword in node.keywords:
                    keyword_lower = keyword.lower()
                    if keyword_lower in text_lower:
                        # Puntuación más alta para coincidencias exactas
                        if keyword_lower == text_lower:
                            score += 10
                        elif text_lower.startswith(keyword_lower) or text_lower.endswith(keyword_lower):
                            score += 5
                        else:
                            score += 1
            
            # Buscar en la descripción del nodo
            if node.description:
                desc_lower = node.description.lower()
                desc_clean = re.sub(r'[^\w\s]', '', desc_lower)
                # Coincidencia exacta con descripción
                if desc_clean == text_clean:
                    score += 15
                # Descripción contiene el texto o viceversa
                elif desc_clean in text_clean or text_clean in desc_clean:
                    score += 10
                # Palabras de la descripción en el texto
                elif any(word in text_clean for word in desc_clean.split() if len(word) > 4):
                    score += 3
            
            # Buscar en el ID del nodo (última opción)
            node_id_lower = node.id.lower()
            if node_id_lower in text_lower or text_lower in node_id_lower:
                score += 3
            
            # Si es una consulta de acción, dar bonus a nodos "tool" y penalizar "menu"
            if is_action_query and score > 0:
                if node.action == "tool":
                    score += 10  # Bonus grande para herramientas cuando hay palabras de acción
                elif node.action == "menu" and node.children:
                    score -= 3  # Penalizar menús con hijos (el usuario probablemente quiere datos)
            
            # Priorizar nodos "tool" sobre nodos "menu" con scores similares
            # Los nodos "tool" dan respuestas directas, los "menu" muestran submenús
            if score > best_score:
                best_score = score
                best_match = node
            elif score == best_score and score > 0:
                # En caso de empate, preferir "tool" sobre "menu"
                if node.action == "tool" and (best_match is None or best_match.action == "menu"):
                    best_match = node
        
        # Solo retornar si hay una coincidencia significativa
        if best_score >= 5:  # Aumentado el umbral para ser más estricto
            return best_match
        
        return None
    
    def get_child_by_number(self, node_id: str, number: int) -> Optional[MenuNode]:
        """Obtener un nodo hijo por número de opción.
        
        Args:
            node_id: ID del nodo padre
            number: Número de opción (1-indexed)
            
        Returns:
            El nodo hijo si existe, None en caso contrario
        """
        node = self.get_node(node_id)
        if not node or not node.children:
            return None
        
        if 1 <= number <= len(node.children):
            child_id = node.children[number - 1]
            return self.get_node(child_id)
        
        return None
    
    def find_path_to_node(self, target_node_id: str) -> List[str]:
        """Encontrar el camino desde la raíz hasta un nodo.
        
        Args:
            target_node_id: ID del nodo objetivo
            
        Returns:
            Lista de IDs de nodos desde la raíz hasta el objetivo
        """
        def dfs(current_id: str, path: List[str], visited: set) -> Optional[List[str]]:
            if current_id == target_node_id:
                return path + [current_id]
            
            node = self.get_node(current_id)
            if not node:
                return None
            
            visited.add(current_id)
            
            for child_id in node.children:
                if child_id not in visited:
                    result = dfs(child_id, path + [current_id], visited)
                    if result:
                        return result
            
            return None
        
        if not self.root_node_id:
            return []
        
        result = dfs(self.root_node_id, [], set())
        return result if result else []

