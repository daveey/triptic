"""Image generation utilities for triptic."""

import subprocess
import json
from pathlib import Path


def call_mcp_tool(tool_name: str, arguments: dict) -> dict:
    """
    Call an MCP tool via the Claude CLI.

    Args:
        tool_name: Name of the MCP tool to call
        arguments: Dict of arguments to pass to the tool

    Returns:
        Dict containing the tool result
    """
    # This is a placeholder - in practice, you'd need to call the MCP tool
    # through the appropriate interface. For now, we'll use subprocess to call
    # the nano-banana tool directly if available.
    raise NotImplementedError("Direct MCP tool calling not yet implemented")


def generate_image_with_gemini(prompt: str, output_path: Path, screen: str) -> Path:
    """
    Generate an image using Gemini via nano-banana MCP.

    Args:
        prompt: Text description of what to generate
        output_path: Path where to save the generated image
        screen: Screen position (left, center, right) for context

    Returns:
        Path to the generated image
    """
    # Add screen-specific context to the prompt
    screen_prompts = {
        'left': f"{prompt} (left panel perspective)",
        'center': f"{prompt} (center panel, main focus)",
        'right': f"{prompt} (right panel perspective)",
    }

    full_prompt = screen_prompts.get(screen, prompt)

    print(f"  Generating {screen} image with Gemini: {full_prompt}")

    # For now, generate a simple placeholder SVG since we can't directly call MCP tools
    # TODO: Integrate with nano-banana MCP when API is available
    generate_placeholder_svg(prompt, output_path, screen)

    return output_path


def generate_placeholder_svg(prompt: str, output_path: Path, screen: str) -> None:
    """Generate a placeholder SVG image."""
    colors = {
        'left': '#3498db',
        'center': '#e74c3c',
        'right': '#2ecc71',
    }

    width = 1080
    height = 1920

    # Extract just the filename for the label
    name = output_path.stem.split('.')[0]

    svg_content = f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{width}" height="{height}" fill="{colors[screen]}"/>
  <text x="{width//2}" y="800" font-family="Arial, sans-serif" font-size="80" fill="#ffffff" text-anchor="middle" font-weight="bold">
    {prompt}
  </text>
  <text x="{width//2}" y="1000" font-family="Arial, sans-serif" font-size="60" fill="#ecf0f1" text-anchor="middle">
    {screen.upper()}
  </text>
  <text x="{width//2}" y="1150" font-family="Arial, sans-serif" font-size="50" fill="#bdc3c7" text-anchor="middle">
    #{name}
  </text>
  <text x="{width//2}" y="1300" font-family="Arial, sans-serif" font-size="40" fill="#95a5a6" text-anchor="middle">
    (AI generation coming soon)
  </text>
</svg>
'''
    output_path.write_text(svg_content)


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

    for screen, path in output_paths.items():
        generate_image_with_gemini(prompt, path, screen)

    return output_paths
