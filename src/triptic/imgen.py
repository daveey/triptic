"""Image generation utilities for triptic."""

import json
import logging
import os
import base64
from pathlib import Path
from io import BytesIO

try:
    from google import genai
    from google.genai import types
    from PIL import Image
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


def get_api_key() -> str | None:
    """Get the Gemini API key from environment or .env file."""
    # First check environment variable
    api_key = os.environ.get('GEMINI_API_KEY')
    if api_key:
        return api_key

    # Check .env file in project root
    env_file = Path.cwd() / '.env'
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith('GEMINI_API_KEY='):
                    return line.split('=', 1)[1].strip()

    return None


def save_api_key(api_key: str) -> None:
    """Save the Gemini API key to .env file."""
    env_file = Path.cwd() / '.env'

    # Read existing content
    existing_lines = []
    if env_file.exists():
        with open(env_file) as f:
            existing_lines = [line for line in f if not line.strip().startswith('GEMINI_API_KEY=')]

    # Write back with new key
    with open(env_file, 'w') as f:
        f.writelines(existing_lines)
        f.write(f'GEMINI_API_KEY={api_key}\n')

    print(f"    ✓ Saved API key to {env_file}")


def prompt_for_api_key() -> str | None:
    """Prompt user for Gemini API key."""
    print()
    print("    Gemini API key not found!")
    print("    Get your API key from: https://aistudio.google.com/apikey")
    print()

    try:
        api_key = input("    Enter your Gemini API key (or press Enter to skip): ").strip()
        if api_key:
            save_api_key(api_key)
            return api_key
    except (KeyboardInterrupt, EOFError):
        print()

    return None


def get_state_file() -> Path:
    """Get the path to the state file."""
    state_dir = Path.home() / ".state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "triptic.json"


def get_settings() -> dict:
    """Get settings from state file."""
    state_file = get_state_file()
    if not state_file.exists():
        return {}
    try:
        with open(state_file, 'r') as f:
            state = json.load(f)
            return state.get('settings', {})
    except (json.JSONDecodeError, IOError):
        return {}


def get_model() -> str:
    """Get the selected image generation model from settings."""
    settings = get_settings()
    return settings.get('model', 'imagen-4.0-fast-generate-001')


def get_video_model() -> str:
    """Get the selected video generation model from settings."""
    settings = get_settings()
    return settings.get('video_model', 'veo-3.1-generate-preview')


def get_api_key_from_settings() -> str | None:
    """Get API key from settings."""
    settings = get_settings()
    model = get_model()

    if model.startswith('imagen-'):
        return settings.get('gemini_api_key')
    elif model.startswith('grok-'):
        return settings.get('grok_api_key')

    return None


def generate_image_with_gemini(prompt: str, output_path: Path, screen: str) -> Path:
    """
    Generate an image using Google's Gemini API.

    Args:
        prompt: Text description of what to generate
        output_path: Path where to save the generated image
        screen: Screen position (left, center, right) for context

    Returns:
        Path to the generated image

    Raises:
        RuntimeError: If Gemini SDK is not available or image generation fails
    """
    # Add screen-specific context to the prompt
    screen_prompts = {
        'left': f"{prompt} (left panel perspective)",
        'center': f"{prompt} (center panel, main focus)",
        'right': f"{prompt} (right panel perspective)",
    }

    full_prompt = screen_prompts.get(screen, prompt)

    print(f"  Generating {screen} image with Gemini: {full_prompt}")

    if not GEMINI_AVAILABLE:
        raise RuntimeError("google-genai is not installed. Install with: uv add google-genai pillow")

    # Get model from settings
    model = get_model()

    # Get API key (from settings first, then env, .env file, or prompt user)
    api_key = get_api_key_from_settings()
    if not api_key:
        api_key = get_api_key()
    if not api_key and screen == 'left':  # Only prompt once for the first image
        api_key = prompt_for_api_key()

    if not api_key:
        raise RuntimeError("No Gemini API key configured. Get one at: https://aistudio.google.com/apikey")

    # Create client
    client = genai.Client(api_key=api_key)

    # Log the Imagen API call
    logging.info(f"[Imagen] Generating image for {screen} screen using model {model}")
    logging.info(f"[Imagen] Prompt: {full_prompt}")

    # Generate image using selected model
    response = client.models.generate_images(
        model=model,
        prompt=full_prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio='9:16',  # Portrait orientation for triptic displays
        )
    )

    if not response.generated_images or len(response.generated_images) == 0:
        raise RuntimeError("No images generated by Gemini API")

    # Get the first (and only) generated image
    generated_image = response.generated_images[0]

    # Ensure output has .png extension
    if output_path.suffix != '.png':
        output_path = output_path.with_suffix('.png')

    # Convert Gemini Image to PIL Image first
    gemini_img = generated_image.image

    # Get image bytes directly
    img_bytes = BytesIO(gemini_img.image_bytes)

    # Load as PIL Image
    pil_img = Image.open(img_bytes)

    # Force resize to exactly 1080x1920 to ensure consistent dimensions
    target_size = (1080, 1920)

    if pil_img.size != target_size:
        print(f"    Resizing from {pil_img.size} to {target_size}")
        pil_img = pil_img.resize(target_size, Image.Resampling.LANCZOS)

    # Save the image to file
    pil_img.save(output_path)
    print(f"    ✓ Saved to {output_path}")
    return output_path


