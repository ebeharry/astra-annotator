"""Prompt management functionality."""

import json
import logging
from typing import Any, Dict, List

import pandas as pd

from core.database import DatabaseManager


class CSVValidator:
    """Validates CSV imports for prompts."""

    REQUIRED_COLUMNS = ["content", "condition"]
    OPTIONAL_COLUMNS = ["communication_style", "severity", "group_type", "list_order"]
    VALID_COMMUNICATION_STYLES = ["implicit", "neutral", "explicit"]
    VALID_SEVERITIES = ["low", "moderate", "high"]
    VALID_GROUP_TYPES = ["grid_3x3", "single", "list"]

    def validate_csv(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Validate CSV data for prompt import."""
        errors = []
        warnings = []

        # Check required columns
        missing_cols = set(self.REQUIRED_COLUMNS) - set(df.columns)
        if missing_cols:
            errors.append(f"Missing required columns: {missing_cols}")

        if errors:
            return {"valid": False, "errors": errors, "warnings": warnings}

        # Validate enum values (only if columns exist)
        if "communication_style" in df.columns:
            invalid_styles = df[
                df["communication_style"].notna()
                & ~df["communication_style"].isin(self.VALID_COMMUNICATION_STYLES)
            ]
            if not invalid_styles.empty:
                errors.append(
                    f"Invalid communication styles found: {invalid_styles['communication_style'].unique()}"
                )

        if "severity" in df.columns:
            invalid_severities = df[
                df["severity"].notna() & ~df["severity"].isin(self.VALID_SEVERITIES)
            ]
            if not invalid_severities.empty:
                errors.append(
                    f"Invalid severities found: {invalid_severities['severity'].unique()}"
                )

        if "group_type" in df.columns:
            invalid_types = df[
                df["group_type"].notna() & ~df["group_type"].isin(self.VALID_GROUP_TYPES)
            ]
            if not invalid_types.empty:
                errors.append(f"Invalid group types found: {invalid_types['group_type'].unique()}")

        # Check for empty content
        empty_content = df[df["content"].isna() | (df["content"].str.strip() == "")]
        if not empty_content.empty:
            errors.append(f"Found {len(empty_content)} rows with empty content")

        # Check for empty conditions
        empty_conditions = df[df["condition"].isna() | (df["condition"].str.strip() == "")]
        if not empty_conditions.empty:
            errors.append(f"Found {len(empty_conditions)} rows with empty condition")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


class PromptManager:
    """Manages prompt operations and statistics."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.csv_validator = CSVValidator()

    def import_prompts_from_csv(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Import prompts from CSV DataFrame."""
        # Validate CSV
        validation_result = self.csv_validator.validate_csv(df)
        if not validation_result["valid"]:
            return validation_result

        try:
            imported_prompts = 0
            created_groups = 0

            # Determine grouping strategy based on available columns
            if "group_name" in df.columns:
                # Group by condition and group_name
                group_key = ["condition", "group_name"]
            else:
                # Group by condition only
                group_key = ["condition"]

            for group_keys, group_df in df.groupby(group_key):
                if isinstance(group_keys, tuple):
                    condition, group_name = group_keys
                else:
                    condition = group_keys
                    group_name = condition

                # Extract group-level info from first row
                first_row = group_df.iloc[0]
                group_type = first_row.get("group_type", "grid_3x3")
                risk_category = first_row.get("risk", None)
                severity_explanation = first_row.get("severity_explanation", None)

                # Create or get condition
                existing_conditions = self.db_manager.get_conditions()
                condition_obj = next(
                    (c for c in existing_conditions if c["name"] == condition), None
                )
                if not condition_obj:
                    condition_id = self.db_manager.create_condition(
                        condition, f"Imported condition: {condition}"
                    )
                else:
                    condition_id = condition_obj["id"]

                # Create prompt group
                group_id = self.db_manager.create_prompt_group(
                    condition_id=condition_id,
                    name=group_name,
                    description=f"Imported group: {group_name}",
                    group_type=group_type,
                    risk_category=risk_category,
                    severity_explanation=severity_explanation,
                )
                created_groups += 1

                # Import prompts based on group type
                if group_type == "single":
                    # Single prompt group - should have exactly one prompt
                    if len(group_df) > 1:
                        logging.warning(
                            f"Single prompt group {group_name} has multiple prompts, using first one"
                        )
                    content = group_df.iloc[0]["content"].strip()
                    self.db_manager.create_single_prompt(group_id, content)
                    imported_prompts += 1

                elif group_type == "list":
                    # List prompt group - preserve order
                    prompt_list = []
                    for _, row in group_df.iterrows():
                        prompt_list.append(row["content"].strip())
                    prompt_ids = self.db_manager.create_list_prompts(group_id, prompt_list)
                    imported_prompts += len(prompt_ids)

                else:  # grid_3x3
                    # Traditional 3x3 grid
                    prompt_grid = {
                        "implicit": {"low": "", "moderate": "", "high": ""},
                        "neutral": {"low": "", "moderate": "", "high": ""},
                        "explicit": {"low": "", "moderate": "", "high": ""},
                    }

                    for _, row in group_df.iterrows():
                        style = row.get("communication_style", "neutral")
                        severity = row.get("severity", "moderate")
                        content = row["content"].strip()
                        prompt_grid[style][severity] = content

                    prompt_ids = self.db_manager.create_prompt_with_grid(group_id, prompt_grid)
                    imported_prompts += len(prompt_ids)

                # Handle additional labels if present
                prompts = self.db_manager.get_prompts({"group_id": group_id})
                for i, (_, row) in enumerate(group_df.iterrows()):
                    if i < len(prompts):
                        prompt_id = prompts[i]["id"]
                        if "additional_labels" in row and pd.notna(row["additional_labels"]):
                            try:
                                additional_labels = json.loads(row["additional_labels"])
                                for key, value in additional_labels.items():
                                    self.db_manager.add_prompt_label(prompt_id, key, value)
                            except json.JSONDecodeError:
                                # Skip invalid JSON, but continue processing
                                pass

            return {
                "valid": True,
                "imported_prompts": imported_prompts,
                "created_groups": created_groups,
                "errors": [],
                "warnings": validation_result["warnings"],
            }

        except Exception as e:
            logging.error(f"Error importing CSV: {e}")
            return {"valid": False, "errors": [f"Import failed: {str(e)}"], "warnings": []}

    def get_prompt_statistics(self) -> Dict[str, Any]:
        """Generate comprehensive prompt statistics."""
        prompts = self.db_manager.get_prompts()
        groups = self.db_manager.get_prompt_groups()

        if not prompts:
            return {
                "total_prompts": 0,
                "total_groups": 0,
                "by_group_type": {},
                "by_communication_style": {},
                "by_severity": {},
                "by_group": {},
                "cross_tabulation": {},
            }

        df = pd.DataFrame(prompts)
        groups_df = pd.DataFrame(groups)

        # Basic counts
        stats = {
            "total_prompts": len(prompts),
            "total_groups": len(groups),
            "by_group_type": groups_df["group_type"].value_counts().to_dict(),
            "by_communication_style": df[df["communication_style"].notna()]["communication_style"]
            .value_counts()
            .to_dict(),
            "by_severity": df[df["severity"].notna()]["severity"].value_counts().to_dict(),
            "by_group": df["group_name"].value_counts().to_dict(),
        }

        # Cross-tabulation (only for grid_3x3 prompts)
        grid_prompts = df[(df["communication_style"].notna()) & (df["severity"].notna())]
        if len(grid_prompts) > 0:
            crosstab = pd.crosstab(grid_prompts["communication_style"], grid_prompts["severity"])
            stats["cross_tabulation"] = crosstab.to_dict()
        else:
            stats["cross_tabulation"] = {}

        return stats

    def copy_prompt_set(self, group_id: int, new_group_name: str) -> int:
        """Copy all prompts from one group to a new group."""
        # Get original group
        groups = self.db_manager.get_prompt_groups()
        original_group = next((g for g in groups if g["id"] == group_id), None)
        if not original_group:
            raise ValueError(f"Group with ID {group_id} not found")

        # Create new group
        new_group_id = self.db_manager.create_prompt_group(
            name=new_group_name,
            description=f"Copy of {original_group['name']}",
            risk_category=original_group["risk_category"],
            severity_explanation=original_group["severity_explanation"],
        )

        # Get prompts from original group
        prompts = self.db_manager.get_prompts({"group_id": group_id})

        # Copy prompts to new group
        copied_count = 0
        for prompt in prompts:
            self.db_manager.create_prompt(
                group_id=new_group_id,
                content=prompt["content"],
                communication_style=prompt["communication_style"],
                severity=prompt["severity"],
                additional_labels=prompt["additional_labels"],
            )
            copied_count += 1

        return copied_count

    def create_single_prompt_group(
        self,
        condition_id: int,
        name: str,
        content: str,
        description: str = None,
        risk_category: str = None,
    ) -> int:
        """Create a single prompt group with one prompt."""
        group_id = self.db_manager.create_prompt_group(
            condition_id=condition_id,
            name=name,
            description=description,
            group_type="single",
            risk_category=risk_category,
        )

        self.db_manager.create_single_prompt(group_id, content)
        return group_id

    def create_list_prompt_group(
        self,
        condition_id: int,
        name: str,
        prompt_list: List[str],
        description: str = None,
        risk_category: str = None,
    ) -> int:
        """Create a list prompt group with multiple prompts."""
        group_id = self.db_manager.create_prompt_group(
            condition_id=condition_id,
            name=name,
            description=description,
            group_type="list",
            risk_category=risk_category,
        )

        self.db_manager.create_list_prompts(group_id, prompt_list)
        return group_id

    def create_grid_prompt_group(
        self,
        condition_id: int,
        name: str,
        prompt_grid: Dict[str, Dict[str, str]],
        description: str = None,
        risk_category: str = None,
        low_severity_explanation: str = None,
        moderate_severity_explanation: str = None,
        high_severity_explanation: str = None,
    ) -> int:
        """Create a 3x3 grid prompt group."""
        group_id = self.db_manager.create_prompt_group(
            condition_id=condition_id,
            name=name,
            description=description,
            group_type="grid_3x3",
            risk_category=risk_category,
            low_severity_explanation=low_severity_explanation,
            moderate_severity_explanation=moderate_severity_explanation,
            high_severity_explanation=high_severity_explanation,
        )

        self.db_manager.create_prompt_with_grid(group_id, prompt_grid)
        return group_id
