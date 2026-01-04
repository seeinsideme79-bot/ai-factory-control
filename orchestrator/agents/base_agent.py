#!/usr/bin/env python3
"""
AI Factory - Base Agent
Ortak agent mantığı
"""

from abc import ABC, abstractmethod
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_loader import get_projects_path, load_agent_prompt, load_yaml
from llm_client import LLMClient
from state_manager import (
    load_state, save_state, update_last_event, 
    update_phase, update_actors, update_next_action,
    set_blocked
)


class BaseAgent(ABC):
    """Base class for all agents"""
    
    agent_type: str = None  # Override in subclass
    
    def __init__(self, project_name: str, llm_config: dict):
        self.project_name = project_name
        self.llm_config = llm_config
        self.project_path = get_projects_path() / project_name
        self.llm_client = LLMClient(llm_config)
        
        # Agent prompt yükle
        self.system_prompt = load_agent_prompt(self.agent_type, project_name)
    
    def get_project_file(self, relative_path: str) -> str:
        """Proje dosyası içeriğini oku"""
        file_path = self.project_path / relative_path
        if not file_path.exists():
            return ""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def save_project_file(self, relative_path: str, content: str):
        """Proje dosyasına yaz"""
        file_path = self.project_path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    @abstractmethod
    def build_prompt(self, state: dict) -> str:
        """Agent-specific prompt oluştur"""
        pass
    
    @abstractmethod
    def process_output(self, output: str, state: dict) -> dict:
        """
        LLM çıktısını işle ve state güncellemelerini döndür
        
        Returns:
            {
                'files': [(relative_path, content), ...],
                'state_updates': callable(state) -> state,
                'next_phase': str or None,
                'next_agent': str or None,
                'next_action': str or None
            }
        """
        pass
    
    def run(self) -> dict:
        """
        Agent'ı çalıştır
        
        Returns:
            {
                'success': bool,
                'message': str,
                'model': str,
                'error': str or None
            }
        """
        # State yükle
        try:
            state = load_state(self.project_name)
        except FileNotFoundError as e:
            return {
                'success': False,
                'message': str(e),
                'model': self.llm_config.get('model'),
                'error': 'state_not_found'
            }
        
        # Prompt oluştur
        prompt = self.build_prompt(state)
        
        # LLM çağrısı
        result = self.llm_client.call(prompt)
        
        if not result['success']:
            # Hata durumunda state güncelle
            state = update_last_event(
                state, 
                f"{self.agent_type}_agent",
                f"{self.agent_type} generation failed",
                'failure',
                result['model']
            )
            state = set_blocked(state, 'agent_error')
            save_state(self.project_name, state)
            
            return {
                'success': False,
                'message': f"LLM call failed: {result['error']}",
                'model': result['model'],
                'error': result['error']
            }
        
        # Çıktıyı işle
        try:
            processed = self.process_output(result['content'], state)
        except Exception as e:
            state = update_last_event(
                state,
                f"{self.agent_type}_agent",
                f"{self.agent_type} output processing failed",
                'failure',
                result['model']
            )
            state = set_blocked(state, 'agent_error')
            save_state(self.project_name, state)
            
            return {
                'success': False,
                'message': f"Output processing failed: {str(e)}",
                'model': result['model'],
                'error': str(e)
            }
        
        # Dosyaları kaydet
        for relative_path, content in processed.get('files', []):
            self.save_project_file(relative_path, content)
        
        # State güncellemeleri
        if processed.get('state_updates'):
            state = processed['state_updates'](state)
        
        # Phase güncelle
        if processed.get('next_phase'):
            state = update_phase(state, processed['next_phase'])
        
        # Actors güncelle
        next_agent = processed.get('next_agent', 'human')
        awaiting_human = next_agent == 'human'
        state = update_actors(state, next_agent, awaiting_human)
        
        # Next action güncelle
        if processed.get('next_action'):
            state = update_next_action(
                state,
                next_agent,
                processed['next_action'],
                requires_human_approval=True
            )
        
        # Last event güncelle
        state = update_last_event(
            state,
            f"{self.agent_type}_agent",
            f"{self.agent_type} completed successfully",
            'success',
            result['model']
        )
        
        # State kaydet
        save_state(self.project_name, state)
        
        return {
            'success': True,
            'message': f"{self.agent_type}_agent completed successfully",
            'model': result['model'],
            'error': None
        }
