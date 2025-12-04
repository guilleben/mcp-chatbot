"""Main entry point for the MCP chatbot application."""
import asyncio
import logging

from chat_session import ChatSession
from config import Configuration
from database import DatabaseClient
from llm_clients import LLMClient, OpenAIClient
from mcp_server import Server
from web_search import WebSearchClient, WebSearchWithSerpAPI

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


async def main() -> None:
    """Initialize and run the chat session."""
    config = Configuration()
    server_config = config.load_config('servers_config.json')
    servers = [Server(name, srv_config) for name, srv_config in server_config['mcpServers'].items()]
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
            logging.info(f"Available databases: {', '.join([db for db in config.db_databases.values() if db])}")
        except Exception as e:
            logging.error(f"Error initializing database client: {e}")
    else:
        logging.warning("Database configuration not found. Database search will not be available.")
    
    # Crear cliente OpenAI como fallback si está disponible
    openai_client = None
    if config.has_openai_key:
        openai_client = OpenAIClient(config.openai_api_key)
        logging.info("OpenAI client initialized as fallback")
    else:
        logging.warning("OPENAI_API_KEY not found. Fallback to OpenAI will not be available.")
    
    # Crear cliente de búsqueda web
    web_search_client = None
    if config.has_openai_key:
        web_search_client = WebSearchClient(config.openai_api_key)
        logging.info("Web search client initialized (OpenAI + DuckDuckGo)")
    else:
        logging.warning("Web search will use DuckDuckGo only (no OpenAI API key)")
        web_search_client = WebSearchClient(None)
    
    # Crear cliente SerpAPI si está disponible (opcional, mejor calidad)
    serp_api_client = None
    if config.has_serp_api_key:
        serp_api_client = WebSearchWithSerpAPI(config.serp_api_key)
        logging.info("SerpAPI client initialized for enhanced web search")
    else:
        logging.info("SerpAPI key not found. Using free web search methods.")
    
    chat_session = ChatSession(servers, llm_client, openai_client, db_client, 
                              web_search_client, serp_api_client)
    await chat_session.start()


if __name__ == "__main__":
    asyncio.run(main())
