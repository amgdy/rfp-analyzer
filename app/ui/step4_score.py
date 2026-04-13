"""Step 4: Score Proposals and Compare vendor results."""

import streamlit as st
import asyncio
import time
import uuid
import json

from services.utils import format_duration
from services.comparison_agent import ComparisonAgent, generate_word_report, generate_full_analysis_report
from services.processing_queue import ProcessingQueue, QueueItemStatus
from services.logging_config import get_logger
from services.telemetry import get_tracer
from ui.styles import STEP_ANIMATION_CSS
from ui.components import render_step_indicator

# Optional chart support
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

logger = get_logger(__name__)
tracer = get_tracer(__name__)


def render_step4():
    """Step 4: Score Proposals & Compare."""
    render_step_indicator(current_step=4)

    st.header("Step 4: Score & Compare")
    st.markdown("Scoring vendor proposals against the extracted criteria and generating comparison.")

    # Show files summary
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.session_state.rfp_file:
            st.info(f"📄 RFP: {st.session_state.rfp_file['name']}")
    with col2:
        if st.session_state.proposal_files:
            st.info(f"📝 Proposals: {len(st.session_state.proposal_files)} file(s)")
    with col3:
        criteria_data = st.session_state.extracted_criteria
        if criteria_data:
            criteria_count = len(criteria_data.get("criteria", []))
            st.info(f"📋 Criteria: {criteria_count}")

    # Show scoring process info
    with st.expander("🤖 Scoring Process", expanded=False):
        st.info("""
        **How Scoring Works:**

        1. **Proposal Scoring Agent**: Evaluates each vendor proposal against the
           extracted criteria, providing detailed scores and justifications.

        2. **Comparison Agent**: Compares all vendor scores and generates a
           comprehensive comparison report with rankings.

        Criteria have already been extracted in the previous step.
        """)

    # Check if evaluation has been completed
    has_results = st.session_state.evaluation_results and st.session_state.comparison_results
    has_disqualified = getattr(st.session_state, "disqualified_results", None)
    if has_results or has_disqualified:
        render_comparison_results()
    else:
        # Start evaluation
        if st.button(
            "🎯 Start Evaluation",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.is_processing
        ):
            logger.info("User starting evaluation - Mode: individual, Effort: %s, Proposals: %d",
                       st.session_state.reasoning_effort,
                       len(st.session_state.proposal_files))
            st.session_state.is_processing = True
            run_evaluation_pipeline()

    # Navigation
    st.markdown("---")
    if st.button("⬅️ Back to Step 3", disabled=st.session_state.is_processing):
        logger.info("User navigating back to Step 3")
        st.session_state.step = 3
        st.session_state.evaluation_results = []
        st.session_state.disqualified_results = []
        st.session_state.comparison_results = None
        st.rerun()


