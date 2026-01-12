"""
RFP Analyzer - Streamlit Application

A 3-step workflow for analyzing RFPs and scoring vendor proposals:
1. Upload the RFP file
2. Upload the Vendor proposal
3. Evaluate and score
"""

import streamlit as st
from pathlib import Path
import asyncio

from services.document_processor import DocumentProcessor
from services.scoring_agent import ScoringAgent

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


def get_scoring_guide() -> str:
    """Load the scoring guide from file."""
    guide_path = Path(__file__).parent / "scoring_guide.md"
    if guide_path.exists():
        return guide_path.read_text(encoding="utf-8")
    return ""


async def process_document(file_bytes: bytes, filename: str) -> str:
    """Process uploaded document using Azure Content Understanding."""
    processor = DocumentProcessor()
    return await processor.extract_content(file_bytes, filename)


async def evaluate_proposal(rfp_content: str, proposal_content: str, scoring_guide: str) -> dict:
    """Evaluate the vendor proposal against the RFP using AI agent."""
    agent = ScoringAgent()
    return await agent.evaluate(rfp_content, proposal_content, scoring_guide)


def render_sidebar():
    """Render the sidebar with step navigation."""
    with st.sidebar:
        st.title("📄 RFP Analyzer")
        st.markdown("---")
        
        # Step indicators
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
    st.header("Step 3: Evaluate & Score")
    st.markdown("Processing documents and analyzing the vendor proposal against RFP requirements.")
    
    # Show uploaded files summary
    col1, col2 = st.columns(2)
    with col1:
        if st.session_state.rfp_file:
            st.info(f"📄 RFP: {st.session_state.rfp_file['name']}")
    with col2:
        if st.session_state.proposal_file:
            st.info(f"📝 Proposal: {st.session_state.proposal_file['name']}")
    
    # Scoring guide
    scoring_guide = get_scoring_guide()
    with st.expander("📊 Scoring Guide", expanded=False):
        if scoring_guide:
            st.markdown(scoring_guide)
        else:
            st.warning("No scoring guide found. Using default evaluation criteria.")
    
    # Process and evaluate
    if st.session_state.scoring_results is None:
        if st.button("🎯 Start Evaluation", type="primary", use_container_width=True):
            run_evaluation_pipeline(scoring_guide)
    
    # Display results
    if st.session_state.scoring_results:
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
    """Run the full evaluation pipeline with progress indicators."""
    progress_container = st.container()
    
    with progress_container:
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Step indicators
        step1_status = st.empty()
        step2_status = st.empty()
        step3_status = st.empty()
        
        try:
            # Step 1: Process RFP
            step1_status.markdown("⏳ **1. Processing RFP document...**")
            step2_status.markdown("⬜ 2. Processing Proposal document...")
            step3_status.markdown("⬜ 3. Scoring and evaluation...")
            status_text.text("Processing RFP document...")
            progress_bar.progress(10)
            
            rfp_content = asyncio.run(
                process_document(
                    st.session_state.rfp_file["bytes"],
                    st.session_state.rfp_file["name"]
                )
            )
            st.session_state.rfp_content = rfp_content
            
            step1_status.markdown("✅ **1. Processing RFP document... Done!**")
            progress_bar.progress(33)
            
            # Step 2: Process Proposal
            step2_status.markdown("⏳ **2. Processing Proposal document...**")
            status_text.text("Processing Proposal document...")
            
            proposal_content = asyncio.run(
                process_document(
                    st.session_state.proposal_file["bytes"],
                    st.session_state.proposal_file["name"]
                )
            )
            st.session_state.proposal_content = proposal_content
            
            step2_status.markdown("✅ **2. Processing Proposal document... Done!**")
            progress_bar.progress(66)
            
            # Step 3: Scoring
            step3_status.markdown("⏳ **3. Scoring and evaluation...**")
            status_text.text("AI Agent is evaluating the proposal...")
            
            results = asyncio.run(
                evaluate_proposal(
                    st.session_state.rfp_content,
                    st.session_state.proposal_content,
                    scoring_guide
                )
            )
            st.session_state.scoring_results = results
            
            step3_status.markdown("✅ **3. Scoring and evaluation... Done!**")
            progress_bar.progress(100)
            status_text.text("Evaluation complete!")
            
            # Clear progress indicators after a moment
            st.rerun()
            
        except Exception as e:
            status_text.empty()
            st.error(f"Error during evaluation: {str(e)}")


def render_results(results: dict):
    """Render the evaluation results in a comprehensive markdown report format."""
    st.markdown("---")
    
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
    
    # Download buttons
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="📥 Download Report (Markdown)",
            data=report_md,
            file_name=f"rfp_score_report_{results.get('response_id', 'report')}.md",
            mime="text/markdown",
            use_container_width=True
        )
    with col2:
        import json
        st.download_button(
            label="📥 Download Report (JSON)",
            data=json.dumps(results, indent=2),
            file_name=f"rfp_score_report_{results.get('response_id', 'report')}.json",
            mime="application/json",
            use_container_width=True
        )


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
