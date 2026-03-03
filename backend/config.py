# VoiceSlide AI - Backend Configuration
# This file contains API keys. In production, use environment variables.

import os
from dotenv import load_dotenv

# Try to load from .env file if it exists
load_dotenv()

# API Keys - Can be overridden by user-provided keys in requests
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")

# Authentication
ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD", "")  # Empty = no password required (local dev)

# Server configuration
HOST = "0.0.0.0"
# Use BACKEND_PORT to avoid conflict with Railway's PORT (used for frontend)
PORT = int(os.getenv("BACKEND_PORT", os.getenv("PORT", 8001)))

# File paths
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "outputs")

# Video settings (defaults: landscape 16:9)
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
VIDEO_FPS = 30

# Aspect ratio presets
ASPECT_RATIO_PRESETS = {
    "landscape": {"width": 1920, "height": 1080, "label": "16:9 (横長)"},
    "portrait":  {"width": 1080, "height": 1920, "label": "9:16 (縦長)"},
}

def get_video_dimensions(aspect_ratio: str = "landscape") -> tuple:
    """Get (width, height) for a given aspect ratio preset."""
    preset = ASPECT_RATIO_PRESETS.get(aspect_ratio, ASPECT_RATIO_PRESETS["landscape"])
    return preset["width"], preset["height"]

# Debug mode
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
