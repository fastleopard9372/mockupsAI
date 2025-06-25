import torch
from diffusers import StableDiffusionControlNetPipeline, ControlNetModel
from PIL import Image
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
        """Get prompt enhancement based on marking technique"""
        technique_prompts = {
            "SERIGRAFIA": "screen printed logo, vibrant colors, smooth finish, professional quality",
            "BORDADO": "embroidered logo, raised threads, textured surface, stitched details",
            "GRABADO_LASER": "laser engraved logo, precise lines, etched surface, subtle depth",
            "IMPRESION_DIGITAL": "digitally printed logo, high resolution, crisp details, photo quality",
            "TRANSFER_DIGITAL": "heat transfer logo, smooth application, durable finish",
            "DOMING": "3D domed logo, raised surface, glossy finish, dimensional effect",
            "TAMPOGRAFIA": "pad printed logo, precise details, smooth surface, even coverage",
            "SUBLIMACION": "sublimated logo, integrated colors, permanent application",
            "TERMOGRABADO": "heat embossed logo, raised surface, metallic finish",
            "VINILO_TEXTIL": "vinyl cut logo, clean edges, matte finish, precise application",
            "TRANSFER_SERIGRAFICO": "screen print transfer, vibrant colors, durable application",
            "ETIQUETA_DIGITAL": "digital label, high quality print, adhesive application",
            "VINILO_ADHESIVO": "adhesive vinyl logo, weather resistant, clean application",
            "TRANSFER_CERAMICO": "ceramic transfer, heat resistant, permanent application",
            "MOLDE_3D": "3D molded logo, raised surface, detailed contours",
            "GRABADO_FUEGO": "fire engraved logo, charred effect, rustic appearance",
            "GRABADO_UV": "UV engraved logo, precise details, clean finish",
            "GRABADO_RELIEVE": "relief engraved logo, raised surface, tactile texture",
            "SERIGRAFIA_CIRCULAR": "circular screen print, curved application, seamless finish"
        }
        
        return technique_prompts.get(technique, "professionally applied logo, high quality finish")
    
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
        """Generate mockup using AI pipeline"""
        try:
            # First, apply logo traditionally as a base
            base_mockup = apply_logo_to_product(
                product_image, logo_image, marking_zone,
                logo_scale, logo_rotation, logo_color, technique
            )
            
            # Prepare control image for ControlNet
            control_image = self.prepare_control_image(base_mockup)
            
            # Create technique-specific prompt
            technique_prompt = self.get_technique_prompt(technique)
            
            # Construct full prompt
            prompt = f"high quality product mockup, {technique_prompt}, professional photography, studio lighting, realistic textures, detailed surface, commercial product photo"
            
            negative_prompt = "blurry, low quality, distorted, unrealistic, cartoon, sketch, drawing, artificial, fake, poor lighting, amateur"
            
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
            
            # Generate with AI
            with torch.no_grad():
                result = self.pipeline(
                    prompt=prompt,
                    image=control_image_resized,
                    negative_prompt=negative_prompt,
                    num_inference_steps=20,  # Fewer steps for speed
                    guidance_scale=7.5,
                    controlnet_conditioning_scale=0.8,
                    generator=torch.Generator(device=self.device).manual_seed(42)
                ).images[0]
            
            # Resize back to original size if needed
            if result.size != original_size:
                result = result.resize(original_size, Image.Resampling.LANCZOS)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in AI generation: {e}")
            # Fallback to traditional method
            return apply_logo_to_product(
                product_image, logo_image, marking_zone,
                logo_scale, logo_rotation, logo_color, technique
            )
    
    async def enhance_mockup(self, mockup_image: Image.Image) -> Image.Image:
        """Post-process mockup for better quality"""
        try:
            # Apply subtle enhancements
            from app.services.image_service import enhance_image
            
            enhanced = enhance_image(
                mockup_image,
                brightness=1.05,
                contrast=1.1,
                sharpness=1.1
            )
            
            return enhanced
            
        except Exception as e:
            logger.error(f"Error enhancing mockup: {e}")
            return mockup_image
    
    def estimate_processing_time(self, use_ai: bool = True) -> int:
        """Estimate processing time in seconds"""
        if use_ai and self.pipeline:
            return 30 if self.device == "cuda" else 120  # GPU vs CPU
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