"""
RFP Analyzer - Streamlit Application

A 3-step workflow for analyzing RFPs and scoring vendor proposals:
1. Upload the RFP file
2. Upload the Vendor proposal
3. Evaluate and score
"""

import os
import streamlit as st
from pathlib import Path
import asyncio
import time
import logging
import io
from datetime import datetime

# Initialize Azure Monitor / Application Insights telemetry
# Must be done before other imports to instrument all libraries
from azure.monitor.opentelemetry import configure_azure_monitor
from agent_framework.observability import create_resource, enable_instrumentation


from opentelemetry import trace

os.environ["AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED"] = "true" # False by default


# Configure Application Insights if connection string is available
app_insights_conn_str = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
if app_insights_conn_str:
    configure_azure_monitor(
        connection_string=app_insights_conn_str,
        enable_live_metrics=True,
        resource=create_resource(),
    )

# # optional if you do not have ENABLE_INSTRUMENTATION in env vars
enable_instrumentation()    
from services.document_processor import DocumentProcessor
from services.scoring_agent import ScoringAgent
from services.scoring_agent_v2 import ScoringAgentV2

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
if "proposal_file" not in st.session_state:
    st.session_state.proposal_file = None
if "rfp_content" not in st.session_state:
    st.session_state.rfp_content = None
if "proposal_content" not in st.session_state:
    st.session_state.proposal_content = None
if "scoring_results" not in st.session_state:
    st.session_state.scoring_results = None
if "step_durations" not in st.session_state:
    st.session_state.step_durations = {}
if "scoring_version" not in st.session_state:
    st.session_state.scoring_version = "v1"
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


async def process_document(file_bytes: bytes, filename: str) -> tuple[str, float]:
    """Process uploaded document using Azure Content Understanding.
    
    Returns:
        Tuple of (content, duration_seconds)
    """
    with tracer.start_as_current_span("process_document") as span:
        span.set_attribute("document.filename", filename)
        span.set_attribute("document.size_bytes", len(file_bytes))
        
        start_time = time.time()
        logger.info("Starting document processing: %s", filename)
        
        processor = DocumentProcessor()
        content = await processor.extract_content(file_bytes, filename)
        
        duration = time.time() - start_time
        span.set_attribute("document.content_length", len(content))
        span.set_attribute("document.duration_seconds", duration)
        logger.info("Document processed: %s (%.2fs, %d chars)", filename, duration, len(content))
        
        return content, duration


async def evaluate_proposal(
    rfp_content: str, 
    proposal_content: str, 
    scoring_guide: str, 
    version: str = "v1", 
    reasoning_effort: str = "high",
    progress_callback: callable = None
) -> tuple[dict, float]:
    """Evaluate the vendor proposal against the RFP using AI agent.
    
    Args:
        rfp_content: The RFP content
        proposal_content: The proposal content
        scoring_guide: The scoring guide (used in v1 only)
        version: Scoring version ("v1" or "v2")
        reasoning_effort: Reasoning effort level ("low", "medium", "high")
        progress_callback: Optional callback for progress updates (V2 only)
    
    Returns:
        Tuple of (results, duration_seconds)
    """
    with tracer.start_as_current_span("evaluate_proposal") as span:
        span.set_attribute("evaluation.version", version)
        span.set_attribute("evaluation.reasoning_effort", reasoning_effort)
        span.set_attribute("evaluation.rfp_content_length", len(rfp_content))
        span.set_attribute("evaluation.proposal_content_length", len(proposal_content))
        
        start_time = time.time()
        logger.info("Starting proposal evaluation (version: %s, effort: %s)...", version, reasoning_effort)
        
        if version == "v2":
            agent = ScoringAgentV2()
            results = await agent.evaluate(
                rfp_content, 
                proposal_content, 
                reasoning_effort=reasoning_effort,
                progress_callback=progress_callback
            )
        else:
            agent = ScoringAgent()
            results = await agent.evaluate(rfp_content, proposal_content, scoring_guide, reasoning_effort=reasoning_effort)
        
        duration = time.time() - start_time
        
        # Add result attributes to span
        if isinstance(results, dict) and "total_score" in results:
            span.set_attribute("evaluation.total_score", results["total_score"])
        elif hasattr(results, "evaluation") and hasattr(results.evaluation, "total_score"):
            span.set_attribute("evaluation.total_score", results.evaluation.total_score)
        span.set_attribute("evaluation.duration_seconds", duration)
        
        logger.info("Evaluation completed in %.2fs", duration)
        
        return results, duration


