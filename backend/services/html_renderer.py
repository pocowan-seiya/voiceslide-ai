"""
HTML-to-Image Renderer (Lightweight Alternative to Playwright)

This module provides a lightweight HTML to PNG renderer using Node.js html-to-image,
consuming ~50MB per process vs Playwright's ~500MB.

Usage:
    from services.html_renderer import render_html_to_image
    
    success = await render_html_to_image(
        html_content="<html>...</html>",
        output_path="/path/to/output.png",
        width=1600,
        height=900
    )
"""

import os
import json
import asyncio
import tempfile
from pathlib import Path
from typing import Optional, Tuple

# Path to Node.js renderer script
NODE_RENDERER_PATH = Path(__file__).parent / "node_renderer.js"

# Default slide dimensions
DEFAULT_WIDTH = 1600
DEFAULT_HEIGHT = 900


async def render_html_to_image(
    html_content: str,
    output_path: str,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    timeout: float = 30.0
) -> bool:
    """
    Render HTML content to PNG image using Node.js html-to-image.
    
    Args:
        html_content: Full HTML string to render
        output_path: Path to save the PNG file
        width: Image width in pixels
        height: Image height in pixels
        timeout: Timeout in seconds
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Write HTML to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            temp_html_path = f.name
        
        try:
            # Call Node.js renderer
            result = await _call_node_renderer(
                temp_html_path, output_path, width, height, timeout
            )
            return result
        finally:
            # Cleanup temp file
            if os.path.exists(temp_html_path):
                os.remove(temp_html_path)
                
    except Exception as e:
        print(f"[html-to-image] Render error: {e}")
        return False


async def render_html_file_to_image(
    html_path: str,
    output_path: str,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    timeout: float = 30.0
) -> bool:
    """
    Render HTML file to PNG image.
    
    Args:
        html_path: Path to HTML file
        output_path: Path to save the PNG file
        width: Image width in pixels
        height: Image height in pixels
        timeout: Timeout in seconds
        
    Returns:
        True if successful, False otherwise
    """
    return await _call_node_renderer(html_path, output_path, width, height, timeout)


async def _call_node_renderer(
    html_path: str,
    output_path: str,
    width: int,
    height: int,
    timeout: float
) -> bool:
    """
    Internal function to call Node.js renderer subprocess.
    """
    cmd = [
        "node",
        str(NODE_RENDERER_PATH),
        html_path,
        output_path,
        str(width),
        str(height)
    ]
    
    print(f"[html-to-image] Rendering {width}x{height} -> {output_path}")
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout
        )
        
        if process.returncode == 0:
            try:
                result = json.loads(stdout.decode())
                if result.get('success'):
                    print(f"[html-to-image] ✓ Success: {output_path}")
                    return True
            except json.JSONDecodeError:
                pass
            return True
        else:
            error_msg = stderr.decode() if stderr else stdout.decode()
            print(f"[html-to-image] ✗ Failed: {error_msg}")
            return False
            
    except asyncio.TimeoutError:
        print(f"[html-to-image] ✗ Timeout after {timeout}s")
        return False
    except Exception as e:
        print(f"[html-to-image] ✗ Error: {e}")
        return False


# Feature flag for renderer selection
def get_renderer_type() -> str:
    """
    Get the configured renderer type.
    
    Returns:
        "playwright" or "html-to-image"
    """
    return os.getenv("SLIDE_RENDERER", "playwright")


def is_html_to_image_enabled() -> bool:
    """
    Check if html-to-image renderer is enabled.
    """
    return get_renderer_type() == "html-to-image"
