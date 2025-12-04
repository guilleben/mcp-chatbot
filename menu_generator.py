"""Generador de menú dinámico basado en la estructura de la base de datos."""
import logging
import re
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict

from database import DatabaseClient
from menu_tree import MenuNode, MenuTree

# Caché global para estructura de BD (evita consultas repetidas)
_db_structure_cache: Optional[Dict] = None
_categorized_tables_cache: Optional[Dict] = None


class MenuGenerator:
    """Genera menú dinámico basado en la estructura de la base de datos."""
    
    # Mapeo de nombres técnicos a nombres amigables
    FRIENDLY_NAMES = {
        # PBG
        "pbg_valor_anual": "PBG Anual",
        "pbg_valor_trimestral": "PBG Trimestral",
        "pbg_anual_desglosado": "PBG Anual Desglosado",
        
        # Inflación
        "tabla_ipc_acumulados": "Índice de Precios al Consumidor",
        "ipc": "Inflación Mensual",
        
        # Empleo
        "empleados_cada_mil_habitantes": "Empleados por cada 1000 habitantes",
        "empleo_nacional_porcentajes_variaciones": "Variaciones de Empleo Nacional",
        "empleo_nea_variaciones": "Variaciones de Empleo NEA",
        "indicadores_semaforo": "Indicadores Semáforo",
        "puestos_de_trabajo": "Puestos de Trabajo",
        
        # Población
        "censo_ipecd_departamentos": "Población por Departamento",
        "censo_ipecd_municipios": "Población por Municipio",
        "base_poblacion_viviendas": "Población y Viviendas",
        "base_piramide": "Pirámide Poblacional",
        
        # Educación
        "base_asistencia_escolar": "Asistencia Escolar",
        "base_nivel_educativo": "Nivel Educativo",
        "clima_educativo": "Clima Educativo del Hogar",
        "ecv_educacion": "Educación - Encuesta de Condiciones de Vida",
        
        # Salud
        "base_cobertura_salud": "Cobertura de Salud",
        "censo_nea_nacion_cobertura_salud": "Cobertura de Salud NEA",
        
        # Vivienda
        "base_inmat": "Calidad de Vivienda (INMAT)",
        "base_material_piso": "Material de Piso",
        "base_propiedad_de_la_vivienda": "Propiedad de Vivienda",
        
        # Servicios
        "base_agua_beber_o_cocinar": "Acceso al Agua",
        "base_cloaca": "Servicio de Cloaca",
        "base_combustible_para_cocinar": "Combustible para Cocinar",
        "base_internet": "Acceso a Internet",
        
        # Comercio
        "canasta_basica": "Canasta Básica",
        "supermercado_deflactado": "Ventas de Supermercados",
        
        # Moneda
        "dolar_blue": "Dólar Blue",
        "dolar_ccl": "Dólar CCL",
        "dolar_mep": "Dólar MEP",
        "dolar_oficial": "Dólar Oficial",
        
        # Transporte
        "anac": "Tráfico Aéreo",
        "dnrpa": "Patentamiento de Vehículos",
    }
    
    # Categorías predefinidas y sus palabras clave
    CATEGORIES = {
        "pbg": {
            "keywords": ["pbg", "producto bruto geográfico", "producto bruto", "pbi", "producto interno bruto"],
            "icon": "📈",
            "description": "Producto Bruto Geográfico"
        },
        "inflacion": {
            "keywords": ["inflación", "inflacion", "ipc", "índice de precios", "indice de precios", "precios"],
            "icon": "💰",
            "description": "Inflación e Índices de Precios"
        },
        "empleo": {
            "keywords": ["empleo", "trabajo", "desempleo", "ocupación", "ocupacion", "puestos", "empleados"],
            "icon": "💼",
            "description": "Empleo y Ocupación"
        },
        "poblacion": {
            "keywords": ["población", "poblacion", "habitantes", "ciudadanos", "personas", "censo"],
            "icon": "👥",
            "description": "Población y Demografía"
        },
        "educacion": {
            "keywords": ["educación", "educacion", "escolaridad", "nivel educativo", "clima educativo"],
            "icon": "🎓",
            "description": "Educación"
        },
        "salud": {
            "keywords": ["salud", "cobertura", "obra social", "pami", "hospital"],
            "icon": "🏥",
            "description": "Salud y Cobertura"
        },
        "vivienda": {
            "keywords": ["vivienda", "hogar", "inmat", "calidad", "material"],
            "icon": "🏠",
            "description": "Vivienda e Infraestructura"
        },
        "servicios": {
            "keywords": ["agua", "cloaca", "combustible", "internet", "servicios básicos", "servicios basicos"],
            "icon": "⚡",
            "description": "Servicios Básicos"
        },
        "transporte": {
            "keywords": ["transporte", "vehículos", "vehiculos", "patentamiento", "dnrpa", "anac"],
            "icon": "🚗",
            "description": "Transporte y Vehículos"
        },
        "comercio": {
            "keywords": ["comercio", "supermercado", "facturación", "facturacion", "ventas", "canasta básica", "canasta basica"],
            "icon": "🛒",
            "description": "Comercio y Consumo"
        },
        "moneda": {
            "keywords": ["dólar", "dolar", "moneda", "tipo de cambio", "blue", "ccl"],
            "icon": "💵",
            "description": "Moneda y Tipo de Cambio"
        },
        "combustible": {
            "keywords": ["combustible", "nafta", "gasoil", "precio combustible"],
            "icon": "⛽",
            "description": "Combustibles"
        }
    }
    
    def __init__(self, db_client: Optional[DatabaseClient] = None):
        """Inicializar el generador de menú.
        
        Args:
            db_client: Cliente de base de datos
        """
        self.db_client = db_client
    
    def analyze_database_structure(self, use_cache: bool = True) -> Dict[str, List[Dict]]:
        """Analizar estructura de la base de datos y agrupar tablas por categorías.
        
        Args:
            use_cache: Si usar caché para evitar consultas repetidas
        
        Returns:
            Diccionario con categorías y sus tablas asociadas
        """
        global _categorized_tables_cache
        
        # Usar caché si está disponible
        if use_cache and _categorized_tables_cache is not None:
            logging.info("Using cached database structure")
            return _categorized_tables_cache
        
        if not self.db_client:
            logging.warning("No database client available for menu generation")
            return {}
        
        try:
            structure = self.db_client.get_database_structure()
            categorized_tables = defaultdict(list)
            
            # Limitar análisis a tablas más relevantes (primeras 50 por BD)
            for db_name, tables in structure.items():
                # Limitar número de tablas analizadas para mejorar rendimiento
                limited_tables = dict(list(tables.items())[:50])
                
                for table_name, table_info in limited_tables.items():
                    # Buscar categoría para esta tabla
                    category = self._categorize_table(table_name, table_info)
                    if category:
                        categorized_tables[category].append({
                            "db_name": db_name,
                            "table_name": table_name,
                            "columns": table_info.get('columns', []),
                            "sample": table_info.get('sample')
                        })
            
            result = dict(categorized_tables)
            
            # Guardar en caché
            if use_cache:
                _categorized_tables_cache = result
            
            logging.info(f"Analyzed database structure: {len(result)} categories found")
            return result
            
        except Exception as e:
            logging.error(f"Error analyzing database structure: {e}")
            return {}
    
    def _categorize_table(self, table_name: str, table_info: Dict) -> Optional[str]:
        """Categorizar una tabla basándose en su nombre y columnas.
        
        Args:
            table_name: Nombre de la tabla
            table_info: Información de la tabla (columnas, muestra)
            
        Returns:
            Nombre de la categoría o None
        """
        table_lower = table_name.lower()
        columns = [c.lower() for c in table_info.get('columns', [])]
        
        # Buscar coincidencias con categorías
        best_match = None
        best_score = 0
        
        for category, cat_info in self.CATEGORIES.items():
            score = 0
            
            # Verificar nombre de tabla
            for keyword in cat_info["keywords"]:
                if keyword in table_lower:
                    score += 10  # Alta puntuación para coincidencias en nombre
            
            # Verificar columnas
            for keyword in cat_info["keywords"]:
                if any(keyword in col for col in columns):
                    score += 5  # Media puntuación para coincidencias en columnas
            
            if score > best_score:
                best_score = score
                best_match = category
        
        # Solo retornar si hay una coincidencia significativa
        return best_match if best_score >= 5 else None
    
    def _get_friendly_name(self, table_name: str) -> str:
        """Convertir nombre técnico de tabla a nombre amigable.
        
        Args:
            table_name: Nombre técnico de la tabla
            
        Returns:
            Nombre amigable para mostrar al usuario
        """
        table_lower = table_name.lower()
        
        # Buscar coincidencia exacta primero
        if table_name in self.FRIENDLY_NAMES:
            return self.FRIENDLY_NAMES[table_name]
        
        # Buscar coincidencias parciales
        for tech_name, friendly_name in self.FRIENDLY_NAMES.items():
            if tech_name.lower() in table_lower or table_lower in tech_name.lower():
                return friendly_name
        
        # Si no hay coincidencia, crear nombre amigable desde el nombre técnico
        # Remover prefijos comunes
        friendly = table_name
        friendly = friendly.replace("base_", "")
        friendly = friendly.replace("censo_", "")
        friendly = friendly.replace("ecv_", "")
        friendly = friendly.replace("tabla_", "")
        friendly = friendly.replace("dp_", "")
        friendly = friendly.replace("dicc_", "")
        friendly = friendly.replace("dwh_", "")
        friendly = friendly.replace("datalake_", "")
        
        # Convertir guiones bajos a espacios y capitalizar
        friendly = friendly.replace("_", " ")
        friendly = " ".join(word.capitalize() for word in friendly.split())
        
        return friendly
    
    def generate_menu_nodes(self, limit_per_category: int = 10) -> List[MenuNode]:
        """Generar nodos de menú basados en la estructura de la base de datos.
        
        Args:
            limit_per_category: Límite de tablas por categoría para mejorar rendimiento
        
        Returns:
            Lista de nodos de menú generados
        """
        categorized_tables = self.analyze_database_structure()
        nodes = []
        
        # Crear nodos por categoría
        for category, tables in categorized_tables.items():
            if not tables:
                continue
            
            cat_info = self.CATEGORIES.get(category, {})
            icon = cat_info.get("icon", "📊")
            description = cat_info.get("description", category.title())
            
            # Limitar número de tablas por categoría
            limited_tables = tables[:limit_per_category]
            
            # Crear nodo de categoría
            category_node_id = f"cat_{category}"
            
            # Agrupar tablas por base de datos
            children_by_db = defaultdict(list)
            for table_info in limited_tables:
                db_name = table_info["db_name"]
                table_name = table_info["table_name"]
                
                # Crear nodo hijo para la tabla con nombre amigable
                table_node_id = f"{category_node_id}_{db_name}_{table_name}"
                friendly_name = self._get_friendly_name(table_name)
                
                table_node = MenuNode(
                    node_id=table_node_id,
                    title=friendly_name,  # Sin icono técnico, solo nombre amigable
                    description="",  # Sin descripción técnica
                    action="query",
                    db_query=f"{db_name}.{table_name}",
                    keywords=[table_name.lower(), db_name.lower()] + cat_info.get("keywords", [])
                )
                nodes.append(table_node)
                children_by_db[db_name].append(table_node_id)
            
            # Crear submenús por base de datos con nombres amigables
            category_children = []
            for db_name, table_ids in children_by_db.items():
                db_node_id = f"{category_node_id}_{db_name}"
                
                # Nombre amigable para la base de datos
                db_friendly_name = db_name.replace("datalake_", "").replace("dwh_", "").replace("_", " ").title()
                if "economico" in db_name.lower():
                    db_friendly_name = "Datos Económicos"
                elif "socio" in db_name.lower() or "sociodemografico" in db_name.lower():
                    db_friendly_name = "Datos Sociales"
                
                db_node = MenuNode(
                    node_id=db_node_id,
                    title=db_friendly_name,  # Nombre amigable sin iconos técnicos
                    description="",  # Sin descripción técnica
                    action="menu",
                    children=table_ids,
                    keywords=[db_name.lower()]
                )
                nodes.append(db_node)
                category_children.append(db_node_id)
            
            # Crear nodo de categoría con hijos de BD
            category_node = MenuNode(
                node_id=category_node_id,
                title=f"{icon} {description}",
                description="",  # Sin descripción técnica
                action="menu",
                children=category_children,
                keywords=cat_info.get("keywords", [])
            )
            nodes.append(category_node)
        
        return nodes
    
    def enhance_menu_tree(self, menu_tree: MenuTree) -> MenuTree:
        """Mejorar el árbol de menú existente con opciones dinámicas de la BD.
        
        Args:
            menu_tree: Árbol de menú existente
            
        Returns:
            Árbol de menú mejorado
        """
        if not self.db_client:
            return menu_tree
        
        # Generar nodos dinámicos
        dynamic_nodes = self.generate_menu_nodes()
        
        # Obtener nodos económicos y sociales existentes
        economico_node = menu_tree.get_node("economico")
        socio_node = menu_tree.get_node("socio")
        
        # Agregar categorías dinámicas a los nodos existentes
        economic_categories = []
        social_categories = []
        
        for node in dynamic_nodes:
            # Determinar si es económico o social basándose en las tablas asociadas
            is_economic = False
            is_social = False
            
            # Buscar en los hijos del nodo para ver qué bases de datos usa
            for child_id in node.children:
                child_node = menu_tree.get_node(child_id)
                if child_node and child_node.db_query:
                    if "economico" in child_node.db_query.lower():
                        is_economic = True
                    elif "socio" in child_node.db_query.lower():
                        is_social = True
            
            # Agregar nodo al árbol
            menu_tree.nodes[node.id] = node
            
            # Agregar a la categoría apropiada
            if is_economic and economico_node:
                economic_categories.append(node.id)
            elif is_social and socio_node:
                social_categories.append(node.id)
        
        # Actualizar hijos de nodos económicos y sociales (eliminando duplicados)
        if economico_node and economic_categories:
            # Agregar categorías dinámicas después de las opciones existentes, eliminando duplicados
            existing_children = economico_node.children.copy() if economico_node.children else []
            # Eliminar duplicados manteniendo el orden: primero los existentes, luego los nuevos
            seen = set(existing_children)
            new_categories = [cat for cat in economic_categories if cat not in seen]
            economico_node.children = existing_children + new_categories
        
        if socio_node and social_categories:
            existing_children = socio_node.children.copy() if socio_node.children else []
            # Eliminar duplicados manteniendo el orden
            seen = set(existing_children)
            new_categories = [cat for cat in social_categories if cat not in seen]
            socio_node.children = existing_children + new_categories
        
        # Guardar menú actualizado
        menu_tree.save_menu()
        
        logging.info(f"Enhanced menu tree with {len(dynamic_nodes)} dynamic nodes")
        return menu_tree

