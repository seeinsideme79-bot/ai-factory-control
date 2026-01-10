#!/usr/bin/env python3
"""
AI Factory - Config Loader
Profile çözümleme ve LLM config okuma
"""

import os
import yaml
from pathlib import Path


def get_control_plane_path() -> Path:
    """Control plane root path"""
    return Path(__file__).parent.parent


def get_projects_path() -> Path:
    """Projects dizini (control plane'in parent'ı)"""
    return get_control_plane_path().parent


def load_yaml(file_path: Path) -> dict:
    """YAML dosyası yükle"""
    if not file_path.exists():
        return {}
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def save_yaml(file_path: Path, data: dict):
    """YAML dosyası kaydet"""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def load_profiles() -> dict:
    """Global LLM profiles yükle"""
    profiles_path = get_control_plane_path() / 'config' / 'llm.profiles.yaml'
    return load_yaml(profiles_path)


def resolve_llm_config(project_name: str, profile_override: str = None) -> dict:
    """
    Proje için LLM config çözümle
    
    Öncelik:
    1. profile_override (CLI --model parametresi)
    2. Proje config/llm.yaml (full config varsa)
    3. Proje config/llm.yaml (profile referansı varsa) -> profiles.yaml'dan çözümle
    4. Global default_profile -> profiles.yaml'dan çözümle
    
    Args:
        project_name: Proje adı
        profile_override: CLI'dan gelen profile override (opsiyonel)
    
    Returns:
        LLM config dictionary
    """
    profiles_data = load_profiles()
    profiles = profiles_data.get('profiles', {})
    providers = profiles_data.get('providers', {})
    default_profile = profiles_data.get('default_profile', 'gemma-free')
    
    # 1. CLI Override varsa direkt kullan
    if profile_override:
        if profile_override not in profiles:
            raise ValueError(f"Unknown profile: {profile_override}")
        config = profiles[profile_override].copy()
    else:
        # 2. Proje llm.yaml kontrol et
        project_path = get_projects_path() / project_name
        project_llm_path = project_path / 'config' / 'llm.yaml'
        project_config = load_yaml(project_llm_path)
        
        if project_config:
            # Full config mi yoksa profile referansı mı?
            if 'profile' in project_config and 'provider' not in project_config:
                # Profile referansı
                profile_name = project_config['profile']
                if profile_name not in profiles:
                    raise ValueError(f"Unknown profile: {profile_name}")
                config = profiles[profile_name].copy()
            else:
                # Full config
                config = project_config.copy()
        else:
            # 3. Default profile kullan
            if default_profile not in profiles:
                raise ValueError(f"Default profile not found: {default_profile}")
            config = profiles[default_profile].copy()
    
    # Provider bilgilerini ekle
    provider_name = config.get('provider')
    if provider_name and provider_name in providers:
        config['provider_config'] = providers[provider_name]
    
    return config


def load_agent_prompt(agent_type: str, project_name: str = None) -> str:
    """
    Agent prompt'unu yükle
    
    Öncelik:
    1. Proje agents/overrides/{agent_type}.md
    2. Global agents/templates/{agent_type}.md
    """
    agent_file = f"{agent_type}_agent.md"
    
    # Proje override kontrol et
    if project_name:
        project_path = get_projects_path() / project_name
        override_path = project_path / 'agents' / 'overrides' / agent_file
        if override_path.exists():
            with open(override_path, 'r', encoding='utf-8') as f:
                return f.read()
    
    # Global template
    template_path = get_control_plane_path() / 'agents' / 'templates' / agent_file
    if template_path.exists():
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    raise FileNotFoundError(f"Agent prompt not found: {agent_file}")


def get_api_key(config: dict) -> str:
    """Environment variable'dan API key al"""
    api_key_env = config.get('api_key_env')
    if not api_key_env:
        return None
    
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise ValueError(f"API key not found in environment: {api_key_env}")
    
    return api_key
