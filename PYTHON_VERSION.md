# Python Version Compatibility

This project is designed to work with **Python 3.13.5** (as included on Raspberry Pi OS).

## Version Requirements

- **Minimum**: Python 3.11
- **Target**: Python 3.13.5 (Raspberry Pi)
- **Maximum**: Python < 3.14 (to ensure compatibility)

## Why Python 3.13.5?

The Raspberry Pi comes with Python 3.13.5 pre-installed, so no additional Python installation is needed. This simplifies deployment and ensures consistency.

## Virtual Environment Setup

### On Development Machine

1. **Using pyenv** (recommended):
   ```bash
   pyenv install 3.13.5
   pyenv local 3.13.5
   python --version  # Should show 3.13.5
   ```

2. **Using system Python**:
   ```bash
   python3 --version  # Check version
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Using setup script**:
   ```bash
   ./setup-venv.sh 3.13.5
   source venv/bin/activate
   ```

### On Raspberry Pi

The system Python 3.13.5 is used automatically:

```bash
python3 --version  # Should show Python 3.13.5
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Compatibility Notes

The code uses modern Python features that are compatible with Python 3.11+:

- ✅ Type hints with built-in generics (`dict[str, Any]`, `tuple[int, int]`)
- ✅ `dataclasses` (Python 3.7+)
- ✅ `asyncio` with async/await
- ✅ `match` statements (Python 3.10+, but not used in this project)
- ✅ `Optional` and `Union` type hints

All dependencies are compatible with Python 3.11-3.13.

## Testing Compatibility

To verify your setup works:

```bash
# Check Python version
python3 --version

# Create and activate venv
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest

# Run the application
python3 -m src.main
```

## Troubleshooting

**Issue**: `python3 --version` shows a different version than 3.13.5

- On Raspberry Pi: This is normal if you've updated the system. Python 3.11+ should work fine.
- On development machine: Use pyenv or ensure your venv uses the correct version.

**Issue**: Import errors or syntax errors

- Ensure you're using Python 3.11 or higher
- Check that all dependencies are installed: `pip install -r requirements.txt`

**Issue**: Virtual environment not activating

- Make sure you're in the project directory
- Use `source venv/bin/activate` (not `./venv/bin/activate`)

