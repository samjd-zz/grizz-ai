"""
EbSynth Style Transfer Implementation

This script implements style transfer using the EbSynth algorithm via the ezsynth library.
It allows you to apply the style of one image to the content of another image.

How to use this script:
1. Ensure you have the required dependencies installed (ezsynth).
2. Prepare your style image, source image, and target image.
3. Call the ebsynth_style_transfer function with the paths to your images.
4. The resulting stylized image will be saved to the specified output path.

Note: This implementation requires the ezsynth library, which is a wrapper for EbSynth.
"""

import os
import time
from ezsynth import ImageSynth, load_guide
from config import Config
from logger import app_logger
from database import insert_ebsynth_style_transfer_operation

# Load environment variables
config = Config()

def ebsynth_style_transfer(style_path, src_path, tgt_path, output_path, use_guide=False, guide_path=None):
    """
    Perform EbSynth style transfer and save the result.
    
    This function handles the entire process of style transfer using EbSynth,
    including logging and database operations.
    
    Args:
    style_path (str): Path to the style image.
    src_path (str): Path to the source image.
    tgt_path (str): Path to the target image.
    output_path (str): Path where the resulting image will be saved.
    use_guide (bool): Whether to use a guide image for the synthesis.
    guide_path (str): Path to the guide image (required if use_guide is True).
    
    Returns:
    bool: True if the process was successful, False otherwise.
    """
    try:
        # Verify that all input files exist
        for path in [style_path, src_path, tgt_path]:
            if not os.path.exists(path):
                raise FileNotFoundError(f"Input file not found: {path}")
        
        if use_guide and (guide_path is None or not os.path.exists(guide_path)):
            raise ValueError("Guide path is required and must exist when use_guide is True")

        # Create an ImageSynth instance
        synth = ImageSynth(style_path, src_path, tgt_path)

        # Load guide if specified
        if use_guide:
            guide = load_guide(guide_path)
            synth.add_guide(guide)

        # Perform style transfer
        app_logger.info("Starting EbSynth style transfer...")
        result = synth.synthesize()

        # Save the result
        result.save(output_path)
        
        # Log the operation in the database
        insert_ebsynth_style_transfer_operation(
            style_path, src_path, tgt_path, output_path, use_guide, guide_path, time.time()
        )
        
        app_logger.info(f"EbSynth style transfer completed. Result saved to {output_path}")
        return True
    except Exception as e:
        app_logger.error(f"Error during EbSynth style transfer: {str(e)}")
        return False

def batch_ebsynth_style_transfer(style_path, src_folder, tgt_folder, output_folder, use_guide=False, guide_folder=None):
    """
    Perform EbSynth style transfer on multiple images in a batch.
    
    This function applies the style transfer to all images in the target folder,
    using corresponding images from the source folder.
    
    Args:
    style_path (str): Path to the style image.
    src_folder (str): Path to the folder containing source images.
    tgt_folder (str): Path to the folder containing target images.
    output_folder (str): Path to the folder where resulting images will be saved.
    use_guide (bool): Whether to use guide images for the synthesis.
    guide_folder (str): Path to the folder containing guide images (required if use_guide is True).
    
    Returns:
    bool: True if all processes were successful, False otherwise.
    """
    try:
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        
        src_files = sorted(os.listdir(src_folder))
        tgt_files = sorted(os.listdir(tgt_folder))
        
        if len(src_files) != len(tgt_files):
            raise ValueError("Number of source and target images must match")
        
        if use_guide:
            if guide_folder is None or not os.path.exists(guide_folder):
                raise ValueError("Guide folder is required and must exist when use_guide is True")
            guide_files = sorted(os.listdir(guide_folder))
            if len(guide_files) != len(src_files):
                raise ValueError("Number of guide images must match source and target images")
        
        success = True
        for i, (src_file, tgt_file) in enumerate(zip(src_files, tgt_files)):
            src_path = os.path.join(src_folder, src_file)
            tgt_path = os.path.join(tgt_folder, tgt_file)
            output_path = os.path.join(output_folder, f"stylized_{tgt_file}")
            
            guide_path = None
            if use_guide:
                guide_path = os.path.join(guide_folder, guide_files[i])
            
            result = ebsynth_style_transfer(style_path, src_path, tgt_path, output_path, use_guide, guide_path)
            if not result:
                app_logger.warning(f"Failed to process {tgt_file}")
                success = False
        
        return success
    except Exception as e:
        app_logger.error(f"Error during batch EbSynth style transfer: {str(e)}")
        return False

if __name__ == "__main__":
    # Example usage
    style_path = 'path/to/style_image.png'
    src_path = 'path/to/source_image.png'
    tgt_path = 'path/to/target_image.png'
    output_path = 'path/to/output_image.png'
    
    success = ebsynth_style_transfer(style_path, src_path, tgt_path, output_path)
    if success:
        app_logger.info("EbSynth style transfer completed successfully!")
    else:
        app_logger.error("EbSynth style transfer failed. Check logs for details.")

    # Example of batch processing
    # style_path = 'path/to/style_image.png'
    # src_folder = 'path/to/source_folder'
    # tgt_folder = 'path/to/target_folder'
    # output_folder = 'path/to/output_folder'
    # 
    # success = batch_ebsynth_style_transfer(style_path, src_folder, tgt_folder, output_folder)
    # if success:
    #     app_logger.info("Batch EbSynth style transfer completed successfully!")
    # else:
    #     app_logger.error("Batch EbSynth style transfer failed. Check logs for details.")
