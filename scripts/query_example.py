#!/usr/bin/env python3
"""
ContextForge Query Example Script
Demonstrates how to query the ContextForge API and display results.
"""

import os
import sys
import argparse
import requests
import json
import time
from typing import Dict, Any


def format_context(context: Dict[str, Any], index: int) -> str:
    """Format a context result for display."""
    meta = context.get("meta", {})
    file_path = meta.get("file_path", "unknown")
    start_line = meta.get("start_line")
    end_line = meta.get("end_line")
    score = context.get("score", 0)
    text = context.get("text", "")
    
    # Format location info
    location = file_path
    if start_line:
        if end_line and end_line != start_line:
            location += f" (lines {start_line}-{end_line})"
        else:
            location += f" (line {start_line})"
    
    # Truncate text if too long
    display_text = text
    if len(display_text) > 300:
        display_text = display_text[:300] + "..."
    
    return f"""
[SOURCE {index + 1}] {location} (score: {score:.3f})
{'-' * 60}
{display_text}
"""


def format_web_result(result: Dict[str, Any], index: int) -> str:
    """Format a web search result for display."""
    title = result.get("title", "No title")
    url = result.get("url", "")
    snippet = result.get("snippet", "")
    
    return f"""
[WEB {index + 1}] {title}
{url}
{snippet}
"""


def main():
    parser = argparse.ArgumentParser(description='Query ContextForge for answers')
    parser.add_argument('--query', '-q', required=True, help='Question to ask')
    parser.add_argument('--api-url', default='http://localhost:8080', 
                       help='ContextForge API Gateway URL')
    parser.add_argument('--max-tokens', type=int, default=512,
                       help='Maximum tokens for LLM response')
    parser.add_argument('--top-k', type=int, default=10,
                       help='Number of contexts to retrieve')
    parser.add_argument('--enable-web-search', action='store_true',
                       help='Enable web search for additional context')
    parser.add_argument('--disable-web-search', action='store_true',
                       help='Disable web search')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    parser.add_argument('--json-output', action='store_true',
                       help='Output raw JSON response')
    
    args = parser.parse_args()
    
    print(f"🤔 Question: {args.query}")
    print(f"📡 API Gateway: {args.api_url}")
    
    # Check API health
    try:
        health_response = requests.get(f"{args.api_url}/health", timeout=10)
        health_response.raise_for_status()
        print("✅ API Gateway is healthy")
    except Exception as e:
        print(f"❌ API Gateway health check failed: {e}")
        sys.exit(1)
    
    # Prepare query request
    query_data = {
        "query": args.query,
        "max_tokens": args.max_tokens,
        "top_k": args.top_k
    }
    
    # Handle web search settings
    if args.enable_web_search:
        query_data["enable_web_search"] = True
    elif args.disable_web_search:
        query_data["enable_web_search"] = False
    # Otherwise, use API default
    
    if args.verbose:
        print(f"📋 Query parameters:")
        print(json.dumps(query_data, indent=2))
    
    # Execute query
    print("🔍 Searching for answer...")
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{args.api_url}/query",
            json=query_data,
            timeout=60  # 1 minute timeout
        )
        response.raise_for_status()
        
        end_time = time.time()
        duration = end_time - start_time
        
        result = response.json()
        
        if args.json_output:
            print(json.dumps(result, indent=2))
            return
        
        print(f"✅ Query completed in {duration:.2f} seconds")
        print("=" * 80)
        
        # Display answer
        answer = result.get("answer", "No answer provided")
        print(f"🤖 Answer:")
        print(answer)
        print()
        
        # Display contexts
        contexts = result.get("contexts", [])
        if contexts:
            print(f"📄 Code Contexts ({len(contexts)} found):")
            for i, context in enumerate(contexts):
                print(format_context(context, i))
        else:
            print("📄 No code contexts found")
        
        # Display web results
        web_results = result.get("web_results", [])
        if web_results:
            print(f"🌐 Web Results ({len(web_results)} found):")
            for i, web_result in enumerate(web_results):
                print(format_web_result(web_result, i))
        else:
            print("🌐 No web results found")
        
        # Display metadata
        meta = result.get("meta", {})
        print("📊 Query Metadata:")
        print(f"   Backend: {meta.get('backend', 'unknown')}")
        print(f"   Total latency: {meta.get('total_latency_ms', 0)}ms")
        print(f"   Contexts found: {meta.get('num_contexts', 0)}")
        print(f"   Web results: {meta.get('num_web_results', 0)}")
        
        if args.verbose:
            print(f"📄 Full response:")
            print(json.dumps(result, indent=2))
        
    except requests.exceptions.Timeout:
        print("❌ Query timed out (>1 minute)")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"❌ Query failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"   Error details: {error_detail}")
            except:
                print(f"   Response: {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
