#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import logging
import sys

from lib import SocketIO, set_proxy

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    from packaging import version
    HAS_PACKAGING = True
except ImportError:
    HAS_PACKAGING = False


class RobustFileHandler(logging.FileHandler):
    """FileHandler that gracefully handles flush errors on Windows"""

    def flush(self):
        """Flush the stream, catching OSError on Windows file handles"""
        try:
            super().flush()
        except OSError as e:
            # Windows can sometimes fail to flush with "Invalid argument"
            # This typically happens when the file handle is in an
            # inconsistent state. We log it but don't crash.
            if e.errno == 22:  # EINVAL
                # Silently ignore invalid argument errors
                pass
            else:
                raise


def configure_logger(logger,
                     log_file=None,
                     log_format=None,
                     log_level=logging.INFO):
    """Configure a logger with a file or stream handler

    Args:
        logger: Logger instance or logger name string
        log_file: File path string or file-like object (None for stderr)
        log_format: Format string for log messages
        log_level: Logging level (e.g., logging.INFO, logging.DEBUG)

    Returns:
        Configured logger instance
    """
    # Create file handler if path string, otherwise stream handler
    if isinstance(log_file, str):
        # Append mode with UTF-8 encoding and error handling for Windows
        # Use RobustFileHandler to catch flush errors
        handler = RobustFileHandler(
            log_file,
            mode='a',
            encoding='utf-8',
            errors='replace'  # Replace problematic chars
        )
    else:
        handler = logging.StreamHandler(log_file)  # Default to stderr if None

    # Create and attach formatter
    formatter = logging.Formatter(log_format)

    # Get logger by name if string provided
    if isinstance(logger, str):
        logger = logging.getLogger(logger)

    # Configure the logger
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(log_level)

    return logger


def configure_proxy(conf):
    """Configure SOCKS proxy from config dictionary

    Args:
        conf: Configuration dictionary containing optional 'proxy' key
              Format: "host:port" or just "host" (default port 1080)
    """
    proxy = conf.get('proxy', None)
    if not proxy:
        return

    # Parse proxy address - split on last colon
    proxy = proxy.rsplit(':', 1)
    if len(proxy) == 1:
        # No port specified, use default SOCKS port
        addr, port = proxy[0], 1080
    else:
        # Port was specified
        addr, port = proxy[0], int(proxy[1])

    # Set the global proxy configuration
    set_proxy(addr, port)


def get_config():
    """Load and parse configuration from JSON or YAML file specified in command line

    Returns:
        Tuple of (conf, kwargs) where:
            conf: Full configuration dictionary from config file
            kwargs: Bot initialization parameters extracted from config

    Exits:
        Exits with status 1 if incorrect number of arguments
    """
    # Validate command line arguments
    if len(sys.argv) != 2:
        print('usage: %s <config file>' % sys.argv[0], file=sys.stderr)
        sys.exit(1)

    config_file = sys.argv[1]

    # Determine file format from extension
    if config_file.endswith(('.yaml', '.yml')):
        if not HAS_YAML:
            print('ERROR: PyYAML is required for YAML config files', file=sys.stderr)
            print('Install with: pip install pyyaml', file=sys.stderr)
            sys.exit(1)
        # Load YAML configuration file
        with open(config_file, 'r', encoding='utf-8') as fp:
            conf = yaml.safe_load(fp)
    else:
        # Load JSON configuration file (default)
        with open(config_file, 'r', encoding='utf-8') as fp:
            conf = json.load(fp)

    # Extract connection retry settings
    retry = conf.get('retry', 0)  # Number of connection retries
    retry_delay = conf.get('retry_delay', 1)  # Seconds between retries

    # Handle config v2 format (platforms array) vs v1 (flat)
    config_version = conf.get('version', '1.0')
    # Use semantic versioning for robust version comparison
    if HAS_PACKAGING:
        # Prefer packaging library for proper semver support
        is_v2 = version.parse(str(config_version)) >= version.parse('2.0')
    else:
        # Fallback to string comparison (less robust but works for major versions)
        is_v2 = str(config_version).startswith('2.')

    if is_v2:
        # Extract from v2 nested structure
        platforms = conf.get('platforms', [])
        if not platforms:
            print('ERROR: No platforms configured in v2 config', file=sys.stderr)
            sys.exit(1)
        platform = platforms[0]  # Primary platform
        logging_config = conf.get('logging', {})
        log_level_str = logging_config.get('level', 'info')
    else:
        # Extract from v1 flat structure
        platform = conf
        log_level_str = conf.get('log_level', 'info')

    # Parse log level from string to logging constant
    log_level = getattr(logging, log_level_str.upper())

    # Configure root logger with basic settings
    logging.basicConfig(
        level=log_level,
        format='[%(asctime).19s] [%(name)s] [%(levelname)s] %(message)s'
    )

    # Configure SOCKS proxy if specified in config
    configure_proxy(conf)

    # Return full config and extracted bot parameters
    return conf, {
        'domain': platform['domain'],  # CyTube server domain (required)
        'user': platform.get('user', None),  # Bot username/credentials (optional)
        'channel': platform.get('channel', None),  # Channel name/password (optional)
        'response_timeout': platform.get('response_timeout', 0.1),  # Socket.IO response timeout
        'restart_delay': platform.get('restart_delay', None),  # Delay before reconnect on error
        'socket_io': lambda url, loop: SocketIO.connect(
            url,
            retry=retry,
            retry_delay=retry_delay,
            loop=loop
        )
    }
