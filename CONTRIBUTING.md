# Contributing to RFP Analyzer

Thank you for your interest in contributing to RFP Analyzer! This document provides guidelines and information for contributors.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Reporting Issues](#reporting-issues)

## Code of Conduct

This project adheres to a code of conduct. By participating, you are expected to uphold this code. Please be respectful and inclusive in all interactions.

## Getting Started

### Prerequisites

Before contributing, ensure you have:

- Python 3.13 or higher
- [UV package manager](https://docs.astral.sh/uv/)
- [Azure CLI](https://docs.microsoft.com/cli/azure/install-azure-cli)
- An Azure subscription with appropriate services
- Git

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/rfp-analyzer.git
   cd rfp-analyzer
   ```
3. Add the upstream remote:
   ```bash
   git remote add upstream https://github.com/ORIGINAL-ORG/rfp-analyzer.git
   ```

## Development Setup

### 1. Install Dependencies

```bash
cd app
uv sync
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your Azure credentials
```

### 3. Authenticate with Azure

```bash
az login
```

### 4. Run the Application

```bash
uv run streamlit run main.py
```

The application will be available at `http://localhost:8501`

### 5. Run with Hot Reload (Development)

```bash
uv run streamlit run main.py --server.runOnSave true
```

## Making Changes

### Branch Naming

Use descriptive branch names following this convention:

- `feature/` - New features (e.g., `feature/export-pdf`)
- `fix/` - Bug fixes (e.g., `fix/scoring-calculation`)
- `docs/` - Documentation updates (e.g., `docs/api-reference`)
- `refactor/` - Code refactoring (e.g., `refactor/agent-structure`)
- `test/` - Test additions/updates (e.g., `test/comparison-agent`)

### Creating a Branch

```bash
# Ensure you're on main and up to date
git checkout main
git pull upstream main

# Create your feature branch
git checkout -b feature/your-feature-name
```

### Making Commits

- Write clear, concise commit messages
- Use present tense ("Add feature" not "Added feature")
- Reference issues when applicable (`Fixes #123`)

Example commit messages:
```
Add PDF export functionality for evaluation reports

- Implement WeasyPrint integration for PDF generation
- Add CSS styling for professional output
- Include table formatting and charts

Fixes #45
```

## Coding Standards

### Python Style Guide

We follow [PEP 8](https://pep8.org/) with the following tools:

- **Formatter**: [Ruff](https://docs.astral.sh/ruff/)
- **Linter**: [Ruff](https://docs.astral.sh/ruff/)
- **Type Hints**: Use type hints for all function signatures

### Code Quality Commands

```bash
# Format code
uv run ruff format .

# Check for linting issues
uv run ruff check .

# Fix auto-fixable issues
uv run ruff check . --fix
```

### Code Style Examples

#### Good Example

```python
from typing import List, Optional
from pydantic import BaseModel, Field

class EvaluationResult(BaseModel):
    """Result of a proposal evaluation.
    
    Attributes:
        vendor_name: Name of the vendor being evaluated
        total_score: Overall weighted score (0-100)
        recommendations: List of actionable recommendations
    """
    vendor_name: str = Field(description="Name of the vendor")
    total_score: float = Field(ge=0, le=100, description="Total score")
    recommendations: List[str] = Field(default_factory=list)

    def get_grade(self) -> str:
        """Calculate letter grade from total score.
        
        Returns:
            Letter grade (A, B, C, D, or F)
        """
        if self.total_score >= 90:
            return "A"
        elif self.total_score >= 80:
            return "B"
        elif self.total_score >= 70:
            return "C"
        elif self.total_score >= 60:
            return "D"
        return "F"
```

### Documentation Standards

- Use docstrings for all public modules, classes, and functions
- Follow [Google-style docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
- Include type hints in function signatures
- Document exceptions that may be raised

### Project Structure

When adding new files, follow the existing structure:

```
app/
├── main.py                    # Streamlit application
├── services/
│   ├── __init__.py
│   ├── document_processor.py  # Document handling
│   ├── scoring_agent.py    # Scoring agents
│   ├── comparison_agent.py    # Comparison agent
│   └── your_new_service.py    # New services go here
└── tests/
    ├── __init__.py
    ├── test_scoring_agent.py
    └── test_your_service.py   # Tests for your service
```

## Testing

### Running Tests

```bash
cd app
uv run pytest
```

### Running Tests with Coverage

```bash
uv run pytest --cov=services --cov-report=html
```

### Writing Tests

- Place tests in the `app/tests/` directory
- Use descriptive test names that explain what is being tested
- Include both positive and negative test cases
- Mock external services (Azure AI) in unit tests

Example test:

```python
import pytest
from services.scoring_agent import CriteriaExtractionAgent, ExtractedCriteria

class TestCriteriaExtractionAgent:
    """Tests for the Criteria Extraction Agent."""

    def test_weights_sum_to_100(self, sample_criteria: ExtractedCriteria):
        """Verify that all criteria weights sum to 100%."""
        total_weight = sum(c.weight for c in sample_criteria.criteria)
        assert abs(total_weight - 100.0) < 0.01, f"Weights sum to {total_weight}, expected 100"

    def test_criterion_has_required_fields(self, sample_criteria: ExtractedCriteria):
        """Verify each criterion has all required fields populated."""
        for criterion in sample_criteria.criteria:
            assert criterion.criterion_id, "Criterion ID is required"
            assert criterion.name, "Criterion name is required"
            assert criterion.weight > 0, "Criterion weight must be positive"
```

## Submitting Changes

### Pull Request Process

1. **Update your branch** with the latest upstream changes:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Push your changes** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

3. **Create a Pull Request** on GitHub:
   - Use a descriptive title
   - Fill out the PR template
   - Reference any related issues

### Pull Request Checklist

Before submitting, ensure:

- [ ] Code follows the project's style guidelines
- [ ] All tests pass locally
- [ ] New functionality includes tests
- [ ] Documentation is updated (if applicable)
- [ ] Commit messages are clear and descriptive
- [ ] Branch is up to date with main

### Pull Request Template

```markdown
## Description
Brief description of the changes made.

## Type of Change
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] Documentation update

## How Has This Been Tested?
Describe the tests you ran to verify your changes.

## Related Issues
Fixes #(issue number)

## Checklist
- [ ] My code follows the style guidelines
- [ ] I have performed a self-review of my code
- [ ] I have added tests that prove my fix/feature works
- [ ] New and existing tests pass locally
```

### Review Process

1. A maintainer will review your PR
2. Address any feedback or requested changes
3. Once approved, your PR will be merged
4. Delete your feature branch after merge

## Reporting Issues

### Bug Reports

When reporting bugs, include:

1. **Description**: Clear description of the bug
2. **Steps to Reproduce**: Detailed steps to reproduce the issue
3. **Expected Behavior**: What you expected to happen
4. **Actual Behavior**: What actually happened
5. **Environment**: 
   - Python version
   - OS
   - Browser (if applicable)
   - Azure service versions
6. **Screenshots/Logs**: If applicable

### Feature Requests

For feature requests, include:

1. **Problem Statement**: What problem does this solve?
2. **Proposed Solution**: Your suggested implementation
3. **Alternatives Considered**: Other approaches you've thought of
4. **Additional Context**: Any other relevant information

## Questions?

If you have questions about contributing, feel free to:

- Open a [GitHub Discussion](https://github.com/amgdy/rfp-analyzer/discussions)
- Review existing issues and PRs for context
- Check the [Architecture Documentation](docs/ARCHITECTURE.md)

Thank you for contributing to RFP Analyzer! 🎉
