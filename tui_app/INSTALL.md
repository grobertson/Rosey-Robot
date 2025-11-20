# CyTube TUI Installation Guide

## Option 1: Run from Source (Recommended)

This is the easiest way to run the TUI without installing it system-wide.

### 1. Install Dependencies

```bash
# Navigate to project root
cd /path/to/Rosey-Robot

# Install required packages
pip install -r requirements.txt blessed

# Or use virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt blessed
```

### 2. Create Config

```bash
# Copy example config
cp tui_app/configs/config.yaml.example tui_app/configs/config.yaml

# Edit config with your settings
nano tui_app/configs/config.yaml  # or your preferred editor
```

### 3. Run

```bash
# From project root
python -m tui_app tui_app/configs/config.yaml

# Or use launcher scripts
# Windows:
tui_app\run.bat

# Linux/Mac:
chmod +x tui_app/run.sh
./tui_app/run.sh
```

## Option 2: Install as Package

Install the TUI as a system-wide command `cytube-tui`.

### 1. Install

```bash
# From project root
pip install -e .  # Editable install (for development)
# OR
pip install .     # Regular install
```

### 2. Create Config

```bash
# Create config directory in your home folder
mkdir -p ~/.config/cytube-tui
cp tui_app/configs/config.yaml.example ~/.config/cytube-tui/config.yaml

# Edit config
nano ~/.config/cytube-tui/config.yaml
```

### 3. Run

```bash
# Now available as command anywhere
cytube-tui ~/.config/cytube-tui/config.yaml
```

## Option 3: Standalone Distribution (Future)

Coming soon: Pre-built executables for Windows, Linux, and macOS that don't require Python installation.

## Updating

### From Source

```bash
cd /path/to/Rosey-Robot
git pull origin main
pip install -r requirements.txt --upgrade
```

### Installed Package

```bash
cd /path/to/Rosey-Robot
git pull origin main
pip install -e . --upgrade
```

## Uninstalling

### Package Installation

```bash
pip uninstall cytube-tui
```

### Source Installation

Simply delete the repository directory. No system files are modified.

## Troubleshooting

### "ModuleNotFoundError: No module named 'blessed'"

```bash
pip install blessed
```

### "ModuleNotFoundError: No module named 'yaml'"

```bash
pip install pyyaml
```

### "Command 'cytube-tui' not found" (after installation)

Ensure pip's bin directory is in your PATH:

```bash
# Linux/Mac
export PATH="$HOME/.local/bin:$PATH"

# Windows
# Add %APPDATA%\Python\Scripts to your PATH environment variable
```

### Colors not displaying properly

Ensure your terminal supports 256 colors:

```bash
echo $TERM  # Should be xterm-256color or similar
```

### Permission denied on run.sh

```bash
chmod +x tui_app/run.sh
```

## Platform-Specific Notes

### Windows

- **Windows Terminal** (recommended) - Best color support and performance
- **PowerShell** - Works well
- **CMD** - Basic functionality, limited colors
- **Git Bash** - Works well

### Linux

- Most modern terminals work great (gnome-terminal, konsole, terminator, alacritty)
- Ensure UTF-8 locale: `export LANG=en_US.UTF-8`

### macOS

- **iTerm2** (recommended) - Best experience
- **Terminal.app** - Works well
- May need to install Python 3.7+ via Homebrew

## Next Steps

After installation, see the [main README](README.md) for:
- Configuration options
- Keyboard controls
- Available commands
- Theme customization
- Usage tips
