"""Annotation management functionality."""

import json
import logging
from typing import List, Dict, Any, Optional
from core.database import DatabaseManager


class AnnotationManager:
    """Manages annotation workflows and assignments."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    def create_annotation_run(self, experiment_id: int, name: str, description: str,
                             guidelines: str, response_ordering: str,
                             filter_models: List[str] = None,
                             filter_conditions: List[str] = None) -> int:
        """Create a new annotation run."""
        return self.db_manager.create_annotation_run(
            experiment_id=experiment_id,
            name=name,
            description=description,
            guidelines=guidelines,
            response_ordering=response_ordering,
            filter_models=filter_models,
            filter_conditions=filter_conditions
        )
    
    def create_assessment_category(self, annotation_run_id: int, name: str,
                                  category_type: str, possible_values: List[str] = None,
                                  guidelines: str = None, display_order: int = None) -> int:
        """Create assessment category for an annotation run."""
        return self.db_manager.create_assessment_category(
            annotation_run_id=annotation_run_id,
            name=name,
            category_type=category_type,
            possible_values=possible_values,
            guidelines=guidelines,
            display_order=display_order
        )
    
    def assign_labeler(self, annotation_run_id: int, labeler_initials: str):
        """Assign labeler to annotation run."""
        self.db_manager.assign_labeler(annotation_run_id, labeler_initials)
    
    def get_annotation_runs(self) -> List[Dict]:
        """Get all annotation runs."""
        return self.db_manager.get_annotation_runs()
    
    def get_annotation_run_details(self, annotation_run_id: int) -> Dict:
        """Get detailed information about an annotation run."""
        # Get the annotation run
        annotation_runs = self.db_manager.get_annotation_runs()
        annotation_run = next((ar for ar in annotation_runs if ar['id'] == annotation_run_id), None)
        
        if not annotation_run:
            raise ValueError(f"Annotation run {annotation_run_id} not found")
        
        # Get assessment categories
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM assessment_categories 
                WHERE annotation_run_id = ? 
                ORDER BY display_order, id
            """, (annotation_run_id,))
            categories = [dict(row) for row in cursor.fetchall()]
            
            # Parse possible_values JSON
            for category in categories:
                if category['possible_values']:
                    category['possible_values'] = json.loads(category['possible_values'])
            
            annotation_run['assessment_categories'] = categories
        
        # Get labeler assignments
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute("""
                SELECT labeler_initials FROM labeler_assignments 
                WHERE annotation_run_id = ?
            """, (annotation_run_id,))
            labelers = [row['labeler_initials'] for row in cursor.fetchall()]
            annotation_run['assigned_labelers'] = labelers
        
        # Get eligible responses for this annotation run
        eligible_responses = self.get_eligible_responses(annotation_run_id)
        annotation_run['eligible_responses_count'] = len(eligible_responses)
        
        return annotation_run
    
    def get_eligible_responses(self, annotation_run_id: int) -> List[Dict]:
        """Get responses eligible for annotation based on run filters."""
        # Get annotation run details
        annotation_runs = self.db_manager.get_annotation_runs()
        annotation_run = next((ar for ar in annotation_runs if ar['id'] == annotation_run_id), None)
        
        if not annotation_run:
            return []
        
        # Get experiment details
        experiment = self.db_manager.get_experiment_details(annotation_run['experiment_id'])
        
        # Filter responses based on annotation run criteria
        eligible_responses = []
        for response in experiment['responses']:
            if response['status'] != 'completed':
                continue  # Only include completed responses
            
            # Apply model filter
            if annotation_run['filter_models']:
                filter_models = json.loads(annotation_run['filter_models'])
                if response['model'] not in filter_models:
                    continue
            
            # Apply condition filter
            if annotation_run['filter_conditions']:
                filter_conditions = json.loads(annotation_run['filter_conditions'])
                # Find the prompt for this response to get its condition
                prompt = next((p for p in experiment['prompts'] if p['id'] == response['prompt_id']), None)
                if prompt and prompt.get('condition_name') not in filter_conditions:
                    continue
            
            eligible_responses.append(response)
        
        return eligible_responses
    
    def save_annotation(self, annotation_run_id: int, response_id: int,
                       category_id: int, labeler_initials: str, value: str,
                       justification: str = None):
        """Save an annotation."""
        self.db_manager.save_annotation(
            annotation_run_id=annotation_run_id,
            response_id=response_id,
            category_id=category_id,
            labeler_initials=labeler_initials,
            value=value,
            justification=justification
        )
    
    def get_labeler_progress(self, annotation_run_id: int, labeler_initials: str) -> Dict:
        """Get progress for a specific labeler."""
        eligible_responses = self.get_eligible_responses(annotation_run_id)
        total_responses = len(eligible_responses)
        
        if total_responses == 0:
            return {
                'total_responses': 0,
                'completed_responses': 0,
                'completion_percentage': 0
            }
        
        # Get completed annotations for this labeler
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute("""
                SELECT COUNT(DISTINCT response_id) as completed
                FROM annotations
                WHERE annotation_run_id = ? AND labeler_initials = ?
            """, (annotation_run_id, labeler_initials))
            completed_responses = cursor.fetchone()['completed']
        
        return {
            'total_responses': total_responses,
            'completed_responses': completed_responses,
            'completion_percentage': (completed_responses / total_responses * 100) if total_responses > 0 else 0
        }
    
    def get_annotation_for_response(self, annotation_run_id: int, response_id: int, 
                                   category_id: int, labeler_initials: str) -> Optional[Dict]:
        """Get existing annotation for a specific response/category/labeler combination."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM annotations
                WHERE annotation_run_id = ? AND response_id = ? 
                      AND category_id = ? AND labeler_initials = ?
            """, (annotation_run_id, response_id, category_id, labeler_initials))
            result = cursor.fetchone()
            return dict(result) if result else None