"""
Neural Style Transfer Implementation

This script implements neural style transfer using TensorFlow and Keras.
It allows you to apply the style of one image to the content of another image.

How to use this script:
1. Ensure you have the required dependencies installed (TensorFlow, NumPy, Pillow).
2. Prepare your content and style images (in JPEG or PNG format).
3. Call the neural_style_transfer function with the paths to your images.
4. The resulting stylized image will be saved to the specified output path.

Example usage:
    content_image = "path/to/your/content_image.jpg"
    style_image = "path/to/your/style_image.jpg"
    output_image = "path/to/save/output_image.jpg"
    max_size = 512  # Set to None for no resizing
    
    success = neural_style_transfer(content_image, style_image, output_image, max_image_size=max_size)
    if success:
        app_logger.info("Style transfer completed successfully!")
    else:
        app_logger.error("Style transfer failed. Check logs for details.")

Note: This implementation uses a pre-trained VGG19 model for feature extraction.

VRAM Usage:
The VRAM usage for neural style transfer depends primarily on the size of the input images
and the architecture of the neural network used (in this case, VGG19). Here's a rough estimate:
- For 512x512 pixel images: Approximately 2-3 GB of VRAM
- For 1024x1024 pixel images: Approximately 8-10 GB of VRAM
- For larger images or higher resolution: 12+ GB of VRAM

You can control VRAM usage by specifying a maximum image size when calling the neural_style_transfer function.
"""

import tensorflow as tf
import numpy as np
import PIL.Image
import time
import subprocess
from tensorflow.keras.applications import vgg19

from config import Config
from logger import app_logger
from database import insert_style_transfer_operation

# Load environment variables
config = Config()

def load_and_resize_img(path_to_img, max_size=None):
    """
    Load and preprocess an image for style transfer, with optional resizing.
    
    Args:
    path_to_img (str): Path to the image file.
    max_size (int, optional): Maximum size for the image's longer side.
    
    Returns:
    tf.Tensor: Preprocessed image tensor.
    """
    img = tf.io.read_file(path_to_img)
    img = tf.image.decode_image(img, channels=3)
    img = tf.image.convert_image_dtype(img, tf.float32)

    if max_size is not None:
        shape = tf.cast(tf.shape(img)[:-1], tf.float32)
        long_dim = max(shape)
        scale = max_size / long_dim

        new_shape = tf.cast(shape * scale, tf.int32)
        img = tf.image.resize(img, new_shape)

    img = img[tf.newaxis, :]
    return img

def tensor_to_image(tensor):
    """
    Convert a tensor to a PIL Image.
    
    Args:
    tensor (tf.Tensor): Input tensor representing an image.
    
    Returns:
    PIL.Image: Converted PIL Image.
    """
    tensor = tensor*255
    tensor = np.array(tensor, dtype=np.uint8)
    if np.ndim(tensor)>3:
        assert tensor.shape[0] == 1
        tensor = tensor[0]
    return PIL.Image.fromarray(tensor)

class StyleContentModel(tf.keras.models.Model):
    """
    A model that extracts style and content features from images.
    
    This model uses a pre-trained VGG19 network to extract features
    from specified style and content layers.
    """
    def __init__(self, style_layers, content_layers):
        super(StyleContentModel, self).__init__()
        self.vgg = vgg19.VGG19(include_top=False, weights='imagenet')
        self.vgg.trainable = False
        self.style_layers = style_layers
        self.content_layers = content_layers
        self.num_style_layers = len(style_layers)
        self.vgg_layers = [self.vgg.get_layer(name).output for name in style_layers + content_layers]
        self.model = tf.keras.Model([self.vgg.input], self.vgg_layers)

    def call(self, inputs):
        """
        Extract style and content features from the input image.
        
        Args:
        inputs (tf.Tensor): Input image tensor.
        
        Returns:
        dict: Dictionary containing style and content features.
        """
        inputs = inputs*255.0
        preprocessed_input = vgg19.preprocess_input(inputs)
        outputs = self.model(preprocessed_input)
        style_outputs, content_outputs = (outputs[:self.num_style_layers], 
                                          outputs[self.num_style_layers:])

        style_outputs = [gram_matrix(style_output)
                         for style_output in style_outputs]

        content_dict = {content_name: value 
                        for content_name, value 
                        in zip(self.content_layers, content_outputs)}

        style_dict = {style_name: value
                      for style_name, value
                      in zip(self.style_layers, style_outputs)}

        return {'content': content_dict, 'style': style_dict}

