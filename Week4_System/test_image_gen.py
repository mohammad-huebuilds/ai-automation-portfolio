import requests
import time
import os
import urllib.parse
import random # Added for random seed generation

def generate_image(prompt: str, width: int = 1080, height: int = 1080, 
                   max_retries: int = 3) -> str | None:
    """
    Generate an image using Pollinations.ai.
    Returns the local filename if successful, None if failed.
    """
    # Clean the prompt for URL embedding
    encoded_prompt = urllib.parse.quote(prompt)
    
    # Generate a random seed to ensure a fresh image every time
    seed = random.randint(1, 1000000)
    
    # URL updated with enhance=true and the random seed
    url = (
        f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        f"?width={width}&height={height}&nologo=true&model=flux"
        f"&enhance=true&seed={seed}"
    )
    
    print(f"Generating image...")
    print(f"Prompt: {prompt[:80]}...")
    
    for attempt in range(max_retries):
        try:
            print(f"Attempt {attempt + 1}/{max_retries}...")
            
            response = requests.get(url, timeout=60)
            
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if "image" not in content_type:
                    print(f"Got non-image response: {content_type}")
                    time.sleep(3)
                    continue
                
                filename = f"generated_image_{int(time.time())}.png"
                with open(filename, "wb") as f:
                    f.write(response.content)
                
                file_size_kb = len(response.content) / 1024
                print(f"Image saved: {filename} ({file_size_kb:.0f}KB)")
                return filename
            else:
                print(f"HTTP {response.status_code}. Retrying in 5s...")
                time.sleep(5)
                
        except requests.exceptions.Timeout:
            print(f"Timeout on attempt {attempt + 1}. Retrying...")
            time.sleep(3)
        except Exception as e:
            print(f"Error: {e}. Retrying...")
            time.sleep(3)
    
    print("Image generation failed after all retries.")
    return None

if __name__ == "__main__":
    filename = generate_image(
        "A clean minimalist visualization of AI neural networks "
        "connecting to automation workflows, dark background, "
        "electric blue accent colors, professional tech aesthetic"
    )
    
    if filename:
        print(f"\nSuccess. Open {filename} to see the result.")
    else:
        print("\nFailed. Pollinations.ai may be under heavy load — try again in a few minutes.")