#!/usr/bin/env python3
"""
AI Factory - Orchestrator
Ana CLI giriş noktası

Kullanım:
    python3 orchestrator.py <project_name> <agent_type>
    
Örnekler:
    python3 orchestrator.py product-hello-world prp
    python3 orchestrator.py product-hello-world dev
    python3 orchestrator.py product-hello-world test
    python3 orchestrator.py product-hello-world doc
"""

import sys
import argparse
from pathlib import Path

# Path setup
sys.path.insert(0, str(Path(__file__).parent))

from config_loader import resolve_llm_config, get_projects_path
from state_manager import load_state

# Agent imports
from agents.prp_agent import PRPAgent
from agents.dev_agent import DevAgent
from agents.test_agent import TestAgent
from agents.doc_agent import DocAgent


AGENTS = {
    'prp': PRPAgent,
    'dev': DevAgent,
    'test': TestAgent,
    'doc': DocAgent,
}


def main():
    parser = argparse.ArgumentParser(
        description='AI Factory Orchestrator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 orchestrator.py product-hello-world prp
    python3 orchestrator.py product-hello-world dev
    python3 orchestrator.py product-hello-world test
    python3 orchestrator.py product-hello-world doc
        """
    )
    parser.add_argument('project', help='Project name (e.g., product-hello-world)')
    parser.add_argument('agent', choices=list(AGENTS.keys()), help='Agent type to run')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without executing')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    project_name = args.project
    agent_type = args.agent
    
    # Proje var mı kontrol et
    project_path = get_projects_path() / project_name
    if not project_path.exists():
        print(f"❌ Error: Project not found: {project_path}")
        sys.exit(1)
    
    # LLM config çözümle
    try:
        llm_config = resolve_llm_config(project_name)
    except Exception as e:
        print(f"❌ Error loading LLM config: {e}")
        sys.exit(1)
    
    if args.verbose:
        print(f"📋 Project: {project_name}")
        print(f"🤖 Agent: {agent_type}")
        print(f"🔧 Model: {llm_config.get('model')}")
        print(f"🌐 Provider: {llm_config.get('provider')}")
        print(f"📊 Max context: {llm_config.get('max_context_tokens')}")
        print(f"📝 Max output: {llm_config.get('max_output_tokens')}")
        print()
    
    # Dry run
    if args.dry_run:
        print("🔍 Dry run mode - no changes will be made")
        try:
            state = load_state(project_name)
            print(f"📊 Current phase: {state.get('phase')}")
            print(f"📊 Current actor: {state.get('actors', {}).get('current')}")
        except:
            print("⚠️ Could not load state")
        sys.exit(0)
    
    # Agent çalıştır
    print(f"🚀 Running {agent_type}_agent on {project_name}...")
    print()
    
    agent_class = AGENTS[agent_type]
    agent = agent_class(project_name, llm_config)
    
    result = agent.run()
    
    if result['success']:
        print(f"✅ {result['message']}")
        print(f"🤖 Model used: {result['model']}")
    else:
        print(f"❌ {result['message']}")
        if result.get('error'):
            print(f"📛 Error: {result['error']}")
        sys.exit(1)


if __name__ == '__main__':
    main()
