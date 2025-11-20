# LLM Configuration Guide

Complete guide for configuring LLM (Large Language Model) integration in Rosey bot.

## Table of Contents

- [Overview](#overview)
- [Providers](#providers)
  - [OpenAI](#openai)
  - [Azure OpenAI](#azure-openai)
  - [Ollama (Local)](#ollama-local)
  - [Ollama (Remote)](#ollama-remote)
  - [OpenRouter](#openrouter)
  - [LocalAI / LM Studio](#localai--lm-studio)
- [Trigger Configuration](#trigger-configuration)
- [Advanced Configuration](#advanced-configuration)
- [Troubleshooting](#troubleshooting)

---

## Overview

Rosey supports multiple LLM providers for generating AI-powered chat responses. All configuration is managed through `config.json`.

**Key Features:**
- Multiple provider support (OpenAI, Ollama, OpenRouter)
- Flexible trigger system (mentions, commands, keywords, ambient chat)
- Per-user conversation context
- Rate limiting and cooldowns
- Production-ready with systemd

---

## Providers

### OpenAI

Use OpenAI's GPT models (GPT-4, GPT-3.5-turbo, etc.).

**Configuration:**
```json
{
  "llm": {
    "enabled": true,
    "provider": "openai",
    "openai": {
      "api_key": "sk-YOUR_API_KEY_HERE",
      "model": "gpt-4o-mini"
    },
    "system_prompt_file": "prompt.md",
    "max_context_messages": 10,
    "temperature": 0.7,
    "max_tokens": 500
  }
}
```

**Setup:**
1. Get API key from [OpenAI Platform](https://platform.openai.com/api-keys)
2. Add to `config.json`
3. Install dependency: `pip install "openai>=1.0.0"`

**Recommended Models:**
- `gpt-4o-mini` - Fast, affordable, great for chat (✅ **Recommended**)
- `gpt-4o` - Latest GPT-4, multimodal
- `gpt-4-turbo` - Previous generation, still excellent
- `gpt-3.5-turbo` - Fastest, cheapest

**Cost Estimates (as of 2025):**
- `gpt-4o-mini`: ~$0.15 per 1M input tokens, ~$0.60 per 1M output tokens
- `gpt-4o`: ~$2.50 per 1M input tokens, ~$10 per 1M output tokens

---

### Azure OpenAI

Use OpenAI models hosted on Microsoft Azure.

**Configuration:**
```json
{
  "llm": {
    "enabled": true,
    "provider": "openai",
    "openai": {
      "api_key": "YOUR_AZURE_API_KEY",
      "model": "gpt-4",
      "base_url": "https://YOUR-RESOURCE.openai.azure.com/openai/deployments/YOUR-DEPLOYMENT",
      "organization": null
    }
  }
}
```

**Setup:**
1. Create Azure OpenAI resource
2. Deploy a model (creates deployment name)
3. Get API key and endpoint from Azure portal
4. Update `base_url` with your resource and deployment names

**URL Format:**
```
https://{resource-name}.openai.azure.com/openai/deployments/{deployment-name}
```

---

### Ollama (Local)

Run models locally on your server (no API costs!).

**Configuration:**
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

**Setup:**
1. Install Ollama: `curl https://ollama.ai/install.sh | sh`
2. Start server: `ollama serve` (or use systemd)
3. Pull model: `ollama pull llama3`
4. Verify: `curl http://localhost:11434/api/tags`

**Recommended Models:**
- `llama3:8b` - Fast, 4-8GB RAM (✅ **Recommended for local**)
- `llama3:70b` - Better quality, needs 48GB+ RAM or GPU
- `mistral` - Fast alternative, 4GB RAM
- `phi3` - Very small, 2GB RAM, good for testing

**System Requirements:**
- **CPU-only:** 8GB+ RAM for 8B models, 16GB+ recommended
- **With GPU:** NVIDIA GPU with 6GB+ VRAM significantly improves speed

---

### Ollama (Remote)

Run Ollama on a separate GPU server, connect bot from another machine.

**Configuration (Bot Server):**
```json
{
  "llm": {
    "enabled": true,
    "provider": "ollama",
    "ollama": {
      "base_url": "http://192.168.1.100:11434",
      "model": "llama3:70b"
    }
  }
}
```

**Setup:**

**On GPU Server:**
```bash
# Install Ollama
curl https://ollama.ai/install.sh | sh

# Configure to listen on all interfaces
# Edit /etc/systemd/system/ollama.service (if using systemd)
# Or set environment: OLLAMA_HOST=0.0.0.0:11434

# Start service
systemctl start ollama

# Pull large model (70B recommended for GPU server)
ollama pull llama3:70b

# Verify listening
netstat -tlnp | grep 11434
```

**On Bot Server:**
- Update `config.json` with GPU server IP
- Test connection: `curl http://GPU_SERVER_IP:11434/api/tags`
- Start bot

**Firewall Configuration:**
```bash
# On GPU server, allow bot server IP
sudo ufw allow from BOT_SERVER_IP to any port 11434
```

---

### OpenRouter

Access multiple model providers (OpenAI, Anthropic, Google, Meta, etc.) through one API.

**Configuration:**
```json
{
  "llm": {
    "enabled": true,
    "provider": "openrouter",
    "openrouter": {
      "api_key": "sk-or-v1-YOUR_KEY_HERE",
      "model": "anthropic/claude-3-haiku",
      "site_url": "https://your-site.com",
      "site_name": "Rosey CyTube Bot"
    }
  }
}
```

**Setup:**
1. Get API key from [OpenRouter](https://openrouter.ai/)
2. Add credits to account
3. Choose model from [OpenRouter models](https://openrouter.ai/models)

**Popular Models:**
- `anthropic/claude-3-haiku` - Fast, cheap, excellent quality
- `anthropic/claude-3-5-sonnet` - Best quality, slower
- `meta-llama/llama-3-8b-instruct` - Open source, cheap
- `google/gemini-pro` - Google's model

**Benefits:**
- Single API for many providers
- Automatic fallback if provider is down
- No need to manage multiple API keys

---

### LocalAI / LM Studio

Use local models with OpenAI-compatible servers.

**Configuration:**
```json
{
  "llm": {
    "enabled": true,
    "provider": "openai",
    "openai": {
      "api_key": "not-needed",
      "model": "local-model-name",
      "base_url": "http://localhost:1234/v1"
    }
  }
}
```

**LocalAI Setup:**
```bash
# Install LocalAI
curl https://localai.io/install.sh | sh

# Start with model
localai run llama3

# API endpoint: http://localhost:8080/v1
```

**LM Studio Setup:**
1. Download [LM Studio](https://lmstudio.ai/)
2. Download a model (e.g., Llama 3)
3. Start local server (default port: 1234)
4. Use `http://localhost:1234/v1` as `base_url`

---

## Trigger Configuration

Control when the bot responds with LLM-generated text.

### Basic Triggers

**Direct Mentions:**
```json
{
  "llm": {
    "triggers": {
      "enabled": true,
      "direct_mention": true
    }
  }
}
```

User says: `"hey CynthiaRothbot, what's the weather?"`  
Bot responds with LLM.

**Commands:**
```json
{
  "llm": {
    "triggers": {
      "enabled": true,
      "commands": ["!ai", "!ask", "!rosey"]
    }
  }
}
```

User says: `"!ai tell me a joke"`  
Bot responds with LLM.

### Advanced Triggers

**Keyword Triggers with Probability:**
```json
{
  "llm": {
    "triggers": {
      "keywords": [
        {
          "phrases": ["toddy", "the toddy"],
          "probability": 0.1,
          "cooldown_seconds": 300
        },
        {
          "phrases": ["boobs", "boobies"],
          "probability": 0.05,
          "cooldown_seconds": 600
        }
      ]
    }
  }
}
```

- Bot has 10% chance to respond when "toddy" is mentioned
- Only responds once every 5 minutes per keyword (cooldown)
- Useful for creating personality without being annoying

**Ambient Chat (Periodic):**
```json
{
  "llm": {
    "triggers": {
      "ambient_chat": {
        "enabled": true,
        "every_n_messages": 20,
        "randomness": 0.5
      }
    }
  }
}
```

- Bot responds roughly every 20 messages
- `randomness: 0.5` means it will vary between 10-30 messages
- Creates feeling of bot being "part of the conversation"

**Greeting System:**
```json
{
  "llm": {
    "triggers": {
      "greetings": {
        "enabled": true,
        "on_join": {
          "enabled": true,
          "probability": 0.2,
          "idle_threshold_minutes": 60,
          "moderators_only": false,
          "specific_users": {
            "alice": 1.0,
            "bob": 0.5
          }
        }
      }
    }
  }
}
```

- 20% chance to greet users when they join
- Only greets if they've been idle for 60+ minutes
- Always greets "alice", 50% chance for "bob"

---

## Advanced Configuration

### System Prompt

Define bot personality:

**Create `prompt.md`:**
```markdown
You are Rosey, a friendly and helpful bot in a CyTube channel.

Personality traits:
- Casual and conversational
- Slightly sarcastic but never mean
- Loves talking about movies and TV shows
- Keeps responses brief (1-3 sentences usually)

Guidelines:
- Don't use emojis excessively
- Reference ongoing channel conversations when relevant
- Admit when you don't know something
```

**In config.json:**
```json
{
  "llm": {
    "system_prompt_file": "prompt.md"
  }
}
```

### Context Window

Control conversation memory:

```json
{
  "llm": {
    "max_context_messages": 10
  }
}
```

- Bot remembers last 10 messages per user
- Higher = more context = better responses but slower/costlier
- Lower = faster/cheaper but less context
- Recommended: 5-10 for chat, 20+ for complex tasks

### Temperature & Creativity

```json
{
  "llm": {
    "temperature": 0.7,
    "max_tokens": 500
  }
}
```

**Temperature:**
- `0.0` - Deterministic, factual, boring
- `0.5` - Balanced
- `0.7` - Creative, natural (✅ **Recommended**)
- `1.0` - Very creative, sometimes random
- `1.5+` - Chaotic, unpredictable

**Max Tokens:**
- `100` - Very short responses (1-2 sentences)
- `250` - Short responses (2-3 sentences) ✅ **Recommended**
- `500` - Medium responses (paragraph)
- `1000+` - Long responses (multiple paragraphs)

### Log-Only Mode

Test configuration without sending messages:

```json
{
  "llm": {
    "enabled": true,
    "log_only": true
  }
}
```

Bot will:
- Detect triggers normally
- Generate LLM responses
- Log responses instead of sending to channel
- Useful for testing triggers and responses

---

## Troubleshooting

### Bot Doesn't Respond

**Check triggers:**
```json
// Enable debug logging
{
  "log_level": "DEBUG",
  "llm": {
    "triggers": {
      "enabled": true,
      "direct_mention": true
    }
  }
}
```

Watch logs:
```bash
sudo journalctl -u cytube-bot -f | grep -i "trigger\|llm"
```

**Common issues:**
- Bot name not mentioned correctly (case-sensitive)
- Command not in `commands` list
- Ambient chat disabled
- Cooldown active (check `cooldown_seconds`)

### OpenAI Errors

**401 Unauthorized:**
- Invalid API key
- Check key starts with `sk-`
- Verify key at [OpenAI Platform](https://platform.openai.com/api-keys)

**429 Rate Limit:**
- Too many requests
- Check OpenAI usage limits
- Add rate limiting in triggers

**Insufficient Credits:**
- Add payment method to OpenAI account
- Check billing at [OpenAI Billing](https://platform.openai.com/account/billing)

### Ollama Errors

**Connection Refused:**
```bash
# Check if Ollama is running
systemctl status ollama
# or
curl http://localhost:11434/api/tags

# Start if needed
ollama serve
```

**Model Not Found:**
```bash
# List installed models
ollama list

# Pull missing model
ollama pull llama3
```

**Slow Responses:**
- Model too large for available RAM/VRAM
- Try smaller model: `ollama pull llama3:8b`
- Or use GPU server setup

**Remote Ollama Connection:**
```bash
# Test connectivity
telnet GPU_SERVER_IP 11434
curl http://GPU_SERVER_IP:11434/api/tags

# Check firewall
sudo ufw status
sudo ufw allow from BOT_IP to any port 11434
```

### Performance Issues

**Slow responses:**
- Reduce `max_tokens` (try 250)
- Lower `max_context_messages` (try 5)
- Use faster model (gpt-4o-mini, llama3:8b)
- Use GPU for local models

**High API costs:**
- Use cheaper model (gpt-4o-mini instead of gpt-4o)
- Add stricter triggers (lower probability)
- Increase cooldowns
- Reduce `max_tokens`
- Use Ollama (free, local)

**High memory usage:**
- Lower `max_context_messages`
- Restart bot periodically (clears context history)
- Use smaller Ollama models

### Config Errors

**Invalid JSON:**
```bash
# Validate JSON syntax
python -m json.tool bot/rosey/config.json
```

**Provider Not Found:**
- Check `"provider"` spelling: must be `"openai"`, `"ollama"`, or `"openrouter"`
- Ensure corresponding section exists (`"openai": {...}`)

**Import Errors:**
```bash
# Missing dependencies
pip install -r requirements.txt

# Specific providers
pip install "openai>=1.0.0"  # For OpenAI
pip install "aiohttp>=3.9.0"  # For all providers
```

---

## Examples

### Minimal Configuration (OpenAI)

```json
{
  "domain": "https://cytu.be",
  "channel": "MyChannel",
  "user": ["BotName", "password"],
  "llm": {
    "enabled": true,
    "provider": "openai",
    "openai": {
      "api_key": "sk-YOUR_KEY",
      "model": "gpt-4o-mini"
    },
    "triggers": {
      "enabled": true,
      "direct_mention": true
    }
  }
}
```

### Complete Configuration (All Features)

```json
{
  "domain": "https://cytu.be",
  "channel": "MyChannel",
  "user": ["Rosey", "password"],
  "log_level": "INFO",
  "llm": {
    "enabled": true,
    "provider": "openai",
    "system_prompt_file": "prompt.md",
    "max_context_messages": 10,
    "temperature": 0.7,
    "max_tokens": 250,
    "log_only": false,
    "openai": {
      "api_key": "sk-YOUR_KEY",
      "model": "gpt-4o-mini"
    },
    "triggers": {
      "enabled": true,
      "direct_mention": true,
      "commands": ["!ai", "!ask"],
      "ambient_chat": {
        "enabled": true,
        "every_n_messages": 25,
        "randomness": 0.5
      },
      "keywords": [
        {
          "phrases": ["interesting topic"],
          "probability": 0.15,
          "cooldown_seconds": 300
        }
      ],
      "greetings": {
        "enabled": true,
        "on_join": {
          "enabled": true,
          "probability": 0.2,
          "idle_threshold_minutes": 60
        }
      }
    }
  }
}
```

---

## Additional Resources

- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Ollama Documentation](https://ollama.ai/docs)
- [OpenRouter Documentation](https://openrouter.ai/docs)
- [Rosey Bot README](../README.md)
- [Systemd Deployment Guide](../systemd/README.md)
