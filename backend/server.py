from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import jwt
import bcrypt
from datetime import datetime, timedelta
from pymongo import MongoClient
import uuid
import socketio
from dotenv import load_dotenv

load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB setup
mongo_url = os.environ.get('MONGO_URL')
db_name = os.environ.get('DB_NAME', 'chat_app')
client = MongoClient(mongo_url)
db = client[db_name]

# Collections
users_collection = db.users
messages_collection = db.messages
conversations_collection = db.conversations

# Security
security = HTTPBearer()
SECRET_KEY = "your-secret-key-for-jwt"
ALGORITHM = "HS256"

# Socket.IO setup with better proxy support
sio = socketio.AsyncServer(
    cors_allowed_origins="*",
    async_mode="asgi",
    transports=['polling', 'websocket'],  # Start with polling, upgrade to websocket
    engineio_logger=True,
    socketio_logger=True
)

socket_app = socketio.ASGIApp(sio, app)

# Connected users tracking
connected_users: Dict[str, str] = {}  # socket_id -> user_id
user_sockets: Dict[str, str] = {}     # user_id -> socket_id

# Pydantic models
class UserRegister(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class MessageSend(BaseModel):
    recipient_id: str
    content: str

class MessageResponse(BaseModel):
    message_id: str
    sender_id: str
    recipient_id: str
    content: str
    timestamp: datetime
    is_read: bool

class ConversationResponse(BaseModel):
    conversation_id: str
    other_user_id: str
    other_username: str
    last_message: Optional[str]
    last_message_time: Optional[datetime]
    unread_count: int

# JWT functions
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Hash password
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# Socket.IO events
@sio.event
async def connect(sid, environ):
    print(f"Client {sid} connected")

@sio.event
async def disconnect(sid):
    print(f"Client {sid} disconnected")
    # Remove from connected users
    if sid in connected_users:
        user_id = connected_users[sid]
        del connected_users[sid]
        if user_id in user_sockets:
            del user_sockets[user_id]
        # Broadcast user offline status
        await sio.emit('user_status', {'user_id': user_id, 'status': 'offline'})

@sio.event
async def authenticate(sid, data):
    try:
        token = data.get('token')
        if not token:
            await sio.emit('auth_error', {'message': 'No token provided'}, room=sid)
            return
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        
        if user_id:
            # Store connection
            connected_users[sid] = user_id
            user_sockets[user_id] = sid
            
            # Broadcast user online status
            await sio.emit('user_status', {'user_id': user_id, 'status': 'online'})
            await sio.emit('authenticated', {'status': 'success'}, room=sid)
            print(f"User {user_id} authenticated on socket {sid}")
        else:
            await sio.emit('auth_error', {'message': 'Invalid token'}, room=sid)
    except jwt.PyJWTError:
        await sio.emit('auth_error', {'message': 'Invalid token'}, room=sid)

@sio.event
async def send_message(sid, data):
    try:
        if sid not in connected_users:
            await sio.emit('error', {'message': 'Not authenticated'}, room=sid)
            return
        
        sender_id = connected_users[sid]
        recipient_id = data.get('recipient_id')
        content = data.get('content')
        
        if not recipient_id or not content:
            await sio.emit('error', {'message': 'Missing recipient_id or content'}, room=sid)
            return
        
        # Save message to database
        message_id = str(uuid.uuid4())
        message_doc = {
            "message_id": message_id,
            "sender_id": sender_id,
            "recipient_id": recipient_id,
            "content": content,
            "timestamp": datetime.utcnow(),
            "is_read": False
        }
        messages_collection.insert_one(message_doc)
        
        # Update or create conversation
        conversation_id = get_or_create_conversation(sender_id, recipient_id)
        conversations_collection.update_one(
            {"conversation_id": conversation_id},
            {
                "$set": {
                    "last_message": content,
                    "last_message_time": datetime.utcnow(),
                    "last_sender_id": sender_id
                }
            }
        )
        
        # Send to recipient if online
        if recipient_id in user_sockets:
            recipient_socket = user_sockets[recipient_id]
            await sio.emit('new_message', {
                'message_id': message_id,
                'sender_id': sender_id,
                'content': content,
                'timestamp': message_doc['timestamp'].isoformat(),
                'conversation_id': conversation_id
            }, room=recipient_socket)
        
        # Confirm to sender
        await sio.emit('message_sent', {
            'message_id': message_id,
            'timestamp': message_doc['timestamp'].isoformat(),
            'conversation_id': conversation_id
        }, room=sid)
        
    except Exception as e:
        await sio.emit('error', {'message': str(e)}, room=sid)

# Helper functions
def get_or_create_conversation(user1_id: str, user2_id: str) -> str:
    # Sort user IDs to ensure consistent conversation ID
    participants = sorted([user1_id, user2_id])
    
    conversation = conversations_collection.find_one({
        "participants": participants
    })
    
    if conversation:
        return conversation["conversation_id"]
    else:
        conversation_id = str(uuid.uuid4())
        conversations_collection.insert_one({
            "conversation_id": conversation_id,
            "participants": participants,
            "created_at": datetime.utcnow(),
            "last_message": "",
            "last_message_time": datetime.utcnow(),
            "last_sender_id": ""
        })
        return conversation_id

# API Routes
@app.post("/api/register")
async def register(user_data: UserRegister):
    # Check if user exists
    if users_collection.find_one({"username": user_data.username}):
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Hash password and create user
    user_id = str(uuid.uuid4())
    hashed_password = hash_password(user_data.password)
    
    user_doc = {
        "user_id": user_id,
        "username": user_data.username,
        "password": hashed_password,
        "created_at": datetime.utcnow(),
        "last_active": datetime.utcnow()
    }
    
    users_collection.insert_one(user_doc)
    
    # Create access token
    access_token = create_access_token(
        data={"sub": user_id}, 
        expires_delta=timedelta(days=30)
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user_id,
        "username": user_data.username
    }

@app.post("/api/login")
async def login(user_data: UserLogin):
    # Find user
    user = users_collection.find_one({"username": user_data.username})
    if not user or not verify_password(user_data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    # Update last active
    users_collection.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"last_active": datetime.utcnow()}}
    )
    
    # Create access token
    access_token = create_access_token(
        data={"sub": user["user_id"]}, 
        expires_delta=timedelta(days=30)
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user["user_id"],
        "username": user["username"]
    }

