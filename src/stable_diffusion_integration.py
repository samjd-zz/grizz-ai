from stability_sdk import client
import stability_sdk.interfaces.gooseai.generation.generation_pb2 as generation
from logger import app_logger

def generate_image(prompt, api_key):
    """
    Generate an image using Stable Diffusion based on a text prompt.
    
    :param prompt: Text prompt for image generation
    :param api_key: Stable Diffusion API key
    :return: Generated image data
    """
    try:
        app_logger.info(f"Generating image with Stable Diffusion. Prompt: {prompt[:50]}...")
        
        # Initialize Stability API client
        stability_api = client.StabilityInference(key=api_key, engine="stable-diffusion-512-v2-1", verbose=True)

        # Generate image
        answers = stability_api.generate(
            prompt=prompt,
            seed=992446758,
            steps=30,
            cfg_scale=8.0,
            width=1024,
            height=1024,
            samples=1,
            sampler=generation.SAMPLER_K_LMS  # Updated to a more standard sampler
        )

        for resp in answers:
            for artifact in resp.artifacts:
                if artifact.finish_reason == generation.FILTER:
                    app_logger.warning("Your request activated the API's safety filters and could not be processed.")
                    return None
                if artifact.type == generation.ARTIFACT_IMAGE:
                    app_logger.info("Image generated successfully with Stable Diffusion")
                    return artifact.binary

        app_logger.warning("No image was generated")
        return None
    except Exception as e:
        app_logger.error(f"Error generating image with Stable Diffusion: {e}")
        return None

def create_comic_panel(script, api_key):
    """
    Create a comic panel based on a script.
    
    :param script: Text description of the comic panel
    :param api_key: Stable Diffusion API key
    :return: Generated image data for the comic panel
    """
    app_logger.info(f"Creating comic panel. Script: {script[:50]}...")
    prompt = f"Create a comic based on the following script: {script}"
    image_data = generate_image(prompt, api_key)
    if image_data:
        app_logger.info("Comic panel created successfully")
    else:
        app_logger.warning("Failed to create comic panel")
    return image_data
