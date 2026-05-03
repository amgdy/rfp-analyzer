# RFP Analyzer Architecture

This document provides a comprehensive overview of the RFP Analyzer application architecture, including component diagrams, data flow, and Azure resource topology.

## Table of Contents

- [System Overview](#system-overview)
- [Application Architecture](#application-architecture)
- [Component Architecture](#component-architecture)
- [Session State & Persistence](#session-state--persistence)
- [Multi-Agent System](#multi-agent-system)
- [Azure Infrastructure](#azure-infrastructure)
- [Data Flow](#data-flow)
  - [Large Document Chunking Process](#large-document-chunking-process)
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

```mermaid
flowchart TB
    subgraph UI["🖥️ User Interface"]
        direction LR
        ST["Streamlit Web Application"]
        subgraph Panels["Application Panels"]
            UP["📤 Upload Panel"]
            EP["⚙️ Extract Panel"]
            EV["🤖 Evaluate Panel"]
            EX["📊 Export Panel"]
        end
        ST --> Panels
    end

    subgraph APP["⚡ Application Layer"]
        direction TB
        subgraph DP["Document Processor"]
            CU["Content Understanding Client"]
            DI["Document Intelligence Client"]
        end
        
        subgraph MAS["Multi-Agent Scoring System"]
            CEA["Criteria Extraction Agent"]
            PSA["Proposal Scoring Agent"]
            CA["Comparison Agent"]
            CEA --> PSA --> CA
        end
        
        subgraph SS["Support Services"]
            PQ["Processing Queue"]
            LC["Logging Config"]
            RG["Report Generator"]
        end
    end

    subgraph AZURE["☁️ Azure AI Services"]
        direction LR
        AOA["Azure OpenAI<br>(GPT-5.2 / GPT-4.1)"]
        ADI["Azure Document<br>Intelligence"]
        ACU["Azure AI Content<br>Understanding"]
    end

    UI --> APP
    APP --> AZURE
    
    style UI fill:#e1f5fe,stroke:#01579b
    style APP fill:#f3e5f5,stroke:#4a148c
    style AZURE fill:#e8f5e9,stroke:#1b5e20
```

---

## Component Architecture

### Core Components

#### 1. Streamlit Web Application (`main.py`)

The main entry point providing an interactive web interface:

```mermaid
flowchart TB
    subgraph StreamlitApp["Streamlit Application"]
        subgraph SSM["Session & Storage"]
            SID["Session ID (URL query param)"]
            BS["Azure Blob Storage<br>• Uploaded files<br>• Extracted text"]
            ER["Extraction Results (cache)"]
            EVR["Evaluation Results"]
            UIS["UI State"]
        end
        
        subgraph Steps["Workflow Steps"]
            S1["Step 1: Upload<br>• RFP file → Blob<br>• Proposals → Blob<br>• Preview"]
            S2["Step 2: Extract<br>• Service selection<br>• Progress<br>• Results → Blob"]
            S3["Step 3: Criteria<br>• AI-extracted criteria<br>• Weights review<br>• User confirmation"]
            S4["Step 4: Score<br>• Proposal scoring<br>• Vendor comparison<br>• Export options"]
        end
        
        SSM --> Steps
        S1 --> S2 --> S3 --> S4
    end
    
    style StreamlitApp fill:#fff3e0,stroke:#e65100
```

#### 2. Document Processor (`document_processor.py`)

Orchestrates document extraction across multiple Azure AI services:

```mermaid
flowchart TB
    subgraph DocProcessor["Document Processor"]
        subgraph Selector["Service Selector"]
            CUS["ExtractionService.CONTENT_UNDERSTANDING"]
            DIS["ExtractionService.DOCUMENT_INTELLIGENCE"]
        end
        
        subgraph Clients["Client Layer"]
            CUC["Content Understanding Client<br>• Analyzer API<br>• Multi-modal<br>• Markdown output"]
            DIC["Document Intelligence Client<br>• Layout model<br>• Pre-built models<br>• Markdown output"]
        end
        
        CUS --> CUC
        DIS --> DIC
        
        Formats["📄 Supported Formats:<br>PDF, DOCX (AI extraction)<br>TXT, MD (read directly)"]
    end
    
    style DocProcessor fill:#e3f2fd,stroke:#1565c0
```

#### 3. Multi-Agent Scoring System (`scoring_agent.py`)

Implements the AI-powered evaluation using specialized agents:

```mermaid
flowchart TB
    subgraph ScoringSystem["Scoring Agent System"]
        subgraph Agent1["Criteria Extraction Agent"]
            I1["Input: RFP Document (Markdown)"]
            O1["Output: ExtractedCriteria<br>• rfp_title<br>• rfp_summary<br>• criteria[] with weights<br>• evaluation_guidance<br>• confidence scores<br>• auto re-reasoning"]
            I1 --> O1
        end
        
        subgraph Agent2["Proposal Scoring Agent"]
            I2["Input: Proposal + ExtractedCriteria"]
            O2["Output: ProposalEvaluation<br>• total_score<br>• criterion_scores[]<br>• strengths / weaknesses<br>• recommendation<br>• confidence per criterion<br>• reasoning_iterations"]
            I2 --> O2
        end
        
        Agent1 --> Agent2
        
        subgraph Models["Pydantic Models"]
            M1["ScoringCriterion"]
            M2["ExtractedCriteria"]
            M3["CriterionScore"]
            M4["ProposalEvaluation"]
        end
    end
    
    style ScoringSystem fill:#fce4ec,stroke:#880e4f
```

#### 4. Comparison Agent (`comparison_agent.py`)

Compares multiple vendor evaluations and generates comparative analysis:

```mermaid
flowchart TB
    subgraph CompAgent["Comparison Agent"]
        Input["Input: List[ProposalEvaluation]"]
        
        subgraph Engine["Analysis Engine"]
            E1["1. Rank vendors by total score"]
            E2["2. Compare performance by criterion"]
            E3["3. Identify patterns across vendors"]
            E4["4. Generate recommendations"]
            E1 --> E2 --> E3 --> E4
        end
        
        subgraph Output["Output: ComparisonResult"]
            VR["vendor_rankings: List[VendorRanking]"]
            CC["criterion_comparisons: List[CriterionComparison]"]
            WS["winner_summary"]
            CI["comparison_insights"]
            SR["selection_recommendation"]
            RC["risk_comparison"]
        end
        
        subgraph Reports["Report Generation"]
            R1["📄 generate_word_report()"]
            R2["📊 generate_full_analysis_report()"]
            R3["📋 CSV export"]
            R4["🔧 JSON export"]
        end
        
        Input --> Engine --> Output --> Reports
    end
    
    style CompAgent fill:#e8eaf6,stroke:#283593
```

---

## Session State & Persistence

The application persists all workflow state to Azure Blob Storage as a JSON state file, enabling:

1. **Resume from any step** — If the browser is closed or session state is lost, reopening the same URL (`?session=<id>`) restores the workflow at the last completed step.
2. **Permanent report links** — Generated reports (Word, CSV, JSON) are stored in blob storage with permanent blob paths. Time-limited SAS URLs are generated on-demand for secure downloads.
3. **Session audit trail** — The state file records timestamps, durations, and configuration for each pipeline stage.

### Storage Structure

```
<container: rfp-sessions>/
  <session_id>/
    state.json                          ← Session state (JSON)
    uploads/
      rfp/<filename>                    ← Original uploaded RFP
      proposals/<filename>              ← Original uploaded proposals
    extracted/
      rfp/<filename>.md                 ← Extracted RFP text
      proposals/<filename>.md           ← Extracted proposal text
    reports/
      rfp_full_analysis_report.docx     ← Full analysis Word doc
      vendor_comparison.csv             ← CSV comparison
      evaluation_data.json              ← Full JSON data export
      report_<vendor_name>.docx         ← Per-vendor Word reports
```

### State File Schema (`state.json`)

```json
{
  "version": "1.0",
  "session_id": "abc123def456",
  "created_at": "2024-01-15T10:30:00+00:00",
  "updated_at": "2024-01-15T11:45:00+00:00",
  "current_step": 4,
  "config": {
    "extraction_service": "document_intelligence",
    "reasoning_effort": "high",
    "global_criteria": ""
  },
  "uploads": {
    "rfp": {"name": "rfp.pdf", "size": 52000, "blob_path": "..."},
    "proposals": [{"name": "vendor_a.pdf", "size": 31000, "blob_path": "..."}]
  },
  "extraction": {"completed": true, "duration_seconds": 15.2},
  "criteria": {"completed": true, "criteria_count": 8, "criteria_data": {...}},
  "evaluation": {"completed": true, "results": [...], "comparison": {...}},
  "reports": {
    "full_analysis": {"blob_path": "...", "filename": "...", "generated_at": "..."},
    "csv_comparison": {"blob_path": "...", "filename": "...", "generated_at": "..."},
    "json_data": {"blob_path": "...", "filename": "...", "generated_at": "..."},
    "vendor_reports": [{"vendor_name": "...", "blob_path": "...", "filename": "..."}]
  },
  "step_durations": {"extraction_total": 15.2, "criteria_extraction": 8.1}
}
```

### Download Handler

Reports can be accessed via permanent URLs:

```
/?session=<session_id>&download=full_analysis
/?session=<session_id>&download=csv_comparison
/?session=<session_id>&download=json_data
/?session=<session_id>&download=vendor_report_<vendor_name>
```

Each access generates a fresh time-limited SAS token (60-minute expiry) using either:
- **User Delegation Key** (Managed Identity in production)
- **Account Key** (connection string in local dev)

---

## Multi-Agent System

The evaluation pipeline uses a sequential multi-agent architecture:

```mermaid
flowchart TB
    subgraph Inputs["📥 Inputs"]
        RFP["RFP Document"]
        VP["Vendor Proposals"]
    end
    
    subgraph Agent1["🔍 AGENT 1: Criteria Extraction"]
        A1D["• Analyzes RFP requirements<br>• Identifies evaluation criteria<br>• Assigns weights total = 100%<br>• Provides scoring guidance<br>• Confidence scoring per criterion<br>• Auto re-reasoning on low confidence"]
        A1M["Model: Azure OpenAI GPT-5.2"]
        A1O["Output: ExtractedCriteria"]
    end
    
    EC["📋 Extracted Criteria<br>JSON/Pydantic"]
    
    subgraph Agent2["📊 AGENT 2: Proposal Scoring - Parallel"]
        direction LR
        A2A["Scoring Agent<br>Vendor A<br>• Evaluates proposal<br>• Scores per criterion<br>• Confidence scoring<br>• Re-reasons low-confidence"]
        A2B["Scoring Agent<br>Vendor B<br>• Evaluates proposal<br>• Scores per criterion<br>• Confidence scoring<br>• Re-reasons low-confidence"]
        A2N["Scoring Agent<br>Vendor N<br>• Evaluates proposal<br>• Scores per criterion<br>• Confidence scoring<br>• Re-reasons low-confidence"]
    end
    
    subgraph Agent3["🏆 AGENT 3: Comparison"]
        A3D["• Ranks all vendors by score<br>• Compares criterion performance<br>• Identifies best/worst performers<br>• Generates recommendations<br>• Assesses comparative risks"]
        A3M["Model: Azure OpenAI GPT-5.2"]
        A3O["Output: ComparisonResult"]
    end
    
    subgraph Outputs["📤 Final Reports"]
        FR1["📄 Word documents"]
        FR2["📊 CSV exports"]
        FR3["🔧 JSON data"]
    end
    
    RFP --> Agent1
    VP --> EC
    Agent1 --> EC
    EC --> A2A & A2B & A2N
    A2A & A2B & A2N --> Agent3
    Agent3 --> Outputs
    
    style Agent1 fill:#bbdefb,stroke:#1976d2
    style Agent2 fill:#c8e6c9,stroke:#388e3c
    style Agent3 fill:#fff9c4,stroke:#f9a825
```

### Agent Communication Pattern

```mermaid
flowchart TB
    subgraph Framework["Agent Framework Integration"]
        subgraph Client["AzureOpenAIResponsesClient"]
            C1["• Structured output generation"]
            C2["• Pydantic model integration"]
            C3["• Automatic JSON schema generation"]
            C4["• Response validation"]
        end
        
        subgraph Auth["DefaultAzureCredential"]
            A1["1. Managed Identity (in Azure)"]
            A2["2. Azure CLI (local development)"]
            A3["3. Environment variables"]
        end
        
        Client --> Auth
    end
    
    style Framework fill:#f5f5f5,stroke:#616161
```

---

## Azure Infrastructure

### Resource Topology

```mermaid
flowchart TB
    subgraph Subscription["☁️ Azure Subscription"]
        subgraph RG["📁 Resource Group: rg-{env-name}"]
            subgraph AIFoundry["🧠 Azure AI Foundry Account - AIServices"]
                direction TB
                Capabilities["Capabilities:<br>• OpenAI Language Model API<br>• Form Recognizer<br>• Content Understanding"]
                
                subgraph Models["Model Deployments"]
                    GPT52["gpt-5.2<br>GlobalStd<br>100K TPM"]
                    GPT41["gpt-4.1<br>GlobalStd<br>100K TPM"]
                    GPT41M["gpt-4.1-mini<br>GlobalStd<br>100K TPM"]
                    EMB["text-embedding-3-large<br>GlobalStd<br>300K TPM"]
                end
                
                subgraph Project["AI Foundry Project"]
                    AppInsConn["App Insights Connection<br>Telemetry integration"]
                end
            end
            
            subgraph Monitoring["📊 Monitoring Stack"]
                LAW["Log Analytics<br>Workspace<br>• Container logs<br>• AI service logs<br>• Custom metrics"]
                AI["Application Insights<br>• Performance metrics<br>• Request tracing<br>• Exception tracking<br>• Custom events"]
                Dashboard["Application Insights Dashboard"]
                AI --> LAW
            end
            
            subgraph Container["🐳 Container Platform"]
                ACR["Container Registry<br>• rfp-analyzer image<br>• SKU: Standard"]
                
                subgraph CAE["Container Apps Environment"]
                    CA["rfp-analyzer<br>Container App<br>• Port: 8501<br>• CPU: 2 cores<br>• Memory: 4Gi<br>• Scale: 1-10"]
                end
                
                ACR --> CA
            end
            
            subgraph Storage["💾 Azure Storage"]
                SA["Storage Account<br>• Standard_LRS<br>• StorageV2"]
                BC["Blob Container:<br>rfp-sessions<br>• Uploaded docs<br>• Extracted text"]
                SA --> BC
            end
            
            MI["🔐 User-Assigned Managed Identity<br>• Azure AI Developer<br>• Cognitive Services User<br>• Storage Blob Data Contributor<br>• AcrPull"]
        end
    end
    
    MI -.-> AIFoundry
    MI -.-> ACR
    MI -.-> SA
    CA -.-> AIFoundry
    CA -.-> SA
    
    style Subscription fill:#e3f2fd,stroke:#1565c0
    style AIFoundry fill:#fff3e0,stroke:#ef6c00
    style Monitoring fill:#e8f5e9,stroke:#2e7d32
    style Container fill:#fce4ec,stroke:#c2185b
```

### Infrastructure as Code (Bicep)

```mermaid
flowchart TB
    subgraph Infra["📁 infra/"]
        Main["main.bicep<br>subscription scope"]
        Params["main.parameters.json"]
        Resources["resources.bicep"]
        Abbr["abbreviations.json"]
        
        subgraph Modules["modules/"]
            Fetch["fetch-container-image.bicep"]
        end
        
        subgraph Hooks["hooks/"]
            PostSh["postprovision.sh"]
            PostPs["postprovision.ps1"]
        end
    end
    
    style Infra fill:#f5f5f5,stroke:#424242
```

### Bicep Module Dependencies

```mermaid
flowchart TB
    Main["main.bicep<br>subscription scope"]
    
    Main --> RG["rfpResourceGroup<br>AVM module"]
    
    RG --> Resources["resources.bicep<br>resource group scope"]
    
    Resources --> Monitoring["monitoring<br>AVM pattern"]
    Resources --> Identity["rfpAnalyzerIdentity<br>AVM module"]
    Resources --> Foundry["foundryAccount<br>AVM module"]
    Resources --> Project["foundryProject<br>native resource"]
    Resources --> Registry["containerRegistry<br>AVM module"]
    Resources --> CAEnv["containerAppsEnvironment<br>AVM module"]
    Resources --> FetchImg["rfpAnalyzerFetchLatestImage<br>custom module"]
    Resources --> ContainerApp["rfpAnalyzer<br>AVM module"]
    Resources --> Roles["Role Assignments<br>AVM modules"]
    
    Monitoring --> LAW["Log Analytics Workspace"]
    Monitoring --> AppIns["Application Insights"]
    Monitoring --> Dash["Dashboard"]
    
    Identity --> UAMI["User-Assigned Managed Identity"]
    
    Foundry --> AIS["AIServices Account"]
    Foundry --> Deploy["Model Deployments"]
    
    Project --> AIC["App Insights Connection"]
    
    ContainerApp --> CA["Container App"]
    
    Roles --> R1["Azure AI Developer"]
    Roles --> R2["Cognitive Services User"]
    Roles --> R3["Cognitive Services OpenAI User"]
    Roles --> R4["Monitoring Metrics Publisher"]
    
    Main --> Outputs["Outputs"]
    Outputs --> O1["AZURE_CONTAINER_REGISTRY_ENDPOINT"]
    Outputs --> O2["AZURE_RESOURCE_RFP_ANALYZER_ID"]
    Outputs --> O3["AZURE_OPENAI_ENDPOINT"]
    Outputs --> O4["AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"]
    Outputs --> O5["AZURE_CONTENT_UNDERSTANDING_ENDPOINT"]
    
    style Main fill:#bbdefb,stroke:#1976d2
    style Resources fill:#c8e6c9,stroke:#388e3c
```

---

## Data Flow

### Document Processing Flow

```mermaid
flowchart TB
    Upload["👤 User uploads document(s)"]
    
    subgraph DocProc["Document Processor"]
        V["1. Validate file type<br>PDF, DOCX, TXT, MD"]
        R["2. Read file bytes into memory"]
        S["3. Classify file type<br>AI extraction vs direct read"]
    end
    
    Upload --> DocProc
    
    DocProc --> TextRead & ProtCheck
    
    subgraph TextRead["Direct Read (TXT, MD)"]
        TR1["UTF-8 decode"]
        TR2["Instant — no AI needed"]
    end
    
    subgraph ProtCheck["🔒 Protection Check (PDF, DOCX)"]
        PC1["PDF → pypdf PdfReader.is_encrypted"]
        PC2["DOCX → msoffcrypto OfficeFile.is_encrypted()"]
        PC3{"Protected?"}
        PC1 --> PC3
        PC2 --> PC3
        PC3 -- Yes --> Err["❌ ValueError:<br>Document is protected"]
        PC3 -- No --> OK["✅ Proceed to extraction"]
    end
    
    OK --> CU & DI
    
    subgraph CU["Content Understanding"]
        CU1["POST /contentunderstanding/analyzer"]
        CU2["• Create analyzer"]
        CU3["• Upload document"]
        CU4["• Poll for results"]
        CU5["• Get markdown output"]
    end
    
    subgraph DI["Document Intelligence"]
        DI1["POST /documentModels/prebuilt-layout:analyze"]
        DI2["• Submit for analysis"]
        DI3["• Poll for results"]
        DI4["• Extract markdown"]
    end
    
    CU & DI & TextRead --> Output
    
    subgraph Output["📄 Extracted Markdown"]
        O1["Stored in Azure Blob Storage:"]
        O2["• RFP content → &lt;session_id&gt;/extracted/rfp/"]
        O3["• Proposal contents → &lt;session_id&gt;/extracted/proposals/"]
    end
    
    style DocProc fill:#e3f2fd,stroke:#1565c0
    style ProtCheck fill:#fff3e0,stroke:#ef6c00
    style CU fill:#fff3e0,stroke:#ef6c00
    style DI fill:#e8f5e9,stroke:#2e7d32
```

### Evaluation Pipeline Flow

```mermaid
flowchart TB
    subgraph Session["Azure Blob Storage (Session)"]
        RFP["RFP Markdown<br>&lt;session_id&gt;/extracted/rfp/"]
        P1["Proposal 1 Markdown"]
        PN["Proposal N Markdown"]
    end
    
    RFP --> CEA
    
    subgraph CEA["Step 3: Criteria Extraction Agent"]
        CEA1["Azure OpenAI Call<br>structured output"]
    end
    
    CEA --> EC["ExtractedCriteria<br>Pydantic model"]
    
    EC --> Review["👤 User Reviews Criteria &amp; Weights"]
    Review --> SA1 & SAN
    P1 --> SA1
    PN --> SAN
    
    subgraph Scoring["Step 4: Parallel Scoring"]
        SA1["Scoring Agent<br>Proposal 1<br>Azure OpenAI"]
        SAN["Scoring Agent<br>Proposal N<br>Azure OpenAI"]
    end
    
    SA1 --> EV1["Evaluation<br>Vendor 1"]
    SAN --> EVN["Evaluation<br>Vendor N"]
    
    EV1 & EVN --> CA
    
    subgraph CA["Comparison Agent"]
        CA1["• Rank vendors"]
        CA2["• Compare criteria"]
        CA3["• Recommend winner"]
    end
    
    CA --> CR
    
    subgraph CR["ComparisonResult"]
        CR1["📄 Word documents"]
        CR2["📊 CSV comparison"]
        CR3["🔧 JSON data"]
    end
    
    style Session fill:#f3e5f5,stroke:#7b1fa2
    style Scoring fill:#e8f5e9,stroke:#388e3c
    style CA fill:#fff9c4,stroke:#f9a825
```

### Confidence Scoring & Auto Re-Reasoning

Each agent produces confidence scores (0.0–1.0) for its outputs. When confidence falls below the configurable `CONFIDENCE_THRESHOLD` (default 0.7), the system automatically triggers a deeper analysis pass.

```mermaid
flowchart TB
    subgraph Initial["Initial Extraction / Scoring"]
        I1["LLM Call → Results with confidence scores"]
    end

    I1 --> Check{"Overall confidence<br>≥ threshold?"}

    Check -- Yes --> Done["✅ Accept results"]
    Check -- No --> ReReason

    subgraph ReReason["Re-Reasoning Pass"]
        R1["Identify low-confidence items"]
        R2["Follow-up prompt:<br>'Re-examine with deeper analysis'"]
        R3["Increase reasoning effort to 'high'"]
        R4["Merge: keep higher-confidence version"]
    end

    ReReason --> Final["📊 Final Results<br>(improved confidence)"]

    style Initial fill:#e3f2fd,stroke:#1565c0
    style ReReason fill:#fff3e0,stroke:#ef6c00
```

### Large Document Chunking Process

When a document exceeds the model's context window (configurable via `MAX_CONTEXT_TOKENS` env var, default 1,050,000 tokens), the system automatically splits it into manageable chunks and processes them using a map-reduce pattern.

#### Scoring Agent — Map-Reduce Chunked Processing

```mermaid
flowchart TB
    Doc["📄 Input Document<br>(RFP or Proposal)"]

    Doc --> EstTokens["🔢 Estimate Token Count<br>(chars ÷ 3.5)"]
    EstTokens --> Check{"Tokens ≤<br>context budget?"}

    Check -- Yes --> Single["✅ Single-Call Processing<br>Send full document to LLM"]

    Check -- No --> Split["✂️ Split by Token Budget"]

    subgraph Splitting["Content Splitting Strategy"]
        direction TB
        Split --> H["1. Split by markdown headings"]
        H --> P["2. Oversized sections → split by paragraphs"]
        P --> T["3. Oversized paragraphs → truncate at boundary"]
        T --> OV["4. Add overlap tokens between chunks<br>for context continuity"]
    end

    subgraph MapPhase["Map Phase — Process Each Chunk"]
        direction LR
        C1["📦 Chunk 1<br>LLM Call"]
        C2["📦 Chunk 2<br>LLM Call"]
        CN["📦 Chunk N<br>LLM Call"]
    end

    Splitting --> MapPhase

    subgraph ReducePhase["Reduce Phase — Merge Results"]
        direction TB
        Best["For each criterion:<br>keep highest raw_score<br>across all chunks"]
        Best --> Recalc["Recalculate<br>weighted scores &amp; totals"]
        Recalc --> Dedup["Deduplicate strengths,<br>weaknesses, recommendations"]
        Dedup --> Grade["Assign final grade<br>(A/B/C/D/F)"]
    end

    MapPhase --> ReducePhase
    ReducePhase --> Final["📊 Final Merged Evaluation"]
    Single --> Final

    style Splitting fill:#e3f2fd,stroke:#1565c0
    style MapPhase fill:#fff3e0,stroke:#ef6c00
    style ReducePhase fill:#e8f5e9,stroke:#2e7d32
```

#### Criteria Extraction — Chunked Merge

When the RFP document itself is too large for a single LLM call, criteria extraction also uses chunking:

```mermaid
flowchart TB
    RFP["📄 Large RFP Document"]
    RFP --> Split["✂️ Split into N chunks<br>(by heading / paragraph boundaries)"]

    subgraph Extract["Extract Criteria per Chunk"]
        direction LR
        E1["Chunk 1 → Criteria[]"]
        E2["Chunk 2 → Criteria[]"]
        EN["Chunk N → Criteria[]"]
    end

    Split --> Extract

    subgraph Merge["Merge &amp; Normalize"]
        direction TB
        DD["Deduplicate criteria<br>(by name, case-insensitive)"]
        DD --> ReID["Re-assign criterion IDs<br>(C-1, C-2, …)"]
        ReID --> Norm["Normalize weights<br>to sum = 100%"]
    end

    Extract --> Merge
    Merge --> Out["📋 ExtractedCriteria<br>(unified, deduplicated)"]

    style Extract fill:#fff3e0,stroke:#ef6c00
    style Merge fill:#e8f5e9,stroke:#2e7d32
```

---

## Resilience Architecture

### Document Protection Detection

Before any document is sent to an extraction service, the system checks for encryption or IRM protection. This avoids wasting API calls on documents that cannot be processed.

```mermaid
flowchart TB
    Input["📄 Uploaded File"]
    Input --> Ext{"File extension?"}

    Ext -- .pdf --> PDF["pypdf PdfReader(bytes)"]
    PDF --> PEnc{"is_encrypted?"}
    PEnc -- Yes --> Reject["❌ ValueError:<br>'Document is protected (encrypted/IRM).<br>Please remove protection and re-upload.'"]
    PEnc -- No --> Pass["✅ Proceed"]

    Ext -- .docx --> DOCX["msoffcrypto OfficeFile(bytes)"]
    DOCX --> DEnc{"is_encrypted()?"}
    DEnc -- Yes --> Reject
    DEnc -- No --> Pass

    Ext -- .txt / .md --> Pass

    style Reject fill:#ffcdd2,stroke:#c62828
    style Pass fill:#c8e6c9,stroke:#2e7d32
```

### Retry & Refusal Detection

All OpenAI agent calls are wrapped with exponential backoff retry logic. Additionally, AI refusal responses (e.g. *"I'm sorry, but I cannot assist"*) are detected and automatically retried.

```mermaid
flowchart TB
    Call["Agent.run() call"]
    Call --> Response{"Response OK?"}

    Response -- Success --> Parse["Parse structured output"]
    Parse --> Refusal{"Refusal detected?<br>(7 phrase patterns)"}
    Refusal -- No --> Accept["✅ Accept result"]
    Refusal -- Yes --> RetryR["🔄 Retry (new attempt)"]

    Response -- Error / Empty --> RetryE["🔄 Retry with<br>exponential backoff"]

    RetryR --> Call
    RetryE --> Call

    style Accept fill:#c8e6c9,stroke:#2e7d32
    style RetryR fill:#fff3e0,stroke:#ef6c00
    style RetryE fill:#fff3e0,stroke:#ef6c00
```

---

## Security Architecture

### Authentication Flow

```mermaid
flowchart TB
    subgraph DAC["DefaultAzureCredential"]
        direction TB
        Chain["Credential Chain (tried in order):"]
        
        C1["1. EnvironmentCredential<br>AZURE_CLIENT_ID, AZURE_TENANT_ID,<br>AZURE_CLIENT_SECRET"]
        C2["2. ManagedIdentityCredential ◀️ Used in Azure<br>User-Assigned Managed Identity<br>AZURE_CLIENT_ID env var"]
        C3["3. AzureCliCredential ◀️ Used in local dev<br>az login session"]
        C4["4. AzurePowerShellCredential"]
        C5["5. VisualStudioCodeCredential"]
        
        Chain --> C1 --> C2 --> C3 --> C4 --> C5
    end
    
    DAC --> Token
    
    subgraph Token["Token Acquisition"]
        T1["Scope: https://cognitiveservices.azure.com/.default"]
        T2["Token used for:<br>• Azure OpenAI API calls<br>• Content Understanding API calls<br>• Document Intelligence API calls"]
    end
    
    style DAC fill:#e3f2fd,stroke:#1565c0
    style Token fill:#e8f5e9,stroke:#2e7d32
```

### RBAC Configuration

```mermaid
flowchart TB
    MI["🔐 User-Assigned Managed Identity<br>rfp-analyzer-identity"]
    
    MI --> R1 & R2 & R3 & R4 & R5
    
    subgraph Roles["Role Assignments"]
        R1["Azure AI Developer<br><br>Scope: Resource Group<br><br>Allows:<br>• Create/manage AI resources<br>• Deploy models"]
        R2["Cognitive Services User<br><br>Scope: Resource Group<br><br>Allows:<br>• Use AI services<br>• Make API calls"]
        R3["Cognitive Services OpenAI User<br><br>Scope: Resource Group<br><br>Allows:<br>• Keyless OpenAI API access<br>• Responses API calls"]
        R4["Monitoring Metrics Publisher<br><br>Scope: Resource Group<br><br>Allows:<br>• Publish telemetry metrics<br>• App Insights data ingestion"]
        R5["AcrPull<br><br>Scope: Container Registry<br><br>Allows:<br>• Pull images"]
    end
    
    subgraph Security["🛡️ Security Features"]
        S1["• No stored credentials in application code"]
        S2["• Keys rotation handled by Azure"]
        S3["• Audit logging via Azure Activity Log"]
        S4["• Network isolation available (private endpoints)"]
        S5["• disableLocalAuth: true on AI Services account"]
    end
    
    style MI fill:#fff3e0,stroke:#ef6c00
    style Roles fill:#e3f2fd,stroke:#1565c0
    style Security fill:#e8f5e9,stroke:#2e7d32
```

---

## Deployment Architecture

### Azure Developer CLI (azd) Workflow

```mermaid
flowchart TB
    subgraph AZD["azd up Workflow"]
        S1["Step 1: Initialize"]
        S1D["azd init<br>• Creates .azure/ directory<br>• Selects subscription and location<br>• Creates environment configuration"]
        
        S2["Step 2: Provision Infrastructure"]
        S2D["azd provision<br>• Deploys main.bicep at subscription scope<br>• Creates resource group<br>• Provisions all Azure resources<br>• Configures role assignments<br>• Runs postprovision hooks"]
        
        S3["Step 3: Build & Deploy Application"]
        S3D["azd deploy<br>• Builds Docker image remote build<br>• Pushes to Azure Container Registry<br>• Updates Container App with new image"]
        
        S4["Step 4: Output"]
        S4D["Environment variables and URLs<br>• Application URL<br>• Azure OpenAI endpoint<br>• Content Understanding endpoint<br>• Document Intelligence endpoint"]
        
        S1 --> S1D --> S2 --> S2D --> S3 --> S3D --> S4 --> S4D
    end
    
    style AZD fill:#e3f2fd,stroke:#1565c0
```

### Container Deployment

```mermaid
flowchart TB
    Source["📁 Source Code<br>app/"]
    
    subgraph Docker["Dockerfile"]
        D1["FROM python:3.13-slim"]
        D2["• Install UV package manager"]
        D3["• Copy pyproject.toml, uv.lock"]
        D4["• Install dependencies"]
        D5["• Copy application code"]
        D6["• EXPOSE 8501"]
        D7["• CMD: streamlit run main.py"]
    end
    
    subgraph ACR["Azure Container Registry"]
        ACR1["• Remote build (Cloud Build)"]
        ACR2["• Image: {acr}.azurecr.io/rfp-analyzer:latest"]
    end
    
    subgraph ACA["Azure Container Apps"]
        ACA1["Configuration:"]
        ACA2["• Ingress: External, port 8501"]
        ACA3["• Scale: 1-10 replicas"]
        ACA4["• Resources: 2 CPU, 4GB memory"]
        ACA5["• Identity: User-assigned managed identity"]
        
        ACA6["Environment Variables:"]
        ACA7["• AZURE_OPENAI_ENDPOINT"]
        ACA8["• AZURE_OPENAI_DEPLOYMENT_NAME"]
        ACA9["• AZURE_CONTENT_UNDERSTANDING_ENDPOINT"]
        ACA10["• AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"]
        ACA11["• AZURE_CLIENT_ID (managed identity)"]
        ACA12["• APPLICATIONINSIGHTS_CONNECTION_STRING"]
        ACA13["• OTEL_LOGGING_ENABLED"]
        ACA14["• OTEL_TRACING_ENABLED"]
    end
    
    Source --> Docker --> ACR --> ACA
    
    style Docker fill:#e3f2fd,stroke:#1565c0
    style ACR fill:#fff3e0,stroke:#ef6c00
    style ACA fill:#e8f5e9,stroke:#2e7d32
```

---

## Monitoring & Observability

```mermaid
flowchart TB
    subgraph AppLayer["Application Layer"]
        L["📝 Logging<br>Python"]
        M["📊 Metrics<br>Custom"]
        T["🔍 Tracing<br>OpenTelemetry"]
    end
    
    AppLayer --> SDK
    
    subgraph SDK["Application Insights SDK"]
        SDK1["azure-monitor-opentelemetry"]
        SDK2["Automatic instrumentation for HTTP, Azure SDK"]
        SDK3["Custom spans for agent operations"]
    end
    
    SDK --> AI
    
    subgraph AI["Application Insights"]
        AI1["• Live Metrics Stream"]
        AI2["• Transaction Search"]
        AI3["• Application Map"]
        AI4["• Failures and Performance"]
    end
    
    AI --> LAW
    
    subgraph LAW["Log Analytics Workspace"]
        LAW1["Tables:"]
        LAW2["• AppTraces - Application logs"]
        LAW3["• AppRequests - HTTP requests"]
        LAW4["• AppDependencies - External calls"]
        LAW5["• AppExceptions - Errors"]
        LAW6["• ContainerAppConsoleLogs - Container logs"]
        LAW7["• ContainerAppSystemLogs - Platform logs"]
    end
    
    style AppLayer fill:#f3e5f5,stroke:#7b1fa2
    style SDK fill:#e3f2fd,stroke:#1565c0
    style AI fill:#fff3e0,stroke:#ef6c00
    style LAW fill:#e8f5e9,stroke:#2e7d32
```

---

## Class Diagrams

### Pydantic Models

```mermaid
classDiagram
    class ScoringCriterion {
        +str criterion_id
        +str name
        +str description
        +str category
        +float weight
        +int max_score
        +str evaluation_guidance
        +float confidence
    }
    
    class ExtractedCriteria {
        +str rfp_title
        +str rfp_summary
        +float total_weight
        +List~ScoringCriterion~ criteria
        +str extraction_notes
        +float overall_confidence
    }
    
    class CriterionScore {
        +str criterion_id
        +str criterion_name
        +float weight
        +float raw_score
        +float weighted_score
        +str evidence
        +str justification
        +List~str~ strengths
        +List~str~ gaps
        +float confidence
        +int reasoning_iterations
    }
    
    class ProposalEvaluation {
        +str rfp_title
        +str supplier_name
        +str supplier_site
        +str response_id
        +str evaluation_date
        +bool is_qualified_proposal
        +str disqualification_reason
        +float total_score
        +float score_percentage
        +str grade
        +str recommendation
        +List~CriterionScore~ criterion_scores
        +str executive_summary
        +List~str~ overall_strengths
        +List~str~ overall_weaknesses
        +List~str~ recommendations
        +str risk_assessment
        +float overall_confidence
    }
    
    class VendorRanking {
        +int rank
        +str vendor_name
        +float total_score
        +str grade
        +List~str~ key_strengths
        +List~str~ key_concerns
        +str recommendation
    }
    
    class ComparisonResult {
        +str rfp_title
        +str comparison_date
        +int total_vendors
        +List~VendorRanking~ vendor_rankings
        +List~CriterionComparison~ criterion_comparisons
        +str winner_summary
        +List~str~ comparison_insights
        +str selection_recommendation
        +str risk_comparison
    }
    
    ExtractedCriteria "1" *-- "*" ScoringCriterion
    ProposalEvaluation "1" *-- "*" CriterionScore
    ComparisonResult "1" *-- "*" VendorRanking
```

### Service Classes

```mermaid
classDiagram
    class DocumentProcessor {
        +ExtractionService service
        +AzureContentUnderstandingClient cu_client
        +AzureDocumentIntelligenceClient di_client
        +__init__(service: ExtractionService)
        +process_document(file_bytes, filename) str
        +requires_ai_extraction(filename)$ bool
        +TEXT_EXTENSIONS$ tuple
        +AI_EXTRACTED_EXTENSIONS$ tuple
    }
    
    class CriteriaExtractionAgent {
        +AzureOpenAIResponsesClient client
        +str model
        +extract_criteria(rfp_content, scoring_guide) ExtractedCriteria
    }
    
    class ProposalScoringAgent {
        +AzureOpenAIResponsesClient client
        +str model
        +score_proposal(proposal, criteria) ProposalEvaluation
    }
    
    class ComparisonAgent {
        +AzureOpenAIResponsesClient client
        +str model
        +compare_vendors(evaluations) ComparisonResult
        +generate_word_report(evaluation) bytes
        +generate_full_analysis_report(comparison) bytes
    }
    
    class ExtractionService {
        <<enumeration>>
        CONTENT_UNDERSTANDING
        DOCUMENT_INTELLIGENCE
    }
    
    DocumentProcessor --> ExtractionService
    CriteriaExtractionAgent --> ExtractedCriteria
    ProposalScoringAgent --> ProposalEvaluation
    ComparisonAgent --> ComparisonResult
```

---

## Sequence Diagrams

### Full Evaluation Flow

```mermaid
sequenceDiagram
    actor User
    participant UI as Streamlit UI
    participant DP as Document Processor
    participant CU as Content Understanding
    participant CEA as Criteria Agent
    participant PSA as Scoring Agent
    participant CA as Comparison Agent
    participant AOAI as Azure OpenAI
    
    User->>UI: Upload RFP & Proposals
    UI->>UI: Generate session ID (in URL)
    UI->>UI: Upload files to Azure Blob Storage
    
    User->>UI: Click "Extract"
    UI->>UI: Download files from Blob
    UI->>DP: Process documents
    DP->>CU: Extract content
    CU-->>DP: Markdown content
    DP-->>UI: Store extracted content in Blob
    
    User->>UI: Click "Extract Criteria"
    UI->>CEA: Extract criteria from RFP
    CEA->>AOAI: Structured output request
    AOAI-->>CEA: ExtractedCriteria
    CEA-->>UI: Display criteria for review
    
    User->>UI: Review criteria & Click "Score"
    loop For each proposal
        UI->>PSA: Score proposal
        PSA->>AOAI: Structured output request
        AOAI-->>PSA: ProposalEvaluation
        PSA-->>UI: Evaluation complete
    end
    
    UI->>CA: Compare all vendors
    CA->>AOAI: Structured output request
    AOAI-->>CA: ComparisonResult
    CA-->>UI: Comparison complete
    
    UI-->>User: Display results & export options
```

---

## Additional Resources

- [Azure AI Foundry Documentation](https://learn.microsoft.com/azure/ai-studio/)
- [Azure Container Apps Documentation](https://learn.microsoft.com/azure/container-apps/)
- [Azure Developer CLI Documentation](https://learn.microsoft.com/azure/developer/azure-developer-cli/)
- [Bicep Documentation](https://learn.microsoft.com/azure/azure-resource-manager/bicep/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
- [Mermaid Documentation](https://mermaid.js.org/)
