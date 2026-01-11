"""
ContextForge Dashboard Service.

Web-based dashboard for real-time monitoring.

Copyright (c) 2025 ContextForge
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import httpx
import asyncio

# Configure logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# Service URLs
PERSISTENCE_URL = os.getenv("PERSISTENCE_URL", "http://localhost:8010")
VECTOR_INDEX_URL = os.getenv("VECTOR_INDEX_URL", "http://localhost:8001")
API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8000")

app = FastAPI(
    title="ContextForge Dashboard",
    description="Real-time monitoring dashboard",
    version="0.1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


# Response Models
class ServiceStatus(BaseModel):
    name: str
    status: str  # healthy, unhealthy, unknown
    latency_ms: Optional[int] = None
    last_check: datetime


class DashboardStats(BaseModel):
    active_sessions: int = 0
    total_queries: int = 0
    avg_latency_ms: Optional[float] = None
    error_rate: Optional[float] = None
    cache_hit_rate: Optional[float] = None
    index_size: int = 0
    services: List[ServiceStatus] = []
    timestamp: datetime


async def check_service_health(name: str, url: str) -> ServiceStatus:
    """Check health of a service."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            start = datetime.utcnow()
            response = await client.get(f"{url}/health")
            latency = int((datetime.utcnow() - start).total_seconds() * 1000)
            status = "healthy" if response.status_code == 200 else "unhealthy"
            return ServiceStatus(name=name, status=status, latency_ms=latency, last_check=datetime.utcnow())
    except Exception:
        return ServiceStatus(name=name, status="unhealthy", last_check=datetime.utcnow())


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy", "timestamp": datetime.utcnow()}


@app.get("/api/stats", response_model=DashboardStats)
async def get_stats():
    """Get dashboard statistics."""
    # Check services in parallel
    services = await asyncio.gather(
        check_service_health("persistence", PERSISTENCE_URL),
        check_service_health("vector-index", VECTOR_INDEX_URL),
        check_service_health("api-gateway", API_GATEWAY_URL),
    )
    
    stats = DashboardStats(
        services=list(services),
        timestamp=datetime.utcnow()
    )
    
    # Try to get persistence stats
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{PERSISTENCE_URL}/dashboard/summary")
            if resp.status_code == 200:
                data = resp.json()
                stats.active_sessions = data.get("active_sessions", 0)
                stats.avg_latency_ms = data.get("avg_query_latency_ms")
                stats.error_rate = data.get("error_rate_percent")
                stats.cache_hit_rate = data.get("cache_hit_rate_percent")
    except Exception as e:
        logger.warning(f"Failed to get persistence stats: {e}")
    
    # Try to get vector index stats
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{VECTOR_INDEX_URL}/stats")
            if resp.status_code == 200:
                data = resp.json()
                stats.index_size = data.get("total_chunks", 0)
    except Exception as e:
        logger.warning(f"Failed to get vector index stats: {e}")
    
    return stats


