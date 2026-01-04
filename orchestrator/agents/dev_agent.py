#!/usr/bin/env python3
"""
AI Factory - Dev Agent
PRP'den kod üretimi
"""

import re
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.base_agent import BaseAgent
from state_manager import update_version, increment_revision


class DevAgent(BaseAgent):
    """PRP'den kod üreten agent"""
    
    agent_type = 'dev'
    
    def build_prompt(self, state: dict) -> str:
        """Kod üretim prompt'u oluştur"""
        
        # PRP dosyasını oku
        prp = self.get_project_file('prp/prp.md')
        
        # Mevcut kod (varsa, güncelleme için)
        # src/ altındaki dosyaları listele
        src_path = self.project_path / 'src'
        existing_code = []
        
        if src_path.exists():
            for file_path in src_path.rglob('*'):
                if file_path.is_file():
                    relative = file_path.relative_to(self.project_path)
                    try:
                        content = file_path.read_text(encoding='utf-8')
                        existing_code.append((str(relative), content))
                    except:
                        pass
        
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
        else:
            prompt_parts.extend([
                "\n## PRP\n",
                "ERROR: No PRP document found. Cannot generate code without PRP.\n"
            ])
            return "".join(prompt_parts)
        
        if existing_code:
            prompt_parts.append("\n## Existing Code\n")
            for rel_path, content in existing_code:
                prompt_parts.extend([
                    f"\n### {rel_path}\n",
                    "```\n",
                    content,
                    "\n```\n"
                ])
        
        prompt_parts.extend([
            "\n## Task\n",
            "Generate the implementation code based on the PRP above.\n",
            "Use the following format for each file:\n\n",
            "```\n",
            "### FILE: src/filename.py\n",
            "```python\n",
            "# code here\n",
            "```\n",
            "```\n\n",
            "Output ALL necessary files with their complete content.\n"
        ])
        
        return "".join(prompt_parts)
    
    def process_output(self, output: str, state: dict) -> dict:
        """Kod çıktısını işle ve dosyalara ayır"""
        
        files = []
        
        # FILE: pattern'i ile dosyaları ayır
        # Format: ### FILE: path/to/file.py
        file_pattern = r'###\s*FILE:\s*(.+?)\n```[\w]*\n(.*?)```'
        matches = re.findall(file_pattern, output, re.DOTALL)
        
        if matches:
            for file_path, content in matches:
                file_path = file_path.strip()
                content = content.strip()
                files.append((file_path, content))
        else:
            # Fallback: Eğer format tutmadıysa, tüm çıktıyı src/main.py olarak kaydet
            # Bu durumda Python kod bloğunu bulmaya çalış
            code_match = re.search(r'```python\n(.*?)```', output, re.DOTALL)
            if code_match:
                files.append(('src/main.py', code_match.group(1).strip()))
            else:
                # Son çare: tüm çıktıyı kaydet
                files.append(('src/main.py', output.strip()))
        
        # Versiyon güncelle
        current_version = state.get('version', {}).get('code', '0.0.0')
        try:
            parts = current_version.split('.')
            parts[-1] = str(int(parts[-1]) + 1)
            new_version = '.'.join(parts)
        except:
            new_version = '0.1.0'
        
        def state_updates(s):
            s = update_version(s, 'code', new_version)
            return s
        
        return {
            'files': files,
            'state_updates': state_updates,
            'next_phase': 'test',
            'next_agent': 'test_agent',
            'next_action': 'generate and run tests'
        }
