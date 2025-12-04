"""LLM client modules for Groq and OpenAI."""
import logging
from typing import Dict, List, Optional

import requests


class LLMClient:
    """Manages communication with the LLM provider (Groq)."""

    def __init__(self, api_key: str) -> None:
        self.api_key: str = api_key

    def get_response(self, messages: List[Dict[str, str]], fallback_client=None) -> Optional[str]:
        """Get a response from the LLM.
        
        Args:
            messages: A list of message dictionaries.
            fallback_client: Optional OpenAI client to use as fallback if Groq fails.
            
        Returns:
            The LLM's response as a string, or None if failed and no fallback.
            
        Raises:
            RequestException: If the request to the LLM fails and no fallback is available.
        """
        url = "https://api.groq.com/openai/v1/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "messages": messages,
            "model": "openai/gpt-oss-20b",  # Modelo válido según ejemplo del usuario
            "temperature": 0.7,
            "max_tokens": 4096,
            "top_p": 1,
            "stream": False,
            "stop": None
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data['choices'][0]['message']['content']
            
        except requests.exceptions.RequestException as e:
            error_message = f"Error getting LLM response from Groq: {str(e)}"
            logging.warning(error_message)
            
            if e.response is not None:
                status_code = e.response.status_code
                logging.warning(f"Groq API status code: {status_code}")
                
                # Si hay un fallback disponible, usarlo automáticamente
                if fallback_client and (status_code >= 500 or status_code in [401, 403, 429]):
                    logging.info("Groq API error detected, switching to OpenAI fallback...")
                    try:
                        return fallback_client.get_response(messages)
                    except Exception as fallback_error:
                        logging.error(f"OpenAI fallback also failed: {fallback_error}")
                        return None
            
            # Si no hay fallback o es un error diferente, retornar None para que el sistema maneje el error
            return None


class OpenAIClient:
    """Manages communication with OpenAI API as fallback when database doesn't have information."""

    def __init__(self, api_key: str) -> None:
        self.api_key: str = api_key
        self.base_url = "https://api.openai.com/v1/chat/completions"

    def get_response(self, messages: List[Dict[str, str]]) -> str:
        """Get a response from OpenAI API.
        
        Args:
            messages: A list of message dictionaries.
            
        Returns:
            The OpenAI's response as a string.
            
        Raises:
            RequestException: If the request to OpenAI fails.
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "messages": messages,
            "model": "gpt-4o-mini",  # Modelo económico y eficiente
            "temperature": 0.7,
            "max_tokens": 4096,
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data['choices'][0]['message']['content']
            
        except requests.exceptions.RequestException as e:
            error_message = f"Error getting OpenAI response: {str(e)}"
            logging.error(error_message)
            
            if e.response is not None:
                status_code = e.response.status_code
                logging.error(f"Status code: {status_code}")
                logging.error(f"Response details: {e.response.text}")
                
            return f"I encountered an error: {error_message}. Please try again or rephrase your request."

