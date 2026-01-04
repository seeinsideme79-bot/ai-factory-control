#!/usr/bin/env python3
"""
AI Factory - Test Agent
Test üretimi ve çalıştırma (sadece pass/fail raporu - A1 kararı)
"""

import re
import subprocess
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.base_agent import BaseAgent


class TestAgent(BaseAgent):
    """Test üreten ve çalıştıran agent"""
    
    agent_type = 'test'
    
    def build_prompt(self, state: dict) -> str:
        """Test üretim prompt'u oluştur"""
        
        # PRP dosyasını oku
        prp = self.get_project_file('prp/prp.md')
        
        # Kod dosyalarını oku
        src_path = self.project_path / 'src'
        code_files = []
        
        if src_path.exists():
            for file_path in src_path.rglob('*'):
                if file_path.is_file() and file_path.suffix in ['.py', '.js', '.ts', '.sh']:
                    relative = file_path.relative_to(self.project_path)
                    try:
                        content = file_path.read_text(encoding='utf-8')
                        code_files.append((str(relative), content))
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
        
        if code_files:
            prompt_parts.append("\n## Source Code\n")
            for rel_path, content in code_files:
                prompt_parts.extend([
                    f"\n### {rel_path}\n",
                    "```\n",
                    content,
                    "\n```\n"
                ])
        else:
            prompt_parts.append("\n## Source Code\nNo source code found in src/\n")
        
        prompt_parts.extend([
            "\n## Task\n",
            "Generate test specifications based on the PRP and code above.\n",
            "Use the following format:\n\n",
            "```\n",
            "## Test Specifications\n\n",
            "### Test 1: [Test Name]\n",
            "- Input: [input description]\n",
            "- Expected: [expected output]\n",
            "- Command: [command to run, if applicable]\n\n",
            "### Test 2: ...\n",
            "```\n\n",
            "Output ONLY the test specifications in Markdown format.\n"
        ])
        
        return "".join(prompt_parts)
    
    def _run_tests(self, test_specs: str) -> str:
        """Test'leri çalıştır ve sonuçları döndür"""
        
        results = ["# Test Results\n"]
        results.append(f"Project: {self.project_name}\n")
        results.append(f"Date: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Basit test: Python dosyası varsa syntax kontrolü
        src_path = self.project_path / 'src'
        passed = 0
        failed = 0
        
        if src_path.exists():
            for py_file in src_path.rglob('*.py'):
                relative = py_file.relative_to(self.project_path)
                try:
                    # Syntax check
                    result = subprocess.run(
                        ['python3', '-m', 'py_compile', str(py_file)],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if result.returncode == 0:
                        results.append(f"✅ PASS: {relative} - Syntax OK\n")
                        passed += 1
                    else:
                        results.append(f"❌ FAIL: {relative} - Syntax Error\n")
                        results.append(f"   Error: {result.stderr[:200]}\n")
                        failed += 1
                except subprocess.TimeoutExpired:
                    results.append(f"⚠️ TIMEOUT: {relative}\n")
                    failed += 1
                except Exception as e:
                    results.append(f"❌ ERROR: {relative} - {str(e)}\n")
                    failed += 1
        
        # Özet
        total = passed + failed
        results.append(f"\n## Summary\n")
        results.append(f"- Total: {total}\n")
        results.append(f"- Passed: {passed}\n")
        results.append(f"- Failed: {failed}\n")
        
        if total > 0:
            results.append(f"- Pass Rate: {passed/total:.1%}\n")
        
        return "".join(results), passed, failed
    
    def process_output(self, output: str, state: dict) -> dict:
        """Test çıktısını işle"""
        
        # Test specs'i kaydet
        files = [('tests/test_specs.md', output.strip())]
        
        # Testleri çalıştır
        test_results, passed, failed = self._run_tests(output)
        files.append(('reports/test_results.md', test_results))
        
        # Pass rate hesapla
        total = passed + failed
        pass_rate = passed / total if total > 0 else 0
        
        def state_updates(s):
            if 'health' not in s:
                s['health'] = {}
            s['health']['test_pass_rate'] = pass_rate
            return s
        
        # Sonraki adım
        if failed > 0:
            next_phase = 'development'
            next_agent = 'dev_agent'
            next_action = 'fix failing tests'
        else:
            next_phase = 'human_validation'
            next_agent = 'human'
            next_action = 'manual testing and validation'
        
        return {
            'files': files,
            'state_updates': state_updates,
            'next_phase': next_phase,
            'next_agent': next_agent,
            'next_action': next_action
        }
