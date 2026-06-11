# AGENTS.md — IPL Query Resolver

## Language Policy

All communication, explanations, code comments, and responses **must be in English only**.

## Scope of Changes

Modify **only the files explicitly mentioned in the current task**. Do not edit any other files without permission.

## Dataset Rules

- **Do not** inspect or process `IPL.csv` unless explicitly instructed.
- If dataset inspection is required, use `first_rows.csv` as the reference.
- Never assume column names without verifying from `first_rows.csv` or user-provided information.

## Project Objective

Build a ball-by-ball IPL query resolver for seasons **2008–2025**.

### Phases

| Phase | Description |
|-------|-------------|
| **1 — Database Design** | Analyze the dataset, design a relational BCNF schema, define PKs, FKs, and relationships. |
| **2 — Data Processing** | Write Python scripts to transform raw IPL data into the normalized schema. Validate integrity during migration. |
| **3 — Query Engine** | Build a query layer to answer IPL questions efficiently against the normalized DB. |
| **4 — Frontend** | Create `app.py` using Streamlit for interactive querying with tables, charts, and summaries. |

## Technology Stack

| Technology | Usage |
|-----------|-------|
| Python 3 | Core language |
| Streamlit | Frontend UI (`app.py`) |
| SQL (BCNF) | Relational database schema |
| Pandas | Data transformation & analysis |
| SQLAlchemy | ORM (if needed) |

## Dataset Files

- `IPL.csv` — Full dataset (~millions of ball-by-ball rows). **Do not open unless explicitly requested.**
- `first_rows.csv` — Sample (first row) for schema understanding and development.

## Development Principles

- Write clean, modular, maintainable code following **PEP 8**.
- Prefer reusable functions over duplicated logic.
- Add clear docstrings and comments where necessary.
- Consider scalability — the full dataset contains millions of records.
- Prioritize query performance and database efficiency.
- Keep BCNF normalization and data integrity as primary goals.

## Expected Agent Behavior

1. Understand the project architecture before making changes.
2. Suggest schema improvements when beneficial.
3. Maintain **BCNF compliance** in all database design work.
4. Focus on **correctness, performance, and maintainability**.
5. Preserve the existing project structure unless a change is specifically requested.
6. Before making changes, explain the intended modifications and affected files.
