"""Detector de palabras clave para preguntas abiertas."""
import logging
import re
from typing import Dict, List, Optional, Tuple

from menu_tree import MenuTree


class KeywordDetector:
    """Detecta palabras clave en preguntas abiertas y las relaciona con acciones."""
    
    def __init__(self, menu_tree: MenuTree, db_client=None):
        """Inicializar el detector de palabras clave.
        
        Args:
            menu_tree: Árbol de menú para buscar coincidencias
            db_client: Cliente de base de datos opcional para cargar palabras clave reales
        """
        self.menu_tree = menu_tree
        self.db_client = db_client
        self.db_keywords = []  # Palabras clave extraídas de la base de datos
        
        # Palabras clave comunes y sus acciones
        self.common_keywords = {
            # Comandos de navegación
            "menu": ["menú", "menu", "inicio", "principal", "volver"],
            "back": ["atrás", "back", "volver", "anterior", "regresar"],
            "help": ["ayuda", "help", "como usar", "instrucciones", "información"],
            
            # Consultas comunes
            "ultimo": ["último", "ultimo", "última", "ultima", "reciente", "más reciente", "last"],
            "primero": ["primero", "primera", "inicial", "first"],
            "promedio": ["promedio", "media", "average", "mean"],
            "suma": ["suma", "total", "sum", "total"],
            "maximo": ["máximo", "maximo", "mayor", "highest", "max"],
            "minimo": ["mínimo", "minimo", "menor", "lowest", "min"],
            
            # Tipos de datos
            "economico": ["económico", "economico", "economía", "economia", "finanzas", "dinero", 
                         "presupuesto", "ingresos", "gastos", "inflación", "inflacion"],
            "socio": ["social", "sociedad", "demografía", "demografia", "población", "poblacion",
                      "ciudadanos", "habitantes", "personas", "gente"],
            "datalake": ["datalake", "raw", "bruto", "crudo", "sin procesar"],
            "dwh": ["dwh", "warehouse", "almacén", "almacen", "procesado", "transformado"],
            
            # Acciones
            "buscar": ["buscar", "busca", "encontrar", "muestra", "muéstrame", "dame", "dame",
                      "quiero ver", "necesito", "información sobre", "datos de"],
            "estructura": ["estructura", "tablas", "columnas", "schema", "esquema", "base de datos",
                          "qué hay", "que hay", "qué información", "que información"],
        }
        
        # Patrones para detectar consultas específicas
        self.query_patterns = [
            (r"(último|ultimo|última|ultima|más reciente|mas reciente)\s+(valor|dato|registro|resultado)", "ultimo"),
            (r"(primer|primera|inicial)\s+(valor|dato|registro|resultado)", "primero"),
            (r"(promedio|media)\s+(de|del|de la)", "promedio"),
            (r"(suma|total)\s+(de|del|de la)", "suma"),
            (r"(máximo|maximo|mayor)\s+(valor|dato)", "maximo"),
            (r"(mínimo|minimo|menor)\s+(valor|dato)", "minimo"),
            (r"(año|ano|años|anos)\s+(\d{4})", "year"),
            (r"(\d{4})", "year"),
            (r"(mes|meses)\s+(de|del)", "month"),
            (r"(día|dia|días|dias)\s+(de|del)", "day"),
        ]
        
        # Cargar palabras clave de la base de datos si está disponible
        self._load_database_keywords()
    
    def detect_intent(self, text: str) -> Dict[str, any]:
        """Detectar la intención del usuario basándose en palabras clave.
        
        Args:
            text: Texto del usuario
            
        Returns:
            Diccionario con información sobre la intención detectada:
            {
                "type": "menu" | "query" | "keyword" | "open",
                "node_id": ID del nodo si es menú,
                "keywords": Lista de palabras clave encontradas,
                "query_type": Tipo de consulta (ultimo, promedio, etc.),
                "db_query": Consulta para la base de datos,
                "confidence": Nivel de confianza (0-1)
            }
        """
        text_lower = text.lower().strip()
        
        # Detectar si es un número (selección de menú)
        try:
            option_number = int(text_lower)
            # Buscar en el menú actual (por defecto root)
            root = self.menu_tree.get_root()
            if root and root.children:
                if 1 <= option_number <= len(root.children):
                    child_id = root.children[option_number - 1]
                    child_node = self.menu_tree.get_node(child_id)
                    if child_node:
                        return {
                            "type": "menu" if child_node.action == "menu" else "query",
                            "node_id": child_node.id,
                            "keywords": ["number_selection"],
                            "db_query": child_node.db_query,
                            "confidence": 1.0
                        }
        except ValueError:
            pass  # No es un número, continuar
        
        # Detectar comandos de navegación
        if any(keyword in text_lower for keyword in self.common_keywords["menu"]):
            return {
                "type": "menu",
                "node_id": "root",
                "keywords": ["menu"],
                "confidence": 1.0
            }
        
        if any(keyword in text_lower for keyword in self.common_keywords["back"]):
            return {
                "type": "back",
                "keywords": ["back"],
                "confidence": 1.0
            }
        
        if any(keyword in text_lower for keyword in self.common_keywords["help"]):
            return {
                "type": "menu",
                "node_id": "ayuda",
                "keywords": ["help"],
                "confidence": 1.0
            }
        
        # Detectar tipo de consulta (último, promedio, etc.)
        query_type = None
        for pattern, qtype in self.query_patterns:
            if re.search(pattern, text_lower):
                query_type = qtype
                break
        
        # Detectar palabras clave comunes
        found_keywords = []
        for category, keywords in self.common_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    found_keywords.append(category)
                    break
        
        # Detectar palabras clave de la base de datos
        db_matches = []
        for db_keyword in self.db_keywords:
            # Buscar coincidencias exactas o parciales
            if db_keyword in text_lower or text_lower in db_keyword:
                db_matches.append(db_keyword)
        
        # Si hay coincidencias con la base de datos, aumentar la confianza
        if db_matches:
            found_keywords.append("database_match")
            logging.info(f"Found database keyword matches: {db_matches[:5]}")  # Log primeros 5
        
        # Buscar nodo del menú por palabras clave explícitas o variaciones comunes
        # Mapeo de términos comunes a IDs de nodos PADRES (que tienen menús)
        menu_term_mapping = {
            # Términos principales - navegar a nodos padre con menús
            "datos económicos": "economico",
            "datos economicos": "economico",
            "datos sociales": "socio",
            "datalake económico": "economico",  # Navegar al padre para ver opciones
            "datalake economico": "economico",
            "datalake social": "socio",  # Navegar al padre "socio" para ver opciones
            "datalake socio": "socio",
            "dwh económico": "economico",  # Navegar al padre
            "dwh economico": "economico",
            "dwh social": "socio",  # Navegar al padre
            "dwh socio": "socio",
            "información general": "general",
            "informacion general": "general",
        }
        
        # Buscar coincidencias exactas primero
        matched_node_id = None
        for term, node_id in menu_term_mapping.items():
            if term in text_lower:
                matched_node_id = node_id
                break
        
        # Si no hay coincidencia exacta, buscar por palabras clave en los nodos
        if not matched_node_id:
            menu_node = self.menu_tree.find_node_by_keyword(text)
            if menu_node:
                # Si el nodo encontrado es un menú, usarlo directamente
                if menu_node.action == "menu":
                    matched_node_id = menu_node.id
                else:
                    # Si es un nodo hijo (query), buscar su nodo padre que tenga menú
                    # Buscar en el árbol para encontrar el padre
                    for parent_node in self.menu_tree.nodes.values():
                        if parent_node.children and menu_node.id in parent_node.children:
                            if parent_node.action == "menu":
                                matched_node_id = parent_node.id
                                break
        
        # Si encontramos un nodo de menú, navegar a él
        if matched_node_id:
            menu_node = self.menu_tree.get_node(matched_node_id)
            if menu_node and menu_node.action == "menu":
                return {
                    "type": "menu",
                    "node_id": matched_node_id,
                    "keywords": menu_node.keywords if menu_node else [],
                    "confidence": 0.95  # Alta confianza para términos explícitos del menú
                }
        
        # Si hay palabras clave de estructura, manejar directamente
        if "estructura" in found_keywords:
            return {
                "type": "query",
                "node_id": "estructura",
                "keywords": found_keywords,
                "db_query": "structure",
                "query_type": query_type,
                "confidence": 0.9
            }
        
        # Si hay coincidencias con la base de datos, aumentar la confianza de que es una consulta válida
        confidence = 0.6
        if db_matches:
            confidence = 0.8  # Mayor confianza si hay palabras clave de la BD
        
        # Para cualquier otra consulta (incluyendo "tasa de inflación"), tratarla como consulta abierta
        # Esto permite que se busque primero en la base de datos
        return {
            "type": "open",
            "keywords": found_keywords,
            "query_type": query_type,
            "db_query": text,  # Usar el texto completo como consulta
            "confidence": confidence,
            "db_matches": db_matches[:10] if db_matches else []  # Guardar primeras 10 coincidencias
        }
    
    def extract_keywords(self, text: str) -> List[str]:
        """Extraer palabras clave relevantes del texto.
        
        Args:
            text: Texto a analizar
            
        Returns:
            Lista de palabras clave encontradas
        """
        text_lower = text.lower()
        keywords = []
        
        # Buscar todas las palabras clave
        for category, keyword_list in self.common_keywords.items():
            for keyword in keyword_list:
                if keyword in text_lower:
                    keywords.append(keyword)
        
        return list(set(keywords))  # Eliminar duplicados
    
    def build_database_query(self, intent: Dict[str, any], original_text: str) -> str:
        """Construir una consulta optimizada para la base de datos basada en la intención.
        
        Args:
            intent: Intención detectada
            original_text: Texto original del usuario
            
        Returns:
            Consulta optimizada para la base de datos
        """
        query_type = intent.get("query_type")
        db_query = intent.get("db_query", original_text)
        
        # Si hay un tipo de consulta específico, agregarlo al query
        if query_type == "ultimo":
            # Buscar términos relacionados con "último" en el texto original
            query = original_text
            # Priorizar términos que no sean "último" para la búsqueda
            words = original_text.lower().split()
            relevant_words = [w for w in words if w not in ["último", "ultimo", "última", "ultima", 
                                                             "más", "reciente", "mas", "valor", "dato"]]
            if relevant_words:
                query = " ".join(relevant_words)
        elif query_type == "promedio":
            query = original_text.replace("promedio", "").replace("media", "").strip()
        elif query_type == "suma":
            query = original_text.replace("suma", "").replace("total", "").strip()
        else:
            query = original_text
        
        return query.strip() if query.strip() else original_text
    
    def _load_database_keywords(self):
        """Cargar palabras clave desde la estructura de la base de datos."""
        if not self.db_client:
            return
        
        try:
            structure = self.db_client.get_database_structure()
            db_keywords = []
            
            for db_name, tables in structure.items():
                # Agregar nombre de base de datos como palabra clave
                db_keywords.append(db_name.lower())
                
                for table_name, table_info in tables.items():
                    # Agregar nombre de tabla como palabra clave
                    table_lower = table_name.lower()
                    db_keywords.append(table_lower)
                    
                    # Agregar nombres de columnas como palabras clave
                    columns = table_info.get('columns', [])
                    for column in columns:
                        column_lower = column.lower()
                        # Excluir columnas genéricas como id, fecha, etc.
                        if column_lower not in ['id', 'created_at', 'updated_at', 'deleted_at', 'timestamp', 'fecha']:
                            db_keywords.append(column_lower)
                    
                    # Extraer palabras clave de datos de muestra si están disponibles
                    sample = table_info.get('sample')
                    if sample and isinstance(sample, dict):
                        for key, value in sample.items():
                            if isinstance(value, str) and len(value) > 3:
                                # Agregar valores de muestra como palabras clave potenciales
                                words = value.lower().split()
                                for word in words:
                                    if len(word) > 3 and word.isalpha():
                                        db_keywords.append(word)
            
            # Eliminar duplicados y guardar
            self.db_keywords = list(set(db_keywords))
            logging.info(f"Loaded {len(self.db_keywords)} keywords from database structure")
            
        except Exception as e:
            logging.warning(f"Error loading database keywords: {e}")
            self.db_keywords = []

