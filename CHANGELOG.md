# Changelog

All notable changes to the RFP Analyzer project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-04-13

### Added

#### Document Protection Detection
- **Encrypted/IRM document detection** — password-protected and IRM-protected PDFs and DOCX files are now detected *before* calling Azure extraction services, giving users a clear, actionable error message
- Added `pypdf` dependency for PDF encryption detection via `PdfReader.is_encrypted`
- Added `msoffcrypto-tool` dependency for DOCX encryption/IRM detection via `OfficeFile.is_encrypted()`
- New `check_document_protection()` utility in `services/utils.py`
- Upload UI shows an info box explaining that protected documents are not supported

#### Confidence Scoring & Re-Reasoning
- **Confidence scores (0.0–1.0)** on `ScoringCriterion`, `ExtractedCriteria`, `CriterionScore`, and `ProposalEvaluation` models
- **Automatic re-reasoning** — when overall confidence falls below `CONFIDENCE_THRESHOLD` (default 0.7, configurable via env var), the system runs a deeper analysis pass with increased reasoning effort
- Re-reasoning capped at one extra pass per agent to control costs
- `reasoning_iterations` field on `CriterionScore` tracks how many passes were used
- Confidence badges in criteria review UI (🟢 High / 🟡 Medium / 🔴 Low)
- Confidence display in scoring results with re-reasoning progress indicators

#### Document Processing Improvements
- **Local DOCX extraction** via `python-docx` when using Document Intelligence (which does not support DOCX natively)
- **Corrupt file handling** — renamed `.doc` files and corrupt DOCX archives produce clear `ValueError` messages instead of cryptic stack traces
- **File type awareness** in upload and extraction UIs — PDF/DOCX flagged as AI-extracted; TXT/MD shown as instant read
- Removed `.doc` from the upload type list (unsupported by both `python-docx` and Document Intelligence)

#### Resilience & Retry Logic
- **AI refusal detection** — 7 refusal phrase patterns (e.g. "I'm sorry, but I cannot assist") are detected by `check_for_refusal()` and automatically retried
- **Exponential backoff** on all `agent.run()` OpenAI calls
- **Empty response handling** — `"empty response"` added to retryable substrings for automatic retry on empty model output
- **Token-aware large document chunking** — documents exceeding the model context window (configurable `MAX_CONTEXT_TOKENS`, default 1,050,000) are automatically split using a map-reduce pattern with heading/paragraph boundaries and overlap tokens

#### Visualization & Charts
- **Consistent vendor colors** across all dashboard charts using a 12-color deterministic palette
- Vendors sorted alphabetically so colors are stable across sessions

#### Non-Proposal Filtering
- **Non-proposal document detection** — documents that are clearly not vendor proposals (e.g. cover letters, supplementary info) are detected and excluded from scoring with disqualification reasons shown in the report
- **Filename fallback** — when vendor name cannot be extracted from content, falls back to the proposal filename

#### Extraction Quality
- **Cleaner markdown output** — `clean_extracted_markdown()` improves markdown from both Content Understanding and Document Intelligence
- **Table summaries** — Document Intelligence client produces descriptive table summaries
- **Improved figure descriptions** — figure elements include surrounding content for better AI comprehension

### Changed

#### Infrastructure
- Bumped version from 0.2.0 to 0.3.0
- Updated IaC resource names to Microsoft CAF naming convention (`<abbreviation><workload>-<resourceToken>`)
- Endpoint configuration no longer includes `/openai/` suffix (SDK adds it automatically)
- OTEL logging auto-enables when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set
- Container App resources: 2 CPU / 4Gi (Consumption plan max)

#### Dependencies
- Added `pypdf>=5.0.0` for PDF protection detection
- Added `msoffcrypto-tool>=5.4.0` for DOCX encryption/IRM detection
- Upgraded all Python packages and AVM Bicep module versions
- Migrated agent-framework imports from `azure` to `openai` module (1.0.1 API)

#### Code Quality
- Extracted constants for DOCX extensions and heading levels
- Centralized logging with structured span context across all pipeline functions
- 260 unit tests (up from 198 in v0.2.0)

## [0.2.0] - 2026-04-12

### Added