@app.get("/api/conversations")
async def get_conversations(current_user_id: str = Depends(verify_token)):
    # Get all conversations for the current user
    conversations = list(conversations_collection.find({
        "participants": current_user_id
    }).sort("last_message_time", -1))
    
    result = []
    for conv in conversations:
        # Get other user info
        other_user_id = next(p for p in conv["participants"] if p != current_user_id)
        other_user = users_collection.find_one({"user_id": other_user_id})
        
        # Count unread messages
        unread_count = messages_collection.count_documents({
            "recipient_id": current_user_id,
            "sender_id": other_user_id,
            "is_read": False
        })
        
        result.append({
            "conversation_id": conv["conversation_id"],
            "other_user_id": other_user_id,
            "other_username": other_user["username"] if other_user else "Unknown",
            "last_message": conv.get("last_message", ""),
            "last_message_time": conv.get("last_message_time"),
            "unread_count": unread_count
        })
    
    return result

@app.get("/api/messages/{conversation_id}")
async def get_messages(conversation_id: str, current_user_id: str = Depends(verify_token)):
    # Verify user is part of this conversation
    conversation = conversations_collection.find_one({
        "conversation_id": conversation_id,
        "participants": current_user_id
    })
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Get messages
    messages = list(messages_collection.find({
        "$or": [
            {"sender_id": current_user_id, "recipient_id": {"$in": conversation["participants"]}},
            {"sender_id": {"$in": conversation["participants"]}, "recipient_id": current_user_id}
        ]
    }).sort("timestamp", 1))
    
    # Mark messages as read
    messages_collection.update_many(
        {"recipient_id": current_user_id, "sender_id": {"$in": conversation["participants"]}},
        {"$set": {"is_read": True}}
    )
    
    return messages

@app.get("/api/users/search")
async def search_users(q: str, current_user_id: str = Depends(verify_token)):
    # Search for users by username (excluding current user)
    users = list(users_collection.find({
        "username": {"$regex": q, "$options": "i"},
        "user_id": {"$ne": current_user_id}
    }).limit(10))
    
    return [{"user_id": user["user_id"], "username": user["username"]} for user in users]

@app.post("/api/send-message")
async def send_message_api(message_data: MessageSend, current_user_id: str = Depends(verify_token)):
    """Fallback API endpoint for sending messages when WebSocket is not available"""
    try:
        # Save message to database
        message_id = str(uuid.uuid4())
        message_doc = {
            "message_id": message_id,
            "sender_id": current_user_id,
            "recipient_id": message_data.recipient_id,
            "content": message_data.content,
            "timestamp": datetime.utcnow(),
            "is_read": False
        }
        messages_collection.insert_one(message_doc)
        
        # Update or create conversation
        conversation_id = get_or_create_conversation(current_user_id, message_data.recipient_id)
        conversations_collection.update_one(
            {"conversation_id": conversation_id},
            {
                "$set": {
                    "last_message": message_data.content,
                    "last_message_time": datetime.utcnow(),
                    "last_sender_id": current_user_id
                }
            }
        )
        
        # Try to notify via WebSocket if connected
        if message_data.recipient_id in user_sockets:
            recipient_socket = user_sockets[message_data.recipient_id]
            await sio.emit('new_message', {
                'message_id': message_id,
                'sender_id': current_user_id,
                'content': message_data.content,
                'timestamp': message_doc['timestamp'].isoformat(),
                'conversation_id': conversation_id
            }, room=recipient_socket)
        
        return {
            "message_id": message_id,
            "timestamp": message_doc['timestamp'],
            "conversation_id": conversation_id,
            "status": "sent"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/me")
async def get_current_user(current_user_id: str = Depends(verify_token)):
    user = users_collection.find_one({"user_id": current_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "created_at": user["created_at"],
        "last_active": user["last_active"]
    }

# Health check
@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(socket_app, host="0.0.0.0", port=8001)