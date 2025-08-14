"""Database manager for Astra Annotator."""

import json
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional


class DatabaseManager:
    """Manages SQLite database operations for Astra Annotator."""

    def __init__(self, db_path: str = "astra_annotator.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize database with schema."""
        schema_path = Path(__file__).parent / "schema.sql"
        with open(schema_path) as f:
            schema_sql = f.read()

        with self.get_connection() as conn:
            conn.executescript(schema_sql)
            conn.commit()

    @contextmanager
    def get_connection(self):
        """Get database connection with proper cleanup."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def safe_database_operation(func):
        """Decorator for database operations with transaction management."""

        def wrapper(self, *args, **kwargs):
            with self.get_connection() as conn:
                try:
                    conn.execute("BEGIN")
                    result = func(self, conn, *args, **kwargs)
                    conn.commit()
                    return result
                except Exception as e:
                    conn.rollback()
                    logging.error(f"Database operation failed: {e}")
                    raise

        return wrapper

    # Condition Operations
    @safe_database_operation
    def create_condition(self, conn, name: str, description: str = None) -> int:
        """Create new condition and return ID."""
        cursor = conn.execute(
            """INSERT INTO conditions (name, description)
               VALUES (?, ?)""",
            (name, description),
        )
        return cursor.lastrowid

    def get_conditions(self) -> List[Dict]:
        """Retrieve all conditions."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM conditions ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]

    # Prompt Group Operations
    @safe_database_operation
    def create_prompt_group(
        self,
        conn,
        condition_id: int,
        name: str,
        description: str = None,
        group_type: str = "grid_3x3",
        risk_category: str = None,
        low_severity_explanation: str = None,
        moderate_severity_explanation: str = None,
        high_severity_explanation: str = None,
    ) -> int:
        """Create new prompt group and return ID."""
        cursor = conn.execute(
            """INSERT INTO prompt_groups (condition_id, name, description, group_type, risk_category,
                                        low_severity_explanation, moderate_severity_explanation, high_severity_explanation)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                condition_id,
                name,
                description,
                group_type,
                risk_category,
                low_severity_explanation,
                moderate_severity_explanation,
                high_severity_explanation,
            ),
        )
        return cursor.lastrowid

    def get_prompt_groups(self) -> List[Dict]:
        """Retrieve all prompt groups with condition info."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT pg.*, c.name as condition_name
                FROM prompt_groups pg
                JOIN conditions c ON pg.condition_id = c.id
                ORDER BY c.name, pg.name
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_risk_categories(self) -> List[str]:
        """Get all unique risk categories that have been used."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT DISTINCT risk_category
                FROM prompt_groups
                WHERE risk_category IS NOT NULL AND risk_category != ''
                ORDER BY risk_category
            """)
            return [row["risk_category"] for row in cursor.fetchall()]

    # Prompt Operations
    @safe_database_operation
    def create_prompt(
        self,
        conn,
        group_id: int,
        content: str,
        communication_style: str = None,
        severity: str = None,
        list_order: int = None,
    ) -> int:
        """Create new prompt and return ID."""
        cursor = conn.execute(
            """INSERT INTO prompts (group_id, content, communication_style, severity, list_order)
               VALUES (?, ?, ?, ?, ?)""",
            (group_id, content, communication_style, severity, list_order),
        )
        return cursor.lastrowid

    @safe_database_operation
    def create_prompt_with_grid(
        self, conn, group_id: int, prompt_grid: Dict[str, Dict[str, str]]
    ) -> List[int]:
        """Create a complete 3x3 grid of prompts for a group."""
        prompt_ids = []

        communication_styles = ["implicit", "neutral", "explicit"]
        severities = ["low", "moderate", "high"]

        for style in communication_styles:
            for severity in severities:
                content = prompt_grid.get(style, {}).get(severity, "")
                if content.strip():  # Only create if content exists
                    cursor = conn.execute(
                        """INSERT OR REPLACE INTO prompts (group_id, content, communication_style, severity)
                           VALUES (?, ?, ?, ?)""",
                        (group_id, content.strip(), style, severity),
                    )
                    prompt_ids.append(cursor.lastrowid)

        return prompt_ids

    @safe_database_operation
    def create_single_prompt(self, conn, group_id: int, content: str) -> int:
        """Create a single prompt for a 'single' type group."""
        cursor = conn.execute(
            """INSERT INTO prompts (group_id, content)
               VALUES (?, ?)""",
            (group_id, content),
        )
        return cursor.lastrowid

    @safe_database_operation
    def create_list_prompts(self, conn, group_id: int, prompt_list: List[str]) -> List[int]:
        """Create multiple prompts for a 'list' type group."""
        prompt_ids = []
        for i, content in enumerate(prompt_list):
            if content.strip():  # Only create if content exists
                cursor = conn.execute(
                    """INSERT INTO prompts (group_id, content, list_order)
                       VALUES (?, ?, ?)""",
                    (group_id, content.strip(), i + 1),
                )
                prompt_ids.append(cursor.lastrowid)
        return prompt_ids

    @safe_database_operation
    def add_prompt_label(self, conn, prompt_id: int, label_key: str, label_value: str):
        """Add or update a label for a prompt."""
        conn.execute(
            """INSERT OR REPLACE INTO prompt_labels (prompt_id, label_key, label_value)
               VALUES (?, ?, ?)""",
            (prompt_id, label_key, label_value),
        )

    def get_prompt_labels(self, prompt_id: int) -> Dict[str, str]:
        """Get all labels for a prompt."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT label_key, label_value FROM prompt_labels WHERE prompt_id = ?", (prompt_id,)
            )
            return {row["label_key"]: row["label_value"] for row in cursor.fetchall()}

    def get_prompts(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Retrieve prompts with optional filtering."""
        query = """
            SELECT p.*, pg.name as group_name, pg.condition_id, pg.group_type,
                   c.name as condition_name
            FROM prompts p
            JOIN prompt_groups pg ON p.group_id = pg.id
            JOIN conditions c ON pg.condition_id = c.id
        """
        params = []

        if filters:
            conditions = []
            if "communication_style" in filters:
                conditions.append("p.communication_style = ?")
                params.append(filters["communication_style"])
            if "severity" in filters:
                conditions.append("p.severity = ?")
                params.append(filters["severity"])
            if "group_id" in filters:
                conditions.append("p.group_id = ?")
                params.append(filters["group_id"])
            if "condition_id" in filters:
                conditions.append("pg.condition_id = ?")
                params.append(filters["condition_id"])

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

        query += """ ORDER BY c.name, pg.name,
                     CASE pg.group_type
                         WHEN 'grid_3x3' THEN
                             CASE p.severity WHEN 'low' THEN 1 WHEN 'moderate' THEN 2 WHEN 'high' THEN 3 END * 10 +
                             CASE p.communication_style WHEN 'implicit' THEN 1 WHEN 'neutral' THEN 2 WHEN 'explicit' THEN 3 END
                         WHEN 'list' THEN COALESCE(p.list_order, 999)
                         ELSE 1
                     END"""

        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            prompts = [dict(row) for row in cursor.fetchall()]

            # Add labels for each prompt
            for prompt in prompts:
                prompt["labels"] = self.get_prompt_labels(prompt["id"])

            return prompts

    def get_prompt_grid(self, group_id: int) -> Dict[str, Dict[str, str]]:
        """Get prompts organized as a 3x3 grid for a group."""
        prompts = self.get_prompts({"group_id": group_id})

        grid = {
            "implicit": {"low": "", "moderate": "", "high": ""},
            "neutral": {"low": "", "moderate": "", "high": ""},
            "explicit": {"low": "", "moderate": "", "high": ""},
        }

        for prompt in prompts:
            style = prompt["communication_style"]
            severity = prompt["severity"]
            grid[style][severity] = prompt["content"]

        return grid

    # Experiment Operations
    @safe_database_operation
    def create_experiment(
        self, conn, name: str, description: str, models: List[str], prompt_ids: List[int]
    ) -> int:
        """Create experiment and return ID."""
        cursor = conn.execute(
            """INSERT INTO experiments (name, description, models)
               VALUES (?, ?, ?)""",
            (name, description, json.dumps(models)),
        )
        experiment_id = cursor.lastrowid

        # Add prompt associations
        for prompt_id in prompt_ids:
            conn.execute(
                """INSERT INTO experiment_prompts (experiment_id, prompt_id)
                   VALUES (?, ?)""",
                (experiment_id, prompt_id),
            )

        # Create initial LLM response records
        for prompt_id in prompt_ids:
            for model in models:
                conn.execute(
                    """INSERT INTO llm_responses (experiment_id, prompt_id, model)
                       VALUES (?, ?, ?)""",
                    (experiment_id, prompt_id, model),
                )

        return experiment_id

    def get_experiments(self) -> List[Dict]:
        """Retrieve all experiments."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM experiments ORDER BY created_at DESC")
            experiments = [dict(row) for row in cursor.fetchall()]

            for experiment in experiments:
                experiment["models"] = json.loads(experiment["models"])

            return experiments

    def get_experiment_details(self, experiment_id: int) -> Dict:
        """Get detailed experiment information including prompts and responses."""
        with self.get_connection() as conn:
            # Get experiment
            cursor = conn.execute("SELECT * FROM experiments WHERE id = ?", (experiment_id,))
            experiment = dict(cursor.fetchone())
            experiment["models"] = json.loads(experiment["models"])

            # Get prompts
            cursor = conn.execute(
                """SELECT p.*, pg.name as group_name
                   FROM prompts p
                   JOIN prompt_groups pg ON p.group_id = pg.id
                   JOIN experiment_prompts ep ON p.id = ep.prompt_id
                   WHERE ep.experiment_id = ?""",
                (experiment_id,),
            )
            experiment["prompts"] = [dict(row) for row in cursor.fetchall()]

            # Get responses
            cursor = conn.execute(
                """SELECT * FROM llm_responses WHERE experiment_id = ?""", (experiment_id,)
            )
            experiment["responses"] = [dict(row) for row in cursor.fetchall()]

            return experiment

    @safe_database_operation
    def update_experiment_status(self, conn, experiment_id: int, status: str):
        """Update experiment status."""
        conn.execute("UPDATE experiments SET status = ? WHERE id = ?", (status, experiment_id))

    # LLM Response Operations
    @safe_database_operation
    def update_response_status(
        self,
        conn,
        response_id: int,
        status: str,
        response_text: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        """Update LLM response status and content."""
        params = [status]
        query = "UPDATE llm_responses SET status = ?"

        if response_text is not None:
            query += ", response_text = ?"
            params.append(response_text)

        if error_message is not None:
            query += ", error_message = ?"
            params.append(error_message)

        if status == "completed":
            query += ", completed_at = CURRENT_TIMESTAMP"

        query += " WHERE id = ?"
        params.append(response_id)

        conn.execute(query, params)

    def get_pending_responses(self, experiment_id: int) -> List[Dict]:
        """Get all pending responses for an experiment."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """SELECT lr.*, p.content as prompt_content
                   FROM llm_responses lr
                   JOIN prompts p ON lr.prompt_id = p.id
                   WHERE lr.experiment_id = ? AND lr.status = 'pending'""",
                (experiment_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    # Annotation Operations
    @safe_database_operation
    def create_annotation_run(
        self,
        conn,
        experiment_id: int,
        name: str,
        description: str,
        guidelines: str,
        response_ordering: str,
        filter_models: List[str] = None,
        filter_conditions: List[str] = None,
    ) -> int:
        """Create annotation run and return ID."""
        cursor = conn.execute(
            """INSERT INTO annotation_runs
               (experiment_id, name, description, guidelines, response_ordering, filter_models, filter_conditions)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                experiment_id,
                name,
                description,
                guidelines,
                response_ordering,
                json.dumps(filter_models) if filter_models else None,
                json.dumps(filter_conditions) if filter_conditions else None,
            ),
        )
        return cursor.lastrowid

    @safe_database_operation
    def create_assessment_category(
        self,
        conn,
        annotation_run_id: int,
        name: str,
        category_type: str,
        possible_values: List[str] = None,
        guidelines: str = None,
        display_order: int = None,
    ) -> int:
        """Create assessment category and return ID."""
        cursor = conn.execute(
            """INSERT INTO assessment_categories
               (annotation_run_id, name, type, possible_values, guidelines, display_order)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                annotation_run_id,
                name,
                category_type,
                json.dumps(possible_values) if possible_values else None,
                guidelines,
                display_order,
            ),
        )
        return cursor.lastrowid

    @safe_database_operation
    def assign_labeler(self, conn, annotation_run_id: int, labeler_initials: str):
        """Assign labeler to annotation run."""
        conn.execute(
            """INSERT OR IGNORE INTO labeler_assignments (annotation_run_id, labeler_initials)
               VALUES (?, ?)""",
            (annotation_run_id, labeler_initials),
        )

    @safe_database_operation
    def save_annotation(
        self,
        conn,
        annotation_run_id: int,
        response_id: int,
        category_id: int,
        labeler_initials: str,
        value: str,
        justification: str = None,
    ):
        """Save or update annotation."""
        conn.execute(
            """INSERT OR REPLACE INTO annotations
               (annotation_run_id, response_id, category_id, labeler_initials, value, justification, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (annotation_run_id, response_id, category_id, labeler_initials, value, justification),
        )

    def get_annotation_runs(self) -> List[Dict]:
        """Get all annotation runs."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """SELECT ar.*, e.name as experiment_name
                   FROM annotation_runs ar
                   JOIN experiments e ON ar.experiment_id = e.id
                   ORDER BY ar.created_at DESC"""
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_annotation_progress(self, annotation_run_id: int) -> Dict:
        """Get annotation progress statistics."""
        with self.get_connection() as conn:
            # Get total responses in annotation run
            cursor = conn.execute(
                """SELECT COUNT(*) as total FROM llm_responses lr
                   JOIN annotation_runs ar ON lr.experiment_id = ar.experiment_id
                   WHERE ar.id = ? AND lr.status = 'completed'""",
                (annotation_run_id,),
            )
            total_responses = cursor.fetchone()["total"]

            # Get completed annotations by labeler
            cursor = conn.execute(
                """SELECT labeler_initials, COUNT(DISTINCT response_id) as completed
                   FROM annotations
                   WHERE annotation_run_id = ?
                   GROUP BY labeler_initials""",
                (annotation_run_id,),
            )
            labeler_progress = {
                row["labeler_initials"]: row["completed"] for row in cursor.fetchall()
            }

            return {"total_responses": total_responses, "labeler_progress": labeler_progress}
