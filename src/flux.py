import warnings
warnings.filterwarnings("ignore", message="You set `add_prefix_space`. The tokenizer needs to be converted from the slow tokenizers")

import matplotlib.pyplot as plt
import torch
from diffusers import FluxPipeline

# from huggingface_hub import snapshot_download
# snapshot_download("XLabs-Ai/flux-RealismLora", revision="main", local_dir="/home/samjd/Apps/FLUX.1-RealismLora")
# snapshot_download("black-forest-labs/FLUX.1-schnell", revision="main", local_dir="/home/samjd/Apps/FLUX.1-schnell")

model_id = "/home/samjd/Apps/FLUX.1-schnell"
#model_id = "/home/samjd/Apps/FLUX.1-RealismLora"

pipe = FluxPipeline.from_pretrained(model_id, torch_dtype=torch.bfloat16)
# #pipe.enable_model_cpu_offload() #save some VRAM by offloading the model to CPU. Remove this if you have enough GPU power
pipe.enable_sequential_cpu_offload() # offload the model to CPU in a sequential manner. This is useful for large batch sizes

# system_prompt = """
#     You are a visionary comic artist. Transform brief narratives into three detailed, 
#     visually stunning panels that convey emotions and themes through vivid imagery, character expressions, 
#     dynamic compositions, and accompanying text.
# """


prompt =""" 
The Lillooet Chamber of Commerce hosts an All-Candidates Meeting for the Fraser-Nicola riding. President 
Rachel Thompson welcomes attendees, her hands clasped together, as she introduces the evening's 
proceedings. The room is filled with murmured conversations and rustling papers. A dais stands at the far 
end, displaying the words "Fraser-Nicola All-Candidates Meeting"
"""
# image = pipe(
#     prompt,                          # The main text prompt
#     prompt_2=None,                   # Secondary prompt for T5 encoder (optional)
#     height=None,                     # Height of the generated image (optional)
#     width=None,                      # Width of the generated image (optional)
#     num_inference_steps=4,           # Number of denoising steps
#     guidance_scale=7.5,              # Controls adherence to prompt [1 to 20, default 7-7.5]
#     negative_prompt=None,            # Prompt for what to avoid in the image (optional)
#     num_images_per_prompt=1,         # Number of images to generate per prompt
#     eta=0.0,                         # Controls noise addition during denoising (optional)
#     generator=torch.Generator("cpu").manual_seed(seed),  # For reproducibility
#     latents=None,                    # Pre-generated noisy latents (optional)
#     prompt_embeds=None,              # Pre-computed text embeddings (optional)
#     negative_prompt_embeds=None,     # Embeddings for negative prompt (optional)
#     output_type="pil",               # Output format ("pil" or "np")
#     return_dict=True,                # Whether to return a FluxPipelineOutput object
#     callback=None,                   # Callback function (optional)
#     callback_steps=1,                # Frequency of callback (optional)
#     cross_attention_kwargs=None,     # Additional args for cross attention (optional)
#     joint_attention_kwargs=None,     # Additional args for joint attention (optional)
#     max_sequence_length=256,         # Maximum sequence length for the prompt
#     callback_on_step_end=None,       # Function called at end of each step (optional)
#     callback_on_step_end_tensor_inputs=None  # Tensor inputs for callback (optional)
# )

seed = 69
images = pipe(
    prompt,
    guidance_scale=7.5, # 0.0 is the for maximum creativity [1 to 20, with most models using a default of 7-7.5]
    output_type="pil",
    num_inference_steps=4, #use a larger number if you are using [dev]
    max_sequence_length=256,
    generator=torch.Generator("cpu").manual_seed(seed)
).images
#image.save("flux-schnell.png")

# Iterate over the generated images and save each one
for i, image in enumerate(images):
    filename = f"flux-schnell-{i+1}.png"
    image.save(filename)
    print(f"Generated and saved: {filename}")

print("All images generated and saved.")