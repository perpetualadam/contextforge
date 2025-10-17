#!/usr/bin/env python3
"""
ContextForge LLM Test Script
Tests all available LLM adapters and displays their status.
"""

import os
import sys
import argparse
import requests
import json
import time
from typing import Dict, Any, List


def test_adapter(api_url: str, adapter_name: str, test_prompt: str) -> Dict[str, Any]:
    """Test a specific LLM adapter."""
    print(f"🧪 Testing {adapter_name} adapter...")
    
    try:
        start_time = time.time()
        
        response = requests.post(
            f"{api_url}/llm/generate",
            json={
                "prompt": test_prompt,
                "model": None,  # Use default model
                "max_tokens": 100,
                "temperature": 0.7
            },
            timeout=30
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        if response.status_code == 200:
            result = response.json()
            return {
                "adapter": adapter_name,
                "status": "success",
                "duration": duration,
                "response": result.get("text", "")[:100] + "...",
                "backend": result.get("meta", {}).get("backend", "unknown"),
                "model": result.get("meta", {}).get("model", "unknown"),
                "latency_ms": result.get("meta", {}).get("latency_ms", 0)
            }
        else:
            return {
                "adapter": adapter_name,
                "status": "error",
                "duration": duration,
                "error": f"HTTP {response.status_code}: {response.text}"
            }
            
    except requests.exceptions.Timeout:
        return {
            "adapter": adapter_name,
            "status": "timeout",
            "duration": 30.0,
            "error": "Request timed out after 30 seconds"
        }
    except Exception as e:
        return {
            "adapter": adapter_name,
            "status": "error",
            "duration": 0,
            "error": str(e)
        }


def get_available_adapters(api_url: str) -> Dict[str, Any]:
    """Get list of available LLM adapters."""
    try:
        response = requests.get(f"{api_url}/llm/adapters", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Failed to get adapter list: {e}")
        return {"available_adapters": [], "priority": []}


def test_health_endpoints(api_url: str) -> Dict[str, Any]:
    """Test health of all services."""
    print("🏥 Testing service health...")
    
    services = {
        "API Gateway": f"{api_url}/health",
        "Vector Index": f"{api_url.replace('8080', '8001')}/health",
        "Preprocessor": f"{api_url.replace('8080', '8003')}/health",
        "Connector": f"{api_url.replace('8080', '8002')}/health",
        "Web Fetcher": f"{api_url.replace('8080', '8004')}/health",
        "Mock LLM": f"{api_url.replace('8080', '8005')}/health"
    }
    
    health_results = {}
    
    for service_name, health_url in services.items():
        try:
            response = requests.get(health_url, timeout=5)
            if response.status_code == 200:
                health_results[service_name] = {
                    "status": "healthy",
                    "response_time": response.elapsed.total_seconds()
                }
            else:
                health_results[service_name] = {
                    "status": "unhealthy",
                    "error": f"HTTP {response.status_code}"
                }
        except Exception as e:
            health_results[service_name] = {
                "status": "unreachable",
                "error": str(e)
            }
    
    return health_results


def main():
    parser = argparse.ArgumentParser(description='Test ContextForge LLM adapters')
    parser.add_argument('--api-url', default='http://localhost:8080', 
                       help='ContextForge API Gateway URL')
    parser.add_argument('--test-prompt', 
                       default='Write a simple Python function that adds two numbers.',
                       help='Test prompt to send to LLM adapters')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    parser.add_argument('--json-output', action='store_true',
                       help='Output results as JSON')
    parser.add_argument('--health-only', action='store_true',
                       help='Only test service health, skip LLM tests')
    
    args = parser.parse_args()
    
    print(f"🔧 ContextForge LLM Test Suite")
    print(f"📡 API Gateway: {args.api_url}")
    print(f"💬 Test prompt: {args.test_prompt}")
    print("=" * 80)
    
    # Test service health
    health_results = test_health_endpoints(args.api_url)
    
    print("🏥 Service Health Status:")
    for service, health in health_results.items():
        status_emoji = "✅" if health["status"] == "healthy" else "❌"
        print(f"   {status_emoji} {service}: {health['status']}")
        if health["status"] != "healthy" and args.verbose:
            print(f"      Error: {health.get('error', 'Unknown error')}")
    print()
    
    if args.health_only:
        if args.json_output:
            print(json.dumps({"health": health_results}, indent=2))
        return
    
    # Check if API Gateway is healthy
    if health_results.get("API Gateway", {}).get("status") != "healthy":
        print("❌ API Gateway is not healthy. Cannot proceed with LLM tests.")
        sys.exit(1)
    
    # Get available adapters
    adapter_info = get_available_adapters(args.api_url)
    available_adapters = adapter_info.get("available_adapters", [])
    priority_order = adapter_info.get("priority", [])
    
    print(f"🔌 Available LLM Adapters: {', '.join(available_adapters) if available_adapters else 'None'}")
    print(f"📋 Priority Order: {' → '.join(priority_order) if priority_order else 'None'}")
    print()
    
    if not available_adapters:
        print("⚠️  No LLM adapters available. Check your configuration.")
        if args.json_output:
            print(json.dumps({
                "health": health_results,
                "adapters": [],
                "summary": {"total": 0, "successful": 0, "failed": 0}
            }, indent=2))
        return
    
    # Test each adapter
    test_results = []
    
    print("🧪 Testing LLM Adapters:")
    print("-" * 40)
    
    for adapter in priority_order:
        if adapter in available_adapters:
            result = test_adapter(args.api_url, adapter, args.test_prompt)
            test_results.append(result)
            
            status_emoji = "✅" if result["status"] == "success" else "❌"
            print(f"{status_emoji} {adapter}: {result['status']} ({result['duration']:.2f}s)")
            
            if result["status"] == "success":
                print(f"   Backend: {result.get('backend', 'unknown')}")
                print(f"   Model: {result.get('model', 'unknown')}")
                print(f"   Response: {result.get('response', 'No response')}")
            else:
                print(f"   Error: {result.get('error', 'Unknown error')}")
            
            if args.verbose and result["status"] == "success":
                print(f"   Latency: {result.get('latency_ms', 0)}ms")
            
            print()
    
    # Summary
    successful = len([r for r in test_results if r["status"] == "success"])
    failed = len([r for r in test_results if r["status"] != "success"])
    
    print("📊 Test Summary:")
    print(f"   Total adapters tested: {len(test_results)}")
    print(f"   Successful: {successful}")
    print(f"   Failed: {failed}")
    
    if successful > 0:
        print("✅ At least one LLM adapter is working!")
    else:
        print("❌ No LLM adapters are working. Check your configuration.")
    
    # JSON output
    if args.json_output:
        output = {
            "health": health_results,
            "adapters": test_results,
            "summary": {
                "total": len(test_results),
                "successful": successful,
                "failed": failed
            }
        }
        print("\n" + "=" * 80)
        print("JSON Output:")
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
