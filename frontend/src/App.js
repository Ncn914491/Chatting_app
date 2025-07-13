import React, { useState, useEffect, useRef, useCallback } from 'react';
import io from 'socket.io-client';
import axios from 'axios';
import './App.css';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL;

function App() {
  // Auth state
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));
  
  // UI state
  const [activeView, setActiveView] = useState('login'); // 'login', 'register', 'chat'
  const [loading, setLoading] = useState(false);
  
  // Chat state
  const [conversations, setConversations] = useState([]);
  const [activeConversation, setActiveConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [showUserSearch, setShowUserSearch] = useState(false);
  const [isSocketConnected, setIsSocketConnected] = useState(false);
  const [usePolling, setUsePolling] = useState(false);
  
  // Form state
  const [formData, setFormData] = useState({ username: '', password: '' });
  const [error, setError] = useState('');
  
  // Refs
  const socketRef = useRef(null);
  const messagesEndRef = useRef(null);
  const pollingInterval = useRef(null);
  
  // Scroll to bottom of messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  
  useEffect(() => {
    scrollToBottom();
  }, [messages]);
  
  // Check if user is logged in on mount
  useEffect(() => {
    if (token) {
      fetchCurrentUser();
    }
  }, [token]);
  
  // Setup socket connection when logged in
  useEffect(() => {
    if (isLoggedIn && token && !socketRef.current) {
      setupSocket();
    }
    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
        socketRef.current = null;
      }
    };
  }, [isLoggedIn, token]);
  
  // Load conversations when logged in
  useEffect(() => {
    if (isLoggedIn) {
      loadConversations();
    }
  }, [isLoggedIn]);
  
  // Message polling for fallback when WebSocket fails
  const startMessagePolling = useCallback(() => {
    if (pollingInterval.current) return;
    
    pollingInterval.current = setInterval(() => {
      if (activeConversation && activeConversation.conversation_id !== `temp_${Date.now()}`) {
        loadMessages(activeConversation.conversation_id);
      }
      loadConversations(); // Refresh conversation list
    }, 3000); // Poll every 3 seconds
  }, [activeConversation]);
  
  const stopMessagePolling = useCallback(() => {
    if (pollingInterval.current) {
      clearInterval(pollingInterval.current);
      pollingInterval.current = null;
    }
  }, []);
  
  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      stopMessagePolling();
    };
  }, [stopMessagePolling]);
  
  const setupSocket = useCallback(() => {
    if (socketRef.current) return;
    
    socketRef.current = io(API_BASE_URL, {
      transports: ['polling', 'websocket'], // Start with polling, then upgrade
      upgrade: true,
      rememberUpgrade: true,
      timeout: 20000,
      forceNew: true
    });
    
    socketRef.current.on('connect', () => {
      console.log('Connected to server');
      setIsSocketConnected(true);
      setUsePolling(false);
      // Authenticate with token
      socketRef.current.emit('authenticate', { token });
    });
    
    socketRef.current.on('connect_error', (error) => {
      console.log('Socket connection failed, switching to polling mode:', error);
      setIsSocketConnected(false);
      setUsePolling(true);
      // Start polling for messages
      startMessagePolling();
    });
    
    socketRef.current.on('disconnect', (reason) => {
      console.log('Disconnected from server:', reason);
      setIsSocketConnected(false);
      if (reason === 'io server disconnect') {
        // Server disconnected, try to reconnect
        socketRef.current.connect();
      }
    });
    
    socketRef.current.on('authenticated', (data) => {
      console.log('Authenticated successfully');
    });
    
    socketRef.current.on('auth_error', (data) => {
      console.error('Authentication error:', data.message);
      logout();
    });
    
    socketRef.current.on('new_message', (data) => {
      console.log('New message received:', data);
      
      // Add message to current conversation if it's active
      if (activeConversation && 
          (data.sender_id === activeConversation.other_user_id || 
           data.sender_id === currentUser?.user_id)) {
        setMessages(prev => [...prev, {
          message_id: data.message_id,
          sender_id: data.sender_id,
          recipient_id: data.recipient_id || currentUser?.user_id,
          content: data.content,
          timestamp: data.timestamp,
          is_read: true
        }]);
      }
      
      // Refresh conversations to update last message
      loadConversations();
    });
    
    socketRef.current.on('message_sent', (data) => {
      console.log('Message sent confirmation:', data);
    });
    
    socketRef.current.on('user_status', (data) => {
      console.log('User status update:', data);
      // Update user online status in conversations
    });
    
    socketRef.current.on('error', (data) => {
      console.error('Socket error:', data.message);
      setError(data.message);
    });
    
    socketRef.current.on('disconnect', () => {
      console.log('Disconnected from server');
    });
  }, [token, activeConversation, currentUser]);
  
  const fetchCurrentUser = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setCurrentUser(response.data);
      setIsLoggedIn(true);
      setActiveView('chat');
    } catch (error) {
      console.error('Failed to fetch current user:', error);
      logout();
    }
  };
  
  const loadConversations = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/conversations`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setConversations(response.data);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  };
  
  const loadMessages = async (conversationId) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/messages/${conversationId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setMessages(response.data);
    } catch (error) {
      console.error('Failed to load messages:', error);
    }
  };
  
  const handleAuth = async (isRegister = false) => {
    setLoading(true);
    setError('');
    
    try {
      const endpoint = isRegister ? '/api/register' : '/api/login';
      const response = await axios.post(`${API_BASE_URL}${endpoint}`, formData);
      
      const { access_token, user_id, username } = response.data;
      
      localStorage.setItem('token', access_token);
      setToken(access_token);
      setCurrentUser({ user_id, username });
      setIsLoggedIn(true);
      setActiveView('chat');
      setFormData({ username: '', password: '' });
    } catch (error) {
      setError(error.response?.data?.detail || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };
  
  const logout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setIsLoggedIn(false);
    setCurrentUser(null);
    setActiveView('login');
    setConversations([]);
    setMessages([]);
    setActiveConversation(null);
    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
    }
  };
  
  const searchUsers = async (query) => {
    if (!query.trim()) {
      setSearchResults([]);
      return;
    }
    
    try {
      const response = await axios.get(`${API_BASE_URL}/api/users/search?q=${query}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSearchResults(response.data);
    } catch (error) {
      console.error('Failed to search users:', error);
    }
  };
  
  const startConversation = async (otherUser) => {
    // Check if conversation already exists
    const existingConv = conversations.find(conv => 
      conv.other_user_id === otherUser.user_id
    );
    
    if (existingConv) {
      setActiveConversation(existingConv);
      loadMessages(existingConv.conversation_id);
    } else {
      // Create new conversation locally
      const newConv = {
        conversation_id: `temp_${Date.now()}`,
        other_user_id: otherUser.user_id,
        other_username: otherUser.username,
        last_message: '',
        last_message_time: new Date(),
        unread_count: 0
      };
      setActiveConversation(newConv);
      setMessages([]);
    }
    
    setShowUserSearch(false);
    setSearchTerm('');
    setSearchResults([]);
  };
  
  const sendMessage = async () => {
    if (!newMessage.trim() || !activeConversation) return;
    
    const messageData = {
      recipient_id: activeConversation.other_user_id,
      content: newMessage.trim()
    };
    
    // Add message to UI immediately
    const tempMessage = {
      message_id: `temp_${Date.now()}`,
      sender_id: currentUser.user_id,
      recipient_id: activeConversation.other_user_id,
      content: newMessage.trim(),
      timestamp: new Date().toISOString(),
      is_read: false
    };
    
    setMessages(prev => [...prev, tempMessage]);
    setNewMessage('');
    
    try {
      if (isSocketConnected && socketRef.current) {
        // Send via WebSocket
        socketRef.current.emit('send_message', messageData);
      } else {
        // Send via REST API fallback
        const response = await axios.post(`${API_BASE_URL}/api/send-message`, messageData, {
          headers: { Authorization: `Bearer ${token}` }
        });
        
        if (response.data) {
          // Update the temporary message with real data
          setMessages(prev => prev.map(msg => 
            msg.message_id === tempMessage.message_id 
              ? { ...msg, message_id: response.data.message_id, timestamp: response.data.timestamp }
              : msg
          ));
          
          // Refresh conversations
          loadConversations();
        }
      }
    } catch (error) {
      console.error('Failed to send message:', error);
      // Remove the failed message from UI
      setMessages(prev => prev.filter(msg => msg.message_id !== tempMessage.message_id));
      setError('Failed to send message. Please try again.');
    }
  };
  
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };
  
  // Auth Forms
  const AuthForm = ({ isRegister }) => (
    <div className="min-h-screen bg-gradient-to-br from-blue-900 to-purple-900 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-800 mb-2">
            💬 ChatApp
          </h1>
          <p className="text-gray-600">
            {isRegister ? 'Create your account' : 'Welcome back'}
          </p>
        </div>
        
        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
            {error}
          </div>
        )}
        
        <form onSubmit={(e) => { e.preventDefault(); handleAuth(isRegister); }}>
          <div className="mb-4">
            <label className="block text-gray-700 text-sm font-bold mb-2">
              Username
            </label>
            <input
              type="text"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500"
              value={formData.username}
              onChange={(e) => setFormData({...formData, username: e.target.value})}
              required
            />
          </div>
          
          <div className="mb-6">
            <label className="block text-gray-700 text-sm font-bold mb-2">
              Password
            </label>
            <input
              type="password"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500"
              value={formData.password}
              onChange={(e) => setFormData({...formData, password: e.target.value})}
              required
            />
          </div>
          
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-lg transition duration-200"
          >
            {loading ? 'Loading...' : (isRegister ? 'Sign Up' : 'Sign In')}
          </button>
        </form>
        
        <div className="text-center mt-4">
          <button
            onClick={() => {
              setActiveView(isRegister ? 'login' : 'register');
              setError('');
              setFormData({ username: '', password: '' });
            }}
            className="text-blue-500 hover:text-blue-700 text-sm"
          >
            {isRegister ? 'Already have an account? Sign In' : "Don't have an account? Sign Up"}
          </button>
        </div>
      </div>
    </div>
  );
  
  // Chat Interface
  const ChatInterface = () => (
    <div className="flex h-screen bg-gray-100">
      {/* Sidebar */}
      <div className="w-1/3 bg-white border-r border-gray-300 flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-gray-200 bg-blue-600 text-white">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold">💬 Chats</h2>
            <button
              onClick={logout}
              className="text-blue-200 hover:text-white text-sm"
            >
              Logout
            </button>
          </div>
          <p className="text-blue-200 text-sm">@{currentUser?.username}</p>
        </div>
        
        {/* Search */}
        <div className="p-4 border-b border-gray-200">
          <div className="relative">
            <input
              type="text"
              placeholder="Search users..."
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500"
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                searchUsers(e.target.value);
                setShowUserSearch(e.target.value.length > 0);
              }}
            />
            {searchTerm && (
              <button
                onClick={() => {
                  setSearchTerm('');
                  setSearchResults([]);
                  setShowUserSearch(false);
                }}
                className="absolute right-2 top-2 text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            )}
          </div>
          
          {/* Search Results */}
          {showUserSearch && searchResults.length > 0 && (
            <div className="mt-2 bg-white border border-gray-200 rounded-lg shadow-lg max-h-40 overflow-y-auto">
              {searchResults.map(user => (
                <button
                  key={user.user_id}
                  onClick={() => startConversation(user)}
                  className="w-full px-4 py-2 text-left hover:bg-gray-100 border-b border-gray-100 last:border-b-0"
                >
                  <div className="font-medium">{user.username}</div>
                  <div className="text-sm text-gray-500">Start conversation</div>
                </button>
              ))}
            </div>
          )}
        </div>
        
        {/* Conversations */}
        <div className="flex-1 overflow-y-auto">
          {conversations.length === 0 ? (
            <div className="p-4 text-center text-gray-500">
              <p>No conversations yet</p>
              <p className="text-sm mt-1">Search for users to start chatting</p>
            </div>
          ) : (
            conversations.map(conv => (
              <button
                key={conv.conversation_id}
                onClick={() => {
                  setActiveConversation(conv);
                  loadMessages(conv.conversation_id);
                }}
                className={`w-full p-4 text-left border-b border-gray-100 hover:bg-gray-50 ${
                  activeConversation?.conversation_id === conv.conversation_id ? 'bg-blue-50' : ''
                }`}
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="font-semibold text-gray-800">{conv.other_username}</div>
                    <div className="text-sm text-gray-600 truncate mt-1">
                      {conv.last_message || 'No messages yet'}
                    </div>
                  </div>
                  {conv.unread_count > 0 && (
                    <div className="bg-blue-500 text-white text-xs rounded-full px-2 py-1 ml-2">
                      {conv.unread_count}
                    </div>
                  )}
                </div>
              </button>
            ))
          )}
        </div>
      </div>
      
      {/* Chat Area */}
      <div className="flex-1 flex flex-col">
        {activeConversation ? (
          <>
            {/* Chat Header */}
            <div className="p-4 border-b border-gray-200 bg-white">
              <h3 className="text-lg font-semibold text-gray-800">
                {activeConversation.other_username}
              </h3>
            </div>
            
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.map(message => (
                <div
                  key={message.message_id}
                  className={`flex ${
                    message.sender_id === currentUser?.user_id ? 'justify-end' : 'justify-start'
                  }`}
                >
                  <div
                    className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                      message.sender_id === currentUser?.user_id
                        ? 'bg-blue-500 text-white'
                        : 'bg-gray-200 text-gray-800'
                    }`}
                  >
                    <p>{message.content}</p>
                    <p className={`text-xs mt-1 ${
                      message.sender_id === currentUser?.user_id ? 'text-blue-100' : 'text-gray-500'
                    }`}>
                      {new Date(message.timestamp).toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
            
            {/* Message Input */}
            <div className="p-4 border-t border-gray-200 bg-white">
              <div className="flex space-x-2">
                <input
                  type="text"
                  placeholder="Type a message..."
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500"
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  onKeyPress={handleKeyPress}
                />
                <button
                  onClick={sendMessage}
                  disabled={!newMessage.trim()}
                  className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed"
                >
                  Send
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center bg-gray-50">
            <div className="text-center text-gray-500">
              <div className="text-6xl mb-4">💬</div>
              <h3 className="text-xl font-semibold mb-2">Welcome to ChatApp</h3>
              <p>Select a conversation or search for users to start chatting</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
  
  // Main render
  if (activeView === 'login') {
    return <AuthForm isRegister={false} />;
  } else if (activeView === 'register') {
    return <AuthForm isRegister={true} />;
  } else if (activeView === 'chat' && isLoggedIn) {
    return <ChatInterface />;
  } else {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }
}

export default App;