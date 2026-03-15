"""
Utility functions for Anthropic client initialization.
Handles proxy configuration issues in sandbox environments.
"""
import os
import anthropic


def create_anthropic_client(api_key: str = None) -> anthropic.Anthropic:
    """
    Create an Anthropic client with proxy workaround for sandbox environments.

    Args:
        api_key: Anthropic API key. If None, uses ANTHROPIC_API_KEY or EMERGENT_LLM_KEY env vars.

    Returns:
        anthropic.Anthropic: Configured Anthropic client
    """
    if api_key is None:
        api_key = os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('EMERGENT_LLM_KEY')

    if not api_key:
        return None

    # Temporarily unset proxy env vars to avoid SOCKS proxy issues in sandbox
    http_proxy_backup = os.environ.get('HTTP_PROXY')
    https_proxy_backup = os.environ.get('HTTPS_PROXY')
    all_proxy_backup = os.environ.get('ALL_PROXY')

    os.environ.pop('HTTP_PROXY', None)
    os.environ.pop('HTTPS_PROXY', None)
    os.environ.pop('ALL_PROXY', None)
    os.environ.pop('http_proxy', None)
    os.environ.pop('https_proxy', None)
    os.environ.pop('all_proxy', None)

    try:
        client = anthropic.Anthropic(api_key=api_key)
    finally:
        # Restore proxy settings
        if http_proxy_backup:
            os.environ['HTTP_PROXY'] = http_proxy_backup
        if https_proxy_backup:
            os.environ['HTTPS_PROXY'] = https_proxy_backup
        if all_proxy_backup:
            os.environ['ALL_PROXY'] = all_proxy_backup

    return client