def gram_matrix(input_tensor):
    """
    Compute the Gram matrix of an input tensor.
    
    The Gram matrix is used to capture style information from feature maps.
    
    Args:
    input_tensor (tf.Tensor): Input feature map tensor.
    
    Returns:
    tf.Tensor: Gram matrix of the input tensor.
    """
    result = tf.linalg.einsum('bijc,bijd->bcd', input_tensor, input_tensor)
    input_shape = tf.shape(input_tensor)
    num_locations = tf.cast(input_shape[1]*input_shape[2], tf.float32)
    return result/(num_locations)

def style_content_loss(outputs, style_targets, content_targets, style_weight, content_weight):
    """
    Compute the total loss for style transfer.
    
    This function calculates both style and content losses and combines them.
    
    Args:
    outputs (dict): Output features from the style-content model.
    style_targets (dict): Target style features.
    content_targets (dict): Target content features.
    style_weight (float): Weight for style loss.
    content_weight (float): Weight for content loss.
    
    Returns:
    tf.Tensor: Total loss (style loss + content loss).
    """
    style_outputs = outputs['style']
    content_outputs = outputs['content']
    style_loss = tf.add_n([tf.reduce_mean((style_outputs[name]-style_targets[name])**2) 
                           for name in style_outputs.keys()])
    style_loss *= style_weight / len(style_outputs)

    content_loss = tf.add_n([tf.reduce_mean((content_outputs[name]-content_targets[name])**2) 
                             for name in content_outputs.keys()])
    content_loss *= content_weight / len(content_outputs)
    loss = style_loss + content_loss
    return loss

@tf.function()
def train_step(image, extractor, style_targets, content_targets, style_weight, content_weight, opt):
    """
    Perform one optimization step for style transfer.
    
    This function computes the loss and updates the image using gradient descent.
    
    Args:
    image (tf.Variable): The image being optimized.
    extractor (StyleContentModel): Model to extract style and content features.
    style_targets (dict): Target style features.
    content_targets (dict): Target content features.
    style_weight (float): Weight for style loss.
    content_weight (float): Weight for content loss.
    opt (tf.optimizers.Optimizer): Optimizer for updating the image.
    """
    with tf.GradientTape() as tape:
        outputs = extractor(image)
        loss = style_content_loss(outputs, style_targets, content_targets, style_weight, content_weight)

    grad = tape.gradient(loss, image)
    opt.apply_gradients([(grad, image)])
    image.assign(tf.clip_by_value(image, clip_value_min=0.0, clip_value_max=1.0))

def estimate_vram_usage(image_size):
    """
    Estimate the VRAM usage for neural style transfer based on image size.
    
    Args:
    image_size (tuple): Size of the image (height, width).
    
    Returns:
    float: Estimated VRAM usage in GB.
    """
    # Rough estimate based on VGG19 architecture
    base_vram = 1  # GB, for model weights and other overhead
    image_vram = (image_size[0] * image_size[1] * 4 * 8) / (1024 ** 3)  # GB
    return base_vram + image_vram * 3  # Multiply by 3 for safety margin

