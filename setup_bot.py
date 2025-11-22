#!/usr/bin/env python3
"""
Rosey Bot Setup Script

Interactive setup for deploying a fresh Rosey bot instance from a cloned repo.
Creates a configured bot ready to run.
"""

import argparse
import json
import sys
from pathlib import Path
from getpass import getpass


def get_input(prompt, default=None, password=False):
    """Get user input with optional default value."""
    if default:
        prompt = f"{prompt} [{default}]"
    prompt += ": "
    
    if password:
        value = getpass(prompt)
    else:
        value = input(prompt).strip()
    
    return value if value else default


def load_config_file(config_file):
    """Load configuration from a JSON file."""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Config file '{config_file}' not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in config file: {e}")
        sys.exit(1)


def interactive_setup():
    """Interactive configuration gathering."""
    print("=" * 60)
    print("Rosey Bot Interactive Setup")
    print("=" * 60)
    print()
    
    config = {}
    
    # Basic CyTube settings
    print("CyTube Connection Settings")
    print("-" * 40)
    config['domain'] = get_input("CyTube domain", "https://cytu.be")
    config['channel'] = get_input("Channel name (required)")
    if not config['channel']:
        print("Error: Channel name is required")
        sys.exit(1)
    
    print()
    
    # Bot credentials
    print("Bot Account Credentials")
    print("-" * 40)
    username = get_input("Bot username (required)")
    if not username:
        print("Error: Bot username is required")
        sys.exit(1)
    
    password = get_input("Bot password (required)", password=True)
    if not password:
        print("Error: Bot password is required")
        sys.exit(1)
    
    config['user'] = [username, password]
    print()
    
    # LLM settings
    print("LLM Configuration (Optional)")
    print("-" * 40)
    enable_llm = get_input("Enable LLM integration? (y/n)", "n").lower()
    
    if enable_llm in ['y', 'yes']:
        config['llm'] = {
            'enabled': True,
            'provider': 'ollama',
            'system_prompt_file': 'prompt.md',
            'max_context_messages': 10,
            'temperature': 0.7,
            'max_tokens': 500,
            'log_only': False
        }
        
        # Ollama settings
        print("\nOllama Settings:")
        ollama_url = get_input("Ollama base URL", "http://localhost:11434")
        ollama_model = get_input("Ollama model", "llama3")
        
        config['llm']['ollama'] = {
            'base_url': ollama_url,
            'model': ollama_model
        }
        
        # Trigger settings
        print("\nTrigger Settings:")
        config['llm']['triggers'] = {
            'enabled': True,
            'direct_mention': True,
            'commands': ['!ai', '!ask'],
            'ambient_chat': {
                'enabled': False,
                'every_n_messages': 20,
                'randomness': 0.5
            },
            'keywords': [],
            'greetings': {
                'enabled': False,
                'on_join': {
                    'enabled': True,
                    'probability': 0.2,
                    'idle_threshold_minutes': 60,
                    'moderators_only': False,
                    'specific_users': {}
                },
                'on_status_change': {
                    'enabled': False,
                    'probability': 0.1
                }
            }
        }
        
        # OpenRouter (optional alternative)
        config['llm']['openrouter'] = {
            'api_key': 'YOUR_OPENROUTER_API_KEY',
            'model': 'anthropic/claude-3-haiku',
            'site_url': 'https://your-site.com',
            'site_name': 'Rosey CyTube Bot'
        }
    else:
        config['llm'] = {'enabled': False}
    
    print()
    
    # Other settings with defaults
    config['response_timeout'] = 1
    config['restart_delay'] = 5
    config['log_level'] = 'INFO'
    config['chat_log_file'] = 'chat.log'
    config['media_log_file'] = 'media.log'
    config['shell'] = 'localhost:5555'
    config['db'] = 'bot_data.db'
    
    return config


