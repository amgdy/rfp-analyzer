"""
RFP Analyzer - Streamlit Application

A comprehensive workflow for analyzing RFPs and scoring vendor proposals:
1. Upload RFP file and Vendor proposals (multiple files)
2. Configure extraction service and evaluation criteria
3. AI-powered evaluation and multi-vendor comparison
"""

import os
import streamlit as st
from pathlib import Path
import asyncio
import time
import logging
import io
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

# Initialize Azure Monitor / Application Insights telemetry
# Must be done before other imports to instrument all libraries
from azure.monitor.opentelemetry import configure_azure_monitor
from agent_framework.observability import create_resource, enable_instrumentation


from opentelemetry import trace

os.environ["AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED"] = "true" # False by default


# Configure Application Insights if connection string is available
# app_insights_conn_str = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
# if app_insights_conn_str:
#     configure_azure_monitor(
#         connection_string=app_insights_conn_str,
#         enable_live_metrics=True
#     )

# # # optional if you do not have ENABLE_INSTRUMENTATION in env vars
# enable_instrumentation()    
from services.document_processor import DocumentProcessor, ExtractionService
from services.scoring_agent_v2 import ScoringAgentV2
from services.comparison_agent import ComparisonAgent, generate_word_report

# Optional PDF support
try:
    from weasyprint import HTML, CSS
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d | %(levelname)s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Get tracer for custom spans
tracer = trace.get_tracer(__name__)


