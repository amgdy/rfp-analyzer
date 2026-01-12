# RFP Analyzer

A Streamlit-based POC application for analyzing RFPs (Request for Proposals) and scoring vendor proposals using Azure AI services.

## Features

- **3-Step Workflow:**
  1. Upload and process RFP documents
  2. Upload and process Vendor Proposals
  3. AI-powered evaluation and scoring

- **Azure Content Understanding**: Extracts text and structure from PDF, Word, and other document formats
- **Microsoft Agent Framework**: Intelligent evaluation using Azure OpenAI

## Prerequisites

- Python 3.13+
- [UV](https://docs.astral.sh/uv/) package manager
- Azure subscription with:
  - Azure OpenAI resource (with a deployed model like `gpt-4o-mini`)
  - Azure Document Intelligence resource

## Setup

1. **Clone and install dependencies:**
   ```bash
   uv sync
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` with your Azure credentials:
   - `AZURE_OPENAI_ENDPOINT`: Your Azure OpenAI endpoint
   - `AZURE_OPENAI_DEPLOYMENT_NAME`: Your deployed model name
   - `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT`: Your Document Intelligence endpoint

3. **Authenticate with Azure:**
   ```bash
   az login
   ```

## Running the Application

```bash
uv run streamlit run app/main.py
```

The app will open in your browser at `http://localhost:8501`

## Project Structure

```
rfp-analyzer/
├── app/
│   ├── main.py                    # Streamlit application
│   ├── scoring_guide.md           # Evaluation criteria
│   └── services/
│       ├── document_processor.py  # Azure Document Intelligence
│       └── scoring_agent.py       # Microsoft Agent Framework
├── pyproject.toml                 # Dependencies
├── .env.example                   # Environment template
└── README.md                      # This file
```

## Customization

### Scoring Guide
Edit `app/scoring_guide.md` to customize evaluation criteria and weights.

### Document Processing
The `DocumentProcessor` class uses Azure Document Intelligence's `prebuilt-layout` model. You can modify this in `app/services/document_processor.py`.

### AI Agent
The `ScoringAgent` uses Microsoft Agent Framework with Azure OpenAI. Customize the evaluation logic in `app/services/scoring_agent.py`.

## Dependencies

- `streamlit` - Web application framework
- `agent-framework-azure-ai` - Microsoft Agent Framework (preview)
- `azure-ai-documentintelligence` - Azure Content Understanding
- `azure-identity` - Azure authentication
- `python-dotenv` - Environment configuration
- `pydantic` - Data validation

> **Note:** The `agent-framework-azure-ai` package is in preview. The `--pre` flag is required for installation.

## License

MIT
