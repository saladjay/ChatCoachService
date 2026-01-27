# Core Libraries Installation Guide

## Overview

This project depends on three core libraries located in the `core/` directory:

1. **llm_adapter** - LLM provider abstraction layer
2. **moderation-service** - Content moderation service
3. **user_profile** - User profile management service

These libraries are installed in **editable mode** (`-e` flag), which means changes to the library code will be immediately reflected without reinstallation.

## Installation Scripts

Two installation scripts are provided for different platforms:

### Windows (PowerShell)

```powershell
.\install_core_libs.ps1
```

### Linux/macOS (Bash)

```bash
chmod +x install_core_libs.sh
./install_core_libs.sh
```

## What the Scripts Do

1. **Check for `uv` command** - Prefers `uv` if available, falls back to `pip`
2. **Install each library in editable mode** - Uses `uv pip install -e` or `pip install -e`
3. **Display installation summary** - Shows success/failure for each library

## Requirements

- Python 3.10+ (as specified in `.python-version`)
- Either `uv` (recommended) or `pip` package manager
- Virtual environment activated (recommended)

## Manual Installation

If you prefer to install manually or need to install only specific libraries:

```bash
# Using uv (recommended)
uv pip install -e core/llm_adapter
uv pip install -e core/moderation-service
uv pip install -e core/user_profile

# Using pip
pip install -e core/llm_adapter
pip install -e core/moderation-service
pip install -e core/user_profile
```

## Troubleshooting

### Script Execution Policy (Windows)

If you get an execution policy error on Windows:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Permission Denied (Linux/macOS)

If you get a permission error:

```bash
chmod +x install_core_libs.sh
```

### Missing Dependencies

If installation fails due to missing dependencies, ensure you have:

1. Activated your virtual environment
2. Updated pip/uv: `pip install --upgrade pip` or `uv self update`
3. Installed system dependencies (if any are required by the libraries)

## Verification

After installation, verify the libraries are installed:

```bash
# Using uv
uv pip list | grep -E "(llm-adapter|moderation-service|user-profile)"

# Using pip
pip list | grep -E "(llm-adapter|moderation-service|user-profile)"
```

You should see all three libraries listed with their installation paths.

## Next Steps

After installing the core libraries, you can:

1. Run the main application: `python main.py`
2. Run tests: `pytest`
3. Continue with Phase 1 Day 7-10 integration tasks

## Related Documentation

- `PHASE1_COMPLETION_REPORT.md` - Phase 1 completion status
- `README.md` - Main project documentation
- `QUICKSTART.md` - Quick start guide
