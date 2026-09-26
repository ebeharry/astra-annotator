"""Results Analysis page."""

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.database import DatabaseManager
from core.managers.annotation import AnnotationManager


def show_results_analysis():
    """Display the results analysis interface."""
    st.header("📊 Results Analysis")

    # Initialize managers
    db = DatabaseManager(st.session_state.db_path)
    annotation_manager = AnnotationManager(db)

    # Get annotation runs
    annotation_runs = annotation_manager.get_annotation_runs()

    if not annotation_runs:
        st.info("📋 No annotation runs found. Create annotation runs to see analysis.")
        return

    # Tabs for different analysis views
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📈 Overview", "🎯 Inter-Rater Reliability", "🔍 Detailed Analysis", "📊 Export Results"]
    )

    with tab1:
        show_overview_analysis(annotation_manager, annotation_runs)

    with tab2:
        show_reliability_analysis(annotation_manager, annotation_runs, db)

    with tab3:
        show_detailed_analysis(annotation_manager, annotation_runs, db)

    with tab4:
        show_export_results(annotation_manager, annotation_runs, db)


def show_overview_analysis(annotation_manager: AnnotationManager, annotation_runs: List[Dict]):
    """Display overview statistics."""
    st.subheader("📈 Annotation Progress Overview")

    # Calculate overall statistics
    total_runs = len(annotation_runs)
    completed_runs = len([r for r in annotation_runs if r["status"] == "completed"])
    active_runs = len([r for r in annotation_runs if r["status"] == "active"])

    # Display summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Runs", total_runs)

    with col2:
        st.metric("Active Runs", active_runs)

    with col3:
        st.metric("Completed Runs", completed_runs)

    with col4:
        completion_rate = (completed_runs / total_runs * 100) if total_runs > 0 else 0
        st.metric("Completion Rate", f"{completion_rate:.1f}%")

    st.divider()

    # Per-run progress details
    st.subheader("📋 Run-by-Run Progress")

    progress_data = []

    for run in annotation_runs:
        run_details = annotation_manager.get_annotation_run_details(run["id"])
        eligible_responses = annotation_manager.get_eligible_responses(run["id"])
        total_responses = len(eligible_responses)

        # Calculate progress per labeler
        labeler_progress = {}
        total_completed = 0

        for labeler in run_details["assigned_labelers"]:
            progress = annotation_manager.get_labeler_progress(run["id"], labeler)
            labeler_progress[labeler] = progress
            total_completed += progress["completed_responses"]

        # Calculate overall completion
        total_expected = total_responses * len(run_details["assigned_labelers"])
        overall_completion = (total_completed / total_expected * 100) if total_expected > 0 else 0

        progress_data.append(
            {
                "run": run,
                "run_details": run_details,
                "total_responses": total_responses,
                "labeler_progress": labeler_progress,
                "overall_completion": overall_completion,
                "total_expected": total_expected,
                "total_completed": total_completed,
            }
        )

    # Display progress for each run
    for data in progress_data:
        run = data["run"]

        with st.expander(f"📊 {run['name']} ({run['status']})"):
            col1, col2 = st.columns([2, 1])

            with col1:
                st.write(f"**Experiment:** {run['experiment_name']}")
                st.write(f"**Description:** {run['description'] or 'No description'}")
                st.write(f"**Total Responses:** {data['total_responses']}")
                st.write(f"**Assigned Labelers:** {len(data['labeler_progress'])}")

                # Progress bar
                st.progress(data["overall_completion"] / 100)
                st.write(
                    f"**Overall Progress:** {data['overall_completion']:.1f}% ({data['total_completed']}/{data['total_expected']})"
                )

            with col2:
                # Labeler-specific progress
                st.write("**Progress by Labeler:**")
                for labeler, progress in data["labeler_progress"].items():
                    pct = progress["completion_percentage"]
                    completed = progress["completed_responses"]
                    total = progress["total_responses"]

                    if pct == 100:
                        st.success(f"✅ {labeler}: {completed}/{total} ({pct:.1f}%)")
                    elif pct > 0:
                        st.warning(f"🔄 {labeler}: {completed}/{total} ({pct:.1f}%)")
                    else:
                        st.error(f"⏳ {labeler}: {completed}/{total} ({pct:.1f}%)")


