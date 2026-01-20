
import os
import sys
# Add current directory to path to find config
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import google.generativeai as genai
try:
    from config import GEMINI_API_KEY
except ImportError:
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def test_imagen():
    if not GEMINI_API_KEY:
        print("API key not found")
        return

    genai.configure(api_key=GEMINI_API_KEY)
    
    # Check for available models that might support image generation
    print("Checking available models...")
    try:
        for m in genai.list_models():
            if 'generate_content' in m.supported_generation_methods:
                print(f"Model ID: {m.name}")
    except Exception as e:
        print(f"Error listing models: {e}")

    # The specific model requested by user
    model_name = "gemini-3-pro-image-preview"
    
    prompt = "A high-quality 3D render of a futuristic AI robot teaching humans, vibrant colors, cinematic lighting"
    
    print(f"\nAttempting to generate image with model: {model_name}")
    print(f"Prompt: {prompt}")
    
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        
        # Check if we got an image
        if hasattr(response, 'candidates') and response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data'):
                    print("Successfully generated image data!")
                    # Save for verification
                    with open("test_image.png", "wb") as f:
                        f.write(part.inline_data.data)
                    print("Saved to test_image.png")
                    return
        print("Model call succeeded but no image data found in response.")
        print(f"Response: {response}")
    except Exception as e:
        print(f"Error during generation: {e}")

if __name__ == "__main__":
    test_imagen()
