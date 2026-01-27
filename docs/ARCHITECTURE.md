# RFP Analyzer Architecture

This document provides a comprehensive overview of the RFP Analyzer application architecture, including component diagrams, data flow, and Azure resource topology.

## Table of Contents

- [System Overview](#system-overview)
- [Application Architecture](#application-architecture)
- [Component Architecture](#component-architecture)
- [Multi-Agent System](#multi-agent-system)
- [Azure Infrastructure](#azure-infrastructure)
- [Data Flow](#data-flow)
- [Security Architecture](#security-architecture)

---

## System Overview

RFP Analyzer is a cloud-native application that leverages Azure AI services to automate the evaluation of vendor proposals against RFP requirements. The system uses a multi-agent architecture powered by Azure OpenAI to provide intelligent, consistent, and scalable proposal evaluation.

### Architecture Principles

- **Cloud-Native**: Designed for Azure Container Apps with managed scaling
- **Serverless AI**: Leverages Azure AI services without managing infrastructure
- **Secure by Default**: Uses managed identities and RBAC for authentication
- **Observable**: Integrated monitoring with Application Insights and Log Analytics

---

## Application Architecture

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE                                     │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                         Streamlit Web Application                         │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │  │
│  │  │   Upload    │  │  Extract    │  │  Evaluate   │  │     Export      │  │  │
│  │  │   Panel     │  │   Panel     │  │    Panel    │  │     Panel       │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                            APPLICATION LAYER                                    │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │                        Document Processor                               │    │
│  │  ┌─────────────────────────┐  ┌─────────────────────────────────────┐  │    │
│  │  │  Content Understanding  │  │     Document Intelligence Client    │  │    │
│  │  │        Client           │  │                                     │  │    │
│  │  └─────────────────────────┘  └─────────────────────────────────────┘  │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│                                                                                 │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │                      Multi-Agent Scoring System                         │    │
│  │  ┌──────────────┐  ┌───────────────────┐  ┌─────────────────────────┐  │    │
│  │  │   Criteria   │  │     Proposal      │  │      Comparison         │  │    │
│  │  │  Extraction  │──│     Scoring       │──│        Agent            │  │    │
│  │  │    Agent     │  │      Agent        │  │                         │  │    │
│  │  └──────────────┘  └───────────────────┘  └─────────────────────────┘  │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│                                                                                 │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │                          Support Services                               │    │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐    │    │
│  │  │  Processing     │  │    Logging      │  │    Report           │    │    │
│  │  │    Queue        │  │   Config        │  │   Generator         │    │    │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────┘    │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                             AZURE AI SERVICES                                   │
│  ┌────────────────┐  ┌───────────────────┐  ┌───────────────────────────────┐  │
│  │  Azure OpenAI  │  │      Azure        │  │    Azure AI Content          │  │
│  │   (GPT-4.1+)   │  │   Document        │  │     Understanding            │  │
│  │                │  │  Intelligence     │  │                              │  │
│  └────────────────┘  └───────────────────┘  └───────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### Core Components

#### 1. Streamlit Web Application (`main.py`)

The main entry point providing an interactive web interface:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Streamlit Application                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   Session State Manager                  │    │
│  │  • Document storage    • Extraction results              │    │
│  │  • Evaluation results  • UI state                        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────┐ │
│  │  Step 1:     │ │  Step 2:     │ │  Step 3:                 │ │
│  │  Upload      │ │  Extract     │ │  Evaluate & Compare      │ │
│  │              │ │              │ │                          │ │
│  │ • RFP file   │ │ • Service    │ │ • Criteria extraction    │ │
│  │ • Proposals  │ │   selection  │ │ • Proposal scoring       │ │
│  │ • Preview    │ │ • Progress   │ │ • Vendor comparison      │ │
│  │              │ │ • Results    │ │ • Export options         │ │
│  └──────────────┘ └──────────────┘ └──────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

#### 2. Document Processor (`document_processor.py`)

Orchestrates document extraction across multiple Azure AI services:

```
┌─────────────────────────────────────────────────────────────────┐
│                     Document Processor                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  Service Selector                        │    │
│  │                                                          │    │
│  │   ExtractionService.CONTENT_UNDERSTANDING ──────┐        │    │
│  │                                                 │        │    │
│  │   ExtractionService.DOCUMENT_INTELLIGENCE ─────┐│        │    │
│  └────────────────────────────────────────────────┼┼────────┘    │
│                                                   ││             │
│  ┌────────────────────────────────────────────────┼┼────────┐    │
│  │                  Client Layer                  ││        │    │
│  │                                                ▼▼        │    │
│  │  ┌─────────────────────┐  ┌─────────────────────────┐   │    │
│  │  │  Content            │  │   Document              │   │    │
│  │  │  Understanding      │  │   Intelligence          │   │    │
│  │  │  Client             │  │   Client                │   │    │
│  │  │                     │  │                         │   │    │
│  │  │  • Analyzer API     │  │  • Layout model         │   │    │
│  │  │  • Multi-modal      │  │  • Pre-built models     │   │    │
│  │  │  • Markdown output  │  │  • Markdown output      │   │    │
│  │  └─────────────────────┘  └─────────────────────────┘   │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Supported Formats: PDF, DOCX, PNG, JPG, JPEG, BMP, TIFF         │
└─────────────────────────────────────────────────────────────────┘
```

#### 3. Multi-Agent Scoring System (`scoring_agent_v2.py`)

Implements the AI-powered evaluation using specialized agents:

```
┌─────────────────────────────────────────────────────────────────┐
│                   Scoring Agent V2 System                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Criteria Extraction Agent                   │    │
│  │                                                          │    │
│  │  Input:  RFP Document (Markdown)                         │    │
│  │  Output: ExtractedCriteria                               │    │
│  │          • rfp_title                                     │    │
│  │          • rfp_summary                                   │    │
│  │          • criteria[] (with weights)                     │    │
│  │          • evaluation_guidance                           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │               Proposal Scoring Agent                     │    │
│  │                                                          │    │
│  │  Input:  Proposal + ExtractedCriteria                    │    │
│  │  Output: ProposalEvaluationV2                            │    │
│  │          • total_score                                   │    │
│  │          • criterion_scores[]                            │    │
│  │          • strengths / weaknesses                        │    │
│  │          • recommendation                                │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Pydantic Models:                                                │
│  • ScoringCriterion    • ExtractedCriteria                      │
│  • CriterionScore      • ProposalEvaluationV2                   │
└─────────────────────────────────────────────────────────────────┘
```

#### 4. Comparison Agent (`comparison_agent.py`)

Compares multiple vendor evaluations and generates comparative analysis:

```
┌─────────────────────────────────────────────────────────────────┐
│                     Comparison Agent                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Input: List[ProposalEvaluationV2]                               │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   Analysis Engine                        │    │
│  │                                                          │    │
│  │  1. Rank vendors by total score                          │    │
│  │  2. Compare performance by criterion                     │    │
│  │  3. Identify patterns across vendors                     │    │
│  │  4. Generate recommendations                             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  Output: ComparisonResult                                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  • vendor_rankings: List[VendorRanking]                  │    │
│  │  • criterion_comparisons: List[CriterionComparison]      │    │
│  │  • winner_summary                                        │    │
│  │  • comparison_insights                                   │    │
│  │  • selection_recommendation                              │    │
│  │  • risk_comparison                                       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Report Generation:                                              │
│  • generate_word_report()                                        │
│  • generate_full_analysis_report()                               │
│  • CSV export                                                    │
│  • JSON export                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Multi-Agent System

The evaluation pipeline uses a sequential multi-agent architecture:

```
                    RFP Document                    Vendor Proposals
                         │                                │
                         ▼                                │
┌──────────────────────────────────────┐                  │
│     AGENT 1: Criteria Extraction     │                  │
│                                      │                  │
│  • Analyzes RFP requirements         │                  │
│  • Identifies evaluation criteria    │                  │
│  • Assigns weights (total = 100%)    │                  │
│  • Provides scoring guidance         │                  │
│                                      │                  │
│  Model: Azure OpenAI (GPT-4.1+)      │                  │
│  Output: ExtractedCriteria           │                  │
└──────────────────────────────────────┘                  │
                         │                                │
                         ▼                                │
              ┌─────────────────────┐                     │
              │  Extracted Criteria │◄────────────────────┘
              │  (JSON/Pydantic)    │
              └─────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   AGENT 2    │ │   AGENT 2    │ │   AGENT 2    │
│   Scoring    │ │   Scoring    │ │   Scoring    │
│  (Vendor A)  │ │  (Vendor B)  │ │  (Vendor N)  │
│              │ │              │ │              │
│ • Evaluates  │ │ • Evaluates  │ │ • Evaluates  │
│   proposal   │ │   proposal   │ │   proposal   │
│ • Scores per │ │ • Scores per │ │ • Scores per │
│   criterion  │ │   criterion  │ │   criterion  │
│ • Provides   │ │ • Provides   │ │ • Provides   │
│   evidence   │ │   evidence   │ │   evidence   │
└──────────────┘ └──────────────┘ └──────────────┘
          │              │              │
          └──────────────┼──────────────┘
                         │
                         ▼
┌──────────────────────────────────────┐
│       AGENT 3: Comparison            │
│                                      │
│  • Ranks all vendors by score        │
│  • Compares criterion performance    │
│  • Identifies best/worst performers  │
│  • Generates recommendations         │
│  • Assesses comparative risks        │
│                                      │
│  Model: Azure OpenAI (GPT-4.1+)      │
│  Output: ComparisonResult            │
└──────────────────────────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │    Final Reports    │
              │  • Word documents   │
              │  • CSV exports      │
              │  • JSON data        │
              └─────────────────────┘
```

### Agent Communication Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agent Framework Integration                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │           AzureOpenAIResponsesClient                     │    │
│  │                                                          │    │
│  │  • Structured output generation                          │    │
│  │  • Pydantic model integration                            │    │
│  │  • Automatic JSON schema generation                      │    │
│  │  • Response validation                                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    DefaultAzureCredential                │    │
│  │                                                          │    │
│  │  Authentication flow:                                    │    │
│  │  1. Managed Identity (in Azure)                          │    │
│  │  2. Azure CLI (local development)                        │    │
│  │  3. Environment variables                                │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Azure Infrastructure

### Resource Topology

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Azure Subscription                                   │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    Resource Group: rg-{env-name}                       │  │
│  │                                                                        │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │              Azure AI Foundry Account (AIServices)               │  │  │
│  │  │                                                                  │  │  │
│  │  │  Capabilities:                                                   │  │  │
│  │  │  • OpenAI Language Model Instance API                            │  │  │
│  │  │  • Form Recognizer (Document Intelligence)                       │  │  │
│  │  │  • Content Understanding                                         │  │  │
│  │  │                                                                  │  │  │
│  │  │  ┌────────────────────────────────────────────────────────────┐ │  │  │
│  │  │  │                  Model Deployments                          │ │  │  │
│  │  │  │                                                             │ │  │  │
│  │  │  │  ┌──────────────┐ ┌──────────────┐ ┌───────────────────┐  │ │  │  │
│  │  │  │  │   gpt-5.2    │ │   gpt-4.1    │ │   gpt-4.1-mini    │  │ │  │  │
│  │  │  │  │              │ │              │ │                   │  │ │  │  │
│  │  │  │  │ GlobalStd    │ │ GlobalStd    │ │   GlobalStd       │  │ │  │  │
│  │  │  │  │ 100K TPM     │ │ 100K TPM     │ │   100K TPM        │  │ │  │  │
│  │  │  │  └──────────────┘ └──────────────┘ └───────────────────┘  │ │  │  │
│  │  │  │                                                             │ │  │  │
│  │  │  │  ┌─────────────────────────────────────────────────────┐  │ │  │  │
│  │  │  │  │           text-embedding-3-large                     │  │ │  │  │
│  │  │  │  │           GlobalStd | 300K TPM                       │  │ │  │  │
│  │  │  │  └─────────────────────────────────────────────────────┘  │ │  │  │
│  │  │  └────────────────────────────────────────────────────────────┘ │  │  │
│  │  │                                                                  │  │  │
│  │  │  ┌────────────────────────────────────────────────────────────┐ │  │  │
│  │  │  │                   AI Foundry Project                        │ │  │  │
│  │  │  │                                                             │ │  │  │
│  │  │  │  ┌───────────────────────────────────────────────────────┐ │ │  │  │
│  │  │  │  │  App Insights Connection                               │ │ │  │  │
│  │  │  │  │  (Telemetry integration)                               │ │ │  │  │
│  │  │  │  └───────────────────────────────────────────────────────┘ │ │  │  │
│  │  │  └────────────────────────────────────────────────────────────┘ │  │  │
│  │  └──────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                        │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │                    Monitoring Stack                              │  │  │
│  │  │                                                                  │  │  │
│  │  │  ┌────────────────────┐  ┌────────────────────────────────┐    │  │  │
│  │  │  │  Log Analytics     │  │    Application Insights         │    │  │  │
│  │  │  │  Workspace         │◄─│                                 │    │  │  │
│  │  │  │                    │  │  • Performance metrics          │    │  │  │
│  │  │  │  • Container logs  │  │  • Request tracing              │    │  │  │
│  │  │  │  • AI service logs │  │  • Exception tracking           │    │  │  │
│  │  │  │  • Custom metrics  │  │  • Custom events                │    │  │  │
│  │  │  └────────────────────┘  └────────────────────────────────┘    │  │  │
│  │  │                                                                  │  │  │
│  │  │  ┌────────────────────────────────────────────────────────┐    │  │  │
│  │  │  │              Application Insights Dashboard             │    │  │  │
│  │  │  └────────────────────────────────────────────────────────┘    │  │  │
│  │  └──────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                        │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │                    Container Platform                            │  │  │
│  │  │                                                                  │  │  │
│  │  │  ┌────────────────────┐  ┌────────────────────────────────┐    │  │  │
│  │  │  │  Container         │  │  Container Apps Environment    │    │  │  │
│  │  │  │  Registry          │  │                                │    │  │  │
│  │  │  │                    │  │  ┌──────────────────────────┐  │    │  │  │
│  │  │  │  • rfp-analyzer    │──│  │   rfp-analyzer           │  │    │  │  │
│  │  │  │    image           │  │  │   Container App          │  │    │  │  │
│  │  │  │                    │  │  │                          │  │    │  │  │
│  │  │  │  SKU: Standard     │  │  │   Port: 8501             │  │    │  │  │
│  │  │  │                    │  │  │   CPU: 2 cores           │  │    │  │  │
│  │  │  │                    │  │  │   Memory: 4Gi            │  │    │  │  │
│  │  │  │                    │  │  │   Min: 1, Max: 10        │  │    │  │  │
│  │  │  └────────────────────┘  │  └──────────────────────────┘  │    │  │  │
│  │  │                          └────────────────────────────────┘    │  │  │
│  │  └──────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                        │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │               User-Assigned Managed Identity                     │  │  │
│  │  │                                                                  │  │  │
│  │  │  Role Assignments:                                               │  │  │
│  │  │  • Azure AI Developer (Resource Group scope)                     │  │  │
│  │  │  • Cognitive Services User (Resource Group scope)                │  │  │
│  │  │  • AcrPull (Container Registry scope)                            │  │  │
│  │  └──────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Infrastructure as Code (Bicep)

```
infra/
├── main.bicep                 # Entry point - subscription scope
│   ├── Creates resource group
│   └── Invokes resources.bicep
│
├── main.parameters.json       # Deployment parameters
│
├── resources.bicep            # All resource definitions
│   ├── Azure AI Foundry Account (AIServices)
│   │   └── Model deployments (GPT-5.2, GPT-4.1, etc.)
│   ├── AI Foundry Project
│   │   └── App Insights connection
│   ├── Monitoring (Log Analytics + App Insights)
│   ├── Container Registry
│   ├── Container Apps Environment
│   ├── Container App (rfp-analyzer)
│   ├── Managed Identity
│   └── Role Assignments
│
├── abbreviations.json         # Resource naming conventions
│
├── modules/
│   └── fetch-container-image.bicep
│
└── hooks/
    ├── postprovision.sh       # Post-deployment (Linux/macOS)
    └── postprovision.ps1      # Post-deployment (Windows)
```

### Bicep Module Dependencies

```
main.bicep (subscription scope)
     │
     ├──► rfpResourceGroup (AVM module)
     │         │
     │         └──► resources.bicep (resource group scope)
     │                   │
     │                   ├──► monitoring (AVM pattern)
     │                   │         │
     │                   │         ├──► Log Analytics Workspace
     │                   │         ├──► Application Insights
     │                   │         └──► Dashboard
     │                   │
     │                   ├──► rfpAnalyzerIdentity (AVM module)
     │                   │         └──► User-Assigned Managed Identity
     │                   │
     │                   ├──► foundryAccount (AVM module)
     │                   │         │
     │                   │         ├──► AIServices Account
     │                   │         └──► Model Deployments
     │                   │
     │                   ├──► foundryProject (native resource)
     │                   │         └──► App Insights Connection
     │                   │
     │                   ├──► containerRegistry (AVM module)
     │                   │
     │                   ├──► containerAppsEnvironment (AVM module)
     │                   │
     │                   ├──► rfpAnalyzerFetchLatestImage (custom module)
     │                   │
     │                   ├──► rfpAnalyzer (AVM module)
     │                   │         └──► Container App
     │                   │
     │                   └──► Role Assignments (AVM modules)
     │                             ├──► Azure AI Developer
     │                             └──► Cognitive Services User
     │
     └──► Outputs
              ├──► AZURE_CONTAINER_REGISTRY_ENDPOINT
              ├──► AZURE_RESOURCE_RFP_ANALYZER_ID
              ├──► AZURE_OPENAI_ENDPOINT
              ├──► AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT
              └──► AZURE_CONTENT_UNDERSTANDING_ENDPOINT
```

---

## Data Flow

### Document Processing Flow

```
┌─────────────────┐
│  User uploads   │
│  document(s)    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Document Processor                            │
│                                                                  │
│  1. Validate file type (PDF, DOCX, PNG, JPG, etc.)               │
│  2. Read file bytes into memory                                  │
│  3. Select extraction service based on user choice               │
└────────────────────────────────────────────────────────────────┬─┘
                                                                 │
         ┌───────────────────────────────────────────────────────┤
         │                                                       │
         ▼                                                       ▼
┌─────────────────────────┐                    ┌─────────────────────────┐
│  Content Understanding  │                    │  Document Intelligence  │
│                         │                    │                         │
│  POST /contentunder-    │                    │  POST /documentModels/  │
│       standing/analyzer │                    │       prebuilt-layout:  │
│                         │                    │       analyze           │
│  • Create analyzer      │                    │                         │
│  • Upload document      │                    │  • Submit for analysis  │
│  • Poll for results     │                    │  • Poll for results     │
│  • Get markdown output  │                    │  • Extract markdown     │
└────────────┬────────────┘                    └────────────┬────────────┘
             │                                              │
             └──────────────────┬───────────────────────────┘
                                │
                                ▼
                   ┌─────────────────────────┐
                   │   Extracted Markdown    │
                   │                         │
                   │  Stored in session:     │
                   │  • RFP content          │
                   │  • Proposal contents[]  │
                   └─────────────────────────┘
```

### Evaluation Pipeline Flow

```
                         Session State
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
   │ RFP Markdown │   │ Proposal 1   │   │ Proposal N   │
   └──────┬───────┘   │  Markdown    │   │  Markdown    │
          │           └──────┬───────┘   └──────┬───────┘
          │                  │                  │
          ▼                  │                  │
┌───────────────────┐        │                  │
│ Criteria          │        │                  │
│ Extraction Agent  │        │                  │
│                   │        │                  │
│ Azure OpenAI Call │        │                  │
│ (structured output)        │                  │
└─────────┬─────────┘        │                  │
          │                  │                  │
          ▼                  │                  │
┌───────────────────┐        │                  │
│ ExtractedCriteria │        │                  │
│ (Pydantic model)  │────────┼──────────────────┤
└───────────────────┘        │                  │
                             │                  │
                             ▼                  ▼
                    ┌────────────────┐  ┌────────────────┐
                    │ Scoring Agent  │  │ Scoring Agent  │
                    │ (Proposal 1)   │  │ (Proposal N)   │
                    │                │  │                │
                    │ Azure OpenAI   │  │ Azure OpenAI   │
                    │ (parallel)     │  │ (parallel)     │
                    └───────┬────────┘  └───────┬────────┘
                            │                   │
                            ▼                   ▼
                    ┌────────────────┐  ┌────────────────┐
                    │ Evaluation V2  │  │ Evaluation V2  │
                    │ (Vendor 1)     │  │ (Vendor N)     │
                    └───────┬────────┘  └───────┬────────┘
                            │                   │
                            └─────────┬─────────┘
                                      │
                                      ▼
                         ┌─────────────────────┐
                         │  Comparison Agent   │
                         │                     │
                         │  • Rank vendors     │
                         │  • Compare criteria │
                         │  • Recommend winner │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │  ComparisonResult   │
                         │                     │
                         │  Available exports: │
                         │  • Word documents   │
                         │  • CSV comparison   │
                         │  • JSON data        │
                         └─────────────────────┘
```

---

## Security Architecture

### Authentication Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Authentication Architecture                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                 DefaultAzureCredential                   │    │
│  │                                                          │    │
│  │  Credential Chain (tried in order):                      │    │
│  │                                                          │    │
│  │  1. EnvironmentCredential                                │    │
│  │     └─ AZURE_CLIENT_ID, AZURE_TENANT_ID,                 │    │
│  │        AZURE_CLIENT_SECRET (Service Principal)           │    │
│  │                                                          │    │
│  │  2. ManagedIdentityCredential ◄── Used in Azure          │    │
│  │     └─ User-Assigned Managed Identity                    │    │
│  │        (AZURE_CLIENT_ID env var)                         │    │
│  │                                                          │    │
│  │  3. AzureCliCredential ◄── Used in local dev             │    │
│  │     └─ 'az login' session                                │    │
│  │                                                          │    │
│  │  4. AzurePowerShellCredential                            │    │
│  │  5. VisualStudioCodeCredential                           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                     Token Acquisition                    │    │
│  │                                                          │    │
│  │  Scope: https://cognitiveservices.azure.com/.default     │    │
│  │                                                          │    │
│  │  Token used for:                                         │    │
│  │  • Azure OpenAI API calls                                │    │
│  │  • Content Understanding API calls                       │    │
│  │  • Document Intelligence API calls                       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### RBAC Configuration

```
┌─────────────────────────────────────────────────────────────────┐
│                     Role-Based Access Control                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │            User-Assigned Managed Identity                │    │
│  │                 (rfp-analyzer-identity)                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│       ┌──────────────────────┼──────────────────────┐           │
│       │                      │                      │           │
│       ▼                      ▼                      ▼           │
│  ┌──────────────┐   ┌────────────────┐   ┌─────────────────┐   │
│  │ Azure AI     │   │  Cognitive     │   │    AcrPull      │   │
│  │ Developer    │   │  Services      │   │                 │   │
│  │              │   │  User          │   │  Scope:         │   │
│  │ Scope:       │   │                │   │  Container      │   │
│  │ Resource     │   │  Scope:        │   │  Registry       │   │
│  │ Group        │   │  Resource      │   │                 │   │
│  │              │   │  Group         │   │  Allows:        │   │
│  │ Allows:      │   │                │   │  • Pull images  │   │
│  │ • Create/    │   │  Allows:       │   │                 │   │
│  │   manage AI  │   │  • Use AI      │   └─────────────────┘   │
│  │   resources  │   │    services    │                         │
│  │ • Deploy     │   │  • Make API    │                         │
│  │   models     │   │    calls       │                         │
│  └──────────────┘   └────────────────┘                         │
│                                                                  │
│  Security Features:                                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  • No stored credentials in application code             │    │
│  │  • Keys rotation handled by Azure                        │    │
│  │  • Audit logging via Azure Activity Log                  │    │
│  │  • Network isolation available (private endpoints)       │    │
│  │  • disableLocalAuth: true on AI Services account         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Deployment Architecture

### Azure Developer CLI (azd) Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                      azd up Workflow                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Step 1: Initialize                                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  azd init                                                │    │
│  │  • Creates .azure/ directory                             │    │
│  │  • Selects subscription and location                     │    │
│  │  • Creates environment configuration                     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  Step 2: Provision Infrastructure                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  azd provision                                           │    │
│  │  • Deploys main.bicep at subscription scope              │    │
│  │  • Creates resource group                                │    │
│  │  • Provisions all Azure resources                        │    │
│  │  • Configures role assignments                           │    │
│  │  • Runs postprovision hooks                              │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  Step 3: Build & Deploy Application                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  azd deploy                                              │    │
│  │  • Builds Docker image (remote build)                    │    │
│  │  • Pushes to Azure Container Registry                    │    │
│  │  • Updates Container App with new image                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  Step 4: Output                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Environment variables and URLs                          │    │
│  │  • Application URL                                       │    │
│  │  • Azure OpenAI endpoint                                 │    │
│  │  • Content Understanding endpoint                        │    │
│  │  • Document Intelligence endpoint                        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Container Deployment

```
┌─────────────────────────────────────────────────────────────────┐
│                    Container Deployment Flow                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                      Source Code                         │    │
│  │                         (app/)                           │    │
│  └────────────────────────────┬────────────────────────────┘    │
│                               │                                  │
│                               ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                     Dockerfile                           │    │
│  │                                                          │    │
│  │  FROM python:3.13-slim                                   │    │
│  │  • Install UV package manager                            │    │
│  │  • Copy pyproject.toml, uv.lock                          │    │
│  │  • Install dependencies                                  │    │
│  │  • Copy application code                                 │    │
│  │  • EXPOSE 8501                                           │    │
│  │  • CMD: streamlit run main.py                            │    │
│  └────────────────────────────┬────────────────────────────┘    │
│                               │                                  │
│                               ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Azure Container Registry                    │    │
│  │                                                          │    │
│  │  • Remote build (Cloud Build)                            │    │
│  │  • Image: {acr}.azurecr.io/rfp-analyzer:latest           │    │
│  └────────────────────────────┬────────────────────────────┘    │
│                               │                                  │
│                               ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │             Azure Container Apps                         │    │
│  │                                                          │    │
│  │  Configuration:                                          │    │
│  │  • Ingress: External, port 8501                          │    │
│  │  • Scale: 1-10 replicas                                  │    │
│  │  • Resources: 2 CPU, 4GB memory                          │    │
│  │  • Identity: User-assigned managed identity              │    │
│  │                                                          │    │
│  │  Environment Variables:                                  │    │
│  │  • AZURE_OPENAI_ENDPOINT                                 │    │
│  │  • AZURE_OPENAI_DEPLOYMENT_NAME                          │    │
│  │  • AZURE_CONTENT_UNDERSTANDING_ENDPOINT                  │    │
│  │  • AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT                  │    │
│  │  • AZURE_CLIENT_ID (managed identity)                    │    │
│  │  • APPLICATIONINSIGHTS_CONNECTION_STRING                 │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Monitoring & Observability

```
┌─────────────────────────────────────────────────────────────────┐
│                    Observability Stack                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   Application Layer                      │    │
│  │                                                          │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │    │
│  │  │  Logging    │  │  Metrics    │  │    Tracing      │  │    │
│  │  │  (Python)   │  │ (Custom)    │  │  (OpenTelemetry)│  │    │
│  │  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘  │    │
│  └─────────┼────────────────┼──────────────────┼───────────┘    │
│            │                │                  │                 │
│            └────────────────┼──────────────────┘                 │
│                             │                                    │
│                             ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Application Insights SDK                    │    │
│  │                                                          │    │
│  │  • azure-monitor-opentelemetry                           │    │
│  │  • Automatic instrumentation for HTTP, Azure SDK         │    │
│  │  • Custom spans for agent operations                     │    │
│  └────────────────────────────┬────────────────────────────┘    │
│                               │                                  │
│                               ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │               Application Insights                       │    │
│  │                                                          │    │
│  │  • Live Metrics Stream                                   │    │
│  │  • Transaction Search                                    │    │
│  │  • Application Map                                       │    │
│  │  • Failures and Performance                              │    │
│  └────────────────────────────┬────────────────────────────┘    │
│                               │                                  │
│                               ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Log Analytics Workspace                     │    │
│  │                                                          │    │
│  │  Tables:                                                 │    │
│  │  • AppTraces - Application logs                          │    │
│  │  • AppRequests - HTTP requests                           │    │
│  │  • AppDependencies - External calls                      │    │
│  │  • AppExceptions - Errors                                │    │
│  │  • ContainerAppConsoleLogs - Container logs              │    │
│  │  • ContainerAppSystemLogs - Platform logs                │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Additional Resources

- [Azure AI Foundry Documentation](https://learn.microsoft.com/azure/ai-studio/)
- [Azure Container Apps Documentation](https://learn.microsoft.com/azure/container-apps/)
- [Azure Developer CLI Documentation](https://learn.microsoft.com/azure/developer/azure-developer-cli/)
- [Bicep Documentation](https://learn.microsoft.com/azure/azure-resource-manager/bicep/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
