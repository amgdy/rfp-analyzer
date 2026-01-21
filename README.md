# RFP Analyzer

A Streamlit-based POC application for analyzing RFPs (Request for Proposals) and scoring multiple vendor proposals using Azure AI services.

## Features

- **3-Step Workflow:**
  1. Upload RFP document and multiple vendor proposals
  2. Configure extraction service and extract content
  3. AI-powered evaluation, scoring, and multi-vendor comparison

- **Document Extraction Options:**
  - Azure Content Understanding
  - Azure Document Intelligence

- **Multi-Agent Evaluation:**
  - Criteria Extraction Agent - Automatically extracts scoring criteria from RFP
  - Proposal Scoring Agent - Evaluates each vendor against criteria
  - Comparison Agent - Compares and ranks all vendors

- **Evaluation Modes:**
  - Individual scoring - Score each proposal separately
  - Combined scoring - Evaluate all proposals together

- **Export Options:**
  - CSV comparison reports with all metrics
  - Word document reports for each vendor
  - JSON data export

## Prerequisites

- Python 3.13+
- [UV](https://docs.astral.sh/uv/) package manager
- Azure subscription with:
  - Azure OpenAI resource (with a deployed model like `gpt-4o-mini`)
  - Azure Content Understanding resource OR Azure Document Intelligence resource

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
   - `AZURE_CONTENT_UNDERSTANDING_ENDPOINT`: Your Azure AI/Content Understanding endpoint
   - `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT`: (Optional) Your Document Intelligence endpoint

3. **Authenticate with Azure:**
   ```bash
   az login
   ```

## Running the Application

### Local Development

```bash
cd app
uv sync
uv run streamlit run main.py
```

The app will open in your browser at `http://localhost:8501`

### Docker

**Using Docker Compose (recommended):**

```bash
cd app

# Copy environment file and configure
cp .env.example .env
# Edit .env with your Azure credentials

# Build and run
docker compose up --build

# Run in background
docker compose up -d
```

**Using Docker directly:**

```bash
cd app

# Build the image
docker build -t rfp-analyzer .

# Run the container
docker run -p 8501:8501 \
  -e AZURE_CONTENT_UNDERSTANDING_ENDPOINT=your-endpoint \
  -e AZURE_OPENAI_ENDPOINT=your-openai-endpoint \
  -e AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-mini \
  -e AZURE_TENANT_ID=your-tenant-id \
  -e AZURE_CLIENT_ID=your-client-id \
  -e AZURE_CLIENT_SECRET=your-client-secret \
  rfp-analyzer
```

The app will be available at `http://localhost:8501`

## Project Structure

```
rfp-analyzer/
├── README.md                      # This file
├── azure.yaml                     # Azure Developer CLI config
└── app/
    ├── .env                       # Environment variables (create from .env.example)
    ├── .env.example               # Environment template
    ├── main.py                    # Streamlit application
    ├── pyproject.toml             # Dependencies (uv)
    ├── uv.lock                    # Lock file
    ├── Dockerfile                 # Docker image definition
    ├── docker-compose.yml         # Docker Compose config
    ├── scoring_guide.md           # Default evaluation criteria
    └── services/
        ├── document_processor.py  # Document extraction orchestrator
        ├── content_understanding_client.py  # Azure Content Understanding
        ├── document_intelligence_client.py  # Azure Document Intelligence
        ├── scoring_agent.py       # V1 Single Agent scoring (legacy)
        ├── scoring_agent_v2.py    # V2 Multi-Agent scoring
        └── comparison_agent.py    # Multi-vendor comparison
```

## Customization

### Scoring Guide
Edit `app/scoring_guide.md` to customize default evaluation criteria and weights.

### Document Processing
Choose between Azure Content Understanding and Azure Document Intelligence in the sidebar.

### AI Agent
The evaluation uses a multi-agent architecture powered by Azure OpenAI. Customize the evaluation logic in `app/services/scoring_agent_v2.py`.

## Dependencies

- `streamlit` - Web application framework
- `agent-framework` - Microsoft Agent Framework
- `azure-ai-documentintelligence` - Azure Document Intelligence
- `azure-identity` - Azure authentication
- `python-dotenv` - Environment configuration
- `pydantic` - Data validation
- `python-docx` - Word document generation

## License

MIT
