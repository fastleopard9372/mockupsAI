import torch
from diffusers import StableDiffusionControlNetPipeline, ControlNetModel
from PIL import Image, ImageFilter
import cv2
import numpy as np
import requests
from typing import Optional, Tuple
import io
import os
import logging
from app.config.settings import settings
from app.services.image_service import apply_logo_to_product, image_to_bytes
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)


class AIService:
    """Service for AI-powered mockup generation using Stable Diffusion + ControlNet"""
    
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.pipeline = None
        self.controlnet = None
        self.storage_service = StorageService()
        
    async def initialize_models(self):
        """Initialize AI models (called once on startup)"""
        try:
            # Load ControlNet for better control over generation
            self.controlnet = ControlNetModel.from_pretrained(
                "lllyasviel/sd-controlnet-canny",
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32
            )
            
            # Load Stable Diffusion pipeline with ControlNet
            self.pipeline = StableDiffusionControlNetPipeline.from_pretrained(
                "runwayml/stable-diffusion-v1-5",
                controlnet=self.controlnet,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                safety_checker=None,
                requires_safety_checker=False
            )
            
            if self.device == "cuda":
                self.pipeline = self.pipeline.to("cuda")
                # Enable memory efficient attention
                self.pipeline.enable_attention_slicing()
                self.pipeline.enable_xformers_memory_efficient_attention()
            
            logger.info(f"AI models initialized on {self.device}")
            
        except Exception as e:
            logger.error(f"Failed to initialize AI models: {e}")
            raise
    
    async def download_image(self, url: str) -> Image.Image:
        """Download image from URL"""
        try:
            # Handle relative URLs by converting to absolute URLs
            if url.startswith('/'):
                # For relative URLs, we need to construct the full URL
                # Assuming the images are served from the same domain
                base_url = "http://localhost:5371"  # Default for development
                # url = f"{base_url}{url}"
            
            # response = requests.get(url, timeout=30)
            # response.raise_for_status()
            path = "./"+url
            return Image.open(path).convert('RGB')
        except Exception as e:
            logger.error(f"Failed to download image from {url}: {e}")
            raise
    
    def prepare_control_image(self, image: Image.Image) -> Image.Image:
        """Prepare control image (edge detection) for ControlNet"""
        try:
            # Convert to numpy array
            image_array = np.array(image)
            
            # Convert to grayscale
            gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
            
            # Apply Canny edge detection
            edges = cv2.Canny(gray, 100, 200)
            
            # Convert back to PIL Image
            control_image = Image.fromarray(edges).convert('RGB')
            
            return control_image
            
        except Exception as e:
            logger.error(f"Error preparing control image: {e}")
            return image
    
    def get_technique_prompt(self, technique: str) -> str:
        """Get prompt enhancement based on marking technique with fitting emphasis"""
        technique_prompts = {
            "SERIGRAFIA": "screen printed logo perfectly fitted and conforming to product surface, vibrant colors, smooth finish, logo follows product contours naturally",
            "BORDADO": "embroidered logo seamlessly integrated into fabric, raised threads conforming to material texture, logo perfectly aligned with product surface",
            "GRABADO_LASER": "laser engraved logo precisely fitted to product surface, following natural curves and contours, etched depth matches material characteristics",
            "IMPRESION_DIGITAL": "digitally printed logo perfectly mapped to product geometry, high resolution fitting exactly to surface curvature, no distortion",
            "TRANSFER_DIGITAL": "heat transfer logo conforming perfectly to product shape, smooth application following surface topology, exact fit",
            "DOMING": "3D domed logo fitted precisely to marking area, dimensional effect matching product surface, perfect alignment",
            "TAMPOGRAFIA": "pad printed logo conforming to product surface irregularities, precise fitting to curved surfaces, even coverage following contours",
            "SUBLIMACION": "sublimated logo integrated seamlessly into material, colors perfectly matched to surface, following natural product lines",
            "TERMOGRABADO": "heat embossed logo fitted to product topology, raised surface conforming to base material, metallic finish following curves",
            "VINILO_TEXTIL": "vinyl cut logo applied with perfect conformity to fabric weave and texture, clean edges following surface contours",
            "TRANSFER_SERIGRAFICO": "screen print transfer perfectly fitted to product curvature, vibrant colors conforming to surface geometry",
            "ETIQUETA_DIGITAL": "digital label conforming exactly to product surface, high quality print fitted to marking zone precisely",
            "VINILO_ADHESIVO": "adhesive vinyl logo fitted perfectly to surface texture, weather resistant application following product contours",
            "TRANSFER_CERAMICO": "ceramic transfer conforming to product surface curvature, heat resistant application fitted precisely",
            "MOLDE_3D": "3D molded logo fitted exactly to product geometry, raised surface matching base topology perfectly",
            "GRABADO_FUEGO": "fire engraved logo following natural wood grain and surface texture, charred effect fitted to material characteristics",
            "GRABADO_UV": "UV engraved logo precisely fitted to material surface, clean lines following product contours exactly",
            "GRABADO_RELIEVE": "relief engraved logo conforming to product surface topology, raised texture fitted perfectly to marking area",
            "SERIGRAFIA_CIRCULAR": "circular screen print fitted perfectly to curved surfaces, seamless application following product geometry"
        }
        
        return technique_prompts.get(technique, "logo perfectly fitted and conforming to product surface, seamlessly integrated with natural surface topology")
    
    async def generate_mockup(
        self,
        product_image_url: str,
        logo_image_url: str,
        marking_zone: Tuple[float, float, float, float],  # x, y, width, height
        technique: str,
        logo_scale: float = 1.0,
        logo_rotation: float = 0.0,
        logo_color: Optional[str] = None,
        use_ai: bool = True
    ) -> str:
        """Generate mockup with logo applied to product"""
        try:
            # Download images
            product_image = await self.download_image(product_image_url)
            logo_image = await self.download_image(logo_image_url)
            
            if use_ai and self.pipeline:
                # Use AI-powered generation
                result_image = await self._generate_with_ai(
                    product_image, logo_image, marking_zone, 
                    technique, logo_scale, logo_rotation, logo_color
                )
            else:
                # Use traditional image composition
                result_image = apply_logo_to_product(
                    product_image, logo_image, marking_zone,
                    logo_scale, logo_rotation, logo_color, technique
                )
            
            # Upload result to storage
            result_bytes = image_to_bytes(result_image, 'PNG')
            logging.info(f"=============")
            # Generate unique filename
            import uuid
            result_filename = f"mockups/{uuid.uuid4()}.png"
            result_url = await self.storage_service.upload_from_bytes(
                result_bytes, result_filename, 'image/png'
            )
            
            return result_url
            
        except Exception as e:
            logger.error(f"Error generating mockup: {e}")
            raise
    
    async def _generate_with_ai(
        self,
        product_image: Image.Image,
        logo_image: Image.Image,
        marking_zone: Tuple[float, float, float, float],
        technique: str,
        logo_scale: float,
        logo_rotation: float,
        logo_color: Optional[str]
    ) -> Image.Image:
        """Generate mockup using AI pipeline with improved logo fitting"""
        try:
            # First, apply logo traditionally as a base
            base_mockup = apply_logo_to_product(
                product_image, logo_image, marking_zone,
                logo_scale, logo_rotation, logo_color, technique
            )
            
            # Prepare control image for ControlNet
            control_image = self.prepare_control_image(base_mockup)
            
            # Create technique-specific prompt with fitting emphasis
            
            # technique_prompt = self.get_technique_prompt(technique)
            technique_prompt = self.get_technique_prompt("SERIGRAFIA")
            
            # Enhanced prompt focusing on perfect logo fitting and integration
            prompt = f"photorealistic product mockup with logo perfectly fitted and conforming to surface geometry, {technique_prompt}, logo seamlessly integrated following product contours and curves, precise logo alignment to marking area, logo wraps naturally around product shape, perfect perspective matching, realistic surface mapping, logo adapts to material texture and lighting, professional commercial photography, studio lighting, no logo distortion, exact fit to background surface topology, logo follows natural product lines and edges"
            
            negative_prompt = "floating logo, misaligned logo, distorted perspective, logo not conforming to surface, flat logo on curved surface, incorrect logo positioning, logo detached from product, unrealistic logo placement, poor surface mapping, logo ignoring product geometry, artificial placement, cartoon, sketch, drawing, low quality, blurry, amateur, washed out colors, logo floating above surface, incorrect scaling, perspective errors"
            
            # Resize images for AI processing (max 512x512 for speed)
            original_size = base_mockup.size
            max_size = 512
            
            if max(original_size) > max_size:
                ratio = max_size / max(original_size)
                new_size = (int(original_size[0] * ratio), int(original_size[1] * ratio))
                base_mockup_resized = base_mockup.resize(new_size, Image.Resampling.LANCZOS)
                control_image_resized = control_image.resize(new_size, Image.Resampling.LANCZOS)
            else:
                base_mockup_resized = base_mockup
                control_image_resized = control_image
            
            # Generate with AI - optimized parameters for better logo fitting
            with torch.no_grad():
                result = self.pipeline(
                    prompt=prompt,
                    image=control_image_resized,
                    negative_prompt=negative_prompt,
                    num_inference_steps=20,  # More steps for better quality and fitting
                    guidance_scale=5.0,  # Higher guidance for better prompt adherence
                    controlnet_conditioning_scale=1,  # Higher to better preserve structure and positioning
                    generator=torch.Generator(device=self.device).manual_seed(30)
                ).images[0]
            
            # Resize back to original size if needed
            if result.size != original_size:
                result = result.resize(original_size, Image.Resampling.LANCZOS)
            
            # Enhanced post-processing for better logo integration
            from PIL import ImageEnhance, ImageDraw, ImageFilter
            
            # Create mask for logo area with feathered edges for better blending
            mask = Image.new('L', result.size, 0)
            logo_x = int(marking_zone[0] * result.width)
            logo_y = int(marking_zone[1] * result.height)
            logo_w = int(marking_zone[2] * result.width)
            logo_h = int(marking_zone[3] * result.height)
            
            # Draw white rectangle in logo area
            draw = ImageDraw.Draw(mask)
            draw.rectangle([logo_x, logo_y, logo_x + logo_w, logo_y + logo_h], fill=255)
            
            # Apply Gaussian blur to mask for smooth blending
            mask = mask.filter(ImageFilter.GaussianBlur(radius=15))
            
            # Apply subtle sharpening to logo area for better definition
            enhanced_result = result.copy()
            enhancer = ImageEnhance.Sharpness(enhanced_result)
            enhanced_result = enhancer.enhance(1.2)  # Slight sharpening
            
            # Enhance contrast in logo area for better fitting visibility
            enhancer = ImageEnhance.Contrast(enhanced_result)
            enhanced_result = enhancer.enhance(1.15)  # Subtle contrast boost
            
            # Composite enhanced logo area with original using soft mask
            result = Image.composite(enhanced_result, result, mask)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in AI generation: {e}")
            # Fallback to traditional method
            return apply_logo_to_product(
                product_image, logo_image, marking_zone,
                logo_scale, logo_rotation, logo_color, technique
            )
    
    async def enhance_mockup(self, mockup_image: Image.Image) -> Image.Image:
        """Post-process mockup for better quality and logo fitting"""
        try:
            # Apply subtle enhancements
            from app.services.image_service import enhance_image
            
            enhanced = enhance_image(
                mockup_image,
                brightness=1.03,  # Slightly reduced to maintain realism
                contrast=1.08,    # Reduced for more natural look
                sharpness=1.15    # Increased for better logo definition
            )
            
            return enhanced
            
        except Exception as e:
            logger.error(f"Error enhancing mockup: {e}")
            return mockup_image
    
    def estimate_processing_time(self, use_ai: bool = True) -> int:
        """Estimate processing time in seconds"""
        if use_ai and self.pipeline:
            return 35 if self.device == "cuda" else 140  # Slightly longer due to more inference steps
        else:
            return 5  # Traditional image processing is much faster
    
    async def cleanup_models(self):
        """Clean up models to free memory"""
        if self.pipeline:
            del self.pipeline
            self.pipeline = None
        
        if self.controlnet:
            del self.controlnet
            self.controlnet = None
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        logger.info("AI models cleaned up")


# Global AI service instance
ai_service = AIService()