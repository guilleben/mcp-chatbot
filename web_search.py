"""Web search module using OpenAI function calling and alternative search APIs."""
import logging
from typing import Dict, List, Optional, Any
import json

import requests


class WebSearchClient:
    """Manages web search using OpenAI function calling and alternative APIs."""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        """Initialize web search client.
        
        Args:
            openai_api_key: OpenAI API key for using OpenAI's web search capabilities
        """
        self.openai_api_key = openai_api_key
        self.base_url = "https://api.openai.com/v1/chat/completions"
    
    def search_with_openai(self, query: str) -> Optional[str]:
        """Search the web using OpenAI's function calling with web_search tool.
        
        Args:
            query: Search query string
            
        Returns:
            Search results as formatted string, or None if failed
        """
        if not self.openai_api_key:
            return None
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.openai_api_key}"
        }
        
        # Usar OpenAI con function calling para búsqueda web
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "user",
                    "content": f"Busca información actualizada sobre: {query}"
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "description": "Search the web for current information",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The search query"
                                }
                            },
                            "required": ["query"]
                        }
                    }
                }
            ],
            "tool_choice": "auto",
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Procesar la respuesta
            if 'choices' in data and len(data['choices']) > 0:
                choice = data['choices'][0]
                
                # Si hay tool calls, procesarlos
                if 'message' in choice and 'tool_calls' in choice['message']:
                    # OpenAI ejecutó la búsqueda web, obtener el resultado
                    tool_call = choice['message']['tool_calls'][0]
                    if 'function' in tool_call and 'arguments' in tool_call['function']:
                        function_args = json.loads(tool_call['function']['arguments'])
                        search_query = function_args.get('query')
                        
                        # Ejecutar búsqueda real con DuckDuckGo
                        logging.info(f"Executing actual web search for: {search_query}")
                        search_results = self.search_with_duckduckgo(search_query)
                        
                        if not search_results:
                            search_results = "No results found."

                        # Continuar la conversación con los resultados
                        messages = [
                            {
                                "role": "user",
                                "content": f"Busca información sobre: {query}"
                            },
                            choice['message'],
                            {
                                "role": "tool",
                                "tool_call_id": tool_call['id'],
                                "name": "web_search",
                                "content": search_results
                            }
                        ]
                        
                        # Segunda llamada para obtener la respuesta final
                        payload2 = {
                            "model": "gpt-4o-mini",
                            "messages": messages,
                            "temperature": 0.7,
                            "max_tokens": 2000
                        }
                        
                        response2 = requests.post(self.base_url, headers=headers, json=payload2, timeout=30)
                        response2.raise_for_status()
                        data2 = response2.json()
                        
                        if 'choices' in data2 and len(data2['choices']) > 0:
                            return data2['choices'][0]['message']['content']
                
                # Si no hay tool calls, usar la respuesta directa
                if 'message' in choice and 'content' in choice['message']:
                    return choice['message']['content']
            
            return None
            
        except Exception as e:
            logging.warning(f"Error using OpenAI web search: {e}")
            return None
    
    def search_with_duckduckgo(self, query: str, max_results: int = 5) -> Optional[str]:
        """Search the web using DuckDuckGo (free, no API key required).
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            
        Returns:
            Formatted search results, or None if failed
        """
        try:
            # DuckDuckGo Instant Answer API (gratis, sin API key)
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1"
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            results = []
            
            # Extraer respuesta directa si existe
            if data.get('AbstractText'):
                results.append(f"📄 {data['AbstractText']}")
                if data.get('AbstractURL'):
                    results.append(f"Fuente: {data['AbstractURL']}")
            
            # Extraer temas relacionados
            if data.get('RelatedTopics'):
                for topic in data['RelatedTopics'][:max_results]:
                    if isinstance(topic, dict) and 'Text' in topic:
                        results.append(f"• {topic['Text']}")
                        if 'FirstURL' in topic:
                            results.append(f"  {topic['FirstURL']}")
            
            # Extraer definiciones
            if data.get('Definition'):
                results.append(f"📖 Definición: {data['Definition']}")
                if data.get('DefinitionURL'):
                    results.append(f"Fuente: {data['DefinitionURL']}")
            
            if results:
                return "\n".join(results)
            
            return None
            
        except Exception as e:
            logging.warning(f"Error using DuckDuckGo search: {e}")
            return None
    
    def search(self, query: str, prefer_openai: bool = True) -> Optional[str]:
        """Search the web using available methods.
        
        Args:
            query: Search query string
            prefer_openai: If True, try OpenAI first, then DuckDuckGo. If False, use DuckDuckGo only.
            
        Returns:
            Formatted search results, or None if all methods failed
        """
        # Intentar con OpenAI si está disponible y preferido
        if prefer_openai and self.openai_api_key:
            result = self.search_with_openai(query)
            if result:
                logging.info("Web search successful using OpenAI")
                return result
        
        # Fallback a DuckDuckGo
        result = self.search_with_duckduckgo(query)
        if result:
            logging.info("Web search successful using DuckDuckGo")
            return result
        
        logging.warning("All web search methods failed")
        return None


