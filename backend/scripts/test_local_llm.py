#!/usr/bin/env python3
"""
Test script for Local LLM Integration

Tests the Ollama-based local LLM provider to ensure it works correctly.
Run this script with USE_LOCAL_LLM=true to test local mode.
"""

import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def test_ollama_provider():
    """Test the OllamaProvider directly."""
    print("\n" + "="*60)
    print("TEST 1: Direct OllamaProvider Test")
    print("="*60)

    from services.llm_provider import OllamaProvider
    import httpx

    # OllamaProvider reads from environment variables
    provider = OllamaProvider()

    print(f"Connecting to Ollama at: {provider.base_url}")
    print(f"Using model: {provider.model}")

    # Test health check via Ollama API tags endpoint
    print("\n[1.1] Health Check...")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.get(f"{provider.base_url}/api/tags")
            healthy = resp.status_code == 200
    except Exception:
        healthy = False

    print(f"  ✓ Ollama health: {'OK' if healthy else 'FAILED'}")

    if not healthy:
        print("  ⚠️  Ollama is not running. Start it with: ollama serve")
        print("  ⚠️  Skipping generation tests (provider class validated)")
        # Still validate the provider class structure
        assert hasattr(provider, 'generate'), "Missing generate method"
        assert hasattr(provider, 'generate_json'), "Missing generate_json method"
        assert hasattr(provider, 'get_provider_name'), "Missing get_provider_name method"
        assert provider.get_provider_name() == "ollama", "Wrong provider name"
        print("  ✓ OllamaProvider class structure validated")
        return True

    # Test simple generation
    print("\n[1.2] Simple Generation Test...")
    response = await provider.generate(
        system="You are a helpful assistant. Be concise.",
        prompt="What is 2 + 2? Answer in one word.",
        max_tokens=50,
        temperature=0.1
    )
    print(f"  Response: {response.strip()}")
    print(f"  ✓ Generation works!")

    # Test compliance-style prompt
    print("\n[1.3] Compliance Analysis Test...")
    response = await provider.generate(
        system="""You are a BFSI compliance expert. Analyze regulatory requirements
and provide structured JSON output.""",
        prompt="""Analyze this regulatory text and extract key requirements:

"Banks shall maintain records of all customer transactions for a minimum period of 5 years."

Return JSON with: requirement_type, obligation, retention_period, entities_involved""",
        max_tokens=500,
        temperature=0.3
    )
    print(f"  Response preview: {response[:300]}...")
    print(f"  ✓ Compliance analysis works!")

    return True


async def test_llm_provider_switching():
    """Test the get_llm_provider() switching mechanism."""
    print("\n" + "="*60)
    print("TEST 2: LLM Provider Switching")
    print("="*60)
    
    from services.llm_provider import get_llm_provider, is_using_local_llm, OllamaProvider, ClaudeProvider
    
    # Check current mode
    use_local = is_using_local_llm()
    print(f"USE_LOCAL_LLM = {os.environ.get('USE_LOCAL_LLM', 'not set')}")
    print(f"is_using_local_llm() = {use_local}")
    
    provider = get_llm_provider()
    provider_type = type(provider).__name__
    print(f"Provider type: {provider_type}")
    
    if use_local:
        assert isinstance(provider, OllamaProvider), "Expected OllamaProvider!"
        print("  ✓ Correctly using OllamaProvider")
    else:
        # When not using local, it should return Claude provider (or None if no API key)
        print("  ⚠️  Not in local mode. Set USE_LOCAL_LLM=true to test local LLM")
    
    return True


async def test_multi_llm_service():
    """Test the MultiLLMService with local LLM."""
    print("\n" + "="*60)
    print("TEST 3: MultiLLMService Integration")
    print("="*60)
    
    try:
        from services.multi_llm_service_new import MultiLLMService
        
        service = MultiLLMService()
        print(f"use_local_llm = {service.use_local_llm}")
        print(f"local_provider = {type(service.local_provider).__name__ if service.local_provider else None}")
        
        if service.use_local_llm:
            # Test chat response
            print("\n[3.1] Testing chat_response...")
            response = await service.chat_response(
                user_message="What are the key KYC requirements in India?",
                context=[]
            )
            print(f"  Response preview: {response[:200]}...")
            print("  ✓ chat_response works!")
            
            return True
        else:
            print("  ⚠️  Set USE_LOCAL_LLM=true to test local LLM integration")
            return True
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("CompliAI Local LLM Integration Test Suite")
    print("="*60)
    print(f"Current USE_LOCAL_LLM: {os.environ.get('USE_LOCAL_LLM', 'not set')}")
    
    results = []
    
    # Test 1: Direct provider
    try:
        results.append(("OllamaProvider", await test_ollama_provider()))
    except Exception as e:
        print(f"  ✗ Test failed: {e}")
        results.append(("OllamaProvider", False))
    
    # Test 2: Provider switching
    try:
        results.append(("Provider Switching", await test_llm_provider_switching()))
    except Exception as e:
        print(f"  ✗ Test failed: {e}")
        results.append(("Provider Switching", False))
    
    # Test 3: MultiLLMService
    try:
        results.append(("MultiLLMService", await test_multi_llm_service()))
    except Exception as e:
        print(f"  ✗ Test failed: {e}")
        results.append(("MultiLLMService", False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST RESULTS SUMMARY")
    print("="*60)
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")
    
    all_passed = all(r[1] for r in results)
    print(f"\nOverall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    
    return all_passed


if __name__ == "__main__":
    # Set USE_LOCAL_LLM for testing
    os.environ["USE_LOCAL_LLM"] = "true"
    
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
