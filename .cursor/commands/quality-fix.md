# Quality Fix

## Overview
Auto-fix code quality issues, format code, run type checking, and execute unit tests. This command will modify files to fix linting and formatting issues.

## Steps
1. **Auto-fix Linting**
   - Run ruff with --fix to automatically fix linting issues
   - Resolve code quality problems

2. **Format Code**
   - Run black to format code according to project standards
   - Ensure consistent code style

3. **Type Checking**
   - Run mypy to check type annotations
   - Verify type safety across the codebase

4. **Unit Tests**
   - Run pytest test suite
   - Verify all tests pass after fixes

## Command
```bash
source venv/bin/activate && ruff check --fix src tests && black src tests && mypy src && pytest
```

## Quality Checklist
- [ ] Linting issues auto-fixed
- [ ] Code formatted with black
- [ ] No type errors
- [ ] All tests pass

