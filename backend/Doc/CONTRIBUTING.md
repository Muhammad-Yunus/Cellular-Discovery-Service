# Contributing Guidelines

## Development Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Running Tests

```bash
pytest tests/ -v                    # Run all tests with verbose output
pytest tests/ --cov=app             # Run tests with coverage report
pytest tests/test_e2e.py            # Run only E2E tests
pytest tests/unit/                  # Run unit tests only (organize your tests)
```

## Code Style

All code should follow:
- **PEP 8** style guide
- Type hints on all function signatures
- Max line length 100 characters
- Clear, descriptive variable names
- No magic numbers (use named constants)

## Adding a New Feature

When adding new functionality, please ensure it follows these criteria:

1. ✅ Typed (all parameters and return values have type annotations)
2. ✅ Tested (unit/integration tests included)
3. ✅ Documented (API docs updated)
4. ✅ Follows folder structure (place files in correct layer)
5. ✅ Follows dependency rules (API → Service → Repository → DB)
6. ✅ Generates Alembic migration if database changes are needed
7. ✅ Passes linting (`black`, `flake8` recommended)
8. ✅ Contains no duplicated logic
9. ✅ No hardcoded configuration (use environment variables)
10. ✅ Code reviewed before merge

### Example: Adding a New REST Endpoint

```
# Step 1: Create schema
app/schemas/new_resource.py

# Step 2: Create repository
app/repositories/new_resource_repository.py

# Step 3: Create service
app/services/new_service.py

# Step 4: Create router
app/api/routers/new_router.py

# Step 5: Register in app/main.py

# Step 6: Write tests
tests/test_new_resource.py

# Step 7: Generate Alembic migration if needed
alembic revision --autogenerate -m "add new resource"
alembic upgrade head
```

## Database Changes

Any change to the database schema requires:

1. Update SQLAlchemy model in `app/db/models/`
2. Generate Alembic migration:
   ```bash
   alembic revision --autogenerate -m "your descriptive message"
   ```
3. Review migration diff before committing
4. Add migration to deployment script

## CLI Adapter Integration

If adding support for additional CLI tools:

1. Extend `CLIAdapter` or create subclass
2. Implement exception mapping to existing exception hierarchy
3. Keep JSON parsing inside the adapter only
4. Service layer should never know about CLI implementation details

## GPS Provider Extensions

To add a new GPS provider:

1. Implement `GPSProvider` protocol (structural typing)
2. Create new class in `app/gps/`
3. Register in `create_gps_provider()` factory
4. Write unit test mocking external hardware

---

## Pull Request Checklist

- [ ] All tests pass
- [ ] Coverage maintained or improved
- [ ] Documentation updated
- [ ] No broken imports
- [ ] PE P8 compliance
- [ ] Meaningful commit messages

---

**Questions?** Contact project maintainers or check `https://github.com/anomalyco/opencode/issues` for tool-related feedback.
