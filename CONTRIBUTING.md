# Contributing to SuperPort

Thank you for your interest in contributing to SuperPort! This document provides guidelines for contributing to the project.

---

## Development Setup

See [QUICKSTART.md](QUICKSTART.md) for detailed setup instructions.

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# Frontend
cd frontend
npm install
```

---

## Code Quality

### Before submitting any changes

```bash
# Backend — all tests must pass
cd backend && pytest

# Frontend — must type-check and build cleanly
cd frontend && npm run typecheck && npm run build
```

### Coding Standards

- **Python:** Follow PEP 8. Use type hints. Pydantic models for data validation.
- **TypeScript:** Strict mode enabled. No `any` types without justification.
- **Tests:** Add or update tests with every behaviour change.
- **Documentation:** Update README.md and relevant docs when behaviour changes.

---

## Project Principles

These are non-negotiable and must be preserved in all contributions:

1. **Human-in-the-loop is enforced on the server** — never move approval gates to the client
2. **AI recommends, humans decide** — every AI output carries its source
3. **No silent fabrication** — generated data must be labelled
4. **Never present risk scores as authority decisions** — keep disclaimers
5. **Demo and production integrations stay separated** behind provider interfaces
6. **Audit everything** — human and AI actions logged via `AuditEvent`

---

## Adding a New Agent

1. Subclass `Agent` in `backend/app/agents/`
2. Implement `run(ctx) -> AgentResult`
3. Register in `agents/builtin.py`
4. Add tests
5. The dashboard automatically lists registered agents

## Adding a New SerpApi Integration

1. Add the search function in `backend/app/intelligence/` or `backend/app/market/`
2. Use the existing SerpApi client with budget tracking
3. Cache responses using the response cache
4. Every result must cite its source — uncited items are discarded
5. Add mock-based tests
6. Update cost control documentation

---

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add Google Shopping price comparison
fix: handle empty SerpApi response gracefully
docs: update API reference with new endpoints
test: add counterparty screening test cases
refactor: extract evidence pipeline into separate module
```

---

## Reporting Issues

Please include:
- Steps to reproduce
- Expected vs actual behaviour
- Environment details (OS, Python version, Node version)
- Relevant log output
