"""Labeling Interface page."""

import random
from typing import Dict, List

import streamlit as st

from apps.context_formatting import render_claim_context
from core.database import DatabaseManager
from core.managers.annotation import AnnotationManager


def show_labeling_interface():
    """Display the labeling interface."""
    st.header("🏷️ Labeling Interface")

    # Initialize managers
    db = DatabaseManager(st.session_state.db_path)
    annotation_manager = AnnotationManager(db)

    # Get available annotation runs
    annotation_runs = annotation_manager.get_annotation_runs()
    active_runs = [run for run in annotation_runs if run["status"] == "active"]

    if not active_runs:
        st.warning("⚠️ No active annotation runs available. Please check Annotation Setup.")
        st.info("💡 Annotation runs must be set to 'active' status to appear here.")
        return

    # Labeler authentication
    if "labeler_initials" not in st.session_state:
        st.session_state.labeler_initials = ""

    if not st.session_state.labeler_initials:
        show_labeler_login(active_runs, annotation_manager)
        return

    # Show labeling interface
    show_annotation_interface(annotation_manager, db)


def show_labeler_login(active_runs: List[Dict], annotation_manager: AnnotationManager):
    """Display labeler login interface."""
    st.subheader("👤 Labeler Authentication")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.write("**Select Annotation Run:**")
        selected_run = st.selectbox(
            "Annotation Run",
            options=[(run["id"], run["name"]) for run in active_runs],
            format_func=lambda x: x[1],
            key="login_run_selection",
        )

        if selected_run:
            run_id = selected_run[0]
            run_details = annotation_manager.get_annotation_run_details(run_id)

            st.write(f"**Description:** {run_details['description'] or 'No description'}")
            st.write(f"**Guidelines:** {run_details['guidelines'] or 'No specific guidelines'}")

            # Show assigned labelers
            assigned_labelers = run_details["assigned_labelers"]
            if assigned_labelers:
                st.write(f"**Assigned Labelers:** {', '.join(assigned_labelers)}")

        st.write("**Enter Your Initials:**")
        labeler_initials = st.text_input(
            "Labeler Initials", placeholder="e.g., JD, MS, etc.", key="labeler_initials_input"
        )

    with col2:
        st.write("**Instructions:**")
        st.info("""
        1. Select your annotation run
        2. Enter your assigned initials
        3. Click Start Labeling
        4. Complete assessments for each response
        """)

    if st.button("🚀 Start Labeling", type="primary"):
        if not labeler_initials:
            st.error("Please enter your initials")
            return

        if not selected_run:
            st.error("Please select an annotation run")
            return

        # Verify labeler is assigned
        run_details = annotation_manager.get_annotation_run_details(selected_run[0])
        if labeler_initials not in run_details["assigned_labelers"]:
            st.error(f"Initials '{labeler_initials}' are not assigned to this annotation run")
            st.info("Please contact the study coordinator if you believe this is an error")
            return

        # Set session state
        st.session_state.labeler_initials = labeler_initials
        st.session_state.selected_annotation_run = selected_run[0]
        st.session_state.current_response_index = 0

        st.rerun()


