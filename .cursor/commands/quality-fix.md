# Quality Fix

## Overview
Auto-fix code quality issues, format code, run type checking, and execute unit tests. This command will modify files to fix linting and formatting issues.

## Steps
1. **Activate Virtual Environment**
   - Activate venv: `source venv/bin/activate`
   - Ensure all dependencies are installed

2. **Auto-fix Linting**
   - Run ruff with --fix to automatically fix linting issues
   - Resolve code quality problems

3. **Format Code**
   - Run black to format code according to project standards
   - Ensure consistent code style

4. **Type Checking**
   - Run mypy to check type annotations
   - Verify type safety across the codebase

5. **Unit Tests**
   - Run pytest test suite
   - Verify all tests pass after fixes

## Command
```bash
source venv/bin/activate && ruff check --fix aero_pi_cam tests && black aero_pi_cam tests && mypy aero_pi_cam && pytest tests/
```

## Quality Checklist
- [ ] Linting issues auto-fixed
- [ ] Code formatted with black
- [ ] No type errors
- [ ] All tests pass

