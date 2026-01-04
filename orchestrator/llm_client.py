#!/usr/bin/env python3
"""
AI Factory - LLM Client
Provider-agnostic LLM çağrısı
"""

import requests
import json
from typing import Optional

from config_loader import get_api_key
from token_utils import check_context_limit


class LLMClient:
    """Provider-agnostic LLM client"""
    
    def __init__(self, config: dict):
        self.config = config
        self.provider = config.get('provider')
        self.model = config.get('model')
        self.temperature = config.get('temperature', 0.7)
        self.max_output_tokens = config.get('max_output_tokens', 2048)
        self.provider_config = config.get('provider_config', {})
        
        # API key
        self.api_key = get_api_key(config)
    
    def _get_headers(self) -> dict:
        """Provider'a göre headers oluştur"""
        headers = {
            'Content-Type': 'application/json'
        }
        
        auth_header = self.provider_config.get('auth_header')
        auth_prefix = self.provider_config.get('auth_prefix', '')
        
        if auth_header and self.api_key:
            headers[auth_header] = f"{auth_prefix}{self.api_key}"
        
        # OpenRouter için ek header
        if self.provider == 'openrouter':
            headers['HTTP-Referer'] = 'https://aifactory.seeinside.me'
            headers['X-Title'] = 'AI Factory Orchestrator'
        
        return headers
    
    def _build_request_body(self, prompt: str, effective_max_output: int) -> dict:
        """Provider'a göre request body oluştur"""
        
        if self.provider == 'anthropic':
            # Anthropic Messages API
            return {
                'model': self.model,
                'max_tokens': effective_max_output,
                'messages': [
                    {'role': 'user', 'content': prompt}
                ]
            }
        elif self.provider == 'ollama':
            # Ollama API
            return {
                'model': self.model,
                'messages': [
                    {'role': 'user', 'content': prompt}
                ],
                'stream': False,
                'options': {
                    'temperature': self.temperature,
                    'num_predict': effective_max_output
                }
            }
        else:
            # OpenAI-compatible (OpenRouter, OpenAI)
            return {
                'model': self.model,
                'max_tokens': effective_max_output,
                'temperature': self.temperature,
                'messages': [
                    {'role': 'user', 'content': prompt}
                ]
            }
    
    def _parse_response(self, response_json: dict) -> str:
        """Provider'a göre response parse et"""
        
        if self.provider == 'anthropic':
            # Anthropic format
            content = response_json.get('content', [])
            if content and len(content) > 0:
                return content[0].get('text', '')
            return ''
        elif self.provider == 'ollama':
            # Ollama format
            message = response_json.get('message', {})
            return message.get('content', '')
        else:
            # OpenAI-compatible format
            choices = response_json.get('choices', [])
            if choices and len(choices) > 0:
                message = choices[0].get('message', {})
                return message.get('content', '')
            return ''
    
    def call(self, prompt: str) -> dict:
        """
        LLM çağrısı yap
        
        Returns:
            {
                'success': bool,
                'content': str,
                'model': str,
                'error': str or None,
                'token_info': dict
            }
        """
        # Token kontrolü
        token_check = check_context_limit(prompt, self.config)
        
        if not token_check['ok']:
            return {
                'success': False,
                'content': '',
                'model': self.model,
                'error': token_check['warning'],
                'token_info': token_check
            }
        
        effective_max_output = token_check['effective_max_output']
        
        # Request hazırla
        base_url = self.provider_config.get('base_url')
        if not base_url:
            return {
                'success': False,
                'content': '',
                'model': self.model,
                'error': f"No base_url configured for provider: {self.provider}",
                'token_info': token_check
            }
        
        headers = self._get_headers()
        body = self._build_request_body(prompt, effective_max_output)
        
        try:
            response = requests.post(
                base_url,
                headers=headers,
                json=body,
                timeout=120  # 2 dakika timeout
            )
            
            if response.status_code != 200:
                error_msg = f"API error {response.status_code}: {response.text[:500]}"
                return {
                    'success': False,
                    'content': '',
                    'model': self.model,
                    'error': error_msg,
                    'token_info': token_check
                }
            
            response_json = response.json()
            content = self._parse_response(response_json)
            
            return {
                'success': True,
                'content': content,
                'model': self.model,
                'error': None,
                'token_info': token_check
            }
            
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'content': '',
                'model': self.model,
                'error': 'Request timeout (120s)',
                'token_info': token_check
            }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'content': '',
                'model': self.model,
                'error': f"Request failed: {str(e)}",
                'token_info': token_check
            }
        except json.JSONDecodeError as e:
            return {
                'success': False,
                'content': '',
                'model': self.model,
                'error': f"Invalid JSON response: {str(e)}",
                'token_info': token_check
            }
