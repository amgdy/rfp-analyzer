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