def show_reliability_analysis(
    annotation_manager: AnnotationManager, annotation_runs: List[Dict], db: DatabaseManager
):
    """Display inter-rater reliability analysis."""
    st.subheader("🎯 Inter-Rater Reliability Analysis")

    # Select annotation run for analysis
    run_options = [(run["id"], run["name"]) for run in annotation_runs]
    selected_run = st.selectbox(
        "Select Annotation Run for Reliability Analysis",
        options=run_options,
        format_func=lambda x: x[1],
    )

    if not selected_run:
        return

    run_id = selected_run[0]
    run_details = annotation_manager.get_annotation_run_details(run_id)

    # Get all annotations for this run
    annotations_df = get_annotations_dataframe(run_id, db)

    if annotations_df.empty:
        st.warning("No annotations found for this run")
        return

    # Calculate reliability metrics for each assessment category
    st.subheader("📈 Reliability by Assessment Category")

    for category in run_details["assessment_categories"]:
        category_id = category["id"]
        category_name = category["name"]
        category_type = category["type"]

        # Filter annotations for this category
        category_annotations = annotations_df[annotations_df["category_id"] == category_id]

        if category_annotations.empty:
            st.write(f"**{category_name}:** No annotations yet")
            continue

        st.write(f"**{category_name}** ({category_type})")

        # Create pivot table for reliability analysis
        reliability_matrix = category_annotations.pivot_table(
            index="response_id", columns="labeler_initials", values="value", aggfunc="first"
        )

        # Calculate agreement statistics
        if category_type in ["categorical", "binary"]:
            agreement_stats = calculate_categorical_agreement(reliability_matrix)

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Percent Agreement", f"{agreement_stats['percent_agreement']:.1f}%")

            with col2:
                if agreement_stats["fleiss_kappa"] is not None:
                    st.metric("Fleiss' Kappa", f"{agreement_stats['fleiss_kappa']:.3f}")
                else:
                    st.metric("Fleiss' Kappa", "N/A")

            with col3:
                st.metric("Complete Cases", agreement_stats["complete_cases"])

            # Show agreement matrix heatmap if multiple labelers
            if reliability_matrix.shape[1] > 1:
                fig = create_agreement_heatmap(reliability_matrix, category_name)
                st.plotly_chart(fig, use_container_width=True)

        else:  # text type
            st.info("Text categories require qualitative analysis")
            st.write(f"Total annotations: {len(category_annotations)}")

        st.divider()


