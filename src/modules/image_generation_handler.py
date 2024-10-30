from logger import app_logger
from utils import filter_content
from image_generation import generate_dalle_images, generate_flux1_images

def generate_images(event_analysis, event_story, comic_artist_style, progress_callback=None):
    """
    Generate images using DALL-E first, then try FLUX.1 if DALL-E fails due to safety system,
    and finally fall back to DALL-E with the original story if both fail.
    """
    app_logger.debug("Starting image generation process")
    
    if progress_callback:
        progress_callback(0, "Starting image generation with DALL-E")
    
    # First attempt: DALL-E with generated script
    try:
        app_logger.debug(f"Attempting DALL-E with generated script and style: {comic_artist_style}")
        image_results = generate_dalle_images(filter_content(event_analysis), event_story, comic_artist_style)
        if image_results:
            app_logger.debug(f"Successfully generated {len(image_results)} images with DALL-E using generated script")
            if progress_callback:
                progress_callback(100, f"Successfully generated {len(image_results)} images")
            return image_results
        else:
            app_logger.debug("DALL-E did not return any images")
            if progress_callback:
                progress_callback(30, "DALL-E generation failed, trying FLUX.1")
    except Exception as e:
        app_logger.warning(f"DALL-E image generation failed with generated script: {str(e)}")
        if progress_callback:
            progress_callback(30, "DALL-E generation failed, trying FLUX.1")
    
    # Second attempt: FLUX.1 with generated script
    try:
        app_logger.debug(f"Attempting FLUX.1 with generated script and style: {comic_artist_style}")
        if progress_callback:
            progress_callback(40, "Generating images with FLUX.1")
        image_results = generate_flux1_images(filter_content(event_analysis), event_story, comic_artist_style)
        if image_results:
            app_logger.debug(f"Successfully generated {len(image_results)} images with FLUX.1 using generated script")
            if progress_callback:
                progress_callback(100, f"Successfully generated {len(image_results)} images")
            return image_results
        else:
            app_logger.debug("FLUX.1 did not return any images")
            if progress_callback:
                progress_callback(70, "FLUX.1 generation failed, trying DALL-E with original story")
    except Exception as e:
        app_logger.warning(f"FLUX.1 image generation failed: {str(e)}")
        if progress_callback:
            progress_callback(70, "FLUX.1 generation failed, trying DALL-E with original story")
    
    # Third attempt: DALL-E with original story
    try:
        app_logger.debug(f"Attempting DALL-E with original story and style: {comic_artist_style}")
        if progress_callback:
            progress_callback(80, "Final attempt with DALL-E using original story")
        image_results = generate_dalle_images(filter_content(event_story), event_story, comic_artist_style)
        if image_results:
            app_logger.debug(f"Successfully generated {len(image_results)} images with DALL-E using original story")
            if progress_callback:
                progress_callback(100, f"Successfully generated {len(image_results)} images")
            return image_results
        else:
            app_logger.debug("DALL-E did not return any images with original story")
            if progress_callback:
                progress_callback(100, "Failed to generate images")
    except Exception as e:
        app_logger.error(f"DALL-E image generation failed with original story: {str(e)}")
        if progress_callback:
            progress_callback(100, "Failed to generate images")
    
    app_logger.error("All image generation attempts failed")
    return None
