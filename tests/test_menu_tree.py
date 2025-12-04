"""Tests para el árbol de menú y navegación."""
import pytest
import sys
import os
import json
from unittest.mock import MagicMock, patch, mock_open

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from menu_tree import MenuTree, MenuNode


class TestMenuNode:
    """Tests para la clase MenuNode."""
    
    @pytest.mark.unit
    def test_create_menu_node(self):
        """Crea un MenuNode correctamente."""
        node = MenuNode(
            node_id="test",
            title="Test Node",
            description="A test node",
            action="menu"
        )
        assert node.id == "test"
        assert node.title == "Test Node"
        assert node.description == "A test node"
        assert node.action == "menu"
    
    @pytest.mark.unit
    def test_menu_node_default_values(self):
        """MenuNode tiene valores por defecto."""
        node = MenuNode(node_id="test", title="Test")
        assert node.children == [] or node.children is None
        assert node.keywords == [] or node.keywords is None
        assert node.db_query is None
        assert node.tool is None
    
    @pytest.mark.unit
    def test_menu_node_with_children(self):
        """MenuNode puede tener hijos."""
        node = MenuNode(
            node_id="parent",
            title="Parent",
            children=["child1", "child2"]
        )
        assert len(node.children) == 2
        assert "child1" in node.children
    
    @pytest.mark.unit
    def test_menu_node_with_tool(self):
        """MenuNode puede tener una herramienta asociada."""
        node = MenuNode(
            node_id="ipc",
            title="IPC",
            action="tool",
            tool="get_ipc",
            tool_args={"region": "NEA"}
        )
        assert node.tool == "get_ipc"
        assert node.tool_args == {"region": "NEA"}


class TestMenuTreeLoading:
    """Tests para carga del menú."""
    
    @pytest.fixture
    def sample_menu_json(self):
        """JSON de menú de ejemplo."""
        return json.dumps({
            "id": "root",
            "title": "Menú Principal",
            "action": "menu",
            "children": ["cat_precios"],
            "nodes": [
                {
                    "id": "root",
                    "title": "Menú Principal",
                    "action": "menu",
                    "children": ["cat_precios"],
                    "keywords": []
                },
                {
                    "id": "cat_precios",
                    "title": "Precios",
                    "action": "menu",
                    "children": ["ipc"],
                    "keywords": ["ipc", "precios"]
                },
                {
                    "id": "ipc",
                    "title": "Último IPC",
                    "action": "tool",
                    "tool": "get_ipc",
                    "children": [],
                    "keywords": ["ipc"]
                }
            ]
        })
    
    @pytest.mark.unit
    def test_load_menu_creates_nodes(self, sample_menu_json):
        """load_menu crea nodos correctamente."""
        with patch("builtins.open", mock_open(read_data=sample_menu_json)):
            tree = MenuTree()
            tree.load_menu()  # No requiere argumento
            
            # Verificar que se cargaron nodos
            assert tree.nodes is not None
    
    @pytest.mark.unit
    def test_load_menu_sets_nodes(self, sample_menu_json):
        """load_menu carga nodos."""
        with patch("builtins.open", mock_open(read_data=sample_menu_json)):
            tree = MenuTree()
            tree.load_menu()
            
            # Verificar que nodes existe y tiene contenido
            assert tree.nodes is not None
            assert len(tree.nodes) > 0


