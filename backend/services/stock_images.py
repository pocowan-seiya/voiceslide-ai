"""
VoiceSlide AI - Stock Image Service
Fetches relevant images from Unsplash/Pexels for slides
"""

import aiohttp
import base64
from typing import Optional, List, Dict, Any
from config import UNSPLASH_ACCESS_KEY


async def search_unsplash_images(
    query: str,
    per_page: int = 1,
    orientation: str = "landscape"
) -> List[Dict[str, Any]]:
    """
    Search for images on Unsplash
    """
    if not UNSPLASH_ACCESS_KEY:
        print("[Stock Images] No Unsplash API key configured")
        return []
    
    url = "https://api.unsplash.com/search/photos"
    params = {
        "query": query,
        "per_page": per_page,
        "orientation": orientation,
        "content_filter": "high"  # Safe content only
    }
    headers = {
        "Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    results = data.get("results", [])
                    print(f"[Stock Images] Found {len(results)} images for '{query}'")
                    return results
                else:
                    print(f"[Stock Images] Unsplash API error: {response.status}")
                    return []
    except Exception as e:
        print(f"[Stock Images] Error: {e}")
        return []


async def get_image_for_slide(
    keywords: List[str],
    fallback_query: str = "business technology"
) -> Optional[Dict[str, str]]:
    """
    Get a relevant image for a slide based on keywords
    Returns dict with url, credit info, etc.
    """
    # Try each keyword until we find an image
    for keyword in keywords[:3]:  # Try max 3 keywords
        results = await search_unsplash_images(keyword)
        if results:
            image = results[0]
            return {
                "url": image["urls"]["regular"],  # 1080px width
                "thumb": image["urls"]["thumb"],  # thumbnail
                "download_url": image["urls"]["raw"],
                "photographer": image["user"]["name"],
                "photographer_url": image["user"]["links"]["html"],
                "unsplash_url": image["links"]["html"],
                "alt_description": image.get("alt_description", keyword)
            }
    
    # Fallback to generic query
    results = await search_unsplash_images(fallback_query)
    if results:
        image = results[0]
        return {
            "url": image["urls"]["regular"],
            "thumb": image["urls"]["thumb"],
            "download_url": image["urls"]["raw"],
            "photographer": image["user"]["name"],
            "photographer_url": image["user"]["links"]["html"],
            "unsplash_url": image["links"]["html"],
            "alt_description": image.get("alt_description", fallback_query)
        }
    
    return None


async def download_image_as_base64(url: str) -> Optional[str]:
    """
    Download image and convert to base64 for embedding in HTML
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    b64 = base64.b64encode(image_data).decode('utf-8')
                    content_type = response.headers.get('Content-Type', 'image/jpeg')
                    return f"data:{content_type};base64,{b64}"
    except Exception as e:
        print(f"[Stock Images] Download error: {e}")
    return None


async def get_slide_image_base64(
    keywords: List[str],
    fallback_query: str = "business technology"
) -> Optional[Dict[str, str]]:
    """
    Get image for slide as base64 data URL
    """
    image_info = await get_image_for_slide(keywords, fallback_query)
    if not image_info:
        return None
    
    # Download and convert to base64
    base64_url = await download_image_as_base64(image_info["url"])
    if base64_url:
        image_info["base64_url"] = base64_url
        return image_info
    
    return None


def extract_image_keywords(slide: Dict[str, Any], strategy: Dict[str, Any]) -> List[str]:
    """
    Extract keywords from slide content for image search
    """
    slide_copy = slide.get("slide_copy", {})
    analysis = strategy.get("content_analysis", {})
    
    keywords = []
    
    # From slide content
    title = slide_copy.get("headline") or slide.get("title", "")
    if title:
        # Extract key words from title
        keywords.append(title)
    
    # From key concepts in strategy
    key_concepts = analysis.get("key_concepts", [])
    keywords.extend(key_concepts[:3])
    
    # From bullet points (first one)
    points = slide_copy.get("bullet_points") or []
    if points and len(points) > 0:
        first_point = points[0] if isinstance(points[0], str) else ""
        if first_point:
            keywords.append(first_point[:50])
    
    return keywords