class WebSearchWithSerpAPI:
    """Alternative web search using SerpAPI (requires API key).
    
    SerpAPI provides Google Search results. Requires SERP_API_KEY in environment.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize SerpAPI client.
        
        Args:
            api_key: SerpAPI key (optional, can be None if not using SerpAPI)
        """
        self.api_key = api_key
        self.base_url = "https://serpapi.com/search"
    
    def search(self, query: str, num_results: int = 8) -> Optional[str]:
        """Search using SerpAPI (Google Search).
        
        Args:
            query: Search query string
            num_results: Number of results to return
            
        Returns:
            Formatted search results, or None if failed
        """
        if not self.api_key:
            logging.warning("SerpAPI key not available")
            return None
        
        try:
            params = {
                "q": query,
                "api_key": self.api_key,
                "num": num_results,
                "hl": "es",  # Idioma español
                "gl": "ar",  # País Argentina (puedes cambiarlo)
                "safe": "active"
            }
            
            logging.info(f"SerpAPI request: {query}")
            response = requests.get(self.base_url, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()
            
            results = []
            
            # Extraer respuesta directa si existe (prioridad)
            if 'answer_box' in data:
                answer = data['answer_box']
                if 'answer' in answer:
                    results.append(f"💡 Respuesta directa: {answer['answer']}")
                    if 'link' in answer:
                        results.append(f"   🔗 Fuente: {answer['link']}")
                    results.append("")  # Línea en blanco
                elif 'snippet' in answer:
                    results.append(f"💡 {answer['snippet']}")
                    if 'link' in answer:
                        results.append(f"   🔗 Fuente: {answer['link']}")
                    results.append("")
                elif 'result' in answer:
                    results.append(f"💡 {answer['result']}")
                    if 'link' in answer:
                        results.append(f"   🔗 Fuente: {answer['link']}")
                    results.append("")
            
            # Extraer knowledge graph si existe
            if 'knowledge_graph' in data:
                kg = data['knowledge_graph']
                if 'description' in kg:
                    results.append(f"📚 Información: {kg['description']}")
                    if 'source' in kg and 'link' in kg['source']:
                        results.append(f"   🔗 Fuente: {kg['source']['link']}")
                    results.append("")
            
            # Extraer resultados orgánicos
            if 'organic_results' in data and data['organic_results']:
                results.append("📄 Resultados de búsqueda:")
                for idx, result in enumerate(data['organic_results'][:num_results], 1):
                    title = result.get('title', '')
                    snippet = result.get('snippet', '')
                    link = result.get('link', '')
                    
                    if title:
                        results.append(f"\n{idx}. {title}")
                        if snippet:
                            results.append(f"   {snippet}")
                        if link:
                            results.append(f"   🔗 {link}")
            
            # Extraer resultados de noticias si existen
            if 'news_results' in data and data['news_results']:
                results.append("\n📰 Noticias relacionadas:")
                for news in data['news_results'][:3]:
                    title = news.get('title', '')
                    snippet = news.get('snippet', '')
                    link = news.get('link', '')
                    if title:
                        results.append(f"   • {title}")
                        if snippet:
                            results.append(f"     {snippet}")
                        if link:
                            results.append(f"     🔗 {link}")
            
            if results:
                result_text = "\n".join(results)
                logging.info(f"SerpAPI returned {len(results)} result lines")
                return result_text
            
            logging.warning("SerpAPI returned no results")
            return None
            
        except requests.exceptions.RequestException as e:
            logging.error(f"SerpAPI request error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logging.error(f"SerpAPI response status: {e.response.status_code}")
                logging.error(f"SerpAPI response: {e.response.text[:200]}")
            return None
        except Exception as e:
            logging.error(f"Error using SerpAPI search: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return None

