"""Disagreement Review page.

Shows each response/category pair where labelers disagreed, rendered in the same
layout labelers see (context, statement, rubric), but read-only: for every rubric
option it shows which labelers chose it and the reason they gave, if any.
"""

from typing import Dict, List

import streamlit as st

from apps.context_formatting import render_claim_context
from apps.results_analysis import add_response_metadata, get_annotations_dataframe
from core.database import DatabaseManager
from core.managers.annotation import AnnotationManager


def show_disagreement_review():
    """Display the disagreement review interface."""
    st.header("🔍 Disagreement Review")

    db = DatabaseManager(st.session_state.db_path)
    annotation_manager = AnnotationManager(db)

    annotation_runs = annotation_manager.get_annotation_runs()
    if not annotation_runs:
        st.info("📋 No annotation runs found.")
        return

    run_options = [(run["id"], run["name"]) for run in annotation_runs]
    selected_run = st.selectbox(
        "Select Annotation Run",
        options=run_options,
        format_func=lambda x: x[1],
        key="disagreement_review_run_select",
    )
    if not selected_run:
        return

    run_id = selected_run[0]
    run_details = annotation_manager.get_annotation_run_details(run_id)

    annotations_df = get_annotations_dataframe(run_id, db)
    if annotations_df.empty:
        st.warning("No annotations found for this run")
        return

    annotations_with_metadata = add_response_metadata(annotations_df, run_id, db)

    cases = get_disagreement_cases(annotations_with_metadata, run_details)

    if not cases:
        st.success("✅ No disagreements found for this run.")
        return

    # Filters
    col1, col2 = st.columns(2)

    with col1:
        available_models = sorted({case["model"] for case in cases})
        selected_models = st.multiselect(
            "Models", options=available_models, default=available_models
        )

    with col2:
        available_categories = sorted({case["category"]["name"] for case in cases})
        selected_categories = st.multiselect(
            "Assessment Categories", options=available_categories, default=available_categories
        )

    filtered_cases = [
        case
        for case in cases
        if case["model"] in selected_models and case["category"]["name"] in selected_categories
    ]

    if not filtered_cases:
        st.warning("No disagreement cases match the current filters")
        return

    st.divider()

    # Case navigation
    total_cases = len(filtered_cases)
    nav_key = f"disagreement_case_index_{run_id}"
    current_index = st.session_state.get(nav_key, 0)
    current_index = max(0, min(current_index, total_cases - 1))

    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if st.button("⬅️ Previous", disabled=current_index == 0, key="disagreement_prev"):
            st.session_state[nav_key] = current_index - 1
            st.rerun()

    with col2:
        new_index = st.selectbox(
            "Case",
            range(total_cases),
            index=current_index,
            format_func=lambda x: (
                f"Case {x + 1} of {total_cases}: "
                f"{filtered_cases[x]['category']['name']} (Response {filtered_cases[x]['response_id']})"
            ),
            key="disagreement_case_selector",
        )
        if new_index != current_index:
            st.session_state[nav_key] = new_index
            st.rerun()

    with col3:
        if st.button("➡️ Next", disabled=current_index == total_cases - 1, key="disagreement_next"):
            st.session_state[nav_key] = current_index + 1
            st.rerun()

    st.divider()

    render_disagreement_case(filtered_cases[current_index], current_index, total_cases)


def get_disagreement_cases(annotations_with_metadata, run_details: Dict) -> List[Dict]:
    """Build one entry per (response, category) pair where labelers disagreed."""
    categories_by_id = {cat["id"]: cat for cat in run_details["assessment_categories"]}

    cases = []
    for (response_id, category_id), group in annotations_with_metadata.groupby(
        ["response_id", "category_id"]
    ):
        if group["value"].nunique() <= 1:
            continue

        category = categories_by_id.get(category_id)
        if category is None:
            continue

        first_row = group.iloc[0]
        labeler_answers = [
            {
                "labeler_initials": row["labeler_initials"],
                "value": row["value"],
                "justification": row.get("justification") or None,
            }
            for _, row in group.sort_values("labeler_initials").iterrows()
        ]

        cases.append(
            {
                "response_id": response_id,
                "category_id": category_id,
                "category": category,
                "model": first_row.get("model", "Unknown"),
                "condition_name": first_row.get("condition_name"),
                "prompt_content": first_row.get("prompt_content", ""),
                "response_text": first_row.get("response_text", ""),
                "labeler_answers": labeler_answers,
            }
        )

    cases.sort(key=lambda c: (c["response_id"], c["category"]["name"]))
    return cases


def render_disagreement_case(case: Dict, current_index: int, total_cases: int):
    """Render one disagreement case in the same layout labelers see, read-only."""
    st.subheader(f"Case {current_index + 1} of {total_cases}")

    with st.expander("📋 Response Metadata", expanded=False):
        st.write(f"**Model:** {case['model']}")
        st.write(f"**Response ID:** {case['response_id']}")
        if case.get("condition_name"):
            st.write(f"**Condition:** {case['condition_name']}")

    st.write("**Claim to Evaluate:**")

    with st.container():
        with st.expander("📄 Context (ground truth, prior turns, user question)", expanded=True):
            render_claim_context(case["prompt_content"])

        st.markdown("**Statement Under Review:**")
        st.success(case["response_text"] or "No response generated")

    st.divider()

    category = case["category"]
    st.subheader(f"📝 {category['name']}")

    if category["guidelines"]:
        st.markdown(category["guidelines"])

    st.write("**Labeler Disagreement:**")

    answers_by_value: Dict[str, List[Dict]] = {}
    for answer in case["labeler_answers"]:
        answers_by_value.setdefault(answer["value"], []).append(answer)

    possible_values = category.get("possible_values") or list(answers_by_value.keys())
    # Include any values labelers picked that aren't in the current rubric list.
    ordered_values = list(possible_values) + [
        value for value in answers_by_value if value not in possible_values
    ]

    for value in ordered_values:
        answers = answers_by_value.get(value)
        if not answers:
            continue

        labeler_list = ", ".join(a["labeler_initials"] for a in answers)
        st.markdown(f"**○ {value}** — chosen by: {labeler_list}")

        for answer in answers:
            reason = answer["justification"] or "*(no reason given)*"
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**{answer['labeler_initials']}:** {reason}")
