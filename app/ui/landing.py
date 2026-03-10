"""Landing page for RFP Analyzer."""

import streamlit as st

from services.logging_config import get_logger

logger = get_logger(__name__)


def render_landing_page():
    """Render the landing page with hero, feature cards and how-it-works timeline."""

    # Gradient hero section
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 50%, #6D28D9 100%);
        border-radius: 16px;
        padding: 48px 24px;
        text-align: center;
        margin-bottom: 32px;
        color: white;
    ">
        <p style="font-size: 3.2rem; margin: 0; line-height: 1.1;">📄</p>
        <h1 style="font-size: 2.6rem; margin: 8px 0 0 0; color: white; font-weight: 800;">
            RFP Analyzer
        </h1>
        <p style="font-size: 1.15rem; opacity: 0.9; margin-top: 8px; color: #E0E7FF;">
            AI-Powered RFP Analysis &amp; Vendor Evaluation
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Description
    st.markdown(
        "### Transform Your RFP Review Process\n\n"
        "RFP Analyzer uses advanced AI to streamline your vendor evaluation process. "
        "Simply upload your RFP document and vendor proposals, and let our multi-agent "
        "system do the heavy lifting."
    )

    st.markdown("")

    # Feature cards using styled containers
    card_css = (
        "background: white; border: 1px solid #E5E7EB; border-radius: 12px; "
        "padding: 24px; height: 100%; box-shadow: 0 1px 3px rgba(0,0,0,0.06);"
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"""
        <div style="{card_css}">
            <p style="font-size:1.6rem;margin:0;">🔍</p>
            <h4 style="margin:8px 0 4px 0;">Smart Extraction</h4>
            <p style="color:#6B7280;font-size:0.95rem;">
                Automatically extract text from PDFs, Word documents, and more using Azure AI services.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="{card_css}">
            <p style="font-size:1.6rem;margin:0;">🎯</p>
            <h4 style="margin:8px 0 4px 0;">Intelligent Scoring</h4>
            <p style="color:#6B7280;font-size:0.95rem;">
                AI agents analyze proposals against RFP criteria with detailed justifications.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)

    col3, col4 = st.columns(2)

    with col3:
        st.markdown(f"""
        <div style="{card_css}">
            <p style="font-size:1.6rem;margin:0;">📊</p>
            <h4 style="margin:8px 0 4px 0;">Comparative Analysis</h4>
            <p style="color:#6B7280;font-size:0.95rem;">
                Compare multiple vendors side-by-side with visual dashboards and rankings.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div style="{card_css}">
            <p style="font-size:1.6rem;margin:0;">📥</p>
            <h4 style="margin:8px 0 4px 0;">Comprehensive Reports</h4>
            <p style="color:#6B7280;font-size:0.95rem;">
                Export detailed reports in Word, CSV, or JSON formats.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("")
    st.divider()

    # How it works — 3-step visual timeline
    st.markdown("### How It Works")
    st.markdown("")

    step_style = (
        "display:flex;align-items:flex-start;gap:16px;margin-bottom:20px;"
    )
    circle_style = (
        "min-width:40px;height:40px;border-radius:50%;background:#4F46E5;"
        "color:white;display:flex;align-items:center;justify-content:center;"
        "font-weight:700;font-size:1.1rem;"
    )

    st.markdown(f"""
    <div style="max-width:600px;margin:0 auto;">
        <div style="{step_style}">
            <div style="{circle_style}">1</div>
            <div>
                <strong>Upload Documents</strong>
                <p style="color:#6B7280;margin:2px 0 0 0;">
                    Add your RFP and vendor proposal files (PDF, Word, TXT).
                </p>
            </div>
        </div>
        <div style="width:2px;height:20px;background:#E5E7EB;margin:0 0 12px 19px;"></div>
        <div style="{step_style}">
            <div style="{circle_style}">2</div>
            <div>
                <strong>Configure &amp; Extract</strong>
                <p style="color:#6B7280;margin:2px 0 0 0;">
                    Select extraction settings and let AI parse your documents.
                </p>
            </div>
        </div>
        <div style="width:2px;height:20px;background:#E5E7EB;margin:0 0 12px 19px;"></div>
        <div style="{step_style}">
            <div style="{circle_style}">3</div>
            <div>
                <strong>Evaluate &amp; Compare</strong>
                <p style="color:#6B7280;margin:2px 0 0 0;">
                    AI scores each proposal and generates a comparative report.
                </p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("")
    st.markdown("")

    # Start button — centered and prominent
    _col_left, col_center, _col_right = st.columns([1, 2, 1])
    with col_center:
        if st.button(
            "🚀 Start Analysis",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.is_processing,
            help="Click to begin the RFP analysis process"
        ):
            logger.info("User started RFP analysis from landing page")
            st.session_state.step = 1
            st.rerun()

    st.markdown("")
    st.caption("Tip: Have your RFP document and vendor proposals ready before starting.")
