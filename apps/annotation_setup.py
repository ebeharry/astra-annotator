"""Annotation Setup page."""

import json

import streamlit as st

from apps.context_formatting import render_claim_context
from core.database import DatabaseManager
from core.managers.annotation import AnnotationManager
from core.managers.experiment import ExperimentManager


def show_annotation_setup():
    """Display the annotation setup interface."""
    st.header("⚙️ Annotation Setup")

    # Initialize managers
    db = DatabaseManager(st.session_state.db_path)
    annotation_manager = AnnotationManager(db)
    experiment_manager = ExperimentManager(db)

    # Tabs for different sections
    tab1, tab2, tab3 = st.tabs(
        ["📋 View Annotation Runs", "➕ Create Annotation Run", "👁️ Preview Interface"]
    )

    with tab1:
        show_annotation_runs_list(annotation_manager)

    with tab2:
        show_create_annotation_run(annotation_manager, experiment_manager, db)

    with tab3:
        show_preview_interface(annotation_manager, db)


def show_annotation_runs_list(annotation_manager: AnnotationManager):
    """Display list of annotation runs."""
    st.subheader("Current Annotation Runs")

    annotation_runs = annotation_manager.get_annotation_runs()

    if not annotation_runs:
        st.info("No annotation runs found. Create an annotation run to get started!")
        return

    # Display annotation runs
    for run in annotation_runs:
        with st.expander(f"📊 {run['name']} ({run['status']})"):
            col1, col2 = st.columns(2)

            with col1:
                st.write(f"**Experiment:** {run['experiment_name']}")
                st.write(f"**Status:** {run['status']}")
                st.write(f"**Description:** {run['description'] or 'No description'}")
                st.write(f"**Created:** {run['created_at']}")
                st.write(f"**Response Ordering:** {run['response_ordering']}")

                # Show filters
                if run["filter_models"]:
                    models = json.loads(run["filter_models"])
                    st.write(f"**Model Filter:** {', '.join(models)}")

                if run["filter_conditions"]:
                    conditions = json.loads(run["filter_conditions"])
                    st.write(f"**Condition Filter:** {', '.join(conditions)}")

            with col2:
                # Get detailed info
                run_details = annotation_manager.get_annotation_run_details(run["id"])

                st.write(f"**Assessment Categories:** {len(run_details['assessment_categories'])}")
                st.write(f"**Assigned Labelers:** {len(run_details['assigned_labelers'])}")
                st.write(f"**Eligible Responses:** {run_details['eligible_responses_count']}")

                # Show assessment categories
                if run_details["assessment_categories"]:
                    st.write("**Categories:**")
                    for cat in run_details["assessment_categories"]:
                        st.write(f"• {cat['name']} ({cat['type']})")

                # Show assigned labelers
                if run_details["assigned_labelers"]:
                    st.write(f"**Labelers:** {', '.join(run_details['assigned_labelers'])}")


