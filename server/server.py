import logging
import psutil
import gc
import os
from typing import List

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from newspaper import Article
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

openai_client = OpenAI(
    api_key=os.environ.get("OPENAI_KEY"),
)

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


def get_memory_usage():
    process = psutil.Process()
    memory_info = process.memory_info()
    logging.info(f"Current memory info: {memory_info}")
    memory_stats = {
        "rss": f"{memory_info.rss / (1024 * 1024):.2f} MB",  # Resident Set Size
        "vms": f"{memory_info.vms / (1024 * 1024):.2f} MB",  # Virtual Memory Size
    }
    return memory_stats


# Models
class URLRequest(BaseModel):
    url: str


class TTSRequest(BaseModel):
    url: str


@app.post("/api/parse_url")
async def parse_url(request: URLRequest):
    url = request.url
    logging.info(f"Received URL: {url}")

    # Memory stats before processing
    memory_before = get_memory_usage()

    try:
        # Parse article with Newspaper
        article = Article(url)
        article.download()
        article.parse()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing URL: {str(e)}")

    # Force garbage collection
    gc.collect()

    # Memory stats after processing
    memory_after = get_memory_usage()

    # Store parsed article text in memory for TTS
    app.state.last_parsed_text = article.text

    return {
        "message": f"Successfully parsed URL: {url}",
        "memory_stats": {
            "before": memory_before,
            "after": memory_after
        }
    }


def split_into_chunks(text: str, max_length: int = 2048) -> List[str]:
    """Split text into chunks of a specified maximum length."""
    return [text[i:i+max_length] for i in range(0, len(text), max_length)]


async def generate_tts(text: str, background_tasks: BackgroundTasks):
    """Generate TTS audio in the background using OpenAI."""
    logging.info("Starting TTS generation...")
    chunks = split_into_chunks(text)
    audio_files = []

    for i, chunk in enumerate(chunks):
        try:
            print("Chunk: ", chunk)
            response = openai_client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=chunk
            )
            audio_filename = f"tts_output_part_{i}.mp3"
            with open(audio_filename, "wb") as f:
                f.write(response.content)
            audio_files.append(audio_filename)
        except Exception as e:
            logging.error(f"Error generating TTS for chunk {i}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"TTS generation failed: {str(e)}")

    logging.info("TTS generation complete.")
    return audio_files


@app.post("/api/generate_tts")
async def generate_tts_endpoint(request: TTSRequest, background_tasks: BackgroundTasks):
    url = request.url
    text = app.state.last_parsed_text

    if not text:
        raise HTTPException(status_code=400, detail="No text available for TTS. Please parse a URL first.")

    # Memory stats before TTS
    memory_before = get_memory_usage()
    logging.info(f"Memory before TTS: {memory_before}")

    # Perform TTS generation
    audio_files = await generate_tts(text, background_tasks)

    # Force garbage collection
    gc.collect()

    # Memory stats after TTS
    memory_after = get_memory_usage()
    logging.info(f"Memory after TTS: {memory_after}")

    return {
        "message": f"TTS generation completed for URL: {url}",
        "audio_files": audio_files,
        "memory_stats": {
            "before": memory_before,
            "after": memory_after
        }
    }

