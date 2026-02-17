"""
Azure OpenAI Provider for GrantScope2 Application.

This module provides a centralized Azure OpenAI client configuration
with proper API versioning for different model types (chat vs embeddings).

Azure Configuration:
- Endpoint: https://aph-cognitive-sandbox-openai-eastus2.openai.azure.com
- Chat Completions (gpt-41, gpt-41-mini): API version 2025-01-01-preview
- Embeddings (text-embedding-ada-002): API version 2023-05-15

Environment Variables Required:
- AZURE_OPENAI_ENDPOINT: Azure OpenAI endpoint URL
- AZURE_OPENAI_KEY: Azure OpenAI API key
- AZURE_OPENAI_API_VERSION: API version for chat completions (default: 2025-01-01-preview)
- AZURE_OPENAI_EMBEDDING_API_VERSION: API version for embeddings (default: 2023-05-15)
- AZURE_OPENAI_DEPLOYMENT_CHAT: Deployment name for main chat model (default: gpt-41)
- AZURE_OPENAI_DEPLOYMENT_CHAT_MINI: Deployment name for fast/cheap chat model (default: gpt-41-mini)
- AZURE_OPENAI_DEPLOYMENT_EMBEDDING: Deployment name for embeddings (default: text-embedding-ada-002)

Usage:
    from app.openai_provider import (
        azure_openai_client,
        azure_openai_async_client,
        get_chat_deployment,
        get_chat_mini_deployment,
        get_embedding_deployment,
    )
"""

import os
import logging
from openai import AzureOpenAI, AsyncAzureOpenAI

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration Loading
# =============================================================================


def _get_required_env(name: str) -> str:
    """Get a required environment variable or raise an error."""
    if value := os.getenv(name):
        return value
    else:
        raise ValueError(
            f"Missing required environment variable: {name}. "
            f"Azure OpenAI configuration is required for this application."
        )


def _get_optional_env(name: str, default: str) -> str:
    """Get an optional environment variable with a default value."""
    return os.getenv(name, default)


# =============================================================================
# Azure OpenAI Configuration
# =============================================================================


class AzureOpenAIConfig:
    """Azure OpenAI configuration container."""

    def __init__(self):
        """Load configuration from environment variables."""
        # Required configuration
        self.endpoint = _get_required_env("AZURE_OPENAI_ENDPOINT")
        self.api_key = _get_required_env("AZURE_OPENAI_KEY")

        # API versions (different for chat vs embeddings)
        self.chat_api_version = _get_optional_env(
            "AZURE_OPENAI_API_VERSION", "2024-12-01-preview"
        )
        self.embedding_api_version = _get_optional_env(
            "AZURE_OPENAI_EMBEDDING_API_VERSION", "2023-05-15"
        )

        # Deployment names (Azure-specific model deployment names)
        self.deployment_chat = _get_optional_env(
            "AZURE_OPENAI_DEPLOYMENT_CHAT", "gpt-4.1"
        )
        self.deployment_chat_mini = _get_optional_env(
            "AZURE_OPENAI_DEPLOYMENT_CHAT_MINI", "gpt-4.1-mini"
        )
        self.deployment_embedding = _get_optional_env(
            "AZURE_OPENAI_DEPLOYMENT_EMBEDDING", "text-embedding-ada-002"
        )

    def log_configuration(self):
        """Log the current configuration (without sensitive data)."""
        logger.info("Azure OpenAI Configuration:")
        logger.info(f"  Endpoint: {self.endpoint}")
        logger.info(f"  Chat API Version: {self.chat_api_version}")
        logger.info(f"  Embedding API Version: {self.embedding_api_version}")
        logger.info(f"  Chat Deployment: {self.deployment_chat}")
        logger.info(f"  Chat Mini Deployment: {self.deployment_chat_mini}")
        logger.info(f"  Embedding Deployment: {self.deployment_embedding}")


# =============================================================================
# Model Name Mapping
# =============================================================================

# Map from OpenAI model names to Azure deployment names
# This allows existing code using OpenAI model names to work with Azure
_MODEL_TO_DEPLOYMENT: dict = {}


def _initialize_model_mapping(config: AzureOpenAIConfig):
    """Initialize the model name to deployment name mapping."""
    global _MODEL_TO_DEPLOYMENT
    _MODEL_TO_DEPLOYMENT = {
        # Chat models
        "gpt-4o": config.deployment_chat,
        "gpt-4o-mini": config.deployment_chat_mini,
        "gpt-4": config.deployment_chat,  # Fallback for gpt-4 references
        "gpt-4-turbo": config.deployment_chat,  # Fallback
        # Embedding models
        "text-embedding-ada-002": config.deployment_embedding,
        "text-embedding-3-small": config.deployment_embedding,  # Fallback
        "text-embedding-3-large": config.deployment_embedding,  # Fallback
    }


