# AGENTS.md

Instructions for AI coding agents working on the RFP Analyzer project.

## Project Overview

RFP Analyzer is an AI-powered application for analyzing Request for Proposals (RFPs) and scoring vendor proposals using Azure AI services and Microsoft Agent Framework. It uses a multi-agent architecture with specialized agents for document processing, scoring, and comparison.

**Tech Stack:**
- Python 3.13+ with UV package manager
- Streamlit for web UI
- Microsoft Agent Framework for multi-agent orchestration
- Azure OpenAI (GPT-4.1, GPT-5.2 models)
- Azure Content Understanding & Document Intelligence
- Azure Container Apps for deployment
- Bicep/AVM for infrastructure as code

## Project Structure

```
rfp-analyzer/
├── app/                    # Main application
│   ├── main.py             # Streamlit entry point
│   ├── services/           # Core services and agents
│   │   ├── scoring_agent_v2.py      # Multi-agent scoring system
│   │   ├── comparison_agent.py      # Vendor comparison agent
│   │   ├── document_processor.py    # Document processing orchestrator
│   │   ├── content_understanding_client.py  # Azure Content Understanding
│   │   └── document_intelligence_client.py  # Azure Document Intelligence
│   ├── pyproject.toml      # Python dependencies (UV)
│   └── requirements.txt    # Pip fallback dependencies
├── infra/                  # Infrastructure as Code
│   ├── main.bicep          # Main Bicep template
│   ├── resources.bicep     # Azure resources
│   └── modules/            # Bicep modules
├── docs/                   # Documentation
└── azure.yaml              # Azure Developer CLI config
```

## Development Environment

### Prerequisites
- Python 3.13+
- [UV](https://docs.astral.sh/uv/) package manager
- Azure CLI with `az login` authenticated
- Azure Developer CLI (`azd`) for deployment

### Setup Commands

```bash
# Navigate to app directory
cd app

# Install dependencies with UV
uv sync

# Create .env file from template
cp .env.example .env  # Then fill in Azure credentials

# Run the application locally
uv run streamlit run main.py --server.port=8501
```

### Alternative Setup (pip)

```bash
cd app
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run main.py --server.port=8501
```

## Environment Variables

Required environment variables in `app/.env`:

```
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<key>  # Or use managed identity
AZURE_CONTENT_UNDERSTANDING_ENDPOINT=https://<resource>.cognitiveservices.azure.com/
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://<resource>.cognitiveservices.azure.com/
```

## Code Style Guidelines

- Use Python type hints for all function signatures
- Follow PEP 8 naming conventions
- Use Pydantic models for data validation
- Async/await for Azure SDK calls where available
- Use `logging` module with `logging_config.py` configuration
- Prefer composition over inheritance for agents

## Key Patterns

### Agent Framework Pattern
Agents in `services/` follow Microsoft Agent Framework patterns:
- Agents are classes with `run()` or `process()` methods
- Use dependency injection for Azure clients
- Return structured Pydantic models

### Azure Client Pattern
```python
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
# Use managed identity in production, CLI auth locally
```

## Testing Instructions

Currently no automated tests. When adding tests:

```bash
# Install dev dependencies
uv sync --group dev

# Run tests (when implemented)
uv run pytest

# Type checking
uv run mypy app/
```

## Azure Deployment

### Deploy with Azure Developer CLI

```bash
# Login to Azure
azd auth login

# Provision infrastructure and deploy
azd up

# Just deploy code changes
azd deploy
```

### Infrastructure Changes

Bicep files are in `infra/`:
- `main.bicep` - Entry point, parameters
- `resources.bicep` - All Azure resources
- `modules/` - Reusable Bicep modules

```bash
# Preview infrastructure changes
azd provision --preview
```

## Security Considerations

- Never commit `.env` files or secrets
- Use Azure Managed Identity in production
- API keys should use Azure Key Vault references
- `test.http` is gitignored (contains test secrets)

## Common Tasks

### Adding a New Agent
1. Create new file in `app/services/`
2. Follow pattern in `scoring_agent_v2.py`
3. Register with document processor if needed
4. Update `__init__.py` exports

### Modifying Scoring Criteria
- Edit `app/scoring_guide.md` for scoring guidelines
- Update `ScoringAgent` prompt templates
- Criteria weights are in scoring agent configuration

### Adding Azure Resources
1. Edit `infra/resources.bicep`
2. Use AVM modules from `modules/` where available
3. Add outputs to `main.bicep` if needed for app config

## PR Guidelines

- Include clear description of changes
- Test locally with `streamlit run main.py`
- Verify Azure deployment with `azd up` for infra changes
- Update documentation if adding new features