def generate_image_with_context(prompt: str, output_path: Path, screen: str, context_images: dict[str, Path]) -> Path:
    """
    Generate an image using Google's Gemini API with context from other images.

    Args:
        prompt: Text description of what to generate
        output_path: Path where to save the generated image
        screen: Screen position (left, center, right) being generated
        context_images: Dict mapping screen names to their image paths (the other two images)

    Returns:
        Path to the generated image

    Raises:
        RuntimeError: If Gemini SDK is not available or image generation fails
    """
    if not GEMINI_AVAILABLE:
        raise RuntimeError("google-genai is not installed. Install with: uv add google-genai pillow")

    # Get model from settings
    model = get_model()

    # Get API key (from settings first, then env, .env file)
    api_key = get_api_key_from_settings()
    if not api_key:
        api_key = get_api_key()
    if not api_key:
        raise RuntimeError("No Gemini API key configured. Get one at: https://aistudio.google.com/apikey")

    # Create client
    client = genai.Client(api_key=api_key)

    # Step 1: Use Gemini's vision model to analyze the context images
    print(f"  Analyzing context images with Gemini vision model...")

    # Load context images and convert to bytes for vision API
    context_parts = []
    context_labels = []
    for ctx_screen, ctx_path in sorted(context_images.items()):
        pil_img = Image.open(ctx_path)
        # Convert PIL image to bytes
        img_bytes = BytesIO()
        pil_img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        context_parts.append(types.Part.from_bytes(data=img_bytes.read(), mime_type='image/png'))
        context_labels.append(ctx_screen)

    context_description = " and ".join(context_labels)

    # Ask Gemini to analyze the style, colors, mood, and composition
    analysis_prompt = f"""Analyze these two images from a three-panel triptych display (the {context_description.upper()} panels).

Describe in detail:
1. The overall artistic style (photorealistic, abstract, illustrated, fractal, etc.)
2. The dominant color palette and color relationships
3. The mood and atmosphere
4. Key visual elements, patterns, and compositional features
5. Lighting style and effects
6. Textures and materials
7. Any recurring motifs or themes

Be specific and detailed. This analysis will be used to generate a matching third panel."""

    # Call vision model to analyze images
    vision_response = client.models.generate_content(
        model='gemini-2.0-flash-exp',
        contents=[analysis_prompt] + context_parts
    )

    style_analysis = vision_response.text
    print(f"  Style analysis: {style_analysis[:200]}...")

    # Step 2: Build enhanced prompt using the vision analysis
    full_prompt = f"""Generate the {screen.upper()} panel of a three-panel triptych display.

STYLE ANALYSIS OF OTHER PANELS:
{style_analysis}

CONTENT REQUIREMENTS:
{prompt}

GENERATION INSTRUCTIONS:
Create an image that perfectly matches the style, color palette, mood, and artistic approach described above. The {screen.upper()} panel must look like it belongs to the same set as the analyzed panels - as if created by the same artist in the same session.

Key requirements:
- Match the exact artistic style and technique
- Use the same color palette and color relationships
- Maintain the same mood and atmosphere
- Continue any visual patterns or motifs
- Use similar lighting and compositional approach
- Ensure seamless visual continuity as part of the triptych

Generate a 9:16 portrait image (1080x1920)."""

    print(f"  Generating {screen} image with vision-analyzed context from {context_description}")

    # Log the Imagen API call
    logging.info(f"[Imagen] Generating image with context for {screen} screen using model {model}")
    logging.info(f"[Imagen] Prompt: {full_prompt}")

    # Step 3: Generate image using Imagen with the enhanced prompt
    response = client.models.generate_images(
        model=model,
        prompt=full_prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio='9:16',
        )
    )

    if not response.generated_images or len(response.generated_images) == 0:
        raise RuntimeError("No images generated by Gemini API")

    # Get the generated image
    generated_image = response.generated_images[0]

    # Ensure output has .png extension
    if output_path.suffix != '.png':
        output_path = output_path.with_suffix('.png')

    # Convert to PIL and resize
    gemini_img = generated_image.image
    img_bytes = BytesIO(gemini_img.image_bytes)
    pil_img = Image.open(img_bytes)

    # Force resize to exactly 1080x1920
    target_size = (1080, 1920)
    if pil_img.size != target_size:
        print(f"    Resizing from {pil_img.size} to {target_size}")
        pil_img = pil_img.resize(target_size, Image.Resampling.LANCZOS)

    # Save the image
    pil_img.save(output_path)
    print(f"    ✓ Saved to {output_path}")
    return output_path