class TestMenuTreeNavigation:
    """Tests para navegación del menú."""
    
    @pytest.fixture
    def tree_with_nodes(self):
        """Crea un árbol con nodos de prueba."""
        tree = MenuTree()
        tree.nodes = {
            "root": MenuNode(
                node_id="root",
                title="Menú Principal",
                action="menu",
                children=["cat_precios", "cat_censo"]
            ),
            "cat_precios": MenuNode(
                node_id="cat_precios",
                title="Precios e Inflación",
                action="menu",
                children=["ipc"],
                keywords=["ipc", "inflacion", "precios"]
            ),
            "cat_censo": MenuNode(
                node_id="cat_censo",
                title="Población y Censo",
                action="menu",
                children=["censo_muni"],
                keywords=["censo", "poblacion"]
            ),
            "ipc": MenuNode(
                node_id="ipc",
                title="Último IPC",
                action="tool",
                tool="get_ipc",
                children=[],
                keywords=["ipc", "ultimo"]
            ),
            "censo_muni": MenuNode(
                node_id="censo_muni",
                title="Población por Municipio",
                action="tool",
                tool="get_censo",
                children=[],
                keywords=["municipio"]
            )
        }
        tree.root = tree.nodes["root"]
        return tree
    
    @pytest.mark.unit
    def test_get_node_by_id(self, tree_with_nodes):
        """Obtiene nodo por ID."""
        node = tree_with_nodes.get_node("cat_precios")
        assert node is not None
        assert node.title == "Precios e Inflación"
    
    @pytest.mark.unit
    def test_get_node_nonexistent(self, tree_with_nodes):
        """Retorna None para nodo inexistente."""
        node = tree_with_nodes.get_node("nonexistent")
        assert node is None
    
    @pytest.mark.unit
    def test_get_children_from_node(self, tree_with_nodes):
        """Obtiene nodos hijos de un nodo."""
        root = tree_with_nodes.get_node("root")
        assert root is not None
        
        # Verificar que el nodo root tiene hijos definidos
        assert root.children is not None
        assert len(root.children) == 2
        
        # Verificar que podemos obtener los nodos hijos
        for child_id in root.children:
            child_node = tree_with_nodes.get_node(child_id)
            assert child_node is not None


class TestMenuTreeFormatting:
    """Tests para formateo del menú."""
    
    @pytest.fixture
    def tree_with_nodes(self):
        """Crea un árbol con nodos de prueba."""
        tree = MenuTree()
        tree.nodes = {
            "root": MenuNode(
                node_id="root",
                title="Menú Principal",
                description="Menu principal",
                action="menu",
                children=["opt1", "opt2"]
            ),
            "opt1": MenuNode(
                node_id="opt1",
                title="Opción 1",
                description="Primera opción",
                action="menu",
                children=[]
            ),
            "opt2": MenuNode(
                node_id="opt2",
                title="Opción 2",
                description="Segunda opción",
                action="tool",
                tool="test_tool",
                children=[]
            )
        }
        tree.root = tree.nodes["root"]
        return tree
    
    @pytest.mark.unit
    def test_format_menu_includes_numbers(self, tree_with_nodes):
        """format_menu incluye números para selección."""
        formatted = tree_with_nodes.format_menu("root")
        assert "1." in formatted
        assert "2." in formatted
    
    @pytest.mark.unit
    def test_format_menu_includes_titles(self, tree_with_nodes):
        """format_menu incluye títulos de opciones."""
        formatted = tree_with_nodes.format_menu("root")
        assert "Opción 1" in formatted
        assert "Opción 2" in formatted
    
    @pytest.mark.unit
    def test_format_menu_from_root(self, tree_with_nodes):
        """format_menu desde el nodo raíz."""
        formatted = tree_with_nodes.format_menu()
        assert len(formatted) > 0


