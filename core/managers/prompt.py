"""Prompt management functionality."""

import pandas as pd
import json
import logging
from typing import List, Dict, Any, Optional
from core.database import DatabaseManager


class CSVValidator:
    """Validates CSV imports for prompts."""
    
    REQUIRED_COLUMNS = ['content', 'communication_style', 'severity', 'condition']
    VALID_COMMUNICATION_STYLES = ['implicit', 'neutral', 'explicit']
    VALID_SEVERITIES = ['low', 'moderate', 'high']
    
    def validate_csv(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Validate CSV data for prompt import."""
        errors = []
        warnings = []
        
        # Check required columns
        missing_cols = set(self.REQUIRED_COLUMNS) - set(df.columns)
        if missing_cols:
            errors.append(f"Missing required columns: {missing_cols}")
        
        if errors:
            return {'valid': False, 'errors': errors, 'warnings': warnings}
        
        # Validate enum values
        invalid_styles = df[~df['communication_style'].isin(self.VALID_COMMUNICATION_STYLES)]
        if not invalid_styles.empty:
            errors.append(f"Invalid communication styles found: {invalid_styles['communication_style'].unique()}")
        
        invalid_severities = df[~df['severity'].isin(self.VALID_SEVERITIES)]
        if not invalid_severities.empty:
            errors.append(f"Invalid severities found: {invalid_severities['severity'].unique()}")
        
        # Check for empty content
        empty_content = df[df['content'].isna() | (df['content'].str.strip() == '')]
        if not empty_content.empty:
            errors.append(f"Found {len(empty_content)} rows with empty content")
        
        # Check for empty conditions
        empty_conditions = df[df['condition'].isna() | (df['condition'].str.strip() == '')]
        if not empty_conditions.empty:
            errors.append(f"Found {len(empty_conditions)} rows with empty condition")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }


class PromptManager:
    """Manages prompt operations and statistics."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.csv_validator = CSVValidator()
    
    def import_prompts_from_csv(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Import prompts from CSV DataFrame."""
        # Validate CSV
        validation_result = self.csv_validator.validate_csv(df)
        if not validation_result['valid']:
            return validation_result
        
        try:
            # Group by condition to create/get prompt groups
            imported_prompts = 0
            created_groups = 0
            
            for condition, group_df in df.groupby('condition'):
                # Get or create prompt group
                existing_groups = self.db_manager.get_prompt_groups()
                existing_group = next((g for g in existing_groups if g['name'] == condition), None)
                
                if existing_group:
                    group_id = existing_group['id']
                else:
                    # Extract group-level info from first row
                    first_row = group_df.iloc[0]
                    risk_category = first_row.get('risk', None)
                    severity_explanation = first_row.get('severity_explanation', None)
                    
                    group_id = self.db_manager.create_prompt_group(
                        name=condition,
                        description=f"Imported condition: {condition}",
                        risk_category=risk_category,
                        severity_explanation=severity_explanation
                    )
                    created_groups += 1
                
                # Import prompts for this group
                for _, row in group_df.iterrows():
                    # Parse additional labels if present
                    additional_labels = None
                    if 'additional_labels' in row and pd.notna(row['additional_labels']):
                        try:
                            additional_labels = json.loads(row['additional_labels'])
                        except json.JSONDecodeError:
                            # Skip invalid JSON, but continue processing
                            pass
                    
                    self.db_manager.create_prompt(
                        group_id=group_id,
                        content=row['content'].strip(),
                        communication_style=row['communication_style'],
                        severity=row['severity'],
                        additional_labels=additional_labels
                    )
                    imported_prompts += 1
            
            return {
                'valid': True,
                'imported_prompts': imported_prompts,
                'created_groups': created_groups,
                'errors': [],
                'warnings': validation_result['warnings']
            }
            
        except Exception as e:
            logging.error(f"Error importing CSV: {e}")
            return {
                'valid': False,
                'errors': [f"Import failed: {str(e)}"],
                'warnings': []
            }
    
    def get_prompt_statistics(self) -> Dict[str, Any]:
        """Generate comprehensive prompt statistics."""
        prompts = self.db_manager.get_prompts()
        groups = self.db_manager.get_prompt_groups()
        
        if not prompts:
            return {
                'total_prompts': 0,
                'total_groups': 0,
                'by_communication_style': {},
                'by_severity': {},
                'by_group': {},
                'cross_tabulation': {}
            }
        
        df = pd.DataFrame(prompts)
        
        # Basic counts
        stats = {
            'total_prompts': len(prompts),
            'total_groups': len(groups),
            'by_communication_style': df['communication_style'].value_counts().to_dict(),
            'by_severity': df['severity'].value_counts().to_dict(),
            'by_group': df['group_name'].value_counts().to_dict()
        }
        
        # Cross-tabulation
        if len(df) > 0:
            crosstab = pd.crosstab(df['communication_style'], df['severity'])
            stats['cross_tabulation'] = crosstab.to_dict()
        else:
            stats['cross_tabulation'] = {}
        
        return stats
    
    def copy_prompt_set(self, group_id: int, new_group_name: str) -> int:
        """Copy all prompts from one group to a new group."""
        # Get original group
        groups = self.db_manager.get_prompt_groups()
        original_group = next((g for g in groups if g['id'] == group_id), None)
        if not original_group:
            raise ValueError(f"Group with ID {group_id} not found")
        
        # Create new group
        new_group_id = self.db_manager.create_prompt_group(
            name=new_group_name,
            description=f"Copy of {original_group['name']}",
            risk_category=original_group['risk_category'],
            severity_explanation=original_group['severity_explanation']
        )
        
        # Get prompts from original group
        prompts = self.db_manager.get_prompts({'group_id': group_id})
        
        # Copy prompts to new group
        copied_count = 0
        for prompt in prompts:
            self.db_manager.create_prompt(
                group_id=new_group_id,
                content=prompt['content'],
                communication_style=prompt['communication_style'],
                severity=prompt['severity'],
                additional_labels=prompt['additional_labels']
            )
            copied_count += 1
        
        return copied_count