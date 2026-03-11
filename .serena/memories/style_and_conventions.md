# Style and Conventions

- Each domain: models/<name>.py, schemas/<name>.py, routers/<name>.py trio
- Pydantic v2 with ConfigDict(from_attributes=True)
- Polish-language enums and some variable names
- DB tables auto-created via Base.metadata.create_all at startup
- CORS for localhost:3000/4173/5173 and 10.10.77.75
- No tests, no linter config, no formatter config found
