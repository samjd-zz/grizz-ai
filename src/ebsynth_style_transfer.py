
from ezsynth import ImageSynth, load_guide

# Define the paths to your images
style_path = 'source_style.png'
src_path = 'source_fullgi.png'
tgt_path = 'target_fullgi.png'

# Create an ImageSynth instance
synth = ImageSynth(style_path, src_path, tgt_path)

# Perform style transfer
synth.synthesize()
