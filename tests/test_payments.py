import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import json


class TestCreditPurchase:
    """Test credit purchase functionality."""
    
    def test_get_credit_packages(self, client: TestClient):
        """Test getting available credit packages."""
        response = client.get("/api/v1/credits/packages")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "packages" in data
        assert len(data["packages"]) > 0
        
        # Check package structure
        package = data["packages"][0]
        assert "amount" in package
        assert "price" in package
        assert "popular" in package
    
    def test_purchase_credits_success(
        self, 
        client: TestClient, 
        auth_headers: dict,
        mock_stripe
    ):
        """Test successful credit purchase."""
        purchase_data = {
            "amount": 10,
            "payment_method_id": "pm_test_123"
        }
        
        response = client.post(
            "/api/v1/credits/purchase",
            json=purchase_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "payment_intent_id" in data
        assert "client_secret" in data
        assert "payment_id" in data
    
    def test_purchase_invalid_credit_amount(
        self, 
        client: TestClient, 
        auth_headers: dict
    ):
        """Test purchasing invalid credit amount."""
        purchase_data = {
            "amount": 15,  # Not in available packages
            "payment_method_id": "pm_test_123"
        }
        
        response = client.post(
            "/api/v1/credits/purchase",
            json=purchase_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422
        assert "Invalid credit package" in response.json()["detail"]
    
    def test_purchase_credits_payment_failure(
        self, 
        client: TestClient, 
        auth_headers: dict
    ):
        """Test credit purchase with payment failure."""
        with patch('stripe.PaymentIntent.create') as mock_create:
            mock_create.side_effect = Exception("Payment failed")
            
            purchase_data = {
                "amount": 10,
                "payment_method_id": "pm_test_123"
            }
            
            response = client.post(
                "/api/v1/credits/purchase",
                json=purchase_data,
                headers=auth_headers
            )
            
            assert response.status_code == 402
            assert "Payment processing failed" in response.json()["detail"]


class TestCreditBalance:
    """Test credit balance functionality."""
    
    def test_get_credit_balance(self, client: TestClient, auth_headers: dict):
        """Test getting user's credit balance."""
        response = client.get("/api/v1/credits/balance", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_credits" in data
        assert "used_credits" in data
        assert "remaining_credits" in data
        assert "expiring_soon" in data
        assert "next_expiry_date" in data
    
    def test_get_user_credits(self, client: TestClient, auth_headers: dict):
        """Test getting user's credit history."""
        response = client.get("/api/v1/credits", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        # Should have at least the free credits from registration
        assert len(data) >= 1
        
        if data:
            credit = data[0]
            assert "id" in credit
            assert "amount" in credit
            assert "used" in credit
            assert "remaining" in credit


class TestCreditHistory:
    """Test credit transaction history."""
    
    def test_get_credit_history(self, client: TestClient, auth_headers: dict):
        """Test getting credit transaction history."""
        response = client.get("/api/v1/credits/history", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "transactions" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "total_pages" in data
    
    def test_credit_history_pagination(self, client: TestClient, auth_headers: dict):
        """Test credit history pagination."""
        response = client.get(
            "/api/v1/credits/history?page=1&per_page=5", 
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["page"] == 1
        assert data["per_page"] == 5
        assert len(data["transactions"]) <= 5


class TestPaymentMethods:
    """Test payment method management."""
    
    def test_create_setup_intent(
        self, 
        client: TestClient, 
        auth_headers: dict,
        mock_stripe
    ):
        """Test creating setup intent for saving payment methods."""
        response = client.get(
            "/api/v1/payments/setup-intent",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "client_secret" in data
    
    def test_get_payment_methods(
        self, 
        client: TestClient, 
        auth_headers: dict,
        mock_stripe
    ):
        """Test getting user's saved payment methods."""
        response = client.get(
            "/api/v1/payments/methods",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "payment_methods" in data
        assert isinstance(data["payment_methods"], list)
    
    def test_delete_payment_method(
        self, 
        client: TestClient, 
        auth_headers: dict,
        mock_stripe
    ):
        """Test deleting a saved payment method."""
        response = client.delete(
            "/api/v1/payments/methods/pm_test_123",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert "deleted successfully" in response.json()["message"]


class TestPaymentHistory:
    """Test payment history functionality."""
    
    def test_get_payment_history(self, client: TestClient, auth_headers: dict):
        """Test getting user's payment history."""
        response = client.get(
            "/api/v1/payments/history",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "payments" in data
        assert isinstance(data["payments"], list)


class TestWebhooks:
    """Test Stripe webhook handling."""
    
    def test_stripe_webhook_payment_success(self, client: TestClient, db):
        """Test handling successful payment webhook."""
        # Create a test payment record first
        import asyncio
        payment = asyncio.run(db.payment.create(
            data={
                "user_id": "test_user_id",
                "amount": 9.99,
                "currency": "EUR",
                "status": "PENDING",
                "stripe_payment_intent_id": "pi_test_123",
                "payment_method": "stripe"
            }
        ))
        
        webhook_payload = {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_test_123",
                    "metadata": {
                        "type": "credit_purchase",
                        "user_id": "test_user_id",
                        "credit_amount": "10"
                    }
                }
            }
        }
        
        # Mock Stripe signature verification
        with patch('stripe.Webhook.construct_event') as mock_construct:
            mock_construct.return_value = webhook_payload
            
            response = client.post(
                "/api/v1/payments/webhook",
                json=webhook_payload,
                headers={"stripe-signature": "test_signature"}
            )
            
            assert response.status_code == 200
            assert response.json()["status"] == "success"
    
    def test_stripe_webhook_invalid_signature(self, client: TestClient):
        """Test webhook with invalid signature."""
        webhook_payload = {
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_test_123"}}
        }
        
        with patch('stripe.Webhook.construct_event') as mock_construct:
            mock_construct.side_effect = stripe.error.SignatureVerificationError(
                "Invalid signature", "sig_header"
            )
            
            response = client.post(
                "/api/v1/payments/webhook",
                json=webhook_payload,
                headers={"stripe-signature": "invalid_signature"}
            )
            
            assert response.status_code == 400
            assert "Invalid signature" in response.json()["detail"]
    
    def test_stripe_webhook_payment_failure(self, client: TestClient, db):
        """Test handling failed payment webhook."""
        # Create a test payment record
        import asyncio
        payment = asyncio.run(db.payment.create(
            data={
                "user_id": "test_user_id",
                "amount": 9.99,
                "currency": "EUR",
                "status": "PENDING",
                "stripe_payment_intent_id": "pi_test_456",
                "payment_method": "stripe"
            }
        ))
        
        webhook_payload = {
            "type": "payment_intent.payment_failed",
            "data": {
                "object": {
                    "id": "pi_test_456"
                }
            }
        }
        
        with patch('stripe.Webhook.construct_event') as mock_construct:
            mock_construct.return_value = webhook_payload
            
            response = client.post(
                "/api/v1/payments/webhook",
                json=webhook_payload,
                headers={"stripe-signature": "test_signature"}
            )
            
            assert response.status_code == 200


class TestSubscriptionPayments:
    """Test subscription-related payment functionality."""
    
    def test_subscription_payment_webhook(self, client: TestClient, db):
        """Test handling subscription payment webhook."""
        # Create test user and subscription
        import asyncio
        from datetime import datetime, timedelta
        
        user = asyncio.run(db.user.create(
            data={
                "email": "sub_user@example.com",
                "password_hash": "hashed_password",
                "first_name": "Sub",
                "last_name": "User"
            }
        ))
        
        subscription = asyncio.run(db.subscription.create(
            data={
                "user_id": user.id,
                "plan": "PRO",
                "status": "ACTIVE",
                "stripe_id": "sub_test_123",
                "current_period_start": datetime.utcnow(),
                "current_period_end": datetime.utcnow() + timedelta(days=30)
            }
        ))
        
        webhook_payload = {
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "subscription": "sub_test_123"
                }
            }
        }
        
        with patch('stripe.Webhook.construct_event') as mock_construct:
            mock_construct.return_value = webhook_payload
            
            response = client.post(
                "/api/v1/payments/webhook",
                json=webhook_payload,
                headers={"stripe-signature": "test_signature"}
            )
            
            assert response.status_code == 200


class TestPaymentErrors:
    """Test payment error handling."""
    
    def test_payment_service_unavailable(
        self, 
        client: TestClient, 
        auth_headers: dict
    ):
        """Test payment when Stripe service is unavailable."""
        with patch('stripe.PaymentIntent.create') as mock_create:
            mock_create.side_effect = stripe.error.APIConnectionError(
                "Network error"
            )
            
            purchase_data = {
                "amount": 10,
                "payment_method_id": "pm_test_123"
            }
            
            response = client.post(
                "/api/v1/credits/purchase",
                json=purchase_data,
                headers=auth_headers
            )
            
            assert response.status_code == 402
    
    def test_payment_method_declined(
        self, 
        client: TestClient, 
        auth_headers: dict
    ):
        """Test payment with declined payment method."""
        with patch('stripe.PaymentIntent.create') as mock_create:
            mock_create.side_effect = stripe.error.CardError(
                "Your card was declined",
                "card_declined",
                "card_declined"
            )
            
            purchase_data = {
                "amount": 10,
                "payment_method_id": "pm_test_declined"
            }
            
            response = client.post(
                "/api/v1/credits/purchase",
                json=purchase_data,
                headers=auth_headers
            )
            
            assert response.status_code == 402


class TestPaymentUnauthorized:
    """Test unauthorized access to payment endpoints."""
    
    def test_purchase_credits_without_auth(self, client: TestClient):
        """Test purchasing credits without authentication."""
        purchase_data = {
            "amount": 10,
            "payment_method_id": "pm_test_123"
        }
        
        response = client.post("/api/v1/credits/purchase", json=purchase_data)
        
        assert response.status_code == 403
    
    def test_get_payment_methods_without_auth(self, client: TestClient):
        """Test getting payment methods without authentication."""
        response = client.get("/api/v1/payments/methods")
        
        assert response.status_code == 403
    
    def test_get_payment_history_without_auth(self, client: TestClient):
        """Test getting payment history without authentication."""
        response = client.get("/api/v1/payments/history")
        
        assert response.status_code == 403