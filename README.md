# Astra Annotator

A Streamlit-based mental health LLM evaluation platform that enables teams of software engineers and psychiatrists to create expert annotations for LLM responses. The system supports a complete workflow from prompt creation through statistical analysis.

## Features

- **Flexible Prompt Management**: Support for single prompts, list prompts, and systematic 3x3 grids (communication style × severity)
- **Multi-LLM Experiments**: Integration with OpenAI, Claude, Grok, Gemini, and Ollama
- **Blind Annotation Interface**: Unbiased evaluation with session resumption and progress tracking
- **Inter-Rater Reliability**: Statistical analysis including Cohen's Kappa and percent agreement
- **Comprehensive Export**: CSV, JSON, and Excel formats for further analysis

## Workflow Overview

1. **Prompt Management**: Create and organize prompts by condition and type
2. **Experiment Execution**: Run prompts through multiple LLM models
3. **Annotation Setup**: Configure assessment categories and assign labelers
4. **Blind Labeling**: Annotate responses without bias
5. **Results Analysis**: Generate statistics and export results

## Quick Start

### Prerequisites

- Python 3.9 or higher
- [uv](https://docs.astral.sh/uv/) package manager

### Installation

1. Clone the repository:
```bash
git clone https://github.com/duncaneddy/astra-annotator
cd astra-annotator
```

2. Install dependencies:
```bash
uv sync --dev
```

3. Set up pre-commit hooks (optional, for development):
```bash
uv run pre-commit install
```

4. Run the application:
```bash
uv run streamlit run app.py
```

The application will be available at `http://localhost:8051`

### Configuration

Set up your LLM provider API keys as environment variables:

```bash
export OPENAI_API_KEY="your-openai-key"
export ANTHROPIC_API_KEY="your-claude-key"
export GEMINI_API_KEY="your-gemini-key"
export GROK_API_KEY="your-grok-key"
```

Or provide them through the application interface.

### Code Quality

This project uses several tools to maintain code quality:

```bash
# Format code
uv run ruff format

# Lint code
uv run ruff check

# Type checking
uv run mypy .
```

### Pre-commit Hooks

The project uses pre-commit hooks to ensure code quality. These are automatically installed if you follow the installation steps above.

Manual installation:
```bash
uv run pre-commit install
```

Run hooks manually:
```bash
uv run pre-commit run --all-files
```

### Development Workflow

The pre-commit hooks will automatically run the following checks on every commit:

- **Ruff formatting**: Automatically formats code
- **Ruff linting**: Checks for code quality issues and fixes them when possible
- **Basic checks**: Trailing whitespace, file endings, YAML syntax, merge conflicts, etc.

Note: MyPy type checking can be run manually with `uv run mypy .` for more comprehensive analysis.

## Architecture

- **Database**: SQLite with ACID transaction management
- **UI**: Streamlit multi-page application
- **LLM Integration**: Unified interface for multiple providers
- **Data Export**: Multiple formats with configurable options

## License

MIT License - see [LICENSE](LICENSE) file for details.
