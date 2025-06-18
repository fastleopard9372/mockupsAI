import pytest
import asyncio
from typing import Generator, AsyncGenerator
from fastapi.testclient import TestClient
from prisma import Prisma
from app.main import app
from app.config.database import get_db
from app.config.settings import settings
from app.core.auth import create_token_pair, get_password_hash
import os


# Test database URL
TEST_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://test:test@localhost:5432/test_ai_mockup")


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_db() -> AsyncGenerator[Prisma, None]:
    """Create test database connection."""
    # Override DATABASE_URL for tests
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    
    db = Prisma()
    await db.connect()
    
    # Reset database for clean tests
    await db.execute_raw("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    
    # Run migrations
    os.system("prisma db push --force-reset")
    
    yield db
    
    await db.disconnect()


@pytest.fixture
async def db(test_db: Prisma) -> AsyncGenerator[Prisma, None]:
    """Get database instance and clean up after each test."""
    # Clean up data after each test
    async with test_db.tx() as transaction:
        yield transaction
        # Transaction will be rolled back automatically


@pytest.fixture
def client(db: Prisma) -> Generator[TestClient, None, None]:
    """Create test client with database override."""
    
    async def override_get_db():
        return db
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db: Prisma) -> dict:
    """Create a test user."""
    user_data = {
        "email": "test@example.com",
        "password_hash": get_password_hash("testpassword123"),
        "first_name": "Test",
        "last_name": "User",
        "role": "REGISTERED",
        "is_active": True
    }
    
    user = await db.user.create(data=user_data)
    
    # Add some test credits
    await db.credit.create(
        data={
            "user_id": user.id,
            "amount": 10,
            "used": 0
        }
    )
    
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
        "password": "testpassword123"
    }


@pytest.fixture
async def admin_user(db: Prisma) -> dict:
    """Create a test admin user."""
    user_data = {
        "email": "admin@example.com",
        "password_hash": get_password_hash("adminpassword123"),
        "first_name": "Admin",
        "last_name": "User",
        "role": "ADMIN",
        "is_active": True
    }
    
    user = await db.user.create(data=user_data)
    
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
        "password": "adminpassword123"
    }


@pytest.fixture
def auth_headers(test_user: dict) -> dict:
    """Create authentication headers for test user."""
    tokens = create_token_pair(test_user["id"], test_user["email"])
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
def admin_headers(admin_user: dict) -> dict:
    """Create authentication headers for admin user."""
    tokens = create_token_pair(admin_user["id"], admin_user["email"])
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
async def test_product(db: Prisma) -> dict:
    """Create a test product."""
    product_data = {
        "name": "Test T-Shirt",
        "description": "A test t-shirt for mockup generation",
        "category": "Apparel",
        "image_url": "https://example.com/test-tshirt.jpg",
        "is_active": True
    }
    
    product = await db.product.create(data=product_data)
    
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "category": product.category,
        "image_url": product.image_url
    }


@pytest.fixture
async def test_mockup(db: Prisma, test_user: dict, test_product: dict) -> dict:
    """Create a test mockup."""
    # First create a credit for the user
    credit = await db.credit.create(
        data={
            "user_id": test_user["id"],
            "amount": 5,
            "used": 0
        }
    )
    
    mockup_data = {
        "user_id": test_user["id"],
        "product_id": test_product["id"],
        "credit_id": credit.id,
        "name": "Test Mockup",
        "marking_technique": "SERIGRAFIA",
        "product_image_url": "https://example.com/product.jpg",
        "logo_image_url": "https://example.com/logo.jpg",
        "marking_zone_x": 0.3,
        "marking_zone_y": 0.4,
        "marking_zone_w": 0.2,
        "marking_zone_h": 0.2,
        "logo_scale": 1.0,
        "logo_rotation": 0.0,
        "status": "PENDING"
    }
    
    mockup = await db.mockup.create(data=mockup_data)
    
    return {
        "id": mockup.id,
        "user_id": mockup.user_id,
        "product_id": mockup.product_id,
        "name": mockup.name,
        "status": mockup.status
    }


