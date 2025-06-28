from PIL import Image, ImageEnhance, ImageFilter
import cv2
import numpy as np
from fastapi import UploadFile
from typing import Tuple, Optional
import io
import magic
from app.config.settings import settings
from app.core.exceptions import FileUploadError
import logging

logger = logging.getLogger(__name__)


def validate_image(file: UploadFile) -> None:
    """Validate uploaded image file"""
    # Check file size
    if file.size > settings.MAX_FILE_SIZE:
        raise FileUploadError(f"File size too large. Maximum {settings.MAX_FILE_SIZE} bytes allowed.")
    
    # Check file extension
    file_extension = None
    if file.filename:
        file_extension = f".{file.filename.split('.')[-1].lower()}"
        if file_extension not in settings.ALLOWED_IMAGE_EXTENSIONS:
            raise FileUploadError(f"Invalid file type. Allowed types: {', '.join(settings.ALLOWED_IMAGE_EXTENSIONS)}")
    
    # Read file content for validation
    try:
        file.file.seek(0)
        content = file.file.read(1024)  # Read first 1KB
        file.file.seek(0)  # Reset pointer
        
        # Check MIME type
        mime_type = magic.from_buffer(content, mime=True)
        if not mime_type.startswith('image/'):
            raise FileUploadError("File is not a valid image")
            
    except Exception as e:
        raise FileUploadError(f"Invalid image file: {str(e)}")


async def upload_image(file: UploadFile, folder: str = "images") -> str:
    """Upload and validate image"""
    validate_image(file)
    
    from app.services.storage_service import StorageService
    storage = StorageService()
    
    # Generate unique filename
    import uuid
    import os
    file_extension = os.path.splitext(file.filename)[1] if file.filename else '.jpg'
    unique_filename = f"{folder}/{uuid.uuid4()}{file_extension}"
    
    # Upload to S3
    url = await storage.upload_file(file, unique_filename)
    return url


def resize_image(image: Image.Image, max_size: Tuple[int, int] = (2048, 2048)) -> Image.Image:
    """Resize image while maintaining aspect ratio"""
    image.thumbnail(max_size, Image.Resampling.LANCZOS)
    return image


def enhance_image(image: Image.Image, brightness: float = 1.0, contrast: float = 1.0, sharpness: float = 1.0) -> Image.Image:
    """Apply image enhancements"""
    if brightness != 1.0:
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(brightness)
    
    if contrast != 1.0:
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(contrast)
    
    if sharpness != 1.0:
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(sharpness)
    
    return image


def remove_background(image_path: str) -> Optional[Image.Image]:
    """Remove background from image (basic implementation)"""
    try:
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            return None
        
        # Convert to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Create mask using GrabCut algorithm
        mask = np.zeros(image_rgb.shape[:2], np.uint8)
        
        # Define rectangle around the object (rough estimation)
        height, width = image_rgb.shape[:2]
        rect = (int(width*0.1), int(height*0.1), int(width*0.8), int(height*0.8))
        
        # Initialize background and foreground models
        bgd_model = np.zeros((1, 65), np.float64)
        fgd_model = np.zeros((1, 65), np.float64)
        
        # Apply GrabCut
        cv2.grabCut(image_rgb, mask, rect, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_RECT)
        
        # Create final mask
        mask2 = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')
        
        # Apply mask to image
        result = image_rgb * mask2[:, :, np.newaxis]
        
        # Convert back to PIL Image with transparency
        result_image = Image.fromarray(result)
        result_image = result_image.convert("RGBA")
        
        # Make background transparent
        data = result_image.getdata()
        new_data = []
        for item in data:
            # Change all black (or nearly black) pixels to transparent
            if item[0] < 10 and item[1] < 10 and item[2] < 10:
                new_data.append((255, 255, 255, 0))  # Transparent
            else:
                new_data.append(item)
        
        result_image.putdata(new_data)
        return result_image
        
    except Exception as e:
        logger.error(f"Error removing background: {e}")
        return None


def detect_marking_zones(image_path: str) -> list:
    """Automatically detect potential marking zones on products"""
    try:
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            return []
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Edge detection
        edges = cv2.Canny(blurred, 50, 150)
        
        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter and analyze contours for potential marking zones
        zones = []
        height, width = image.shape[:2]
        
        for contour in contours:
            # Calculate contour area
            area = cv2.contourArea(contour)
            
            # Filter by area (should be reasonable size for marking)
            if area > (width * height * 0.01) and area < (width * height * 0.5):
                # Get bounding rectangle
                x, y, w, h = cv2.boundingRect(contour)
                
                # Convert to relative coordinates
                zones.append({
                    'x': x / width,
                    'y': y / height,
                    'width': w / width,
                    'height': h / height,
                    'confidence': min(1.0, area / (width * height * 0.1))
                })
        
        # Sort by confidence and return top 3
        zones.sort(key=lambda z: z['confidence'], reverse=True)
        return zones[:3]
        
    except Exception as e:
        logger.error(f"Error detecting marking zones: {e}")
        return []


