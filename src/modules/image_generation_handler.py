from logger import app_logger
from utils import filter_content, sanitize_filename
from image_generation import generate_dalle_images, generate_flux1_images

def generate_images(event_analysis, event_story, comic_artist_style, progress_callback=None):
    """
    Generate images using DALL-E first, then try FLUX.1 if DALL-E fails due to safety system,
    and finally fall back to DALL-E with the original story if both fail.
    """
    app_logger.debug("Starting image generation process")
    
    if progress_callback:
        progress_callback(0, "Starting image generation with DALL-E")

    # Check if this is a "no news" case
    is_no_news = "No Current News Events" in event_story
    
    # First attempt: DALL-E with generated script
    try:
        app_logger.debug(f"Attempting DALL-E with generated script and style: {comic_artist_style}")
        image_results = generate_dalle_images(event_analysis, event_story, comic_artist_style)
        if image_results and all(image_results):  # Check that all images were generated successfully
            app_logger.debug(f"Successfully generated {len(image_results)} images with DALL-E using generated script")
            if progress_callback:
                progress_callback(100, f"Successfully generated {len(image_results)} images")
            return image_results
        else:
            app_logger.debug("DALL-E did not return all images successfully")
            if progress_callback:
                progress_callback(30, "DALL-E generation failed, trying FLUX.1")
    except Exception as e:
        app_logger.warning(f"DALL-E image generation failed with generated script: {str(e)}")
        if progress_callback:
            progress_callback(30, "DALL-E generation failed, trying FLUX.1")
    
    # For "no news" case, we want to ensure consistent image generation
    if is_no_news:
        try:
            app_logger.debug("Attempting DALL-E with specific no-news prompts")
            if progress_callback:
                progress_callback(40, "Generating no-news images")
            
            # Use specific prompts for no-news case
            no_news_prompts = [
                "A modern newsroom interior with large windows, two journalists at their desks checking computers and news monitors. The scene is well-lit and professional.",
                "A peaceful view through a large newsroom window showing a serene town landscape. A journalist holding a coffee mug looks thoughtfully out the window.",
                "Journalists and community members gathered around a planning board in a bright newsroom, discussing future stories. Local photographs and awards visible on walls."
            ]
            
            image_results = []
            for prompt in no_news_prompts:
                result = generate_dalle_images(prompt, event_story, comic_artist_style)
                if result and result[0]:  # Check if we got a valid result
                    image_results.append(result[0])
            
            if len(image_results) == 3:  # Check that we got all three images
                app_logger.debug("Successfully generated no-news images")
                if progress_callback:
                    progress_callback(100, "Successfully generated no-news images")
                return image_results
        except Exception as e:
            app_logger.warning(f"Failed to generate no-news images: {str(e)}")
    
    # Second attempt: FLUX.1 with generated script
    try:
        app_logger.debug(f"Attempting FLUX.1 with generated script and style: {comic_artist_style}")
        if progress_callback:
            progress_callback(40, "Generating images with FLUX.1")
        image_results = generate_flux1_images(event_analysis, event_story, comic_artist_style)
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
        app_logger.error(f"DALL-E image generation failed with original story: {e}")
        if progress_callback:
            progress_callback(100, "Failed to generate images")
    
    app_logger.error("All image generation attempts failed")
    return None