@app.get("/api/queries")
async def get_recent_queries(limit: int = 50):
    """Get recent queries."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{PERSISTENCE_URL}/queries", params={"limit": limit})
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.warning(f"Failed to get queries: {e}")
    return []


@app.get("/api/metrics")
async def get_metrics(metric_type: Optional[str] = None, hours: int = 24):
    """Get metrics for charting."""
    try:
        params = {"limit": 1000}
        if metric_type:
            params["metric_type"] = metric_type
        params["start_time"] = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{PERSISTENCE_URL}/metrics", params=params)
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.warning(f"Failed to get metrics: {e}")
    return []


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates."""
    await manager.connect(websocket)
    try:
        while True:
            # Send stats every 5 seconds
            stats = await get_stats()
            await websocket.send_json(stats.model_dump(mode="json"))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# Serve static dashboard HTML
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ContextForge Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        .status-healthy { color: #10b981; }
        .status-unhealthy { color: #ef4444; }
        .status-unknown { color: #6b7280; }
        .card { @apply bg-white dark:bg-gray-800 rounded-lg shadow-md p-4; }
    </style>
</head>
<body class="bg-gray-100 dark:bg-gray-900 min-h-screen">
    <nav class="bg-indigo-600 text-white p-4 shadow-lg">
        <div class="container mx-auto flex justify-between items-center">
            <h1 class="text-2xl font-bold">🔧 ContextForge Dashboard</h1>
            <span id="connection-status" class="text-sm">⚪ Connecting...</span>
        </div>
    </nav>

    <main class="container mx-auto p-4">
        <!-- Stats Cards -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
            <div class="card">
                <h3 class="text-gray-500 dark:text-gray-400 text-sm">Active Sessions</h3>
                <p id="active-sessions" class="text-3xl font-bold text-indigo-600">-</p>
            </div>
            <div class="card">
                <h3 class="text-gray-500 dark:text-gray-400 text-sm">Index Size</h3>
                <p id="index-size" class="text-3xl font-bold text-green-600">-</p>
            </div>
            <div class="card">
                <h3 class="text-gray-500 dark:text-gray-400 text-sm">Avg Latency</h3>
                <p id="avg-latency" class="text-3xl font-bold text-blue-600">-</p>
            </div>
            <div class="card">
                <h3 class="text-gray-500 dark:text-gray-400 text-sm">Error Rate</h3>
                <p id="error-rate" class="text-3xl font-bold text-red-600">-</p>
            </div>
            <div class="card">
                <h3 class="text-gray-500 dark:text-gray-400 text-sm">Cache Hit Rate</h3>
                <p id="cache-hit" class="text-3xl font-bold text-purple-600">-</p>
            </div>
        </div>

        <!-- Service Status -->
        <div class="card mb-6">
            <h2 class="text-xl font-bold mb-4 dark:text-white">Service Status</h2>
            <div id="services" class="grid grid-cols-1 md:grid-cols-3 gap-4"></div>
        </div>

        <!-- Charts -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            <div class="card">
                <h2 class="text-xl font-bold mb-4 dark:text-white">Query Latency (24h)</h2>
                <canvas id="latency-chart"></canvas>
            </div>
            <div class="card">
                <h2 class="text-xl font-bold mb-4 dark:text-white">Request Volume (24h)</h2>
                <canvas id="volume-chart"></canvas>
            </div>
        </div>

        <!-- Recent Queries -->
        <div class="card">
            <h2 class="text-xl font-bold mb-4 dark:text-white">Recent Queries</h2>
            <div id="queries" class="overflow-x-auto">
                <table class="w-full text-sm">
                    <thead class="bg-gray-50 dark:bg-gray-700">
                        <tr>
                            <th class="p-2 text-left dark:text-white">Time</th>
                            <th class="p-2 text-left dark:text-white">Query</th>
                            <th class="p-2 text-left dark:text-white">Contexts</th>
                            <th class="p-2 text-left dark:text-white">Latency</th>
                            <th class="p-2 text-left dark:text-white">Backend</th>
                        </tr>
                    </thead>
                    <tbody id="queries-body"></tbody>
                </table>
            </div>
        </div>
    </main>

    <script>
        let ws;
        let latencyChart, volumeChart;

        function connect() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

            ws.onopen = () => {
                document.getElementById('connection-status').innerHTML = '🟢 Connected';
            };

            ws.onclose = () => {
                document.getElementById('connection-status').innerHTML = '🔴 Disconnected';
                setTimeout(connect, 3000);
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                updateDashboard(data);
            };
        }

        function updateDashboard(data) {
            document.getElementById('active-sessions').textContent = data.active_sessions || 0;
            document.getElementById('index-size').textContent =
                data.index_size ? data.index_size.toLocaleString() : '-';
            document.getElementById('avg-latency').textContent =
                data.avg_latency_ms ? `${data.avg_latency_ms.toFixed(0)}ms` : '-';
            document.getElementById('error-rate').textContent =
                data.error_rate !== null ? `${data.error_rate.toFixed(1)}%` : '-';
            document.getElementById('cache-hit').textContent =
                data.cache_hit_rate !== null ? `${data.cache_hit_rate.toFixed(1)}%` : '-';

            const servicesDiv = document.getElementById('services');
            servicesDiv.innerHTML = data.services.map(s => `
                <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded">
                    <span class="font-medium dark:text-white">${s.name}</span>
                    <span class="status-${s.status}">
                        ${s.status === 'healthy' ? '✓' : '✗'} ${s.status}
                        ${s.latency_ms ? `(${s.latency_ms}ms)` : ''}
                    </span>
                </div>
            `).join('');
        }

        async function loadQueries() {
            try {
                const resp = await fetch('/api/queries?limit=20');
                const queries = await resp.json();
                const tbody = document.getElementById('queries-body');
                tbody.innerHTML = queries.map(q => `
                    <tr class="border-b dark:border-gray-700">
                        <td class="p-2 dark:text-gray-300">${new Date(q.created_at).toLocaleTimeString()}</td>
                        <td class="p-2 dark:text-gray-300 max-w-md truncate">${q.query}</td>
                        <td class="p-2 dark:text-gray-300">${q.contexts_used}</td>
                        <td class="p-2 dark:text-gray-300">${q.latency_ms}ms</td>
                        <td class="p-2 dark:text-gray-300">${q.llm_backend || '-'}</td>
                    </tr>
                `).join('');
            } catch (e) {
                console.error('Failed to load queries:', e);
            }
        }

        // Initialize
        connect();
        loadQueries();
        setInterval(loadQueries, 30000);
    </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve dashboard HTML."""
    return DASHBOARD_HTML


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8011)