def create_texture_overlay(
    base_image: Image.Image,
    texture_type: str,
    opacity: float = 0.8  # Increased opacity for more vivid logos
) -> Image.Image:
    """Create texture overlay for different marking techniques"""
    try:
        width, height = base_image.size
        
        # Create texture based on type
        if texture_type == "BORDADO":  # Embroidery
            # Create thread-like texture
            texture = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            # Add embroidery pattern simulation
            # This is a simplified version - real implementation would be more complex
            
        elif texture_type == "GRABADO_LASER":  # Laser engraving
            # Create engraved effect
            texture = base_image.filter(ImageFilter.EMBOSS)
            texture = texture.convert('RGBA')
            
        elif texture_type == "SERIGRAFIA":  # Screen printing
            # Smooth color overlay
            texture = base_image.copy()
            
        else:
            # Default texture
            texture = base_image.copy()
        
        # Apply opacity
        if hasattr(texture, 'putalpha'):
            alpha = texture.split()[-1]
            alpha = alpha.point(lambda p: int(p * opacity))
            texture.putalpha(alpha)
        
        return texture
        
    except Exception as e:
        logger.error(f"Error creating texture overlay: {e}")
        return base_image


def apply_logo_to_product(
    product_image: Image.Image,
    logo_image: Image.Image,
    position: Tuple[float, float, float, float],  # x, y, width, height (as percentages)
    scale: float = 1.0,
    rotation: float = 0.0,
    color_overlay: Optional[str] = None,
    texture_type: str = "SERIGRAFIA"
) -> Image.Image:
    """Apply logo to product image with specified parameters"""
    try:
        product_width, product_height = product_image.size
        logo_width, logo_height = logo_image.size
        
        # Calculate absolute position and size
        x = int(position[0] * product_width)
        y = int(position[1] * product_height)
        # zone_width = int(0.5* product_width)
        # zone_height = int(0.5 * product_height)
        logger.info(F"{x} {y} {zone_width}  {zone_height}")
        # zone_width = int(position[2] * product_width)
        # zone_height = int(position[3] * product_height)
        
        # Resize logo to fit zone
        logo_copy = logo_image.copy()
        logo_copy.thumbnail((logo_width, logo_height), Image.Resampling.LANCZOS)
        
        # Apply scale
        if scale != 1.0:
            new_size = (int(logo_copy.width * scale), int(logo_copy.height * scale))
            logo_copy = logo_copy.resize(new_size, Image.Resampling.LANCZOS)
        
        # Enhance logo vividness
        # Increase brightness and contrast to make logo more prominent
        # logo_copy = enhance_image(logo_copy, brightness=1.2, contrast=1.3, sharpness=1.2)
        
        # Apply rotation
        if rotation != 0.0:
            logo_copy = logo_copy.rotate(rotation, expand=True)
        
        # Apply color overlay if specified
        if color_overlay and color_overlay.lower() != 'transparent':
            try:
                # Convert hex color to RGB
                if color_overlay.startswith('#'):
                    color_overlay = color_overlay[1:]
                
                # Validate hex color length
                if len(color_overlay) != 6:
                    logger.warning(f"Invalid color format: {color_overlay}")
                    rgb_color = (0, 0, 0)  # Default to black
                else:
                    rgb_color = tuple(int(color_overlay[i:i+2], 16) for i in (0, 2, 4))
                
                # Apply color tint with higher opacity for vividness
                if logo_copy.mode != 'RGBA':
                    logo_copy = logo_copy.convert('RGBA')
                
                # Create color overlay with higher opacity (200 instead of 128)
                colored_logo = Image.new('RGBA', logo_copy.size, rgb_color + (200,))
                
                # Use multiply blend mode for more vivid colors
                logo_data = logo_copy.getdata()
                color_data = colored_logo.getdata()
                new_data = []
                
                for i in range(len(logo_data)):
                    r1, g1, b1, a1 = logo_data[i]
                    r2, g2, b2, a2 = color_data[i]
                    
                    # Multiply blend mode for vivid colors
                    r = int((r1 * r2) / 255)
                    g = int((g1 * g2) / 255)
                    b = int((b1 * b2) / 255)
                    a = max(a1, a2)
                    
                    new_data.append((r, g, b, a))
                
                logo_copy.putdata(new_data)
            except ValueError as e:
                logger.warning(f"Error parsing color {color_overlay}: {e}") 
                # Skip color overlay on error
        
        # Apply texture effect
        logo_copy = create_texture_overlay(logo_copy, texture_type)
        
        # Create final composite
        result = product_image.copy()
        if result.mode != 'RGBA':
            result = result.convert('RGBA')
        
        # Center logo in the marking zone
        paste_x = x + (zone_width - logo_copy.width) // 2
        paste_y = y + (zone_height - logo_copy.height) // 2
        
        # Paste logo onto product
        if logo_copy.mode == 'RGBA':
            result.paste(logo_copy, (paste_x, paste_y), logo_copy)
        else:
            result.paste(logo_copy, (paste_x, paste_y))
        
        return result
        
    except Exception as e:
        logger.error(f"Error applying logo to product: {e}")
        return product_image


def image_to_bytes(image: Image.Image, format: str = 'PNG') -> bytes:
    """Convert PIL Image to bytes"""
    bio = io.BytesIO()
    image.save(bio, format=format)
    return bio.getvalue()