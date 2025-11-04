"""
clear EXIF metadata from images in bfcl_eval/data/images
"""

import os
from pathlib import Path
from PIL import Image
from tqdm import tqdm

def clear_image_metadata(image_path):
    """
    remove all metadata from an image and save it back.
    
    args:
        image_path
        
    returns:
        True if success, False otherwise
    """
    try:
        # Open the image
        img = Image.open(image_path)
        
        # Get the image data without metadata
        data = list(img.getdata())
        mode = img.mode
        size = img.size
        
        # Create a new image without metadata
        new_img = Image.new(mode, size)
        new_img.putdata(data)
        
        # Save the image, which will exclude metadata
        # For JPEG, we explicitly strip EXIF
        if image_path.suffix.lower() in ['.jpg', '.jpeg']:
            new_img.save(image_path, 'JPEG', quality=95, optimize=True)
        elif image_path.suffix.lower() == '.png':
            new_img.save(image_path, 'PNG', optimize=True)
        else:
            new_img.save(image_path)
        
        return True
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return False

def main():
    # Get the images directory path
    script_dir = Path(__file__).parent
    images_dir = script_dir / "bfcl_eval" / "data" / "images"
    
    # If script is run from a different location, try relative to berkeley-function-call-leaderboard
    if not images_dir.exists():
        images_dir = Path("berkeley-function-call-leaderboard/bfcl_eval/data/images")
    
    if not images_dir.exists():
        images_dir = Path("bfcl_eval/data/images")
    
    if not images_dir.exists():
        print(f"Error: Could not find images directory at {images_dir}")
        print("Please run this script from the repository root or specify the correct path.")
        return
    
    # Find all image files
    image_extensions = ['.jpg', '.jpeg', '.png']
    image_files = []
    for ext in image_extensions:
        image_files.extend(images_dir.glob(f"*{ext}"))
        image_files.extend(images_dir.glob(f"*{ext.upper()}"))
    
    if not image_files:
        print(f"No image files found in {images_dir}")
        return
    
    print(f"Found {len(image_files)} image files to process")
    print(f"Processing images in: {images_dir}")
    
    # Process each image with progress bar
    success_count = 0
    error_count = 0
    
    for image_path in tqdm(image_files, desc="Clearing metadata"):
        if clear_image_metadata(image_path):
            success_count += 1
        else:
            error_count += 1
    
    print(f"\nProcessing complete!")
    print(f"Successfully processed: {success_count}")
    print(f"Errors: {error_count}")

if __name__ == "__main__":
    main()