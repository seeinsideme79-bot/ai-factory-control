#!/usr/bin/env python3
"""
AI Factory - State Manager
State okuma/yazma/güncelleme
"""

from datetime import datetime
from pathlib import Path

from config_loader import get_projects_path, load_yaml, save_yaml


def get_state_path(project_name: str) -> Path:
    """Proje state dosyası path'i"""
    return get_projects_path() / project_name / 'state' / 'state.yaml'


def load_state(project_name: str) -> dict:
    """Proje state'ini yükle"""
    state_path = get_state_path(project_name)
    state = load_yaml(state_path)
    
    if not state:
        raise FileNotFoundError(f"State not found: {state_path}")
    
    return state


def save_state(project_name: str, state: dict):
    """Proje state'ini kaydet"""
    state_path = get_state_path(project_name)
    save_yaml(state_path, state)


def update_last_event(state: dict, agent: str, action: str, result: str, model: str) -> dict:
    """last_event alanını güncelle"""
    state['last_event'] = {
        'agent': agent,
        'action': action,
        'timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'result': result,
        'model': model
    }
    return state


def update_phase(state: dict, new_phase: str) -> dict:
    """Phase'i güncelle"""
    valid_phases = ['idea', 'prp', 'development', 'test', 'human_validation', 'release']
    if new_phase not in valid_phases:
        raise ValueError(f"Invalid phase: {new_phase}. Valid: {valid_phases}")
    
    state['phase'] = new_phase
    return state


def update_actors(state: dict, current: str, awaiting_human: bool) -> dict:
    """Actors alanını güncelle"""
    state['actors'] = {
        'current': current,
        'awaiting_human': awaiting_human
    }
    return state


def update_next_action(state: dict, agent: str, action: str, requires_human_approval: bool = True) -> dict:
    """next_action alanını güncelle"""
    state['next_action'] = {
        'agent': agent,
        'action': action,
        'requires_human_approval': requires_human_approval
    }
    return state


def set_blocked(state: dict, reason: str) -> dict:
    """Projeyi blocked durumuna al"""
    state['blocking'] = {
        'is_blocked': True,
        'reason': reason,
        'since': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    }
    return state


def clear_blocked(state: dict) -> dict:
    """Blocked durumunu temizle"""
    state['blocking'] = {
        'is_blocked': False,
        'reason': None,
        'since': None
    }
    return state


def increment_revision(state: dict) -> dict:
    """Revision sayısını artır"""
    if 'health' not in state:
        state['health'] = {}
    
    current = state['health'].get('revision_count', 0)
    state['health']['revision_count'] = current + 1
    return state


def update_version(state: dict, version_type: str, new_version: str) -> dict:
    """Version alanını güncelle (prp, code, docs)"""
    if 'version' not in state:
        state['version'] = {}
    
    state['version'][version_type] = new_version
    return state
