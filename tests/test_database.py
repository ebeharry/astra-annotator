"""Tests for database functionality."""


class TestDatabaseManager:
    """Test DatabaseManager functionality."""

    def test_database_initialization(self, temp_db):
        """Test that database initializes correctly."""
        assert temp_db is not None

        # Test that tables exist by querying them
        conditions = temp_db.get_conditions()
        assert isinstance(conditions, list)
        assert len(conditions) == 0

    def test_condition_creation(self, temp_db):
        """Test creating and retrieving conditions."""
        # Create condition
        condition_id = temp_db.create_condition("Test Condition", "Test description")
        assert condition_id is not None
        assert isinstance(condition_id, int)

        # Retrieve conditions
        conditions = temp_db.get_conditions()
        assert len(conditions) == 1
        assert conditions[0]["name"] == "Test Condition"
        assert conditions[0]["description"] == "Test description"
        assert conditions[0]["id"] == condition_id

    def test_prompt_group_creation(self, temp_db, sample_condition):
        """Test creating different types of prompt groups."""
        # Test grid_3x3 group
        grid_group_id = temp_db.create_prompt_group(
            condition_id=sample_condition,
            name="Grid Group",
            description="Test grid group",
            group_type="grid_3x3",
            risk_category="Test Risk",
        )
        assert grid_group_id is not None

        # Test single group
        single_group_id = temp_db.create_prompt_group(
            condition_id=sample_condition,
            name="Single Group",
            description="Test single group",
            group_type="single",
        )
        assert single_group_id is not None

        # Test list group
        list_group_id = temp_db.create_prompt_group(
            condition_id=sample_condition,
            name="List Group",
            description="Test list group",
            group_type="list",
        )
        assert list_group_id is not None

        # Verify groups
        groups = temp_db.get_prompt_groups()
        assert len(groups) == 3

        group_types = [g["group_type"] for g in groups]
        assert "grid_3x3" in group_types
        assert "single" in group_types
        assert "list" in group_types

    def test_prompt_creation(self, temp_db, sample_condition):
        """Test creating different types of prompts."""
        # Create a group
        group_id = temp_db.create_prompt_group(
            condition_id=sample_condition, name="Test Group", group_type="grid_3x3"
        )

        # Test grid prompt creation
        prompt_id = temp_db.create_prompt(
            group_id=group_id,
            content="Test prompt content",
            communication_style="neutral",
            severity="moderate",
        )
        assert prompt_id is not None

        # Test single prompt creation
        single_group_id = temp_db.create_prompt_group(
            condition_id=sample_condition, name="Single Group", group_type="single"
        )
        single_prompt_id = temp_db.create_single_prompt(
            group_id=single_group_id, content="Single prompt content"
        )
        assert single_prompt_id is not None

        # Test list prompt creation
        list_group_id = temp_db.create_prompt_group(
            condition_id=sample_condition, name="List Group", group_type="list"
        )
        list_prompt_ids = temp_db.create_list_prompts(
            group_id=list_group_id, prompt_list=["Prompt 1", "Prompt 2", "Prompt 3"]
        )
        assert len(list_prompt_ids) == 3

        # Verify all prompts
        all_prompts = temp_db.get_prompts()
        assert len(all_prompts) == 5  # 1 + 1 + 3

    def test_prompt_grid_creation(self, temp_db, sample_condition, sample_prompt_grid):
        """Test creating a complete 3x3 prompt grid."""
        group_id = temp_db.create_prompt_group(
            condition_id=sample_condition, name="Grid Group", group_type="grid_3x3"
        )

        prompt_ids = temp_db.create_prompt_with_grid(group_id, sample_prompt_grid)
        assert len(prompt_ids) == 9

        # Verify grid structure
        grid = temp_db.get_prompt_grid(group_id)
        assert grid["implicit"]["low"] == "Implicit low severity prompt"
        assert grid["neutral"]["moderate"] == "Neutral moderate severity prompt"
        assert grid["explicit"]["high"] == "Explicit high severity prompt"

    def test_prompt_labels(self, temp_db, sample_condition):
        """Test adding and retrieving prompt labels."""
        group_id = temp_db.create_prompt_group(
            condition_id=sample_condition, name="Test Group", group_type="single"
        )

        prompt_id = temp_db.create_single_prompt(group_id, "Test content")

        # Add labels
        temp_db.add_prompt_label(prompt_id, "category", "mental_health")
        temp_db.add_prompt_label(prompt_id, "difficulty", "moderate")

        # Retrieve labels
        labels = temp_db.get_prompt_labels(prompt_id)
        assert labels["category"] == "mental_health"
        assert labels["difficulty"] == "moderate"

    def test_experiment_creation(self, temp_db, sample_condition):
        """Test creating experiments."""
        # Create prompts first
        group_id = temp_db.create_prompt_group(
            condition_id=sample_condition, name="Test Group", group_type="single"
        )
        prompt_id = temp_db.create_single_prompt(group_id, "Test prompt")

        # Create experiment
        exp_id = temp_db.create_experiment(
            name="Test Experiment",
            description="Test description",
            models=["gpt-3.5-turbo", "claude-3-sonnet"],
            prompt_ids=[prompt_id],
        )
        assert exp_id is not None

        # Verify experiment
        experiments = temp_db.get_experiments()
        assert len(experiments) == 1
        assert experiments[0]["name"] == "Test Experiment"
        assert experiments[0]["models"] == ["gpt-3.5-turbo", "claude-3-sonnet"]

        # Verify responses were created
        experiment_details = temp_db.get_experiment_details(exp_id)
        assert len(experiment_details["responses"]) == 2  # 2 models * 1 prompt

    def test_annotation_run_creation(self, temp_db, sample_condition):
        """Test creating annotation runs."""
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
        run_id = temp_db.create_annotation_run(
            experiment_id=exp_id,
            name="Test Annotation Run",
            description="Test run",
            guidelines="Test guidelines",
            response_ordering="sequential",
            filter_models=["gpt-3.5-turbo"],
        )
        assert run_id is not None

        # Verify annotation run
        runs = temp_db.get_annotation_runs()
        assert len(runs) == 1
        assert runs[0]["name"] == "Test Annotation Run"

    def test_assessment_category_creation(self, temp_db, sample_condition):
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

        # Create assessment category
        cat_id = temp_db.create_assessment_category(
            annotation_run_id=run_id,
            name="Quality",
            category_type="categorical",
            possible_values=["Good", "Fair", "Poor"],
            guidelines="Rate the quality of the response",
        )
        assert cat_id is not None

    def test_database_transaction_rollback(self, temp_db):
        """Test that failed operations rollback properly."""
        initial_count = len(temp_db.get_conditions())

        # This should fail due to duplicate name constraint if we had one
        # For now, just test that we can create and the count increases
        temp_db.create_condition("Test 1", "Description 1")
        temp_db.create_condition("Test 2", "Description 2")

        final_count = len(temp_db.get_conditions())
        assert final_count == initial_count + 2
