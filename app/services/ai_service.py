import requests
import json
from PIL import Image
from typing import Optional, Tuple
import io
import os
import logging
from app.config.settings import settings
from app.services.image_service import apply_logo_to_product, image_to_bytes
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)


class AIService:
    """Service for AI-powered mockup generation using piapi.ai API"""
    
    def __init__(self):
        self.api_url = "https://api.piapi.ai/v1/chat/completions"
        self.api_key = getattr(settings, 'PIAPI_API_KEY', None)
        self.storage_service = StorageService()
        
    async def initialize_models(self):
        """Initialize AI service (no local models needed)"""
        try:
            if not self.api_key:
                logger.warning("PIAPI_API_KEY not set in settings")
            
            logger.info("AI service initialized for piapi.ai")
            
        except Exception as e:
            logger.error(f"Failed to initialize AI service: {e}")
            raise
    
    async def download_image(self, url: str) -> Image.Image:
        """Download image from URL"""
        try:
            # Handle relative URLs by converting to absolute URLs
            if url.startswith('/'):
                path = "./"+url
                return Image.open(path).convert('RGB')
            else:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                return Image.open(io.BytesIO(response.content)).convert('RGB')
        except Exception as e:
            logger.error(f"Failed to download image from {url}: {e}")
            raise
    
    def get_absolute_url(self, url: str) -> str:
        """Convert relative URL to absolute URL for API"""
        if url.startswith('/'):
            # For local development, use localhost
            base_url = getattr(settings, 'BASE_URL', 'http://localhost:5371')
            return f"{base_url}{url}"
        return url
    
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
        marking_technique: str,
        logo_scale: float = 1.0,
        logo_rotation: float = 0.0,
        logo_color: Optional[str] = None,
        use_ai: bool = True
    ) -> str:
        """Generate mockup with logo applied to product using piapi.ai"""
        try:
            if use_ai and self.api_key:
                # Use AI-powered generation via piapi.ai
                result_image = await self._generate_with_piapi(
                    product_image_url, logo_image_url, marking_zone, 
                    marking_technique, logo_scale, logo_rotation, logo_color
                )
            else:
                # Use traditional image composition
                product_image = await self.download_image(product_image_url)
                logo_image = await self.download_image(logo_image_url)
                result_image = apply_logo_to_product(
                    product_image, logo_image, marking_zone,
                    logo_scale, logo_rotation, logo_color, marking_technique
                )
            
            # Upload result to storage
            result_bytes = image_to_bytes(result_image, 'PNG')
            
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
    
    async def _generate_with_piapi(
        self,
        product_image_url: str,
        logo_image_url: str,
        marking_zone: Tuple[float, float, float, float],
        technique: str,
        logo_scale: float,
        logo_rotation: float,
        logo_color: Optional[str]
    ) -> Image.Image:
        """Generate mockup using piapi.ai API"""
        try:
            # Download and encode images as base64
            product_image = await self.download_image(product_image_url)
            logo_image = await self.download_image(logo_image_url)
            
            # Convert images to base64
            import base64
            product_bytes = image_to_bytes(product_image, 'PNG')
            logo_bytes = image_to_bytes(logo_image, 'PNG')
            
            product_b64 = base64.b64encode(product_bytes).decode('utf-8')
            logo_b64 = base64.b64encode(logo_bytes).decode('utf-8')
            
            # Get technique-specific prompt
            technique_prompt = self.get_technique_prompt(technique)
            
            # Calculate position and transform values from marking zone and parameters
            x_pos = int(marking_zone[0])  # Assuming base image size for calculation
            y_pos = int(marking_zone[1])
            scale_percent = int(logo_scale * 100)
            rotation_degrees = int(logo_rotation)
            opacity_percent = 100 if logo_color != 'transparent' else 100
            
            # Create the prompt for logo overlay
            prompt_text = f"Create Image to overlay the second image (logo) onto the first image (product). Place the logo at position x={x_pos}px and y={y_pos}px. Rotate it by {rotation_degrees} degrees around its center. Scale the logo by {scale_percent}% from its original size. Apply a {technique_prompt} with {opacity_percent}% opacity. Ensure the logo blends naturally with the surface."
            
            # Prepare the request payload
            payload = {
                "model": "gpt-4o-image",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": "https://dev.bookbabes.club/1.png" #f"data:image/png;base64,{product_b64}"
                                }
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": "https://dev.bookbabes.club/2.png" #f"data:image/png;base64,{logo_b64}"
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt_text
                            }
                        ]
                    }
                ],
                "stream": True
            }
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            }
            response = requests.post(
                self.api_url,
                headers=headers,
                data=json.dumps(payload),
                stream=True,
                timeout=240
            )
            
            response.raise_for_status()
            
            # Process the streaming response
            result_data = ""
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    logger.info(f"Received line: {line_str}")
                    if line_str.startswith('data: '):
                        data_str = line_str[6:]  # Remove 'data: ' prefix
                        if data_str.strip() == '[DONE]':
                            logger.info("Received [DONE] marker")
                            break
                        try:
                            data = json.loads(data_str)
                            logger.info(f"Parsed JSON data: {data}")
                            if 'choices' in data and len(data['choices']) > 0:
                                delta = data['choices'][0].get('delta', {})
                                if 'content' in delta:
                                    content = delta['content']
                                    logger.info(f"Received content: {content}")
                                    result_data += content
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse JSON: {data_str}, error: {e}")
                            continue
            
            logger.info(f"Complete result_data: {result_data}")
            
            # For now, if piapi returns text instead of image, fallback to traditional method
            # In a real implementation, you'd need to handle the actual image response from piapi
            logger.warning("piapi.ai returned text response, falling back to traditional method")
            
            # Fallback to traditional method
            return apply_logo_to_product(
                product_image, logo_image, marking_zone,
                logo_scale, logo_rotation, logo_color, technique
            )
            
        except Exception as e:
            logger.error(f"Error in piapi.ai generation: {e}")
            # Fallback to traditional method
            product_image = await self.download_image(product_image_url)
            logo_image = await self.download_image(logo_image_url)
            return apply_logo_to_product(
                product_image, logo_image, marking_zone,
                logo_scale, logo_rotation, logo_color, technique
            )

    def estimate_processing_time(self, use_ai: bool = True) -> int:
        """Estimate processing time in seconds"""
        if use_ai and self.api_key:
            return 30  # API processing time
        else:
            return 5  # Traditional image processing is much faster
    
    async def cleanup_models(self):
        """Clean up resources (no local models to clean)"""
        logger.info("AI service cleanup completed")


# Global AI service instance
ai_service = AIService()