"""Encuentra opciones relacionadas del menú basadas en palabras clave.

Similar a como lo hace el MuniBot, cuando no se encuentran datos, muestra opciones del menú relacionadas.
"""
import logging
import re
from typing import List, Dict, Tuple
from menu_tree import MenuTree, MenuNode


class RelatedOptionsFinder:
    """Encuentra opciones del menú relacionadas con una consulta."""
    
    def __init__(self, menu_tree: MenuTree):
        """Inicializar finder de opciones relacionadas.
        
        Args:
            menu_tree: Árbol de menú
        """
        self.menu_tree = menu_tree
    
    def find_related_options(self, query: str, max_options: int = 5) -> List[Tuple[MenuNode, int]]:
        """Encontrar opciones del menú relacionadas con la consulta.
        
        Args:
            query: Consulta del usuario
            max_options: Número máximo de opciones a retornar
            
        Returns:
            Lista de tuplas (nodo, score) ordenadas por relevancia
        """
        if not query or not query.strip():
            return []
        
        # Normalizar query
        query_normalized = re.sub(r'[^\w\s]', '', query.strip().lower())
        query_words = set(query_normalized.split())
        
        # Filtrar palabras comunes
        common_words = {'el', 'la', 'los', 'las', 'de', 'del', 'en', 'un', 'una', 'y', 'o', 'que', 'para', 'por', 'con', 'sin', 'sobre', 'acceso', 'a'}
        query_words = {w for w in query_words if w not in common_words and len(w) > 2}
        
        if not query_words:
            return []
        
        related_nodes = []
        
        # Buscar en todos los nodos del menú
        for node_id, node in self.menu_tree.nodes.items():
            if not node:
                continue
            
            score = 0
            
            # Buscar en título
            if node.title:
                title_normalized = re.sub(r'[^\w\s]', '', node.title.strip().lower())
                title_words = set(title_normalized.split())
                
                # Coincidencia exacta
                if query_normalized == title_normalized:
                    score = 100
                # Coincidencia parcial
                elif query_normalized in title_normalized or title_normalized in query_normalized:
                    score = 50
                # Coincidencia por palabras comunes
                elif query_words & title_words:
                    common_count = len(query_words & title_words)
                    score = common_count * 15
            
            # Buscar en keywords
            if node.keywords:
                for keyword in node.keywords:
                    keyword_normalized = keyword.lower().strip()
                    if keyword_normalized in query_normalized or query_normalized in keyword_normalized:
                        score += 30
                    elif keyword_normalized in query_words:
                        score += 15
            
            # Buscar en descripción
            if node.description:
                desc_normalized = re.sub(r'[^\w\s]', '', node.description.strip().lower())
                desc_words = set(desc_normalized.split())
                if query_words & desc_words:
                    score += len(query_words & desc_words) * 5
            
            # Solo incluir nodos con score significativo
            if score >= 15:
                related_nodes.append((node, score))
        
        # Ordenar por score descendente y retornar los mejores
        related_nodes.sort(key=lambda x: x[1], reverse=True)
        return related_nodes[:max_options]
    
    def format_related_options_menu(self, query: str, related_nodes: List[Tuple[MenuNode, int]]) -> str:
        """Formatear opciones relacionadas como menú.
        
        Args:
            query: Consulta original del usuario
            related_nodes: Lista de nodos relacionados con sus scores
            
        Returns:
            String formateado con el menú de opciones relacionadas
        """
        if not related_nodes:
            return ""
        
        menu_text = f"No encontré información específica sobre '{query}', pero puedo ayudarte con estas opciones relacionadas:\n\n"
        
        for i, (node, score) in enumerate(related_nodes, 1):
            menu_text += f"{i}. {node.title}\n"
            if node.description:
                menu_text += f"   └─ {node.description}\n"
        
        menu_text += "\n💡 También puedes escribir tu consulta de otra manera o navegar por el menú principal."
        
        return menu_text

