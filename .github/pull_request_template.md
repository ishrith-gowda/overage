## What does this PR do?

<!-- Describe the change in 2-3 sentences. Link to a related issue if one exists. -->

Closes #

## Why?

<!-- What problem does this solve? Why is this approach the right one? -->

## How was it tested?

<!-- Describe what tests you wrote or ran. Include commands if relevant. -->

```bash
make test       # All tests pass
make lint       # No lint errors
make typecheck  # No type errors
```

## Screenshots (if UI change)

<!-- Add screenshots or screen recordings for any dashboard or API doc changes. -->

N/A

## Migration required?

<!-- Did you change any SQLAlchemy models? If yes, confirm the migration was generated. -->

- [ ] No schema changes
- [ ] Schema changed — migration generated (`alembic revision --autogenerate`) and tested

## Checklist

> Reference: [INSTRUCTIONS.md](../INSTRUCTIONS.md) for coding standards.

- [ ] Type annotations added for all new functions
- [ ] Google-style docstrings added for all public functions
- [ ] Tests added with >80% coverage on new code
- [ ] No `print()` statements (use `structlog`)
- [ ] No hardcoded secrets, URLs, or magic numbers
- [ ] No bare `except:` clauses
- [ ] Linting passes (`make lint`)
- [ ] Type checking passes (`make typecheck`)
- [ ] All tests pass (`make test`)
- [ ] Documentation updated if API contract changed
- [ ] Alembic migration added if database schema changed
- [ ] `.env.example` updated if new environment variable added