def get_deployment_name(model_name: str) -> str:
    """
    Get the Azure deployment name for a given OpenAI model name.

    Args:
        model_name: OpenAI model name (e.g., 'gpt-4o', 'text-embedding-ada-002')

    Returns:
        Azure deployment name

    Raises:
        ValueError: If model name is not mapped
    """
    if model_name in _MODEL_TO_DEPLOYMENT:
        return _MODEL_TO_DEPLOYMENT[model_name]

    # If the model name is already a deployment name, return it
    if model_name in [
        _config.deployment_chat,
        _config.deployment_chat_mini,
        _config.deployment_embedding,
    ]:
        return model_name

    raise ValueError(
        f"Unknown model name: {model_name}. "
        f"Available mappings: {list(_MODEL_TO_DEPLOYMENT.keys())}"
    )


# =============================================================================
# Convenience Functions for Deployment Names
# =============================================================================


def get_chat_deployment() -> str:
    """Get the main chat model deployment name (gpt-41)."""
    return _config.deployment_chat


def get_chat_mini_deployment() -> str:
    """Get the fast/cheap chat model deployment name (gpt-41-mini)."""
    return _config.deployment_chat_mini


def get_embedding_deployment() -> str:
    """Get the embedding model deployment name (text-embedding-ada-002)."""
    return _config.deployment_embedding


def get_chat_api_version() -> str:
    """Get the API version for chat completions."""
    return _config.chat_api_version


def get_embedding_api_version() -> str:
    """Get the API version for embeddings."""
    return _config.embedding_api_version


# =============================================================================
# Client Initialization
# =============================================================================


def _create_sync_client(config: AzureOpenAIConfig) -> AzureOpenAI:
    """Create a synchronous Azure OpenAI client."""
    return AzureOpenAI(
        api_key=config.api_key,
        api_version=config.chat_api_version,
        azure_endpoint=config.endpoint,
    )


def _create_async_client(config: AzureOpenAIConfig) -> AsyncAzureOpenAI:
    """Create an asynchronous Azure OpenAI client."""
    return AsyncAzureOpenAI(
        api_key=config.api_key,
        api_version=config.chat_api_version,
        azure_endpoint=config.endpoint,
    )


def _create_embedding_client(config: AzureOpenAIConfig) -> AzureOpenAI:
    """
    Create a synchronous Azure OpenAI client specifically for embeddings.
    Uses the embedding-specific API version.
    """
    return AzureOpenAI(
        api_key=config.api_key,
        api_version=config.embedding_api_version,
        azure_endpoint=config.endpoint,
    )


def _create_async_embedding_client(config: AzureOpenAIConfig) -> AsyncAzureOpenAI:
    """
    Create an asynchronous Azure OpenAI client specifically for embeddings.
    Uses the embedding-specific API version.
    """
    return AsyncAzureOpenAI(
        api_key=config.api_key,
        api_version=config.embedding_api_version,
        azure_endpoint=config.endpoint,
    )


# =============================================================================
# Module Initialization (Fail Fast)
# =============================================================================

# Initialize configuration - this will raise if required env vars are missing
try:
    _config = AzureOpenAIConfig()
    _initialize_model_mapping(_config)

    # Create clients
    azure_openai_client = _create_sync_client(_config)
    azure_openai_async_client = _create_async_client(_config)
    azure_openai_embedding_client = _create_embedding_client(_config)
    azure_openai_async_embedding_client = _create_async_embedding_client(_config)

    # Log configuration at startup
    _config.log_configuration()
    logger.info("Azure OpenAI clients initialized successfully")

except ValueError as e:
    # Re-raise with clear error message for fail-fast behavior
    logger.critical(f"Failed to initialize Azure OpenAI: {e}")
    raise


# =============================================================================
# Validation Function
# =============================================================================


async def validate_azure_connection() -> dict:
    """
    Validate the Azure OpenAI connection by making a simple API call.

    Returns:
        Dict with validation status and details

    Raises:
        Exception if connection fails
    """
    try:
        # Test chat completion
        response = azure_openai_client.chat.completions.create(
            model=_config.deployment_chat_mini,
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=5,
        )
        chat_ok = response.choices[0].message.content is not None

        # Test embeddings
        embed_response = azure_openai_embedding_client.embeddings.create(
            model=_config.deployment_embedding,
            input="test",
        )
        embedding_ok = len(embed_response.data[0].embedding) > 0

        return {
            "status": "healthy" if (chat_ok and embedding_ok) else "degraded",
            "chat_completion": "ok" if chat_ok else "failed",
            "embeddings": "ok" if embedding_ok else "failed",
            "endpoint": _config.endpoint,
            "deployments": {
                "chat": _config.deployment_chat,
                "chat_mini": _config.deployment_chat_mini,
                "embedding": _config.deployment_embedding,
            },
        }
    except Exception as e:
        logger.error(f"Azure OpenAI validation failed: {e}")
        raise


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Clients
    "azure_openai_client",
    "azure_openai_async_client",
    "azure_openai_embedding_client",
    "azure_openai_async_embedding_client",
    # Deployment name helpers
    "get_deployment_name",
    "get_chat_deployment",
    "get_chat_mini_deployment",
    "get_embedding_deployment",
    "get_chat_api_version",
    "get_embedding_api_version",
    # Validation
    "validate_azure_connection",
]
