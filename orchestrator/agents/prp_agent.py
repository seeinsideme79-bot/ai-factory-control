#!/usr/bin/env python3
"""
AI Factory - PRP Agent
Vizyon'dan PRP üretimi
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.base_agent import BaseAgent
from state_manager import update_version


class PRPAgent(BaseAgent):
    """Vizyon'dan PRP üreten agent"""
    
    agent_type = 'prp'
    
    def build_prompt(self, state: dict) -> str:
        """PRP üretim prompt'u oluştur"""
        
        # Vizyon dosyasını oku (varsa)
        vision = self.get_project_file('prp/vision.md')
        
        # Mevcut PRP (varsa, güncelleme için)
        existing_prp = self.get_project_file('prp/prp.md')
        
        # PRP template'i (control plane'den)
        # Bu zaten system_prompt içinde olabilir
        
        prompt_parts = [
            self.system_prompt,
            "\n\n---\n\n",
            "## Project Information\n",
            f"Project ID: {state.get('meta', {}).get('project_id', self.project_name)}\n",
        ]
        
        if vision:
            prompt_parts.extend([
                "\n## Vision Document\n",
                "```\n",
                vision,
                "\n```\n"
            ])
        else:
            prompt_parts.extend([
                "\n## Vision\n",
                "No vision document found. Please create prp/vision.md first.\n"
            ])
        
        if existing_prp:
            prompt_parts.extend([
                "\n## Existing PRP (for reference/update)\n",
                "```\n",
                existing_prp,
                "\n```\n"
            ])
        
        prompt_parts.extend([
            "\n## Task\n",
            "Generate a complete PRP (Product Requirements & Planning) document based on the vision above.\n",
            "Output ONLY the PRP content in Markdown format, nothing else.\n"
        ])
        
        return "".join(prompt_parts)
    
    def process_output(self, output: str, state: dict) -> dict:
        """PRP çıktısını işle"""
        
        # Mevcut versiyon
        current_version = state.get('version', {}).get('prp', '0.0')
        
        # Versiyon artır
        try:
            major, minor = current_version.split('.')
            new_version = f"{major}.{int(minor) + 1}"
        except:
            new_version = '1.0'
        
        def state_updates(s):
            return update_version(s, 'prp', new_version)
        
        return {
            'files': [
                ('prp/prp.md', output.strip())
            ],
            'state_updates': state_updates,
            'next_phase': 'development',
            'next_agent': 'dev_agent',
            'next_action': 'implement code based on PRP'
        }
