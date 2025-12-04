"""API REST para el chatbot MCP usando FastAPI."""
import asyncio
import logging
import re
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os

from chat_session import ChatSession
from config import Configuration
from context_manager import (
    get_session_context, detect_category, should_reset_context,
    create_context_aware_messages, get_category_system_prompt
)
from database import DatabaseClient
from keyword_detector import KeywordDetector
from llm_clients import LLMClient, OpenAIClient
from menu_generator import MenuGenerator
from menu_tree import MenuTree
from mcp_server import Server
from mcp_tools_server import DatabaseTools
from query_processor import QueryProcessor
from related_options_finder import RelatedOptionsFinder
from tool_executor import ToolExecutor
from intent_classifier import is_conceptual_question, get_topic_from_query, is_domain_relevant, is_complex_query
from query_router import QueryRouter
from llm_intent_classifier import classify_user_intent, get_intent_classifier
from response_enricher import enrich_data_response
from learning_memory import get_learning_memory, LearningMemory
from web_search import WebSearchClient, WebSearchWithSerpAPI

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Variable global para almacenar la sesión de chat
chat_session: Optional[ChatSession] = None
chat_messages: Dict[str, List[Dict]] = {}  # Almacena mensajes por sesión
menu_states: Dict[str, Dict[str, any]] = {}  # Almacena estado del menú por sesión

# Herramientas de base de datos (para ejecutar tools del menú)
db_tools: Optional[DatabaseTools] = None
tool_executor: Optional[ToolExecutor] = None
openai_client_global: Optional[Any] = None  # Cliente OpenAI global para clasificación

# Sistema de memoria y aprendizaje
learning_memory: Optional[LearningMemory] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicación."""
    global chat_session, db_tools, tool_executor, learning_memory, openai_client_global
    
    # Inicialización
    config = Configuration()
    server_config = config.load_config('servers_config.json')
    servers = []
    try:
        servers = [Server(name, srv_config) for name, srv_config in server_config['mcpServers'].items()]
    except Exception as e:
        logging.warning(f"Could not initialize MCP servers: {e}")
        logging.warning("Continuing without MCP servers - menu and database functionality will work")
    llm_client = LLMClient(config.llm_api_key)
    
    # Crear cliente de base de datos MySQL si está configurado
    db_client = None
    if config.has_database_config:
        try:
            db_client = DatabaseClient(
                host=config.db_host,
                port=config.db_port,
                user=config.db_user,
                password=config.db_password,
                databases=config.db_databases
            )
            logging.info(f"MySQL database client initialized for host: {config.db_host}")
        except Exception as e:
            logging.error(f"Error initializing database client: {e}")
    
    # Crear cliente OpenAI como fallback si está disponible
    openai_client = None
    openai_client_global = None
    if config.has_openai_key:
        openai_client = OpenAIClient(config.openai_api_key)
        openai_client_global = openai_client  # Guardar referencia global
        logging.info("OpenAI client initialized as fallback")
    
    # Crear cliente de búsqueda web
    web_search_client = None
    if config.has_openai_key:
        web_search_client = WebSearchClient(config.openai_api_key)
        logging.info("Web search client initialized")
    else:
        web_search_client = WebSearchClient(None)
    
    # Crear cliente SerpAPI si está disponible
    serp_api_client = None
    if config.has_serp_api_key:
        serp_api_client = WebSearchWithSerpAPI(config.serp_api_key)
        logging.info("SerpAPI client initialized")
    
    # Inicializar servidores (con timeout para evitar bloqueos)
    for server in servers:
        try:
            # Intentar inicializar con timeout implícito
            await asyncio.wait_for(server.initialize(), timeout=5.0)
        except asyncio.TimeoutError:
            logging.warning(f"Timeout initializing server {server.name}, skipping")
        except Exception as e:
            logging.warning(f"Failed to initialize server {server.name}: {e}")
            logging.warning("Continuing without MCP servers - basic functionality will work")
    
    chat_session = ChatSession(servers, llm_client, openai_client, db_client)
    
    # Inicializar herramientas de base de datos
    try:
        db_tools = DatabaseTools()
        tool_executor = ToolExecutor(db_tools)
        logging.info("DatabaseTools and ToolExecutor initialized")
    except Exception as e:
        logging.warning(f"Could not initialize DatabaseTools: {e}")
        db_tools = None
        tool_executor = ToolExecutor(None)
    
    # Inicializar sistema de memoria y aprendizaje (usa MySQL)
    if config.has_database_config:
        learning_memory = get_learning_memory(
            host=config.db_host,
            port=config.db_port,
            user=config.db_user,
            password=config.db_password
        )
        if learning_memory:
            stats = learning_memory.get_stats()
            logging.info(f"Learning memory (MySQL) initialized with {stats.get('total_entries', 0)} entries")
        else:
            logging.warning("Learning memory could not be initialized")
    else:
        logging.warning("No database config - learning memory disabled")
    
    logging.info("API initialization complete, server ready")
    yield
    
    # Cleanup
    if chat_session:
        await chat_session.cleanup_servers()


app = FastAPI(title="MCP Chatbot API", lifespan=lifespan)

# Configurar CORS para permitir requests del frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar el dominio del frontend
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "PUT", "DELETE"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Servir archivos estáticos del frontend
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
async def serve_frontend():
    """Sirve el frontend principal."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "MCP Chatbot API", "docs": "/docs"}


class ChatMessage(BaseModel):
    """Modelo para mensajes del chat."""
    message: str
    session_id: Optional[str] = "default"


class ChatResponse(BaseModel):
    """Modelo para respuestas del chat."""
    response: str
    session_id: str


class ToolRequest(BaseModel):
    """Modelo para ejecución directa de herramientas."""
    tool: str
    args: Optional[Dict] = {}
    session_id: Optional[str] = "default"


class ToolResponse(BaseModel):
    """Modelo para respuesta de herramientas."""
    response: str
    session_id: str
    tool: str


def save_to_memory(question: str, response: str, category: str = None, is_conceptual: bool = False) -> None:
    """
    Guarda una interacción en la memoria aprendida.
    Solo guarda respuestas exitosas (no errores, no menús, solo preguntas del dominio).
    """
    if not learning_memory:
        return
    
    # No guardar preguntas fuera del dominio del IPECD
    if not is_domain_relevant(question):
        logging.info(f"Not saving to memory (out of domain): {question[:50]}...")
        return
    
    # No guardar respuestas cortas o menús
    if len(response) < 100:
        return
    
    # No guardar si es un menú
    if response.startswith("1.") or "└─" in response[:200]:
        return
    
    # No guardar errores
    if "error" in response.lower()[:100] or "lo siento" in response.lower()[:50]:
        return
    
    try:
        learning_memory.learn(
            question=question,
            response=response,
            category=category,
            is_conceptual=is_conceptual,
            quality_score=0.8  # Puntuación base
        )
        logging.info(f"Saved to learning memory: {question[:50]}...")
    except Exception as e:
        logging.warning(f"Could not save to learning memory: {e}")


