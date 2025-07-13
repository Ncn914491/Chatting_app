#!/usr/bin/env python3
"""
Focused REST API Testing for Chat Application
Tests specifically the new /api/send-message endpoint and related functionality
"""

import requests
import json
import time
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

print(f"Testing REST API at: {API_URL}")

class RestAPITester:
    def __init__(self):
        self.session = requests.Session()
        timestamp = str(int(time.time()))
        self.user1_username = f"emma_wilson_{timestamp}"
        self.user2_username = f"james_davis_{timestamp}"
        self.user1_token = None
        self.user2_token = None
        self.user1_id = None
        self.user2_id = None
        
    def setup_users(self):
        """Create test users"""
        print("Setting up test users...")
        
        # Register user 1
        user1_data = {"username": self.user1_username, "password": "testpass123"}
        response1 = self.session.post(f"{API_URL}/register", json=user1_data, timeout=10)
        if response1.status_code != 200:
            print(f"❌ Failed to register user 1: {response1.status_code}")
            return False
        
        data1 = response1.json()
        self.user1_token = data1["access_token"]
        self.user1_id = data1["user_id"]
        
        # Register user 2
        user2_data = {"username": self.user2_username, "password": "testpass456"}
        response2 = self.session.post(f"{API_URL}/register", json=user2_data, timeout=10)
        if response2.status_code != 200:
            print(f"❌ Failed to register user 2: {response2.status_code}")
            return False
        
        data2 = response2.json()
        self.user2_token = data2["access_token"]
        self.user2_id = data2["user_id"]
        
        print(f"✅ Users created: {self.user1_username} and {self.user2_username}")
        return True
    
    def test_rest_api_messaging_flow(self):
        """Test complete REST API messaging flow"""
        print("\n--- TESTING REST API MESSAGING FLOW ---")
        
        # 1. Send message from user1 to user2
        headers1 = {"Authorization": f"Bearer {self.user1_token}"}
        message_data = {
            "recipient_id": self.user2_id,
            "content": "Hello James! This is a test message via REST API."
        }
        
        print("1. Sending message via REST API...")
        response = self.session.post(f"{API_URL}/send-message", json=message_data, headers=headers1, timeout=10)
        
        if response.status_code != 200:
            print(f"❌ Failed to send message: {response.status_code} - {response.text}")
            return False
        
        message_response = response.json()
        conversation_id = message_response.get("conversation_id")
        print(f"✅ Message sent successfully. Conversation ID: {conversation_id}")
        
        # 2. Verify conversation was created for user1
        print("2. Checking conversations for user1...")
        conv_response1 = self.session.get(f"{API_URL}/conversations", headers=headers1, timeout=10)
        
        if conv_response1.status_code != 200:
            print(f"❌ Failed to get conversations for user1: {conv_response1.status_code}")
            return False
        
        conversations1 = conv_response1.json()
        user2_conv = next((c for c in conversations1 if c.get("other_user_id") == self.user2_id), None)
        
        if not user2_conv:
            print("❌ Conversation with user2 not found for user1")
            return False
        
        print(f"✅ Conversation found for user1: {user2_conv['other_username']}")
        
        # 3. Verify conversation appears for user2
        print("3. Checking conversations for user2...")
        headers2 = {"Authorization": f"Bearer {self.user2_token}"}
        conv_response2 = self.session.get(f"{API_URL}/conversations", headers=headers2, timeout=10)
        
        if conv_response2.status_code != 200:
            print(f"❌ Failed to get conversations for user2: {conv_response2.status_code}")
            return False
        
        conversations2 = conv_response2.json()
        user1_conv = next((c for c in conversations2 if c.get("other_user_id") == self.user1_id), None)
        
        if not user1_conv:
            print("❌ Conversation with user1 not found for user2")
            return False
        
        print(f"✅ Conversation found for user2: {user1_conv['other_username']}")
        
        # 4. Retrieve messages from conversation
        print("4. Retrieving messages from conversation...")
        messages_response = self.session.get(f"{API_URL}/messages/{conversation_id}", headers=headers1, timeout=10)
        
        if messages_response.status_code != 200:
            print(f"❌ Failed to retrieve messages: {messages_response.status_code}")
            return False
        
        messages = messages_response.json()
        test_message = next((m for m in messages if m.get("content") == message_data["content"]), None)
        
        if not test_message:
            print("❌ Test message not found in conversation")
            return False
        
        print(f"✅ Message retrieved successfully: {len(messages)} messages in conversation")
        
        # 5. Send reply from user2 to user1
        print("5. Sending reply message...")
        reply_data = {
            "recipient_id": self.user1_id,
            "content": "Hi Emma! I received your message. This is my reply via REST API."
        }
        
        reply_response = self.session.post(f"{API_URL}/send-message", json=reply_data, headers=headers2, timeout=10)
        
        if reply_response.status_code != 200:
            print(f"❌ Failed to send reply: {reply_response.status_code}")
            return False
        
        print("✅ Reply sent successfully")
        
        # 6. Verify both messages are in conversation
        print("6. Verifying both messages in conversation...")
        final_messages_response = self.session.get(f"{API_URL}/messages/{conversation_id}", headers=headers1, timeout=10)
        
        if final_messages_response.status_code != 200:
            print(f"❌ Failed to retrieve final messages: {final_messages_response.status_code}")
            return False
        
        final_messages = final_messages_response.json()
        
        if len(final_messages) < 2:
            print(f"❌ Expected at least 2 messages, found {len(final_messages)}")
            return False
        
        print(f"✅ Conversation complete with {len(final_messages)} messages")
        
        # 7. Test user search functionality
        print("7. Testing user search...")
        search_response = self.session.get(f"{API_URL}/users/search?q={self.user2_username[:5]}", headers=headers1, timeout=10)
        
        if search_response.status_code != 200:
            print(f"❌ User search failed: {search_response.status_code}")
            return False
        
        search_results = search_response.json()
        found_user = next((u for u in search_results if u.get("user_id") == self.user2_id), None)
        
        if not found_user:
            print("❌ User2 not found in search results")
            return False
        
        print(f"✅ User search working: Found {found_user['username']}")
        
        return True
    
    def run_test(self):
        """Run the complete test"""
        print("=" * 60)
        print("FOCUSED REST API MESSAGING TEST")
        print("=" * 60)
        
        if not self.setup_users():
            print("❌ FAILED: Could not set up test users")
            return False
        
        if not self.test_rest_api_messaging_flow():
            print("❌ FAILED: REST API messaging flow test failed")
            return False
        
        print("\n" + "=" * 60)
        print("🎉 ALL REST API TESTS PASSED!")
        print("✅ REST API message sending works correctly")
        print("✅ Message persistence verified")
        print("✅ Conversation creation and management working")
        print("✅ User search functionality operational")
        print("✅ Fallback messaging system is fully functional")
        print("=" * 60)
        
        return True

if __name__ == "__main__":
    tester = RestAPITester()
    success = tester.run_test()
    exit(0 if success else 1)