def run_evaluation_pipeline():
    """Run the proposal scoring pipeline with parallel processing and clean UI."""
    from services.pipelines import score_proposal

    reasoning_effort = st.session_state.reasoning_effort
    extracted_criteria = st.session_state.extracted_criteria

    logger.info("====== SCORING PIPELINE STARTED (Effort: %s) ======", reasoning_effort)
    pipeline_start = time.time()

    with tracer.start_as_current_span("scoring_pipeline") as pipeline_span:
        pipeline_span.set_attribute("pipeline.type", "scoring")
        pipeline_span.set_attribute("pipeline.reasoning_effort", reasoning_effort)
        pipeline_span.set_attribute("pipeline.proposal_count", len(st.session_state.proposal_files))

        # Inject animation CSS
        st.markdown(STEP_ANIMATION_CSS, unsafe_allow_html=True)

        # Create scoring queue
        scoring_queue = ProcessingQueue(name="Proposal Scoring")
        proposal_files = st.session_state.proposal_files

        # Add each proposal as a separate queue item with unique request ID
        for i, proposal_file in enumerate(proposal_files):
            request_id = str(uuid.uuid4())[:8]
            scoring_queue.add_item(
                id=f"proposal_{i}",
                name=proposal_file['name'],
                item_type="evaluation",
                metadata={
                    "filename": proposal_file["name"],
                    "request_id": request_id
                }
            )
            logger.info("Queued proposal for scoring: %s (request_id: %s)",
                       proposal_file['name'], request_id)

        # Add comparison step if multiple proposals
        if len(proposal_files) > 1:
            comparison_request_id = str(uuid.uuid4())[:8]
            scoring_queue.add_item(
                id="comparison",
                name="Vendor Comparison",
                item_type="comparison",
                metadata={"request_id": comparison_request_id}
            )
            logger.info("Queued vendor comparison (request_id: %s)", comparison_request_id)

        scoring_queue.start()
        st.session_state.scoring_queue = scoring_queue

        # UI Setup - single placeholder for clean updates
        st.subheader("🎯 Evaluating Proposals")
        status_placeholder = st.empty()

        def render_status():
            """Render the current scoring status."""
            with status_placeholder.container():
                elapsed = time.time() - pipeline_start
                st.markdown(f"**⏱️ Elapsed: `{format_duration(elapsed)}`**")

                # Progress bar
                progress = scoring_queue.get_progress()
                st.progress(progress["percentage"] / 100)

                # Items status
                for item in scoring_queue.items:
                    icon = item.get_status_icon()
                    elapsed_time = format_duration(item.get_elapsed_time()) if item.start_time else "-"

                    if item.item_type == "comparison":
                        label = f"📊 {item.name}"
                    else:
                        label = f"📝 {item.name}"

                    if item.status == QueueItemStatus.COMPLETED:
                        extra = ""
                        if item.result and isinstance(item.result, dict) and "total_score" in item.result:
                            score = item.result["total_score"]
                            grade = item.result.get("grade", "")
                            extra = f" — Score: **{score:.1f}** ({grade})"
                        st.success(f"{icon} {label}{extra} — `{elapsed_time}`")
                    elif item.status == QueueItemStatus.PROCESSING:
                        st.info(f"{icon} {label} — Processing... `{elapsed_time}`")
                    elif item.status == QueueItemStatus.FAILED:
                        st.error(f"{icon} {label} — Failed: {item.error_message}")
                    else:
                        st.warning(f"{icon} {label} — Waiting...")

        try:
            evaluation_results = []

            # Mark all proposal items as processing
            for i in range(len(proposal_files)):
                item = scoring_queue.get_item(f"proposal_{i}")
                item.start()

            render_status()

            # Define async function for parallel proposal scoring
            async def score_all_proposals():
                tasks = []
                for i, proposal_file in enumerate(proposal_files):
                    proposal_name = proposal_file["name"]
                    proposal_content = st.session_state.proposal_contents.get(proposal_name, "")

                    task = score_proposal(
                        extracted_criteria,
                        proposal_content,
                        reasoning_effort=reasoning_effort,
                        proposal_filename=proposal_name,
                    )
                    tasks.append(task)
                return await asyncio.gather(*tasks, return_exceptions=True)

            # Run parallel scoring
            results = asyncio.run(score_all_proposals())

            # Process results
            for i, result in enumerate(results):
                proposal_name = proposal_files[i]["name"]
                item = scoring_queue.get_item(f"proposal_{i}")

                if isinstance(result, Exception):
                    item.fail(str(result))
                    logger.error("Failed to evaluate %s: %s", proposal_name, str(result))
                else:
                    eval_result, duration = result
                    eval_result["_proposal_file"] = proposal_name
                    evaluation_results.append(eval_result)
                    item.complete(result=eval_result)
                    st.session_state.step_durations[f"eval_{proposal_name}"] = duration
                    logger.info("Proposal %s evaluated in %.2fs", proposal_name, duration)

            render_status()

            # Check for failures using get_failed_items
            failed_items = scoring_queue.get_failed_items()
            if failed_items:
                raise Exception(f"Failed to evaluate {len(failed_items)} proposal(s)")

            # Separate qualified proposals from disqualified documents
            qualified_results = [
                r for r in evaluation_results
                if r.get("is_qualified_proposal", True)
            ]
            disqualified_results = [
                r for r in evaluation_results
                if not r.get("is_qualified_proposal", True)
            ]

            if disqualified_results:
                logger.info(
                    "%d document(s) disqualified as non-proposals: %s",
                    len(disqualified_results),
                    [r.get("_proposal_file", "?") for r in disqualified_results],
                )

            st.session_state.evaluation_results = qualified_results
            st.session_state.disqualified_results = disqualified_results

            # Compare results if multiple qualified proposals
            if len(qualified_results) > 1:
                comparison_item = scoring_queue.get_item("comparison")
                comparison_item.start()

                render_status()

                try:
                    comparison_agent = ComparisonAgent()
                    rfp_title = evaluation_results[0].get("rfp_title", "RFP Evaluation")

                    comparison_results = asyncio.run(
                        comparison_agent.compare_evaluations(
                            qualified_results,
                            rfp_title,
                            reasoning_effort=reasoning_effort
                        )
                    )

                    st.session_state.comparison_results = comparison_results
                    comparison_item.complete(result=comparison_results)
                    logger.info("Comparison completed")

                except Exception as e:
                    comparison_item.fail(str(e))
                    raise
            else:
                # Single proposal - create basic comparison structure
                if qualified_results:
                    st.session_state.comparison_results = {
                        "rfp_title": qualified_results[0].get("rfp_title", "RFP Evaluation"),
                        "total_vendors": len(qualified_results),
                        "vendor_rankings": [{
                            "rank": 1,
                            "vendor_name": qualified_results[0].get("supplier_name", "Unknown"),
                            "total_score": qualified_results[0].get("total_score", 0),
                            "grade": qualified_results[0].get("grade", "N/A"),
                            "key_strengths": qualified_results[0].get("overall_strengths", [])[:3],
                            "key_concerns": qualified_results[0].get("overall_weaknesses", [])[:3],
                            "recommendation": qualified_results[0].get("recommendation", "")
                        }],
                        "selection_recommendation": qualified_results[0].get("recommendation", ""),
                        "comparison_insights": []
                    }
                elif disqualified_results:
                    # All proposals were disqualified
                    st.session_state.comparison_results = {
                        "rfp_title": disqualified_results[0].get("rfp_title", "RFP Evaluation"),
                        "total_vendors": 0,
                        "vendor_rankings": [],
                        "selection_recommendation": "No qualified proposals to compare.",
                        "comparison_insights": []
                    }

            scoring_queue.finish()
            st.session_state.scoring_queue = scoring_queue

            total_duration = time.time() - pipeline_start
            st.session_state.step_durations["evaluation_total"] = total_duration
            pipeline_span.set_attribute("pipeline.duration_seconds", total_duration)
            pipeline_span.set_attribute("pipeline.status", "success")
            pipeline_span.set_attribute("pipeline.qualified_count", len(qualified_results))

            logger.info("====== SCORING PIPELINE COMPLETED in %.2fs ======", total_duration)

            # Final render
            render_status()

            st.success(f"✅ **Evaluation complete in {format_duration(total_duration)}!**")

            st.session_state.is_processing = False
            time.sleep(1)
            st.rerun()

        except Exception as e:
            pipeline_span.record_exception(e)
            pipeline_span.set_attribute("pipeline.status", "failed")
            logger.error("Evaluation pipeline failed: %s", str(e))
            scoring_queue.finish()
            st.session_state.scoring_queue = scoring_queue
            st.session_state.is_processing = False
            render_status()
            st.error("❌ Error during evaluation. Please check the logs and try again.")


