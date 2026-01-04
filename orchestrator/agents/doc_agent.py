#!/usr/bin/env python3
"""
AI Factory - Doc Agent
Dokümantasyon üretimi
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.base_agent import BaseAgent
from state_manager import update_version


class DocAgent(BaseAgent):
    """Dokümantasyon üreten agent"""
    
    agent_type = 'doc'
    
    def build_prompt(self, state: dict) -> str:
        """Dokümantasyon prompt'u oluştur"""
        
        # PRP dosyasını oku
        prp = self.get_project_file('prp/prp.md')
        
        # Kod dosyalarını oku
        src_path = self.project_path / 'src'
        code_files = []
        
        if src_path.exists():
            for file_path in src_path.rglob('*'):
                if file_path.is_file():
                    relative = file_path.relative_to(self.project_path)
                    try:
                        content = file_path.read_text(encoding='utf-8')
                        code_files.append((str(relative), content))
                    except:
                        pass
        
        # Test sonuçları
        test_results = self.get_project_file('reports/test_results.md')
        
        prompt_parts = [
            self.system_prompt,
            "\n\n---\n\n",
            "## Project Information\n",
            f"Project ID: {state.get('meta', {}).get('project_id', self.project_name)}\n",
        ]
        
        if prp:
            prompt_parts.extend([
                "\n## PRP Document\n",
                "```markdown\n",
                prp,
                "\n```\n"
            ])
        
        if code_files:
            prompt_parts.append("\n## Source Code\n")
            for rel_path, content in code_files:
                prompt_parts.extend([
                    f"\n### {rel_path}\n",
                    "```\n",
                    content,
                    "\n```\n"
                ])
        
        if test_results:
            prompt_parts.extend([
                "\n## Test Results\n",
                "```\n",
                test_results,
                "\n```\n"
            ])
        
        prompt_parts.extend([
            "\n## Task\n",
            "Generate architecture documentation based on the PRP and code above.\n",
            "Include:\n",
            "- Overview\n",
            "- Architecture diagram (text-based)\n",
            "- Component descriptions\n",
            "- Usage instructions\n",
            "- API reference (if applicable)\n\n",
            "Output ONLY the documentation in Markdown format.\n"
        ])
        
        return "".join(prompt_parts)
    
    def process_output(self, output: str, state: dict) -> dict:
        """Dokümantasyon çıktısını işle"""
        
        # Versiyon güncelle
        current_version = state.get('version', {}).get('docs', '0.0')
        try:
            major, minor = current_version.split('.')
            new_version = f"{major}.{int(minor) + 1}"
        except:
            new_version = '1.0'
        
        def state_updates(s):
            return update_version(s, 'docs', new_version)
        
        return {
            'files': [
                ('docs/architecture.md', output.strip())
            ],
            'state_updates': state_updates,
            'next_phase': None,  # Phase değişmez
            'next_agent': 'human',
            'next_action': 'review documentation'
        }