#### Observability & Telemetry
- **OpenTelemetry distributed tracing** with spans across all pipeline operations (document processing, criteria extraction, proposal scoring, evaluation)
- **OTLP exporter support** for Aspire Dashboard, Jaeger, and other OTLP-compatible backends
- **Azure Monitor trace exporter** for Application Insights integration
- **OTLP log exporter** bridges console logs to OTEL collectors (Aspire Dashboard / App Insights)
- **Agent Framework observability** integration via `configure_otel_providers()`
- New `services/telemetry.py` module with `setup_telemetry()` and `get_tracer()` helpers
- `OTEL_TRACING_ENABLED` environment variable to control tracing
- `ENABLE_SENSITIVE_DATA` environment variable for AI prompt/response logging in dev

#### User Experience
- **Criteria download button** — download extracted scoring criteria as JSON from Step 3 for user reference
- **App version display** in sidebar (v0.2.0)
- Disqualified non-proposal documents shown with reasons in the scoring report

#### Developer Experience
- **VS Code launch configuration** "Streamlit: Run with OTEL (Aspire Dashboard)" with pre-launch task
- **VS Code tasks** for starting/stopping Aspire Dashboard Docker container
- Updated `.env.example` with comprehensive OTEL configuration section
- 6 new telemetry tests (198 total)

### Changed

#### Infrastructure
- **Container App resources increased** from 2 CPU / 4Gi to 4 CPU / 8Gi memory for large document processing
- **Docker Compose memory limits** increased from 2G/512M to 4G/1G
- **OTEL_LOGGING_ENABLED** and **OTEL_TRACING_ENABLED** enabled in Azure Container App deployment
- Added OpenTelemetry env vars to Container App configuration

#### Dependencies
- Added `opentelemetry-api>=1.20.0`
- Added `opentelemetry-sdk>=1.20.0`
- Added `opentelemetry-exporter-otlp-proto-grpc>=1.20.0`
- Version bumped from 0.1.0 to 0.2.0

#### Code Quality
- Enriched structured logging with span context across all pipeline functions
- Test infrastructure updated with OTEL module stubs for CI environments

## [0.1.0] - 2026-01-27

### Added

#### Core Features
- **Document Upload**: Support for PDF, DOCX, PNG, JPG, and other image formats
- **Document Extraction**: Integration with Azure Content Understanding and Azure Document Intelligence
- **Multi-Agent Scoring System**: 
  - Criteria Extraction Agent for analyzing RFP requirements
  - Proposal Scoring Agent for evaluating vendor proposals
  - Comparison Agent for ranking and comparing vendors
- **Export Capabilities**: CSV, Word document, and JSON export options
- **Interactive Charts**: Plotly-based visualizations for score comparisons

#### Azure Integration
- Azure OpenAI integration (GPT-4.1, GPT-5.2 support)
- Azure AI Foundry (Content Understanding)
- Azure Document Intelligence
- Azure Container Apps deployment
- Managed Identity authentication
- Application Insights telemetry

#### Infrastructure
- Bicep templates for Azure resource provisioning
- Azure Developer CLI (azd) support
- Docker and Docker Compose support
- CI/CD ready configuration

#### Developer Experience
- UV package manager support
- Hot reload development mode
- Centralized logging configuration
- Pydantic models for structured data

### Technical Details

#### Dependencies
- Python 3.13+
- Streamlit 1.52+
- Microsoft Agent Framework
- Azure Identity SDK
- Azure AI Document Intelligence SDK
- Pydantic 2.x
- python-docx for Word generation
- Plotly for visualizations

#### Azure Resources Provisioned
- Azure AI Foundry Account (AIServices)
- Azure AI Foundry Project
- Azure Container Registry
- Azure Container Apps Environment
- Azure Container App
- Log Analytics Workspace
- Application Insights
- User-Assigned Managed Identity

#### Security
- Managed Identity for Azure service authentication
- RBAC-based access control
- No stored credentials in application code
- TLS encryption for all communications

---

## Version History

- `0.3.0` - Document protection detection, confidence scoring, re-reasoning, DOCX handling, resilience improvements, 260 tests
- `0.2.0` - OpenTelemetry observability, criteria download, resource scaling, versioning
- `0.1.0` - Initial release with core RFP analysis features

## Upgrade Notes

### Upgrading to 0.1.0

This is the initial release. No upgrade steps required.

### Future Upgrade Considerations

When upgrading between versions:

1. Review the changelog for breaking changes
2. Update dependencies: `uv sync`
3. Review environment variable changes
4. Test in a non-production environment first
5. For Azure deployments, use `azd up` to apply infrastructure changes