def show_annotation_interface(annotation_manager: AnnotationManager, db: DatabaseManager):
    """Display the main annotation interface."""
    run_id = st.session_state.selected_annotation_run
    labeler_initials = st.session_state.labeler_initials

    # Get run details
    run_details = annotation_manager.get_annotation_run_details(run_id)

    # Get eligible responses
    eligible_responses = annotation_manager.get_eligible_responses(run_id)

    if not eligible_responses:
        st.warning("No responses available for annotation in this run")
        return

    # Order responses based on run settings
    if run_details["response_ordering"] == "randomized":
        if "randomized_response_order" not in st.session_state:
            # Create consistent random order for this labeler/run combination
            random.seed(f"{run_id}_{labeler_initials}")
            st.session_state.randomized_response_order = eligible_responses.copy()
            random.shuffle(st.session_state.randomized_response_order)
        ordered_responses = st.session_state.randomized_response_order
    else:
        # Sequential ordering
        ordered_responses = sorted(
            eligible_responses,
            key=lambda x: (x.get("condition_name", ""), x.get("group_name", ""), x["id"]),
        )

    # Get progress
    progress = annotation_manager.get_labeler_progress(run_id, labeler_initials)
    total_responses = len(ordered_responses)

    # Header with progress
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

    with col1:
        st.write(f"**Labeler:** {labeler_initials} | **Run:** {run_details['name']}")

    with col2:
        st.metric("Progress", f"{progress['completed_responses']}/{total_responses}")

    with col3:
        completion_pct = progress["completion_percentage"]
        st.metric("Complete", f"{completion_pct:.1f}%")

    with col4:
        if st.button("🏠 Main Menu"):
            # Clear labeler session
            for key in [
                "labeler_initials",
                "selected_annotation_run",
                "current_response_index",
                "randomized_response_order",
            ]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

    # Progress bar
    st.progress(completion_pct / 100)

    st.divider()

    # Navigation
    current_index = st.session_state.get("current_response_index", 0)
    current_index = max(0, min(current_index, total_responses - 1))

    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if st.button("⬅️ Previous", disabled=current_index == 0):
            st.session_state.current_response_index = current_index - 1
            st.rerun()

    with col2:
        # Jump to specific response
        new_index = st.selectbox(
            "Response",
            range(total_responses),
            index=current_index,
            format_func=lambda x: f"Response {x + 1} of {total_responses}",
            key="response_selector",
        )
        if new_index != current_index:
            st.session_state.current_response_index = new_index
            st.rerun()

    with col3:
        if st.button("➡️ Next", disabled=current_index == total_responses - 1):
            st.session_state.current_response_index = current_index + 1
            st.rerun()

    st.divider()

    # Current response
    current_response = ordered_responses[current_index]

    # Get prompt content
    with db.get_connection() as conn:
        cursor = conn.execute(
            "SELECT content FROM prompts WHERE id = ?", (current_response["prompt_id"],)
        )
        prompt_result = cursor.fetchone()
        prompt_content = prompt_result["content"] if prompt_result else "Prompt not found"

    # Display prompt-response pair
    st.subheader(f"Response {current_index + 1} of {total_responses}")

    # Show metadata (for context, not part of blind annotation)
    with st.expander("📋 Response Metadata", expanded=False):
        st.write(f"**Model:** {current_response['model']}")
        st.write(f"**Response ID:** {current_response['id']}")
        if current_response.get("condition_name"):
            st.write(f"**Condition:** {current_response['condition_name']}")

    # Display conversation
    st.write("**Claim to Evaluate:**")

    with st.container():
        with st.expander("📄 Context (ground truth, prior turns, user question)", expanded=True):
            render_claim_context(prompt_content)

        st.markdown("**Statement Under Review:**")
        response_text = current_response["response_text"] or "No response generated"
        st.success(response_text)

    st.divider()

    # Assessment categories
    st.subheader("📝 Assessment Categories")
    st.info("For each deception type below, choose the option that best describes the statement, based on the context above.")

    if run_details["guidelines"]:
        with st.expander("📖 General Guidelines"):
            st.write(run_details["guidelines"])

    # Get existing annotations for this response
    existing_annotations = {}
    for category in run_details["assessment_categories"]:
        annotation = annotation_manager.get_annotation_for_response(
            run_id, current_response["id"], category["id"], labeler_initials
        )
        if annotation:
            existing_annotations[category["id"]] = annotation

    # Assessment form
    with st.form(key="annotation_form"):
        annotations = {}

        for i, category in enumerate(run_details["assessment_categories"]):
            st.write(f"**{category['name']}**")

            if category["guidelines"]:
                st.markdown(category["guidelines"])

            # Get existing value
            existing_annotation = existing_annotations.get(category["id"])
            existing_value = existing_annotation["value"] if existing_annotation else None
            existing_justification = (
                existing_annotation["justification"] if existing_annotation else ""
            )

            # Input based on category type
            if category["type"] == "categorical":
                value = st.radio(
                    f"Select {category['name']}",
                    options=category["possible_values"],
                    index=category["possible_values"].index(existing_value)
                    if existing_value in category["possible_values"]
                    else 0,
                    key=f"cat_{category['id']}",
                )
            elif category["type"] == "binary":
                value = st.radio(
                    f"Select {category['name']}",
                    options=category["possible_values"],
                    index=category["possible_values"].index(existing_value)
                    if existing_value in category["possible_values"]
                    else 0,
                    key=f"bin_{category['id']}",
                )
            else:  # text
                value = st.text_area(
                    f"Enter {category['name']}",
                    value=existing_value or "",
                    key=f"text_{category['id']}",
                )

            # Justification
            justification = st.text_area(
                "Justification (optional)",
                value=existing_justification,
                key=f"just_{category['id']}",
                height=80,
            )

            annotations[category["id"]] = {"value": value, "justification": justification}

            if i < len(run_details["assessment_categories"]) - 1:
                st.divider()

        # Submit buttons
        col1, col2, col3 = st.columns([1, 1, 1])

        with col1:
            save_button = st.form_submit_button("💾 Save Annotations", type="primary")

        with col2:
            save_and_next = st.form_submit_button("💾➡️ Save & Next")

        with col3:
            # Show if all categories are filled
            all_filled = all(ann["value"] for ann in annotations.values())
            if all_filled:
                st.success("✅ All categories completed")
            else:
                st.warning("⚠️ Some categories incomplete")

        if save_button or save_and_next:
            # Validate required fields
            missing_categories = []
            for category in run_details["assessment_categories"]:
                if not annotations[category["id"]]["value"]:
                    missing_categories.append(category["name"])

            if missing_categories:
                st.error(
                    f"Please complete these required categories: {', '.join(missing_categories)}"
                )
            else:
                # Save annotations
                try:
                    for category_id, annotation in annotations.items():
                        annotation_manager.save_annotation(
                            annotation_run_id=run_id,
                            response_id=current_response["id"],
                            category_id=category_id,
                            labeler_initials=labeler_initials,
                            value=annotation["value"],
                            justification=annotation["justification"] or None,
                        )

                    st.success("✅ Annotations saved successfully!")

                    # Move to next response if requested
                    if save_and_next and current_index < total_responses - 1:
                        st.session_state.current_response_index = current_index + 1
                        st.rerun()
                    else:
                        # Just refresh to show updated progress
                        st.rerun()

                except Exception as e:
                    st.error(f"Error saving annotations: {e}")

    # Show completion status
    if progress["completed_responses"] == total_responses:
        st.balloons()
        st.success("🎉 Congratulations! You have completed all annotations for this run.")

        if st.button("🔄 Review Annotations"):
            st.session_state.current_response_index = 0
            st.rerun()
