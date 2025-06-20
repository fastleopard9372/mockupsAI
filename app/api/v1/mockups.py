from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, BackgroundTasks
from typing import Optional, List
from prisma.models import User
from pathlib import Path
import os
from prisma.enums import MockupStatus, MarkingTechnique
from app.config.database import get_db
from app.config.settings import settings
from app.api.deps import get_current_user
import logging

from app.workers.tasks import generate_mockup_task

from app.core.exceptions import (
    ValidationError, 
    NotFoundError, 
    InsufficientCreditsError,
    FileUploadError
)
from app.schemas.mockup import (
    MockupUpdate, 
    MockupResponse,
    MockupListResponse,
    MockupGenerationStatus,
    MockupTechniqueInfo,
    MockupStats,
    MockupCreateRequest
)
from app.services.image_service import validate_image, upload_image
from app.services.storage_service import StorageService
from app.workers.tasks import generate_mockup_task
import uuid

router = APIRouter()


@router.get("/mockups/techniques", response_model=List[MockupTechniqueInfo])
async def get_marking_techniques():
    """Get available marking techniques"""
    techniques = [
        MockupTechniqueInfo(
            name="SERIGRAFIA",
            display_name="Serigrafía",
            description="Screen printing technique for vibrant colors",
            premium_only=False
        ),
        MockupTechniqueInfo(
            name="BORDADO",
            display_name="Bordado",
            description="Embroidery technique for textured logos",
            premium_only=True
        ),
        MockupTechniqueInfo(
            name="GRABADO_LASER",
            display_name="Grabado Láser",
            description="Laser engraving for precise details",
            premium_only=True
        ),
        MockupTechniqueInfo(
            name="IMPRESION_DIGITAL",
            display_name="Impresión Digital",
            description="Digital printing for complex designs",
            premium_only=False
        ),
        MockupTechniqueInfo(
            name="TRANSFER_DIGITAL",
            display_name="Transfer Digital",
            description="Heat transfer for smooth application",
            premium_only=False
        ),
        MockupTechniqueInfo(
            name="VINILO_TEXTIL",
            display_name="Vinilo Textil",
            description="Textile vinyl cutting for clean designs",
            premium_only=False
        ),
        MockupTechniqueInfo(
            name="DOMING",
            display_name="Doming",
            description="3D dome effect for premium look",
            premium_only=True
        ),
        MockupTechniqueInfo(
            name="TAMPOGRAFIA",
            display_name="Tampografía",
            description="Pad printing for irregular surfaces",
            premium_only=True
        ),
        MockupTechniqueInfo(
            name="SUBLIMACION",
            display_name="Sublimación",
            description="Sublimation printing for permanent results",
            premium_only=False
        ),
        MockupTechniqueInfo(
            name="TERMOGRABADO",
            display_name="Termograbado",
            description="Heat embossing for raised effect",
            premium_only=True
        ),
    ]
    return techniques


@router.post("/mockups/upload", response_model=dict)
async def upload_mockup_images(
    image: UploadFile = File(...),
    type: str = Form(..., regex="^(products|logos)$"),
    current_user: User = Depends(get_current_user)
):
    """Upload product and logo images for mockup generation"""
    # Validate images
    logging.info(f"Uploading images for user {current_user.id}")
    validate_image(image)
    
    storage = StorageService()
    
    # Generate unique filenames
    #{uuid.uuid4()}
    folder = os.path.dirname(f"{type}/{current_user.id}")
    if folder:
        os.makedirs(folder, exist_ok=True)
    
    filename = f"{folder}/{uuid.uuid4()}_{image.filename}"
    
    # product_filename = f"products/{logo_image.filename}"
    # logo_filename = f"logos/{logo_image.filename}"
    
    try:
        # Upload images to S3
        url = await storage.upload_file(image, filename)
        return {
            "image_url": url,
            "type": type
        }
    except Exception as e:
        raise FileUploadError(f"Failed to upload images: {str(e)}")

