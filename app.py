"""Main Astra Annotator Streamlit Application."""

import streamlit as st

# Configure page
st.set_page_config(
    page_title="Astra Annotator",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main():
    """Main application entry point."""
    st.title("🧠 Astra Annotator")
    st.subheader("Deception Benchmark Annotation Platform")

    # Initialize session state
    if "db_path" not in st.session_state:
        st.session_state.db_path = "astra_annotator.db"

    # Sidebar navigation
    st.sidebar.title("Navigation")

    apps = {
        "🏠 Home": "home",
        "📝 Prompt Management": "prompts",
        "🧪 Experiment Management": "experiments",
        "⚙️ Annotation Setup": "annotation_setup",
        "🏷️ Labeling Interface": "labeling",
        "📊 Results Analysis": "results",
        "🔍 Disagreement Review": "disagreement_review",
    }

    selected_page = st.sidebar.selectbox("Select Page", list(apps.keys()), index=0)

    page_name = apps[selected_page]

    # Display selected page
    if page_name == "home":
        show_home_page()
    elif page_name == "prompts":
        from apps.prompt_management import show_prompt_management

        show_prompt_management()
    elif page_name == "experiments":
        from apps.experiment_management import show_experiment_management

        show_experiment_management()
    elif page_name == "annotation_setup":
        from apps.annotation_setup import show_annotation_setup

        show_annotation_setup()
    elif page_name == "labeling":
        from apps.labeling_interface import show_labeling_interface

        show_labeling_interface()
    elif page_name == "results":
        from apps.results_analysis import show_results_analysis

        show_results_analysis()
    elif page_name == "disagreement_review":
        from apps.disagreement_review import show_disagreement_review

        show_disagreement_review()


def show_home_page():
    """Display the home page."""
    st.markdown("""
    ## Welcome to Astra Annotator

    This platform helps you create and manage expert annotations for LLM claims in deception-benchmark contexts.

    ### Workflow Overview:

    1. **📝 Prompt Management**: Create and organize claim context by scenario
    2. **🧪 Experiment Management**: Run prompts through multiple LLM models
    3. **⚙️ Annotation Setup**: Configure assessment categories and labeling guidelines
    4. **🏷️ Labeling Interface**: Blind annotation interface for expert reviewers
    5. **📊 Results Analysis**: Statistical analysis and inter-rater reliability metrics

    ### Quick Start:

    - **New User**: Start with Prompt Management to import or create your prompt dataset
    - **Existing Data**: Go to Experiment Management to run LLM evaluations
    - **Labelers**: Use the Labeling Interface with your assigned initials
    - **Researchers**: Check Results Analysis for progress and statistics

    ### Database Status:
    """)

    # Show database info
    try:
        from core.database import DatabaseManager

        db = DatabaseManager(st.session_state.db_path)

        # Get basic stats
        prompt_groups = db.get_prompt_groups()
        prompts = db.get_prompts()
        experiments = db.get_experiments()

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Prompt Groups", len(prompt_groups))

        with col2:
            st.metric("Total Prompts", len(prompts))

        with col3:
            st.metric("Experiments", len(experiments))

        st.success(f"✅ Database connected: `{st.session_state.db_path}`")

    except Exception as e:
        st.error(f"❌ Database error: {e}")
        st.info("💡 Try running the app to initialize the database.")


if __name__ == "__main__":
    main()
