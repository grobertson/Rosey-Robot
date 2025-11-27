#!/usr/bin/env python3
"""
Test script for LLM integration.

Run this to verify your LLM setup is working before integrating with Rosey.
"""

import sys
from pathlib import Path
import asyncio

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from lib.llm import LLMClient  # noqa: E402


async def test_ollama():
    """Test Ollama provider."""
    print("\n=== Testing Ollama Provider ===")

    config = {
        'provider': 'ollama',
        'ollama': {
            'base_url': 'http://localhost:11434',
            'model': 'llama3'
        },
        'system_prompt_file': 'prompt.md',
        'temperature': 0.7,
        'max_tokens': 100
    }

    try:
        async with LLMClient(config) as client:
            print("✓ Client initialized")

            # Test simple generation
            response = await client.generate("Say hello in a single sentence.")
            print(f"✓ Generate: {response[:100]}...")

            # Test chat with context
            print("\n--- Chat conversation ---")
            resp1 = await client.chat("alice", "What's your name?")
            print("User: What's your name?")
            print(f"Bot: {resp1}")

            resp2 = await client.chat("alice", "What did I just ask you?")
            print("\nUser: What did I just ask you?")
            print(f"Bot: {resp2}")

            print("\n✓ Ollama tests passed!")

    except Exception as e:
        print(f"✗ Ollama test failed: {e}")
        return False

    return True


async def test_openrouter():
    """Test OpenRouter provider."""
    print("\n=== Testing OpenRouter Provider ===")

    # Check for API key
    api_key = input("Enter your OpenRouter API key (or press Enter to skip): ").strip()
    if not api_key:
        print("⊘ Skipping OpenRouter test (no API key)")
        return True

    config = {
        'provider': 'openrouter',
        'openrouter': {
            'api_key': api_key,
            'model': 'anthropic/claude-3-haiku',
            'site_name': 'Rosey Test'
        },
        'system_prompt_file': 'prompt.md',
        'temperature': 0.7,
        'max_tokens': 100
    }

    try:
        async with LLMClient(config) as client:
            print("✓ Client initialized")

            # Test simple generation
            response = await client.generate("Say hello in a single sentence.")
            print(f"✓ Generate: {response[:100]}...")

            # Test chat with context
            print("\n--- Chat conversation ---")
            resp1 = await client.chat("bob", "What's 2+2?")
            print("User: What's 2+2?")
            print(f"Bot: {resp1}")

            resp2 = await client.chat("bob", "What did I just ask?")
            print("\nUser: What did I just ask?")
            print(f"Bot: {resp2}")

            print("\n✓ OpenRouter tests passed!")

    except Exception as e:
        print(f"✗ OpenRouter test failed: {e}")
        return False

    return True


async def main():
    """Run all tests."""
    print("LLM Integration Test Suite")
    print("=" * 50)

    results = []

    # Test Ollama
    results.append(await test_ollama())

    # Test OpenRouter
    results.append(await test_openrouter())

    # Summary
    print("\n" + "=" * 50)
    if all(results):
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