def main():
    parser = argparse.ArgumentParser(
        description='Setup a Rosey bot instance',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive setup
  python setup_bot.py
  
  # From config file
  python setup_bot.py --from-file my_config.json
  
  # Command line arguments
  python setup_bot.py --username CynthiaRothbot --channel myroom \\
                      --ollama-url http://192.168.1.100:11434
        """
    )
    
    parser.add_argument(
        '--from-file',
        metavar='FILE',
        help='Load configuration from JSON file'
    )
    
    parser.add_argument('--username', help='Bot username')
    parser.add_argument('--password', help='Bot password')
    parser.add_argument('--channel', help='CyTube channel name')
    parser.add_argument('--domain', default='https://cytu.be', help='CyTube domain')
    parser.add_argument('--ollama-url', help='Ollama base URL (enables LLM)')
    parser.add_argument('--ollama-model', default='llama3', help='Ollama model name')
    parser.add_argument('--output', default='bot/rosey/config.json', help='Output config file path')
    
    args = parser.parse_args()
    
    # Determine configuration source
    if args.from_file:
        print(f"Loading configuration from: {args.from_file}")
        config = load_config_file(args.from_file)
    elif args.username and args.channel:
        # Command line mode
        if not args.password:
            args.password = getpass("Bot password: ")
        
        config = {
            'domain': args.domain,
            'channel': args.channel,
            'user': [args.username, args.password],
            'response_timeout': 1,
            'restart_delay': 5,
            'log_level': 'INFO',
            'chat_log_file': 'chat.log',
            'media_log_file': 'media.log',
            'shell': 'localhost:5555',
            'db': 'bot_data.db'
        }
        
        # LLM config if Ollama URL provided
        if args.ollama_url:
            config['llm'] = {
                'enabled': True,
                'provider': 'ollama',
                'system_prompt_file': 'prompt.md',
                'max_context_messages': 10,
                'temperature': 0.7,
                'max_tokens': 500,
                'log_only': False,
                'ollama': {
                    'base_url': args.ollama_url,
                    'model': args.ollama_model
                },
                'triggers': {
                    'enabled': True,
                    'direct_mention': True,
                    'commands': ['!ai', '!ask'],
                    'ambient_chat': {'enabled': False},
                    'keywords': [],
                    'greetings': {'enabled': False}
                }
            }
        else:
            config['llm'] = {'enabled': False}
    else:
        # Interactive mode
        config = interactive_setup()
    
    # Write config file
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print()
    print("=" * 60)
    print("✅ Configuration Complete!")
    print("=" * 60)
    print(f"Config written to: {output_path}")
    print()
    print("Next Steps:")
    print("-" * 40)
    print("1. Review the configuration:")
    print(f"   cat {output_path}")
    print()
    print("2. (Optional) Customize prompt.md for bot personality")
    print(f"   nano {output_path.parent / 'prompt.md'}")
    print()
    print("3. Install dependencies (if not already done):")
    print("   pip install -r requirements.txt")
    print()
    print("4. Start your bot:")
    print(f"   cd {output_path.parent}")
    print("   python rosey.py config.json")
    print()
    
    if config.get('llm', {}).get('enabled'):
        print("LLM Features Enabled:")
        print(f"  • Provider: {config['llm']['provider']}")
        if config['llm']['provider'] == 'ollama':
            print(f"  • Ollama URL: {config['llm']['ollama']['base_url']}")
            print(f"  • Model: {config['llm']['ollama']['model']}")
        print("  • Triggers: Direct mentions and commands (!ai, !ask)")
        print()
        print("Test LLM setup:")
        print(f"   cd {output_path.parent}")
        print("   python test_llm.py")
        print()
    
    print("Bot Details:")
    print(f"  • Username: {config['user'][0]}")
    print(f"  • Channel: {config['domain']}/r/{config['channel']}")
    print(f"  • Log level: {config.get('log_level', 'INFO')}")
    print()


if __name__ == '__main__':
    main()
