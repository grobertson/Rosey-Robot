# Trivia Plugin

Interactive trivia game plugin using the Open Trivia Database (OpenTDB).

## Features

- **Multiple-choice questions** from OpenTDB API
- **Per-channel games** - each channel can have one active game
- **Time-based scoring** - faster answers earn more points
- **Configurable settings** - customize timing and scoring
- **Real-time events** - NATS events for all game actions

## Commands

| Command | Description |
|---------|-------------|
| `!trivia start [N]` | Start a game with N questions (default: 10, max: 50) |
| `!trivia stop` | End the current game early |
| `!a <answer>` | Submit an answer (letter or full text) |
| `!trivia skip` | Skip the current question |

## Usage Examples

### Starting a Game

```
User: !trivia start
Rosey: 🎯 Trivia starting! 10 questions, 30 seconds each.
       First question in 5 seconds...

User: !trivia start 5
Rosey: 🎯 Trivia starting! 5 questions, 30 seconds each.
       First question in 5 seconds...
```

### Answering Questions

```
Rosey: 📝 Question 1/10 (Easy - General Knowledge):

       What is the capital of France?

       A) London  B) Paris  C) Berlin  D) Madrid

       ⏱️ 30 seconds! Use !a <answer>

User: !a B
Rosey: ✅ Correct! User got it in 3.2s! (+12 points)

User: !a Paris
Rosey: ✅ Correct! User got it in 4.1s! (+11 points)
```

### Game End

```
Rosey: 🏆 Game Over!

       🥇 Player1 - 95 points
       🥈 Player2 - 82 points
       🥉 Player3 - 45 points
```

## Configuration

Edit `config.json` to customize:

```json
{
  "time_per_question": 30,
  "start_delay": 5,
  "between_questions": 3,
  "max_questions": 50,
  "default_questions": 10,
  "points_decay": true,
  "emit_events": true
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `time_per_question` | int | 30 | Seconds to answer each question |
| `start_delay` | int | 5 | Seconds before first question |
| `between_questions` | int | 3 | Seconds between questions |
| `max_questions` | int | 50 | Maximum questions per game |
| `default_questions` | int | 10 | Default number if not specified |
| `points_decay` | bool | true | Faster answers = more points |
| `emit_events` | bool | true | Emit NATS events |

## Scoring

### Base Points by Difficulty

| Difficulty | Base Points |
|------------|-------------|
| Easy | 10 |
| Medium | 20 |
| Hard | 30 |

### Time Bonus (with points_decay enabled)

- **Instant answer**: Up to 1.5x base points
- **Slow answer**: Minimum 0.5x base points
- Points scale linearly based on time taken

## NATS Subjects

### Commands (Subscribe)

| Subject | Purpose |
|---------|---------|
| `rosey.command.trivia.start` | Start a new game |
| `rosey.command.trivia.stop` | Stop current game |
| `rosey.command.trivia.answer` | Submit answer |
| `rosey.command.trivia.skip` | Skip question |

### Events (Publish)

| Subject | Purpose |
|---------|---------|
| `trivia.game.started` | Game has started |
| `trivia.question.asked` | New question posed |
| `trivia.answer.correct` | Correct answer submitted |
| `trivia.answer.incorrect` | Wrong answer submitted |
| `trivia.question.timeout` | Time expired on question |
| `trivia.question.skipped` | Question was skipped |
| `trivia.game.ended` | Game has ended |

## Game Flow

```
IDLE ──(start)──► STARTING ──(delay)──► QUESTION_ACTIVE
                                              │
                    ┌─────────────────────────┤
                    │                         │
              (correct answer)          (timeout/skip)
                    │                         │
                    └──► BETWEEN_QUESTIONS ◄──┘
                              │
                       (next question)
                              │
                    (has more)─┴─(last)
                        │           │
                        ▼           ▼
                  QUESTION_ACTIVE  ENDING ──► IDLE
```

## Answer Formats

The following answer formats are accepted:

1. **Letter answer**: `!a B` or `!a b`
2. **Full text**: `!a Paris`
3. **Case insensitive**: `!a PARIS`, `!a paris`
4. **Fuzzy matching**: Minor typos are tolerated

For True/False questions:
- `true`, `t`, `yes`, `y`, `1`, `A`
- `false`, `f`, `no`, `n`, `0`, `B`

## Requirements

- Python 3.9+
- httpx (for API requests)
- nats-py (for NATS messaging)

## API Source

Questions are sourced from the [Open Trivia Database](https://opentdb.com/),
a free community-contributed trivia question database.

## Future Enhancements (Sortie 6)

- Persistent scoring database
- All-time leaderboards
- User statistics
- Category selection
- Custom question sets
