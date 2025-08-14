"""Prompt Management page with flexible prompt group types."""

from typing import Dict

import pandas as pd
import plotly.express as px
import streamlit as st

from core.database import DatabaseManager
from core.managers.prompt import PromptManager


def show_prompt_management():
    """Display the prompt management interface."""
    st.header("📝 Prompt Management")

    # Initialize database and manager
    db = DatabaseManager(st.session_state.db_path)
    prompt_manager = PromptManager(db)

    # Tabs for different sections
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📋 View Prompt Groups", "➕ Create Prompt Group", "📊 Statistics", "📥 Import/Export"]
    )

    with tab1:
        show_prompt_groups_list(db)

    with tab2:
        show_create_prompt_group(db, prompt_manager)

    with tab3:
        show_prompt_statistics(db, prompt_manager)

    with tab4:
        show_import_export(db, prompt_manager)


def show_prompt_groups_list(db: DatabaseManager):
    """Display the list of prompt groups."""
    st.subheader("Current Prompt Groups")

    # Get data
    conditions = db.get_conditions()
    prompt_groups = db.get_prompt_groups()

    if not prompt_groups:
        st.info("No prompt groups found. Create a prompt group to get started!")
        return

    # Filters
    col1, col2 = st.columns(2)
    with col1:
        condition_names = ["All"] + [c["name"] for c in conditions]
        selected_condition = st.selectbox("Filter by Condition", condition_names)

    with col2:
        group_types = ["All", "grid_3x3", "single", "list"]
        selected_type = st.selectbox("Filter by Group Type", group_types)

    # Apply filters
    filtered_groups = prompt_groups
    if selected_condition != "All":
        filtered_groups = [g for g in filtered_groups if g["condition_name"] == selected_condition]
    if selected_type != "All":
        filtered_groups = [
            g for g in filtered_groups if g.get("group_type", "grid_3x3") == selected_type
        ]

    # Display results
    st.write(f"Showing {len(filtered_groups)} of {len(prompt_groups)} prompt groups")

    # Display each group based on its type
    for group in filtered_groups:
        group_type = group.get("group_type", "grid_3x3")
        type_emoji = {"grid_3x3": "🔳", "single": "📄", "list": "📋"}

        with st.expander(
            f"{type_emoji.get(group_type, '🧠')} {group['condition_name']} - {group['name']} ({group_type})"
        ):
            col1, col2 = st.columns([1, 2])

            with col1:
                st.write(f"**Type:** {group_type}")
                st.write(f"**Condition:** {group['condition_name']}")
                st.write(f"**Description:** {group['description'] or 'No description'}")
                st.write(f"**Risk Category:** {group['risk_category'] or 'Not specified'}")
                st.write(f"**Created:** {group['created_at']}")

                # Show severity explanations for grid types
                if group_type == "grid_3x3" and any(
                    [
                        group["low_severity_explanation"],
                        group["moderate_severity_explanation"],
                        group["high_severity_explanation"],
                    ]
                ):
                    st.write("**Severity Explanations:**")
                    if group["low_severity_explanation"]:
                        st.write(f"• **Low:** {group['low_severity_explanation']}")
                    if group["moderate_severity_explanation"]:
                        st.write(f"• **Moderate:** {group['moderate_severity_explanation']}")
                    if group["high_severity_explanation"]:
                        st.write(f"• **High:** {group['high_severity_explanation']}")

            with col2:
                if group_type == "grid_3x3":
                    st.write("**Prompt Grid:**")
                    display_prompt_grid(db, group["id"], editable=False)
                elif group_type == "single":
                    st.write("**Single Prompt:**")
                    display_single_prompt(db, group["id"])
                else:  # list
                    st.write("**Prompt List:**")
                    display_prompt_list(db, group["id"])


