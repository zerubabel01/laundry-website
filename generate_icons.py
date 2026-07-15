import os
from PIL import Image, ImageDraw, ImageFont

def generate_icons():
    """Generate app icons for PWA."""
    # Create icons directory if it doesn't exist
    icon_dir = os.path.join(os.path.dirname(__file__), "static", "icons")
    os.makedirs(icon_dir, exist_ok=True)
    
    sizes = [192, 512]
    for size in sizes:
        path = os.path.join(icon_dir, f"icon-{size}.png")
        
        # Skip if icon already exists
        if os.path.exists(path):
            print(f"Icon {size}x{size} already exists, skipping...")
            continue
            
        print(f"Creating icon {size}x{size}...")
        
        # Create a new image with a teal background
        img = Image.new("RGBA", (size, size), (20, 184, 166, 255))
        draw = ImageDraw.Draw(img)
        
        # Draw a circular border
        border_width = int(size * 0.06)
        draw.ellipse(
            (border_width, border_width, size - border_width, size - border_width),
            outline="white",
            width=border_width
        )
        
        # Draw the laundry swirl (simplified)
        # Arc for the swirl
        arc_width = int(size * 0.06)
        draw.arc(
            (size * 0.25, size * 0.25, size * 0.75, size * 0.75),
            start=45,
            end=225,
            fill="white",
            width=arc_width
        )
        draw.arc(
            (size * 0.35, size * 0.35, size * 0.65, size * 0.65),
            start=225,
            end=45,
            fill="white",
            width=arc_width
        )
        
        # Center dot
        center = size // 2
        dot_radius = int(size * 0.08)
        draw.ellipse(
            (center - dot_radius, center - dot_radius, 
             center + dot_radius, center + dot_radius),
            fill="white"
        )
        
        # Save the image
        img.save(path)
        print(f"  ✓ Created {path}")
    
    # Create maskable icon
    maskable_path = os.path.join(icon_dir, "icon-maskable-512.png")
    if not os.path.exists(maskable_path):
        # Just copy the regular icon for maskable
        import shutil
        shutil.copy(os.path.join(icon_dir, "icon-512.png"), maskable_path)
        print(f"  ✓ Created maskable icon")

if __name__ == "__main__":
    generate_icons()
    print("\nAll icons created! Check the static/icons/ folder.")