# ---------------------------------------------------------------------------
# Comparison results rendering
# ---------------------------------------------------------------------------

def render_comparison_results():
    """Render the multi-vendor comparison results."""
    st.markdown("---")

    comparison = st.session_state.comparison_results
    evaluations = st.session_state.evaluation_results
    disqualified = getattr(st.session_state, "disqualified_results", None) or []

    # Display timing if available
    if st.session_state.step_durations:
        total_time = st.session_state.step_durations.get("evaluation_total", 0)
        st.info(f"⏱️ Total evaluation time: {format_duration(total_time)}")

    # Show disqualified documents if any
    if disqualified:
        st.subheader("⚠️ Disqualified Documents")
        st.warning(
            f"{len(disqualified)} document(s) were excluded from scoring because they are "
            "not qualified vendor proposals for this RFP."
        )
        for dq in disqualified:
            filename = dq.get("_proposal_file", "Unknown file")
            vendor = dq.get("supplier_name", "Unknown")
            reason = dq.get("disqualification_reason", "Not a vendor proposal")
            with st.expander(f"🚫 {filename} ({vendor})"):
                st.markdown(f"**Reason:** {reason}")
                summary = dq.get("executive_summary", "")
                if summary:
                    st.markdown(f"**Summary:** {summary}")
        st.markdown("---")

    if not evaluations:
        st.warning("No qualified vendor proposals to compare.")
        return

    # ------------------------------------------------------------------
    # Build a single, authoritative ranking from evaluation data so that
    # the vendor cards, charts, and text all agree.
    # ------------------------------------------------------------------
    ranked_evals = sorted(evaluations, key=lambda e: e.get("total_score", 0), reverse=True)

    st.subheader("🏆 Vendor Rankings")

    if ranked_evals:
        cols = st.columns(min(len(ranked_evals), 4))
        for i, eval_result in enumerate(ranked_evals[:4]):
            with cols[i]:
                rank = i + 1
                medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "🏅"
                st.metric(
                    label=f"{medal} #{rank}",
                    value=eval_result.get("supplier_name", "Unknown")[:20],
                    delta=f"{eval_result.get('total_score', 0):.1f} ({eval_result.get('grade', 'N/A')})"
                )

    # Selection Recommendation
    recommendation = comparison.get("selection_recommendation", "")
    if recommendation:
        st.success(f"✅ **Recommendation:** {recommendation}")

    st.markdown("---")

    # Tabs for different views
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Dashboard",
        "🔍 Comparison Overview",
        "📋 Individual Reports",
        "📈 Detailed Scores",
        "📥 Export"
    ])

    with tab1:
        render_metrics_dashboard(comparison, evaluations)

    with tab2:
        render_comparison_overview(comparison, evaluations)

    with tab3:
        render_individual_reports(evaluations)

    with tab4:
        render_detailed_scores(evaluations)

    with tab5:
        render_export_options(comparison, evaluations)