def edit_image_with_gemini(edit_prompt: str, input_image_path: Path, output_path: Path) -> Path:
    """
    Generate a new image using an existing image as reference.

    This uses vision model analysis to understand the input image and generate
    a new image that maintains the style while following the edit prompt.

    Args:
        edit_prompt: Text description for the new image
        input_image_path: Path to the existing image to use as reference
        output_path: Path where to save the generated image

    Returns:
        Path to the generated image

    Raises:
        RuntimeError: If Gemini SDK is not available or image generation fails
    """
    if not GEMINI_AVAILABLE:
        raise RuntimeError("google-genai is not installed. Install with: uv add google-genai pillow")

    # Get model from settings
    model = get_model()

    # Get API key (from settings first, then env, .env file)
    api_key = get_api_key_from_settings()
    if not api_key:
        api_key = get_api_key()
    if not api_key:
        raise RuntimeError("No Gemini API key configured. Get one at: https://aistudio.google.com/apikey")

    print(f"  Generating new image with reference")
    print(f"  Prompt: {edit_prompt}")

    # Create client
    client = genai.Client(api_key=api_key)

    # Step 1: Use Gemini's vision model to analyze the input image
    print(f"  Analyzing input image with Gemini vision model...")

    # Load and convert input image to bytes for vision API
    input_image = Image.open(input_image_path)
    img_bytes = BytesIO()
    input_image.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    image_part = types.Part.from_bytes(data=img_bytes.read(), mime_type='image/png')

    # Ask Gemini to analyze the style, colors, mood, and composition
    analysis_prompt = """Analyze this image in detail.

Describe:
1. The overall artistic style (photorealistic, abstract, illustrated, fractal, etc.)
2. The dominant color palette and color relationships
3. The mood and atmosphere
4. Key visual elements, patterns, and compositional features
5. Lighting style and effects
6. Textures and materials
7. Subject matter and content
8. Any recurring motifs or themes

Be specific and detailed. This analysis will be used to generate a modified version of this image."""

    # Log the vision API call
    logging.info(f"[Imagen] Analyzing image: {input_image_path}")

    # Call vision model to analyze the image
    vision_response = client.models.generate_content(
        model='gemini-2.0-flash-exp',
        contents=[analysis_prompt, image_part]
    )

    style_analysis = vision_response.text
    print(f"  Style analysis: {style_analysis[:200]}...")

    # Step 2: Build enhanced prompt using the vision analysis
    # Put the modification first and make it the primary focus
    full_prompt = f"""CRITICAL MODIFICATION REQUIRED:
{edit_prompt}

IMPORTANT: The modification above is the PRIMARY GOAL. You MUST apply this modification prominently and clearly. The style guidance below is SECONDARY to making this change happen.

STYLE REFERENCE (for guidance only):
The original image has the following characteristics:
{style_analysis}

GENERATION INSTRUCTIONS:
1. FIRST AND FOREMOST: Implement the modification "{edit_prompt}" as the central focus of the new image
2. Make the modification PROMINENT and OBVIOUS - it should be immediately visible
3. After applying the modification, use the style reference above to inform the artistic approach
4. Maintain similar color palette and composition ONLY where it doesn't conflict with the modification
5. The modification takes precedence over maintaining the original style

Generate a 9:16 portrait image (1080x1920) that clearly shows: {edit_prompt}"""

    print(f"  Generating edited image with vision-analyzed context")

    # Log the Imagen API call
    logging.info(f"[Imagen] Generating edited image using model {model}")
    logging.info(f"[Imagen] Prompt: {full_prompt}")

    # Step 3: Generate the new image
    try:
        response = client.models.generate_images(
            model=model,
            prompt=full_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio='9:16',
            )
        )
    except Exception as api_error:
        error_msg = str(api_error)
        if 'not found' in error_msg.lower() or 'permission' in error_msg.lower():
            raise RuntimeError(
                "Image generation API is not available with your current Gemini API key. "
                "This feature requires special API access. "
                f"API error: {error_msg}"
            )
        raise RuntimeError(f"Gemini API error during image generation: {error_msg}")

    if not response.generated_images or len(response.generated_images) == 0:
        raise RuntimeError("No images generated by Gemini API")

    # Get the edited image
    generated_image = response.generated_images[0]

    # Ensure output has .png extension
    if output_path.suffix != '.png':
        output_path = output_path.with_suffix('.png')

    # Convert to PIL and resize
    gemini_img = generated_image.image
    img_bytes = BytesIO(gemini_img.image_bytes)
    pil_img = Image.open(img_bytes)

    # Force resize to exactly 1080x1920
    print(f"    Resizing from {pil_img.size} to (1080, 1920)")
    pil_img = pil_img.resize((1080, 1920), Image.Resampling.LANCZOS)

    # Save the image
    pil_img.save(output_path, 'PNG')
    print(f"  Image edited and saved to {output_path}")

    return output_path




