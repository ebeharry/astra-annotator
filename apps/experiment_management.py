"""Experiment Management page."""

import asyncio
import threading
import time
from typing import Dict

import pandas as pd
import streamlit as st

from core.database import DatabaseManager
from core.managers.experiment import ExperimentManager


def show_experiment_management():
    """Display the experiment management interface."""
    st.header("🧪 Experiment Management")

    # Initialize managers
    db = DatabaseManager(st.session_state.db_path)
    experiment_manager = ExperimentManager(db)

    # Initialize session state for experiment execution
    if "running_experiments" not in st.session_state:
        st.session_state.running_experiments = {}

    # Tabs for different sections
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📋 View Experiments", "➕ Create Experiment", "▶️ Run Experiments", "⚙️ API Configuration"]
    )

    with tab1:
        show_experiment_list(experiment_manager)

    with tab2:
        show_create_experiment(experiment_manager, db)

    with tab3:
        show_run_experiments(experiment_manager)

    with tab4:
        show_api_configuration()


def run_experiment_async(
    experiment_manager: ExperimentManager, exp_id: int, api_keys: Dict, max_concurrent: int
):
    """Run experiment in a separate thread."""
    try:
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Run the experiment
        result = loop.run_until_complete(
            experiment_manager.run_experiment(exp_id, api_keys, max_concurrent)
        )

        # Update session state with results
        st.session_state.running_experiments[exp_id] = {
            "status": "completed",
            "result": result,
            "completed_at": time.time(),
        }

    except Exception as e:
        st.session_state.running_experiments[exp_id] = {
            "status": "failed",
            "error": str(e),
            "completed_at": time.time(),
        }
    finally:
        loop.close()


def show_experiment_list(experiment_manager: ExperimentManager):
    """Display list of experiments with details."""
    st.subheader("Current Experiments")

    experiments = experiment_manager.get_experiments()

    if not experiments:
        st.info("No experiments found. Create an experiment to get started!")
        return

    # Auto-refresh for running experiments
    if any(
        exp_id in st.session_state.running_experiments
        for exp_id in [exp["id"] for exp in experiments]
    ):
        time.sleep(2)
        st.rerun()

    # Display experiments
    for exp in experiments:
        # Check if experiment is running
        is_running = exp["id"] in st.session_state.running_experiments
        running_info = st.session_state.running_experiments.get(exp["id"], {})

        status_indicator = "🔄" if is_running and running_info.get("status") != "completed" else ""

        with st.expander(f"🧪 {exp['name']} ({exp['status']}) {status_indicator}"):
            col1, col2 = st.columns(2)

            with col1:
                st.write(f"**Description:** {exp['description'] or 'No description'}")
                st.write(f"**Status:** {exp['status']}")
                st.write(f"**Created:** {exp['created_at']}")
                if exp["completed_at"]:
                    st.write(f"**Completed:** {exp['completed_at']}")

                # Show running status
                if is_running:
                    if running_info.get("status") == "completed":
                        st.success("✅ Background execution completed!")
                        result = running_info.get("result", {})
                        st.write(
                            f"**Results:** {result.get('completed', 0)} completed, {result.get('failed', 0)} failed"
                        )
                    elif running_info.get("status") == "failed":
                        st.error(
                            f"❌ Background execution failed: {running_info.get('error', 'Unknown error')}"
                        )
                    else:
                        st.info("⏳ Running in background...")

            with col2:
                st.write(f"**Models:** {', '.join(exp['models'])}")

                # Get progress
                progress = experiment_manager.get_experiment_progress(exp["id"])
                st.write(f"**Progress:** {progress['completion_percentage']:.1f}%")

                st.progress(progress["completion_percentage"] / 100)

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Completed", progress["completed"])
                with col2:
                    st.metric("Failed", progress["failed"])
                with col3:
                    st.metric("Pending", progress["pending"])

            # Model-wise progress
            if progress["by_model"]:
                st.write("**Progress by Model:**")
                model_df = pd.DataFrame(progress["by_model"]).T
                st.dataframe(model_df)