def _build_criterion_score_map(eval_result: dict) -> dict:
    """Build a {criterion_id: score_dict} lookup from an evaluation result.

    Using criterion_id as the key guarantees that charts and text refer to
    the same criterion regardless of ordering differences between vendors.
    """
    return {
        cs.get("criterion_id", f"C-{i}"): cs
        for i, cs in enumerate(eval_result.get("criterion_scores", []))
    }


# Vendor color palette — visually distinct, color-blind friendly.
# Each vendor gets a fixed color across every chart.
_VENDOR_PALETTE = [
    "#4F46E5",  # indigo
    "#E11D48",  # rose
    "#059669",  # emerald
    "#D97706",  # amber
    "#7C3AED",  # violet
    "#0891B2",  # cyan
    "#DC2626",  # red
    "#2563EB",  # blue
    "#65A30D",  # lime
    "#DB2777",  # pink
    "#0D9488",  # teal
    "#EA580C",  # orange
]


def _build_vendor_color_map(evaluations: list) -> dict[str, str]:
    """Return a deterministic vendor-name → hex-color mapping.

    Vendors are sorted alphabetically so the same set always gets the same
    colors regardless of evaluation order.
    """
    vendor_names = sorted({
        e.get("supplier_name", "Unknown") for e in evaluations
    })
    return {
        name: _VENDOR_PALETTE[i % len(_VENDOR_PALETTE)]
        for i, name in enumerate(vendor_names)
    }


