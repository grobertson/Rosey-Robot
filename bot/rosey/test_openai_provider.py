#!/usr/bin/env python3
"""
Quick test script for OpenAI provider.

Tests that the OpenAIProvider can be instantiated and has the correct structure.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from lib.llm import OpenAIProvider, LLMClient


def test_openai_provider_init():
    """Test OpenAI provider initialization."""
    print("Testing OpenAI provider initialization...")

    # Test with minimal config
    config = {
        'api_key': 'sk-test-key',
        'model': 'gpt-4o-mini'
    }

    provider = OpenAIProvider(config)
    assert provider.api_key == 'sk-test-key'
    assert provider.model == 'gpt-4o-mini'
    assert provider.base_url == 'https://api.openai.com/v1'
    print("✓ Basic initialization works")

    # Test with custom base_url (e.g., LocalAI)
    config_localai = {
        'api_key': 'not-needed',
        'model': 'llama-3',
        'base_url': 'http://localhost:8080/v1'
    }

    provider_localai = OpenAIProvider(config_localai)
    assert provider_localai.base_url == 'http://localhost:8080/v1'
    print("✓ Custom base_url (LocalAI/LM Studio) works")

    # Test missing api_key raises error
    try:
        OpenAIProvider({})
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert 'api_key' in str(e)
        print("✓ Missing api_key raises error")


def test_llm_client_openai():
    """Test LLMClient with OpenAI provider."""
    print("\nTesting LLMClient with OpenAI provider...")

    config = {
        'provider': 'openai',
        'openai': {
            'api_key': 'sk-test-key',
            'model': 'gpt-4o-mini'
        },
        'max_context_messages': 10,
        'temperature': 0.7
    }

    client = LLMClient(config)
    assert client.provider_name == 'openai'
    assert isinstance(client.provider, OpenAIProvider)
    print("✓ LLMClient initializes with OpenAI provider")


def test_all_providers():
    """Test that all three providers can coexist."""
    print("\nTesting all three providers...")

    from lib.llm import OllamaProvider, OpenRouterProvider

    # OpenAI
    openai_config = {'api_key': 'sk-test', 'model': 'gpt-4'}
    OpenAIProvider(openai_config)
    print("✓ OpenAI provider created")

    # Ollama
    ollama_config = {'base_url': 'http://localhost:11434', 'model': 'llama3'}
    OllamaProvider(ollama_config)
    print("✓ Ollama provider created")

    # OpenRouter
    openrouter_config = {
        'api_key': 'sk-test',
        'model': 'anthropic/claude-3-haiku'
    }
    OpenRouterProvider(openrouter_config)
    print("✓ OpenRouter provider created")

    print("✓ All three providers can coexist")


if __name__ == '__main__':
    print("=" * 60)
    print("OpenAI Provider Test Suite")
    print("=" * 60)

    try:
        test_openai_provider_init()
        test_llm_client_openai()
        test_all_providers()

        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        print("\nOpenAI provider is ready to use. Configuration examples:")
        print("\n# Standard OpenAI:")
        print('{"provider": "openai", "openai": {"api_key": "sk-...", "model": "gpt-4o-mini"}}')
        print("\n# Azure OpenAI:")
        print('{"provider": "openai", "openai": {"api_key": "...", "model": "gpt-4",')
        print(' "base_url": "https://YOUR-RESOURCE.openai.azure.com/openai/deployments/YOUR-DEPLOYMENT"}}')
        print("\n# LocalAI/LM Studio:")
        print('{"provider": "openai", "openai": {"api_key": "not-needed", "model": "local-model",')
        print(' "base_url": "http://localhost:1234/v1"}}')

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
