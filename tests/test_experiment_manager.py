"""Tests for ExperimentManager functionality."""

from unittest.mock import AsyncMock, patch

import pytest


class TestExperimentManager:
    """Test ExperimentManager functionality."""

    def test_create_experiment(self, experiment_manager, temp_db, sample_condition):
        """Test creating an experiment."""
        # Create some prompts first
        group_id = temp_db.create_prompt_group(
            condition_id=sample_condition, name="Test Group", group_type="single"
        )
        prompt_id = temp_db.create_single_prompt(group_id, "Test prompt")

        # Create experiment
        exp_id = experiment_manager.create_experiment(
            name="Test Experiment",
            description="Test description",
            models=["gpt-3.5-turbo", "claude-3-sonnet"],
            prompt_ids=[prompt_id],
        )

        assert exp_id is not None

        # Verify experiment was created
        experiments = experiment_manager.get_experiments()
        assert len(experiments) == 1
        assert experiments[0]["name"] == "Test Experiment"
        assert experiments[0]["models"] == ["gpt-3.5-turbo", "claude-3-sonnet"]

    def test_get_experiment_details(self, experiment_manager, temp_db, sample_condition):
        """Test retrieving detailed experiment information."""
        # Create prompts and experiment
        group_id = temp_db.create_prompt_group(
            condition_id=sample_condition, name="Test Group", group_type="single"
        )
        prompt_id = temp_db.create_single_prompt(group_id, "Test prompt")

        exp_id = experiment_manager.create_experiment(
            name="Test Experiment",
            description="Test description",
            models=["gpt-3.5-turbo"],
            prompt_ids=[prompt_id],
        )

        # Get details
        details = experiment_manager.get_experiment_details(exp_id)

        assert details["name"] == "Test Experiment"
        assert details["description"] == "Test description"
        assert len(details["prompts"]) == 1
        assert len(details["responses"]) == 1  # 1 model * 1 prompt
        assert details["responses"][0]["status"] == "pending"

    def test_get_experiment_progress(self, experiment_manager, temp_db, sample_condition):
        """Test getting experiment progress statistics."""
        # Create prompts and experiment
        group_id = temp_db.create_prompt_group(
            condition_id=sample_condition, name="Test Group", group_type="list"
        )
        prompt_ids = temp_db.create_list_prompts(group_id, ["Prompt 1", "Prompt 2"])

        exp_id = experiment_manager.create_experiment(
            name="Test Experiment",
            description="Test description",
            models=["gpt-3.5-turbo", "claude-3-sonnet"],
            prompt_ids=prompt_ids,
        )

        # Get initial progress
        progress = experiment_manager.get_experiment_progress(exp_id)

        assert progress["experiment_id"] == exp_id
        assert progress["total_responses"] == 4  # 2 models * 2 prompts
        assert progress["completed"] == 0
        assert progress["failed"] == 0
        assert progress["pending"] == 4
        assert progress["completion_percentage"] == 0

        # Check by-model breakdown
        assert "gpt-3.5-turbo" in progress["by_model"]
        assert "claude-3-sonnet" in progress["by_model"]
        assert progress["by_model"]["gpt-3.5-turbo"]["total"] == 2
        assert progress["by_model"]["claude-3-sonnet"]["total"] == 2

    def test_provider_selection(self, experiment_manager):
        """Test that correct providers are selected for different models."""
        # Test OpenAI provider
        provider = experiment_manager._get_provider("gpt-3.5-turbo", {"openai": "test-key"})
        assert provider.__class__.__name__ == "OpenAIProvider"

        # Test Claude provider
        provider = experiment_manager._get_provider("claude-3-sonnet", {"anthropic": "test-key"})
        assert provider.__class__.__name__ == "ClaudeProvider"

        # Test Grok provider
        provider = experiment_manager._get_provider("grok-beta", {"xai": "test-key"})
        assert provider.__class__.__name__ == "GrokProvider"

        # Test Gemini provider
        provider = experiment_manager._get_provider("gemini-pro", {"google": "test-key"})
        assert provider.__class__.__name__ == "GeminiProvider"

        # Test Ollama provider
        provider = experiment_manager._get_provider("llama3", {})
        assert provider.__class__.__name__ == "OllamaProvider"

    def test_provider_selection_unknown_model(self, experiment_manager):
        """Test that unknown models raise ValueError."""
        with pytest.raises(ValueError, match="Unknown model"):
            experiment_manager._get_provider("unknown-model", {})

    @pytest.mark.asyncio
    async def test_process_single_response_success(self, experiment_manager, temp_db):
        """Test processing a single successful response."""
        # Mock the provider
        mock_provider = AsyncMock()
        mock_provider.generate_response.return_value = {
            "status": "success",
            "response": "This is a test response",
        }

        with patch.object(experiment_manager, "_get_provider", return_value=mock_provider):
            response_record = {"id": 1, "model": "gpt-3.5-turbo", "prompt_content": "Test prompt"}

            result = await experiment_manager._process_single_response(response_record)

            assert result["status"] == "completed"
            assert result["id"] == 1
            assert result["model"] == "gpt-3.5-turbo"

            # Verify the response was updated in database
            # (This would require checking the database, but we're testing the manager logic)

    @pytest.mark.asyncio
    async def test_process_single_response_failure(self, experiment_manager, temp_db):
        """Test processing a single failed response."""
        # Mock the provider to return failure
        mock_provider = AsyncMock()
        mock_provider.generate_response.return_value = {
            "status": "error",
            "error_message": "API rate limit exceeded",
        }

        with patch.object(experiment_manager, "_get_provider", return_value=mock_provider):
            response_record = {"id": 1, "model": "gpt-3.5-turbo", "prompt_content": "Test prompt"}

            result = await experiment_manager._process_single_response(response_record)

            assert result["status"] == "failed"
            assert result["error"] == "API rate limit exceeded"

    @pytest.mark.asyncio
    async def test_process_single_response_exception(self, experiment_manager):
        """Test processing response when provider raises exception."""
        # Mock the provider to raise an exception
        mock_provider = AsyncMock()
        mock_provider.generate_response.side_effect = Exception("Network error")

        with patch.object(experiment_manager, "_get_provider", return_value=mock_provider):
            response_record = {"id": 1, "model": "gpt-3.5-turbo", "prompt_content": "Test prompt"}

            result = await experiment_manager._process_single_response(response_record)

            assert result["status"] == "failed"
            assert "Network error" in result["error"]

    @pytest.mark.asyncio
    async def test_run_experiment_no_pending_responses(
        self, experiment_manager, temp_db, sample_condition
    ):
        """Test running experiment with no pending responses."""
        # Create experiment with completed responses
        group_id = temp_db.create_prompt_group(
            condition_id=sample_condition, name="Test Group", group_type="single"
        )
        prompt_id = temp_db.create_single_prompt(group_id, "Test prompt")

        exp_id = experiment_manager.create_experiment(
            name="Test Experiment",
            description="Test description",
            models=["gpt-3.5-turbo"],
            prompt_ids=[prompt_id],
        )

        # Mark response as completed
        responses = temp_db.get_pending_responses(exp_id)
        if responses:
            temp_db.update_response_status(responses[0]["id"], "completed", "Test response")

        # Run experiment
        result = await experiment_manager.run_experiment(exp_id)

        assert result["status"] == "completed"
        assert result["message"] == "No pending responses to process"

    @pytest.mark.asyncio
    async def test_run_experiment_with_responses(
        self, experiment_manager, temp_db, sample_condition
    ):
        """Test running experiment with pending responses."""
        # Create experiment
        group_id = temp_db.create_prompt_group(
            condition_id=sample_condition, name="Test Group", group_type="single"
        )
        prompt_id = temp_db.create_single_prompt(group_id, "Test prompt")

        exp_id = experiment_manager.create_experiment(
            name="Test Experiment",
            description="Test description",
            models=["gpt-3.5-turbo"],
            prompt_ids=[prompt_id],
        )

        # Mock successful processing
        with patch.object(experiment_manager, "_process_single_response") as mock_process:
            mock_process.return_value = {"status": "completed", "id": 1, "model": "gpt-3.5-turbo"}

            result = await experiment_manager.run_experiment(exp_id)

            assert result["status"] == "completed"
            assert result["completed"] == 1
            assert result["failed"] == 0
            assert result["total"] == 1

    def test_update_experiment_status(self, experiment_manager, temp_db, sample_condition):
        """Test updating experiment status."""
        # Create experiment
        group_id = temp_db.create_prompt_group(
            condition_id=sample_condition, name="Test Group", group_type="single"
        )
        prompt_id = temp_db.create_single_prompt(group_id, "Test prompt")

        exp_id = experiment_manager.create_experiment(
            name="Test Experiment",
            description="Test description",
            models=["gpt-3.5-turbo"],
            prompt_ids=[prompt_id],
        )

        # Update status
        temp_db.update_experiment_status(exp_id, "running")

        # Verify status update
        experiments = experiment_manager.get_experiments()
        assert experiments[0]["status"] == "running"