def render_metrics_dashboard(comparison: dict, evaluations: list):
    """Render the metrics dashboard with charts for each criterion."""
    st.subheader("📊 Metrics Dashboard")
    st.markdown("Visual comparison of vendor performance across all evaluation criteria.")

    if not evaluations:
        st.warning("No evaluations available to display.")
        return

    if not PLOTLY_AVAILABLE:
        st.warning("📊 Plotly is not installed. Install it with `pip install plotly` for interactive charts.")
        _render_basic_metrics_dashboard(comparison, evaluations)
        return

    # Get all criteria from first evaluation
    criteria = []
    if evaluations[0].get("criterion_scores"):
        criteria = evaluations[0]["criterion_scores"]

    if not criteria:
        st.warning("No criteria scores available.")
        return

    # Build a single vendor→color map shared by every chart
    vendor_color_map = _build_vendor_color_map(evaluations)

    # Overall vendor comparison bar chart (total scores)
    st.markdown("### 🏆 Overall Vendor Performance")
    _render_overall_comparison_bar(evaluations, vendor_color_map)

    st.markdown("---")
    st.markdown("### 📈 Performance by Criterion")
    st.markdown("Each chart shows how vendor scores compare for a specific evaluation criterion. "
                "Taller bars indicate higher scores.")

    # Create bar charts for each criterion
    num_criteria = len(criteria)
    cols_per_row = 2

    for i in range(0, num_criteria, cols_per_row):
        cols = st.columns(cols_per_row)

        for j in range(cols_per_row):
            criterion_idx = i + j
            if criterion_idx >= num_criteria:
                break

            criterion = criteria[criterion_idx]
            criterion_id = criterion.get("criterion_id", f"C-{criterion_idx + 1}")
            criterion_name = criterion.get("criterion_name", f"Criterion {criterion_idx + 1}")
            criterion_weight = criterion.get("weight", 0)

            with cols[j]:
                _render_criterion_bar_chart(evaluations, criterion_id, criterion_name, criterion_weight, vendor_color_map)

    # Vendor recommendation section
    st.markdown("---")
    st.markdown("### 💡 Vendor Recommendations by Criterion")
    _render_criterion_recommendations(comparison, evaluations)


def _render_overall_comparison_bar(evaluations: list, vendor_color_map: dict[str, str]):
    """Render bar chart showing overall vendor comparison with consistent vendor colors."""
    vendor_names = []
    total_scores = []
    grades = []

    for eval_result in evaluations:
        vendor_name = eval_result.get("supplier_name", "Unknown")
        total_score = eval_result.get("total_score", 0)
        grade = eval_result.get("grade", "N/A")
        vendor_names.append(vendor_name)
        total_scores.append(total_score)
        grades.append(grade)

    # Sort by score descending
    sorted_data = sorted(zip(vendor_names, total_scores, grades), key=lambda x: x[1], reverse=True)
    vendor_names, total_scores, grades = zip(*sorted_data) if sorted_data else ([], [], [])

    # Assign consistent colors per vendor
    bar_colors = [vendor_color_map.get(v, "#4F46E5") for v in vendor_names]

    fig = go.Figure(go.Bar(
        x=list(vendor_names),
        y=list(total_scores),
        marker_color=bar_colors,
        text=[f"{s:.1f} ({g})" for s, g in zip(total_scores, grades)],
        textposition='outside',
        hovertemplate="<b>%{x}</b><br>Score: %{y:.1f}<extra></extra>",
    ))

    fig.update_layout(
        title="Total Score Comparison",
        showlegend=False,
        xaxis_title="Vendor",
        yaxis_title="Total Score",
        yaxis_range=[0, 105],
        margin=dict(t=50, b=50, l=50, r=20),
        height=400,
    )

    st.plotly_chart(fig, use_container_width=True)


