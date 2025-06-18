import pytest
from fastapi.testclient import TestClient
from app.core.auth import verify_password, get_password_hash


class TestUserRegistration:
    """Test user registration functionality."""
    
    def test_register_new_user(self, client: TestClient, sample_user_data: dict):
        """Test successful user registration."""
        response = client.post("/api/v1/auth/register", json=sample_user_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["message"] == "User registered successfully"
        assert data["user"]["email"] == sample_user_data["email"]
        assert data["user"]["first_name"] == sample_user_data["first_name"]
        assert data["user"]["last_name"] == sample_user_data["last_name"]
        assert data["user"]["role"] == "REGISTERED"
    
    def test_register_duplicate_email(self, client: TestClient, test_user: dict, sample_user_data: dict):
        """Test registration with existing email."""
        sample_user_data["email"] = test_user["email"]
        
        response = client.post("/api/v1/auth/register", json=sample_user_data)
        
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]
    
    def test_register_invalid_email(self, client: TestClient, sample_user_data: dict):
        """Test registration with invalid email."""
        sample_user_data["email"] = "invalid-email"
        
        response = client.post("/api/v1/auth/register", json=sample_user_data)
        
        assert response.status_code == 422
    
    def test_register_weak_password(self, client: TestClient, sample_user_data: dict):
        """Test registration with weak password."""
        sample_user_data["password"] = "123"
        
        response = client.post("/api/v1/auth/register", json=sample_user_data)
        
        assert response.status_code == 422
    
    def test_register_missing_required_fields(self, client: TestClient):
        """Test registration with missing required fields."""
        response = client.post("/api/v1/auth/register", json={})
        
        assert response.status_code == 422


class TestUserLogin:
    """Test user login functionality."""
    
    def test_login_valid_credentials(self, client: TestClient, test_user: dict):
        """Test login with valid credentials."""
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"]
        }
        
        response = client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == test_user["email"]
    
    def test_login_invalid_email(self, client: TestClient):
        """Test login with invalid email."""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "somepassword"
        }
        
        response = client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]
    
    def test_login_invalid_password(self, client: TestClient, test_user: dict):
        """Test login with invalid password."""
        login_data = {
            "email": test_user["email"],
            "password": "wrongpassword"
        }
        
        response = client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]
    
    def test_login_inactive_user(self, client: TestClient, db, test_user: dict):
        """Test login with inactive user account."""
        # Deactivate user
        import asyncio
        asyncio.run(db.user.update(
            where={"id": test_user["id"]},
            data={"is_active": False}
        ))
        
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"]
        }
        
        response = client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert "deactivated" in response.json()["detail"]


class TestTokenRefresh:
    """Test token refresh functionality."""
    
    def test_refresh_valid_token(self, client: TestClient, test_user: dict):
        """Test token refresh with valid refresh token."""
        # First login to get tokens
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"]
        }
        
        login_response = client.post("/api/v1/auth/login", json=login_data)
        tokens = login_response.json()
        
        # Refresh token
        refresh_data = {
            "refresh_token": tokens["refresh_token"]
        }
        
        response = client.post("/api/v1/auth/refresh", json=refresh_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    def test_refresh_invalid_token(self, client: TestClient):
        """Test token refresh with invalid refresh token."""
        refresh_data = {
            "refresh_token": "invalid_token"
        }
        
        response = client.post("/api/v1/auth/refresh", json=refresh_data)
        
        assert response.status_code == 401
        assert "Invalid or expired" in response.json()["detail"]
    
    def test_refresh_access_token_as_refresh(self, client: TestClient, test_user: dict):
        """Test using access token as refresh token."""
        # First login to get tokens
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"]
        }
        
        login_response = client.post("/api/v1/auth/login", json=login_data)
        tokens = login_response.json()
        
        # Try to use access token as refresh token
        refresh_data = {
            "refresh_token": tokens["access_token"]
        }
        
        response = client.post("/api/v1/auth/refresh", json=refresh_data)
        
        assert response.status_code == 401


class TestProtectedEndpoints:
    """Test protected endpoint access."""
    
    def test_access_protected_endpoint_with_token(self, client: TestClient, auth_headers: dict):
        """Test accessing protected endpoint with valid token."""
        response = client.get("/api/v1/auth/me", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert "email" in data
        assert "role" in data
    
    def test_access_protected_endpoint_without_token(self, client: TestClient):
        """Test accessing protected endpoint without token."""
        response = client.get("/api/v1/auth/me")
        
        assert response.status_code == 403
    
    def test_access_protected_endpoint_with_invalid_token(self, client: TestClient):
        """Test accessing protected endpoint with invalid token."""
        headers = {"Authorization": "Bearer invalid_token"}
        
        response = client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 401


class TestPasswordReset:
    """Test password reset functionality."""
    
    def test_forgot_password_existing_email(self, client: TestClient, test_user: dict):
        """Test forgot password with existing email."""
        forgot_data = {
            "email": test_user["email"]
        }
        
        response = client.post("/api/v1/auth/forgot-password", json=forgot_data)
        
        assert response.status_code == 200
        assert "reset link" in response.json()["message"]
    
    def test_forgot_password_nonexistent_email(self, client: TestClient):
        """Test forgot password with nonexistent email."""
        forgot_data = {
            "email": "nonexistent@example.com"
        }
        
        response = client.post("/api/v1/auth/forgot-password", json=forgot_data)
        
        # Should return success for security reasons
        assert response.status_code == 200
        assert "reset link" in response.json()["message"]


class TestLogout:
    """Test logout functionality."""
    
    def test_logout(self, client: TestClient, auth_headers: dict):
        """Test user logout."""
        response = client.post("/api/v1/auth/logout", headers=auth_headers)
        
        assert response.status_code == 200
        assert "Logged out successfully" in response.json()["message"]


class TestAuthenticationHelpers:
    """Test authentication helper functions."""
    
    def test_password_hashing(self):
        """Test password hashing and verification."""
        password = "test_password_123"
        
        # Hash password
        hashed = get_password_hash(password)
        
        # Verify correct password
        assert verify_password(password, hashed) is True
        
        # Verify incorrect password
        assert verify_password("wrong_password", hashed) is False
    
    def test_password_hash_uniqueness(self):
        """Test that same password generates different hashes."""
        password = "test_password_123"
        
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        # Hashes should be different due to salt
        assert hash1 != hash2
        
        # But both should verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True