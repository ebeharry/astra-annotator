"""Experiment management functionality."""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from core.database import DatabaseManager
from core.llm import (
    OpenAIProvider, ClaudeProvider, GrokProvider, 
    GeminiProvider, OllamaProvider
)


class ExperimentManager:
    """Manages LLM experiments and response generation."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.provider_classes = {
            'openai': OpenAIProvider,
            'claude': ClaudeProvider,
            'grok': GrokProvider,
            'gemini': GeminiProvider,
            'ollama': OllamaProvider
        }
    
    def create_experiment(self, name: str, description: str, models: List[str], 
                         prompt_ids: List[int]) -> int:
        """Create a new experiment."""
        return self.db_manager.create_experiment(name, description, models, prompt_ids)
    
    def get_experiments(self) -> List[Dict]:
        """Get all experiments."""
        return self.db_manager.get_experiments()
    
    def get_experiment_details(self, experiment_id: int) -> Dict:
        """Get detailed experiment information."""
        return self.db_manager.get_experiment_details(experiment_id)
    
    def _get_provider(self, model_name: str, api_keys: Dict[str, str] = None) -> Any:
        """Get appropriate LLM provider for model."""
        api_keys = api_keys or {}
        
        # Map model names to providers
        if model_name.startswith('gpt'):
            return OpenAIProvider(
                api_key=api_keys.get('openai'),
                model=model_name
            )
        elif 'claude' in model_name.lower():
            return ClaudeProvider(
                api_key=api_keys.get('anthropic'),
                model=model_name
            )
        elif 'grok' in model_name.lower():
            return GrokProvider(
                api_key=api_keys.get('xai'),
                model=model_name
            )
        elif 'gemini' in model_name.lower():
            return GeminiProvider(
                api_key=api_keys.get('google'),
                model=model_name
            )
        elif model_name in ['llama2', 'llama3', 'mistral', 'codellama']:
            return OllamaProvider(model=model_name)
        else:
            raise ValueError(f"Unknown model: {model_name}")
    
    async def _process_single_response(self, response_record: Dict, 
                                     api_keys: Dict[str, str] = None) -> Dict:
        """Process a single LLM response."""
        try:
            provider = self._get_provider(response_record['model'], api_keys)
            result = await provider.generate_response(response_record['prompt_content'])
            
            if result['status'] == 'success':
                self.db_manager.update_response_status(
                    response_record['id'], 
                    'completed',
                    response_text=result['response']
                )
                return {
                    'id': response_record['id'],
                    'status': 'completed',
                    'model': response_record['model']
                }
            else:
                self.db_manager.update_response_status(
                    response_record['id'],
                    'failed',
                    error_message=result['error_message']
                )
                return {
                    'id': response_record['id'],
                    'status': 'failed',
                    'model': response_record['model'],
                    'error': result['error_message']
                }
                
        except Exception as e:
            logging.error(f"Error processing response {response_record['id']}: {e}")
            self.db_manager.update_response_status(
                response_record['id'],
                'failed',
                error_message=str(e)
            )
            return {
                'id': response_record['id'],
                'status': 'failed',
                'model': response_record['model'],
                'error': str(e)
            }
    
    async def run_experiment(self, experiment_id: int, api_keys: Dict[str, str] = None,
                           max_concurrent: int = 5) -> Dict:
        """Run experiment with parallel LLM processing."""
        try:
            # Update experiment status
            self.db_manager.update_experiment_status(experiment_id, 'running')
            
            # Get pending responses
            pending_responses = self.db_manager.get_pending_responses(experiment_id)
            
            if not pending_responses:
                self.db_manager.update_experiment_status(experiment_id, 'completed')
                return {
                    'status': 'completed',
                    'message': 'No pending responses to process'
                }
            
            # Process responses in parallel with concurrency limit
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def process_with_semaphore(response_record):
                async with semaphore:
                    return await self._process_single_response(response_record, api_keys)
            
            results = await asyncio.gather(
                *[process_with_semaphore(response) for response in pending_responses],
                return_exceptions=True
            )
            
            # Analyze results
            completed = sum(1 for r in results if isinstance(r, dict) and r.get('status') == 'completed')
            failed = sum(1 for r in results if isinstance(r, dict) and r.get('status') == 'failed')
            exceptions = sum(1 for r in results if isinstance(r, Exception))
            
            # Update experiment status
            if failed == 0 and exceptions == 0:
                self.db_manager.update_experiment_status(experiment_id, 'completed')
                status = 'completed'
            else:
                self.db_manager.update_experiment_status(experiment_id, 'failed')
                status = 'partially_completed'
            
            return {
                'status': status,
                'completed': completed,
                'failed': failed + exceptions,
                'total': len(pending_responses)
            }
            
        except Exception as e:
            logging.error(f"Error running experiment {experiment_id}: {e}")
            self.db_manager.update_experiment_status(experiment_id, 'failed')
            raise
    
    def get_experiment_progress(self, experiment_id: int) -> Dict:
        """Get current progress of experiment."""
        experiment = self.db_manager.get_experiment_details(experiment_id)
        
        total_responses = len(experiment['responses'])
        completed = sum(1 for r in experiment['responses'] if r['status'] == 'completed')
        failed = sum(1 for r in experiment['responses'] if r['status'] == 'failed')
        pending = sum(1 for r in experiment['responses'] if r['status'] == 'pending')
        
        # Group by model
        by_model = {}
        for response in experiment['responses']:
            model = response['model']
            if model not in by_model:
                by_model[model] = {'completed': 0, 'failed': 0, 'pending': 0, 'total': 0}
            by_model[model][response['status']] += 1
            by_model[model]['total'] += 1
        
        return {
            'experiment_id': experiment_id,
            'status': experiment['status'],
            'total_responses': total_responses,
            'completed': completed,
            'failed': failed,
            'pending': pending,
            'completion_percentage': (completed / total_responses * 100) if total_responses > 0 else 0,
            'by_model': by_model
        }