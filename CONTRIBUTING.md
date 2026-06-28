# Contributing to MCP Server Hub

Thank you for your interest! Here's how to get started.

## Development Setup

```bash
git clone <repo>
cd McpServerHub

# Create conda environment
conda create -n McpServerHub python=3.10 -y
conda activate McpServerHub

# Install in dev mode
pip install -e ".[dev]"

# Set up PostgreSQL
# (see docker-compose.yml for easy setup)

# Initialize database
python -m mcp_hub.db.migrations
python -m mcp_hub.db.seed

# Start
mcp daemon start --dev
```

## Code Style

- Python: Ruff + mypy strict
- Type hints required for all functions
- Tests: pytest with pytest-asyncio

```bash
# Run checks
ruff check src/
mypy src/
pytest tests/
```

## Pull Request Process

1. Create a feature branch from `develop`
2. Write tests for new functionality
3. Ensure all tests pass
4. Run linting and type checking
5. Submit PR against `main`
