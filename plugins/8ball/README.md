# 🎱 Magic 8-Ball Plugin

The Magic 8-Ball plugin brings fortune-telling fun to your chat with classic responses and Rosey's personality flair.

## Features

- **Classic 8-Ball**: All 20 original Magic 8-Ball responses
- **Rosey Personality**: Each response includes Rosey's unique flavor text
- **Rate Limiting**: Configurable cooldown prevents spam
- **Event Emission**: Analytics events for tracking usage

## Commands

### `!8ball <question>`

Consult the mystical 8-ball about your burning questions.

```
User: !8ball Will the movie tonight be good?
Rosey: 🎱 "Will the movie tonight be good?" — Signs point to yes. The vibes are immaculate.

User: !8ball Should I have another slice of pizza?
Rosey: 🎱 "Should I have another slice of pizza?" — It is certain. The cosmos smile upon you! ✨

User: !8ball Will I ever find true love?
Rosey: 🎱 "Will I ever find true love?" — Reply hazy, try again. The spirits are being coy today.
```

## Response Categories

The Magic 8-Ball has 20 responses in 3 categories, with probability distribution matching the original toy:

### Positive (50% - 10 responses)
- It is certain
- It is decidedly so
- Without a doubt
- Yes definitely
- You may rely on it
- As I see it, yes
- Most likely
- Outlook good
- Yes
- Signs point to yes

### Neutral (25% - 5 responses)
- Reply hazy, try again
- Ask again later
- Better not tell you now
- Cannot predict now
- Concentrate and ask again

### Negative (25% - 5 responses)
- Don't count on it
- My reply is no
- My sources say no
- Outlook not so good
- Very doubtful

## Rosey's Personality Flavors

Each category has unique flavor text that reflects Rosey's character:

**Positive:**
- The cosmos smile upon you! ✨
- Ooh, looking good!
- The vibes are immaculate.
- I like where this is going!
- The universe has spoken favorably!

**Neutral:**
- Hmm, the mists are cloudy...
- The spirits are being coy today.
- Even I can't see through this fog.
- The universe is buffering...
- *shakes ball dramatically*

**Negative:**
- Yikes. Sorry, friend.
- The spirits are skeptical...
- Oof. Maybe don't bet on that one.
- The universe winced a little.
- That's a big ol' nope from the cosmos.

## Configuration

Edit `config.json` to customize behavior:

```json
{
  "cooldown_seconds": 3,
  "emit_events": true,
  "require_question": true,
  "max_question_length": 100
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `cooldown_seconds` | int | 3 | Seconds between uses per user |
| `emit_events` | bool | true | Emit analytics events |
| `require_question` | bool | true | Require a question to be asked |
| `max_question_length` | int | 100 | Max displayed question length |

## NATS Integration

### Subjects

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `rosey.command.8ball.ask` | Subscribe | Handle !8ball commands |
| `rosey.event.8ball.consulted` | Publish | Analytics event |

### Request Format

```json
{
  "channel": "chat_room",
  "user": "username",
  "args": "Will I win the lottery?",
  "reply_to": "rosey.reply.abc123"
}
```

### Response Format

```json
{
  "success": true,
  "result": {
    "question": "Will I win the lottery?",
    "answer": "Don't count on it",
    "category": "negative",
    "flavor": "The spirits are skeptical...",
    "formatted": "🎱 \"Will I win the lottery?\" — Don't count on it. The spirits are skeptical..."
  }
}
```

### Event Format

```json
{
  "event": "8ball.consulted",
  "timestamp": "2025-11-24T12:00:00Z",
  "channel": "chat_room",
  "user": "username",
  "category": "negative"
}
```

## Programmatic Usage

The plugin provides a direct API for integration:

```python
from plugins.8ball import EightBallPlugin

# Initialize with NATS client
plugin = EightBallPlugin(nats_client)
await plugin.initialize()

# Direct API (bypasses NATS)
response = plugin.ask("Will it rain?")
print(response.answer)      # "Most likely"
print(response.category)    # Category.POSITIVE
print(response.flavor)      # "The vibes are immaculate."

# Formatted output
formatted = plugin.ask_formatted("Will it rain?")
print(formatted)  # 🎱 "Will it rain?" — Most likely. The vibes are immaculate.

# Cleanup
await plugin.shutdown()
```

## Testing

Run tests from the plugin directory:

```bash
cd plugins/8ball
pytest
```

Or with coverage:

```bash
pytest --cov=. --cov-report=term-missing
```

## Development

### Response Selection

The `ResponseSelector` class handles response selection with weighted probability:

```python
from responses import ResponseSelector, Category

selector = ResponseSelector()

# Random selection (matches 8-ball distribution)
response = selector.select()

# Force specific category (for testing)
response = selector.select_from_category(Category.POSITIVE)

# Deterministic testing with seeded RNG
import random
rng = random.Random(42)
selector = ResponseSelector(rng)
```

### Adding Custom Flavors

To add custom Rosey flavor text, edit `responses.py`:

```python
POSITIVE_FLAVORS.append("Your new flavor text here!")
```

## Version History

- **1.0.0** - Initial release with classic 8-ball and Rosey personality

## License

Part of the Rosey-Robot project.
