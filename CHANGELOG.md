# Changelog

All notable changes to the RFP Analyzer project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive project documentation
- Architecture diagrams and component documentation
- CONTRIBUTING.md with development guidelines
- SECURITY.md with security best practices
- MIT License

### Changed
- Updated README.md with complete project information
- Improved deployment documentation

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
