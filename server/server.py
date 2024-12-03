import logging
import psutil
import gc
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from newspaper import Article

app = FastAPI()

# Add CORS middleware to allow requests from your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace "*" with specific origins like ["http://localhost:63342"] for better security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# Input model
class URLRequest(BaseModel):
    url: str


# Helper function to get memory usage
def get_memory_usage():
    process = psutil.Process()
    memory_info = process.memory_info()
    memory_stats = {
        "rss": f"{memory_info.rss / (1024 * 1024):.2f} MB",  # Resident Set Size
        "vms": f"{memory_info.vms / (1024 * 1024):.2f} MB",  # Virtual Memory Size
    }

    # Add `shared` memory if available (Linux-only)
    if hasattr(memory_info, 'shared'):
        memory_stats["shared"] = f"{memory_info.shared / (1024 * 1024):.2f} MB"

    # Add peak memory (not platform-specific)
    memory_stats["peak"] = f"{memory_info.rss / (1024 * 1024):.2f} MB"

    return memory_stats


@app.post("/api/parse_url")
async def parse_url(request: URLRequest):
    url = request.url
    logging.info(f"Received URL: {url}")
    memory_before = get_memory_usage()

    try:
        # Use newspaper to parse the article
        article = Article(url)
        article.download()
        article.parse()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing URL: {str(e)}")

    # Force garbage collection
    gc.collect()
    memory_after = get_memory_usage()

    return {
        "message": f"Successfully parsed URL: {url}",
        "memory_stats": {
            "before": memory_before,
            "after": memory_after
        }
    }
