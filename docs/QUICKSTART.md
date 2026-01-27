# RFP Analyzer - Quick Start Guide

This guide helps you get started with RFP Analyzer in under 5 minutes.

## Prerequisites

- Python 3.13+ installed
- Azure CLI installed and logged in (`az login`)
- Azure subscription with:
  - Azure OpenAI access
  - Azure AI Foundry resource

## Quick Start

### Option 1: Local Development (Fastest)

```bash
# Clone the repository
git clone https://github.com/your-org/rfp-analyzer.git
cd rfp-analyzer/app

# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your Azure endpoints

# Run the application
uv run streamlit run main.py
```

Open `http://localhost:8501` in your browser.

### Option 2: Deploy to Azure (Production)

```bash
# Clone the repository
git clone https://github.com/amgdy/rfp-analyzer.git
cd rfp-analyzer

# Login to Azure
az login

# Deploy with Azure Developer CLI
azd up
```

The command will:
1. Create all required Azure resources
2. Build and deploy the application
3. Output the application URL

## Using the Application

### Step 1: Upload Documents

1. Click **"Upload RFP Document"** and select your RFP file
2. Click **"Upload Vendor Proposals"** and select one or more proposal files
3. Supported formats: PDF, DOCX, PNG, JPG

### Step 2: Extract Content

1. Select extraction service:
   - **Content Understanding**: Best for complex documents
   - **Document Intelligence**: Best for structured documents
2. Click **"Extract All Documents"**
3. Wait for processing to complete

### Step 3: Evaluate & Compare

1. Click **"Start Evaluation"**
2. The AI will:
   - Extract evaluation criteria from the RFP
   - Score each proposal
   - Generate comparative rankings
3. Review results in the interface

### Step 4: Export Results

Download your results:
- **CSV**: Spreadsheet with all metrics
- **Word**: Detailed reports per vendor
- **JSON**: Raw data for integration

## Configuration Options

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_OPENAI_ENDPOINT` | Yes | Azure OpenAI endpoint |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Yes | Model deployment name |
| `AZURE_CONTENT_UNDERSTANDING_ENDPOINT` | Yes* | Content Understanding endpoint |
| `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` | Yes* | Document Intelligence endpoint |

*At least one extraction service endpoint is required.

### Customization

- **Scoring Criteria**: Edit `app/scoring_guide.md` to customize default evaluation criteria
- **Model Selection**: Change `AZURE_OPENAI_DEPLOYMENT_NAME` to use different models

## Troubleshooting

### Authentication Errors

```
Azure.Identity.CredentialUnavailableException
```

**Solution**: Run `az login` to authenticate with Azure CLI.

### Missing Endpoint Errors

```
AZURE_OPENAI_ENDPOINT environment variable is required
```

**Solution**: Ensure your `.env` file has all required variables set.

### Document Extraction Fails

**Solution**: 
1. Check file format is supported (PDF, DOCX, images)
2. Verify the extraction service endpoint is correct
3. Check Azure service quotas and limits

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Review [ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design
- Check [CONTRIBUTING.md](CONTRIBUTING.md) to contribute

## Support

- **Issues**: [GitHub Issues](https://github.com/amgdy/rfp-analyzer/issues)
- **Documentation**: [docs/](docs/)