def get_available_gpu_memory():
    """
    Get the available GPU memory.
    
    Returns:
    float: Available GPU memory in GB, or None if not available.
    """
    try:
        output = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.free', '--format=csv,nounits,noheader'])
        memory_free = int(output.decode('ascii').split('\n')[0])
        return memory_free / 1024  # Convert to GB
    except:
        app_logger.warning("Unable to query GPU memory. nvidia-smi might not be available.")
        return None

def run_style_transfer(content_image, style_image, num_iterations=1000):
    """
    Run the style transfer algorithm.
    
    This function performs the main style transfer process, optimizing an image
    to match the content of one image and the style of another.
    
    Args:
    content_image (tf.Tensor): Content image tensor.
    style_image (tf.Tensor): Style image tensor.
    num_iterations (int): Number of optimization iterations to perform.
    
    Returns:
    PIL.Image: The resulting stylized image.
    """
    # Define content and style layers
    content_layers = ['block5_conv2'] 
    style_layers = ['block1_conv1',
                    'block2_conv1',
                    'block3_conv1', 
                    'block4_conv1', 
                    'block5_conv1']

    # Create the style-content model
    extractor = StyleContentModel(style_layers, content_layers)

    # Extract style and content targets
    style_targets = extractor(style_image)['style']
    content_targets = extractor(content_image)['content']

    # Initialize the image to be optimized
    image = tf.Variable(content_image)

    # Set up the optimizer
    opt = tf.optimizers.Adam(learning_rate=0.02, beta_1=0.99, epsilon=1e-1)

    # Set style and content weights
    style_weight=1e-2
    content_weight=1e4

    # Run the optimization process
    start = time.time()
    for n in range(num_iterations):
        train_step(image, extractor, style_targets, content_targets, style_weight, content_weight, opt)
        if n % 100 == 0:
            app_logger.info(f"Iteration {n}")

    end = time.time()
    app_logger.info(f"Total time: {end-start:.1f}s")

    # Convert the result to an image
    return tensor_to_image(image)

def neural_style_transfer(content_image_path, style_image_path, output_path, max_image_size=None):
    """
    Perform neural style transfer and save the result.
    
    This is the main function to be called by users. It handles the entire process
    of style transfer, including logging and database operations.
    
    Args:
    content_image_path (str): Path to the content image.
    style_image_path (str): Path to the style image.
    output_path (str): Path where the resulting image will be saved.
    max_image_size (int, optional): Maximum size for the image's longer side.
    
    Returns:
    bool: True if the process was successful, False otherwise.
    """
    try:
        # Load and resize images if necessary
        content_image = load_and_resize_img(content_image_path, max_image_size)
        style_image = load_and_resize_img(style_image_path, max_image_size)
        
        # Estimate VRAM usage
        image_size = content_image.shape[1:3]
        estimated_vram = estimate_vram_usage(image_size)
        available_vram = get_available_gpu_memory()
        
        if available_vram is not None and estimated_vram > available_vram:
            app_logger.warning(f"Estimated VRAM usage ({estimated_vram:.2f} GB) exceeds available GPU memory ({available_vram:.2f} GB). Consider using a smaller image size.")
        
        # Run the style transfer
        result = run_style_transfer(content_image, style_image)
        
        # Save the result
        result.save(output_path)
        
        # Log the operation in the database
        insert_style_transfer_operation(
            content_image_path, style_image_path, output_path, str(image_size), estimated_vram, time.time()
        )
        
        app_logger.info(f"Style transfer completed. Result saved to {output_path}")
        return True
    except Exception as e:
        app_logger.error(f"Error during style transfer: {str(e)}")
        return False

if __name__ == "__main__":
    # Example usage
    content_image = "path_to_content_image.jpg"
    style_image = "path_to_style_image.jpg"
    output_image = "output_styled_image.jpg"
    max_size = 512  # Set to None for no resizing
    
    success = neural_style_transfer(content_image, style_image, output_image, max_image_size=max_size)
    if success:
        app_logger.info("Style transfer completed successfully!")
    else:
        app_logger.error("Style transfer failed. Check logs for details.")