def show_create_annotation_run(
    annotation_manager: AnnotationManager,
    experiment_manager: ExperimentManager,
    db: DatabaseManager,
):
    """Display form to create new annotation runs."""
    st.subheader("Create New Annotation Run")

    # Get completed experiments
    experiments = experiment_manager.get_experiments()
    completed_experiments = [exp for exp in experiments if exp["status"] == "completed"]

    if not completed_experiments:
        st.warning("⚠️ No completed experiments available. Please complete an experiment first.")
        return

    with st.form("create_annotation_run_form"):
        # Basic annotation run info
        st.write("**1. Annotation Run Details:**")
        run_name = st.text_input("Annotation Run Name*")
        run_description = st.text_area("Description")

        # Experiment selection
        st.write("**2. Select Experiment:**")
        selected_experiment = st.selectbox(
            "Experiment",
            options=[(exp["id"], exp["name"]) for exp in completed_experiments],
            format_func=lambda x: x[1],
        )

        if selected_experiment:
            exp_id = selected_experiment[0]
            experiment_details = experiment_manager.get_experiment_details(exp_id)

            # Show experiment info
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(
                    "Total Responses",
                    len([r for r in experiment_details["responses"] if r["status"] == "completed"]),
                )
            with col2:
                st.metric("Models", len(experiment_details["models"]))
            with col3:
                unique_conditions = {p.get("condition_name") for p in experiment_details["prompts"]}
                st.metric("Conditions", len(unique_conditions))

        # Response filtering
        st.write("**3. Response Filtering:**")

        # Model filter
        st.write("**Models to Include:**")
        if selected_experiment:
            available_models = experiment_details["models"]
            selected_models = []

            model_selection = st.radio(
                "Model Selection", ["Include All Models", "Select Specific Models"], horizontal=True
            )

            if model_selection == "Select Specific Models":
                selected_models = st.multiselect("Select Models", available_models)
            else:
                selected_models = available_models

        # Condition filter
        st.write("**Conditions to Include:**")
        if selected_experiment:
            available_conditions = list(
                {p.get("condition_name") for p in experiment_details["prompts"]}
            )
            selected_conditions = []

            condition_selection = st.radio(
                "Condition Selection",
                ["Include All Conditions", "Select Specific Conditions"],
                horizontal=True,
            )

            if condition_selection == "Select Specific Conditions":
                selected_conditions = st.multiselect("Select Conditions", available_conditions)
            else:
                selected_conditions = available_conditions

        # Response ordering
        st.write("**4. Response Ordering:**")
        response_ordering = st.radio(
            "How should responses be presented to labelers?",
            ["sequential", "randomized"],
            format_func=lambda x: "Sequential (by condition/group)"
            if x == "sequential"
            else "Randomized",
            horizontal=True,
        )

        # Assessment categories
        st.write("**5. Assessment Categories:**")
        st.write("Define the categories that labelers will use to evaluate responses:")

        # Initialize session state for categories
        if "assessment_categories" not in st.session_state:
            st.session_state.assessment_categories = []

        # Category input
        with st.container():
            col1, col2, col3 = st.columns([2, 1, 1])

            with col1:
                new_cat_name = st.text_input("Category Name", key="new_cat_name")

            with col2:
                new_cat_type = st.selectbox(
                    "Type", ["categorical", "binary", "text"], key="new_cat_type"
                )

            with col3:
                if st.form_submit_button("Add Category", type="secondary"):
                    if new_cat_name:
                        # Handle possible values based on type
                        possible_values = None
                        if new_cat_type == "binary":
                            possible_values = ["Yes", "No"]
                        elif new_cat_type == "categorical":
                            # This will be handled in the next step
                            possible_values = []

                        st.session_state.assessment_categories.append(
                            {
                                "name": new_cat_name,
                                "type": new_cat_type,
                                "possible_values": possible_values,
                                "guidelines": "",
                            }
                        )
                        st.rerun()

        # Show current categories and allow editing
        if st.session_state.assessment_categories:
            st.write("**Current Assessment Categories:**")

            for i, category in enumerate(st.session_state.assessment_categories):
                with st.container():
                    col1, col2, col3 = st.columns([2, 2, 1])

                    with col1:
                        st.write(f"**{category['name']}** ({category['type']})")

                        # Handle possible values for categorical
                        if category["type"] == "categorical" and isinstance(
                            category["possible_values"], list
                        ):
                            values_text = st.text_input(
                                "Possible Values (comma-separated)",
                                value=", ".join(category["possible_values"])
                                if category["possible_values"]
                                else "",
                                key=f"cat_values_{i}",
                            )
                            if values_text:
                                category["possible_values"] = [
                                    v.strip() for v in values_text.split(",") if v.strip()
                                ]
                        elif category["type"] == "binary":
                            st.write("Possible Values: Yes, No")

                    with col2:
                        category["guidelines"] = st.text_area(
                            "Guidelines",
                            value=category["guidelines"],
                            height=80,
                            key=f"cat_guidelines_{i}",
                        )

                    with col3:
                        if st.button("Remove", key=f"remove_cat_{i}"):
                            st.session_state.assessment_categories.pop(i)
                            st.rerun()

        # Labeler assignments
        st.write("**6. Labeler Assignments:**")
        st.write("Enter the initials of labelers who will participate in this annotation run:")

        if "labeler_initials" not in st.session_state:
            st.session_state.labeler_initials = []

        # Add labeler
        col1, col2 = st.columns([3, 1])
        with col1:
            new_labeler = st.text_input("Labeler Initials", key="new_labeler")
        with col2:
            if st.form_submit_button("Add Labeler", type="secondary"):
                if new_labeler and new_labeler not in st.session_state.labeler_initials:
                    st.session_state.labeler_initials.append(new_labeler)
                    st.rerun()

        # Show current labelers
        if st.session_state.labeler_initials:
            st.write("**Assigned Labelers:**")
            for i, labeler in enumerate(st.session_state.labeler_initials):
                col1, col2 = st.columns([3, 1])
                col1.write(f"• {labeler}")
                if col2.button("Remove", key=f"remove_labeler_{i}"):
                    st.session_state.labeler_initials.pop(i)
                    st.rerun()

        # Guidelines
        st.write("**7. General Guidelines:**")
        guidelines = st.text_area(
            "Instructions for Labelers",
            height=150,
            placeholder="Provide general instructions that will be shown to labelers...",
        )

        # Submit button
        submitted = st.form_submit_button("Create Annotation Run", type="primary")

        if submitted:
            # Validation
            if not run_name:
                st.error("Annotation run name is required")
                return

            if not selected_experiment:
                st.error("Please select an experiment")
                return

            if not st.session_state.assessment_categories:
                st.error("At least one assessment category is required")
                return

            if not st.session_state.labeler_initials:
                st.error("At least one labeler must be assigned")
                return

            try:
                # Create annotation run
                annotation_run_id = annotation_manager.create_annotation_run(
                    experiment_id=exp_id,
                    name=run_name,
                    description=run_description,
                    guidelines=guidelines,
                    response_ordering=response_ordering,
                    filter_models=selected_models
                    if model_selection == "Select Specific Models"
                    else None,
                    filter_conditions=selected_conditions
                    if condition_selection == "Select Specific Conditions"
                    else None,
                )

                # Create assessment categories
                for i, category in enumerate(st.session_state.assessment_categories):
                    annotation_manager.create_assessment_category(
                        annotation_run_id=annotation_run_id,
                        name=category["name"],
                        category_type=category["type"],
                        possible_values=category["possible_values"]
                        if category["type"] != "text"
                        else None,
                        guidelines=category["guidelines"],
                        display_order=i,
                    )

                # Assign labelers
                for labeler in st.session_state.labeler_initials:
                    annotation_manager.assign_labeler(annotation_run_id, labeler)

                st.success(f"✅ Annotation run '{run_name}' created successfully!")
                st.write(f"• {len(st.session_state.assessment_categories)} assessment categories")
                st.write(f"• {len(st.session_state.labeler_initials)} labelers assigned")

                # Clear session state
                st.session_state.assessment_categories = []
                st.session_state.labeler_initials = []

                st.rerun()

            except Exception as e:
                st.error(f"Error creating annotation run: {e}")