def display_prompt_grid(
    db: DatabaseManager,
    group_id: int,
    editable: bool = False,
    severity_explanations: Dict[str, str] = None,
):
    """Display a 3x3 grid of prompts with severity explanations."""
    grid = db.get_prompt_grid(group_id)

    communication_styles = ["implicit", "neutral", "explicit"]
    severities = ["low", "moderate", "high"]

    # Show severity explanations above columns if provided
    if severity_explanations:
        exp_cols = st.columns([1] + [2] * 3)
        exp_cols[0].write("")  # Empty space above row labels
        for i, severity in enumerate(severities):
            explanation = severity_explanations.get(f"{severity}_severity_explanation", "")
            if explanation:
                exp_cols[i + 1].info(f"**{severity.title()}:** {explanation}")
            else:
                exp_cols[i + 1].write("")  # Empty space if no explanation

    # Create header row
    header_cols = st.columns([1] + [2] * 3)
    header_cols[0].write("**Style / Severity**")
    for i, severity in enumerate(severities):
        header_cols[i + 1].write(f"**{severity.title()}**")

    # Create grid rows
    for style in communication_styles:
        cols = st.columns([1] + [2] * 3)
        cols[0].write(f"**{style.title()}**")

        for i, severity in enumerate(severities):
            content = grid[style][severity]
            if editable:
                # This would be used in edit mode
                grid[style][severity] = cols[i + 1].text_area(
                    f"{style}_{severity}",
                    value=content,
                    height=200,
                    label_visibility="collapsed",
                    key=f"grid_{group_id}_{style}_{severity}",
                )
            else:
                if content:
                    cols[i + 1].text_area(
                        f"{style}_{severity}",
                        value=content,
                        height=200,
                        disabled=True,
                        label_visibility="collapsed",
                    )
                else:
                    cols[i + 1].info("No prompt defined")

    return grid if editable else None


def display_single_prompt(db: DatabaseManager, group_id: int):
    """Display a single prompt."""
    prompts = db.get_prompts({"group_id": group_id})
    if prompts:
        prompt = prompts[0]
        st.text_area("Prompt Content", value=prompt["content"], height=200, disabled=True)
        if prompt["labels"]:
            st.write("**Labels:**")
            for key, value in prompt["labels"].items():
                st.write(f"• **{key}:** {value}")
    else:
        st.info("No prompt found")


def display_prompt_list(db: DatabaseManager, group_id: int):
    """Display a list of prompts in order."""
    prompts = db.get_prompts({"group_id": group_id})
    if prompts:
        for i, prompt in enumerate(prompts, 1):
            with st.container():
                st.write(f"**Prompt {i}:**")
                st.text_area(
                    f"prompt_{i}",
                    value=prompt["content"],
                    height=100,
                    disabled=True,
                    label_visibility="collapsed",
                )
                if prompt["labels"]:
                    with st.expander(f"Labels for Prompt {i}"):
                        for key, value in prompt["labels"].items():
                            st.write(f"• **{key}:** {value}")
    else:
        st.info("No prompts found")


