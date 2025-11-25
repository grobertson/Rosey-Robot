# LLM Plugin

LLM chat integration for Rosey-Robot with support for multiple providers, personas, and persistent memory.

## Features

- **Multiple Providers**: Ollama (local), OpenAI, OpenRouter
- **Conversation Context**: Per-channel conversation history
- **Persistent Memory**: NATS JetStream KeyValue storage for messages and memories
- **Personas**: Multiple response styles (default, concise, technical, creative)
- **NATS Integration**: Event-driven architecture with service interface
- **Memory Commands**: Remember facts, recall memories, forget entries
- **Plugin-Safe Architecture**: NO direct database access - all persistence via NATS

## Installation

1. Install dependencies:
```bash
pip install httpx nats-py
```

2. Configure your preferred provider in `config.json`

3. Enable the plugin in your bot configuration

## Configuration

### Basic Setup

```json
{
  "name": "llm",
  "enabled": true,
  "default_provider": "ollama",
  "service": {
    "max_context_messages": 10,
    "default_persona": "default"
  }
}
```

### Provider Configuration

#### Ollama (Local)

```json
{
  "providers": {
    "ollama": {
      "base_url": "http://localhost:11434",
      "timeout": 60.0,
      "default_model": "llama3.2"
    }
  }
}
```

**Setup**:
1. Install Ollama: https://ollama.ai
2. Pull a model: `ollama pull llama3.2`
3. Start Ollama server (usually automatic)

#### OpenAI

```json
{
  "providers": {
    "openai": {
      "api_key": "sk-...",
      "base_url": "https://api.openai.com/v1",
      "organization": "",
      "timeout": 60.0,
      "default_model": "gpt-4",
      "max_retries": 2
    }
  }
}
```

**Setup**:
1. Get API key from https://platform.openai.com/api-keys
2. Add to `api_key` field
3. (Optional) Set organization ID

#### OpenRouter

```json
{
  "providers": {
    "openrouter": {
      "api_key": "sk-or-...",
      "base_url": "https://openrouter.ai/api/v1",
      "site_url": "https://your-site.com",
      "site_name": "Rosey-Robot",
      "timeout": 60.0,
      "default_model": "anthropic/claude-3-sonnet"
    }
  }
}
```

**Setup**:
1. Get API key from https://openrouter.ai/keys
2. Add to `api_key` field
3. (Optional) Set site_url and site_name for rankings

## Usage

### User Commands

#### Chat with LLM
```
!chat Hello, how are you?
!chat What is Python?
!chat Tell me about quantum computing
```

#### Reset Context
Clear conversation history:
```
!chat reset
```

#### Change Persona
Switch between response styles:
```
!chat persona              # List available personas
!chat persona concise      # Brief responses
!chat persona technical    # Detailed technical responses
!chat persona creative     # Engaging, creative responses
!chat persona default      # Back to default
```

#### Help
```
!chat help
```

### Memory Commands

#### Remember Facts
Store information for later recall:
```
!chat remember Alice likes Python programming
!chat remember The bot was deployed on November 25, 2025
!chat remember Project deadline is December 1st
```

#### Recall Memories
Search stored memories by keyword:
```
!chat recall Alice
!chat recall Python
!chat recall deadline
```

#### Forget Memories
Remove a specific memory by ID:
```
!chat forget abc12345
```

**Note**: Memory IDs are shown when you remember facts and in recall results.

### Service Interface (Plugin-to-Plugin)

Other plugins can use the LLM service through NATS:

#### Chat Request
```python
# Publish to llm.request
request = {
    "action": "chat",
    "channel_id": "my-channel",
    "message": "What is Python?",
    "username": "User",
    "model": "llama3.2",        # Optional
    "temperature": 0.7,          # Optional
    "max_tokens": 100            # Optional
}
await nc.publish("llm.request", json.dumps(request).encode())

# Subscribe to llm.response
async def handle_response(msg):
    data = json.loads(msg.data.decode())
    print(data["content"])
```

#### Raw Completion
```python
request = {
    "action": "complete",
    "channel_id": "my-channel",
    "message": "Complete this sentence: Python is",
    "temperature": 0.5
}
await nc.publish("llm.request", json.dumps(request).encode())
```

#### Reset Context
```python
request = {
    "action": "reset",
    "channel_id": "my-channel"
}
await nc.publish("llm.request", json.dumps(request).encode())
```

### NATS Subjects

- **rosey.command.chat**: User commands (!chat)
- **rosey.command.chat.remember**: Remember fact command
- **rosey.command.chat.recall**: Recall memories command
- **rosey.command.chat.forget**: Forget memory command
- **llm.request**: Service requests from other plugins
- **llm.response**: Chat/completion responses
- **llm.error**: Error notifications

## Architecture

### Memory Storage (NATS JetStream KV)

The LLM plugin uses **NATS JetStream KeyValue** store for all persistence, adhering to the plugin-safe architecture principle:

**✅ Correct**: Plugins use NATS KV for storage  
**❌ Incorrect**: Plugins never access database directly

#### NATS KV Buckets

**llm_data**: Single bucket for all LLM storage
- **messages:{channel}:recent**: Recent conversation messages (JSON array)
- **memories:{channel}:{id}**: Individual memories (JSON objects)
- **user:{user_id}:context**: User preferences (JSON)

