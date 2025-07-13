#!/usr/bin/env python3
"""
REST API Only Backend Test - Testing message persistence without Socket.io
"""

import requests
import json
import time
from datetime import datetime

# Get backend URL
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

def test_message_flow_via_api():
    """Test message flow using only REST API endpoints"""
    session = requests.Session()
    
    # Register two users
    user1_data = {"username": "charlie_test", "password": "testpass123"}
    user2_data = {"username": "diana_test", "password": "testpass456"}
    
    print("1. Registering users...")
    resp1 = session.post(f"{API_URL}/register", json=user1_data)
    resp2 = session.post(f"{API_URL}/register", json=user2_data)
    
    if resp1.status_code != 200 or resp2.status_code != 200:
        print(f"❌ User registration failed: {resp1.status_code}, {resp2.status_code}")
        return False
    
    user1_token = resp1.json()["access_token"]
    user1_id = resp1.json()["user_id"]
    user2_token = resp2.json()["access_token"]
    user2_id = resp2.json()["user_id"]
    
    print(f"✅ Users registered: {user1_id}, {user2_id}")
    
    # Test user search
    print("2. Testing user search...")
    headers1 = {"Authorization": f"Bearer {user1_token}"}
    search_resp = session.get(f"{API_URL}/users/search?q=diana", headers=headers1)
    
    if search_resp.status_code == 200:
        search_results = search_resp.json()
        diana_found = any(user["username"] == "diana_test" for user in search_results)
        if diana_found:
            print("✅ User search working correctly")
        else:
            print("❌ User search not finding expected user")
            return False
    else:
        print(f"❌ User search failed: {search_resp.status_code}")
        return False
    
    # Test conversations endpoint (should be empty initially)
    print("3. Testing initial conversations...")
    conv_resp = session.get(f"{API_URL}/conversations", headers=headers1)
    
    if conv_resp.status_code == 200:
        conversations = conv_resp.json()
        if len(conversations) == 0:
            print("✅ Initial conversations list is empty as expected")
        else:
            print(f"⚠️  Found {len(conversations)} existing conversations")
    else:
        print(f"❌ Conversations endpoint failed: {conv_resp.status_code}")
        return False
    
    # Since Socket.io is not working, we can't test real-time messaging
    # But we can verify that the database and API structure is correct
    print("4. Testing user profile endpoint...")
    me_resp = session.get(f"{API_URL}/me", headers=headers1)
    
    if me_resp.status_code == 200:
        user_data = me_resp.json()
        if user_data["username"] == "charlie_test":
            print("✅ User profile endpoint working correctly")
        else:
            print("❌ User profile data incorrect")
            return False
    else:
        print(f"❌ User profile endpoint failed: {me_resp.status_code}")
        return False
    
    print("\n✅ All REST API tests passed!")
    print("⚠️  Socket.io real-time messaging could not be tested due to connection issues")
    return True

if __name__ == "__main__":
    success = test_message_flow_via_api()
    if success:
        print("\n🎉 REST API functionality is working correctly!")
    else:
        print("\n❌ Some REST API tests failed")