def show_preview_interface(annotation_manager: AnnotationManager, db: DatabaseManager):
    """Display preview of the annotation interface."""
    st.subheader("Preview Annotation Interface")

    annotation_runs = annotation_manager.get_annotation_runs()

    if not annotation_runs:
        st.info("No annotation runs available for preview")
        return

    # Select annotation run to preview
    selected_run = st.selectbox(
        "Select Annotation Run to Preview",
        options=[(run["id"], run["name"]) for run in annotation_runs],
        format_func=lambda x: x[1],
    )

    if selected_run:
        run_id = selected_run[0]
        run_details = annotation_manager.get_annotation_run_details(run_id)

        st.write(f"**Previewing:** {run_details['name']}")
        st.write(f"**Guidelines:** {run_details['guidelines']}")

        # Get sample response
        eligible_responses = annotation_manager.get_eligible_responses(run_id)

        if not eligible_responses:
            st.warning("No eligible responses found for this annotation run")
            return

        # Show sample response
        sample_response = eligible_responses[0]

        # Get the prompt content
        with db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT content FROM prompts WHERE id = ?", (sample_response["prompt_id"],)
            )
            prompt_content = cursor.fetchone()["content"]

        st.write("**Sample Claim:**")

        with st.container():
            with st.expander("📄 Context (ground truth, prior turns, user question)", expanded=True):
                render_claim_context(prompt_content)

            st.markdown("**Statement Under Review:**")
            st.success(sample_response["response_text"] or "No response generated")

        # Show assessment categories
        st.write("**Assessment Categories:**")
        st.info("For each deception type below, choose the option that best describes the statement, based on the context above.")

        for category in run_details["assessment_categories"]:
            st.write(f"**{category['name']}**")
            if category["guidelines"]:
                st.markdown(category["guidelines"])

            if category["type"] == "categorical":
                st.radio(
                    f"Select {category['name']}",
                    options=category["possible_values"],
                    key=f"preview_{category['id']}",
                    disabled=True,
                )
            elif category["type"] == "binary":
                st.radio(
                    f"Select {category['name']}",
                    options=category["possible_values"],
                    key=f"preview_{category['id']}",
                    disabled=True,
                )
            else:  # text
                st.text_area(
                    f"Enter {category['name']}", key=f"preview_{category['id']}", disabled=True
                )

            # Justification (optional)
            st.text_area(
                "Justification (optional)", key=f"preview_just_{category['id']}", disabled=True
            )

            st.divider()

        st.info("👆 This is how the annotation interface will appear to labelers")