def _render_criterion_bar_chart(
    evaluations: list,
    criterion_id: str,
    criterion_name: str,
    weight: float,
    vendor_color_map: dict[str, str],
):
    """Render a bar chart for a specific criterion with consistent vendor colors.

    Looks up scores by ``criterion_id`` so results match text exactly.
    """
    vendor_names = []
    scores = []

    for eval_result in evaluations:
        vendor_name = eval_result.get("supplier_name", "Unknown")
        score_map = _build_criterion_score_map(eval_result)
        cs = score_map.get(criterion_id, {})
        score = cs.get("raw_score", 0)

        vendor_names.append(vendor_name)
        scores.append(score)

    # Sort by score descending
    sorted_data = sorted(zip(vendor_names, scores), key=lambda x: x[1], reverse=True)
    vendor_names, scores = zip(*sorted_data) if sorted_data else ([], [])

    best_vendor = vendor_names[0] if vendor_names else "N/A"
    best_score = scores[0] if scores else 0

    bar_colors = [vendor_color_map.get(v, "#4F46E5") for v in vendor_names]

    fig = go.Figure(go.Bar(
        x=list(vendor_names),
        y=list(scores),
        marker_color=bar_colors,
        text=[f"{s:.1f}" for s in scores],
        textposition='outside',
        hovertemplate="<b>%{x}</b><br>Score: %{y:.1f}/100<extra></extra>",
    ))

    fig.update_layout(
        title=f"{criterion_name}<br><sup>Weight: {weight:.1f}% | Best: {best_vendor} ({best_score:.1f})</sup>",
        showlegend=False,
        xaxis_title="",
        yaxis_title="Score",
        yaxis_range=[0, 105],
        margin=dict(t=60, b=30, l=40, r=10),
        height=300,
        xaxis_tickangle=-45 if len(vendor_names) > 3 else 0,
    )

    st.plotly_chart(fig, use_container_width=True, key=f"bar_{criterion_id}")


