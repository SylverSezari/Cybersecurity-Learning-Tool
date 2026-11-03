# Cybersecurity-Learning-Tool
Bachelor Thesis project to create a learning tool for schools in the topics of cybersecurity

## Seed the content database

With dependencies installed and the required settings configured in `.env`, run:

```powershell
uv run python seed_database.py
```

The script creates or updates the chapter and exercise catalog, including order, prerequisites, pictures, and answer keys. It is safe to run again and does not create or delete accounts. Existing catalog entries not listed in the seed data are left untouched.
