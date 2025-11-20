# SPEC: Sortie 2 - Configuration Management

**Sprint:** 5 (ship-it)  
**Sortie:** 2 of 12  
**Status:** Ready for Implementation  
**Depends On:** Sortie 1 (GitHub Actions Setup)

---

## Objective

Create separate configuration files for test and production environments with proper secrets management. This enables safe, separate deployments to test and production CyTube channels.

## Success Criteria

- ✅ `bots/rosey/config-test.json` created with test channel settings
- ✅ `bots/rosey/config-prod.json` created with production channel settings
- ✅ `.gitignore` updated to exclude `config.json`, include templates
- ✅ Secrets documentation created
- ✅ Configuration validation in place
- ✅ No credentials committed to repository

## Technical Specification

### File Structure
```
bots/rosey/
  config-test.json      # Test channel configuration (template)
  config-prod.json      # Production configuration (template)
  config.json           # Symlink to active config (gitignored)
  .env.example          # Environment variable template
docs/
  CONFIGURATION.md      # Configuration documentation
```

### Configuration Schema

**config-test.json** (Test Channel):
```json
{
  "channel": "test-rosey",
  "bot_name": "RoseyTest",
  "server": "cytu.be",
  "port": 443,
  "secure": true,
  "password": "${CYTUBEBOT_TEST_PASSWORD}",
  "log_level": "DEBUG",
  "db_path": "data/test-rosey.db",
  "moderators": ["testuser1", "testuser2"],
  "command_prefix": "!",
  "enable_web_status": true,
  "web_status_port": 8081
}
```

**config-prod.json** (Production Channel):
```json
{
  "channel": "rosey",
  "bot_name": "Rosey",
  "server": "cytu.be",
  "port": 443,
  "secure": true,
  "password": "${CYTUBEBOT_PROD_PASSWORD}",
  "log_level": "INFO",
  "db_path": "data/rosey.db",
  "moderators": ["moderator1", "moderator2"],
  "command_prefix": "!",
  "enable_web_status": true,
  "web_status_port": 8080
}
```

### Environment Variables Template

**.env.example**:
```bash
# CyTube Bot Configuration
# Copy this file to .env and fill in actual values

# Test Channel
CYTUBEBOT_TEST_PASSWORD=your_test_password_here

# Production Channel
CYTUBEBOT_PROD_PASSWORD=your_prod_password_here

# Deployment (if using remote deployment)
DEPLOY_SSH_KEY_PATH=/path/to/ssh/key
DEPLOY_HOST=your.server.com
DEPLOY_USER=deployuser
```

### GitHub Secrets Required

Configure in GitHub repository settings → Secrets and variables → Actions:

| Secret Name | Description | Used By |
|-------------|-------------|---------|
| `CYTUBEBOT_TEST_PASSWORD` | Test channel bot password | Test deployment workflow |
| `CYTUBEBOT_PROD_PASSWORD` | Production channel bot password | Prod deployment workflow |
| `DEPLOY_SSH_KEY` | SSH private key for deployment | Both (if remote deploy) |

### Configuration Validation

**common/config.py** (new utility):
```python
"""Configuration management utilities."""
import json
import os
import re
from pathlib import Path
from typing import Any, Dict

class ConfigError(Exception):
    """Configuration validation error."""
    pass

def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from JSON file with environment variable substitution.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configuration dictionary with variables substituted
        
    Raises:
        ConfigError: If config invalid or variables missing
    """
    path = Path(config_path)
    if not path.exists():
        raise ConfigError(f"Configuration file not found: {config_path}")
    
    with open(path) as f:
        config = json.load(f)
    
    # Substitute environment variables
    config = _substitute_env_vars(config)
    
    # Validate required fields
    _validate_config(config)
    
    return config

def _substitute_env_vars(config: Dict[str, Any]) -> Dict[str, Any]:
    """Replace ${VAR_NAME} with environment variable values."""
    result = {}
    for key, value in config.items():
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            var_name = value[2:-1]
            env_value = os.environ.get(var_name)
            if env_value is None:
                raise ConfigError(
                    f"Environment variable '{var_name}' not set (required for {key})"
                )
            result[key] = env_value
        elif isinstance(value, dict):
            result[key] = _substitute_env_vars(value)
        else:
            result[key] = value
    return result

def _validate_config(config: Dict[str, Any]) -> None:
    """Validate configuration has required fields."""
    required_fields = [
        "channel",
        "bot_name",
        "server",
        "password",
        "db_path",
    ]
    
    for field in required_fields:
        if field not in config:
            raise ConfigError(f"Missing required field: {field}")
        if not config[field]:
            raise ConfigError(f"Field '{field}' cannot be empty")
    
    # Validate log level
    valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if "log_level" in config and config["log_level"] not in valid_log_levels:
        raise ConfigError(
            f"Invalid log_level '{config['log_level']}'. "
            f"Must be one of: {', '.join(valid_log_levels)}"
        )
```

### .gitignore Updates