@app.get("/")
async def root():
    """Endpoint raíz."""
    return {"message": "MCP Chatbot API", "status": "running"}


@app.get("/api/memory/stats")
async def memory_stats():
    """Endpoint para ver estadísticas de la memoria aprendida."""
    if not learning_memory:
        return {"error": "Learning memory not initialized"}
    
    stats = learning_memory.get_stats()
    return {
        "status": "ok",
        "learning_memory": stats
    }


@app.get("/api/memory/suggestions")
async def memory_suggestions(q: str = ""):
    """Endpoint para obtener sugerencias basadas en texto parcial."""
    if not learning_memory or not q:
        return {"suggestions": []}
    
    suggestions = learning_memory.get_suggestions(q, limit=5)
    return {"suggestions": suggestions}


@app.get("/api/memory/recent")
async def memory_recent(limit: int = 20):
    """Endpoint para ver las entradas recientes de la memoria."""
    if not learning_memory:
        return {"error": "Learning memory not initialized", "entries": []}
    
    entries = learning_memory.get_recent_entries(limit=min(limit, 100))
    return {
        "status": "ok",
        "count": len(entries),
        "entries": entries
    }


@app.get("/api/memory/export")
async def memory_export():
    """Exporta los datos de aprendizaje para entrenamiento."""
    if not learning_memory:
        return {"error": "Learning memory not initialized", "data": []}
    
    data = learning_memory.export_for_training()
    return {
        "status": "ok",
        "count": len(data),
        "data": data
    }