def show_create_experiment(experiment_manager: ExperimentManager, db: DatabaseManager):
    """Display form to create new experiments."""
    st.subheader("Create New Experiment")

    # Get available prompts
    prompts = db.get_prompts()
    prompt_groups = db.get_prompt_groups()

    if not prompts:
        st.warning(
            "⚠️ No prompts available. Please add prompts first in the Prompt Management section."
        )
        return

    with st.form("create_experiment_form"):
        # Basic experiment info
        st.write("**Experiment Details:**")
        exp_name = st.text_input("Experiment Name*")
        exp_description = st.text_area("Description")

        # Model selection
        st.write("**Model Selection:**")
        available_models = {
            "OpenAI": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"],
            "Claude": [
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307",
            ],
            "Grok": ["grok-beta"],
            "Gemini": ["gemini-pro", "gemini-1.5-pro"],
            "Ollama": ["llama2", "llama3", "mistral", "codellama"],
        }

        selected_models = []
        for provider, models in available_models.items():
            st.write(f"**{provider}:**")
            cols = st.columns(len(models))
            for i, model in enumerate(models):
                with cols[i]:
                    if st.checkbox(model, key=f"model_{model}"):
                        selected_models.append(model)

        # Prompt selection
        st.write("**Prompt Selection:**")

        selection_method = st.radio(
            "Selection Method", ["Select by Groups", "Select Individual Prompts", "Select All"]
        )

        selected_prompt_ids = []

        if selection_method == "Select by Groups":
            selected_groups = st.multiselect(
                "Select Prompt Groups",
                options=[(g["id"], g["name"]) for g in prompt_groups],
                format_func=lambda x: x[1],
            )

            if selected_groups:
                group_ids = [g[0] for g in selected_groups]
                selected_prompt_ids = [p["id"] for p in prompts if p["group_id"] in group_ids]
                st.write(
                    f"Selected {len(selected_prompt_ids)} prompts from {len(selected_groups)} groups"
                )

        elif selection_method == "Select Individual Prompts":
            # Group prompts by group for easier selection
            prompts_by_group = {}
            for prompt in prompts:
                group_name = prompt["group_name"]
                if group_name not in prompts_by_group:
                    prompts_by_group[group_name] = []
                prompts_by_group[group_name].append(prompt)

            for group_name, group_prompts in prompts_by_group.items():
                st.write(f"**{group_name}:**")
                for prompt in group_prompts:
                    prompt_preview = (
                        prompt["content"][:100] + "..."
                        if len(prompt["content"]) > 100
                        else prompt["content"]
                    )
                    if st.checkbox(
                        f"{prompt['communication_style']}/{prompt['severity']}: {prompt_preview}",
                        key=f"prompt_{prompt['id']}",
                    ):
                        selected_prompt_ids.append(prompt["id"])

        else:  # Select All
            selected_prompt_ids = [p["id"] for p in prompts]
            st.write(f"All {len(selected_prompt_ids)} prompts selected")

        submitted = st.form_submit_button("Create Experiment")

        if submitted:
            # Validation
            if not exp_name:
                st.error("Experiment name is required")
                return

            if not selected_models:
                st.error("At least one model must be selected")
                return

            if not selected_prompt_ids:
                st.error("At least one prompt must be selected")
                return

            try:
                experiment_id = experiment_manager.create_experiment(
                    name=exp_name,
                    description=exp_description,
                    models=selected_models,
                    prompt_ids=selected_prompt_ids,
                )

                st.success(
                    f"✅ Experiment '{exp_name}' created successfully! (ID: {experiment_id})"
                )
                st.write(f"• Models: {', '.join(selected_models)}")
                st.write(f"• Prompts: {len(selected_prompt_ids)}")
                st.write(
                    f"• Total responses to generate: {len(selected_models) * len(selected_prompt_ids)}"
                )

                st.rerun()

            except Exception as e:
                st.error(f"Error creating experiment: {e}")


