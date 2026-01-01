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

# Video settings
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
VIDEO_FPS = 30

# Debug mode
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
