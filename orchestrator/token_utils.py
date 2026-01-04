#!/usr/bin/env python3
"""
AI Factory - Token Utilities
Token tahminleme ve context kontrolü
"""


def estimate_tokens(text: str) -> int:
    """
    Basit token tahminleme
    
    Ortalama: 1 token ≈ 4 karakter (İngilizce için)
    Türkçe ve kod için biraz daha yüksek olabilir
    Güvenlik marjı için 3.5 kullanıyoruz
    """
    if not text:
        return 0
    return int(len(text) / 3.5)


def check_context_limit(prompt: str, config: dict) -> dict:
    """
    Context limitini kontrol et
    
    Returns:
        {
            'ok': bool,
            'prompt_tokens': int,
            'max_context_tokens': int,
            'max_output_tokens': int,
            'effective_max_output': int,
            'warning': str or None
        }
    """
    prompt_tokens = estimate_tokens(prompt)
    max_context = config.get('max_context_tokens', 8192)
    max_output = config.get('max_output_tokens', 2048)
    
    available_for_output = max_context - prompt_tokens
    
    result = {
        'ok': True,
        'prompt_tokens': prompt_tokens,
        'max_context_tokens': max_context,
        'max_output_tokens': max_output,
        'effective_max_output': max_output,
        'warning': None
    }
    
    if available_for_output <= 0:
        result['ok'] = False
        result['effective_max_output'] = 0
        result['warning'] = f"Context overflow: prompt ({prompt_tokens}) >= max_context ({max_context})"
    elif available_for_output < max_output:
        result['effective_max_output'] = available_for_output
        result['warning'] = f"Reduced output: {available_for_output} tokens available (requested {max_output})"
    
    return result


def truncate_to_token_limit(text: str, max_tokens: int) -> str:
    """
    Metni token limitine göre kes
    Sondan keser, başlangıcı korur
    """
    estimated = estimate_tokens(text)
    if estimated <= max_tokens:
        return text
    
    # Yaklaşık karakter sayısı
    target_chars = int(max_tokens * 3.5)
    return text[:target_chars] + "\n\n[... truncated ...]"
