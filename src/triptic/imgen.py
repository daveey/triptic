"""Image generation utilities for triptic."""

from pathlib import Path


def generate_svg_triplet(name: str, prompt: str, output_paths: dict[str, Path]) -> dict[str, Path]:
    """
    Generate a triplet of SVG images based on a prompt.

    Args:
        name: The name/identifier for this image set
        prompt: Text description of what to generate
        output_paths: Dict with keys 'left', 'center', 'right' mapping to output file paths

    Returns:
        Dict mapping screen positions to the generated file paths
    """
    # Define colors for each screen position
    colors = {
        'left': '#3498db',    # Blue
        'center': '#e74c3c',  # Red
        'right': '#2ecc71',   # Green
    }

    # Screen dimensions (portrait)
    width = 1080
    height = 1920

    for screen, path in output_paths.items():
        # Generate a simple SVG with the prompt text
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
</svg>
'''
        # Write the SVG file
        path.write_text(svg_content)

    return output_paths