@pytest.fixture
def mock_stripe():
    """Mock Stripe API for payment tests."""
    import stripe
    from unittest.mock import Mock
    
    # Mock Stripe customer
    mock_customer = Mock()
    mock_customer.id = "cus_test123"
    mock_customer.email = "test@example.com"
    
    # Mock Stripe payment intent
    mock_payment_intent = Mock()
    mock_payment_intent.id = "pi_test123"
    mock_payment_intent.client_secret = "pi_test123_secret"
    mock_payment_intent.status = "requires_payment_method"
    
    # Mock Stripe subscription
    mock_subscription = Mock()
    mock_subscription.id = "sub_test123"
    mock_subscription.status = "active"
    mock_subscription.current_period_start = 1640995200  # 2022-01-01
    mock_subscription.current_period_end = 1643673600    # 2022-02-01
    
    stripe.Customer.create = Mock(return_value=mock_customer)
    stripe.Customer.list = Mock(return_value=Mock(data=[]))
    stripe.PaymentIntent.create = Mock(return_value=mock_payment_intent)
    stripe.Subscription.create = Mock(return_value=mock_subscription)
    
    return {
        "customer": mock_customer,
        "payment_intent": mock_payment_intent,
        "subscription": mock_subscription
    }


@pytest.fixture
def mock_s3():
    """Mock AWS S3 for file upload tests."""
    from unittest.mock import Mock
    import boto3
    
    mock_s3_client = Mock()
    mock_s3_client.upload_fileobj = Mock()
    mock_s3_client.put_object = Mock()
    mock_s3_client.delete_object = Mock()
    mock_s3_client.head_object = Mock()
    
    boto3.client = Mock(return_value=mock_s3_client)
    
    return mock_s3_client


@pytest.fixture
def mock_email():
    """Mock email service for testing."""
    from unittest.mock import Mock, patch
    
    with patch('app.services.email_service.EmailService') as mock_email_service:
        mock_instance = Mock()
        mock_instance.send_email = Mock(return_value=True)
        mock_instance.send_templated_email = Mock(return_value=True)
        mock_email_service.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_ai_service():
    """Mock AI service for testing."""
    from unittest.mock import Mock, patch
    
    with patch('app.services.ai_service.ai_service') as mock_ai:
        mock_ai.generate_mockup = Mock(return_value="https://example.com/result.jpg")
        mock_ai.initialize_models = Mock()
        mock_ai.estimate_processing_time = Mock(return_value=30)
        yield mock_ai


# Test data fixtures
@pytest.fixture
def sample_user_data():
    """Sample user registration data."""
    return {
        "email": "newuser@example.com",
        "password": "newpassword123",
        "first_name": "New",
        "last_name": "User"
    }


@pytest.fixture
def sample_mockup_data():
    """Sample mockup creation data."""
    return {
        "name": "Test Mockup",
        "marking_technique": "SERIGRAFIA",
        "marking_zone_x": 0.3,
        "marking_zone_y": 0.4,
        "marking_zone_w": 0.2,
        "marking_zone_h": 0.2,
        "logo_scale": 1.0,
        "logo_rotation": 0.0
    }


@pytest.fixture
def sample_product_data():
    """Sample product creation data."""
    return {
        "name": "New Product",
        "description": "A new product for testing",
        "category": "Electronics",
        "image_url": "https://example.com/newproduct.jpg"
    }


# Utility fixtures
@pytest.fixture
def temp_image_file():
    """Create a temporary image file for upload tests."""
    import tempfile
    from PIL import Image
    import io
    
    # Create a simple test image
    img = Image.new('RGB', (100, 100), color='red')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    
    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
    temp_file.write(img_bytes.getvalue())
    temp_file.close()
    
    yield temp_file.name
    
    # Cleanup
    os.unlink(temp_file.name)


# Test settings override
@pytest.fixture(autouse=True)
def test_settings():
    """Override settings for testing."""
    original_debug = settings.DEBUG
    original_environment = settings.ENVIRONMENT
    
    settings.DEBUG = True
    settings.ENVIRONMENT = "testing"
    
    yield
    
    settings.DEBUG = original_debug
    settings.ENVIRONMENT = original_environment