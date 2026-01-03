# Quality Check

## Overview
Run comprehensive quality checks including linting, format validation, type checking, and unit tests without modifying files.

## Steps
1. **Linting**
   - Run ruff to check for code quality issues
   - Verify code follows style guidelines

2. **Format Check**
   - Verify code is properly formatted with black
   - Check without modifying files

3. **Type Checking**
   - Run mypy to check type annotations
   - Verify type safety across the codebase

4. **Unit Tests**
   - Run pytest test suite
   - Verify all tests pass

## Command
```bash
source venv/bin/activate && ruff check src tests && black --check src tests && mypy src && pytest
```

## Quality Checklist
- [ ] No linting errors
- [ ] Code is properly formatted
- [ ] No type errors
- [ ] All tests pass