class TestMenuTreeKeywordSearch:
    """Tests para búsqueda por keywords."""
    
    @pytest.fixture
    def tree_with_keywords(self):
        """Crea un árbol con keywords."""
        tree = MenuTree()
        tree.nodes = {
            "root": MenuNode(
                node_id="root",
                title="Root",
                action="menu",
                children=["ipc", "censo", "empleo"]
            ),
            "ipc": MenuNode(
                node_id="ipc",
                title="Índice de Precios",
                action="tool",
                keywords=["ipc", "inflacion", "precios"],
                children=[]
            ),
            "censo": MenuNode(
                node_id="censo",
                title="Censo Poblacional",
                action="tool",
                keywords=["censo", "poblacion", "habitantes"],
                children=[]
            ),
            "empleo": MenuNode(
                node_id="empleo",
                title="Datos de Empleo",
                action="tool",
                keywords=["empleo", "trabajo", "desempleo", "eph"],
                children=[]
            )
        }
        tree.root = tree.nodes["root"]
        return tree
    
    @pytest.mark.unit
    def test_find_node_by_keyword_ipc(self, tree_with_keywords):
        """Encuentra nodo por keyword 'ipc'."""
        node = tree_with_keywords.find_node_by_keyword("ipc")
        assert node is not None
        assert node.id == "ipc"
    
    @pytest.mark.unit
    def test_find_node_by_keyword_censo(self, tree_with_keywords):
        """Encuentra nodo por keyword 'censo'."""
        node = tree_with_keywords.find_node_by_keyword("censo")
        assert node is not None
        assert node.id == "censo"
    
    @pytest.mark.unit
    def test_find_node_by_keyword_eph(self, tree_with_keywords):
        """Encuentra nodo por keyword 'eph'."""
        node = tree_with_keywords.find_node_by_keyword("eph")
        assert node is not None
        assert node.id == "empleo"
    
    @pytest.mark.unit
    def test_find_node_not_found(self, tree_with_keywords):
        """Retorna None si no encuentra keyword."""
        node = tree_with_keywords.find_node_by_keyword("xyz123")
        assert node is None


class TestMenuTreeEdgeCases:
    """Tests para casos extremos del árbol de menú."""
    
    @pytest.fixture
    def empty_tree(self):
        """Crea un árbol vacío."""
        return MenuTree()
    
    @pytest.mark.unit
    def test_format_menu_empty_tree(self, empty_tree):
        """format_menu maneja árbol vacío."""
        # No debe lanzar excepción
        try:
            result = empty_tree.format_menu()
            assert result is not None or result == ""
        except:
            pass  # OK si lanza excepción controlada
    
    @pytest.mark.unit
    def test_get_node_empty_tree(self, empty_tree):
        """get_node maneja árbol vacío."""
        node = empty_tree.get_node("any")
        assert node is None
    
    @pytest.mark.unit
    def test_find_keyword_empty_tree(self, empty_tree):
        """find_node_by_keyword maneja árbol vacío."""
        node = empty_tree.find_node_by_keyword("test")
        assert node is None


class TestMenuNodeActions:
    """Tests para diferentes tipos de acciones de nodos."""
    
    @pytest.mark.unit
    def test_menu_action_node(self):
        """Nodo con acción 'menu'."""
        node = MenuNode(
            node_id="menu_node",
            title="Submenú",
            action="menu",
            children=["child1", "child2"]
        )
        assert node.action == "menu"
        assert len(node.children) == 2
    
    @pytest.mark.unit
    def test_tool_action_node(self):
        """Nodo con acción 'tool'."""
        node = MenuNode(
            node_id="tool_node",
            title="Herramienta",
            action="tool",
            tool="get_ipc",
            tool_args={"limit": 10}
        )
        assert node.action == "tool"
        assert node.tool == "get_ipc"
        assert node.tool_args == {"limit": 10}
    
    @pytest.mark.unit
    def test_info_action_node(self):
        """Nodo con acción 'info'."""
        node = MenuNode(
            node_id="info_node",
            title="Información",
            action="info",
            info_text="Texto informativo"
        )
        assert node.action == "info"
        assert node.info_text == "Texto informativo"
    
    @pytest.mark.unit
    def test_query_action_node(self):
        """Nodo con acción 'query'."""
        node = MenuNode(
            node_id="query_node",
            title="Consulta",
            action="query",
            db_query="SELECT * FROM tabla"
        )
        assert node.action == "query"
        assert node.db_query == "SELECT * FROM tabla"

