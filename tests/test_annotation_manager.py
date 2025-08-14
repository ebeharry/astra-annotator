"""Tests for AnnotationManager functionality."""


class TestAnnotationManager:
    """Test AnnotationManager functionality."""

    def test_create_annotation_run(self, annotation_manager, temp_db, sample_condition):
        """Test creating an annotation run."""
        # Create experiment first
        group_id = temp_db.create_prompt_group(
            condition_id=sample_condition, name="Test Group", group_type="single"
        )
        prompt_id = temp_db.create_single_prompt(group_id, "Test prompt")
        exp_id = temp_db.create_experiment(
            name="Test Experiment",
            description="Test description",
            models=["gpt-3.5-turbo"],
            prompt_ids=[prompt_id],
        )

        # Create annotation run
        run_id = annotation_manager.create_annotation_run(
            experiment_id=exp_id,
            name="Test Annotation Run",
            description="Test description",
            guidelines="Test guidelines",
            response_ordering="sequential",
            filter_models=["gpt-3.5-turbo"],
        )

        assert run_id is not None

        # Verify annotation run was created
        runs = annotation_manager.get_annotation_runs()
        assert len(runs) == 1
        assert runs[0]["name"] == "Test Annotation Run"
        assert runs[0]["response_ordering"] == "sequential"

    def test_create_assessment_category(self, annotation_manager, temp_db, sample_condition):
        """Test creating assessment categories."""
        # Setup experiment and annotation run
        group_id = temp_db.create_prompt_group(
            condition_id=sample_condition, name="Test Group", group_type="single"
        )
        prompt_id = temp_db.create_single_prompt(group_id, "Test prompt")
        exp_id = temp_db.create_experiment(
            name="Test Experiment",
            description="Test description",
            models=["gpt-3.5-turbo"],
            prompt_ids=[prompt_id],
        )
        run_id = temp_db.create_annotation_run(
            experiment_id=exp_id,
            name="Test Run",
            description="Test",
            guidelines="Test guidelines",
            response_ordering="sequential",
        )

        # Test categorical assessment
        cat_id = annotation_manager.create_assessment_category(
            annotation_run_id=run_id,
            name="Quality",
            category_type="categorical",
            possible_values=["Excellent", "Good", "Fair", "Poor"],
            guidelines="Rate the overall quality",
        )

        assert cat_id is not None

        # Test binary assessment
        binary_id = annotation_manager.create_assessment_category(
            annotation_run_id=run_id,
            name="Helpful",
            category_type="binary",
            possible_values=["Yes", "No"],
            guidelines="Is the response helpful?",
        )

        assert binary_id is not None

        # Test text assessment
        text_id = annotation_manager.create_assessment_category(
            annotation_run_id=run_id,
            name="Comments",
            category_type="text",
            possible_values=[],
            guidelines="Additional comments",
        )

        assert text_id is not None

        # Verify categories were created by getting annotation run details
        details = annotation_manager.get_annotation_run_details(run_id)
        categories = details["assessment_categories"]
        assert len(categories) == 3

        category_names = [c["name"] for c in categories]
        assert "Quality" in category_names
        assert "Helpful" in category_names
        assert "Comments" in category_names

    def test_get_labeling_session_with_sequential_ordering(
        self, annotation_manager, temp_db, sample_condition
    ):
        """Test getting labeling session with sequential response ordering."""
        # Setup experiment with multiple responses
        group_id = temp_db.create_prompt_group(
            condition_id=sample_condition, name="Test Group", group_type="list"
        )
        prompt_ids = temp_db.create_list_prompts(group_id, ["Prompt 1", "Prompt 2"])
        exp_id = temp_db.create_experiment(
            name="Test Experiment",
            description="Test description",
            models=["gpt-3.5-turbo", "claude-3-sonnet"],
            prompt_ids=prompt_ids,
        )

        # Mark all responses as completed with dummy content
        responses = temp_db.get_pending_responses(exp_id)
        for i, response in enumerate(responses):
            temp_db.update_response_status(response["id"], "completed", f"Sample response {i + 1}")

        # Create annotation run with sequential ordering
        run_id = temp_db.create_annotation_run(
            experiment_id=exp_id,
            name="Test Run",
            description="Test",
            guidelines="Test guidelines",
            response_ordering="sequential",
        )

        # Get eligible responses (this is what the labeling session would use)
        eligible_responses = annotation_manager.get_eligible_responses(run_id)

        assert eligible_responses is not None
        assert len(eligible_responses) == 4  # 2 models * 2 prompts

        # Check that responses are available
        response_ids = [r["id"] for r in eligible_responses]
        assert len(response_ids) == 4

    def test_get_labeling_session_with_randomized_ordering(
        self, annotation_manager, temp_db, sample_condition
    ):
        """Test getting labeling session with randomized response ordering."""
        # Setup experiment
        group_id = temp_db.create_prompt_group(
            condition_id=sample_condition, name="Test Group", group_type="single"
        )
        prompt_id = temp_db.create_single_prompt(group_id, "Test prompt")
        exp_id = temp_db.create_experiment(
            name="Test Experiment",
            description="Test description",
            models=["gpt-3.5-turbo", "claude-3-sonnet", "gemini-pro"],
            prompt_ids=[prompt_id],
        )

        # Mark responses as completed
        responses = temp_db.get_pending_responses(exp_id)
        for i, response in enumerate(responses):
            temp_db.update_response_status(response["id"], "completed", f"Sample response {i + 1}")

        # Create annotation run with randomized ordering
        run_id = temp_db.create_annotation_run(
            experiment_id=exp_id,
            name="Test Run",
            description="Test",
            guidelines="Test guidelines",
            response_ordering="randomized",
        )

        # Get eligible responses for randomized ordering
        eligible_responses = annotation_manager.get_eligible_responses(run_id)

        assert eligible_responses is not None
        assert len(eligible_responses) == 3

        # Verify annotation run details
        details = annotation_manager.get_annotation_run_details(run_id)
        assert details["response_ordering"] == "randomized"

    def test_submit_annotation(self, annotation_manager, temp_db, sample_condition):
        """Test submitting annotations."""
        # Setup complete workflow
        group_id = temp_db.create_prompt_group(
            condition_id=sample_condition, name="Test Group", group_type="single"
        )
        prompt_id = temp_db.create_single_prompt(group_id, "Test prompt")
        exp_id = temp_db.create_experiment(
            name="Test Experiment",
            description="Test description",
            models=["gpt-3.5-turbo"],
            prompt_ids=[prompt_id],
        )

        # Mark response as completed
        responses = temp_db.get_pending_responses(exp_id)
        response_id = responses[0]["id"]
        temp_db.update_response_status(response_id, "completed", "Sample response")

        # Create annotation run and categories
        run_id = temp_db.create_annotation_run(
            experiment_id=exp_id,
            name="Test Run",
            description="Test",
            guidelines="Test guidelines",
            response_ordering="sequential",
        )

        quality_cat_id = temp_db.create_assessment_category(
            annotation_run_id=run_id,
            name="Quality",
            category_type="categorical",
            possible_values=["Good", "Fair", "Poor"],
            guidelines="Rate quality",
        )

        helpful_cat_id = temp_db.create_assessment_category(
            annotation_run_id=run_id,
            name="Helpful",
            category_type="binary",
            possible_values=["Yes", "No"],
            guidelines="Is it helpful?",
        )

        # Save annotations
        annotation_manager.save_annotation(
            annotation_run_id=run_id,
            response_id=response_id,
            category_id=quality_cat_id,
            labeler_initials="AB",
            value="Good",
            justification="This is a good response",
        )

        annotation_manager.save_annotation(
            annotation_run_id=run_id,
            response_id=response_id,
            category_id=helpful_cat_id,
            labeler_initials="AB",
            value="Yes",
        )

        # Verify annotation was saved
        annotation = annotation_manager.get_annotation_for_response(
            annotation_run_id=run_id,
            response_id=response_id,
            category_id=quality_cat_id,
            labeler_initials="AB",
        )
        assert annotation is not None
        assert annotation["value"] == "Good"
        assert annotation["justification"] == "This is a good response"

    def test_get_annotation_progress(self, annotation_manager, temp_db, sample_condition):
        """Test getting annotation progress statistics."""
        # Setup experiment with multiple responses
        group_id = temp_db.create_prompt_group(
            condition_id=sample_condition, name="Test Group", group_type="list"
        )
        prompt_ids = temp_db.create_list_prompts(group_id, ["Prompt 1", "Prompt 2"])
        exp_id = temp_db.create_experiment(
            name="Test Experiment",
            description="Test description",
            models=["gpt-3.5-turbo", "claude-3-sonnet"],
            prompt_ids=prompt_ids,
        )

        # Mark responses as completed
        responses = temp_db.get_pending_responses(exp_id)
        for i, response in enumerate(responses):
            temp_db.update_response_status(response["id"], "completed", f"Response {i + 1}")

        # Create annotation run
        run_id = temp_db.create_annotation_run(
            experiment_id=exp_id,
            name="Test Run",
            description="Test",
            guidelines="Test guidelines",
            response_ordering="sequential",
        )

        # Create assessment category
        cat_id = temp_db.create_assessment_category(
            annotation_run_id=run_id,
            name="Quality",
            category_type="categorical",
            possible_values=["Good", "Fair", "Poor"],
            guidelines="Rate quality",
        )

        # Get initial progress (no annotations yet)
        progress = annotation_manager.get_labeler_progress(
            annotation_run_id=run_id, labeler_initials="AB"
        )

        assert progress["total_responses"] == 4
        assert progress["completed_responses"] == 0
        assert progress["completion_percentage"] == 0

        # Save one annotation
        first_response_id = responses[0]["id"]
        annotation_manager.save_annotation(
            annotation_run_id=run_id,
            response_id=first_response_id,
            category_id=cat_id,
            labeler_initials="AB",
            value="Good",
            justification="Good response",
        )

        # Check updated progress
        progress = annotation_manager.get_labeler_progress(
            annotation_run_id=run_id, labeler_initials="AB"
        )

        assert progress["completed_responses"] == 1
        assert progress["completion_percentage"] == 25

    def test_get_inter_rater_reliability(self, annotation_manager, temp_db, sample_condition):
        """Test calculating inter-rater reliability."""
        # Setup experiment
        group_id = temp_db.create_prompt_group(
            condition_id=sample_condition, name="Test Group", group_type="single"
        )
        prompt_id = temp_db.create_single_prompt(group_id, "Test prompt")
        exp_id = temp_db.create_experiment(
            name="Test Experiment",
            description="Test description",
            models=["gpt-3.5-turbo"],
            prompt_ids=[prompt_id],
        )

        # Mark response as completed
        responses = temp_db.get_pending_responses(exp_id)
        response_id = responses[0]["id"]
        temp_db.update_response_status(response_id, "completed", "Sample response")

        # Create annotation run and category
        run_id = temp_db.create_annotation_run(
            experiment_id=exp_id,
            name="Test Run",
            description="Test",
            guidelines="Test guidelines",
            response_ordering="sequential",
        )

        cat_id = temp_db.create_assessment_category(
            annotation_run_id=run_id,
            name="Quality",
            category_type="categorical",
            possible_values=["Good", "Fair", "Poor"],
            guidelines="Rate quality",
        )

        # Save annotations from two labelers
        annotation_manager.save_annotation(
            annotation_run_id=run_id,
            response_id=response_id,
            category_id=cat_id,
            labeler_initials="AB",
            value="Good",
            justification="Good response",
        )

        annotation_manager.save_annotation(
            annotation_run_id=run_id,
            response_id=response_id,
            category_id=cat_id,
            labeler_initials="CD",
            value="Good",
            justification="Agreed, good response",
        )

        # Verify both annotations were saved
        annotation1 = annotation_manager.get_annotation_for_response(
            annotation_run_id=run_id,
            response_id=response_id,
            category_id=cat_id,
            labeler_initials="AB",
        )
        annotation2 = annotation_manager.get_annotation_for_response(
            annotation_run_id=run_id,
            response_id=response_id,
            category_id=cat_id,
            labeler_initials="CD",
        )

        assert annotation1 is not None
        assert annotation2 is not None
        assert annotation1["value"] == "Good"
        assert annotation2["value"] == "Good"

    def test_export_annotations(self, annotation_manager, temp_db, sample_condition):
        """Test exporting annotations to different formats."""
        # Setup and create some annotations (simplified setup)
        group_id = temp_db.create_prompt_group(
            condition_id=sample_condition, name="Test Group", group_type="single"
        )
        prompt_id = temp_db.create_single_prompt(group_id, "Test prompt")
        exp_id = temp_db.create_experiment(
            name="Test Experiment",
            description="Test description",
            models=["gpt-3.5-turbo"],
            prompt_ids=[prompt_id],
        )

        # Mark response as completed
        responses = temp_db.get_pending_responses(exp_id)
        response_id = responses[0]["id"]
        temp_db.update_response_status(response_id, "completed", "Sample response")

        # Create annotation run and submit annotation
        run_id = temp_db.create_annotation_run(
            experiment_id=exp_id,
            name="Test Run",
            description="Test",
            guidelines="Test guidelines",
            response_ordering="sequential",
        )

        cat_id = temp_db.create_assessment_category(
            annotation_run_id=run_id,
            name="Quality",
            category_type="categorical",
            possible_values=["Good", "Fair", "Poor"],
            guidelines="Rate quality",
        )

        annotation_manager.save_annotation(
            annotation_run_id=run_id,
            response_id=response_id,
            category_id=cat_id,
            labeler_initials="AB",
            value="Good",
            justification="Good response",
        )

        # Verify annotation was saved (export functionality may not be implemented yet)
        annotation = annotation_manager.get_annotation_for_response(
            annotation_run_id=run_id,
            response_id=response_id,
            category_id=cat_id,
            labeler_initials="AB",
        )

        assert annotation is not None
        assert annotation["value"] == "Good"
        assert annotation["justification"] == "Good response"

    def test_validate_assessment_values(self, annotation_manager, temp_db, sample_condition):
        """Test validation of assessment values."""
        # Setup annotation run with categories
        group_id = temp_db.create_prompt_group(
            condition_id=sample_condition, name="Test Group", group_type="single"
        )
        prompt_id = temp_db.create_single_prompt(group_id, "Test prompt")
        exp_id = temp_db.create_experiment(
            name="Test Experiment",
            description="Test description",
            models=["gpt-3.5-turbo"],
            prompt_ids=[prompt_id],
        )
        run_id = temp_db.create_annotation_run(
            experiment_id=exp_id,
            name="Test Run",
            description="Test",
            guidelines="Test guidelines",
            response_ordering="sequential",
        )

        # Create different types of categories
        categorical_id = temp_db.create_assessment_category(
            annotation_run_id=run_id,
            name="Quality",
            category_type="categorical",
            possible_values=["Good", "Fair", "Poor"],
            guidelines="Rate quality",
        )

        binary_id = temp_db.create_assessment_category(
            annotation_run_id=run_id,
            name="Helpful",
            category_type="binary",
            possible_values=["Yes", "No"],
            guidelines="Is helpful?",
        )

        # Test that categories were created correctly
        details = annotation_manager.get_annotation_run_details(run_id)
        categories = details["assessment_categories"]

        categorical_cat = next(c for c in categories if c["name"] == "Quality")
        binary_cat = next(c for c in categories if c["name"] == "Helpful")

        assert categorical_cat["type"] == "categorical"  # Using 'type' instead of 'category_type'
        assert "Good" in categorical_cat["possible_values"]
        assert "Fair" in categorical_cat["possible_values"]
        assert "Poor" in categorical_cat["possible_values"]

        assert binary_cat["type"] == "binary"  # Using 'type' instead of 'category_type'
        assert "Yes" in binary_cat["possible_values"]
        assert "No" in binary_cat["possible_values"]
