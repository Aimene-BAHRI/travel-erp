# Development

## Quality gates

Backend:

```powershell
ruff check .
pytest
python manage.py check
python manage.py spectacular --validate --file schema.yml
```

Frontend:

```powershell
pnpm lint
pnpm typecheck
pnpm build
```

