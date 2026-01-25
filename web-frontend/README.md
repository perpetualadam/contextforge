# ContextForge Web Frontend

A modern, responsive web interface for the ContextForge AI-powered code assistant.

## Features

- **Chat Interface**: Multi-turn conversations with AI about your codebase
- **Query Interface**: Natural language search with code snippets and line numbers
- **Repository Ingestion**: Index new codebases for context retrieval
- **Agent Monitoring**: Real-time status of ContextForge services and agents
- **Offline Support**: Graceful handling when API is unavailable
- **Dark/Light Themes**: System-aware theming with manual toggle
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Local Storage**: Persistent chat history and preferences

## Quick Start

### Prerequisites

- Node.js 18+ and npm
- ContextForge API running on `http://localhost:8080`

### Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Open http://localhost:3000
```

### Production Build

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

### Docker Deployment

```bash
# Build Docker image
docker build -t contextforge-web .

# Run container
docker run -p 3000:80 contextforge-web

# Or use docker-compose
docker-compose up -d
```

## Configuration

### Environment Variables

Create a `.env` file (see `.env.example`):

```env
# API URL (defaults to http://localhost:8080)
VITE_API_URL=http://localhost:8080
```

### API Connection

The frontend connects to the ContextForge API at the configured URL. In development, Vite proxies `/api/*` requests to the backend automatically.

## Project Structure

```
web-frontend/
├── src/
│   ├── api/           # API client with retry logic
│   ├── components/    # Reusable UI components
│   │   ├── layout/    # Layout components (Sidebar, etc.)
│   │   └── ui/        # Base UI components
│   ├── pages/         # Page components
│   ├── store/         # Zustand state management
│   ├── App.tsx        # Main app with routing
│   ├── main.tsx       # Entry point
│   └── index.css      # Global styles & Tailwind
├── public/            # Static assets
├── Dockerfile         # Production container
├── nginx.conf         # Nginx configuration
└── docker-compose.yml # Container orchestration
```

## API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Service health check |
| `POST /query` | Natural language code search |
| `POST /chat` | Multi-turn chat conversations |
| `POST /ingest` | Index new repositories |
| `GET /agents/status` | Agent and service status |
| `GET /config` | System configuration |

## Accessibility

- Full keyboard navigation
- ARIA labels and roles
- Screen reader friendly
- Focus indicators
- Skip to content links

## Browser Support

- Chrome/Edge 90+
- Firefox 90+
- Safari 14+
- Mobile browsers (iOS Safari, Chrome Android)

## Troubleshooting

### API Connection Failed

1. Ensure ContextForge API is running on port 8080
2. Check CORS settings if running on different domains
3. Verify no firewall blocking the connection

### Build Errors

```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
```

## License

MIT License - See LICENSE file in the root directory.