Add to `.gitignore`:
```gitignore
# Configuration files with secrets
bots/*/config.json
.env

# Keep configuration templates
!bots/*/config-*.json
!.env.example

# Deployment backups
.deploy-backup/
```

## Implementation Steps

### Step 1: Create Configuration Templates

```bash
# Test configuration
cat > bots/rosey/config-test.json << 'EOF'
{
  "channel": "test-rosey",
  "bot_name": "RoseyTest",
  "server": "cytu.be",
  "port": 443,
  "secure": true,
  "password": "${CYTUBEBOT_TEST_PASSWORD}",
  "log_level": "DEBUG",
  "db_path": "data/test-rosey.db",
  "moderators": [],
  "command_prefix": "!",
  "enable_web_status": true,
  "web_status_port": 8081
}
EOF

# Production configuration
cat > bots/rosey/config-prod.json << 'EOF'
{
  "channel": "rosey",
  "bot_name": "Rosey",
  "server": "cytu.be",
  "port": 443,
  "secure": true,
  "password": "${CYTUBEBOT_PROD_PASSWORD}",
  "log_level": "INFO",
  "db_path": "data/rosey.db",
  "moderators": [],
  "command_prefix": "!",
  "enable_web_status": true,
  "web_status_port": 8080
}
EOF
```

### Step 2: Create Environment Template

```bash
cat > bots/rosey/.env.example << 'EOF'
# CyTube Bot Configuration
# Copy this file to .env and fill in actual values

# Test Channel
CYTUBEBOT_TEST_PASSWORD=your_test_password_here

# Production Channel
CYTUBEBOT_PROD_PASSWORD=your_prod_password_here
EOF
```

### Step 3: Update .gitignore

```bash
cat >> .gitignore << 'EOF'

# Configuration with secrets
bots/*/config.json
bots/*/.env
.env

# Keep configuration templates
!bots/*/config-*.json
!bots/*/.env.example

# Deployment backups
.deploy-backup/
EOF
```

### Step 4: Create Configuration Utility

Create `common/config.py` with the validation code above.

### Step 5: Add Unit Tests

**tests/unit/test_config.py**:
```python
"""Tests for configuration management."""
import json
import os
import pytest
from pathlib import Path
from common.config import load_config, ConfigError

def test_load_config_success(tmp_path):
    """Test loading valid configuration."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "channel": "test",
        "bot_name": "TestBot",
        "server": "cytu.be",
        "password": "${TEST_PASSWORD}",
        "db_path": "test.db"
    }))
    
    os.environ["TEST_PASSWORD"] = "secret123"
    try:
        config = load_config(str(config_file))
        assert config["password"] == "secret123"
        assert config["channel"] == "test"
    finally:
        del os.environ["TEST_PASSWORD"]

def test_load_config_missing_env_var(tmp_path):
    """Test loading config with missing environment variable."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "channel": "test",
        "bot_name": "TestBot",
        "server": "cytu.be",
        "password": "${MISSING_PASSWORD}",
        "db_path": "test.db"
    }))
    
    with pytest.raises(ConfigError, match="MISSING_PASSWORD"):
        load_config(str(config_file))

def test_load_config_missing_required_field(tmp_path):
    """Test loading config with missing required field."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "channel": "test",
        "bot_name": "TestBot",
        # Missing: server, password, db_path
    }))
    
    with pytest.raises(ConfigError, match="Missing required field"):
        load_config(str(config_file))

def test_load_config_invalid_log_level(tmp_path):
    """Test loading config with invalid log level."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "channel": "test",
        "bot_name": "TestBot",
        "server": "cytu.be",
        "password": "secret",
        "db_path": "test.db",
        "log_level": "INVALID"
    }))
    
    with pytest.raises(ConfigError, match="Invalid log_level"):
        load_config(str(config_file))
```

### Step 6: Create Documentation

Create `docs/CONFIGURATION.md` (see Documentation section below).

### Step 7: Commit Changes

```bash
git add bots/rosey/config-*.json
git add bots/rosey/.env.example
git add .gitignore
git add common/config.py
git add tests/unit/test_config.py
git add docs/CONFIGURATION.md

git commit -m "feat: add configuration management for test and production

Created separate configurations for test and production deployments
with environment variable substitution and validation.

Configuration Templates:
- bots/rosey/config-test.json (test channel settings)
- bots/rosey/config-prod.json (production channel settings)
- bots/rosey/.env.example (environment variable template)

Configuration Utility:
- common/config.py: Load and validate configuration
- Environment variable substitution (\${VAR_NAME})
- Required field validation
- Log level validation

Security:
- .gitignore updated to exclude config.json and .env
- Keep templates in repository
- No credentials committed

Tests:
- tests/unit/test_config.py: Configuration loading tests
- Test env var substitution
- Test validation errors
- Test missing fields

Documentation:
- docs/CONFIGURATION.md: Complete configuration guide
- GitHub Secrets setup instructions
- Local development setup

This enables safe separate deployments to test and production
channels with proper secrets management.

SPEC: Sortie 2 - Configuration Management"
```