def show_create_prompt_group(db: DatabaseManager, prompt_manager: PromptManager):
    """Display form to create new prompt groups of different types."""
    st.subheader("Create New Prompt Group")

    # Group type selection
    st.write("**1. Select Prompt Group Type:**")
    group_type = st.radio(
        "Group Type",
        options=["single", "list", "grid_3x3"],
        format_func=lambda x: {
            "single": "📄 Single Prompt - One prompt only",
            "list": "📋 List Prompts - Multiple prompts in sequence",
            "grid_3x3": "🔳 3x3 Grid - Systematic communication style × severity matrix",
        }[x],
        help="Choose how you want to organize your prompts",
    )

    # Get existing conditions
    conditions = db.get_conditions()

    # Initialize variables for all group types
    prompt_list = []

    with st.form("create_prompt_group_form"):
        # Condition selection or creation
        st.write("**2. Select or Create Condition:**")

        # Create condition options
        condition_options = ["Create New Condition..."]
        if conditions:
            condition_options.extend([c["name"] for c in conditions])

        selected_condition_option = st.selectbox(
            "Condition",
            options=condition_options,
            help="Select an existing condition or create a new one",
        )

        if selected_condition_option == "Create New Condition...":
            # Create new condition
            st.write("**New Condition Details:**")
            new_condition_name = st.text_input("Condition Name*")
            new_condition_description = st.text_area("Condition Description")
            condition_id = None  # Will be created during submission
            condition_option = "Create New Condition"
        else:
            # Use existing condition
            selected_condition = next(
                (c for c in conditions if c["name"] == selected_condition_option), None
            )
            condition_id = selected_condition["id"] if selected_condition else None
            new_condition_name = None
            new_condition_description = None
            condition_option = "Select Existing Condition"

        # Group details
        st.write("**3. Prompt Group Details:**")
        group_name = st.text_input(
            "Group Name*", help="e.g., 'Moderate Severity Focus', 'Therapeutic Setting'"
        )
        group_description = st.text_area("Group Description")

        # Risk category with existing options
        st.write("**Risk Category:**")
        existing_risk_categories = db.get_risk_categories()

        if existing_risk_categories:
            risk_options = ["None"] + existing_risk_categories + ["Other (specify)"]
            selected_risk = st.selectbox("Risk Category", risk_options)

            if selected_risk == "Other (specify)":
                risk_category = st.text_input(
                    "Specify Risk Category", help="e.g., 'Suicidal ideation', 'Self-harm'"
                )
            elif selected_risk == "None":
                risk_category = None
            else:
                risk_category = selected_risk
        else:
            risk_category = st.text_input(
                "Risk Category (Optional)", help="e.g., 'Suicidal ideation', 'Self-harm'"
            )

        # Initialize variables for all group types
        low_severity_explanation = None
        moderate_severity_explanation = None
        high_severity_explanation = None
        prompt_grid = {}
        single_prompt_content = ""
        prompt_list = []

        # Conditional sections based on group type
        if group_type == "grid_3x3":
            # Individual severity explanations
            st.write("**4. Severity Scale Explanations:**")
            st.write("Define what each severity level means for this prompt group:")

            col1, col2, col3 = st.columns(3)
            with col1:
                low_severity_explanation = st.text_area(
                    "Low Severity",
                    height=100,
                    placeholder="What constitutes low severity for this condition...",
                )
            with col2:
                moderate_severity_explanation = st.text_area(
                    "Moderate Severity",
                    height=100,
                    placeholder="What constitutes moderate severity...",
                )
            with col3:
                high_severity_explanation = st.text_area(
                    "High Severity", height=100, placeholder="What constitutes high severity..."
                )

            # 3x3 Prompt Grid
            st.write("**5. Define Prompts (3x3 Grid):**")
            st.write(
                "Create exactly 9 prompts covering all combinations of communication style and severity."
            )

            communication_styles = ["implicit", "neutral", "explicit"]
            severities = ["low", "moderate", "high"]

            # Show severity explanations above columns
            exp_cols = st.columns([1.5] + [2.5] * 3)
            exp_cols[0].write("")  # Empty space above row labels
            explanations = [
                low_severity_explanation,
                moderate_severity_explanation,
                high_severity_explanation,
            ]
            for i, (severity, explanation) in enumerate(zip(severities, explanations)):
                if explanation and explanation.strip():
                    exp_cols[i + 1].info(f"**{severity.title()}:** {explanation}")
                else:
                    exp_cols[i + 1].write("")  # Empty space if no explanation

            # Header row
            header_cols = st.columns([1.5] + [2.5] * 3)
            header_cols[0].write("**Communication Style**")
            for i, severity in enumerate(severities):
                header_cols[i + 1].write(f"**{severity.title()} Severity**")

            # Grid rows
            for style in communication_styles:
                cols = st.columns([1.5] + [2.5] * 3)
                cols[0].write(f"**{style.title()}**")

                if style not in prompt_grid:
                    prompt_grid[style] = {}

                for i, severity in enumerate(severities):
                    prompt_grid[style][severity] = cols[i + 1].text_area(
                        f"Prompt for {style} style, {severity} severity",
                        height=120,
                        key=f"new_prompt_{style}_{severity}",
                        placeholder=f"Enter {style} {severity} prompt here...",
                    )

        elif group_type == "single":
            # Single prompt input
            st.write("**4. Define Single Prompt:**")
            single_prompt_content = st.text_area(
                "Prompt Content",
                height=200,
                placeholder="Enter your prompt here...",
                help="This will be the only prompt in this group",
            )

        else:  # list
            # List prompt input with dynamic boxes
            st.write("**4. Define Prompt List:**")
            st.write("Add multiple prompts that will be presented in sequence:")

            # Initialize prompt list in session state
            if "form_prompt_list" not in st.session_state:
                st.session_state.form_prompt_list = [""]

            # Display current prompt boxes
            prompt_list = []
            for i in range(len(st.session_state.form_prompt_list)):
                col1, col2 = st.columns([10, 1])
                with col1:
                    prompt_value = st.text_area(
                        f"Prompt {i + 1}",
                        value=st.session_state.form_prompt_list[i],
                        height=100,
                        key=f"form_prompt_{i}",
                        placeholder=f"Enter prompt {i + 1} here...",
                    )
                    # Update session state with current value
                    st.session_state.form_prompt_list[i] = prompt_value
                    if prompt_value.strip():
                        prompt_list.append(prompt_value.strip())

                with col2:
                    if len(st.session_state.form_prompt_list) > 1:
                        # Use form_submit_button for remove action
                        if st.form_submit_button(
                            "🗑️", key=f"remove_{i}", help=f"Remove prompt {i + 1}"
                        ):
                            st.session_state.form_prompt_list.pop(i)
                            st.rerun()

            # Add more prompts button
            col1, col2 = st.columns([8, 2])
            with col2:
                if st.form_submit_button("➕ Add More"):
                    st.session_state.form_prompt_list.append("")
                    st.rerun()

            if prompt_list:
                st.info(f"📋 {len(prompt_list)} prompt(s) defined")
            else:
                st.warning("⚠️ Please add at least one prompt")

        # Additional labels
        st.write("**5. Additional Labels (Optional):**")
        st.write("Add custom labels that apply to all prompts in this group:")

        # Dynamic label input
        if "new_labels" not in st.session_state:
            st.session_state.new_labels = []

        # Add label button
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            new_label_key = st.text_input("Label Key", key="new_label_key")
        with col2:
            new_label_value = st.text_input("Label Value", key="new_label_value")
        with col3:
            if st.form_submit_button("Add Label", type="secondary"):
                if new_label_key and new_label_value:
                    st.session_state.new_labels.append((new_label_key, new_label_value))
                    st.rerun()

        # Display current labels
        if st.session_state.new_labels:
            st.write("**Current Labels:**")
            for i, (key, value) in enumerate(st.session_state.new_labels):
                col1, col2, col3 = st.columns([2, 2, 1])
                col1.write(key)
                col2.write(value)
                if col3.button("Remove", key=f"remove_label_{i}"):
                    st.session_state.new_labels.pop(i)
                    st.rerun()

        # Submit button
        submitted = st.form_submit_button("Create Prompt Group", type="primary")

        if submitted:
            # Validation
            if condition_option == "Create New Condition" and not new_condition_name:
                st.error("Condition name is required when creating new condition")
                return

            if condition_option == "Select Existing Condition" and not condition_id:
                st.error("Please select a condition")
                return

            if not group_name:
                st.error("Group name is required")
                return

            # Validate based on group type
            if group_type == "grid_3x3":
                total_prompts = sum(
                    1
                    for style in prompt_grid.values()
                    for content in style.values()
                    if content.strip()
                )
                if total_prompts == 0:
                    st.error("At least one prompt must be defined in the grid")
                    return
            elif group_type == "single":
                if not single_prompt_content.strip():
                    st.error("Prompt content is required for single prompt groups")
                    return
            else:  # list
                if len(prompt_list) == 0:
                    st.error("At least one prompt is required for list groups")
                    return

            try:
                # Create condition if needed
                if condition_option == "Create New Condition":
                    condition_id = db.create_condition(
                        new_condition_name, new_condition_description
                    )

                # Create prompt group using the PromptManager methods
                if group_type == "single":
                    group_id = prompt_manager.create_single_prompt_group(
                        condition_id=condition_id,
                        name=group_name,
                        content=single_prompt_content.strip(),
                        description=group_description,
                        risk_category=risk_category,
                    )
                    prompt_ids = db.get_prompts({"group_id": group_id})
                    created_count = 1

                elif group_type == "list":
                    group_id = prompt_manager.create_list_prompt_group(
                        condition_id=condition_id,
                        name=group_name,
                        prompt_list=prompt_list,
                        description=group_description,
                        risk_category=risk_category,
                    )
                    prompt_ids = db.get_prompts({"group_id": group_id})
                    created_count = len(prompt_list)

                else:  # grid_3x3
                    group_id = prompt_manager.create_grid_prompt_group(
                        condition_id=condition_id,
                        name=group_name,
                        prompt_grid=prompt_grid,
                        description=group_description,
                        risk_category=risk_category,
                        low_severity_explanation=low_severity_explanation,
                        moderate_severity_explanation=moderate_severity_explanation,
                        high_severity_explanation=high_severity_explanation,
                    )
                    prompt_ids = db.get_prompts({"group_id": group_id})
                    created_count = len(prompt_ids)

                # Add labels to all prompts
                if st.session_state.new_labels:
                    for prompt in prompt_ids:
                        for label_key, label_value in st.session_state.new_labels:
                            db.add_prompt_label(prompt["id"], label_key, label_value)

                st.success(f"✅ Prompt group '{group_name}' created successfully!")
                st.write(f"• Created {created_count} prompts")
                st.write(f"• Added {len(st.session_state.new_labels)} labels to each prompt")

                # Clear session state
                st.session_state.new_labels = []
                if group_type == "list" and "form_prompt_list" in st.session_state:
                    st.session_state.form_prompt_list = [""]

                st.rerun()

            except Exception as e:
                st.error(f"Error creating prompt group: {e}")


