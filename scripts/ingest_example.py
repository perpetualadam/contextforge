#!/usr/bin/env python3
"""
ContextForge Ingestion Example Script
Demonstrates how to ingest a repository using the ContextForge API.
"""

import os
import sys
import argparse
import requests
import json
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Ingest a repository into ContextForge')
    parser.add_argument('--path', required=True, help='Path to repository to ingest')
    parser.add_argument('--api-url', default='http://localhost:8080', 
                       help='ContextForge API Gateway URL')
    parser.add_argument('--recursive', action='store_true', default=True,
                       help='Recursively process subdirectories')
    parser.add_argument('--file-patterns', nargs='*',
                       help='File patterns to include (e.g., *.py *.js)')
    parser.add_argument('--exclude-patterns', nargs='*',
                       help='File patterns to exclude (e.g., *.pyc node_modules/*)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    
    args = parser.parse_args()
    
    # Validate path
    repo_path = Path(args.path)
    if not repo_path.exists():
        print(f"Error: Path {args.path} does not exist")
        sys.exit(1)
    
    if not repo_path.is_dir():
        print(f"Error: Path {args.path} is not a directory")
        sys.exit(1)
    
    print(f"🚀 Starting ingestion of: {repo_path.absolute()}")
    print(f"📡 API Gateway: {args.api_url}")
    
    # Check API health
    try:
        health_response = requests.get(f"{args.api_url}/health", timeout=10)
        health_response.raise_for_status()
        print("✅ API Gateway is healthy")
        
        if args.verbose:
            health_data = health_response.json()
            print(f"   Status: {health_data.get('status', 'unknown')}")
    except Exception as e:
        print(f"❌ API Gateway health check failed: {e}")
        sys.exit(1)
    
    # Prepare ingestion request
    ingest_data = {
        "path": str(repo_path.absolute()),
        "recursive": args.recursive
    }
    
    if args.file_patterns:
        ingest_data["file_patterns"] = args.file_patterns
    
    if args.exclude_patterns:
        ingest_data["exclude_patterns"] = args.exclude_patterns
    
    if args.verbose:
        print(f"📋 Ingestion parameters:")
        print(json.dumps(ingest_data, indent=2))
    
    # Start ingestion
    print("🔄 Starting ingestion...")
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{args.api_url}/ingest",
            json=ingest_data,
            timeout=300  # 5 minutes timeout
        )
        response.raise_for_status()
        
        end_time = time.time()
        duration = end_time - start_time
        
        result = response.json()
        
        print("✅ Ingestion completed successfully!")
        print(f"⏱️  Duration: {duration:.2f} seconds")
        
        # Display stats
        stats = result.get("stats", {})
        print(f"📊 Statistics:")
        print(f"   Files processed: {stats.get('files_processed', 0)}")
        print(f"   Chunks created: {stats.get('chunks_created', 0)}")
        print(f"   Chunks indexed: {stats.get('chunks_indexed', 0)}")
        
        if args.verbose:
            print(f"📄 Full response:")
            print(json.dumps(result, indent=2))
        
        # Get index stats
        try:
            index_response = requests.get(f"{args.api_url}/index/stats", timeout=10)
            index_response.raise_for_status()
            index_stats = index_response.json()
            
            print(f"🗂️  Index Statistics:")
            print(f"   Total vectors: {index_stats.get('total_vectors', 0)}")
            print(f"   Embedding model: {index_stats.get('embedding_model', 'unknown')}")
            print(f"   Backend: {index_stats.get('backend', 'unknown')}")
            
        except Exception as e:
            if args.verbose:
                print(f"⚠️  Could not retrieve index stats: {e}")
        
    except requests.exceptions.Timeout:
        print("❌ Ingestion timed out (>5 minutes)")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"❌ Ingestion failed: {e}")
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