def format_duration(seconds: float) -> str:
    """Format duration in minutes and seconds.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string like "1m 30s" or "45s" for durations under a minute
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    remaining_seconds = seconds % 60
    return f"{minutes}m {remaining_seconds:.1f}s"


def generate_pdf_from_markdown(markdown_content: str, title: str = "RFP Score Report") -> bytes | None:
    """Generate PDF from markdown content.
    
    Args:
        markdown_content: The markdown content to convert
        title: Title for the PDF document
        
    Returns:
        PDF bytes if successful, None if PDF generation is not available
    """
    if not PDF_AVAILABLE or not MARKDOWN_AVAILABLE:
        return None
    
    try:
        # Convert markdown to HTML
        html_content = markdown.markdown(
            markdown_content,
            extensions=['tables', 'fenced_code', 'toc']
        )
        
        # CSS styling for the PDF
        css = CSS(string='''
            @page {
                size: A4;
                margin: 2cm;
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                font-size: 11pt;
                line-height: 1.6;
                color: #333;
            }
            h1 {
                color: #1a1a1a;
                border-bottom: 2px solid #0066cc;
                padding-bottom: 10px;
                font-size: 24pt;
            }
            h2 {
                color: #0066cc;
                margin-top: 20px;
                font-size: 18pt;
            }
            h3 {
                color: #333;
                font-size: 14pt;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 15px 0;
                font-size: 10pt;
            }
            th, td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }
            th {
                background-color: #0066cc;
                color: white;
            }
            tr:nth-child(even) {
                background-color: #f9f9f9;
            }
            code {
                background-color: #f4f4f4;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: "Courier New", monospace;
                font-size: 10pt;
            }
            ul, ol {
                margin-left: 20px;
            }
            li {
                margin-bottom: 5px;
            }
            .score-excellent { color: #28a745; }
            .score-good { color: #17a2b8; }
            .score-average { color: #ffc107; }
            .score-poor { color: #dc3545; }
        ''')
        
        # Wrap HTML with proper structure
        full_html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{title}</title>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        '''
        
        # Generate PDF
        pdf_buffer = io.BytesIO()
        HTML(string=full_html).write_pdf(pdf_buffer, stylesheets=[css])
        pdf_buffer.seek(0)
        return pdf_buffer.getvalue()
        
    except Exception as e:
        logger.error(f"Failed to generate PDF: {e}")
        return None


# Page configuration
st.set_page_config(
    page_title="RFP Analyzer",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if "step" not in st.session_state:
    st.session_state.step = 1
if "rfp_file" not in st.session_state:
    st.session_state.rfp_file = None
if "proposal_files" not in st.session_state:
    st.session_state.proposal_files = []  # Changed to list for multiple proposals
if "rfp_content" not in st.session_state:
    st.session_state.rfp_content = None
if "proposal_contents" not in st.session_state:
    st.session_state.proposal_contents = {}  # Dict mapping filename to content
if "evaluation_results" not in st.session_state:
    st.session_state.evaluation_results = []  # List of evaluation results
if "comparison_results" not in st.session_state:
    st.session_state.comparison_results = None
if "step_durations" not in st.session_state:
    st.session_state.step_durations = {}
if "extraction_service" not in st.session_state:
    st.session_state.extraction_service = ExtractionService.CONTENT_UNDERSTANDING
if "evaluation_mode" not in st.session_state:
    st.session_state.evaluation_mode = "individual"  # "individual" or "combined"
if "global_criteria" not in st.session_state:
    st.session_state.global_criteria = ""
if "reasoning_effort" not in st.session_state:
    st.session_state.reasoning_effort = "high"


# Animation CSS for step indicators
STEP_ANIMATION_CSS = """
<style>
@keyframes pulse {
    0% { opacity: 1; }
    50% { opacity: 0.4; }
    100% { opacity: 1; }
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

.step-processing {
    animation: pulse 1.5s ease-in-out infinite;
    background: linear-gradient(90deg, #1f77b4, #2ca02c, #1f77b4);
    background-size: 200% 100%;
    animation: pulse 1.5s ease-in-out infinite, gradient 2s ease infinite;
    padding: 10px;
    border-radius: 8px;
    margin: 5px 0;
}

@keyframes gradient {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

.spinner {
    display: inline-block;
    width: 20px;
    height: 20px;
    border: 3px solid rgba(255,255,255,.3);
    border-radius: 50%;
    border-top-color: #fff;
    animation: spin 1s ease-in-out infinite;
    margin-right: 10px;
}

.processing-container {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 20px;
    border-radius: 10px;
    color: white;
    margin: 10px 0;
}

.duration-badge {
    background: rgba(0,0,0,0.2);
    padding: 4px 12px;
    border-radius: 15px;
    font-size: 14px;
    margin-left: 10px;
}
</style>
"""


def get_scoring_guide() -> str:
    """Load the scoring guide from file."""
    guide_path = Path(__file__).parent / "scoring_guide.md"
    if guide_path.exists():
        return guide_path.read_text(encoding="utf-8")
    return ""


async def process_document(
    file_bytes: bytes, 
    filename: str, 
    extraction_service: ExtractionService = ExtractionService.CONTENT_UNDERSTANDING
) -> tuple[str, float]:
    """Process uploaded document using the configured extraction service.
    
    Args:
        file_bytes: Document content as bytes
        filename: Original filename
        extraction_service: Which service to use for extraction
    
    Returns:
        Tuple of (content, duration_seconds)
    """
    with tracer.start_as_current_span("process_document") as span:
        span.set_attribute("document.filename", filename)
        span.set_attribute("document.size_bytes", len(file_bytes))
        span.set_attribute("document.extraction_service", extraction_service.value)
        
        start_time = time.time()
        logger.info("Starting document processing: %s using %s", filename, extraction_service.value)
        
        processor = DocumentProcessor(service=extraction_service)
        content = await processor.extract_content(file_bytes, filename)
        
        duration = time.time() - start_time
        span.set_attribute("document.content_length", len(content))
        span.set_attribute("document.duration_seconds", duration)
        logger.info("Document processed: %s (%.2fs, %d chars)", filename, duration, len(content))
        
        return content, duration


async def evaluate_proposal(
    rfp_content: str, 
    proposal_content: str, 
    global_criteria: str = "",
    reasoning_effort: str = "high",
    progress_callback: callable = None
) -> tuple[dict, float]:
    """Evaluate the vendor proposal against the RFP using AI agent.
    
    Args:
        rfp_content: The RFP content
        proposal_content: The proposal content
        global_criteria: Optional user-provided global evaluation criteria
        reasoning_effort: Reasoning effort level ("low", "medium", "high")
        progress_callback: Optional callback for progress updates
    
    Returns:
        Tuple of (results, duration_seconds)
    """
    with tracer.start_as_current_span("evaluate_proposal") as span:
        span.set_attribute("evaluation.reasoning_effort", reasoning_effort)
        span.set_attribute("evaluation.rfp_content_length", len(rfp_content))
        span.set_attribute("evaluation.proposal_content_length", len(proposal_content))
        
        start_time = time.time()
        logger.info("Starting proposal evaluation (effort: %s)...", reasoning_effort)
        
        # Always use V2 (multi-agent) for evaluation
        agent = ScoringAgentV2()
        
        # Combine RFP content with global criteria if provided
        if global_criteria:
            enhanced_rfp = f"{rfp_content}\n\n## Additional Evaluation Criteria (User Specified)\n\n{global_criteria}"
        else:
            enhanced_rfp = rfp_content
        
        results = await agent.evaluate(
            enhanced_rfp, 
            proposal_content, 
            reasoning_effort=reasoning_effort,
            progress_callback=progress_callback
        )
        
        duration = time.time() - start_time
        
        # Add result attributes to span
        if isinstance(results, dict) and "total_score" in results:
            span.set_attribute("evaluation.total_score", results["total_score"])
        span.set_attribute("evaluation.duration_seconds", duration)
        
        logger.info("Evaluation completed in %.2fs", duration)
        
        return results, duration


def render_sidebar():
    """Render the sidebar with configuration and navigation."""
    with st.sidebar:
        st.title("📄 RFP Analyzer")
        st.markdown("---")
        
        # Extraction Service Selection
        st.subheader("🔧 Document Extraction")
        
        service_options = {
            ExtractionService.CONTENT_UNDERSTANDING: "Azure Content Understanding",
            ExtractionService.DOCUMENT_INTELLIGENCE: "Azure Document Intelligence"
        }
        
        service = st.radio(
            "Extraction service:",
            options=list(service_options.keys()),
            index=0 if st.session_state.extraction_service == ExtractionService.CONTENT_UNDERSTANDING else 1,
            format_func=lambda x: service_options[x],
            help="Choose the Azure service for document text extraction."
        )
        if service != st.session_state.extraction_service:
            st.session_state.extraction_service = service
            # Reset content when service changes
            st.session_state.rfp_content = None
            st.session_state.proposal_contents = {}
            st.rerun()
        
        st.markdown("")
        
        # Evaluation Mode Selection
        st.subheader("📊 Evaluation Mode")
        
        mode_options = {
            "individual": "Score Each Individually",
            "combined": "Score All Together"
        }
        
        mode = st.radio(
            "Evaluation approach:",
            options=["individual", "combined"],
            index=0 if st.session_state.evaluation_mode == "individual" else 1,
            format_func=lambda x: mode_options[x],
            help="Individual: Each proposal scored separately. Combined: All proposals evaluated together (may require chunking for large documents)."
        )
        if mode != st.session_state.evaluation_mode:
            st.session_state.evaluation_mode = mode
            st.session_state.evaluation_results = []
            st.session_state.comparison_results = None
            st.rerun()
        
        st.markdown("")
        
        # Analysis Depth Selection
        st.subheader("🧠 Analysis Depth")
        depth_options = {
            "low": "Standard (~5 mins)",
            "medium": "Thorough (~10 mins)",
            "high": "Comprehensive (~15 mins)"
        }
        effort = st.radio(
            "Analysis depth:",
            options=["low", "medium", "high"],
            index=["low", "medium", "high"].index(st.session_state.reasoning_effort),
            format_func=lambda x: depth_options[x],
            help="Higher depth = more detailed analysis but longer processing time."
        )
        if effort != st.session_state.reasoning_effort:
            st.session_state.reasoning_effort = effort
            st.session_state.evaluation_results = []
            st.session_state.comparison_results = None
            st.rerun()
        
        st.markdown("---")
        
        # Step indicators
        st.subheader("📍 Progress")
        steps = [
            ("1️⃣", "Upload Documents", st.session_state.step >= 1),
            ("2️⃣", "Configure & Extract", st.session_state.step >= 2),
            ("3️⃣", "Evaluate & Compare", st.session_state.step >= 3),
        ]
        
        for icon, label, active in steps:
            if active:
                st.success(f"{icon} {label}")
            else:
                st.info(f"{icon} {label}")
        
        st.markdown("---")
        
        # Reset button
        if st.button("🔄 Start Over", use_container_width=True):
            st.session_state.step = 1
            st.session_state.rfp_file = None
            st.session_state.proposal_files = []
            st.session_state.rfp_content = None
            st.session_state.proposal_contents = {}
            st.session_state.evaluation_results = []
            st.session_state.comparison_results = None
            st.session_state.global_criteria = ""
            st.session_state.extraction_service = ExtractionService.CONTENT_UNDERSTANDING
            st.session_state.evaluation_mode = "individual"
            st.session_state.reasoning_effort = "high"
            st.rerun()
        
        st.markdown("---")
        st.caption("Powered by Azure AI Services & Microsoft Agent Framework")


def render_step1():
    """Step 1: Upload RFP and Vendor Proposals."""
    st.header("Step 1: Upload Documents")
    st.markdown("Upload the RFP document and vendor proposal files to begin the analysis.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📄 RFP Document")
        st.markdown("Upload a single RFP file")
        
        rfp_file = st.file_uploader(
            "Choose RFP file",
            type=["pdf", "docx", "doc", "txt", "md"],
            key="rfp_uploader",
            help="Supported formats: PDF, Word documents, Text files, Markdown"
        )
        
        if rfp_file is not None:
            st.info(f"📎 **{rfp_file.name}** ({rfp_file.size / 1024:.1f} KB)")
            st.session_state.rfp_file = {
                "bytes": rfp_file.getvalue(),
                "name": rfp_file.name
            }
        
        if st.session_state.rfp_file:
            st.success(f"✅ RFP ready: {st.session_state.rfp_file['name']}")
    
    with col2:
        st.subheader("📝 Vendor Proposals")
        st.markdown("Upload one or more vendor proposal files")
        
        proposal_files = st.file_uploader(
            "Choose Vendor Proposal files",
            type=["pdf", "docx", "doc", "txt", "md"],
            key="proposals_uploader",
            accept_multiple_files=True,
            help="Supported formats: PDF, Word documents, Text files, Markdown"
        )
        
        if proposal_files:
            st.info(f"📎 {len(proposal_files)} file(s) selected")
            for f in proposal_files:
                st.caption(f"• {f.name} ({f.size / 1024:.1f} KB)")
            
            st.session_state.proposal_files = [
                {"bytes": f.getvalue(), "name": f.name}
                for f in proposal_files
            ]
        
        if st.session_state.proposal_files:
            st.success(f"✅ {len(st.session_state.proposal_files)} proposal(s) ready")
    
    st.markdown("---")
    
    # Global Evaluation Criteria
    st.subheader("📋 Global Evaluation Criteria (Optional)")
    st.markdown("Add additional evaluation criteria that will be used alongside criteria extracted from the RFP.")
    
    global_criteria = st.text_area(
        "Enter additional evaluation criteria:",
        value=st.session_state.global_criteria,
        height=150,
        placeholder="Example:\n- Cost effectiveness: 20%\n- Sustainability practices: 15%\n- Local presence: 10%",
        help="These criteria will be added to the automatically extracted criteria from the RFP."
    )
    st.session_state.global_criteria = global_criteria
    
    st.markdown("---")
    
    # Proceed button
    can_proceed = st.session_state.rfp_file is not None and len(st.session_state.proposal_files) > 0
    
    if can_proceed:
        if st.button("Continue to Step 2: Extract Content →", type="primary", use_container_width=True):
            st.session_state.step = 2
            st.rerun()
    else:
        st.warning("⚠️ Please upload an RFP file and at least one vendor proposal to continue.")


def render_step2():
    """Step 2: Extract Content from Documents."""
    st.header("Step 2: Extract & Configure")
    st.markdown("Extract content from uploaded documents and configure evaluation settings.")
    
    # Show uploaded files summary
    col1, col2 = st.columns(2)
    with col1:
        if st.session_state.rfp_file:
            st.info(f"📄 RFP: {st.session_state.rfp_file['name']}")
    with col2:
        if st.session_state.proposal_files:
            st.info(f"📝 Proposals: {len(st.session_state.proposal_files)} file(s)")
    
    # Show configuration summary
    st.markdown("---")
    st.subheader("⚙️ Current Configuration")
    
    config_col1, config_col2, config_col3 = st.columns(3)
    with config_col1:
        service_name = "Content Understanding" if st.session_state.extraction_service == ExtractionService.CONTENT_UNDERSTANDING else "Document Intelligence"
        st.metric("Extraction Service", service_name)
    with config_col2:
        mode_name = "Individual" if st.session_state.evaluation_mode == "individual" else "Combined"
        st.metric("Evaluation Mode", mode_name)
    with config_col3:
        st.metric("Analysis Depth", st.session_state.reasoning_effort.title())
    
    # Global criteria preview
    if st.session_state.global_criteria:
        with st.expander("📋 Global Evaluation Criteria", expanded=False):
            st.markdown(st.session_state.global_criteria)
    
    st.markdown("---")
    
    # Check if content has been extracted
    if st.session_state.rfp_content and st.session_state.proposal_contents:
        st.success("✅ All documents have been processed!")
        
        # Show extracted content previews
        with st.expander("📄 RFP Content Preview", expanded=False):
            st.markdown(st.session_state.rfp_content[:2000] + "..." if len(st.session_state.rfp_content) > 2000 else st.session_state.rfp_content)
        
        with st.expander("📝 Proposal Contents Preview", expanded=False):
            for filename, content in st.session_state.proposal_contents.items():
                st.markdown(f"### {filename}")
                st.markdown(content[:1000] + "..." if len(content) > 1000 else content)
                st.markdown("---")
        
        if st.button("Continue to Step 3: Evaluate →", type="primary", use_container_width=True):
            st.session_state.step = 3
            st.rerun()
    else:
        # Run extraction
        if st.button("🔍 Extract Document Content", type="primary", use_container_width=True):
            run_extraction_pipeline()
    
    # Navigation
    st.markdown("---")
    if st.button("⬅️ Back to Step 1"):
        st.session_state.step = 1
        st.rerun()


def run_extraction_pipeline():
    """Run the document extraction pipeline for all uploaded files."""
    extraction_service = st.session_state.extraction_service
    logger.info("====== EXTRACTION PIPELINE STARTED (Service: %s) ======", extraction_service.value)
    pipeline_start = time.time()
    
    # Inject animation CSS
    st.markdown(STEP_ANIMATION_CSS, unsafe_allow_html=True)
    
    progress_container = st.container()
    
    with progress_container:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Collect all files to process
            all_files = [st.session_state.rfp_file] + st.session_state.proposal_files
            total_files = len(all_files)
            
            status_text.text(f"📄 Processing {total_files} documents...")
            
            async def process_all_documents():
                tasks = []
                for file_data in all_files:
                    task = process_document(
                        file_data["bytes"],
                        file_data["name"],
                        extraction_service
                    )
                    tasks.append(task)
                return await asyncio.gather(*tasks)
            
            results = asyncio.run(process_all_documents())
            
            # Store results
            rfp_content, rfp_duration = results[0]
            st.session_state.rfp_content = rfp_content
            st.session_state.step_durations["rfp_processing"] = rfp_duration
            
            proposal_contents = {}
            for i, file_data in enumerate(st.session_state.proposal_files):
                content, duration = results[i + 1]
                proposal_contents[file_data["name"]] = content
                st.session_state.step_durations[f"proposal_{i}_processing"] = duration
            
            st.session_state.proposal_contents = proposal_contents
            
            progress_bar.progress(100)
            total_duration = time.time() - pipeline_start
            st.session_state.step_durations["extraction_total"] = total_duration
            
            logger.info("====== EXTRACTION PIPELINE COMPLETED in %.2fs ======", total_duration)
            status_text.success(f"✅ All documents processed in {format_duration(total_duration)}")
            
            st.rerun()
            
        except Exception as e:
            logger.error("Extraction pipeline failed: %s", str(e))
            status_text.empty()
            st.error(f"Error during extraction: {str(e)}")


def render_step3():
    """Step 3: Evaluate and Compare."""
    mode_label = "Individual Scoring" if st.session_state.evaluation_mode == "individual" else "Combined Scoring"
    st.header(f"Step 3: Evaluate & Compare ({mode_label})")
    st.markdown("Evaluating vendor proposals against RFP requirements and generating comparison.")
    
    # Show files summary
    col1, col2 = st.columns(2)
    with col1:
        if st.session_state.rfp_file:
            st.info(f"📄 RFP: {st.session_state.rfp_file['name']}")
    with col2:
        if st.session_state.proposal_files:
            st.info(f"📝 Proposals: {len(st.session_state.proposal_files)} file(s)")
    
    # Show evaluation process info
    with st.expander("🤖 Multi-Agent Evaluation Process", expanded=False):
        st.info("""
        **Evaluation Process:**
        
        1. **Criteria Extraction Agent**: Analyzes the RFP document to automatically 
           extract scoring criteria with weights (totaling 100%).
        
        2. **Proposal Scoring Agent**: Evaluates each vendor proposal against the 
           extracted criteria, providing detailed scores and justifications.
        
        3. **Comparison Agent**: Compares all vendor scores and generates a 
           comprehensive comparison report with rankings.
        
        This approach ensures that scoring is tailored to each specific RFP's requirements.
        """)
    
    # Check if evaluation has been completed
    if st.session_state.evaluation_results and st.session_state.comparison_results:
        render_comparison_results()
    else:
        # Start evaluation
        if st.button("🎯 Start Evaluation", type="primary", use_container_width=True):
            run_evaluation_pipeline()
    
    # Navigation
    st.markdown("---")
    if st.button("⬅️ Back to Step 2"):
        st.session_state.step = 2
        st.session_state.evaluation_results = []
        st.session_state.comparison_results = None
        st.rerun()


def run_evaluation_pipeline():
    """Run the full multi-vendor evaluation pipeline with progress indicators."""
    reasoning_effort = st.session_state.reasoning_effort
    evaluation_mode = st.session_state.evaluation_mode
    global_criteria = st.session_state.global_criteria
    
    logger.info("====== EVALUATION PIPELINE STARTED (Mode: %s, Effort: %s) ======", 
               evaluation_mode, reasoning_effort)
    pipeline_start = time.time()
    
    # Inject animation CSS
    st.markdown(STEP_ANIMATION_CSS, unsafe_allow_html=True)
    
    progress_container = st.container()
    
    with progress_container:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            proposal_files = st.session_state.proposal_files
            total_proposals = len(proposal_files)
            
            # Step 1: Evaluate each proposal
            evaluation_results = []
            
            if evaluation_mode == "individual":
                # Score each proposal individually
                for i, proposal_file in enumerate(proposal_files):
                    proposal_name = proposal_file["name"]
                    proposal_content = st.session_state.proposal_contents.get(proposal_name, "")
                    
                    progress_pct = int(10 + (70 * i / total_proposals))
                    progress_bar.progress(progress_pct)
                    status_text.text(f"📊 Evaluating proposal {i+1}/{total_proposals}: {proposal_name}...")
                    
                    logger.info("Evaluating proposal %d/%d: %s", i+1, total_proposals, proposal_name)
                    
                    results, duration = asyncio.run(
                        evaluate_proposal(
                            st.session_state.rfp_content,
                            proposal_content,
                            global_criteria=global_criteria,
                            reasoning_effort=reasoning_effort
                        )
                    )
                    
                    # Add proposal filename to results
                    results["_proposal_file"] = proposal_name
                    evaluation_results.append(results)
                    
                    st.session_state.step_durations[f"eval_{proposal_name}"] = duration
                    logger.info("Proposal %s evaluated in %.2fs", proposal_name, duration)
            else:
                # Combined evaluation - score all together
                # Combine all proposal contents
                combined_content = ""
                for proposal_file in proposal_files:
                    proposal_name = proposal_file["name"]
                    proposal_content = st.session_state.proposal_contents.get(proposal_name, "")
                    combined_content += f"\n\n## Vendor Proposal: {proposal_name}\n\n{proposal_content}"
                
                status_text.text("📊 Evaluating all proposals together...")
                progress_bar.progress(40)
                
                # Check content length and potentially chunk (basic token estimation)
                estimated_tokens = len(combined_content) // 4  # rough estimate
                max_tokens = 100000  # conservative limit
                
                if estimated_tokens > max_tokens:
                    logger.warning("Combined content exceeds token limit, chunking required")
                    # For now, we'll just use the combined content as-is
                    # In production, you'd implement proper chunking
                    st.warning(f"⚠️ Combined content is large ({estimated_tokens:,} estimated tokens). Results may be truncated.")
                
                results, duration = asyncio.run(
                    evaluate_proposal(
                        st.session_state.rfp_content,
                        combined_content,
                        global_criteria=global_criteria,
                        reasoning_effort=reasoning_effort
                    )
                )
                
                results["_proposal_file"] = "Combined Evaluation"
                evaluation_results.append(results)
                st.session_state.step_durations["eval_combined"] = duration
            
            st.session_state.evaluation_results = evaluation_results
            progress_bar.progress(80)
            
            # Step 2: Compare results (if multiple proposals)
            if len(evaluation_results) > 1:
                status_text.text("📈 Comparing vendor results...")
                
                comparison_agent = ComparisonAgent()
                rfp_title = evaluation_results[0].get("rfp_title", "RFP Evaluation")
                
                comparison_results = asyncio.run(
                    comparison_agent.compare_evaluations(
                        evaluation_results,
                        rfp_title,
                        reasoning_effort=reasoning_effort
                    )
                )
                
                st.session_state.comparison_results = comparison_results
                logger.info("Comparison completed")
            else:
                # Single proposal - no comparison needed
                st.session_state.comparison_results = {
                    "rfp_title": evaluation_results[0].get("rfp_title", "RFP Evaluation"),
                    "total_vendors": 1,
                    "vendor_rankings": [{
                        "rank": 1,
                        "vendor_name": evaluation_results[0].get("supplier_name", "Unknown"),
                        "total_score": evaluation_results[0].get("total_score", 0),
                        "grade": evaluation_results[0].get("grade", "N/A"),
                        "key_strengths": evaluation_results[0].get("overall_strengths", [])[:3],
                        "key_concerns": evaluation_results[0].get("overall_weaknesses", [])[:3],
                        "recommendation": evaluation_results[0].get("recommendation", "")
                    }],
                    "selection_recommendation": evaluation_results[0].get("recommendation", ""),
                    "comparison_insights": []
                }
            
            progress_bar.progress(100)
            
            total_duration = time.time() - pipeline_start
            st.session_state.step_durations["evaluation_total"] = total_duration
            
            logger.info("====== EVALUATION PIPELINE COMPLETED in %.2fs ======", total_duration)
            status_text.success(f"✅ Evaluation complete! Total time: {format_duration(total_duration)}")
            
            st.rerun()
            
        except Exception as e:
            logger.error("Evaluation pipeline failed: %s", str(e))
            status_text.empty()
            st.error(f"Error during evaluation: {str(e)}")


def render_comparison_results():
    """Render the multi-vendor comparison results."""
    st.markdown("---")
    
    comparison = st.session_state.comparison_results
    evaluations = st.session_state.evaluation_results
    
    # Display timing if available
    if st.session_state.step_durations:
        total_time = st.session_state.step_durations.get("evaluation_total", 0)
        st.info(f"⏱️ Total evaluation time: {format_duration(total_time)}")
    
    # Vendor Rankings Summary
    st.subheader("🏆 Vendor Rankings")
    
    rankings = comparison.get("vendor_rankings", [])
    if rankings:
        cols = st.columns(min(len(rankings), 4))
        for i, ranking in enumerate(rankings[:4]):
            with cols[i]:
                rank = ranking.get("rank", i+1)
                medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "🏅"
                st.metric(
                    label=f"{medal} #{rank}",
                    value=ranking.get("vendor_name", "Unknown")[:20],
                    delta=f"{ranking.get('total_score', 0):.1f} ({ranking.get('grade', 'N/A')})"
                )
    
    # Selection Recommendation
    recommendation = comparison.get("selection_recommendation", "")
    if recommendation:
        st.success(f"✅ **Recommendation:** {recommendation}")
    
    st.markdown("---")
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Comparison Overview", 
        "📋 Individual Reports", 
        "📈 Detailed Scores",
        "📥 Export"
    ])
    
    with tab1:
        render_comparison_overview(comparison, evaluations)
    
    with tab2:
        render_individual_reports(evaluations)
    
    with tab3:
        render_detailed_scores(evaluations)
    
    with tab4:
        render_export_options(comparison, evaluations)


def render_comparison_overview(comparison: dict, evaluations: list):
    """Render the comparison overview tab."""
    st.subheader("📊 Multi-Vendor Comparison")
    
    # Comparison insights
    insights = comparison.get("comparison_insights", [])
    if insights:
        st.markdown("### Key Insights")
        for insight in insights:
            st.markdown(f"• {insight}")
    
    # Winner summary
    winner_summary = comparison.get("winner_summary", "")
    if winner_summary:
        st.markdown("### Winner Summary")
        st.info(winner_summary)
    
    # Risk comparison
    risk_comparison = comparison.get("risk_comparison", "")
    if risk_comparison:
        st.markdown("### Risk Assessment")
        st.warning(risk_comparison)
    
    # Criterion comparisons
    criterion_comparisons = comparison.get("criterion_comparisons", [])
    if criterion_comparisons:
        st.markdown("### Performance by Criterion")
        
        for cc in criterion_comparisons:
            with st.expander(f"**{cc.get('criterion_name', 'Unknown')}** (Weight: {cc.get('weight', 0):.1f}%)"):
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Best Performer", cc.get("best_vendor", "N/A"))
                with col2:
                    st.metric("Score Range", cc.get("score_range", "N/A"))
                st.caption(cc.get("insights", ""))


def render_individual_reports(evaluations: list):
    """Render individual vendor reports."""
    st.subheader("📋 Individual Vendor Reports")
    
    for i, eval_result in enumerate(evaluations):
        vendor_name = eval_result.get("supplier_name", f"Vendor {i+1}")
        proposal_file = eval_result.get("_proposal_file", "Unknown")
        total_score = eval_result.get("total_score", 0)
        grade = eval_result.get("grade", "N/A")
        
        with st.expander(f"**{vendor_name}** - Score: {total_score:.1f} ({grade})", expanded=i==0):
            # Score summary
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Score", f"{total_score:.1f}")
            with col2:
                st.metric("Grade", grade)
            with col3:
                st.metric("File", proposal_file[:25] + "..." if len(proposal_file) > 25 else proposal_file)
            
            # Criterion scores
            st.markdown("#### Criterion Scores")
            criterion_scores = eval_result.get("criterion_scores", [])
            for cs in criterion_scores:
                score_pct = cs.get("raw_score", 0)
                bar_color = "🟢" if score_pct >= 80 else "🟡" if score_pct >= 60 else "🟠" if score_pct >= 40 else "🔴"
                st.markdown(f"{bar_color} **{cs.get('criterion_name', 'Unknown')}**: {score_pct:.1f}/100 (weighted: {cs.get('weighted_score', 0):.2f})")
            
            # Strengths and weaknesses
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### Strengths")
                for s in eval_result.get("overall_strengths", []):
                    st.markdown(f"✅ {s}")
            with col2:
                st.markdown("#### Weaknesses")
                for w in eval_result.get("overall_weaknesses", []):
                    st.markdown(f"⚠️ {w}")
            
            # Executive summary
            st.markdown("#### Executive Summary")
            st.markdown(eval_result.get("executive_summary", "No summary available."))


def render_detailed_scores(evaluations: list):
    """Render detailed score comparison table."""
    st.subheader("📈 Detailed Score Comparison")
    
    if not evaluations:
        st.warning("No evaluations available.")
        return
    
    # Build comparison data
    # Get all criteria from first evaluation
    criteria = []
    if evaluations[0].get("criterion_scores"):
        criteria = [cs.get("criterion_name", cs.get("criterion_id", f"C-{i}")) 
                   for i, cs in enumerate(evaluations[0]["criterion_scores"])]
    
    # Create comparison table data
    table_data = []
    for criterion_idx, criterion_name in enumerate(criteria):
        row = {"Criterion": criterion_name}
        for eval_result in evaluations:
            vendor_name = eval_result.get("supplier_name", "Unknown")[:15]
            scores = eval_result.get("criterion_scores", [])
            if criterion_idx < len(scores):
                row[vendor_name] = f"{scores[criterion_idx].get('raw_score', 0):.1f}"
            else:
                row[vendor_name] = "N/A"
        table_data.append(row)
    
    # Add total row
    total_row = {"Criterion": "**TOTAL SCORE**"}
    for eval_result in evaluations:
        vendor_name = eval_result.get("supplier_name", "Unknown")[:15]
        total_row[vendor_name] = f"**{eval_result.get('total_score', 0):.1f}**"
    table_data.append(total_row)
    
    st.table(table_data)


def render_export_options(comparison: dict, evaluations: list):
    """Render export options for reports."""
    st.subheader("📥 Export Reports")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### CSV Comparison")
        if comparison and evaluations:
            comparison_agent = ComparisonAgent()
            csv_content = comparison_agent.generate_csv_report(comparison, evaluations)
            st.download_button(
                label="📊 Download CSV",
                data=csv_content,
                file_name="vendor_comparison.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    with col2:
        st.markdown("### JSON Data")
        full_data = {
            "comparison": comparison,
            "evaluations": evaluations
        }
        st.download_button(
            label="📋 Download JSON",
            data=json.dumps(full_data, indent=2),
            file_name="evaluation_data.json",
            mime="application/json",
            use_container_width=True
        )
    
    with col3:
        st.markdown("### Word Reports")
        for i, eval_result in enumerate(evaluations):
            vendor_name = eval_result.get("supplier_name", f"Vendor_{i+1}").replace(" ", "_")
            word_doc = generate_word_report(eval_result)
            if word_doc:
                st.download_button(
                    label=f"📄 {vendor_name[:15]}",
                    data=word_doc,
                    file_name=f"report_{vendor_name}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    key=f"word_{i}"
                )
            else:
                st.caption(f"Word export not available for {vendor_name[:15]}")


def render_results(results: dict):
    """Render the evaluation results in a comprehensive markdown report format."""
    st.markdown("---")
    
    # Display timing information if available
    if st.session_state.step_durations:
        render_timing_summary(st.session_state.step_durations, results)
    
    # Quick score summary at the top
    render_score_summary(results)
    
    # Generate and display the markdown report
    report_md = generate_score_report(results)
    
    # Display report in tabs
    tab1, tab2 = st.tabs(["📊 Score Report", "📋 Raw Data"])
    
    with tab1:
        st.markdown(report_md)
    
    with tab2:
        st.json(results)
    
    # Download buttons section
    st.markdown("---")
    st.subheader("📥 Download Report")
    
    response_id = results.get('response_id', 'report')
    supplier_name = results.get('supplier_name', 'vendor').replace(' ', '_')
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.download_button(
            label="📄 Download Markdown",
            data=report_md,
            file_name=f"rfp_score_report_{response_id}.md",
            mime="text/markdown",
            use_container_width=True,
            help="Download the report as a Markdown file"
        )
    
    with col2:
        import json
        st.download_button(
            label="📋 Download JSON",
            data=json.dumps(results, indent=2),
            file_name=f"rfp_score_report_{response_id}.json",
            mime="application/json",
            use_container_width=True,
            help="Download the raw data as JSON"
        )
    
    with col3:
        if PDF_AVAILABLE and MARKDOWN_AVAILABLE:
            # Generate PDF
            pdf_data = generate_pdf_from_markdown(
                report_md, 
                title=f"RFP Score Report - {supplier_name}"
            )
            if pdf_data:
                st.download_button(
                    label="📑 Download PDF",
                    data=pdf_data,
                    file_name=f"rfp_score_report_{response_id}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    help="Download the report as a PDF file"
                )
            else:
                st.button(
                    "📑 PDF Generation Failed",
                    disabled=True,
                    use_container_width=True,
                    help="PDF generation encountered an error"
                )
        else:
            st.button(
                "📑 PDF Not Available",
                disabled=True,
                use_container_width=True,
                help="Install 'weasyprint' and 'markdown' packages to enable PDF export"
            )


def render_results_v2(results: dict):
    """Render the V2 multi-agent evaluation results."""
    st.markdown("---")
    
    # Display timing information if available
    if st.session_state.step_durations:
        render_timing_summary_v2(st.session_state.step_durations, results)
    
    # Quick score summary
    render_score_summary_v2(results)
    
    # Generate and display the markdown report
    report_md = generate_score_report_v2(results)
    
    # Display report in tabs
    tab1, tab2, tab3 = st.tabs(["📊 Score Report", "📋 Extracted Criteria", "📄 Raw Data"])
    
    with tab1:
        st.markdown(report_md)
    
    with tab2:
        render_extracted_criteria(results)
    
    with tab3:
        st.json(results)
    
    # Download buttons
    st.markdown("---")
    st.subheader("📥 Download Report")
    
    response_id = results.get('response_id', 'report')
    supplier_name = results.get('supplier_name', 'vendor').replace(' ', '_')
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.download_button(
            label="📄 Download Markdown",
            data=report_md,
            file_name=f"rfp_score_report_v2_{response_id}.md",
            mime="text/markdown",
            use_container_width=True
        )
    
    with col2:
        import json
        st.download_button(
            label="📋 Download JSON",
            data=json.dumps(results, indent=2),
            file_name=f"rfp_score_report_v2_{response_id}.json",
            mime="application/json",
            use_container_width=True
        )
    
    with col3:
        if PDF_AVAILABLE and MARKDOWN_AVAILABLE:
            pdf_data = generate_pdf_from_markdown(report_md, title=f"RFP Score Report V2 - {supplier_name}")
            if pdf_data:
                st.download_button(
                    label="📑 Download PDF",
                    data=pdf_data,
                    file_name=f"rfp_score_report_v2_{response_id}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            else:
                st.button("📑 PDF Generation Failed", disabled=True, use_container_width=True)
        else:
            st.button("📑 PDF Not Available", disabled=True, use_container_width=True)


def render_timing_summary_v2(durations: dict, results: dict):
    """Render timing summary for V2 multi-agent evaluation."""
    st.subheader("⏱️ Multi Agents Evaluation Timing")
    
    metadata = results.get("_metadata", {})
    time_saved = durations.get("parallel_time_saved", 0)
    docs_parallel_total = durations.get("docs_parallel_total", 0)
    
    # Row 1: Document processing
    st.markdown("**Document Processing** (parallel)")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        rfp_time = durations.get("rfp_processing", 0)
        st.metric(label="📄 RFP Processing", value=format_duration(rfp_time))
    
    with col2:
        proposal_time = durations.get("proposal_processing", 0)
        st.metric(label="📝 Proposal Processing", value=format_duration(proposal_time))
    
    with col3:
        st.metric(
            label="⚡ Parallel Total", 
            value=format_duration(docs_parallel_total),
            delta=f"-{format_duration(time_saved)} saved" if time_saved > 1 else None,
            delta_color="inverse"
        )
    
    # Row 2: AI Scoring phases
    st.markdown("**AI Evaluation** (multi agents)")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        phase1_time = metadata.get("phase1_criteria_extraction_seconds", 0)
        criteria_count = metadata.get("criteria_count", 0)
        st.metric(
            label="🔍 3a. Criteria Extraction", 
            value=format_duration(phase1_time),
            delta=f"{criteria_count} criteria" if criteria_count else None,
            delta_color="off"
        )
    
    with col2:
        phase2_time = metadata.get("phase2_proposal_scoring_seconds", 0)
        st.metric(label="📊 3b. Proposal Scoring", value=format_duration(phase2_time))
    
    with col3:
        total_time = durations.get("total", 0)
        st.metric(label="⏱️ Total Pipeline", value=format_duration(total_time))
    
    if metadata:
        with st.expander("🔍 Detailed Timing & Model Info", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"""
                **Evaluation Details:**
                - Version: `{metadata.get('version', 'N/A')}`
                - Type: `{metadata.get('evaluation_type', 'N/A')}`
                - Timestamp: `{metadata.get('evaluation_timestamp', 'N/A')}`
                - Model: `{metadata.get('model_deployment', 'N/A')}`
                - Analysis Depth: `{metadata.get('reasoning_effort', 'N/A')}`
                """)
            with col2:
                st.markdown(f"""
                **Multi Agents Timing:**
                - Criteria Extraction (Agent 1): `{format_duration(metadata.get('phase1_criteria_extraction_seconds', 0))}`
                - Proposal Scoring (Agent 2): `{format_duration(metadata.get('phase2_proposal_scoring_seconds', 0))}`
                - Criteria Found: `{metadata.get('criteria_count', 0)}`
                - Time Saved (parallel docs): `{format_duration(time_saved)}`
                """)
    
    st.markdown("---")


def render_score_summary_v2(results: dict):
    """Render a visual score summary header for V2."""
    total_score = results.get("total_score", 0)
    grade = results.get("grade", "N/A")
    supplier_name = results.get("supplier_name", "Unknown Vendor")
    recommendation = results.get("recommendation", "No recommendation")
    criteria_count = results.get("_metadata", {}).get("criteria_count", 0)
    
    # Grade color mapping
    grade_colors = {"A": "green", "B": "blue", "C": "orange", "D": "red", "F": "red"}
    grade_color = grade_colors.get(grade, "gray")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(label="Supplier", value=supplier_name[:20] + "..." if len(supplier_name) > 20 else supplier_name)
    
    with col2:
        st.metric(label="Total Score", value=f"{total_score:.1f}/100", help="Weighted sum of all criterion scores")
    
    with col3:
        st.metric(label="Criteria Evaluated", value=str(criteria_count))
    
    with col4:
        st.markdown(f"""
            <div style="text-align: center; padding: 10px;">
                <p style="font-size: 14px; color: gray; margin: 0;">Grade</p>
                <p style="font-size: 32px; font-weight: bold; color: {grade_color}; margin: 5px 0;">{grade}</p>
            </div>
        """, unsafe_allow_html=True)
    
    # Recommendation banner
    if "recommend" in recommendation.lower() and "not" not in recommendation.lower():
        st.success(f"✅ **Recommendation:** {recommendation}")
    elif "not recommend" in recommendation.lower():
        st.error(f"❌ **Recommendation:** {recommendation}")
    else:
        st.info(f"ℹ️ **Recommendation:** {recommendation}")
    
    st.markdown("---")


def render_extracted_criteria(results: dict):
    """Render the extracted criteria from the RFP."""
    extracted = results.get("extracted_criteria", {})
    criteria = extracted.get("criteria", [])
    
    st.subheader("🔍 Criteria Extracted from RFP")
    
    if extracted.get("rfp_summary"):
        st.info(f"**RFP Summary:** {extracted.get('rfp_summary')}")
    
    if criteria:
        st.markdown(f"**Total Criteria:** {len(criteria)} | **Total Weight:** {extracted.get('total_weight', 100)}%")
        
        # Display as a table
        criteria_data = []
        for c in criteria:
            criteria_data.append({
                "ID": c.get("criterion_id", ""),
                "Name": c.get("name", ""),
                "Category": c.get("category", ""),
                "Weight": f"{c.get('weight', 0):.1f}%",
                "Description": c.get("description", "")[:100] + "..." if len(c.get("description", "")) > 100 else c.get("description", "")
            })
        
        st.dataframe(criteria_data, use_container_width=True)
        
        # Detailed view in expander
        with st.expander("📋 Detailed Criteria Descriptions", expanded=False):
            for c in criteria:
                st.markdown(f"""
                ### {c.get('criterion_id', '')}. {c.get('name', '')} ({c.get('weight', 0):.1f}%)
                
                **Category:** {c.get('category', 'N/A')}
                
                **Description:** {c.get('description', 'N/A')}
                
                **Evaluation Guidance:** {c.get('evaluation_guidance', 'N/A')}
                
                ---
                """)
    else:
        st.warning("No criteria extracted.")
    
    if extracted.get("extraction_notes"):
        st.caption(f"**Notes:** {extracted.get('extraction_notes')}")


def generate_score_report_v2(results: dict) -> str:
    """Generate a comprehensive markdown score report for V2."""
    
    # Extract data
    rfp_title = results.get("rfp_title", "RFP Evaluation")
    supplier_name = results.get("supplier_name", "Unknown Vendor")
    supplier_site = results.get("supplier_site", "N/A")
    response_id = results.get("response_id", "N/A")
    evaluation_date = results.get("evaluation_date", "N/A")
    total_score = results.get("total_score", 0)
    grade = results.get("grade", "N/A")
    recommendation = results.get("recommendation", "N/A")
    
    extracted = results.get("extracted_criteria", {})
    criterion_scores = results.get("criterion_scores", [])
    
    executive_summary = results.get("executive_summary", "")
    overall_strengths = results.get("overall_strengths", [])
    overall_weaknesses = results.get("overall_weaknesses", [])
    recommendations = results.get("recommendations", [])
    risk_assessment = results.get("risk_assessment", "")
    
    # Grade badge
    grade_badges = {
        "A": "🟢 **EXCELLENT**",
        "B": "🔵 **GOOD**",
        "C": "🟡 **ACCEPTABLE**",
        "D": "🟠 **BELOW AVERAGE**",
        "F": "🔴 **POOR**"
    }
    grade_badge = grade_badges.get(grade, "⚪ **UNKNOWN**")
    
    # Build the report
    report = f"""# 📊 RFP Evaluation Report (V2 - Multi Agents)

---

## 📋 Evaluation Summary

| Field | Value |
|-------|-------|
| **RFP Title** | {rfp_title} |
| **Response ID** | {response_id} |
| **Supplier** | {supplier_name} |
| **Supplier Site** | {supplier_site} |
| **Evaluation Date** | {evaluation_date} |
| **Scoring Version** | V2 (Multi-Agent) |

---

## 🎯 Score Overview

| Metric | Value |
|--------|-------|
| **Total Score** | **{total_score:.2f}** / 100 |
| **Grade** | {grade_badge} |
| **Criteria Evaluated** | {len(criterion_scores)} |

### Recommendation

{recommendation}

---

## 🔍 Extracted Criteria Summary

**RFP Summary:** {extracted.get('rfp_summary', 'N/A')}

**Criteria Count:** {extracted.get('criteria_count', len(extracted.get('criteria', [])))}

| ID | Criterion | Category | Weight |
|----|-----------|----------|--------|
"""
    
    # Add criteria summary
    for c in extracted.get("criteria", []):
        report += f"| {c.get('criterion_id', '')} | {c.get('name', '')} | {c.get('category', '')} | {c.get('weight', 0):.1f}% |\n"
    
    report += """
---

## 📈 Detailed Scoring Results

| Criterion | Weight | Raw Score | Weighted Score |
|-----------|--------|-----------|----------------|
"""
    
    # Add score rows
    for cs in criterion_scores:
        raw = cs.get("raw_score", 0)
        weighted = cs.get("weighted_score", 0)
        name = cs.get("criterion_name", cs.get("criterion_id", ""))
        weight = cs.get("weight", 0)
        
        # Score indicator
        if raw >= 80:
            indicator = "🟢"
        elif raw >= 60:
            indicator = "🟡"
        elif raw >= 40:
            indicator = "🟠"
        else:
            indicator = "🔴"
        
        report += f"| {indicator} {name} | {weight:.1f}% | {raw:.1f} | **{weighted:.2f}** |\n"
    
    # Add total row
    total_weighted = sum(cs.get("weighted_score", 0) for cs in criterion_scores)
    report += f"| **TOTAL** | **100%** | - | **{total_weighted:.2f}** |\n"
    
    report += """
---

## 📝 Criterion-by-Criterion Analysis

"""
    
    # Detailed analysis for each criterion
    for cs in criterion_scores:
        criterion_id = cs.get("criterion_id", "")
        criterion_name = cs.get("criterion_name", "")
        raw_score = cs.get("raw_score", 0)
        weighted_score = cs.get("weighted_score", 0)
        weight = cs.get("weight", 0)
        evidence = cs.get("evidence", "No evidence provided")
        justification = cs.get("justification", "No justification provided")
        strengths = cs.get("strengths", [])
        gaps = cs.get("gaps", [])
        
        # Score indicator
        if raw_score >= 80:
            indicator = "🟢"
        elif raw_score >= 60:
            indicator = "🟡"
        elif raw_score >= 40:
            indicator = "🟠"
        else:
            indicator = "🔴"
        
        report += f"""### {indicator} {criterion_id}. {criterion_name}

| Metric | Value |
|--------|-------|
| Raw Score | **{raw_score:.1f}** / 100 |
| Weight | {weight:.1f}% |
| Weighted Score | **{weighted_score:.2f}** |

**Evidence from Proposal:**
> {evidence}

**Justification:**
{justification}

"""
        
        if strengths:
            report += "**Strengths:**\n"
            for s in strengths:
                report += f"- ✅ {s}\n"
            report += "\n"
        
        if gaps:
            report += "**Gaps/Weaknesses:**\n"
            for g in gaps:
                report += f"- ⚠️ {g}\n"
            report += "\n"
        
        report += "---\n\n"
    
    # Overall Analysis
    report += """## 💡 Overall Analysis

### Key Strengths
"""
    if overall_strengths:
        for s in overall_strengths:
            report += f"- ✅ {s}\n"
    else:
        report += "- No specific strengths identified\n"
    
    report += """
### Key Weaknesses
"""
    if overall_weaknesses:
        for w in overall_weaknesses:
            report += f"- ⚠️ {w}\n"
    else:
        report += "- No significant weaknesses identified\n"
    
    report += """
### Recommendations
"""
    if recommendations:
        for i, r in enumerate(recommendations, 1):
            report += f"{i}. {r}\n"
    else:
        report += "1. No specific recommendations at this time\n"
    
    # Risk Assessment
    report += f"""
---

## ⚠️ Risk Assessment

{risk_assessment if risk_assessment else "No risk assessment provided."}

---

## 📋 Executive Summary

{executive_summary if executive_summary else "No executive summary provided."}

---

## 📊 Grade Interpretation Guide

| Grade | Score Range | Interpretation |
|-------|-------------|----------------|
| A | 90-100 | ✅ Excellent - Strongly recommended |
| B | 80-89 | ✅ Good - Recommended |
| C | 70-79 | ⚠️ Acceptable - Consider with improvements |
| D | 60-69 | 🟠 Below Average - Significant concerns |
| F | Below 60 | ❌ Poor - Not recommended |

---

*Report generated by RFP Analyzer V2 (Multi-Agent) - Powered by Azure Content Understanding & Microsoft Agent Framework*
"""
    
    # Add timing metadata if available
    metadata = results.get("_metadata", {})
    if metadata:
        phase1 = format_duration(metadata.get('phase1_criteria_extraction_seconds', 0))
        phase2 = format_duration(metadata.get('phase2_proposal_scoring_seconds', 0))
        total_eval = format_duration(metadata.get('total_duration_seconds', 0))
        
        report += f"""
---

## ⏱️ Evaluation Timing

| Phase | Duration |
|-------|----------|
| **Criteria Extraction (Agent 1)** | {phase1} |
| **Proposal Scoring (Agent 2)** | {phase2} |
| **Total Evaluation Time** | {total_eval} |
| **Model Deployment** | {metadata.get('model_deployment', 'N/A')} |
| **Analysis Depth** | {metadata.get('reasoning_effort', 'N/A')} |
"""
    
    return report


def render_timing_summary(durations: dict, results: dict):
    """Render a timing summary for all evaluation steps."""
    st.subheader("⏱️ Evaluation Timing Summary")
    
    # Get metadata from results if available
    metadata = results.get("_metadata", {})
    
    # Check if parallel processing was used
    time_saved = durations.get("parallel_time_saved", 0)
    docs_parallel_total = durations.get("docs_parallel_total", 0)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        rfp_time = durations.get("rfp_processing", 0)
        st.metric(
            label="📄 RFP Processing",
            value=format_duration(rfp_time),
            help="Time to extract content from RFP document"
        )
    
    with col2:
        proposal_time = durations.get("proposal_processing", 0)
        st.metric(
            label="📝 Proposal Processing",
            value=format_duration(proposal_time),
            help="Time to extract content from Proposal document"
        )
    
    with col3:
        scoring_time = durations.get("scoring", 0)
        api_time = metadata.get("api_call_duration_seconds", scoring_time)
        st.metric(
            label="🧠 AI Scoring",
            value=format_duration(scoring_time),
            delta=f"API: {format_duration(api_time)}" if api_time != scoring_time else None,
            help="Time for AI reasoning and scoring"
        )
    
    with col4:
        total_time = durations.get("total", 0)
        st.metric(
            label="⏱️ Total Time",
            value=format_duration(total_time),
            delta=f"-{format_duration(time_saved)} saved" if time_saved > 1 else None,
            delta_color="inverse",
            help="Total evaluation pipeline duration"
        )
    
    # Show parallel processing info
    if time_saved > 1:
        st.success(f"⚡ **Parallel Processing:** Documents processed simultaneously in {format_duration(docs_parallel_total)} (saved {format_duration(time_saved)})")
    
    # Additional metadata details
    if metadata:
        with st.expander("🔍 Detailed Timing & Model Info", expanded=False):
            detail_col1, detail_col2 = st.columns(2)
            with detail_col1:
                st.markdown(f"""
                **Evaluation Details:**
                - Timestamp: `{metadata.get('evaluation_timestamp', 'N/A')}`
                - Model: `{metadata.get('model_deployment', 'N/A')}`
                - Analysis Depth: `{metadata.get('reasoning_effort', 'N/A')}`
                """)
            with detail_col2:
                api_duration = metadata.get('api_call_duration_seconds', 0)
                parse_duration = metadata.get('parse_duration_seconds', 0)
                total_eval_duration = metadata.get('total_duration_seconds', 0)
                st.markdown(f"""
                **Duration Breakdown:**
                - API Call: `{format_duration(api_duration)}`
                - Response Parsing: `{format_duration(parse_duration)}`
                - Total Evaluation: `{format_duration(total_eval_duration)}`
                """)
    
    st.markdown("---")


def render_score_summary(results: dict):
    """Render a visual score summary header."""
    requirement_score = results.get("requirement_score", 0)
    composite_score = results.get("composite_score", 0)
    supplier_name = results.get("supplier_name", "Unknown Vendor")
    
    # Determine recommendation based on composite score
    if composite_score >= 60:
        recommendation = "✅ STRONGLY RECOMMENDED"
        color = "green"
    elif composite_score >= 50:
        recommendation = "✅ RECOMMENDED"
        color = "green"
    elif composite_score >= 40:
        recommendation = "⚠️ REVIEW REQUIRED"
        color = "orange"
    else:
        recommendation = "❌ NOT RECOMMENDED"
        color = "red"
    
    # Display score cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Supplier",
            value=supplier_name[:20] + "..." if len(supplier_name) > 20 else supplier_name
        )
    
    with col2:
        st.metric(
            label="Requirement Score",
            value=f"{requirement_score:.2f}",
            help="Total score out of 100"
        )
    
    with col3:
        st.metric(
            label="Composite Score",
            value=f"{composite_score:.2f}",
            help="Weighted score out of 70"
        )
    
    with col4:
        st.markdown(
            f"""
            <div style="text-align: center; padding: 10px;">
                <p style="font-size: 14px; color: gray; margin: 0;">Recommendation</p>
                <p style="font-size: 16px; font-weight: bold; color: {color}; margin: 5px 0;">{recommendation}</p>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    st.markdown("---")


def generate_score_report(results: dict) -> str:
    """Generate a comprehensive markdown score report matching the RFP scoring format."""
    
    # Extract data
    rfp_title = results.get("rfp_title", "RFP Evaluation")
    supplier_name = results.get("supplier_name", "Unknown Vendor")
    supplier_site = results.get("supplier_site", "N/A")
    response_id = results.get("response_id", "N/A")
    scoring_status = results.get("scoring_status", "Completed")
    requirement_score = results.get("requirement_score", 0)
    composite_score = results.get("composite_score", 0)
    overall_rank = results.get("overall_rank", 1)
    requirements = results.get("requirements", [])
    strengths = results.get("strengths", [])
    weaknesses = results.get("weaknesses", [])
    recommendations = results.get("recommendations", [])
    summary = results.get("summary", "")
    
    # Determine recommendation based on score
    if composite_score >= 60:
        recommendation_badge = "✅ **RECOMMENDED**"
        recommendation_color = "green"
    elif composite_score >= 50:
        recommendation_badge = "⚠️ **CONDITIONALLY RECOMMENDED**"
        recommendation_color = "orange"
    elif composite_score >= 40:
        recommendation_badge = "🔶 **REVIEW REQUIRED**"
        recommendation_color = "yellow"
    else:
        recommendation_badge = "❌ **NOT RECOMMENDED**"
        recommendation_color = "red"
    
    # Build the report
    report = f"""# 📊 Requirement Scores Report

---

## 📋 Evaluation Summary

| Field | Value |
|-------|-------|
| **Title** | {rfp_title} |
| **Response** | {response_id} |
| **Supplier** | {supplier_name} |
| **Supplier Site** | {supplier_site} |
| **Scoring Status** | {scoring_status} |

---

## 🎯 Score Overview

| Metric | Score |
|--------|-------|
| **Requirement Score** | **{requirement_score:.2f}** / 100 |
| **Composite Score** | **{composite_score:.2f}** / 70 |
| **Overall Rank (Composite)** | {overall_rank} |
| **Recommendation** | {recommendation_badge} |

---

## 📈 Technical Evaluation Criteria

| Requirement | Requirement Text | Evaluation Stage | Target Value | Response Value | Maximum Score | Score | Weight | Weighted Score |
|-------------|------------------|------------------|--------------|----------------|---------------|-------|--------|----------------|
"""
    
    # Add requirement rows
    for req in requirements:
        req_id = req.get("requirement_id", "")
        req_name = req.get("requirement_name", "")
        req_text = req.get("requirement_text", "")
        eval_stage = req.get("evaluation_stage", "Technical")
        target_val = req.get("target_value", "")
        response_val = req.get("response_value", "")[:50] + "..." if len(req.get("response_value", "")) > 50 else req.get("response_value", "")
        max_score = req.get("maximum_score", 20)
        score = req.get("score", 0)
        weight = req.get("weight", 14.0)
        weighted_score = req.get("weighted_score", 0)
        
        report += f"| **{req_id}. {req_name}** | {req_text} | {eval_stage} | {target_val} | {response_val} | {max_score} | **{score:.2f}** | {weight:.0f}% | **{weighted_score:.2f}** |\n"
    
    # Add totals row
    total_max = sum(req.get("maximum_score", 20) for req in requirements) if requirements else 100
    total_score = sum(req.get("score", 0) for req in requirements) if requirements else requirement_score
    total_weight = sum(req.get("weight", 14.0) for req in requirements) if requirements else 70
    total_weighted = sum(req.get("weighted_score", 0) for req in requirements) if requirements else composite_score
    
    report += f"| **TOTAL** | | | | | **{total_max}** | **{total_score:.2f}** | **{total_weight:.0f}%** | **{total_weighted:.2f}** |\n"
    
    report += """
---

## 📝 Detailed Requirement Analysis

"""
    
    # Detailed analysis for each requirement
    for req in requirements:
        req_id = req.get("requirement_id", "")
        req_name = req.get("requirement_name", "")
        score = req.get("score", 0)
        max_score = req.get("maximum_score", 20)
        weighted_score = req.get("weighted_score", 0)
        comments = req.get("comments", "No comments provided")
        response_value = req.get("response_value", "")
        
        # Score indicator
        pct = (score / max_score * 100) if max_score > 0 else 0
        if pct >= 85:
            indicator = "🟢"
        elif pct >= 65:
            indicator = "🟡"
        elif pct >= 45:
            indicator = "🟠"
        else:
            indicator = "🔴"
        
        report += f"""### {indicator} {req_id}. {req_name}

| Metric | Value |
|--------|-------|
| Score | **{score:.2f}** / {max_score} |
| Weighted Score | **{weighted_score:.2f}** |
| Performance | {pct:.0f}% |

**Response Summary:** {response_value}

**Evaluation Comments:** {comments}

---

"""
    
    # Strengths section
    report += """## ✅ Key Strengths

"""
    if strengths:
        for strength in strengths:
            report += f"- {strength}\n"
    else:
        report += "- No specific strengths identified\n"
    
    # Weaknesses section
    report += """
---

## ⚠️ Areas for Improvement

"""
    if weaknesses:
        for weakness in weaknesses:
            report += f"- {weakness}\n"
    else:
        report += "- No significant weaknesses identified\n"
    
    # Recommendations section
    report += """
---

## 💡 Recommendations

"""
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            report += f"{i}. {rec}\n"
    else:
        report += "1. No specific recommendations at this time\n"
    
    # Executive Summary
    report += f"""
---

## 📋 Executive Summary

{summary if summary else "No executive summary provided."}

---

## 📊 Score Interpretation Guide

| Weighted Score Range | Rating | Recommendation |
|---------------------|--------|----------------|
| 60-70 | Excellent | ✅ Strongly recommended for selection |
| 50-59 | Very Good | ✅ Recommended with minor clarifications |
| 40-49 | Good | ⚠️ Consider with some negotiation |
| 30-39 | Acceptable | 🔶 Review concerns before proceeding |
| Below 30 | Poor | ❌ Not recommended |

---

*Report generated by RFP Analyzer - Powered by Azure Content Understanding & Microsoft Agent Framework*
"""
    
    # Add timing metadata if available
    metadata = results.get("_metadata", {})
    if metadata:
        api_duration = format_duration(metadata.get('api_call_duration_seconds', 0))
        total_eval_duration = format_duration(metadata.get('total_duration_seconds', 0))
        report += f"""
---

## ⏱️ Evaluation Timing

| Metric | Value |
|--------|-------|
| **Evaluation Timestamp** | {metadata.get('evaluation_timestamp', 'N/A')} |
| **Model Deployment** | {metadata.get('model_deployment', 'N/A')} |
| **Analysis Depth** | {metadata.get('reasoning_effort', 'N/A')} |
| **API Call Duration** | {api_duration} |
| **Total Evaluation Time** | {total_eval_duration} |
"""
    
    return report


def main():
    """Main application entry point."""
    render_sidebar()
    
    # Render current step
    if st.session_state.step == 1:
        render_step1()
    elif st.session_state.step == 2:
        render_step2()
    elif st.session_state.step == 3:
        render_step3()


if __name__ == "__main__":
    main()