def show_prompt_statistics(db: DatabaseManager, prompt_manager: PromptManager):
    """Display prompt statistics and visualizations."""
    st.subheader("Prompt Statistics")

    prompts = db.get_prompts()
    conditions = db.get_conditions()
    prompt_groups = db.get_prompt_groups()

    if not prompts:
        st.info("No prompts available for statistics")
        return

    df = pd.DataFrame(prompts)

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Prompts", len(df))

    with col2:
        st.metric("Conditions", len(conditions))

    with col3:
        st.metric("Prompt Groups", len(prompt_groups))

    with col4:
        complete_groups = sum(
            1 for group in prompt_groups if len(db.get_prompts({"group_id": group["id"]})) == 9
        )
        st.metric("Complete Groups", complete_groups)

    # Visualizations
    col1, col2 = st.columns(2)

    with col1:
        # Communication style distribution
        style_counts = df["communication_style"].value_counts()
        fig1 = px.pie(
            values=style_counts.values,
            names=style_counts.index,
            title="Distribution by Communication Style",
        )
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        # Severity distribution
        severity_counts = df["severity"].value_counts()
        fig2 = px.pie(
            values=severity_counts.values,
            names=severity_counts.index,
            title="Distribution by Severity",
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Condition distribution
    condition_counts = df["condition_name"].value_counts()
    fig3 = px.bar(x=condition_counts.index, y=condition_counts.values, title="Prompts by Condition")
    fig3.update_xaxes(tickangle=45)
    st.plotly_chart(fig3, use_container_width=True)

    # Grid completeness analysis
    st.subheader("Grid Completeness Analysis")

    completeness_data = []
    for group in prompt_groups:
        group_prompts = db.get_prompts({"group_id": group["id"]})
        grid_completion = len(group_prompts) / 9 * 100
        completeness_data.append(
            {
                "Group": f"{group['condition_name']} - {group['name']}",
                "Completion %": grid_completion,
                "Prompts": len(group_prompts),
            }
        )

    if completeness_data:
        completion_df = pd.DataFrame(completeness_data)
        fig4 = px.bar(
            completion_df,
            x="Group",
            y="Completion %",
            title="Prompt Grid Completion by Group",
            color="Completion %",
            color_continuous_scale="RdYlGn",
        )
        fig4.update_xaxes(tickangle=45)
        st.plotly_chart(fig4, use_container_width=True)

    # Cross-tabulation
    st.subheader("Cross-tabulation")
    crosstab = pd.crosstab(df["communication_style"], df["severity"])
    st.dataframe(crosstab)


def show_import_export(db: DatabaseManager, prompt_manager: PromptManager):
    """Display import/export functionality."""
    st.subheader("Import/Export Prompts")

    tab1, tab2 = st.tabs(["📤 Export Data", "📋 Copy Prompt Groups"])

    with tab1:
        st.write("**Export current prompt data**")

        prompts = db.get_prompts()
        conditions = db.get_conditions()
        prompt_groups = db.get_prompt_groups()

        if prompts:
            col1, col2 = st.columns(2)

            with col1:
                if st.button("📄 Export Prompts as CSV"):
                    # Flatten prompt data for CSV export
                    export_data = []
                    for prompt in prompts:
                        row = {
                            "condition": prompt["condition_name"],
                            "group_name": prompt["group_name"],
                            "communication_style": prompt["communication_style"],
                            "severity": prompt["severity"],
                            "content": prompt["content"],
                            "created_at": prompt["created_at"],
                        }
                        # Add labels as separate columns
                        for key, value in prompt["labels"].items():
                            row[f"label_{key}"] = value
                        export_data.append(row)

                    df = pd.DataFrame(export_data)
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="💾 Download CSV",
                        data=csv,
                        file_name="prompts_export.csv",
                        mime="text/csv",
                    )

            with col2:
                if st.button("📋 Export as JSON"):
                    export_data = {
                        "conditions": conditions,
                        "prompt_groups": prompt_groups,
                        "prompts": prompts,
                    }
                    import json

                    json_data = json.dumps(export_data, indent=2, default=str)
                    st.download_button(
                        label="💾 Download JSON",
                        data=json_data,
                        file_name="astra_prompts_export.json",
                        mime="application/json",
                    )
        else:
            st.info("No prompts to export")

    with tab2:
        st.write("**Copy entire prompt groups (3x3 grids)**")

        prompt_groups = db.get_prompt_groups()
        conditions = db.get_conditions()

        if prompt_groups:
            with st.form("copy_prompt_group"):
                col1, col2 = st.columns(2)

                with col1:
                    source_group = st.selectbox(
                        "Source Group",
                        options=[
                            (g["id"], f"{g['condition_name']} - {g['name']}") for g in prompt_groups
                        ],
                        format_func=lambda x: x[1],
                    )

                with col2:
                    target_condition = st.selectbox(
                        "Target Condition",
                        options=[(c["id"], c["name"]) for c in conditions],
                        format_func=lambda x: x[1],
                    )

                new_group_name = st.text_input("New Group Name*")
                new_group_description = st.text_area("New Group Description")

                if st.form_submit_button("Copy Prompt Group"):
                    if not new_group_name:
                        st.error("New group name is required")
                    else:
                        try:
                            # Get source group details
                            source_group_data = next(
                                g for g in prompt_groups if g["id"] == source_group[0]
                            )

                            # Create new group
                            new_group_id = db.create_prompt_group(
                                condition_id=target_condition[0],
                                name=new_group_name,
                                description=new_group_description,
                                risk_category=source_group_data["risk_category"],
                                severity_explanation=source_group_data["severity_explanation"],
                            )

                            # Copy the 3x3 grid
                            source_grid = db.get_prompt_grid(source_group[0])
                            prompt_ids = db.create_prompt_with_grid(new_group_id, source_grid)

                            # Copy labels from source prompts
                            source_prompts = db.get_prompts({"group_id": source_group[0]})
                            for i, source_prompt in enumerate(source_prompts):
                                if i < len(prompt_ids):  # Safety check
                                    for key, value in source_prompt["labels"].items():
                                        db.add_prompt_label(prompt_ids[i], key, value)

                            st.success(f"✅ Successfully copied prompt group '{new_group_name}'")
                            st.write(f"• Copied {len(prompt_ids)} prompts")
                            st.rerun()

                        except Exception as e:
                            st.error(f"Error copying prompt group: {e}")
        else:
            st.info("No prompt groups available to copy")

    # Note about import functionality
    st.info("""
    **📥 Import Functionality:** The import system has been updated to work with the new condition-based
    structure and 3x3 grid format. Use the "Create Prompt Group" tab to systematically create
    complete prompt sets with all 9 combinations of communication style and severity.
    """)