def show_detailed_analysis(
    annotation_manager: AnnotationManager, annotation_runs: List[Dict], db: DatabaseManager
):
    """Display detailed analysis with filtering and visualization."""
    st.subheader("🔍 Detailed Analysis")

    # Select annotation run
    run_options = [(run["id"], run["name"]) for run in annotation_runs]
    selected_run = st.selectbox(
        "Select Annotation Run for Detailed Analysis",
        options=run_options,
        format_func=lambda x: x[1],
        key="detailed_run_select",
    )

    if not selected_run:
        return

    run_id = selected_run[0]
    run_details = annotation_manager.get_annotation_run_details(run_id)

    # Get annotations and response details
    annotations_df = get_annotations_dataframe(run_id, db)

    if annotations_df.empty:
        st.warning("No annotations found for this run")
        return

    # Add response metadata to annotations
    annotations_with_metadata = add_response_metadata(annotations_df, run_id, db)

    # Filters
    st.subheader("🎛️ Filters")

    col1, col2, col3 = st.columns(3)

    with col1:
        # Model filter
        available_models = sorted(annotations_with_metadata["model"].unique())
        selected_models = st.multiselect(
            "Models", options=available_models, default=available_models
        )

    with col2:
        # Labeler filter
        available_labelers = sorted(annotations_with_metadata["labeler_initials"].unique())
        selected_labelers = st.multiselect(
            "Labelers", options=available_labelers, default=available_labelers
        )

    with col3:
        # Assessment category filter
        available_categories = [
            (cat["id"], cat["name"]) for cat in run_details["assessment_categories"]
        ]
        selected_categories = st.multiselect(
            "Assessment Categories",
            options=available_categories,
            default=available_categories,
            format_func=lambda x: x[1],
        )

    # Apply filters
    filtered_df = annotations_with_metadata[
        (annotations_with_metadata["model"].isin(selected_models))
        & (annotations_with_metadata["labeler_initials"].isin(selected_labelers))
        & (annotations_with_metadata["category_id"].isin([cat[0] for cat in selected_categories]))
    ]

    if filtered_df.empty:
        st.warning("No data matches the current filters")
        return

    st.divider()

    # Analysis visualizations
    st.subheader("📊 Analysis Results")

    # 1. Distribution by Model and Category
    st.write("**Distribution by Model and Assessment Category**")

    # Create summary statistics
    summary_stats = (
        filtered_df.groupby(["model", "category_name", "value"]).size().reset_index(name="count")
    )

    # Create stacked bar chart
    if not summary_stats.empty:
        fig = px.bar(
            summary_stats,
            x="model",
            y="count",
            color="value",
            facet_col="category_name",
            title="Response Distribution by Model and Category",
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    # 2. Labeler Agreement Visualization
    if len(selected_labelers) > 1:
        st.write("**Labeler Agreement Analysis**")

        # Calculate agreement rates between labelers
        agreement_data = calculate_pairwise_agreement(filtered_df)

        if not agreement_data.empty:
            fig = px.imshow(
                agreement_data,
                title="Pairwise Agreement Rates Between Labelers",
                color_continuous_scale="RdYlGn",
                aspect="auto",
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

    # 3. Response-level analysis
    st.write("**Response-Level Analysis**")

    # Show responses with disagreement
    disagreement_responses = find_disagreement_responses(filtered_df)

    if not disagreement_responses.empty:
        st.write(f"Found {len(disagreement_responses)} responses with labeler disagreement:")

        # Show disagreement table
        disagreement_display = disagreement_responses[
            ["response_id", "model", "category_name", "disagreement_count", "values"]
        ].head(10)
        st.dataframe(disagreement_display)

        # Option to export disagreement cases
        if st.button("📥 Export Disagreement Cases"):
            export_df = build_disagreement_export(filtered_df, disagreement_responses)
            csv = export_df.to_csv(index=False)
            st.download_button(
                label="Download Disagreement Cases CSV",
                data=csv,
                file_name=f"disagreement_cases_{run_details['name']}.csv",
                mime="text/csv",
            )


def show_export_results(
    annotation_manager: AnnotationManager, annotation_runs: List[Dict], db: DatabaseManager
):
    """Display export options for annotation results."""
    st.subheader("📊 Export Results")

    # Select annotation runs to export
    st.write("**Select Annotation Runs to Export:**")

    export_options = []
    for run in annotation_runs:
        if st.checkbox(f"{run['name']} ({run['status']})", key=f"export_{run['id']}"):
            export_options.append(run)

    if not export_options:
        st.info("Select annotation runs to export")
        return

    st.divider()

    # Export format options
    st.write("**Export Options:**")

    col1, col2 = st.columns(2)

    with col1:
        include_responses = st.checkbox("Include Full Response Text", value=True)
        include_prompts = st.checkbox("Include Prompt Text", value=True)
        include_metadata = st.checkbox("Include Response Metadata", value=True)

    with col2:
        include_justifications = st.checkbox("Include Justifications", value=True)
        include_timestamps = st.checkbox("Include Timestamps", value=False)
        export_format = st.selectbox("Export Format", ["CSV", "JSON", "Excel"])

    # Generate export
    if st.button("📥 Generate Export", type="primary"):
        try:
            export_data = generate_export_data(
                export_options,
                annotation_manager,
                db,
                include_responses=include_responses,
                include_prompts=include_prompts,
                include_metadata=include_metadata,
                include_justifications=include_justifications,
                include_timestamps=include_timestamps,
            )

            if export_data.empty:
                st.warning("No data to export")
                return

            # Create download
            if export_format == "CSV":
                csv_data = export_data.to_csv(index=False)
                st.download_button(
                    label="📥 Download CSV",
                    data=csv_data,
                    file_name=f"annotation_results_{len(export_options)}_runs.csv",
                    mime="text/csv",
                )

            elif export_format == "JSON":
                json_data = export_data.to_json(orient="records", indent=2)
                st.download_button(
                    label="📥 Download JSON",
                    data=json_data,
                    file_name=f"annotation_results_{len(export_options)}_runs.json",
                    mime="application/json",
                )

            else:  # Excel
                # Create Excel file in memory
                from io import BytesIO

                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                    export_data.to_excel(writer, sheet_name="Annotations", index=False)

                st.download_button(
                    label="📥 Download Excel",
                    data=buffer.getvalue(),
                    file_name=f"annotation_results_{len(export_options)}_runs.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

            # Show preview
            st.write("**Export Preview:**")
            st.dataframe(export_data.head(100))
            st.write(f"Total records: {len(export_data)}")

        except Exception as e:
            st.error(f"Export failed: {e}")


# Helper functions


def get_annotations_dataframe(run_id: int, db: DatabaseManager) -> pd.DataFrame:
    """Get all annotations for a run as a DataFrame."""
    with db.get_connection() as conn:
        query = """
        SELECT a.*, ac.name as category_name, ac.type as category_type
        FROM annotations a
        JOIN assessment_categories ac ON a.category_id = ac.id
        WHERE a.annotation_run_id = ?
        """
        cursor = conn.execute(query, (run_id,))
        data = [dict(row) for row in cursor.fetchall()]

    return pd.DataFrame(data) if data else pd.DataFrame()


def add_response_metadata(
    annotations_df: pd.DataFrame, run_id: int, db: DatabaseManager
) -> pd.DataFrame:
    """Add response metadata to annotations DataFrame."""
    with db.get_connection() as conn:
        query = """
        SELECT lr.id as response_id, lr.model, lr.response_text,
               p.content as prompt_content, p.communication_style, p.severity,
               c.name as condition_name
        FROM llm_responses lr
        JOIN prompts p ON lr.prompt_id = p.id
        JOIN prompt_groups pg ON p.group_id = pg.id
        JOIN conditions c ON pg.condition_id = c.id
        JOIN annotation_runs ar ON lr.experiment_id = ar.experiment_id
        WHERE ar.id = ?
        """
        cursor = conn.execute(query, (run_id,))
        metadata = pd.DataFrame([dict(row) for row in cursor.fetchall()])

    if not metadata.empty:
        return annotations_df.merge(metadata, on="response_id", how="left")
    else:
        return annotations_df


def calculate_categorical_agreement(reliability_matrix: pd.DataFrame) -> Dict:
    """Calculate agreement statistics for categorical data."""
    # Remove rows with any missing values for complete case analysis
    complete_cases = reliability_matrix.dropna()

    if complete_cases.empty or complete_cases.shape[1] < 2:
        return {"percent_agreement": 0, "fleiss_kappa": None, "complete_cases": len(complete_cases)}

    # Calculate percent agreement
    agreements = 0
    total_comparisons = 0

    for _idx, row in complete_cases.iterrows():
        values = row.values
        n_raters = len(values)

        # Count pairwise agreements
        for i in range(n_raters):
            for j in range(i + 1, n_raters):
                total_comparisons += 1
                if values[i] == values[j]:
                    agreements += 1

    percent_agreement = (agreements / total_comparisons * 100) if total_comparisons > 0 else 0

    # Calculate Fleiss' Kappa (simplified version)
    fleiss_kappa = calculate_fleiss_kappa(complete_cases)

    return {
        "percent_agreement": percent_agreement,
        "fleiss_kappa": fleiss_kappa,
        "complete_cases": len(complete_cases),
    }


def calculate_fleiss_kappa(data: pd.DataFrame) -> Optional[float]:
    """Calculate Fleiss' Kappa for multi-rater agreement."""
    if data.empty or data.shape[1] < 2:
        return None

    try:
        n_items, n_raters = data.shape

        # Get all unique categories
        all_values = pd.concat([data[col] for col in data.columns])
        categories = sorted(all_values.unique())
        n_categories = len(categories)

        if n_categories < 2:
            return None

        # Create agreement matrix
        agreements = np.zeros((n_items, n_categories))

        for i, (_idx, row) in enumerate(data.iterrows()):
            for cat_idx, category in enumerate(categories):
                agreements[i, cat_idx] = (row == category).sum()

        # Calculate P_i (proportion of agreement for each item)
        p_i = np.sum(agreements * (agreements - 1), axis=1) / (n_raters * (n_raters - 1))
        P_bar = np.mean(p_i)

        # Calculate P_j (marginal proportion for each category)
        p_j = np.sum(agreements, axis=0) / (n_items * n_raters)
        P_e = np.sum(p_j**2)

        # Calculate Fleiss' Kappa
        if P_e == 1.0:
            return 1.0

        kappa = (P_bar - P_e) / (1 - P_e)
        return kappa

    except Exception:
        return None


def create_agreement_heatmap(reliability_matrix: pd.DataFrame, category_name: str):
    """Create agreement heatmap visualization."""
    # Calculate pairwise agreement matrix
    labelers = reliability_matrix.columns.tolist()
    n_labelers = len(labelers)

    agreement_matrix = np.zeros((n_labelers, n_labelers))

    for i, labeler1 in enumerate(labelers):
        for j, labeler2 in enumerate(labelers):
            if i == j:
                agreement_matrix[i, j] = 1.0
            else:
                # Calculate agreement between two labelers
                common_items = reliability_matrix[[labeler1, labeler2]].dropna()
                if len(common_items) > 0:
                    agreements = (common_items[labeler1] == common_items[labeler2]).sum()
                    agreement_matrix[i, j] = agreements / len(common_items)

    fig = go.Figure(
        data=go.Heatmap(
            z=agreement_matrix,
            x=labelers,
            y=labelers,
            colorscale="RdYlGn",
            zmin=0,
            zmax=1,
            text=np.round(agreement_matrix, 3),
            texttemplate="%{text}",
            textfont={"size": 12},
        )
    )

    fig.update_layout(
        title=f"Pairwise Agreement: {category_name}",
        xaxis_title="Labeler",
        yaxis_title="Labeler",
        height=400,
    )

    return fig


def calculate_pairwise_agreement(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate pairwise agreement rates between labelers."""
    labelers = df["labeler_initials"].unique()
    agreement_matrix = pd.DataFrame(index=labelers, columns=labelers, dtype=float)

    for labeler1 in labelers:
        for labeler2 in labelers:
            if labeler1 == labeler2:
                agreement_matrix.loc[labeler1, labeler2] = 1.0
            else:
                # Find common responses
                l1_responses = df[df["labeler_initials"] == labeler1]
                l2_responses = df[df["labeler_initials"] == labeler2]

                merged = l1_responses.merge(
                    l2_responses, on=["response_id", "category_id"], suffixes=("_1", "_2")
                )

                if len(merged) > 0:
                    agreements = (merged["value_1"] == merged["value_2"]).sum()
                    agreement_matrix.loc[labeler1, labeler2] = agreements / len(merged)
                else:
                    agreement_matrix.loc[labeler1, labeler2] = 0

    return agreement_matrix


def find_disagreement_responses(df: pd.DataFrame) -> pd.DataFrame:
    """Find responses with disagreement between labelers."""
    disagreements = []

    # Group by response and category
    for (response_id, category_id), group in df.groupby(["response_id", "category_id"]):
        if len(group) > 1:  # Multiple labelers
            unique_values = group["value"].nunique()
            if unique_values > 1:  # Disagreement exists
                disagreements.append(
                    {
                        "response_id": response_id,
                        "category_id": category_id,
                        "category_name": group["category_name"].iloc[0],
                        "model": group["model"].iloc[0] if "model" in group.columns else "Unknown",
                        "disagreement_count": unique_values,
                        "values": ", ".join(group["value"].astype(str).unique()),
                        "labelers": ", ".join(group["labeler_initials"].unique()),
                    }
                )

    return pd.DataFrame(disagreements)


def build_disagreement_export(df: pd.DataFrame, disagreement_responses: pd.DataFrame) -> pd.DataFrame:
    """Build a detailed export of disagreement cases with one row per labeler.

    Includes the full prompt text, each labeler's value, and their justification
    (if given) for every response/category pair flagged as a disagreement.
    """
    disagreement_keys = disagreement_responses[["response_id", "category_id"]]

    detail = df.merge(disagreement_keys, on=["response_id", "category_id"], how="inner")

    columns = [
        "response_id",
        "model",
        "category_name",
        "prompt_content",
        "labeler_initials",
        "value",
        "justification",
    ]
    available_columns = [col for col in columns if col in detail.columns]

    export_df = detail[available_columns].sort_values(["response_id", "category_name", "labeler_initials"])
    return export_df.rename(
        columns={
            "prompt_content": "prompt",
            "labeler_initials": "labeler",
            "justification": "reason",
        }
    )


def generate_export_data(
    runs: List[Dict], annotation_manager: AnnotationManager, db: DatabaseManager, **options
) -> pd.DataFrame:
    """Generate comprehensive export data."""
    all_data = []

    for run in runs:
        run_id = run["id"]
        # run_details = annotation_manager.get_annotation_run_details(run_id)  # Not used

        # Get annotations with metadata
        annotations_df = get_annotations_dataframe(run_id, db)
        if not annotations_df.empty:
            annotations_with_metadata = add_response_metadata(annotations_df, run_id, db)

            # Add run information
            annotations_with_metadata["annotation_run_name"] = run["name"]
            annotations_with_metadata["annotation_run_id"] = run_id
            annotations_with_metadata["experiment_name"] = run["experiment_name"]

            # Filter columns based on options
            columns_to_keep = [
                "annotation_run_name",
                "annotation_run_id",
                "experiment_name",
                "response_id",
                "category_name",
                "labeler_initials",
                "value",
            ]

            if options.get("include_justifications", True):
                columns_to_keep.append("justification")

            if options.get("include_timestamps", False):
                columns_to_keep.extend(["created_at", "updated_at"])

            if options.get("include_metadata", True):
                columns_to_keep.extend(
                    ["model", "communication_style", "severity", "condition_name"]
                )

            if options.get("include_prompts", True):
                columns_to_keep.append("prompt_content")

            if options.get("include_responses", True):
                columns_to_keep.append("response_text")

            # Filter to available columns
            available_columns = [
                col for col in columns_to_keep if col in annotations_with_metadata.columns
            ]
            filtered_data = annotations_with_metadata[available_columns]

            all_data.append(filtered_data)

    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
