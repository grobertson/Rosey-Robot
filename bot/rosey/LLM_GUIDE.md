# LLM Integration Guide

## Overview

Rosey v0.2.0 includes built-in support for Large Language Model (LLM) integration, allowing the bot to have intelligent conversations with users in the channel.

## Supported Providers

### Ollama (Local or Remote Inference)

**Best for:**
- Privacy-conscious deployments
- No API costs per request
- Full control over the model
- Local or networked GPU servers
- Running multiple models simultaneously

**Requirements:**
- [Ollama](https://ollama.ai/) installed and running (local or remote)
- A downloaded model (e.g., `llama3`, `mistral`, `phi`)

**Setup (Local):**
```bash
# Install Ollama (see https://ollama.ai)
# Pull a model
ollama pull llama3

# Verify it's running
ollama list
```

**Setup (Remote/Network):**
```bash
# On the Ollama server, expose the service
# Edit /etc/systemd/system/ollama.service or set environment:
OLLAMA_HOST=0.0.0.0:11434

# Or use ollama serve with custom host
ollama serve --host 0.0.0.0:11434

# From your bot machine, test connectivity
curl http://your-ollama-server:11434/api/tags
```

### OpenRouter (Remote API)

**Best for:**
- No local GPU requirements
- Access to multiple models (Claude, GPT-4, etc.)
- Quick setup
- Pay-per-use pricing

**Requirements:**
- OpenRouter API key from [openrouter.ai](https://openrouter.ai)
- Internet connection

## Configuration

### Basic Setup

Add the `llm` section to your `config.json`:

```json
{
  "llm": {
    "enabled": true,
    "provider": "ollama",
    "system_prompt_file": "prompt.md",
    "max_context_messages": 10,
    "temperature": 0.7,
    "max_tokens": 500
  }
}
```

### Ollama Configuration

**Local Ollama:**
```json
{
  "llm": {
    "enabled": true,
    "provider": "ollama",
    "ollama": {
      "base_url": "http://localhost:11434",
      "model": "llama3"
    }
  }
}
```

**Remote Ollama Server:**
```json
{
  "llm": {
    "enabled": true,
    "provider": "ollama",
    "ollama": {
      "base_url": "http://192.168.1.100:11434",
      "model": "llama3"
    }
  }
}
```

**Multiple Models (different bots or contexts):**
Ollama can serve multiple models simultaneously. Just specify different models in different bot instances or contexts:
```json
"model": "llama3"      // For general chat
"model": "mistral"     // For a different bot instance
"model": "codellama"   // For code-related queries
```

**Available Models:**
- `llama3` - Meta's Llama 3 (recommended for general use)
- `llama3:70b` - Larger Llama 3 variant (better quality, slower)
- `mistral` - Mistral AI's model (good balance)
- `phi` - Microsoft's Phi model (smaller, faster)
- `codellama` - Specialized for code
- See `ollama list` on your Ollama server for all downloaded models

### OpenRouter Configuration

```json
{
  "llm": {
    "enabled": true,
    "provider": "openrouter",
    "openrouter": {
      "api_key": "sk-or-v1-...",
      "model": "anthropic/claude-3-haiku",
      "site_url": "https://your-channel.com",
      "site_name": "My CyTube Channel"
    }
  }
}
```

**Popular Models:**
- `anthropic/claude-3-haiku` - Fast, affordable Claude
- `anthropic/claude-3-sonnet` - Balanced performance
- `openai/gpt-3.5-turbo` - OpenAI's GPT-3.5
- `meta-llama/llama-3-8b` - Open source Llama 3
- See [OpenRouter models](https://openrouter.ai/models) for full list

## Configuration Parameters

### Core Settings

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | bool | false | Enable/disable LLM features |
| `provider` | string | "ollama" | Provider to use: "ollama" or "openrouter" |
| `system_prompt_file` | string | "prompt.md" | Path to personality prompt file |
| `max_context_messages` | int | 10 | Number of message pairs to remember |
| `temperature` | float | 0.7 | Creativity (0.0=deterministic, 1.0=creative) |
| `max_tokens` | int | 500 | Maximum response length |

### System Prompt

The `prompt.md` file defines Rosey's personality. Edit this to customize how the bot responds:

```markdown
You are Rosey, a helpful and friendly chat bot in a CyTube channel.

Your personality:
- Friendly and enthusiastic
- Knowledgeable about movies and videos
- Occasionally makes puns
- Never uses offensive language

Keep responses concise (1-3 sentences).
```

## Testing

Before integrating with the bot, test your LLM setup:

```bash
cd bot/rosey
python test_llm.py
```

This will verify:
- Provider connectivity
- Model availability
- Basic generation
- Conversation context

## Usage in Bot Code

### Basic Integration

```python
from bot.rosey.llm import LLMClient

# Initialize
llm_config = config.get('llm', {})
if llm_config.get('enabled'):
    llm_client = LLMClient(llm_config)
    await llm_client.__aenter__()

# In message handler
async def on_chat_message(event, data):
    username = data['username']
    message = data['msg']
    
    if message.startswith('!ai '):
        prompt = message[4:]
        response = await llm_client.chat(username, prompt)
        await bot.chat(response)
```

### Context Management

The client automatically maintains conversation history per user:

```python
# Each user has separate context
await llm_client.chat("alice", "What's your name?")
await llm_client.chat("alice", "What did I ask?")  # Remembers previous

await llm_client.chat("bob", "Hi!")  # Bob has different context

# Clear a user's context
llm_client.clear_conversation("alice")
```

## Performance Tips

### Ollama
- Use smaller models (`phi`, `mistral`) for faster responses
- GPU acceleration highly recommended
- Consider response timeout for channel usability

### OpenRouter
- `haiku` models are fastest and cheapest
- Set appropriate `max_tokens` to control costs
- Monitor usage at [openrouter.ai/activity](https://openrouter.ai/activity)

## Privacy & Safety

### Data Handling
- **Ollama (Local)**: All data stays on your machine, nothing sent externally
- **Ollama (Remote/LAN)**: Data sent to your Ollama server, stays on your network
- **OpenRouter**: Messages sent to their API (see their privacy policy)

### Content Filtering
- Implement rate limiting to prevent spam
- Add profanity filters if needed
- Monitor conversations for appropriate behavior
- Consider moderator-only access initially

### Cost Management
- Set `max_tokens` conservatively
- Implement per-user rate limits
- Monitor OpenRouter billing

## Troubleshooting

### Ollama Issues

**"Connection refused"**
- Ensure Ollama is running: `ollama serve`
- Check base_url matches Ollama's endpoint
- For remote servers: Verify firewall/network access
- Test with: `curl http://your-server:11434/api/tags`

**"Model not found"**
- Pull the model on the Ollama server: `ollama pull llama3`
- Verify with: `ollama list`
- Check spelling of model name in config

**Slow responses**
- Use a smaller model (`phi`, `mistral` vs `llama3:70b`)
- Ensure GPU acceleration is enabled on the server
- Reduce `max_tokens`
- For remote servers: Check network latency

### OpenRouter Issues

**"Invalid API key"**
- Verify key at [openrouter.ai/keys](https://openrouter.ai/keys)
- Check for typos in config.json

**"Rate limited"**
- Implement exponential backoff
- Add rate limiting per user
- Consider upgrading plan

**High costs**
- Switch to cheaper models (haiku, gpt-3.5-turbo)
- Reduce `max_tokens`
- Limit usage to moderators

## Next Steps

1. **Test the integration**: Run `test_llm.py`
2. **Customize personality**: Edit `prompt.md`
3. **Integrate with bot**: Add LLM calls to message handlers
4. **Monitor usage**: Watch for performance and costs
5. **Iterate**: Adjust based on user feedback

## Future Enhancements

- **Multiple personalities**: Different prompts for different contexts
- **Tool use**: Let Rosey control playlist, kick users, etc.
- **Memory**: Long-term memory beyond conversation context
- **Voice**: TTS integration for voice chat
- **Vision**: Image analysis for uploaded media
