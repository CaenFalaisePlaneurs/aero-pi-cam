# Quality Check

## Overview
Run comprehensive quality checks including linting, format validation, type checking, and unit tests without modifying files.

## Steps
1. **Activate Virtual Environment**
   - Activate venv: `source venv/bin/activate`
   - Ensure all dependencies are installed

2. **Linting**
   - Run ruff to check for code quality issues
   - Verify code follows style guidelines

3. **Format Check**
   - Verify code is properly formatted with black
   - Check without modifying files

4. **Type Checking**
   - Run mypy to check type annotations
   - Verify type safety across the codebase

5. **Unit Tests**
   - Run pytest test suite
   - Verify all tests pass

## Command
```bash
source venv/bin/activate && ruff check aero_pi_cam tests && black --check aero_pi_cam tests && mypy aero_pi_cam && pytest tests/
```

## Quality Checklist
- [ ] No linting errors
- [ ] Code is properly formatted
- [ ] No type errors
- [ ] All tests pass

