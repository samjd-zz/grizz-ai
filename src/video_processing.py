import cv2
import numpy as np
from logger import app_logger
from PIL import Image
import traceback
from utils import analyze_frames_with_clip
from text_analysis import analyze_text_opai

def extract_frames(video_path, num_frames=5):
    """
    Extract frames from the video.
    
    :param video_path: Path to the video file
    :param num_frames: Number of frames to extract
    :return: List of extracted frames as PIL Images
    """
    try:
        app_logger.debug(f"Extracting frames from video: {video_path}")
        cap = cv2.VideoCapture(video_path)
        frames = []
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        if total_frames == 0:
            app_logger.error("Video file is empty or corrupted")
            return []

        frame_indices = np.linspace(0, total_frames - 1, num_frames, dtype=int)
        
        for i, frame_index in enumerate(frame_indices):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ret, frame = cap.read()
            if ret:
                # Convert BGR to RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(rgb_frame)
                frames.append(pil_image)
            else:
                app_logger.warning(f"Failed to read frame {i}")

        cap.release()
        app_logger.debug(f"Successfully extracted {len(frames)} frames")
        return frames
    except Exception as e:
        app_logger.error(f"Error extracting frames: {e}")
        app_logger.error(traceback.format_exc())
        return []

def get_video_summary(video_path, pbar, location="a generic city"):
    """
    Get a summary of the video content and generate a comic script.
    
    :param video_path: Path to the video file
    :param pbar: Progress bar object
    :param location: Location setting for the comic script
    :return: Generated comic script
    """
    try:
        frames = extract_frames(video_path)
        pbar.update(1)
        if not frames:
            app_logger.error("Failed to extract frames from the video")
            return "Unable to extract frames from the video"

        app_logger.debug(f"Extracted {len(frames)} frames from the video")
        frame_descriptions = analyze_frames_with_clip(frames)
        pbar.update(1)
        if not frame_descriptions:
            app_logger.error("Failed to analyze frames with CLIP and image captioning")
            return "Unable to analyze video content"

        # Combine frame descriptions into a single text
        combined_description = "\n".join(frame_descriptions)

        comic_script = analyze_text_opai(combined_description, location)
        pbar.update(1)
        if not comic_script:
            app_logger.error("Failed to generate comic script")
            return "Unable to generate comic script"

        app_logger.debug("Successfully generated comic script")
        return comic_script
    except Exception as e:
        app_logger.error(f"Unexpected error in get_video_summary: {e}")
        app_logger.error(traceback.format_exc())
        return f"Error processing video: {str(e)}"