## Documentation

### docs/CONFIGURATION.md

Create comprehensive configuration guide:

```markdown
# Configuration Management

## Overview

Rosey uses separate configuration files for test and production environments, with sensitive values (passwords) stored as environment variables or GitHub Secrets.

## Configuration Files

- `bots/rosey/config-test.json` - Test channel configuration
- `bots/rosey/config-prod.json` - Production channel configuration
- `bots/rosey/config.json` - Active configuration (symlink, gitignored)

## Local Development Setup

1. Copy environment template:
   ```bash
   cp bots/rosey/.env.example bots/rosey/.env
   ```

2. Edit `.env` and fill in actual passwords

3. Create symlink to desired config:
   ```bash
   # For test channel
   ln -s config-test.json bots/rosey/config.json
   
   # For production channel
   ln -s config-prod.json bots/rosey/config.json
   ```

4. Load environment and run bot:
   ```bash
   source bots/rosey/.env
   python -m bots.rosey.bot
   ```

## GitHub Secrets Setup

For CI/CD deployment, configure secrets in GitHub:

1. Go to repository Settings → Secrets and variables → Actions
2. Add secrets:
   - `CYTUBEBOT_TEST_PASSWORD`: Test channel bot password
   - `CYTUBEBOT_PROD_PASSWORD`: Production channel bot password

## Configuration Schema

### Required Fields

- `channel`: CyTube channel name
- `bot_name`: Bot username
- `server`: CyTube server (usually "cytu.be")
- `password`: Bot password (use environment variable)
- `db_path`: Path to SQLite database file

### Optional Fields

- `port`: Server port (default: 443)
- `secure`: Use HTTPS (default: true)
- `log_level`: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)
- `moderators`: List of moderator usernames
- `command_prefix`: Command prefix (default: "!")
- `enable_web_status`: Enable status web server (default: true)
- `web_status_port`: Status server port (default: 8080)

## Environment Variable Substitution

Configuration values can reference environment variables:

```json
{
  "password": "${CYTUBEBOT_TEST_PASSWORD}"
}
```

The `${VAR_NAME}` syntax will be replaced with the environment variable value at runtime.

## Validation

The `common.config.load_config()` function validates:

- Required fields present
- Environment variables set
- Log level valid
- Configuration parseable as JSON

## Security Best Practices

✅ **DO:**
- Use environment variables for passwords
- Keep config templates in repository
- Document configuration schema
- Validate configuration on load

❌ **DON'T:**
- Commit `config.json` with passwords
- Commit `.env` files
- Hardcode passwords in configuration
- Share secrets in public channels

## Troubleshooting

### Error: "Environment variable 'X' not set"
- Ensure `.env` file exists and is sourced
- Check GitHub Secrets configured
- Verify variable name matches exactly (case-sensitive)

### Error: "Configuration file not found"
- Check `config.json` symlink exists
- Verify pointing to correct template
- Ensure running from repository root

### Error: "Missing required field"
- Check configuration template complete
- Verify all required fields present
- Compare against schema documentation

## Testing Configuration

Run configuration tests:
```bash
pytest tests/unit/test_config.py -v
```

Validate configuration manually:
```python
from common.config import load_config
config = load_config("bots/rosey/config-test.json")
print(f"Loaded config for channel: {config['channel']}")
```
```

## Validation Checklist

- [ ] `bots/rosey/config-test.json` created
- [ ] `bots/rosey/config-prod.json` created
- [ ] `bots/rosey/.env.example` created
- [ ] `.gitignore` updated correctly
- [ ] `common/config.py` implemented
- [ ] `tests/unit/test_config.py` created
- [ ] All config tests pass
- [ ] `docs/CONFIGURATION.md` created
- [ ] No credentials in repository
- [ ] Configuration validates correctly

## Dependencies

### Required Tools
- Python 3.11
- pytest (for tests)

### Environment
- GitHub Secrets (for CI/CD)
- Local `.env` file (for development)

## Testing Strategy

1. **Unit tests** for config.py utility
2. **Manual validation** of config templates
3. **Verify .gitignore** excludes secrets
4. **Test env var substitution** works
5. **Test validation errors** raised correctly

## Performance Impact

- Negligible (configuration loaded once at startup)
- Validation adds < 10ms to startup time

## Rollback Plan

If configuration causes issues:
1. Revert this sortie: `git revert HEAD`
2. Restore old config.json (if backed up)
3. Remove config.py utility
4. Update .gitignore to revert changes

## Success Metrics

- ✅ Configuration validates successfully
- ✅ Environment variables substitute correctly
- ✅ No secrets committed to repository
- ✅ All configuration tests pass
- ✅ Documentation complete and clear

## Next Sortie

**Sortie 3: Deployment Scripts** - Create deploy.sh, rollback.sh, and health_check.py scripts.

---

**Implementation Time Estimate:** 3-4 hours  
**Risk Level:** Low  
**Priority:** High (required for deployment)