@app.post("/api/tool", response_model=ToolResponse)
async def tool_endpoint(tool_request: ToolRequest):
    """Endpoint para ejecutar herramientas directamente (sin pasar por el LLM)."""
    global tool_executor
    
    try:
        tool_name = tool_request.tool
        args = tool_request.args or {}
        session_id = tool_request.session_id or "default"
        
        logging.info(f"Direct tool execution: {tool_name} with args {args}")
        
        if not tool_executor or not tool_executor.is_available():
            return ToolResponse(
                response="Lo siento, las herramientas no están disponibles en este momento.",
                session_id=session_id,
                tool=tool_name
            )
        
        # Ejecutar la herramienta directamente
        result = tool_executor.execute(tool_name, args)
        
        return ToolResponse(
            response=result,
            session_id=session_id,
            tool=tool_name
        )
        
    except Exception as e:
        logging.error(f"Error executing tool {tool_request.tool}: {e}")
        return ToolResponse(
            response=f"Lo siento, hubo un error al ejecutar la consulta.",
            session_id=tool_request.session_id or "default",
            tool=tool_request.tool
        )


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(chat_message: ChatMessage):
    """Endpoint para enviar mensajes al chatbot."""
    global chat_session, chat_messages, menu_states, openai_client_global
    
    try:
        logging.info(f"Received chat request: session_id={chat_message.session_id}, message_length={len(chat_message.message) if chat_message.message else 0}")
    except Exception as e:
        logging.error(f"Error logging request: {e}")
    
    if not chat_session:
        logging.error("Chat session not initialized")
        raise HTTPException(status_code=503, detail="Chat session not initialized")
    
    session_id = chat_message.session_id or "default"
    
    # Inicializar menú tree y keyword detector para esta sesión si no existen
    if session_id not in menu_states:
        menu_tree = MenuTree()
        
        # Cargar menú básico primero (rápido)
        # El menú mejorado se cargará de forma lazy cuando se acceda a categorías específicas
        
        menu_states[session_id] = {
            "menu_tree": menu_tree,
            "keyword_detector": None,
            "current_menu_node_id": None,
            "menu_history": [],
            "menu_enhanced": False  # Flag para saber si ya se mejoró el menú
        }
        menu_states[session_id]["keyword_detector"] = KeywordDetector(
            menu_states[session_id]["menu_tree"],
            db_client=chat_session.db_client if chat_session else None
        )
    
    menu_state = menu_states[session_id]
    menu_tree = menu_state["menu_tree"]
    keyword_detector = menu_state["keyword_detector"]
    
    # Inicializar mensajes de la sesión si no existen
    if session_id not in chat_messages:
        # Obtener herramientas disponibles
        all_tools = []
        if chat_session and chat_session.servers:
            for server in chat_session.servers:
                try:
                    tools = await server.list_tools()
                    all_tools.extend(tools)
                except Exception as e:
                    logging.warning(f"Could not list tools from server {server.name}: {e}")
        
        tools_description = "\n".join([tool.format_for_llm() for tool in all_tools])
        
        # Determinar si hay acceso a base de datos
        has_db_access = chat_session.db_client is not None or any(
            any(keyword in tool.name.lower() for keyword in ['sql', 'query', 'database', 'db', 'table'])
            for server in chat_session.servers
            for tool in all_tools
        )
        
        db_instruction = ""
        web_instruction = ""
        
        if has_db_access:
            db_instruction = """
CRITICAL: Tienes acceso a una base de datos. Cuando se proporcionen resultados de búsqueda en la base de datos en el contexto del sistema:

1. SIEMPRE usa la información de la base de datos directamente - ya ha sido buscada por ti
2. Presenta los datos de manera clara y completa - NO digas que vas a buscar o buscar información
3. Si el usuario pregunta por "último valor" o "último", muestra los datos más recientes de los resultados
4. Formatea la información de manera clara y legible (tablas, listas, etc.)
5. Si se proporciona información de la base de datos, úsala inmediatamente - no ofrezcas buscar

La búsqueda en la base de datos ya se ha realizado. Tu trabajo es presentar los resultados claramente al usuario.
"""
        
        # NO usar búsqueda web - solo base de datos
            web_instruction = """
IMPORTANTE: SOLO tienes acceso a la base de datos del IPECD. NO uses búsqueda web ni fuentes externas.
Si la información no se encuentra en la base de datos, informa al usuario de manera amigable que los datos no están disponibles en nuestra base de datos.
NUNCA uses información de internet, Google, o cualquier otra fuente externa.
"""
        
        system_message = f"""Eres un asistente amigable del IPECD (Instituto Provincial de Estadística y Censos de Corrientes). Tu trabajo es ayudar a usuarios comunes (no técnicos) a entender información estadística de manera simple y clara.

REGLAS CRÍTICAS:
- NUNCA menciones nombres de tablas, columnas, bases de datos o cualquier detalle técnico.
- Presenta SOLO la información estadística concreta y los datos numéricos.
- Responde de manera amigable y conversacional, como si fueras un analista presentando estadísticas a una audiencia general.
- Formatea los números de manera clara (separadores de miles, porcentajes, etc.).
- NO digas "en la tabla X" o "en la columna Y", simplemente presenta los datos directamente.
- Si hay múltiples registros, presenta los datos más relevantes o recientes primero.

⚠️ REGLA IMPORTANTE - NO MEZCLAR TEMAS:
- Cada vez que el usuario cambie de tema, OLVIDA la información anterior.
- Si el usuario pregunta por DÓLAR, responde SOLO sobre dólar - NO menciones IPC, censo, empleo, etc.
- Si el usuario pregunta por IPC/INFLACIÓN, responde SOLO sobre precios - NO menciones dólar, censo, empleo, etc.
- Si el usuario pregunta por EMPLEO, responde SOLO sobre empleo - NO menciones dólar, IPC, censo, etc.
- Si el usuario pregunta por CENSO/POBLACIÓN, responde SOLO sobre demografía - NO menciones dólar, IPC, empleo, etc.
- NUNCA mezcles información de temas diferentes en una misma respuesta.
- Si cambió el tema, NO hagas referencia a datos anteriores de otros temas.

{tools_description}
{db_instruction}
{web_instruction}

INSTRUCCIONES CRÍTICAS PARA RESPUESTAS:

1. **Lenguaje simple y accesible**:
   - Habla como si le explicaras a una persona sin conocimientos técnicos
   - Evita términos técnicos complejos (API, endpoints, JSON, etc.)
   - Si debes mencionar algo técnico, explícalo en palabras simples
   - Usa ejemplos de la vida cotidiana cuando sea posible

2. **Formato de respuestas - CRÍTICO PARA LEGIBILIDAD**:
   - Usa lenguaje conversacional y amigable
   - Organiza la información de manera clara con títulos (##, ###) y listas
   - Destaca los datos más importantes con negritas (**texto**)
   - Usa tablas markdown SOLO cuando muestres datos comparativos o estructurados
   - Las tablas deben ser simples: máximo 4 columnas, con encabezados claros
   - Usa listas con viñetas (-) para explicar conceptos o pasos
   - Separa los párrafos con líneas en blanco para mejor legibilidad
   - Usa citas (>) para notas importantes o aclaraciones
   - Evita tablas muy largas o complejas - mejor usa listas o párrafos explicativos

3. **Cuando recibas resultados de la base de datos**:
   - Explica QUÉ significan los datos en términos simples
   - NO menciones detalles técnicos como "endpoints", "API", "JSON", "GET", etc.
   - En lugar de decir "usa el endpoint GET /dwh/social", di "puedes encontrar estos datos en nuestra página web"
   - Si hay datos disponibles, muestra los valores más importantes de forma clara
   - Explica para qué sirve cada dato

4. **Ejemplos de cómo NO responder**:
   ❌ "Utiliza los endpoints GET /dwh/social/{{tema}}"
   ❌ "Respuesta (JSON simplificado):"
   ❌ "API: Utiliza los endpoints..."
   
   ✅ "Puedes encontrar información sobre empleo en nuestra página de datos sociales"
   ✅ "Los datos muestran que en diciembre de 2023 había 120,000 empleados"
   ✅ "Si necesitas más información, puedes consultar nuestra página web"

5. **Cuando uses herramientas**:
   - Responde SOLO con el JSON exacto si necesitas usar una herramienta:
{{
    "tool": "tool-name",
    "arguments": {{
        "argument-name": "value"
    }}
}}
   - Si no necesitas herramientas, responde directamente

6. **Optimización de respuestas**:
   - Enfócate en responder la pregunta del usuario de forma directa
   - Si hay muchos datos, muestra los más relevantes primero (máximo 5-7 filas en tablas)
   - Explica qué significan los números en términos que cualquiera pueda entender
   - Evita información técnica innecesaria
   - Estructura la respuesta así:
     * Título principal con ##
     * Breve explicación del concepto (2-3 líneas)
     * Datos en tabla o lista (si aplica)
     * Explicación de qué significan los datos
     * Nota final si es necesario (usando >)

IMPORTANTE: Tu audiencia son ciudadanos comunes que buscan información estadística. No necesitan saber sobre APIs, endpoints o formatos técnicos. Solo quieren entender los datos de forma simple."""

        chat_messages[session_id] = [
            {
                "role": "system",
                "content": system_message
            }
        ]
    
        # Inicializar estado del menú
        menu_state["current_menu_node_id"] = "root"
        menu_state["menu_history"] = ["root"]
    
    user_input = chat_message.message.strip() if chat_message.message else ""
    
    try:
        # Si el mensaje está vacío, mostrar menú inicial
        is_first_message = len(chat_messages[session_id]) == 1  # Solo tiene el system message
        is_empty_message = not user_input or user_input == ""
        
        logging.info(f"Session {session_id}: is_first_message={is_first_message}, is_empty_message={is_empty_message}, user_input='{user_input}'")
        
        # SOLO mostrar menú si el mensaje está vacío (no si es primer mensaje con contenido)
        if is_empty_message:
            try:
                initial_menu = menu_tree.format_menu()
                logging.info(f"Initial menu formatted: {initial_menu[:100]}...")  # Log primeros 100 chars
                
                if not initial_menu or initial_menu.strip() == "":
                    logging.warning("Empty menu returned, using default")
                    initial_menu = "1. 📊 Datos Económicos\n2. 👥 Datos Sociales\n3. ℹ️ Información General"
                
                if is_first_message:
                    chat_messages[session_id].append({
                        "role": "assistant",
                        "content": initial_menu
                    })
                return ChatResponse(response=initial_menu, session_id=session_id)
            except Exception as e:
                logging.error(f"Error formatting initial menu: {e}", exc_info=True)
                # Fallback a menú básico
                fallback_menu = "1. 📊 Datos Económicos\n2. 👥 Datos Sociales\n3. ℹ️ Información General"
                return ChatResponse(response=fallback_menu, session_id=session_id)
        
        # Detectar si el usuario quiere volver al menú principal
        menu_keywords = ["menu", "menú", "volver", "inicio", "principal", "atras", "atrás", "back"]
        if user_input.lower().strip() in menu_keywords:
            # Limpiar contexto al volver al menú
            session_context = get_session_context(session_id)
            session_context.reset_for_new_topic()
            session_context.current_category = None
            
            # Limpiar mensajes excepto system message
            if session_id in chat_messages and len(chat_messages[session_id]) > 1:
                system_msg = chat_messages[session_id][0]
                chat_messages[session_id] = [system_msg]
            
            # Volver al menú raíz
            menu_state["current_menu_node_id"] = "root"
            menu_state["menu_history"] = ["root"]
            
            try:
                initial_menu = menu_tree.format_menu("root")
                initial_menu = "👋 ¡Hola de nuevo! ¿En qué puedo ayudarte?\n\n" + initial_menu
                chat_messages[session_id].append({"role": "assistant", "content": initial_menu})
                return ChatResponse(response=initial_menu, session_id=session_id)
            except Exception as e:
                logging.error(f"Error formatting menu: {e}")
                fallback = "1. 📊 Datos Económicos\n2. 👥 Datos Sociales\n3. ℹ️ Información General"
                return ChatResponse(response=fallback, session_id=session_id)
        
        # ============================================================
        # SELECCIÓN NUMÉRICA DE MENÚ (procesar ANTES del clasificador LLM)
        # ============================================================
        # Si el usuario ingresa un número, es selección de menú
        if user_input.strip().isdigit():
            option_number = int(user_input.strip())
            current_node_id = menu_state.get("current_menu_node_id", "root")
            current_node = menu_tree.get_node(current_node_id)
            
            if current_node and current_node.children:
                child_node = menu_tree.get_child_by_number(current_node_id, option_number)
                if child_node:
                    logging.info(f"Menu selection: {option_number} -> {child_node.id}")
                    
                    if child_node.action == "menu":
                        menu_text = menu_tree.format_menu(child_node.id)
                        menu_state["current_menu_node_id"] = child_node.id
                        if child_node.id not in menu_state["menu_history"]:
                            menu_state["menu_history"].append(child_node.id)
                        chat_messages[session_id].append({"role": "user", "content": user_input})
                        chat_messages[session_id].append({"role": "assistant", "content": menu_text})
                        return ChatResponse(response=menu_text, session_id=session_id)
                    
                    elif child_node.action == "tool" and child_node.tool and tool_executor and tool_executor.is_available():
                        result = tool_executor.execute(child_node.tool, child_node.tool_args or {})
                        # Enriquecer respuesta si hay cliente LLM
                        if chat_session and chat_session.openai_client:
                            result = enrich_data_response(result, child_node.title or user_input, chat_session.openai_client)
                        chat_messages[session_id].append({"role": "user", "content": user_input})
                        chat_messages[session_id].append({"role": "assistant", "content": result})
                        return ChatResponse(response=result, session_id=session_id, tool=child_node.tool)
                    
                    elif child_node.action == "info" and child_node.info_text:
                        result = child_node.info_text
                        chat_messages[session_id].append({"role": "user", "content": user_input})
                        chat_messages[session_id].append({"role": "assistant", "content": result})
                        return ChatResponse(response=result, session_id=session_id)
            
            # Si el número no corresponde a ninguna opción válida
            invalid_msg = f"Opción {option_number} no válida. Por favor, elige una opción del menú."
            chat_messages[session_id].append({"role": "user", "content": user_input})
            chat_messages[session_id].append({"role": "assistant", "content": invalid_msg})
            return ChatResponse(response=invalid_msg, session_id=session_id)
        
        # ============================================================
        # BÚSQUEDA POR TEXTO EN MENÚ (antes del clasificador LLM)
        # ============================================================
        # Si el usuario escribe el título/descripción de una opción del menú, ejecutarla
        matched_menu_node = menu_tree.find_node_by_keyword(user_input)
        if matched_menu_node:
            logging.info(f"Menu text search matched: {matched_menu_node.title} (action: {matched_menu_node.action})")
            
            # Si es una herramienta, ejecutarla directamente
            if matched_menu_node.action == "tool" and matched_menu_node.tool:
                if tool_executor and tool_executor.is_available():
                    result = tool_executor.execute(matched_menu_node.tool, matched_menu_node.tool_args or {})
                    # Enriquecer respuesta con contexto usando LLM si está disponible
                    if chat_session and chat_session.openai_client:
                        result = enrich_data_response(result, user_input, chat_session.openai_client)
                    chat_messages[session_id].append({"role": "user", "content": user_input})
                    chat_messages[session_id].append({"role": "assistant", "content": result})
                    return ChatResponse(response=result, session_id=session_id, tool=matched_menu_node.tool)
            
            # Si es un menú, navegar a él y mostrar opciones
            elif matched_menu_node.action == "menu":
                menu_text = menu_tree.format_menu(matched_menu_node.id)
                menu_state["current_menu_node_id"] = matched_menu_node.id
                if matched_menu_node.id not in menu_state["menu_history"]:
                    menu_state["menu_history"].append(matched_menu_node.id)
                chat_messages[session_id].append({"role": "user", "content": user_input})
                chat_messages[session_id].append({"role": "assistant", "content": menu_text})
                return ChatResponse(response=menu_text, session_id=session_id)
            
            # Si es info, mostrar el texto informativo
            elif matched_menu_node.action == "info" and matched_menu_node.info_text:
                result = matched_menu_node.info_text
                chat_messages[session_id].append({"role": "user", "content": user_input})
                chat_messages[session_id].append({"role": "assistant", "content": result})
                return ChatResponse(response=result, session_id=session_id)
        
        # ============================================================
        # CLASIFICACIÓN DE INTENCIÓN USANDO LLM (más escalable)
        # ============================================================
        # Usar el clasificador LLM para entender la intención del usuario
        # Intentar obtener cliente OpenAI: primero del chat_session, luego global
        llm_client_for_intent = None
        if chat_session and chat_session.openai_client:
            llm_client_for_intent = chat_session.openai_client
        elif openai_client_global:
            llm_client_for_intent = openai_client_global
        
        intent_result = classify_user_intent(user_input, llm_client_for_intent)
        user_intent = intent_result.get("intencion", "consulta_datos")
        intent_confidence = intent_result.get("confianza", 0.5)
        
        logging.info(f"LLM Intent: {user_intent} (confidence: {intent_confidence}) for: {user_input[:50]}")
        
        # Manejar según la intención clasificada
        if user_intent == "saludo":
            # Detectar si también pregunta qué puede hacer
            asks_capabilities = any(word in user_input.lower() for word in ['podes', 'puedes', 'hacer', 'haces', 'ayudar', 'servir', 'funciona', 'sabes', 'capaz', 'capacidad'])
            
            if asks_capabilities:
                # Respuesta más completa si pregunta sobre capacidades
                welcome_response = """¡Hola! 👋 Soy el asistente virtual del **Instituto Provincial de Estadística y Censos de Corrientes** (IPECD).

**¿Qué puedo hacer por vos?**

📈 **Datos económicos** - IPC, inflación, cotización del dólar (blue, oficial, MEP), canasta básica, semáforo económico.

👔 **Empleo** - Tasas de empleo/desempleo (EPH), empleo registrado (SIPA), Encuesta de Calidad de Vida.

👥 **Demografía** - Población por municipio según censos, comparativas entre localidades.

**Ejemplos de preguntas:**
- _"¿Cuántos habitantes tiene Goya?"_
- _"Dame la cotización del dólar"_
- _"¿Cuál es la tasa de desempleo?"_

¿Qué necesitás saber?"""
            else:
                # Saludo simple
                welcome_response = """👋 ¡Hola! Soy el asistente del **IPECD** (Instituto Provincial de Estadística y Censos de Corrientes).

Puedo ayudarte con información sobre:
- 📈 Precios, inflación y dólar
- 👔 Empleo y trabajo
- 👥 Población y censo

¿En qué te puedo ayudar?"""
            
            chat_messages[session_id].append({"role": "user", "content": user_input})
            chat_messages[session_id].append({"role": "assistant", "content": welcome_response})
            return ChatResponse(response=welcome_response, session_id=session_id)
        
        if user_intent == "despedida":
            farewell_response = "😊 ¡De nada! Fue un placer ayudarte.\n\n"
            farewell_response += "Si necesitas más información sobre estadísticas de Corrientes, estaré aquí para ayudarte.\n\n"
            farewell_response += "¡Hasta pronto! 👋"
            chat_messages[session_id].append({"role": "user", "content": user_input})
            chat_messages[session_id].append({"role": "assistant", "content": farewell_response})
            return ChatResponse(response=farewell_response, session_id=session_id)
        
        if user_intent == "ayuda":
            # Respuesta conversacional y natural sobre capacidades
            help_response = """¡Hola! 👋 Soy el asistente virtual del **Instituto Provincial de Estadística y Censos de Corrientes** (IPECD).

**¿Qué puedo hacer por vos?**

📈 **Consultarte datos económicos** - Te puedo dar información sobre el IPC (inflación), cotización del dólar (blue, oficial, MEP), la canasta básica, y el semáforo económico de Corrientes.

👔 **Información sobre empleo** - Tasas de empleo y desempleo de la EPH, datos del SIPA sobre empleo registrado, y la Encuesta de Calidad de Vida.

👥 **Datos demográficos** - Población por municipio y departamento según los censos, comparativas entre localidades.

🔍 **Hacer comparaciones** - Podés pedirme que compare datos entre distintas localidades o períodos de tiempo.

**Ejemplos de preguntas que puedo responder:**
- _"¿Cuántos habitantes tiene Goya?"_
- _"Dame la cotización del dólar blue"_
- _"Comparar población de Corrientes y Resistencia"_
- _"¿Cuál es la tasa de desempleo?"_

¿En qué te puedo ayudar hoy?"""
            chat_messages[session_id].append({"role": "user", "content": user_input})
            chat_messages[session_id].append({"role": "assistant", "content": help_response})
            return ChatResponse(response=help_response, session_id=session_id)
        
        if user_intent == "fuera_de_dominio":
            logging.info(f"Query outside domain: {user_input[:50]}...")
            out_of_domain_response = """Lo siento, pero solo puedo ayudarte con información estadística del IPECD (Instituto Provincial de Estadística y Censos de Corrientes).

Puedo ayudarte con:
- 📊 **Precios e Inflación** (IPC, canasta básica)
- 💵 **Cotización del Dólar** (blue, oficial, MEP, CCL)
- 👔 **Empleo y Trabajo** (EPH, SIPA, tasas de empleo)
- 🚦 **Semáforo Económico** (indicadores de Corrientes)
- 👥 **Población y Censo** (datos demográficos)

¿En qué tema puedo ayudarte?"""
            chat_messages[session_id].append({"role": "user", "content": user_input})
            chat_messages[session_id].append({"role": "assistant", "content": out_of_domain_response})
            return ChatResponse(response=out_of_domain_response, session_id=session_id)
        
        # SISTEMA DE MEMORIA APRENDIDA: Buscar respuesta similar antes de procesar
        if learning_memory and not user_input.isdigit() and is_domain_relevant(user_input):
            learned_response = learning_memory.get_response(user_input)
            if learned_response:
                logging.info(f"Found learned response for: {user_input[:50]}...")
                chat_messages[session_id].append({"role": "user", "content": user_input})
                chat_messages[session_id].append({"role": "assistant", "content": learned_response})
                return ChatResponse(response=learned_response, session_id=session_id)
        
        # Obtener mensajes de la sesión
        messages = chat_messages[session_id].copy()
        messages.append({"role": "user", "content": user_input})
        
        # Paso 0: Detectar si es un número para selección de menú actual
        current_node_id = menu_state.get("current_menu_node_id", "root")
        try:
            option_number = int(user_input.strip())
            current_node = menu_tree.get_node(current_node_id)
            if current_node and current_node.children:
                child_node = menu_tree.get_child_by_number(current_node_id, option_number)
                if child_node:
                    # Mejorar menú de forma lazy si se accede a categorías económicas o sociales
                    if (not menu_states[session_id].get("menu_enhanced", False) and 
                        chat_session and chat_session.db_client and
                        child_node.id in ["economico", "socio"]):
                        try:
                            menu_generator = MenuGenerator(chat_session.db_client)
                            menu_tree = menu_generator.enhance_menu_tree(menu_tree)
                            menu_states[session_id]["menu_enhanced"] = True
                            menu_states[session_id]["menu_tree"] = menu_tree
                            menu_state["menu_tree"] = menu_tree
                            # Re-obtener el nodo después de mejorar el menú
                            child_node = menu_tree.get_child_by_number(current_node_id, option_number)
                            logging.info(f"Lazy-loaded enhanced menu for category: {child_node.id if child_node else 'unknown'}")
                        except Exception as e:
                            logging.warning(f"Error enhancing menu tree lazily: {e}")
                    
                    if child_node:
                        # Detectar cambio de categoría para limpiar contexto
                        new_category = detect_category(child_node.title + " " + (child_node.description or ""))
                        session_context = get_session_context(session_id)
                        if should_reset_context(session_context.current_category, new_category, menu_navigation=True):
                            # Limpiar mensajes anteriores excepto el system message
                            if session_id in chat_messages and len(chat_messages[session_id]) > 1:
                                system_msg = chat_messages[session_id][0]
                                chat_messages[session_id] = [system_msg]
                                logging.info(f"Context reset for session {session_id} due to topic change")
                            session_context.current_category = new_category
                        
                        if child_node.action == "menu":
                            menu_text = menu_tree.format_menu(child_node.id)
                            menu_state["current_menu_node_id"] = child_node.id
                            if child_node.id not in menu_state["menu_history"]:
                                menu_state["menu_history"].append(child_node.id)
                            chat_messages[session_id].append({"role": "user", "content": user_input})
                            chat_messages[session_id].append({"role": "assistant", "content": menu_text})
                            return ChatResponse(response=menu_text, session_id=session_id)
                        
                        elif child_node.action == "tool" and child_node.tool and tool_executor.is_available():
                            # Ejecutar herramienta usando ToolExecutor centralizado
                            result = tool_executor.execute(child_node.tool, child_node.tool_args)
                            chat_messages[session_id].append({"role": "user", "content": user_input})
                            chat_messages[session_id].append({"role": "assistant", "content": result})
                            return ChatResponse(response=result, session_id=session_id)
                        
                        elif child_node.action == "info" and child_node.info_text:
                            # Mostrar texto informativo
                            result = child_node.info_text
                            chat_messages[session_id].append({"role": "user", "content": user_input})
                            chat_messages[session_id].append({"role": "assistant", "content": result})
                            return ChatResponse(response=result, session_id=session_id)
                        
                        else:
                            # Es una consulta tradicional (query), usar el db_query del nodo
                            if child_node.db_query:
                                user_input = child_node.db_query
                                logging.info(f"Using db_query from node {child_node.id}: {user_input}")
                            else:
                                user_input = user_input
        except ValueError:
            pass  # No es un número, continuar normalmente
        
        # CONSULTAS DE DATOS: Usar información del clasificador LLM + QueryRouter
        # El LLM ya clasificó la intención, tema y entidades
        skip_menu_search = False
        
        # Si el LLM detectó consulta_datos o pregunta_conceptual con tema específico
        is_data_query = user_intent in ["consulta_datos", "pregunta_conceptual"]
        has_entities = len(intent_result.get("entidades", [])) > 0
        is_comparison = intent_result.get("es_comparacion", False)
        
        if is_data_query and (has_entities or is_comparison or intent_result.get("tema")):
            logging.info(f"LLM detected data query: tema={intent_result.get('tema')}, entidades={intent_result.get('entidades')}")
            skip_menu_search = True
            
            # Usar QueryRouter para ejecutar la herramienta correcta
            if tool_executor and tool_executor.is_available():
                query_router = QueryRouter(tool_executor)
                result = query_router.route_and_execute(user_input)
                
                if result:
                    tool_used, response = result
                    logging.info(f"QueryRouter executed {tool_used} successfully")
                    
                    # Enriquecer respuesta con contexto usando LLM si está disponible
                    if llm_client_for_intent:
                        response = enrich_data_response(response, user_input, llm_client_for_intent)
                    
                    chat_messages[session_id].append({"role": "user", "content": user_input})
                    chat_messages[session_id].append({"role": "assistant", "content": response})
                    return ChatResponse(response=response, session_id=session_id, tool=tool_used)
        
        # También verificar si el user_input es el título o keyword de alguna opción del menú
        # Esto maneja el caso cuando el frontend envía el título en lugar del número o cuando el usuario escribe directamente
        if not skip_menu_search and user_input and not user_input.isdigit():
            # Normalizar el input del usuario (remover emojis y espacios extra)
            user_input_normalized = re.sub(r'[^\w\s]', '', user_input.strip().lower())
            user_input_words = set(user_input_normalized.split())
            
            # Primero buscar en el menú actual
            current_node_id = menu_state.get("current_menu_node_id", "root")
            current_node = menu_tree.get_node(current_node_id)
            matched_node = None
            best_match_score = 0
            
            if current_node and current_node.children:
                for child_id in current_node.children:
                    child_node = menu_tree.get_node(child_id)
                    if child_node:
                        score = 0
                        # Buscar en título
                        if child_node.title:
                            title_normalized = re.sub(r'[^\w\s]', '', child_node.title.strip().lower())
                            title_words = set(title_normalized.split())
                            # Coincidencia exacta
                            if user_input_normalized == title_normalized:
                                score = 100
                            # Coincidencia parcial
                            elif user_input_normalized in title_normalized or title_normalized in user_input_normalized:
                                score = 50
                            # Coincidencia por palabras comunes
                            elif user_input_words & title_words:
                                score = len(user_input_words & title_words) * 10
                        
                        # Buscar en keywords
                        if child_node.keywords:
                            for keyword in child_node.keywords:
                                keyword_normalized = keyword.lower().strip()
                                if keyword_normalized in user_input_normalized or user_input_normalized in keyword_normalized:
                                    score += 20
                                elif keyword_normalized in user_input_words:
                                    score += 10
                        
                        if score > best_match_score:
                            best_match_score = score
                            matched_node = child_node
            
            # Si no se encontró en el menú actual, buscar en todo el árbol
            if not matched_node or best_match_score < 30:
                for node_id, node in menu_tree.nodes.items():
                    if node:
                        score = 0
                        # Buscar en título
                        if node.title:
                            title_normalized = re.sub(r'[^\w\s]', '', node.title.strip().lower())
                            title_words = set(title_normalized.split())
                            if user_input_normalized == title_normalized:
                                score = 100
                            elif user_input_normalized in title_normalized or title_normalized in user_input_normalized:
                                score = 50
                            elif user_input_words & title_words:
                                score = len(user_input_words & title_words) * 10
                        
                        # Buscar en keywords
                        if node.keywords:
                            for keyword in node.keywords:
                                keyword_normalized = keyword.lower().strip()
                                if keyword_normalized in user_input_normalized or user_input_normalized in keyword_normalized:
                                    score += 20
                                elif keyword_normalized in user_input_words:
                                    score += 10
                        
                        if score > best_match_score:
                            best_match_score = score
                            matched_node = node
            
            # Solo usar el nodo si tiene un score mínimo de confianza
            if matched_node and best_match_score >= 20:
                logging.info(f"Matched menu option '{matched_node.title}' (score: {best_match_score}, action: {matched_node.action})")
                
                # IMPORTANTE: Verificar si es una pregunta conceptual antes de ejecutar herramientas
                if is_conceptual_question(user_input):
                    logging.info(f"Detected conceptual question about '{matched_node.title}', passing to LLM")
                    # No ejecutar herramienta, dejar que el LLM responda la pregunta conceptual
                    # El matched_node nos da contexto sobre el tema
                    topic = get_topic_from_query(user_input)
                    conceptual_context = f"""El usuario pregunta sobre: {matched_node.title}
Descripción: {matched_node.description or 'Indicador estadístico del IPECD'}

Responde de forma clara y educativa qué es este indicador, cómo se calcula, para qué sirve, etc.
NO muestres datos numéricos a menos que el usuario los pida explícitamente después."""
                    
                    messages = chat_messages[session_id].copy()
                    messages.append({"role": "user", "content": user_input})
                    messages.append({"role": "system", "content": conceptual_context})
                    
                    llm_response = chat_session.llm_client.get_response(messages, fallback_client=chat_session.openai_client)
                    if llm_response:
                        chat_messages[session_id].append({"role": "user", "content": user_input})
                        chat_messages[session_id].append({"role": "assistant", "content": llm_response})
                        # Guardar en memoria aprendida (pregunta conceptual)
                        save_to_memory(user_input, llm_response, category=matched_node.id, is_conceptual=True)
                        return ChatResponse(response=llm_response, session_id=session_id)
                
                # Limpiar contexto al cambiar de tema
                new_category = detect_category(matched_node.title + " " + (matched_node.description or ""))
                session_context = get_session_context(session_id)
                if should_reset_context(session_context.current_category, new_category, menu_navigation=False):
                    if session_id in chat_messages and len(chat_messages[session_id]) > 1:
                        system_msg = chat_messages[session_id][0]
                        chat_messages[session_id] = [system_msg]
                        logging.info(f"Context reset for session {session_id} due to topic change to {new_category}")
                    session_context.current_category = new_category
                
                # Manejar según el tipo de acción (solo si NO es pregunta conceptual)
                if matched_node.action == "tool" and matched_node.tool and tool_executor.is_available():
                    # Ejecutar herramienta usando ToolExecutor centralizado
                    result = tool_executor.execute(matched_node.tool, matched_node.tool_args)
                    
                    # Enriquecer respuesta con contexto usando LLM si está disponible
                    if chat_session and chat_session.openai_client:
                        result = enrich_data_response(result, user_input, chat_session.openai_client)
                    
                    chat_messages[session_id].append({"role": "user", "content": user_input})
                    chat_messages[session_id].append({"role": "assistant", "content": result})
                    # Guardar en memoria aprendida (solicitud de datos)
                    save_to_memory(user_input, result, category=matched_node.id, is_conceptual=False)
                    return ChatResponse(response=result, session_id=session_id, tool=matched_node.tool)
                
                elif matched_node.action == "info" and matched_node.info_text:
                    result = matched_node.info_text
                    chat_messages[session_id].append({"role": "user", "content": user_input})
                    chat_messages[session_id].append({"role": "assistant", "content": result})
                    return ChatResponse(response=result, session_id=session_id)
                
                elif matched_node.action == "menu":
                    # Si es un menú, navegar a él
                    menu_text = menu_tree.format_menu(matched_node.id)
                    menu_state["current_menu_node_id"] = matched_node.id
                    if matched_node.id not in menu_state["menu_history"]:
                        menu_state["menu_history"].append(matched_node.id)
                    chat_messages[session_id].append({"role": "user", "content": user_input})
                    chat_messages[session_id].append({"role": "assistant", "content": menu_text})
                    return ChatResponse(response=menu_text, session_id=session_id)
                
                elif matched_node.db_query:
                    # Tiene un db_query, usarlo para la búsqueda
                    user_input = matched_node.db_query
                    logging.info(f"Using db_query: {user_input}")
        
        # Paso 0: Procesar entrada con sistema de menú y detección de palabras clave
        # SOLO si no es una consulta compleja que debe ir al LLM
        if skip_menu_search:
            # Para consultas complejas, forzar intent "open" para que vaya al LLM
            intent = {"type": "open", "confidence": 1.0, "query": user_input}
            logging.info(f"Complex query, forcing open intent: {user_input[:50]}...")
        else:
            intent = keyword_detector.detect_intent(user_input)
            logging.info(f"Detected intent: {intent}")
        
        # Manejar navegación del menú SOLO si es explícita (alta confianza)
        if not skip_menu_search and intent["type"] == "menu" and intent.get("confidence", 0) >= 0.8:
            node_id = intent.get("node_id", "root")
            
            # Mejorar menú de forma lazy cuando se accede a categorías económicas o sociales
            if (not menu_states[session_id].get("menu_enhanced", False) and 
                chat_session and chat_session.db_client and
                node_id in ["economico", "socio"]):
                try:
                    menu_generator = MenuGenerator(chat_session.db_client)
                    menu_tree = menu_generator.enhance_menu_tree(menu_tree)
                    menu_states[session_id]["menu_enhanced"] = True
                    menu_states[session_id]["menu_tree"] = menu_tree
                    menu_state["menu_tree"] = menu_tree
                    logging.info(f"Lazy-loaded enhanced menu for category: {node_id}")
                except Exception as e:
                    logging.warning(f"Error enhancing menu tree lazily: {e}")
            
            # Verificar que el nodo existe y tiene acción de menú
            target_node = menu_tree.get_node(node_id)
            if not target_node:
                logging.warning(f"Menu node {node_id} not found, using root")
                node_id = "root"
            elif target_node.action != "menu":
                # Si el nodo encontrado no es un menú, buscar su padre que tenga menú
                logging.info(f"Node {node_id} is not a menu (action={target_node.action}), searching for parent menu")
                for parent_node in menu_tree.nodes.values():
                    if parent_node.children and node_id in parent_node.children:
                        if parent_node.action == "menu":
                            node_id = parent_node.id
                            logging.info(f"Found parent menu node: {node_id}")
                            break
            
            menu_text = menu_tree.format_menu(node_id)
            menu_state["current_menu_node_id"] = node_id
            if node_id not in menu_state["menu_history"]:
                menu_state["menu_history"].append(node_id)
            chat_messages[session_id].append({"role": "user", "content": user_input})
            chat_messages[session_id].append({"role": "assistant", "content": menu_text})
            return ChatResponse(response=menu_text, session_id=session_id)
        
        if intent["type"] == "back":
            if menu_state["menu_history"]:
                menu_state["menu_history"].pop()
                if menu_state["menu_history"]:
                    prev_node_id = menu_state["menu_history"][-1]
                else:
                    prev_node_id = "root"
            else:
                prev_node_id = "root"
            menu_text = menu_tree.format_menu(prev_node_id)
            menu_state["current_menu_node_id"] = prev_node_id
            chat_messages[session_id].append({"role": "user", "content": user_input})
            chat_messages[session_id].append({"role": "assistant", "content": menu_text})
            return ChatResponse(response=menu_text, session_id=session_id)
        
        # Si es una consulta de estructura, manejarla directamente
        if intent.get("db_query") == "structure":
            if chat_session.db_client:
                try:
                    structure = chat_session.db_client.get_database_structure()
                    structure_info = []
                    for db_name, tables in structure.items():
                        db_info = f"Base de datos: {db_name}\n"
                        db_info += f"  Tablas disponibles: {len(tables)}\n"
                        for table_name, table_data in list(tables.items())[:10]:
                            columns = table_data.get('columns', [])
                            db_info += f"    - {table_name} ({len(columns)} columnas)\n"
                            if columns:
                                db_info += f"      Columnas: {', '.join(columns[:5])}"
                                if len(columns) > 5:
                                    db_info += f" ... (+{len(columns)-5} más)"
                                db_info += "\n"
                        structure_info.append(db_info)
                    
                    structure_response = "\n\n".join(structure_info)
                    chat_messages[session_id].append({"role": "user", "content": user_input})
                    chat_messages[session_id].append({"role": "assistant", "content": structure_response})
                    return ChatResponse(response=structure_response, session_id=session_id)
                except Exception as e:
                    logging.error(f"Error getting database structure: {e}")
        
        # Construir consulta optimizada para la base de datos
        # Nota: user_input ya puede haber sido actualizado con un db_query del menú en el código anterior
        # Verificar si es un query especial del menú (ej: "datalake_economico_ultimo_valor")
        query_processor = QueryProcessor(chat_session.db_client) if chat_session and chat_session.db_client else None
        
        # Usar user_input como db_query base (ya puede contener un db_query del menú)
        db_query = user_input
        
        # Detectar queries especiales del menú (pueden venir como db_query o como título)
        is_special_query = False
        if query_processor:
            # Verificar si contiene patrones de queries especiales (con guión bajo o espacios)
            special_patterns = ["_ultimo_valor", "_consulta_personalizada", "_ver_grafico", "_comparar_fechas",
                               "ultimo valor", "último valor", "ver gráfico", "ver grafico", 
                               "comparar fechas", "consulta personalizada"]
            is_special_query = any(pattern in db_query.lower() for pattern in special_patterns)
            
            if is_special_query:
                processed_query = query_processor.process_special_query(db_query, user_input)
                if processed_query and processed_query != db_query:
                    db_query = processed_query
                    logging.info(f"Processed special query: {user_input} -> {db_query}")
                else:
                    db_query = db_query if intent["type"] == "open" else keyword_detector.build_database_query(intent, user_input)
            else:
                # Para consultas abiertas, usar el texto original directamente
                db_query = db_query if intent["type"] == "open" else keyword_detector.build_database_query(intent, user_input)
        else:
            # Para consultas abiertas, usar el texto original directamente
            db_query = db_query if intent["type"] == "open" else keyword_detector.build_database_query(intent, user_input)
        
        # Paso 1: Buscar SOLO en la base de datos (NO usar búsqueda web)
        db_result = await chat_session.search_in_database(db_query)
        
        # NO buscar en web - solo usar base de datos
        web_result = None
        
        # Preparar mensajes para el LLM
        current_messages = messages.copy()
        
        # Si encontramos información en la BD, incluirla en el contexto
        if db_result:
            current_messages.append({
                "role": "system", 
                "content": f"IMPORTANT: I found relevant statistical information in the database. Here are the data:\n\n{db_result}\n\nYou MUST use this information to directly answer the user's question with concrete statistics and numbers. Present the data in a friendly, conversational way. DO NOT mention table names, column names, database names, or any technical details. Only present the actual statistical information and data values. If the user asks for 'ultimo valor' or 'last value', show the most recent data from the results. Format numbers clearly (use thousands separators, percentages, etc.). IMPORTANT: Only use information from the database. Do NOT use any external sources or web search. Respond as if you are a friendly data analyst presenting statistics to a general audience."
            })
        else:
            # Si no hay resultados en la BD, buscar opciones relacionadas del menú
            related_finder = RelatedOptionsFinder(menu_tree)
            related_options = related_finder.find_related_options(user_input, max_options=5)
            
            if related_options:
                # Si encontramos opciones relacionadas, mostrar menú de opciones
                related_menu = related_finder.format_related_options_menu(user_input, related_options)
                chat_messages[session_id].append({"role": "user", "content": user_input})
                chat_messages[session_id].append({"role": "assistant", "content": related_menu})
                return ChatResponse(response=related_menu, session_id=session_id)
            else:
                # Si no hay opciones relacionadas, informar al usuario
                current_messages.append({
                    "role": "system",
                    "content": "No se encontró información en la base de datos para esta consulta. Responde de manera amigable indicando que no hay datos disponibles en nuestra base de datos para esta consulta específica. Sugiere al usuario que puede navegar por el menú principal o reformular su consulta. NO uses información de internet ni fuentes externas."
            })
        
        # Paso 2: Obtener respuesta del LLM principal con fallback automático
        llm_response = chat_session.llm_client.get_response(
            current_messages, 
            fallback_client=chat_session.openai_client
        )
        
        if not llm_response and chat_session.openai_client:
            llm_response = chat_session.openai_client.get_response(current_messages)
        
        if not llm_response:
            error_msg = "Lo siento, hubo un error al procesar tu solicitud. Por favor intenta de nuevo."
            chat_messages[session_id].append({"role": "user", "content": user_input})
            chat_messages[session_id].append({"role": "assistant", "content": error_msg})
            return ChatResponse(response=error_msg, session_id=session_id)
        
        # Si tenemos información de BD y la respuesta del LLM parece incompleta
        if db_result and llm_response:
            response_lower = llm_response.lower()
            if any(phrase in response_lower for phrase in [
                'déjame buscar', 'déjame', 'buscar', 'busco', 'voy a buscar', 
                'te ayudo a buscar', 'buscaré', 'buscaré el'
            ]) and len(llm_response) < 100:
                direct_response_messages = [
                    {
                        "role": "system",
                        "content": f"You found this information in the database:\n\n{db_result}\n\nPresent this information directly to the user in a clear, formatted way. Do NOT say you will search - show the actual data now."
                    },
                    {"role": "user", "content": user_input}
                ]
                direct_response = chat_session.llm_client.get_response(
                    direct_response_messages, 
                    fallback_client=chat_session.openai_client
                )
                if direct_response and len(direct_response) > len(llm_response):
                    llm_response = direct_response
        
        # Paso 3: Procesar la respuesta (ejecutar herramientas si es necesario)
        result = await chat_session.process_llm_response(llm_response)
        
        # Paso 4: Si se ejecutó una herramienta, obtener respuesta final
        if result != llm_response:
            current_messages.append({"role": "assistant", "content": llm_response})
            current_messages.append({"role": "system", "content": result})
            
            if "No information found" in result or "not found" in result.lower():
                if chat_session.openai_client:
                    fallback_messages = [
                        {
                            "role": "system",
                            "content": "You are a helpful assistant. The user asked a question but no relevant information was found in their database or on the web. Provide a helpful answer based on your general knowledge."
                        },
                        {"role": "user", "content": user_input}
                    ]
                    final_response = chat_session.openai_client.get_response(fallback_messages)
                    if final_response:
                        chat_messages[session_id].append({"role": "user", "content": user_input})
                        chat_messages[session_id].append({"role": "assistant", "content": final_response})
                        return ChatResponse(response=final_response, session_id=session_id)
            
            final_response = chat_session.llm_client.get_response(
                current_messages, 
                fallback_client=chat_session.openai_client
            )
            if not final_response and chat_session.openai_client:
                final_response = chat_session.openai_client.get_response(current_messages)
            
            if final_response:
                chat_messages[session_id].append({"role": "user", "content": user_input})
                chat_messages[session_id].append({"role": "assistant", "content": final_response})
                return ChatResponse(response=final_response, session_id=session_id)
        else:
            # Respuesta directa sin herramientas
            chat_messages[session_id].append({"role": "user", "content": user_input})
            chat_messages[session_id].append({"role": "assistant", "content": llm_response})
            return ChatResponse(response=llm_response, session_id=session_id)
        
        # Fallback final
        error_msg = "Lo siento, hubo un error al procesar tu solicitud. Por favor intenta de nuevo."
        return ChatResponse(response=error_msg, session_id=session_id)
        
    except HTTPException:
        # Re-lanzar HTTPExceptions sin modificar
        raise
    except Exception as e:
        logging.error(f"Error processing chat message: {e}", exc_info=True)
        # Asegurar que siempre devolvemos una respuesta válida
        try:
            return ChatResponse(
                response=f"Lo siento, hubo un error al procesar tu solicitud: {str(e)}",
                session_id=chat_message.session_id or "default"
            )
        except Exception as fallback_error:
            logging.error(f"Error in fallback response: {fallback_error}")
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")


@app.get("/api/health")
async def health_check():
    """Endpoint de salud."""
    return {"status": "healthy", "chat_session": chat_session is not None}