#### Data Structures

```python
# Message storage
{
    "role": "user" | "assistant" | "system",
    "content": "message text",
    "user_id": "username",
    "timestamp": "2025-11-25T12:00:00"
}

# Memory storage
{
    "id": "abc12345",
    "content": "fact or memory text",
    "category": "fact" | "preference" | "topic",
    "importance": 1-5,
    "user_id": "username",
    "created_at": "2025-11-25T12:00:00",
    "accessed_at": "2025-11-25T13:00:00"
}
```

#### Benefits of NATS KV

1. **Plugin-Safe**: No direct database coupling
2. **Distributed**: Works across NATS cluster
3. **Lightweight**: Simple key-value operations
4. **Isolated**: Per-channel data separation
5. **Versioned**: JetStream provides history tracking

#### Memory Operations

```python
# ConversationMemory API (internal)
await memory.add_message(channel, role, content, user_id)
messages = await memory.get_recent_messages(channel, limit=20)
await memory.reset_context(channel)

memory_id = await memory.remember(channel, content, category, importance)
memories = await memory.recall(channel, query, limit=5)
await memory.forget(channel, memory_id)
```

## Personas

### Default
Friendly, conversational, balanced responses. Good for general chat.

### Concise
Brief, to-the-point responses. Use when you want quick answers.

### Technical
Detailed, precise technical explanations. Best for programming, systems, and technical topics.

### Creative
Engaging, imaginative responses with vivid language. Makes topics more interesting.

## Development

### Project Structure

```
plugins/llm/
├── __init__.py           # Package exports
├── plugin.py             # NATS plugin (commands, service interface, memory)
├── service.py            # LLMService (chat interface, context management)
├── prompts.py            # System prompts for personas
├── memory.py             # ConversationMemory (NATS KV storage)
├── summarizer.py         # ConversationSummarizer (LLM-based)
├── config.json           # Default configuration
├── README.md             # This file
├── providers/
│   ├── __init__.py       # Provider exports
│   ├── base.py           # Abstract base class and types
│   ├── ollama.py         # Ollama provider
│   ├── openai.py         # OpenAI provider
│   └── openrouter.py     # OpenRouter provider
└── tests/
    ├── __init__.py
    ├── test_providers.py # Provider tests
    ├── test_service.py   # Service tests
    ├── test_memory.py    # Memory system tests (NATS KV)
    └── test_plugin.py    # Plugin integration tests
```

### Running Tests

```bash
# All LLM tests
pytest plugins/llm/tests/ -v

# Specific test file
pytest plugins/llm/tests/test_providers.py -v

# With coverage
pytest plugins/llm/tests/ --cov=plugins.llm --cov-report=html
```

### Adding a New Provider

1. Create `providers/my_provider.py`:
```python
from .base import LLMProvider, CompletionRequest, CompletionResponse

class MyProvider(LLMProvider):
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        # Implementation
        pass
    
    async def chat(self, messages, model, temperature=0.7, max_tokens=None, stream=False):
        # Implementation
        pass
    
    async def stream(self, request: CompletionRequest):
        # Implementation
        pass
    
    async def is_available(self) -> bool:
        # Implementation
        pass
```

2. Export in `providers/__init__.py`
3. Add to `service.py` provider_classes dict
4. Add configuration to `config.json`
5. Write tests in `tests/test_providers.py`

## Troubleshooting

### Ollama Not Available
```
Provider ollama is not available. Plugin will be limited.
```

**Solutions**:
- Check Ollama is running: `ollama list`
- Verify base_url in config matches Ollama server
- Test manually: `curl http://localhost:11434/api/tags`

### OpenAI/OpenRouter Errors
```
OpenAI API error: 401 Unauthorized
```

**Solutions**:
- Verify API key is correct
- Check API key has credits/quota
- Confirm base_url is correct

### Context Not Reset
```
Old messages still appearing
```

**Solutions**:
- Use `!chat reset` to clear context
- Check channel_id is correct in requests
- Restart bot to clear all contexts

## Migration from lib/llm

This plugin replaces the old `lib/llm/` module:

**Old**:
```python
from lib.llm.client import LLMClient

client = LLMClient(provider="ollama", config={...})
response = await client.chat("Hello", user_id="123")
```

**New**:
```python
from plugins.llm import LLMService, OllamaProvider

provider = OllamaProvider(config={...})
service = LLMService(provider=provider)
response = await service.chat("Hello", channel_id="main")
```

**Key Changes**:
- Context is per-channel instead of per-user
- NATS integration for plugin architecture
- Enhanced provider interface with streaming
- Multiple personas
- Service interface for plugin-to-plugin communication

## Future Enhancements (Planned Sorties)

- **Sortie 5**: Streaming responses
- **Sortie 6**: Advanced features (function calling, embeddings)
- **Sortie 7**: Performance optimization (caching, batching)
- **Sortie 8**: Monitoring and analytics

## License

Part of Rosey-Robot project. See main LICENSE file.

## Support

- Issues: https://github.com/grobertson/Rosey-Robot/issues
- Docs: See `docs/sprints/19-core-migration/`
- Chat: Join the community channel