def _render_criterion_recommendations(comparison: dict, evaluations: list):
    """Render recommendations for each criterion based on vendor performance."""
    criterion_comparisons = comparison.get("criterion_comparisons", [])

    if not criterion_comparisons:
        # Fall back to generating recommendations from evaluations
        if not evaluations or not evaluations[0].get("criterion_scores"):
            return

        criteria = evaluations[0]["criterion_scores"]
        for criterion in criteria:
            criterion_id = criterion.get("criterion_id", "")
            criterion_name = criterion.get("criterion_name", criterion_id)

            # Find best vendor for this criterion using criterion_id lookup
            best_vendor = None
            best_score = -1
            all_scores = []

            for eval_result in evaluations:
                vendor_name = eval_result.get("supplier_name", "Unknown")
                score_map = _build_criterion_score_map(eval_result)
                cs = score_map.get(criterion_id, {})
                score = cs.get("raw_score", 0)
                all_scores.append((vendor_name, score))
                if score > best_score:
                    best_score = score
                    best_vendor = vendor_name

            if best_vendor:
                with st.expander(f"**{criterion_name}** - Recommended: {best_vendor}"):
                    st.markdown(f"**Best Performer:** {best_vendor} (Score: {best_score:.1f}/100)")

                    # Show all vendor scores
                    st.markdown("**All Vendors:**")
                    for vendor, score in sorted(all_scores, key=lambda x: x[1], reverse=True):
                        icon = "🥇" if vendor == best_vendor else "📊"
                        st.markdown(f"  {icon} {vendor}: {score:.1f}/100")
    else:
        # Use the comparison agent's criterion comparisons
        for cc in criterion_comparisons:
            criterion_name = cc.get("criterion_name", "Unknown")
            best_vendor = cc.get("best_vendor", "N/A")
            worst_vendor = cc.get("worst_vendor", "N/A")
            score_range = cc.get("score_range", "N/A")
            insights = cc.get("insights", "")
            weight = cc.get("weight", 0)

            with st.expander(f"**{criterion_name}** (Weight: {weight:.1f}%) - Recommended: {best_vendor}"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("🥇 Best", best_vendor)
                with col2:
                    st.metric("📉 Lowest", worst_vendor)
                with col3:
                    st.metric("📊 Score Range", score_range)

                if insights:
                    st.markdown(f"**Why choose {best_vendor}:** {insights}")


def _render_basic_metrics_dashboard(comparison: dict, evaluations: list):
    """Render a basic metrics dashboard without plotly charts."""
    st.markdown("### Vendor Performance Summary")

    # Overall comparison table — sorted by score (single source of truth)
    st.markdown("#### Total Scores")
    for eval_result in sorted(evaluations, key=lambda x: x.get("total_score", 0), reverse=True):
        vendor_name = eval_result.get("supplier_name", "Unknown")
        total_score = eval_result.get("total_score", 0)
        grade = eval_result.get("grade", "N/A")

        st.markdown(f"**{vendor_name}**: {total_score:.1f}/100 ({grade})")
        st.progress(min(total_score / 100, 1.0))

    st.markdown("---")
    st.markdown("#### Criterion Scores")

    if evaluations and evaluations[0].get("criterion_scores"):
        criteria = evaluations[0]["criterion_scores"]

        for criterion in criteria:
            criterion_id = criterion.get("criterion_id", "")
            criterion_name = criterion.get("criterion_name", criterion_id)
            criterion_weight = criterion.get("weight", 0)

            st.markdown(f"**{criterion_name}** (Weight: {criterion_weight:.1f}%)")

            for eval_result in evaluations:
                vendor_name = eval_result.get("supplier_name", "Unknown")
                score_map = _build_criterion_score_map(eval_result)
                cs = score_map.get(criterion_id, {})
                score = cs.get("raw_score", 0)
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.progress(min(score / 100, 1.0))
                with col2:
                    st.write(f"{vendor_name[:15]}: {score:.1f}")


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
        overall_confidence = eval_result.get("overall_confidence", 0.8)

        conf_badge = "🟢" if overall_confidence >= 0.9 else "🟡" if overall_confidence >= 0.7 else "🔴"
        with st.expander(f"**{vendor_name}** - Score: {total_score:.1f} ({grade}) {conf_badge} {overall_confidence:.0%}", expanded=i==0):
            # Score summary
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Score", f"{total_score:.1f}")
            with col2:
                st.metric("Grade", grade)
            with col3:
                st.metric("File", proposal_file[:25] + "..." if len(proposal_file) > 25 else proposal_file)
            with col4:
                conf_label = "High" if overall_confidence >= 0.9 else "Good" if overall_confidence >= 0.7 else "Low"
                st.metric("Confidence", f"{overall_confidence:.0%}", delta=conf_label,
                          delta_color="normal" if overall_confidence >= 0.7 else "inverse")

            # Criterion scores with justifications
            st.markdown("#### Criterion Scores & Justifications")
            criterion_scores = eval_result.get("criterion_scores", [])
            for cs in criterion_scores:
                score_pct = cs.get("raw_score", 0)
                bar_color = "🟢" if score_pct >= 80 else "🟡" if score_pct >= 60 else "🟠" if score_pct >= 40 else "🔴"
                criterion_name = cs.get('criterion_name', 'Unknown')
                weighted_score = cs.get('weighted_score', 0)
                justification = cs.get('justification', '')
                cs_confidence = cs.get('confidence', 0.8)
                cs_iterations = cs.get('reasoning_iterations', 1)

                # Confidence indicator
                conf_icon = "🟢" if cs_confidence >= 0.9 else "🟡" if cs_confidence >= 0.7 else "🔴"
                re_reason_tag = " 🔄" if cs_iterations > 1 else ""

                # Show criterion score with expandable justification
                with st.container():
                    st.markdown(
                        f"{bar_color} **{criterion_name}**: {score_pct:.1f}/100 "
                        f"(weighted: {weighted_score:.2f}) — "
                        f"{conf_icon} {cs_confidence:.0%}{re_reason_tag}"
                    )
                    if justification:
                        with st.expander("📝 View Justification", expanded=False):
                            st.markdown(justification)

                    # Show strengths and gaps for this criterion if available
                    strengths = cs.get('strengths', [])
                    gaps = cs.get('gaps', [])
                    if strengths or gaps:
                        col_s, col_g = st.columns(2)
                        with col_s:
                            if strengths:
                                st.markdown("**Strengths:**")
                                for s in strengths[:3]:
                                    st.markdown(f"  ✅ {s}")
                        with col_g:
                            if gaps:
                                st.markdown("**Gaps:**")
                                for g in gaps[:3]:
                                    st.markdown(f"  ⚠️ {g}")
                    st.markdown("---")

            # Overall Strengths and weaknesses
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### Overall Strengths")
                for s in eval_result.get("overall_strengths", []):
                    st.markdown(f"✅ {s}")
            with col2:
                st.markdown("#### Overall Weaknesses")
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

    # Build the set of criteria from the first evaluation (the canonical list)
    first_criteria = evaluations[0].get("criterion_scores", [])
    if not first_criteria:
        st.warning("No criteria scores available.")
        return

    # Create comparison table data — lookup by criterion_id
    # Show raw scores per criterion with weight column so users understand the total
    table_data = []
    for criterion in first_criteria:
        cid = criterion.get("criterion_id", "")
        criterion_name = criterion.get("criterion_name", cid)
        weight = criterion.get("weight", 0)
        row = {"Criterion": criterion_name, "Weight": f"{weight:.1f}%"}
        for eval_result in evaluations:
            vendor_name = eval_result.get("supplier_name", "Unknown")[:15]
            score_map = _build_criterion_score_map(eval_result)
            cs = score_map.get(cid, {})
            raw = cs.get("raw_score", 0) or 0
            criterion_weight = cs.get("weight", 0) or 0
            weighted = round((raw * criterion_weight) / 100, 2)
            row[vendor_name] = f"{raw:.1f} ({weighted:.1f})"
        table_data.append(row)

    # Add total row — compute weighted totals from raw data in code
    total_row = {"Criterion": "**TOTAL SCORE**", "Weight": "100%"}
    for eval_result in evaluations:
        vendor_name = eval_result.get("supplier_name", "Unknown")[:15]
        # Recompute total from criterion scores for accuracy
        computed_total = 0.0
        for cs in eval_result.get("criterion_scores", []):
            raw = cs.get("raw_score", 0) or 0
            criterion_weight = cs.get("weight", 0) or 0
            computed_total += (raw * criterion_weight) / 100
        computed_total = round(computed_total, 1)
        total_row[vendor_name] = f"**{computed_total}**"
    table_data.append(total_row)

    st.caption("Scores shown as: Raw Score (Weighted Score). Total is the sum of weighted scores.")
    st.table(table_data)


def render_export_options(comparison: dict, evaluations: list):
    """Render export options for reports."""
    st.subheader("📥 Export Reports")

    # Full Analysis Report (with comparison)
    st.markdown("### 📑 Full Analysis Report")
    st.markdown("Complete report including comparison, rankings, and all vendor details.")

    if comparison and evaluations:
        full_report = generate_full_analysis_report(comparison, evaluations)
        if full_report:
            st.download_button(
                label="📑 Download Full Analysis Report (Word)",
                data=full_report,
                file_name="rfp_full_analysis_report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                key="full_analysis_report"
            )
        else:
            st.caption("Word export not available. Install python-docx with: pip install python-docx")

    st.markdown("---")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### 📊 CSV Comparison")
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
        st.markdown("### 📋 JSON Data")
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
        st.markdown("### 📄 Individual Reports")
        st.caption("Detailed Word report for each vendor")

    # Individual vendor reports in a separate section
    st.markdown("### 📄 Individual Vendor Reports (Word)")
    st.markdown("Detailed reports with criterion justifications for each vendor.")

    vendor_cols = st.columns(min(len(evaluations), 4))
    for i, eval_result in enumerate(evaluations):
        col_idx = i % min(len(evaluations), 4)
        with vendor_cols[col_idx]:
            vendor_name = eval_result.get("supplier_name", f"Vendor_{i+1}").replace(" ", "_")
            word_doc = generate_word_report(eval_result)
            if word_doc:
                st.download_button(
                    label=f"📄 {vendor_name[:20]}",
                    data=word_doc,
                    file_name=f"report_{vendor_name}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    key=f"word_{i}"
                )
            else:
                st.caption(f"Not available for {vendor_name[:15]}")
