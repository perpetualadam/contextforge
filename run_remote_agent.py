#!/usr/bin/env python3
"""
Convenience script to run the ContextForge Remote Agent service.

Usage:
    python run_remote_agent.py [coordinator|worker] [--port PORT]

Examples:
    # Run as coordinator (default)
    python run_remote_agent.py
    python run_remote_agent.py coordinator --port 8011
    
    # Run as worker
    python run_remote_agent.py worker --coordinator-url http://localhost:8011

Copyright (c) 2025 ContextForge
"""

import os
import sys
import argparse

# Add services directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'services'))


def main():
    parser = argparse.ArgumentParser(description='Run ContextForge Remote Agent')
    parser.add_argument('mode', nargs='?', default='coordinator',
                        choices=['coordinator', 'worker'],
                        help='Run mode: coordinator or worker (default: coordinator)')
    parser.add_argument('--port', type=int, default=8011,
                        help='Port to listen on (default: 8011)')
    parser.add_argument('--coordinator-url', type=str, default='http://localhost:8011',
                        help='Coordinator URL for worker mode')
    parser.add_argument('--name', type=str, default='Remote Agent',
                        help='Agent name')
    parser.add_argument('--capabilities', type=str, default='code_analysis,rag_query,web_search',
                        help='Comma-separated list of capabilities')
    
    args = parser.parse_args()
    
    # Set environment variables
    if args.mode == 'coordinator':
        os.environ['COORDINATOR_MODE'] = 'true'
        os.environ['WORKER_MODE'] = 'false'
    else:
        os.environ['COORDINATOR_MODE'] = 'false'
        os.environ['WORKER_MODE'] = 'true'
        os.environ['COORDINATOR_URL'] = args.coordinator_url
    
    os.environ['PORT'] = str(args.port)
    os.environ['AGENT_NAME'] = args.name
    os.environ['AGENT_CAPABILITIES'] = args.capabilities
    
    # Import and run
    import uvicorn
    from remote_agent.app import app
    
    print(f"Starting Remote Agent in {args.mode} mode on port {args.port}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()

