"""
LLM Provider Abstraction Layer

This module provides a unified interface for LLM providers (Claude vs Local Ollama).
Use the factory function `get_llm_provider()` to get the appropriate provider based on
the USE_LOCAL_LLM environment variable.

Usage:
    provider = get_llm_provider()
    response = await provider.generate("You are a helpful assistant", "Hello!")
"""

import os
import json
import logging
import httpx
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def generate(
        self, 
        system: str, 
        prompt: str, 
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> str:
        """Generate a response from the LLM."""
        pass
    
    @abstractmethod
    async def generate_json(
        self, 
        system: str, 
        prompt: str, 
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """Generate a JSON response from the LLM."""
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the name of the provider."""
        pass


class ClaudeProvider(LLMProvider):
    """Claude (Anthropic) LLM provider - uses the paid API."""
    
    def __init__(self):
        self.api_key = os.getenv('ANTHROPIC_API_KEY') or os.getenv('EMERGENT_LLM_KEY')
        if not self.api_key:
            logger.warning("No Anthropic API key found")
            self.client = None
        else:
            self.client = AsyncAnthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-20250514"
    
    async def generate(
        self, 
        system: str, 
        prompt: str, 
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> str:
        if not self.client:
            raise ValueError("Anthropic client not initialized - API key required")
        
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude API error: {str(e)}")
            raise
    
    async def generate_json(
        self, 
        system: str, 
        prompt: str, 
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        response = await self.generate(
            system=system + "\n\nRespond ONLY with valid JSON, no additional text.",
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=0.3  # Lower temperature for structured output
        )
        
        # Try to parse JSON from response
        try:
            # Handle potential markdown code blocks
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            return json.loads(response.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Claude response: {response[:200]}")
            raise ValueError(f"Invalid JSON response from Claude: {str(e)}")
    
    def get_provider_name(self) -> str:
        return "claude"


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider - uses local Llama 3.1 8B model."""
    
    def __init__(self):
        self.base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        self.model = os.getenv('OLLAMA_MODEL', 'llama3.1:8b')
        self.timeout = httpx.Timeout(300.0)  # 5 minute timeout for slow CPU inference
    
    async def _call_ollama(
        self, 
        system: str, 
        prompt: str, 
        max_tokens: int = 4096,
        temperature: float = 0.7,
        format: Optional[str] = None
    ) -> str:
        """Make a request to the Ollama API."""
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature
            }
        }
        
        if format == "json":
            payload["format"] = "json"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()
                return result.get("response", "")
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Make sure Ollama is running: `ollama serve`"
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Ollama API error: {str(e)}")
            raise
    
    async def generate(
        self, 
        system: str, 
        prompt: str, 
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> str:
        return await self._call_ollama(
            system=system,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )
    
    async def generate_json(
        self, 
        system: str, 
        prompt: str, 
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        response = await self._call_ollama(
            system=system + "\n\nRespond ONLY with valid JSON, no additional text.",
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=0.3,
            format="json"
        )
        
        try:
            # Handle potential markdown code blocks
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            return json.loads(response.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Ollama response: {response[:200]}")
            raise ValueError(f"Invalid JSON response from Ollama: {str(e)}")
    
    def get_provider_name(self) -> str:
        return "ollama"


# Singleton instances
_claude_provider: Optional[ClaudeProvider] = None
_ollama_provider: Optional[OllamaProvider] = None


def get_llm_provider() -> LLMProvider:
    """
    Factory function to get the appropriate LLM provider.
    
    Uses USE_LOCAL_LLM environment variable to determine which provider to use:
    - USE_LOCAL_LLM=true  -> OllamaProvider (local Llama 3.1 8B)
    - USE_LOCAL_LLM=false -> ClaudeProvider (Anthropic API)
    
    Returns:
        LLMProvider: The appropriate provider instance
    """
    global _claude_provider, _ollama_provider
    
    use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
    
    if use_local:
        if _ollama_provider is None:
            _ollama_provider = OllamaProvider()
            logger.info(f"Using Ollama provider with model: {_ollama_provider.model}")
        return _ollama_provider
    else:
        if _claude_provider is None:
            _claude_provider = ClaudeProvider()
            logger.info(f"Using Claude provider with model: {_claude_provider.model}")
        return _claude_provider


def get_collection_name(base_name: str) -> str:
    """
    Get the appropriate collection name based on LLM mode.
    
    When using local LLM (USE_LOCAL_LLM=true), collections are prefixed with 'local_'
    to keep data separate from Claude-generated data.
    
    Args:
        base_name: The base collection name (e.g., 'policies', 'regulations')
    
    Returns:
        str: The collection name to use (e.g., 'policies' or 'local_policies')
    """
    use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
    
    if use_local:
        return f"local_{base_name}"
    return base_name


def is_using_local_llm() -> bool:
    """Check if local LLM mode is enabled."""
    return os.getenv("USE_LOCAL_LLM", "false").lower() == "true"


async def log_llm_cost(
    db,
    provider: str,
    operation: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost: float = 0.0,
    model: str = "",
    user_id: str = "",
):
    """
    Feature #212: Log LLM operation cost to MongoDB for tracking.
    Local LLM operations always log cost as 0.
    Cloud operations estimate cost based on token usage.
    """
    from datetime import datetime, timezone

    # Local LLM operations are always zero cost
    if provider in ("ollama", "local"):
        cost = 0.0
    elif provider == "claude" and cost == 0.0:
        # Estimate Claude costs: ~$3/M input, ~$15/M output for Sonnet
        cost = (input_tokens * 0.000003) + (output_tokens * 0.000015)

    try:
        await db.llm_cost_tracking.insert_one({
            "provider": provider,
            "operation": operation,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": round(cost, 8),
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning(f"Failed to log LLM cost: {e}")
