#!/usr/bin/env python3
"""
Simple Socket.io Connection Test
"""

import asyncio
import socketio
import requests

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
print(f"Testing Socket.io connection to: {BASE_URL}")

async def test_simple_connection():
    try:
        # First test if the server responds to HTTP
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        print(f"HTTP Health check: {response.status_code}")
        
        # Test Socket.io connection
        sio = socketio.AsyncClient()
        
        @sio.event
        async def connect():
            print("✅ Socket.io connected successfully!")
            await sio.disconnect()
        
        @sio.event
        async def connect_error(data):
            print(f"❌ Socket.io connection error: {data}")
        
        @sio.event
        async def disconnect():
            print("Socket.io disconnected")
        
        print("Attempting Socket.io connection...")
        await sio.connect(BASE_URL, wait_timeout=10)
        await asyncio.sleep(2)
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_simple_connection())