from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from datetime import datetime, timezone
import redis
import json
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
if not MONGODB_URI:
    raise ValueError("MONGODB_URI environment variable is required!")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

mongo_client: Optional[MongoClient] = None
db = None
urls_collection = None
counters_collection = None
redis_client: Optional[redis.Redis] = None

def init_mongodb():
    global mongo_client, db, urls_collection, counters_collection
    
    try:
        mongo_client = MongoClient(MONGODB_URI, server_api=ServerApi('1'))
        db = mongo_client["shortener_db"]
        urls_collection = db["urls"]
        counters_collection = db["counters"]
        urls_collection.create_index("short_code", unique=True)
        
        mongo_client.admin.command('ping')
        print("✓ MongoDB connected successfully!")
        return True
    except Exception as e:
        print(f"✗ MongoDB connection failed: {e}")
        return False


def init_redis():
    global redis_client
    
    try:
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True
        )
        redis_client.ping()
        print("✓ Redis connected successfully!")
        return True
    except Exception as e:
        print(f"✗ Redis connection failed: {e}")
        return False

def close_mongodb():
    global mongo_client
    if mongo_client:
        mongo_client.close()
        print("✓ MongoDB connection closed")

def close_redis():
    global redis_client
    if redis_client:
        redis_client.close()
        print("✓ Redis connection closed")

class URLRequest(BaseModel):
    url: str
    
class URLResponse(BaseModel):
    shortened_url: str
    original_url: str
    created_at: str

def generate_short_code(url: str) -> str:
    unique_id = counters_collection.find_one_and_update(
        {"_id": "url_count"},
        {"$inc": {"count": 1}},
        upsert=True,
        return_document=True
    )["count"]    
    base62_chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    
    if unique_id == 0:
        return "0" * 6
    
    short_code = ""
    while unique_id > 0:
        short_code = base62_chars[unique_id % 62] + short_code
        unique_id //= 62
    
    return short_code.rjust(6, '0')

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting URL Shortener Application...")
    
    mongodb_ok = init_mongodb()
    redis_ok = init_redis()
    
    if not mongodb_ok or not redis_ok:
        print("⚠️  Warning: Some services failed to initialize")
    else:
        print("✓ All services initialized successfully!")
    
    yield
    
    print("🛑 Shutting down URL Shortener Application...")
    close_mongodb()
    close_redis()
    print("="*50 + "\n")

app = FastAPI(
    title="URL Shortener API",
    description="A high-performance URL shortener with Redis caching and MongoDB persistence",
    version="1.0.0",
    lifespan=lifespan
)

@app.post("/shorten", response_model=URLResponse)
async def shorten_url(request: URLRequest) -> URLResponse:
    cached_result = redis_client.get(f"url_mapping:{request.url}")
    if cached_result:
        cached_data = json.loads(cached_result)
        return URLResponse(
            shortened_url=cached_data["shortened_url"],
            original_url=request.url,
            created_at=cached_data["created_at"]
        )
    
    existing = urls_collection.find_one({"original_url": request.url})
    if existing:
        created_at_str = existing["created_at"].isoformat().replace('+00:00', 'Z')
        cache_data = {
            "shortened_url": existing["shortened_url"],
            "created_at": created_at_str
        }
        redis_client.setex(f"url_mapping:{request.url}", 86400, json.dumps(cache_data))
        return URLResponse(
            shortened_url=existing["shortened_url"],
            original_url=request.url,
            created_at=created_at_str
        )
    
    short_code = generate_short_code(request.url)
    shortened_url = "http://short.url/" + short_code
    created_at = datetime.now(timezone.utc)
    
    urls_collection.insert_one({
        "short_code": short_code,
        "shortened_url": shortened_url,
        "original_url": request.url,
        "created_at": created_at
    })
    
    created_at_str = created_at.isoformat().replace('+00:00', 'Z')
    
    cache_data = {
        "shortened_url": shortened_url,
        "created_at": created_at_str
    }
    redis_client.setex(f"url_mapping:{request.url}", 86400, json.dumps(cache_data))
    redis_client.setex(f"short_code:{short_code}", 86400, request.url)
    
    response = URLResponse(
        shortened_url=shortened_url,
        original_url=request.url,
        created_at=created_at_str
    )
    return response

@app.get("/{short_code}")
async def redirect(short_code: str):
    cached_url = redis_client.get(f"short_code:{short_code}")
    if cached_url:
        return RedirectResponse(url=cached_url, status_code=301)
    
    url_doc = urls_collection.find_one({"short_code": short_code})
    if url_doc:
        redis_client.setex(f"short_code:{short_code}", 86400, url_doc["original_url"])
        return RedirectResponse(url=url_doc["original_url"], status_code=301)
    else:
        raise HTTPException(status_code=404, detail="Short code not found")