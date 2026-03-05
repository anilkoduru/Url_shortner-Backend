# URL Shortener

A simple, fast URL shortener built with FastAPI, Redis, and MongoDB.

## Features

- ⚡ Fast redirects with Redis caching
- 🗄️ Persistent storage with MongoDB Atlas
- 🔢 Base62 encoded short codes

## Quick Start

### Requirements
- Python 3.8+
- MongoDB Atlas account
- Redis (Docker or cloud)

### Install & Run

```bash
# Install dependencies
pip install -r requirement.txt

# Start Redis
docker run -d -p 6379:6379 redis:latest

# Run the app
uvicorn main:app --reload
```

## API Usage

### Shorten URL
```bash
POST /shorten
Content-Type: application/json

{"url": "https://example.com/long-url"}
```

**Response:**
```json
{
  "shortened_url": "http://short.url/000001",
  "original_url": "https://example.com/long-url",
  "created_at": "2026-03-05T10:30:00Z"
}
```

### Redirect
```bash
GET /{short_code}
# Example: GET /000001 → redirects to original URL
```

## Environment Variables

```env
MONGODB_URI=your-mongodb-atlas-connection-string
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

## Tech Stack

- **FastAPI** - Web framework
- **Redis** - Caching (24h TTL)
- **MongoDB Atlas** - Database
- **Uvicorn** - ASGI server

## Deployment

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for production deployment options.

## Testing

```bash
# Shorten URL
curl -X POST http://localhost:8000/shorten \
  -H "Content-Type: application/json" \
  -d '{"url":"https://github.com"}'

# Test redirect
curl -L http://localhost:8000/000001
```

---

Built with FastAPI, Redis & MongoDB Atlas