def save_prompt_file(prompt: str, output_paths: dict[str, Path], screen_prompts: dict[str, str]) -> None:
    """
    Save the prompt information to a .prompt.txt file alongside the images.

    Args:
        prompt: The main prompt used for generation
        output_paths: Dict with keys 'left', 'center', 'right' mapping to output file paths
        screen_prompts: Dict with the actual prompts used for each screen
    """
    # Save the prompt file next to the first image (use left as reference)
    left_path = output_paths['left']
    prompt_file = left_path.parent / f"{left_path.stem.split('.')[0]}.prompt.txt"

    with open(prompt_file, 'w') as f:
        f.write(f"Main prompt: {prompt}\n\n")
        f.write("Screen-specific prompts:\n")
        f.write(f"  Left: {screen_prompts['left']}\n")
        f.write(f"  Center: {screen_prompts['center']}\n")
        f.write(f"  Right: {screen_prompts['right']}\n")


def generate_svg_triplet(name: str, prompt: str, output_paths: dict[str, Path]) -> dict[str, Path]:
    """
    Generate a triplet of images based on a prompt using Gemini.

    Args:
        name: The name/identifier for this image set
        prompt: Text description of what to generate
        output_paths: Dict with keys 'left', 'center', 'right' mapping to output file paths

    Returns:
        Dict mapping screen positions to the generated file paths
    """
    print(f"[triptic] Generating triplet with Gemini...")

    # Store the screen-specific prompts
    screen_prompts = {
        'left': f"{prompt} (left panel perspective)",
        'center': f"{prompt} (center panel, main focus)",
        'right': f"{prompt} (right panel perspective)",
    }

    for screen, path in output_paths.items():
        generate_image_with_gemini(prompt, path, screen)

    # Save prompt information
    save_prompt_file(prompt, output_paths, screen_prompts)

    return output_paths


