#!/usr/bin/env python3
"""
Comprehensive Backend Testing for Chat Application
Tests all API endpoints and Socket.io functionality
"""

import requests
import json
import time
import asyncio
import socketio
import os
from datetime import datetime

# Get backend URL from frontend .env file
def get_backend_url():
    try:
        with open('/app/frontend/.env', 'r') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    return line.split('=', 1)[1].strip()
    except:
        pass
    return "http://localhost:8001"

BASE_URL = get_backend_url()
API_URL = f"{BASE_URL}/api"

print(f"Testing backend at: {BASE_URL}")
print(f"API endpoints at: {API_URL}")

class ChatAppTester:
    def __init__(self):
        self.session = requests.Session()
        self.user1_token = None
        self.user2_token = None
        self.user1_id = None
        self.user2_id = None
        # Use timestamp to ensure unique usernames
        timestamp = str(int(time.time()))
        self.user1_username = f"alice_smith_{timestamp}"
        self.user2_username = f"bob_jones_{timestamp}"
        self.conversation_id = None
        self.test_results = []
        
    def log_test(self, test_name, success, message=""):
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
        if message:
            print(f"    {message}")
        self.test_results.append({
            "test": test_name,
            "success": success,
            "message": message
        })
        
    def test_health_check(self):
        """Test health check endpoint"""
        try:
            response = self.session.get(f"{API_URL}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    self.log_test("Health Check", True, "Backend is healthy")
                    return True
                else:
                    self.log_test("Health Check", False, f"Unexpected response: {data}")
                    return False
            else:
                self.log_test("Health Check", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Health Check", False, f"Connection error: {str(e)}")
            return False
    
    def test_user_registration(self):
        """Test user registration endpoint"""
        try:
            # Test user 1 registration
            user1_data = {
                "username": self.user1_username,
                "password": "securepass123"
            }
            
            response = self.session.post(f"{API_URL}/register", json=user1_data, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["access_token", "token_type", "user_id", "username"]
                
                if all(field in data for field in required_fields):
                    self.user1_token = data["access_token"]
                    self.user1_id = data["user_id"]
                    self.log_test("User Registration (User 1)", True, f"User {self.user1_username} registered successfully")
                    
                    # Test user 2 registration
                    user2_data = {
                        "username": self.user2_username,
                        "password": "anotherpass456"
                    }
                    
                    response2 = self.session.post(f"{API_URL}/register", json=user2_data, timeout=10)
                    if response2.status_code == 200:
                        data2 = response2.json()
                        self.user2_token = data2["access_token"]
                        self.user2_id = data2["user_id"]
                        self.log_test("User Registration (User 2)", True, f"User {self.user2_username} registered successfully")
                        return True
                    else:
                        self.log_test("User Registration (User 2)", False, f"Status code: {response2.status_code}")
                        return False
                else:
                    self.log_test("User Registration (User 1)", False, f"Missing required fields in response")
                    return False
            else:
                self.log_test("User Registration (User 1)", False, f"Status code: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("User Registration", False, f"Error: {str(e)}")
            return False
    
    def test_duplicate_registration(self):
        """Test duplicate username registration"""
        try:
            user_data = {
                "username": self.user1_username,
                "password": "differentpass"
            }
            
            response = self.session.post(f"{API_URL}/register", json=user_data, timeout=10)
            
            if response.status_code == 400:
                self.log_test("Duplicate Registration Prevention", True, "Correctly rejected duplicate username")
                return True
            else:
                self.log_test("Duplicate Registration Prevention", False, f"Expected 400, got {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Duplicate Registration Prevention", False, f"Error: {str(e)}")
            return False
    
    def test_user_login(self):
        """Test user login endpoint"""
        try:
            # Test valid login
            login_data = {
                "username": self.user1_username,
                "password": "securepass123"
            }
            
            response = self.session.post(f"{API_URL}/login", json=login_data, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["access_token", "token_type", "user_id", "username"]
                
                if all(field in data for field in required_fields):
                    # Update token (should be same as registration token)
                    self.user1_token = data["access_token"]
                    self.log_test("User Login (Valid)", True, f"User {self.user1_username} logged in successfully")
                    
                    # Test invalid login
                    invalid_login = {
                        "username": self.user1_username,
                        "password": "wrongpassword"
                    }
                    
                    response2 = self.session.post(f"{API_URL}/login", json=invalid_login, timeout=10)
                    if response2.status_code == 401:
                        self.log_test("User Login (Invalid)", True, "Correctly rejected invalid credentials")
                        return True
                    else:
                        self.log_test("User Login (Invalid)", False, f"Expected 401, got {response2.status_code}")
                        return False
                else:
                    self.log_test("User Login (Valid)", False, "Missing required fields in response")
                    return False
            else:
                self.log_test("User Login (Valid)", False, f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("User Login", False, f"Error: {str(e)}")
            return False
    
    def test_protected_endpoints(self):
        """Test JWT token authentication on protected endpoints"""
        try:
            # Test with valid token
            headers = {"Authorization": f"Bearer {self.user1_token}"}
            response = self.session.get(f"{API_URL}/me", headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("username") == self.user1_username:
                    self.log_test("Protected Endpoint (Valid Token)", True, "Successfully accessed /me with valid token")
                    
                    # Test with invalid token
                    invalid_headers = {"Authorization": "Bearer invalid_token_here"}
                    response2 = self.session.get(f"{API_URL}/me", headers=invalid_headers, timeout=10)
                    
                    if response2.status_code == 401:
                        self.log_test("Protected Endpoint (Invalid Token)", True, "Correctly rejected invalid token")
                        
                        # Test without token
                        response3 = self.session.get(f"{API_URL}/me", timeout=10)
                        if response3.status_code == 403:
                            self.log_test("Protected Endpoint (No Token)", True, "Correctly rejected request without token")
                            return True
                        else:
                            self.log_test("Protected Endpoint (No Token)", False, f"Expected 403, got {response3.status_code}")
                            return False
                    else:
                        self.log_test("Protected Endpoint (Invalid Token)", False, f"Expected 401, got {response2.status_code}")
                        return False
                else:
                    self.log_test("Protected Endpoint (Valid Token)", False, f"Wrong user data returned")
                    return False
            else:
                self.log_test("Protected Endpoint (Valid Token)", False, f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Protected Endpoints", False, f"Error: {str(e)}")
            return False
    
    def test_user_search(self):
        """Test user search functionality"""
        try:
            headers = {"Authorization": f"Bearer {self.user1_token}"}
            
            # Search for user2
            response = self.session.get(f"{API_URL}/users/search?q={self.user2_username}", headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    found_user = next((user for user in data if user["username"] == self.user2_username), None)
                    if found_user:
                        self.log_test("User Search", True, f"Successfully found user {self.user2_username}")
                        return True
                    else:
                        self.log_test("User Search", False, f"User {self.user2_username} not found in search results")
                        return False
                else:
                    self.log_test("User Search", False, "No search results returned")
                    return False
            else:
                self.log_test("User Search", False, f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("User Search", False, f"Error: {str(e)}")
            return False
    
    def test_conversations_endpoint(self):
        """Test conversations endpoint"""
        try:
            headers = {"Authorization": f"Bearer {self.user1_token}"}
            response = self.session.get(f"{API_URL}/conversations", headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    self.log_test("Get Conversations", True, f"Successfully retrieved {len(data)} conversations")
                    return True
                else:
                    self.log_test("Get Conversations", False, "Response is not a list")
                    return False
            else:
                self.log_test("Get Conversations", False, f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Get Conversations", False, f"Error: {str(e)}")
            return False

    async def test_socketio_connection(self):
        """Test Socket.io connection and authentication"""
        try:
            # Create socket client
            sio = socketio.AsyncClient()
            
            # Connection events
            connection_success = False
            auth_success = False
            
            @sio.event
            async def connect():
                nonlocal connection_success
                connection_success = True
                print("    Socket.io connected successfully")
            
            @sio.event
            async def authenticated(data):
                nonlocal auth_success
                if data.get('status') == 'success':
                    auth_success = True
                    print("    Socket.io authentication successful")
            
            @sio.event
            async def auth_error(data):
                print(f"    Socket.io auth error: {data}")
            
            @sio.event
            async def disconnect():
                print("    Socket.io disconnected")
            
            # Connect to server
            await sio.connect(BASE_URL)
            await asyncio.sleep(1)  # Wait for connection
            
            if connection_success:
                self.log_test("Socket.io Connection", True, "Successfully connected to Socket.io server")
                
                # Test authentication
                await sio.emit('authenticate', {'token': self.user1_token})
                await asyncio.sleep(2)  # Wait for auth response
                
                if auth_success:
                    self.log_test("Socket.io Authentication", True, "Successfully authenticated via Socket.io")
                    
                    # Disconnect
                    await sio.disconnect()
                    return True
                else:
                    self.log_test("Socket.io Authentication", False, "Authentication failed")
                    await sio.disconnect()
                    return False
            else:
                self.log_test("Socket.io Connection", False, "Failed to connect to Socket.io server")
                return False
                
        except Exception as e:
            self.log_test("Socket.io Connection", False, f"Error: {str(e)}")
            return False

    async def test_socketio_messaging(self):
        """Test Socket.io real-time messaging"""
        try:
            # Create two socket clients
            sio1 = socketio.AsyncClient()  # User 1
            sio2 = socketio.AsyncClient()  # User 2
            
            message_received = False
            received_message = None
            
            @sio2.event
            async def new_message(data):
                nonlocal message_received, received_message
                message_received = True
                received_message = data
                print(f"    User 2 received message: {data}")
            
            # Connect both clients
            await sio1.connect(BASE_URL)
            await sio2.connect(BASE_URL)
            await asyncio.sleep(1)
            
            # Authenticate both clients
            await sio1.emit('authenticate', {'token': self.user1_token})
            await sio2.emit('authenticate', {'token': self.user2_token})
            await asyncio.sleep(2)
            
            # Send message from user1 to user2
            test_message = "Hello from Alice! This is a test message."
            await sio1.emit('send_message', {
                'recipient_id': self.user2_id,
                'content': test_message
            })
            
            # Wait for message to be received
            await asyncio.sleep(3)
            
            if message_received and received_message:
                if received_message.get('content') == test_message:
                    self.log_test("Socket.io Real-time Messaging", True, "Message sent and received successfully")
                    
                    # Store conversation ID for later tests
                    self.conversation_id = received_message.get('conversation_id')
                    
                    await sio1.disconnect()
                    await sio2.disconnect()
                    return True
                else:
                    self.log_test("Socket.io Real-time Messaging", False, "Message content mismatch")
                    await sio1.disconnect()
                    await sio2.disconnect()
                    return False
            else:
                self.log_test("Socket.io Real-time Messaging", False, "Message not received")
                await sio1.disconnect()
                await sio2.disconnect()
                return False
                
        except Exception as e:
            self.log_test("Socket.io Real-time Messaging", False, f"Error: {str(e)}")
            return False

    def test_message_persistence(self):
        """Test message storage and retrieval"""
        try:
            if not self.conversation_id:
                self.log_test("Message Persistence", False, "No conversation ID available from previous test")
                return False
            
            headers = {"Authorization": f"Bearer {self.user1_token}"}
            response = self.session.get(f"{API_URL}/messages/{self.conversation_id}", headers=headers, timeout=10)
            
            if response.status_code == 200:
                messages = response.json()
                if isinstance(messages, list) and len(messages) > 0:
                    # Check if our test message is in the database
                    test_message_found = any(
                        msg.get('content') == "Hello from Alice! This is a test message." 
                        for msg in messages
                    )
                    
                    if test_message_found:
                        self.log_test("Message Persistence", True, f"Messages stored and retrieved successfully ({len(messages)} messages)")
                        return True
                    else:
                        self.log_test("Message Persistence", False, "Test message not found in database")
                        return False
                else:
                    self.log_test("Message Persistence", False, "No messages found in conversation")
                    return False
            else:
                self.log_test("Message Persistence", False, f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Message Persistence", False, f"Error: {str(e)}")
            return False

    def test_conversation_management(self):
        """Test conversation creation and management"""
        try:
            headers = {"Authorization": f"Bearer {self.user1_token}"}
            response = self.session.get(f"{API_URL}/conversations", headers=headers, timeout=10)
            
            if response.status_code == 200:
                conversations = response.json()
                if isinstance(conversations, list) and len(conversations) > 0:
                    # Find conversation with user2
                    user2_conversation = next(
                        (conv for conv in conversations if conv.get('other_user_id') == self.user2_id), 
                        None
                    )
                    
                    if user2_conversation:
                        required_fields = ['conversation_id', 'other_user_id', 'other_username', 'last_message']
                        if all(field in user2_conversation for field in required_fields):
                            self.log_test("Conversation Management", True, "Conversation created and managed successfully")
                            return True
                        else:
                            self.log_test("Conversation Management", False, "Missing required fields in conversation")
                            return False
                    else:
                        self.log_test("Conversation Management", False, "Conversation with user2 not found")
                        return False
                else:
                    self.log_test("Conversation Management", False, "No conversations found")
                    return False
            else:
                self.log_test("Conversation Management", False, f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Conversation Management", False, f"Error: {str(e)}")
            return False

    def test_rest_api_message_sending(self):
        """Test REST API message sending endpoint (fallback when WebSocket unavailable)"""
        try:
            headers = {"Authorization": f"Bearer {self.user1_token}"}
            
            # Test sending message via REST API
            message_data = {
                "recipient_id": self.user2_id,
                "content": "Hello from REST API! This is a fallback message test."
            }
            
            response = self.session.post(f"{API_URL}/send-message", json=message_data, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["message_id", "timestamp", "conversation_id", "status"]
                
                if all(field in data for field in required_fields):
                    if data.get("status") == "sent":
                        self.log_test("REST API Message Sending", True, "Message sent successfully via REST API")
                        
                        # Store conversation ID for verification
                        self.conversation_id = data["conversation_id"]
                        
                        # Verify message was stored in database
                        time.sleep(1)  # Brief delay to ensure database write
                        
                        # Get messages to verify persistence
                        messages_response = self.session.get(f"{API_URL}/messages/{self.conversation_id}", headers=headers, timeout=10)
                        
                        if messages_response.status_code == 200:
                            messages = messages_response.json()
                            rest_message_found = any(
                                msg.get('content') == "Hello from REST API! This is a fallback message test." 
                                for msg in messages
                            )
                            
                            if rest_message_found:
                                self.log_test("REST API Message Persistence", True, "REST API message stored and retrieved successfully")
                                return True
                            else:
                                self.log_test("REST API Message Persistence", False, "REST API message not found in database")
                                return False
                        else:
                            self.log_test("REST API Message Persistence", False, f"Failed to retrieve messages: {messages_response.status_code}")
                            return False
                    else:
                        self.log_test("REST API Message Sending", False, f"Unexpected status: {data.get('status')}")
                        return False
                else:
                    self.log_test("REST API Message Sending", False, "Missing required fields in response")
                    return False
            else:
                self.log_test("REST API Message Sending", False, f"Status code: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("REST API Message Sending", False, f"Error: {str(e)}")
            return False

    def test_rest_api_conversation_creation(self):
        """Test conversation creation via REST API messaging"""
        try:
            # Create a third user for testing new conversation creation
            user3_data = {
                "username": "charlie_brown",
                "password": "testpass789"
            }
            
            response = self.session.post(f"{API_URL}/register", json=user3_data, timeout=10)
            
            if response.status_code == 200:
                user3_data_response = response.json()
                user3_id = user3_data_response["user_id"]
                
                # Send message to new user via REST API
                headers = {"Authorization": f"Bearer {self.user1_token}"}
                message_data = {
                    "recipient_id": user3_id,
                    "content": "Hello Charlie! This is a new conversation via REST API."
                }
                
                message_response = self.session.post(f"{API_URL}/send-message", json=message_data, headers=headers, timeout=10)
                
                if message_response.status_code == 200:
                    # Check if new conversation was created
                    conversations_response = self.session.get(f"{API_URL}/conversations", headers=headers, timeout=10)
                    
                    if conversations_response.status_code == 200:
                        conversations = conversations_response.json()
                        charlie_conversation = next(
                            (conv for conv in conversations if conv.get('other_user_id') == user3_id), 
                            None
                        )
                        
                        if charlie_conversation:
                            self.log_test("REST API Conversation Creation", True, "New conversation created successfully via REST API")
                            return True
                        else:
                            self.log_test("REST API Conversation Creation", False, "New conversation not found")
                            return False
                    else:
                        self.log_test("REST API Conversation Creation", False, f"Failed to get conversations: {conversations_response.status_code}")
                        return False
                else:
                    self.log_test("REST API Conversation Creation", False, f"Failed to send message: {message_response.status_code}")
                    return False
            else:
                self.log_test("REST API Conversation Creation", False, f"Failed to create test user: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("REST API Conversation Creation", False, f"Error: {str(e)}")
            return False

    async def run_all_tests(self):
        """Run all backend tests"""
        print("=" * 60)
        print("STARTING COMPREHENSIVE BACKEND TESTING")
        print("=" * 60)
        
        # Basic connectivity tests
        if not self.test_health_check():
            print("\n❌ CRITICAL: Backend health check failed. Cannot proceed with testing.")
            return False
        
        # Authentication tests
        print("\n--- AUTHENTICATION TESTING ---")
        if not self.test_user_registration():
            print("❌ CRITICAL: User registration failed. Cannot proceed.")
            return False
        
        self.test_duplicate_registration()
        
        if not self.test_user_login():
            print("❌ CRITICAL: User login failed. Cannot proceed.")
            return False
        
        if not self.test_protected_endpoints():
            print("❌ CRITICAL: JWT authentication failed. Cannot proceed.")
            return False
        
        # API endpoint tests
        print("\n--- API ENDPOINT TESTING ---")
        self.test_user_search()
        self.test_conversations_endpoint()
        
        # REST API Message Sending Tests (Primary Focus)
        print("\n--- REST API MESSAGE SENDING TESTING (FALLBACK MODE) ---")
        self.test_rest_api_message_sending()
        self.test_rest_api_conversation_creation()
        
        # Real-time messaging tests
        print("\n--- REAL-TIME MESSAGING TESTING ---")
        await self.test_socketio_connection()
        await self.test_socketio_messaging()
        
        # Data persistence tests
        print("\n--- DATA PERSISTENCE TESTING ---")
        self.test_message_persistence()
        self.test_conversation_management()
        
        return True

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for result in self.test_results if result["success"])
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        
        if total - passed > 0:
            print("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  - {result['test']}: {result['message']}")
        
        print("\n" + "=" * 60)
        
        return passed == total

async def main():
    """Main test execution"""
    tester = ChatAppTester()
    
    try:
        success = await tester.run_all_tests()
        all_passed = tester.print_summary()
        
        if all_passed:
            print("🎉 ALL TESTS PASSED! Backend is working correctly.")
            return True
        else:
            print("⚠️  Some tests failed. Check the summary above.")
            return False
            
    except Exception as e:
        print(f"❌ CRITICAL ERROR during testing: {str(e)}")
        return False

if __name__ == "__main__":
    asyncio.run(main())