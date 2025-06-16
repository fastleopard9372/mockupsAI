import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock
import io


class TestMockupGeneration:
    """Test mockup generation functionality."""
    
    def test_create_mockup_success(
        self, 
        client: TestClient, 
        auth_headers: dict, 
        sample_mockup_data: dict,
        mock_ai_service
    ):
        """Test successful mockup creation."""
        # Mock form data for file uploads
        form_data = {
            **sample_mockup_data,
            "product_image_url": "https://example.com/product.jpg",
            "logo_image_url": "https://example.com/logo.jpg"
        }
        
        response = client.post(
            "/api/v1/mockups", 
            data=form_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == sample_mockup_data["name"]
        assert data["marking_technique"] == sample_mockup_data["marking_technique"]
        assert data["status"] == "PENDING"
        assert "id" in data
    
    def test_create_mockup_insufficient_credits(
        self, 
        client: TestClient, 
        auth_headers: dict, 
        sample_mockup_data: dict,
        db
    ):
        """Test mockup creation with insufficient credits."""
        # Remove all credits from user
        import asyncio
        asyncio.run(db.credit.delete_many(where={}))
        
        form_data = {
            **sample_mockup_data,
            "product_image_url": "https://example.com/product.jpg",
            "logo_image_url": "https://example.com/logo.jpg"
        }
        
        response = client.post(
            "/api/v1/mockups", 
            data=form_data,
            headers=auth_headers
        )
        
        assert response.status_code == 402
        assert "Insufficient credits" in response.json()["detail"]
    
    def test_create_mockup_invalid_technique(
        self, 
        client: TestClient, 
        auth_headers: dict, 
        sample_mockup_data: dict
    ):
        """Test mockup creation with invalid marking technique."""
        sample_mockup_data["marking_technique"] = "INVALID_TECHNIQUE"
        
        form_data = {
            **sample_mockup_data,
            "product_image_url": "https://example.com/product.jpg",
            "logo_image_url": "https://example.com/logo.jpg"
        }
        
        response = client.post(
            "/api/v1/mockups", 
            data=form_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422
    
    def test_create_mockup_invalid_coordinates(
        self, 
        client: TestClient, 
        auth_headers: dict, 
        sample_mockup_data: dict
    ):
        """Test mockup creation with invalid zone coordinates."""
        sample_mockup_data["marking_zone_x"] = 1.5  # Invalid > 1.0
        
        form_data = {
            **sample_mockup_data,
            "product_image_url": "https://example.com/product.jpg",
            "logo_image_url": "https://example.com/logo.jpg"
        }
        
        response = client.post(
            "/api/v1/mockups", 
            data=form_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422


class TestMockupRetrieval:
    """Test mockup retrieval functionality."""
    
    def test_get_user_mockups(self, client: TestClient, auth_headers: dict, test_mockup: dict):
        """Test getting user's mockups."""
        response = client.get("/api/v1/mockups", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "mockups" in data
        assert "total" in data
        assert "page" in data
        assert len(data["mockups"]) >= 1
    
    def test_get_user_mockups_with_filters(
        self, 
        client: TestClient, 
        auth_headers: dict, 
        test_mockup: dict
    ):
        """Test getting user's mockups with status filter."""
        response = client.get(
            "/api/v1/mockups?status=PENDING", 
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        for mockup in data["mockups"]:
            assert mockup["status"] == "PENDING"
    
    def test_get_mockup_by_id(self, client: TestClient, auth_headers: dict, test_mockup: dict):
        """Test getting specific mockup by ID."""
        response = client.get(
            f"/api/v1/mockups/{test_mockup['id']}", 
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == test_mockup["id"]
        assert data["name"] == test_mockup["name"]
    
    def test_get_mockup_not_found(self, client: TestClient, auth_headers: dict):
        """Test getting nonexistent mockup."""
        response = client.get(
            "/api/v1/mockups/nonexistent_id", 
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    def test_get_other_user_mockup(
        self, 
        client: TestClient, 
        auth_headers: dict, 
        test_mockup: dict,
        db
    ):
        """Test accessing another user's mockup."""
        # Create another user's mockup
        import asyncio
        other_user = asyncio.run(db.user.create(
            data={
                "email": "other@example.com",
                "password_hash": "hashed_password",
                "first_name": "Other",
                "last_name": "User"
            }
        ))
        
        other_mockup = asyncio.run(db.mockup.create(
            data={
                "user_id": other_user.id,
                "name": "Other's Mockup",
                "marking_technique": "SERIGRAFIA",
                "product_image_url": "https://example.com/product.jpg",
                "logo_image_url": "https://example.com/logo.jpg",
                "marking_zone_x": 0.3,
                "marking_zone_y": 0.4,
                "marking_zone_w": 0.2,
                "marking_zone_h": 0.2,
                "status": "PENDING"
            }
        ))
        
        response = client.get(
            f"/api/v1/mockups/{other_mockup.id}", 
            headers=auth_headers
        )
        
        assert response.status_code == 404


class TestMockupStatus:
    """Test mockup status functionality."""
    
    def test_get_mockup_status(self, client: TestClient, auth_headers: dict, test_mockup: dict):
        """Test getting mockup generation status."""
        response = client.get(
            f"/api/v1/mockups/{test_mockup['id']}/status", 
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["mockup_id"] == test_mockup["id"]
        assert data["status"] == test_mockup["status"]
        assert "progress" in data


class TestMockupUpdate:
    """Test mockup update functionality."""
    
    def test_update_mockup_success(
        self, 
        client: TestClient, 
        auth_headers: dict, 
        test_mockup: dict
    ):
        """Test successful mockup update."""
        update_data = {
            "name": "Updated Mockup Name",
            "logo_scale": 1.5
        }
        
        response = client.put(
            f"/api/v1/mockups/{test_mockup['id']}", 
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == update_data["name"]
        assert data["logo_scale"] == update_data["logo_scale"]
    
    def test_update_processing_mockup(
        self, 
        client: TestClient, 
        auth_headers: dict, 
        test_mockup: dict,
        db
    ):
        """Test updating mockup that is currently processing."""
        # Set mockup status to processing
        import asyncio
        asyncio.run(db.mockup.update(
            where={"id": test_mockup["id"]},
            data={"status": "PROCESSING"}
        ))
        
        update_data = {"name": "Updated Name"}
        
        response = client.put(
            f"/api/v1/mockups/{test_mockup['id']}", 
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422
        assert "Cannot update mockup while processing" in response.json()["detail"]


class TestMockupRegeneration:
    """Test mockup regeneration functionality."""
    
    def test_regenerate_mockup_success(
        self, 
        client: TestClient, 
        auth_headers: dict, 
        test_mockup: dict,
        mock_ai_service
    ):
        """Test successful mockup regeneration."""
        response = client.post(
            f"/api/v1/mockups/{test_mockup['id']}/regenerate", 
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "PENDING"
    
    def test_regenerate_mockup_insufficient_credits(
        self, 
        client: TestClient, 
        auth_headers: dict, 
        test_mockup: dict,
        db
    ):
        """Test regenerating mockup with insufficient credits."""
        # Use up all credits
        import asyncio
        credits = asyncio.run(db.credit.find_many())
        for credit in credits:
            asyncio.run(db.credit.update(
                where={"id": credit.id},
                data={"used": credit.amount}
            ))
        
        response = client.post(
            f"/api/v1/mockups/{test_mockup['id']}/regenerate", 
            headers=auth_headers
        )
        
        assert response.status_code == 402
        assert "Insufficient credits" in response.json()["detail"]


class TestMockupDeletion:
    """Test mockup deletion functionality."""
    
    def test_delete_mockup_success(
        self, 
        client: TestClient, 
        auth_headers: dict, 
        test_mockup: dict
    ):
        """Test successful mockup deletion."""
        response = client.delete(
            f"/api/v1/mockups/{test_mockup['id']}", 
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert "deleted successfully" in response.json()["message"]
        
        # Verify mockup is deleted
        get_response = client.get(
            f"/api/v1/mockups/{test_mockup['id']}", 
            headers=auth_headers
        )
        assert get_response.status_code == 404
    
    def test_delete_nonexistent_mockup(self, client: TestClient, auth_headers: dict):
        """Test deleting nonexistent mockup."""
        response = client.delete(
            "/api/v1/mockups/nonexistent_id", 
            headers=auth_headers
        )
        
        assert response.status_code == 404


class TestMockupTechniques:
    """Test marking techniques functionality."""
    
    def test_get_marking_techniques(self, client: TestClient):
        """Test getting available marking techniques."""
        response = client.get("/api/v1/mockups/techniques")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) > 0
        
        # Check technique structure
        technique = data[0]
        assert "name" in technique
        assert "display_name" in technique
        assert "description" in technique
        assert "premium_only" in technique
    
    def test_technique_includes_serigrafia(self, client: TestClient):
        """Test that SERIGRAFIA technique is included."""
        response = client.get("/api/v1/mockups/techniques")
        techniques = response.json()
        
        technique_names = [t["name"] for t in techniques]
        assert "SERIGRAFIA" in technique_names


class TestMockupStats:
    """Test mockup statistics functionality."""
    
    def test_get_mockup_stats(self, client: TestClient, auth_headers: dict, test_mockup: dict):
        """Test getting user's mockup statistics."""
        response = client.get("/api/v1/mockups/stats", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_mockups" in data
        assert "completed_mockups" in data
        assert "failed_mockups" in data
        assert "processing_mockups" in data
        assert "total_processing_time" in data
        
        assert data["total_mockups"] >= 1  # At least our test mockup


class TestFileUpload:
    """Test file upload functionality."""
    
    def test_upload_mockup_images_success(
        self, 
        client: TestClient, 
        auth_headers: dict, 
        temp_image_file: str,
        mock_s3
    ):
        """Test successful image upload."""
        with open(temp_image_file, 'rb') as f:
            files = {
                'product_image': ('product.jpg', f, 'image/jpeg'),
                'logo_image': ('logo.jpg', f, 'image/jpeg')
            }
            
            response = client.post(
                "/api/v1/mockups/upload",
                files=files,
                headers=auth_headers
            )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "product_image_url" in data
        assert "logo_image_url" in data
    
    def test_upload_invalid_file_type(self, client: TestClient, auth_headers: dict):
        """Test uploading invalid file type."""
        # Create a text file instead of image
        text_content = b"This is not an image"
        
        files = {
            'product_image': ('document.txt', io.BytesIO(text_content), 'text/plain'),
            'logo_image': ('logo.jpg', io.BytesIO(text_content), 'image/jpeg')
        }
        
        response = client.post(
            "/api/v1/mockups/upload",
            files=files,
            headers=auth_headers
        )
        
        assert response.status_code == 400
    
    def test_upload_file_too_large(self, client: TestClient, auth_headers: dict):
        """Test uploading file that's too large."""
        # Create a large file (larger than MAX_FILE_SIZE)
        large_content = b"x" * (11 * 1024 * 1024)  # 11MB
        
        files = {
            'product_image': ('large.jpg', io.BytesIO(large_content), 'image/jpeg'),
            'logo_image': ('logo.jpg', io.BytesIO(b"small"), 'image/jpeg')
        }
        
        response = client.post(
            "/api/v1/mockups/upload",
            files=files,
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "File size too large" in response.json()["detail"]


class TestMockupPagination:
    """Test mockup pagination functionality."""
    
    def test_mockup_pagination(self, client: TestClient, auth_headers: dict, db):
        """Test mockup list pagination."""
        # Create multiple mockups
        import asyncio
        
        # Get user ID from token
        user_response = client.get("/api/v1/auth/me", headers=auth_headers)
        user_id = user_response.json()["id"]
        
        # Create additional test mockups
        for i in range(5):
            asyncio.run(db.mockup.create(
                data={
                    "user_id": user_id,
                    "name": f"Test Mockup {i}",
                    "marking_technique": "SERIGRAFIA",
                    "product_image_url": f"https://example.com/product{i}.jpg",
                    "logo_image_url": f"https://example.com/logo{i}.jpg",
                    "marking_zone_x": 0.3,
                    "marking_zone_y": 0.4,
                    "marking_zone_w": 0.2,
                    "marking_zone_h": 0.2,
                    "status": "PENDING"
                }
            ))
        
        # Test first page
        response = client.get(
            "/api/v1/mockups?page=1&per_page=3", 
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["page"] == 1
        assert data["per_page"] == 3
        assert len(data["mockups"]) <= 3
        assert data["total"] >= 5


class TestMockupValidation:
    """Test mockup validation functionality."""
    
    def test_invalid_marking_zone_coordinates(
        self, 
        client: TestClient, 
        auth_headers: dict, 
        sample_mockup_data: dict
    ):
        """Test mockup creation with invalid zone coordinates."""
        test_cases = [
            {"marking_zone_x": -0.1},  # Negative value
            {"marking_zone_y": 1.1},   # Greater than 1
            {"marking_zone_w": 0},     # Zero width
            {"marking_zone_h": -0.5},  # Negative height
        ]
        
        for invalid_data in test_cases:
            form_data = {
                **sample_mockup_data,
                **invalid_data,
                "product_image_url": "https://example.com/product.jpg",
                "logo_image_url": "https://example.com/logo.jpg"
            }
            
            response = client.post(
                "/api/v1/mockups", 
                data=form_data,
                headers=auth_headers
            )
            
            assert response.status_code == 422
    
    def test_invalid_logo_parameters(
        self, 
        client: TestClient, 
        auth_headers: dict, 
        sample_mockup_data: dict
    ):
        """Test mockup creation with invalid logo parameters."""
        test_cases = [
            {"logo_scale": 0},      # Zero scale
            {"logo_scale": 4.0},    # Scale too large
            {"logo_rotation": 400}, # Rotation out of range
            {"logo_rotation": -400}, # Negative rotation out of range
        ]
        
        for invalid_data in test_cases:
            form_data = {
                **sample_mockup_data,
                **invalid_data,
                "product_image_url": "https://example.com/product.jpg",
                "logo_image_url": "https://example.com/logo.jpg"
            }
            
            response = client.post(
                "/api/v1/mockups", 
                data=form_data,
                headers=auth_headers
            )
            
            assert response.status_code == 422


class TestMockupUnauthorizedAccess:
    """Test unauthorized access to mockup endpoints."""
    
    def test_create_mockup_without_auth(self, client: TestClient, sample_mockup_data: dict):
        """Test creating mockup without authentication."""
        form_data = {
            **sample_mockup_data,
            "product_image_url": "https://example.com/product.jpg",
            "logo_image_url": "https://example.com/logo.jpg"
        }
        
        response = client.post("/api/v1/mockups", data=form_data)
        
        assert response.status_code == 403
    
    def test_get_mockups_without_auth(self, client: TestClient):
        """Test getting mockups without authentication."""
        response = client.get("/api/v1/mockups")
        
        assert response.status_code == 403
    
    def test_upload_images_without_auth(self, client: TestClient):
        """Test uploading images without authentication."""
        files = {
            'product_image': ('product.jpg', io.BytesIO(b"test"), 'image/jpeg'),
            'logo_image': ('logo.jpg', io.BytesIO(b"test"), 'image/jpeg')
        }
        
        response = client.post("/api/v1/mockups/upload", files=files)
        
        assert response.status_code == 403