"""Configuration management module."""
import json
import os
from typing import Dict, Any

from dotenv import load_dotenv


class Configuration:
    """Manages configuration and environment variables for the MCP client."""

    def __init__(self) -> None:
        """Initialize configuration with environment variables."""
        self.load_env()
        self.api_key = os.getenv("GROQ_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.serp_api_key = os.getenv("SERP_API_KEY")  # Opcional: para búsqueda web con SerpAPI
        
        # Database configuration
        self.db_host = os.getenv("HOST_DBB")
        self.db_port = int(os.getenv("DB_PORT", "3306"))
        self.db_user = os.getenv("USER_DBB")
        self.db_password = os.getenv("PASSWORD_DBB")
        self.db_databases = {
            "datalake_economico": os.getenv("NAME_DBB_DATALAKE_ECONOMICO"),
            "dwh_economico": os.getenv("NAME_DBB_DWH_ECONOMICO"),
            "datalake_socio": os.getenv("NAME_DBB_DATALAKE_SOCIO"),
            "dwh_socio": os.getenv("NAME_DBB_DWH_SOCIO"),
        }

    @staticmethod
    def load_env() -> None:
        """Load environment variables from .env file."""
        load_dotenv()

    @staticmethod
    def load_config(file_path: str) -> Dict[str, Any]:
        """Load server configuration from JSON file.
        
        Args:
            file_path: Path to the JSON configuration file.
            
        Returns:
            Dict containing server configuration.
            
        Raises:
            FileNotFoundError: If configuration file doesn't exist.
            JSONDecodeError: If configuration file is invalid JSON.
        """
        with open(file_path, 'r') as f:
            return json.load(f)

    @property
    def llm_api_key(self) -> str:
        """Get the LLM API key.
        
        Returns:
            The API key as a string.
            
        Raises:
            ValueError: If the API key is not found in environment variables.
        """
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables")
        return self.api_key
    
    @property
    def has_openai_key(self) -> bool:
        """Check if OpenAI API key is available.
        
        Returns:
            True if OpenAI API key is set, False otherwise.
        """
        return bool(self.openai_api_key)
    
    @property
    def has_database_config(self) -> bool:
        """Check if database configuration is available.
        
        Returns:
            True if database configuration is complete, False otherwise.
        """
        return bool(self.db_host and self.db_user and self.db_password)
    
    @property
    def has_serp_api_key(self) -> bool:
        """Check if SerpAPI key is available for web search.
        
        Returns:
            True if SerpAPI key is set, False otherwise.
        """
        return bool(self.serp_api_key)