def show_run_experiments(experiment_manager: ExperimentManager):
    """Display interface to run experiments."""
    st.subheader("Run Experiments")

    experiments = experiment_manager.get_experiments()

    # Filter to runnable experiments
    runnable_experiments = [exp for exp in experiments if exp["status"] in ["created", "failed"]]

    if not runnable_experiments:
        st.info(
            "No experiments available to run. Create an experiment first or all experiments are already completed."
        )
        return

    # Select experiment to run
    selected_exp = st.selectbox(
        "Select Experiment to Run",
        options=[(exp["id"], exp["name"]) for exp in runnable_experiments],
        format_func=lambda x: x[1],
    )

    if selected_exp:
        exp_id = selected_exp[0]
        progress = experiment_manager.get_experiment_progress(exp_id)

        # Check if experiment is currently running
        is_running = exp_id in st.session_state.running_experiments
        running_info = st.session_state.running_experiments.get(exp_id, {})

        # Show experiment details
        st.write("**Experiment Details:**")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Responses", progress["total_responses"])
        with col2:
            st.metric("Completed", progress["completed"])
        with col3:
            st.metric("Pending", progress["pending"])

        # Progress bar
        if progress["total_responses"] > 0:
            st.progress(progress["completion_percentage"] / 100)
            st.write(f"Progress: {progress['completion_percentage']:.1f}%")

        # Show running status
        if is_running:
            if running_info.get("status") == "completed":
                st.success("✅ Experiment completed in background!")
                if st.button("Clear Status"):
                    del st.session_state.running_experiments[exp_id]
                    st.rerun()
            elif running_info.get("status") == "failed":
                st.error(f"❌ Experiment failed: {running_info.get('error')}")
                if st.button("Clear Status"):
                    del st.session_state.running_experiments[exp_id]
                    st.rerun()
            else:
                st.info("⏳ Experiment is running in background...")
                st.write(
                    "The page will auto-refresh to show progress. You can navigate to other pages while it runs."
                )

                if st.button("Cancel Experiment"):
                    del st.session_state.running_experiments[exp_id]
                    st.rerun()
                return

        # API Keys configuration
        st.write("**API Keys (Optional - will use environment variables if not provided):**")

        col1, col2 = st.columns(2)
        with col1:
            openai_key = st.text_input("OpenAI API Key", type="password", value="")
            anthropic_key = st.text_input("Anthropic API Key", type="password", value="")
            google_key = st.text_input("Google API Key", type="password", value="")

        with col2:
            xai_key = st.text_input("xAI API Key", type="password", value="")
            max_concurrent = st.number_input(
                "Max Concurrent Requests", min_value=1, max_value=20, value=5
            )

        # Run button
        if st.button("🚀 Run Experiment", type="primary"):
            # Prepare API keys
            api_keys = {}
            if openai_key:
                api_keys["openai"] = openai_key
            if anthropic_key:
                api_keys["anthropic"] = anthropic_key
            if google_key:
                api_keys["google"] = google_key
            if xai_key:
                api_keys["xai"] = xai_key

            # Start experiment in background thread
            st.session_state.running_experiments[exp_id] = {
                "status": "running",
                "started_at": time.time(),
            }

            # Start background thread
            thread = threading.Thread(
                target=run_experiment_async,
                args=(experiment_manager, exp_id, api_keys, max_concurrent),
            )
            thread.daemon = True
            thread.start()

            st.success("🚀 Experiment started in background!")
            st.info(
                "The experiment will run in the background. You can navigate to other pages and check back for progress."
            )

            # Auto-refresh to show running status
            time.sleep(1)
            st.rerun()


def show_api_configuration():
    """Display API configuration interface."""
    st.subheader("API Configuration")

    st.write("""
    Configure your LLM provider API keys. You can either set them as environment variables
    or provide them when running experiments.
    """)

    # Environment variables info
    st.write("**Environment Variables:**")
    env_vars = {
        "OpenAI": "OPENAI_API_KEY",
        "Anthropic": "ANTHROPIC_API_KEY",
        "Google": "GOOGLE_API_KEY",
        "xAI": "XAI_API_KEY",
    }

    import os

    for provider, env_var in env_vars.items():
        value = os.getenv(env_var)
        if value:
            st.success(f"✅ {provider}: {env_var} is set")
        else:
            st.warning(f"⚠️ {provider}: {env_var} is not set")

    st.write("**Model Information:**")

    model_info = {
        "OpenAI GPT-4": "Requires OPENAI_API_KEY. High quality but expensive.",
        "Claude 3": "Requires ANTHROPIC_API_KEY. Excellent for complex reasoning.",
        "Grok": "Requires XAI_API_KEY. Fast and efficient.",
        "Gemini Pro": "Requires GOOGLE_API_KEY. Good balance of speed and quality.",
        "Ollama (Local)": "No API key required. Runs locally - make sure Ollama is running.",
    }

    for model, description in model_info.items():
        st.write(f"• **{model}**: {description}")

    st.info("""
    💡 **Tips:**
    - Set environment variables in your system or `.env` file for convenience
    - API keys provided in the interface override environment variables
    - Local models (Ollama) don't require API keys but need the service running
    - Start with fewer concurrent requests if you hit rate limits
    - Experiments run in background threads - you can navigate between pages while they execute
    """)
