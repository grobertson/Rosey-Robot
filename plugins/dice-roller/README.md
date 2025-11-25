# Dice Roller Plugin

Roll dice and flip coins in chat. A simple, stateless plugin that demonstrates the NATS-based plugin architecture.

## Features

- **!roll** - Roll dice using standard notation (XdY, XdY+Z, XdY-Z)
- **!flip** - Flip a coin (Heads/Tails)
- Event emission for analytics
- Configurable limits

## Installation

This plugin runs as a separate process communicating via NATS.

```bash
# Install dependencies
pip install nats-py

# Run the plugin
python -m plugins.dice_roller
```

## Usage

### Commands

```text
!roll 2d6      -> 🎲 [4, 3] = 7
!roll d20+5    -> 🎲 [17] + 5 = 22
!roll 4d6-2    -> 🎲 [6, 4, 3, 2] - 2 = 13
!flip          -> 🪙 Heads!
```

### Dice Notation

| Notation | Description |
|----------|-------------|
| `d6` | Roll one 6-sided die |
| `2d6` | Roll two 6-sided dice |
| `d20+5` | Roll d20 and add 5 |
| `3d8-2` | Roll 3d8 and subtract 2 |

## Configuration

Create or edit `config.json`:

```json
{
  "max_dice": 20,
  "max_sides": 1000,
  "max_modifier": 100,
  "emit_events": true
}
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `max_dice` | 20 | Maximum number of dice per roll |
| `max_sides` | 1000 | Maximum sides per die |
| `max_modifier` | 100 | Maximum modifier value (absolute) |
| `emit_events` | true | Emit analytics events |

## NATS Subjects

### Commands (Subscribe)

| Subject | Purpose |
|---------|---------|
| `rosey.command.dice.roll` | Handle !roll commands |
| `rosey.command.dice.flip` | Handle !flip commands |

### Events (Publish)

| Subject | Purpose |
|---------|---------|
| `rosey.event.dice.rolled` | Analytics for dice rolls |
| `rosey.event.dice.flipped` | Analytics for coin flips |

## Message Formats

### Roll Request

```json
{
  "channel": "#general",
  "user": "alice",
  "args": "2d6+5"
}
```

### Roll Response

```json
{
  "success": true,
  "result": {
    "notation": "2d6+5",
    "rolls": [4, 3],
    "modifier": 5,
    "total": 12,
    "formatted": "🎲 [4, 3] + 5 = 12"
  }
}
```

### Error Response

```json
{
  "success": false,
  "error": "❌ Invalid dice notation"
}
```

### Roll Event

```json
{
  "timestamp": "2025-11-24T10:00:00Z",
  "channel": "#general",
  "user": "alice",
  "dice_count": 2,
  "dice_sides": 6,
  "modifier": 5,
  "rolls": [4, 3],
  "total": 12
}
```

## Development

### Running Tests

```bash
cd plugins/dice-roller
python -m pytest tests/ -v
```

### Test Coverage

```bash
python -m pytest tests/ --cov=. --cov-report=term-missing
```

### Files

```text
plugins/dice-roller/
├── __init__.py       # Package exports
├── plugin.py         # DiceRollerPlugin (NATS-based)
├── dice.py           # DiceParser, DiceRoll, DiceRoller
├── config.json       # Default configuration
├── README.md         # This file
└── tests/
    ├── conftest.py   # Test fixtures
    ├── test_dice.py  # Unit tests (52 tests)
    └── test_plugin.py # Integration tests (30 tests)
```

## License

MIT License - See project root LICENSE file.