@router.post("/mockups", response_model=MockupResponse)
async def create_mockup(
    request: MockupCreateRequest,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """Create a new mockup generation request"""
    name = request.name
    technique = request.technique
    # Check if user has available credits
    available_credits = await db.credit.find_many(
        where={"user_id": current_user.id}
    )
    
    total_available = sum(c.amount - c.used for c in available_credits)
    logging.info(f"total_available:{total_available}")
    if total_available < 1:
        raise InsufficientCreditsError("Insufficient credits to generate mockup")
    
    # Create mockup record
    mockup = await db.mockup.create(
        data={
            "user_id": current_user.id,
            "product_id": None,
            "name": name,
            "marking_technique": technique,
            "product_image_url":'/uploads/products/test.png',
            "logo_image_url": '/uploads/logos/test.png',
            "marking_zone_x": 0,
            "marking_zone_y": 0,
            "marking_zone_w": 1,
            "marking_zone_h": 1,
            "logo_scale": 0,
            "logo_rotation": 0,
            "logo_color": 'transparent',
            "status": MockupStatus.PENDING
        }
    )
    
    # Deduct credit
    credit_to_use = next(c for c in available_credits if c.amount > c.used)
    await db.credit.update(
        where={"id": credit_to_use.id},
        data={"used": credit_to_use.used + 1}
    )
    
    # Update mockup with credit reference
    await db.mockup.update(
        where={"id": mockup.id},
        data={"credit_id": credit_to_use.id}
    )
    
    # Queue background task for AI generation
    background_tasks.add_task(generate_mockup_task.delay, mockup.id)
    
    generate_mockup_task(mockup.id)
    
    return MockupResponse.from_orm(mockup)


@router.get("/mockups", response_model=MockupListResponse)
async def list_user_mockups(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[MockupStatus] = Query(None),
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """Get user's mockups"""
    skip = (page - 1) * per_page
    
    where = {"user_id": current_user.id}
    if status:
        where["status"] = status
    
    mockups = await db.mockup.find_many(
        where=where,
        skip=skip,
        take=per_page,
        order={"created_at": "desc"}
    )
    
    total = await db.mockup.count(where=where)
    total_pages = (total + per_page - 1) // per_page
    
    return MockupListResponse(
        mockups=[MockupResponse.from_orm(m) for m in mockups],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.get("/mockups/{mockup_id}", response_model=MockupResponse)
async def get_mockup(
    mockup_id: str,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """Get specific mockup"""
    mockup = await db.mockup.find_unique(
        where={"id": mockup_id}
    )
    
    if not mockup:
        raise NotFoundError("Mockup not found")
    
    if mockup.user_id != current_user.id:
        raise NotFoundError("Mockup not found")
    
    return MockupResponse.from_orm(mockup)


@router.get("/mockups/{mockup_id}/status", response_model=MockupGenerationStatus)
async def get_mockup_status(
    mockup_id: str,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """Get mockup generation status"""
    mockup = await db.mockup.find_unique(
        where={"id": mockup_id}
    )
    
    if not mockup or mockup.user_id != current_user.id:
        raise NotFoundError("Mockup not found")
    
    # Calculate progress based on status
    progress = None
    if mockup.status == MockupStatus.PENDING:
        progress = 10
    elif mockup.status == MockupStatus.PROCESSING:
        progress = 50
    elif mockup.status == MockupStatus.COMPLETED:
        progress = 100
    elif mockup.status == MockupStatus.FAILED:
        progress = 0
    
    return MockupGenerationStatus(
        mockup_id=mockup.id,
        status=mockup.status,
        progress=progress,
        error_message=mockup.error_message
    )


@router.put("/mockups/{mockup_id}", response_model=MockupResponse)
async def update_mockup(
    mockup_id: str,
    mockup_update: MockupUpdate,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """Update mockup parameters"""
    mockup = await db.mockup.find_unique(
        where={"id": mockup_id}
    )
    
    if not mockup or mockup.user_id != current_user.id:
        raise NotFoundError("Mockup not found")
    
    # Only allow updates if mockup is not processing
    if mockup.status == MockupStatus.PROCESSING:
        raise ValidationError("Cannot update mockup while processing")
    
    update_data = mockup_update.dict(exclude_unset=True)
    if not update_data:
        return MockupResponse.from_orm(mockup)
    
    updated_mockup = await db.mockup.update(
        where={"id": mockup_id},
        data=update_data
    )
    
    return MockupResponse.from_orm(updated_mockup)


@router.post("/mockups/{mockup_id}/regenerate", response_model=MockupResponse)
async def regenerate_mockup(
    mockup_id: str,
    # background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """Regenerate mockup with same parameters"""
    mockup = await db.mockup.find_unique(
        where={"id": mockup_id}
    )
    
    if not mockup or mockup.user_id != current_user.id:
        raise NotFoundError("Mockup not found")
    
    # Check credits
    available_credits = await db.credit.find_many(
        where={"user_id": current_user.id}
    )
    total_available = sum(c.amount - c.used for c in available_credits)
    if total_available < 1:
        raise InsufficientCreditsError("Insufficient credits to regenerate mockup")
    
    # Deduct credit
    credit_to_use = next(c for c in available_credits if c.amount > c.used)
    await db.credit.update(
        where={"id": credit_to_use.id},
        data={"used": credit_to_use.used + 1}
    )
    
    # Reset mockup status
    updated_mockup = await db.mockup.update(
        where={"id": mockup_id},
        data={
            "status": MockupStatus.PENDING,
            "result_image_url": None,
            "error_message": None,
            "processing_time": None
        }
    )
    
    # Queue background task
    logging.info(f"=================Regenerating mockup {mockup_id} for user {current_user.id}")
    # background_tasks.add_task(generate_mockup_task.delay, mockup_id)
    await generate_mockup_task(mockup_id=mockup_id)
    
    return MockupResponse.from_orm(updated_mockup)


@router.delete("/mockups/{mockup_id}")
async def delete_mockup(
    mockup_id: str,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """Delete a mockup"""
    mockup = await db.mockup.find_unique(
        where={"id": mockup_id}
    )
    
    if not mockup or mockup.user_id != current_user.id:
        raise NotFoundError("Mockup not found")
    
    await db.mockup.delete(where={"id": mockup_id})
    
    return {"message": "Mockup deleted successfully"}


@router.get("/mockups/stats", response_model=MockupStats)
async def get_mockup_stats(
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """Get user's mockup statistics"""
    total_mockups = await db.mockup.count(
        where={"user_id": current_user.id}
    )
    
    completed_mockups = await db.mockup.count(
        where={
            "user_id": current_user.id,
            "status": MockupStatus.COMPLETED
        }
    )
    
    failed_mockups = await db.mockup.count(
        where={
            "user_id": current_user.id,
            "status": MockupStatus.FAILED
        }
    )
    
    processing_mockups = await db.mockup.count(
        where={
            "user_id": current_user.id,
            "status": MockupStatus.PROCESSING
        }
    )
    
    # Calculate total processing time
    completed = await db.mockup.find_many(
        where={
            "user_id": current_user.id,
            "status": MockupStatus.COMPLETED,
            "processing_time": {"not": None}
        }
    )
    
    total_processing_time = sum(m.processing_time for m in completed if m.processing_time)
    average_processing_time = total_processing_time / len(completed) if completed else None
    
    return MockupStats(
        total_mockups=total_mockups,
        completed_mockups=completed_mockups,
        failed_mockups=failed_mockups,
        processing_mockups=processing_mockups,
        total_processing_time=total_processing_time,
        average_processing_time=average_processing_time
    )