def render_sidebar():
    """Render the sidebar with step navigation."""
    with st.sidebar:
        st.title("📄 RFP Analyzer")
        st.markdown("---")
        
        # Scoring Mode Section (at the top)
        st.subheader("⚙️ Scoring Mode")
        
        # Scoring Version Selection
        version = st.radio(
            "Select scoring version:",
            options=["v1", "v2"],
            index=0 if st.session_state.scoring_version == "v1" else 1,
            format_func=lambda x: "V1 - Single Agent" if x == "v1" else "V2 - Multi Agents",
            help="V1: Uses predefined scoring guide. V2: Extracts criteria from RFP automatically."
        )
        if version != st.session_state.scoring_version:
            st.session_state.scoring_version = version
            st.session_state.scoring_results = None  # Reset results when version changes
            st.rerun()
        
        # Show version description
        if st.session_state.scoring_version == "v1":
            st.caption("📋 Uses predefined scoring criteria from the scoring guide.")
        else:
            st.caption("🤖 Multi Agents: Extracts criteria from RFP, then scores the proposal.")
        
        st.markdown("")
        
        # Analysis Depth Selection
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
            st.session_state.scoring_results = None  # Reset results when effort changes
            st.rerun()
        
        st.markdown("---")
        
        # Step indicators
        st.subheader("📍 Progress")
        steps = [
            ("1️⃣", "Upload RFP", st.session_state.step >= 1),
            ("2️⃣", "Upload Proposal", st.session_state.step >= 2),
            ("3️⃣", "Evaluate & Score", st.session_state.step >= 3),
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
            st.session_state.proposal_file = None
            st.session_state.rfp_content = None
            st.session_state.proposal_content = None
            st.session_state.scoring_results = None
            st.session_state.scoring_version = "v1"
            st.session_state.reasoning_effort = "high"
            st.rerun()
        
        st.markdown("---")
        st.caption("Powered by Azure Content Understanding & Microsoft Agent Framework")


def render_step1():
    """Step 1: Upload RFP file."""
    st.header("Step 1: Upload RFP Document")
    st.markdown("Upload the Request for Proposal (RFP) document to begin the analysis.")
    
    uploaded_file = st.file_uploader(
        "Choose RFP file",
        type=["pdf", "docx", "doc", "txt", "md"],
        key="rfp_uploader",
        help="Supported formats: PDF, Word documents, Text files, Markdown"
    )
    
    if uploaded_file is not None:
        st.info(f"📎 File: **{uploaded_file.name}** ({uploaded_file.size / 1024:.1f} KB)")
        
        if st.button("Continue to Step 2 →", type="primary", use_container_width=True):
            # Store file data for later processing
            st.session_state.rfp_file = {
                "bytes": uploaded_file.getvalue(),
                "name": uploaded_file.name
            }
            st.session_state.step = 2
            st.rerun()
    
    # Show stored file if available
    if st.session_state.rfp_file:
        st.success(f"✅ RFP uploaded: {st.session_state.rfp_file['name']}")


def render_step2():
    """Step 2: Upload Vendor Proposal."""
    st.header("Step 2: Upload Vendor Proposal")
    st.markdown("Upload the vendor's proposal document to compare against the RFP.")
    
    # Show uploaded RFP file
    if st.session_state.rfp_file:
        st.success(f"✅ RFP: {st.session_state.rfp_file['name']}")
    
    uploaded_file = st.file_uploader(
        "Choose Vendor Proposal file",
        type=["pdf", "docx", "doc", "txt", "md"],
        key="proposal_uploader",
        help="Supported formats: PDF, Word documents, Text files, Markdown"
    )
    
    if uploaded_file is not None:
        st.info(f"📎 File: **{uploaded_file.name}** ({uploaded_file.size / 1024:.1f} KB)")
        
        if st.button("Continue to Evaluation →", type="primary", use_container_width=True):
            # Store file data for later processing
            st.session_state.proposal_file = {
                "bytes": uploaded_file.getvalue(),
                "name": uploaded_file.name
            }
            st.session_state.step = 3
            st.rerun()
    
    # Show stored file if available
    if st.session_state.proposal_file:
        st.success(f"✅ Proposal uploaded: {st.session_state.proposal_file['name']}")
    
    # Navigation
    st.markdown("---")
    if st.button("⬅️ Back to Step 1"):
        st.session_state.step = 1
        st.rerun()


def render_step3():
    """Step 3: Evaluate and Score."""
    version_label = "Multi Agents (V2)" if st.session_state.scoring_version == "v2" else "Single Agent (V1)"
    st.header(f"Step 3: Evaluate & Score ({version_label})")
    st.markdown("Processing documents and analyzing the vendor proposal against RFP requirements.")
    
    # Show uploaded files summary
    col1, col2 = st.columns(2)
    with col1:
        if st.session_state.rfp_file:
            st.info(f"📄 RFP: {st.session_state.rfp_file['name']}")
    with col2:
        if st.session_state.proposal_file:
            st.info(f"📝 Proposal: {st.session_state.proposal_file['name']}")
    
    # Scoring guide (v1) or criteria extraction info (v2)
    scoring_guide = get_scoring_guide()
    if st.session_state.scoring_version == "v1":
        with st.expander("📊 Scoring Guide (V1)", expanded=False):
            if scoring_guide:
                st.markdown(scoring_guide)
            else:
                st.warning("No scoring guide found. Using default evaluation criteria.")
    else:
        with st.expander("🤖 Multi Agents Scoring (V2)", expanded=False):
            st.info("""
            **V2 Multi Agents Scoring Process:**
            
            1. **Agent 1 - Criteria Extraction**: Analyzes the RFP document to automatically 
               extract scoring criteria with weights (totaling 100%).
            
            2. **Agent 2 - Proposal Scoring**: Evaluates the vendor proposal against the 
               extracted criteria, providing detailed scores and justifications.
            
            This approach ensures that scoring is tailored to each specific RFP's requirements.
            """)
    
    # Process and evaluate
    if st.session_state.scoring_results is None:
        if st.button("🎯 Start Evaluation", type="primary", use_container_width=True):
            run_evaluation_pipeline(scoring_guide)
    
    # Display results
    if st.session_state.scoring_results:
        if st.session_state.scoring_version == "v2":
            render_results_v2(st.session_state.scoring_results)
        else:
            render_results(st.session_state.scoring_results)
        
        # Show processed content
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            with st.expander("📄 Processed RFP Content", expanded=False):
                st.markdown(st.session_state.rfp_content)
        with col2:
            with st.expander("📝 Processed Proposal Content", expanded=False):
                st.markdown(st.session_state.proposal_content)
    
    # Navigation
    st.markdown("---")
    if st.button("⬅️ Back to Step 2"):
        st.session_state.step = 2
        st.session_state.scoring_results = None
        st.session_state.rfp_content = None
        st.session_state.proposal_content = None
        st.rerun()


def run_evaluation_pipeline(scoring_guide: str):
    """Run the full evaluation pipeline with progress indicators, animations, and timing."""
    scoring_version = st.session_state.scoring_version
    reasoning_effort = st.session_state.reasoning_effort
    logger.info("====== EVALUATION PIPELINE STARTED (Version: %s, Effort: %s) ======", 
               scoring_version.upper(), reasoning_effort)
    pipeline_start = time.time()
    
    # Inject animation CSS
    st.markdown(STEP_ANIMATION_CSS, unsafe_allow_html=True)
    
    progress_container = st.container()
    
    with progress_container:
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Step indicators with animation containers
        step1_container = st.empty()
        step2_container = st.empty()
        step3_container = st.empty()
        
        # Timer display
        timer_display = st.empty()
        
        try:
            # Step 1: Process RFP and Proposal documents IN PARALLEL
            docs_start = time.time()
            logger.info("STEP 1: Processing documents in parallel (RFP + Proposal)...")
            
            step1_container.markdown("""
                <div class="processing-container">
                    <span class="spinner"></span>
                    <strong>1. Processing RFP document...</strong>
                    <span class="duration-badge">⏱️ Running...</span>
                </div>
            """, unsafe_allow_html=True)
            step2_container.markdown("""
                <div class="processing-container">
                    <span class="spinner"></span>
                    <strong>2. Processing Proposal document...</strong>
                    <span class="duration-badge">⏱️ Running in parallel...</span>
                </div>
            """, unsafe_allow_html=True)
            step3_container.markdown("⬜ 3. AI Reasoning & Scoring...")
            status_text.text("📄📝 Processing both documents in parallel...")
            progress_bar.progress(10)
            
            # Process both documents concurrently using asyncio.gather
            async def process_documents_parallel():
                rfp_task = process_document(
                    st.session_state.rfp_file["bytes"],
                    st.session_state.rfp_file["name"]
                )
                proposal_task = process_document(
                    st.session_state.proposal_file["bytes"],
                    st.session_state.proposal_file["name"]
                )
                return await asyncio.gather(rfp_task, proposal_task)
            
            (rfp_content, rfp_duration), (proposal_content, proposal_duration) = asyncio.run(
                process_documents_parallel()
            )
            
            # Calculate parallel processing stats
            docs_total_duration = time.time() - docs_start
            time_saved = (rfp_duration + proposal_duration) - docs_total_duration
            
            st.session_state.rfp_content = rfp_content
            st.session_state.proposal_content = proposal_content
            st.session_state.step_durations["rfp_processing"] = rfp_duration
            st.session_state.step_durations["proposal_processing"] = proposal_duration
            st.session_state.step_durations["docs_parallel_total"] = docs_total_duration
            st.session_state.step_durations["parallel_time_saved"] = time_saved
            
            step1_container.markdown(f"✅ **1. Processing RFP document... Done!** `{format_duration(rfp_duration)}`")
            step2_container.markdown(f"✅ **2. Processing Proposal document... Done!** `{format_duration(proposal_duration)}`")
            logger.info("STEP 1-2 completed in %.2fs (parallel) - RFP: %.2fs, Proposal: %.2fs, Time saved: %.2fs", 
                       docs_total_duration, rfp_duration, proposal_duration, time_saved)
            progress_bar.progress(50)
            
            # Step 3: Scoring with AI Reasoning
            step3_start = time.time()
            scoring_version = st.session_state.scoring_version
            
            # For V2, we have two sub-steps: extraction and scoring
            step3a_container = st.empty()  # Criteria extraction (V2 only)
            step3b_container = st.empty()  # Proposal scoring (V2) or combined scoring (V1)
            
            if scoring_version == "v2":
                logger.info("STEP 3: Multi-Agent Scoring (V2)...")
                
                # Show V2 sub-steps
                step3_container.markdown("**3. AI Evaluation (Multi Agents V2)**")
                step3a_container.markdown("""
                    <div class="processing-container">
                        <span class="spinner"></span>
                        <strong>3a. Extracting scoring criteria from RFP...</strong>
                        <span class="duration-badge">🔍 Analyzing requirements...</span>
                    </div>
                """, unsafe_allow_html=True)
                step3b_container.markdown("⬜ 3b. Scoring proposal against criteria...")
                status_text.text("🔍 Agent 1: Analyzing RFP to extract evaluation criteria...")
                
                # Track V2 phase durations
                phase1_duration = 0
                phase2_duration = 0
                
                def v2_progress_callback(phase_message: str):
                    nonlocal phase1_duration
                    if "Phase 2" in phase_message or "Scoring" in phase_message:
                        # Phase 1 complete, update UI for phase 2
                        phase1_duration = time.time() - step3_start
                        step3a_container.markdown(f"✅ **3a. Extracting criteria... Done!** `{format_duration(phase1_duration)}`")
                        step3b_container.markdown("""
                            <div class="processing-container">
                                <span class="spinner"></span>
                                <strong>3b. Scoring proposal against criteria...</strong>
                                <span class="duration-badge">📊 Evaluating proposal...</span>
                            </div>
                        """, unsafe_allow_html=True)
                        status_text.text("📊 Agent 2: Evaluating proposal against extracted criteria...")
                        progress_bar.progress(75)
                
                results, scoring_duration = asyncio.run(
                    evaluate_proposal(
                        st.session_state.rfp_content,
                        st.session_state.proposal_content,
                        scoring_guide,
                        version=scoring_version,
                        reasoning_effort=st.session_state.reasoning_effort,
                        progress_callback=v2_progress_callback
                    )
                )
                
                # Get actual phase durations from metadata
                metadata = results.get("_metadata", {})
                phase1_actual = metadata.get("phase1_criteria_extraction_seconds", phase1_duration)
                phase2_actual = metadata.get("phase2_proposal_scoring_seconds", 0)
                
                step3a_container.markdown(f"✅ **3a. Extracting criteria... Done!** `{format_duration(phase1_actual)}`")
                step3b_container.markdown(f"✅ **3b. Scoring proposal... Done!** `{format_duration(phase2_actual)}`")
                
            else:
                logger.info("STEP 3: AI Reasoning & Scoring (V1)...")
                step3_container.markdown("""
                    <div class="processing-container">
                        <span class="spinner"></span>
                        <strong>3. AI Reasoning & Scoring (V1)...</strong>
                        <span class="duration-badge">🧠 Deep analysis in progress...</span>
                    </div>
                """, unsafe_allow_html=True)
                status_text.text("🧠 AI Agent is performing deep reasoning analysis (this may take a moment)...")
                
                results, scoring_duration = asyncio.run(
                    evaluate_proposal(
                        st.session_state.rfp_content,
                        st.session_state.proposal_content,
                        scoring_guide,
                        version=scoring_version,
                        reasoning_effort=st.session_state.reasoning_effort
                    )
                )
                
                step3_container.markdown(f"✅ **3. AI Scoring (V1)... Done!** `{format_duration(scoring_duration)}`")
            
            st.session_state.scoring_results = results
            st.session_state.step_durations["scoring"] = scoring_duration
            
            logger.info("STEP 3 completed in %.2fs", scoring_duration)
            progress_bar.progress(100)
            
            # Calculate total duration
            total_duration = time.time() - pipeline_start
            st.session_state.step_durations["total"] = total_duration
            
            # Calculate time saved from parallel processing
            time_saved = st.session_state.step_durations.get("parallel_time_saved", 0)
            
            logger.info("====== EVALUATION PIPELINE COMPLETED ======")
            logger.info("Total pipeline duration: %.2fs", total_duration)
            logger.info("Breakdown - Docs (parallel): %.2fs (RFP: %.2fs, Proposal: %.2fs, Saved: %.2fs), Scoring: %.2fs",
                       docs_total_duration, rfp_duration, proposal_duration, time_saved, scoring_duration)
            
            saved_msg = f" (saved {format_duration(time_saved)} with parallel processing)" if time_saved > 1 else ""
            status_text.success(f"✨ Evaluation complete! Total time: {format_duration(total_duration)}{saved_msg}")
            
            # Clear progress indicators after a moment
            st.rerun()
            
        except Exception as e:
            logger.error("Pipeline failed with error: %s", str(e))
            status_text.empty()
            st.error(f"Error during evaluation: {str(e)}")


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