def generate_video_from_image(input_image_path: Path, output_video_path: Path) -> Path:
    """
    Generate a video from an image using Google's Veo API.

    Args:
        input_image_path: Path to the source image
        output_video_path: Path where to save the generated video

    Returns:
        Path to the generated video

    Raises:
        RuntimeError: If Gemini SDK is not available or video generation fails
    """
    if not GEMINI_AVAILABLE:
        raise RuntimeError("google-genai is not installed. Install with: uv add google-genai pillow")

    # Get API key
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError("No Gemini API key configured. Get one at: https://aistudio.google.com/apikey")

    print(f"  Generating video from image with Veo")

    # Log the Veo API call
    logging.info(f"[Veo] Generating video from image: {input_image_path}")

    # Load the input image (must be PNG or JPEG)
    input_image = Image.open(input_image_path)

    # Create client
    client = genai.Client(api_key=api_key)

    # Convert PIL image to bytes for the API
    img_bytes = BytesIO()
    input_image.save(img_bytes, format='PNG')
    img_bytes.seek(0)

    # Create reference image for Veo with proper format
    ref_image = types.Image(
        imageBytes=img_bytes.read(),
        mimeType='image/png'
    )

    # Generate video using selected video model
    video_model = get_video_model()
    try:
        logging.info(f"[Veo] Calling generate_videos API with model: {video_model}")

        operation = client.models.generate_videos(
            model=video_model,
            prompt="Animate this image with subtle, natural movements. Keep the composition stable.",
            image=ref_image,
            config=types.GenerateVideosConfig(
                number_of_videos=1,
                aspect_ratio='9:16',  # Portrait orientation for triptic displays
            )
        )

        # Wait for the operation to complete by polling
        logging.info(f"[Veo] Waiting for video generation to complete (operation: {operation})")
        print("  Waiting for video generation to complete (this may take a few minutes)...")

        import time
        max_wait = 600  # 10 minutes max
        start_time = time.time()
        response = None
        while time.time() - start_time < max_wait:
            # Check operation status by fetching it again (pass the operation object, not string)
            try:
                op_status = client.operations.get(operation)
                logging.info(f"[Veo] Operation status - done: {op_status.done}")
                if op_status.done:
                    logging.info(f"[Veo] Video generation complete, extracting response")
                    response = op_status.response
                    logging.info(f"[Veo] Response type: {type(response)}")
                    break
            except Exception as poll_error:
                logging.error(f"[Veo] Error polling operation: {poll_error}")
                raise
            time.sleep(5)  # Poll every 5 seconds
        else:
            raise RuntimeError("Video generation timed out after 10 minutes")

        if response is None:
            raise RuntimeError("No response received from video generation")

        logging.info(f"[Veo] Checking for generated videos in response")

    except Exception as api_error:
        error_msg = str(api_error)
        import traceback
        traceback_str = traceback.format_exc()
        logging.error(f"[Veo] API error: {error_msg}\n{traceback_str}")
        if 'not found' in error_msg.lower() or 'permission' in error_msg.lower():
            raise RuntimeError(
                "Video generation API is not available with your current Gemini API key. "
                "This feature requires special API access. "
                f"API error: {error_msg}"
            )
        raise RuntimeError(f"Gemini Veo API error during video generation: {error_msg}")

    if not hasattr(response, 'generated_videos') or not response.generated_videos or len(response.generated_videos) == 0:
        logging.error(f"[Veo] Response does not contain generated_videos. Response attributes: {dir(response)}")
        raise RuntimeError("No videos generated by Veo API")

    # Get the generated video
    generated_video = response.generated_videos[0]
    logging.info(f"[Veo] Generated video type: {type(generated_video)}, attributes: {dir(generated_video)}")

    # Ensure output has .mp4 extension
    if output_video_path.suffix != '.mp4':
        output_video_path = output_video_path.with_suffix('.mp4')

    # Write video bytes to file
    if hasattr(generated_video, 'video_bytes'):
        output_video_path.write_bytes(generated_video.video_bytes)
    elif hasattr(generated_video, 'video'):
        # Alternative: video might be a file object
        logging.info(f"[Veo] Using generated_video.video instead of video_bytes")
        video_file = generated_video.video
        # Download the video file
        client.files.download(file=video_file)
        video_file.save(str(output_video_path))
    else:
        logging.error(f"[Veo] Cannot find video bytes or video file in generated_video")
        raise RuntimeError("Generated video does not have video_bytes or video attribute")
    logging.info(f"[Veo] Video saved to {output_video_path}")
    print(f"  Video generated and saved to {output_video_path}")

    return output_video_path
