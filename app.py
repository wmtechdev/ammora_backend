"""
Main Flask Application
Read-only backend API for AI chat functionality
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv

from services.firebase_service import FirebaseService
from services.llm_service import LLMService
from services.prompt_builder import PromptBuilder

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Initialize services
firebase_service = FirebaseService()
llm_service = LLMService()
prompt_builder = PromptBuilder()

# Get API key from environment
API_KEY ="321"

def validate_api_key():
    """Validate API key from request headers"""
    api_key = request.headers.get('X-API-Key')
    if not api_key or api_key != API_KEY:
        return False
    return True

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'AI Chat Backend API',
        'version': '1.0.0'
    }), 200

@app.route('/api/user/<user_id>', methods=['GET'])
def get_user(user_id):
    """Get user data"""
    try:
        user_data = firebase_service.get_user(user_id)
        if not user_data:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        return jsonify({
            'success': True,
            'data': {
                'name': user_data.get('name'),
                'age': user_data.get('age'),
                'email': user_data.get('email'),
                'created_at': str(user_data.get('created_at', ''))
            }
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/preferences/<user_id>', methods=['GET'])
def get_preferences(user_id):
    """Get user preferences"""
    try:
        preferences = firebase_service.get_user_preferences(user_id)
        if not preferences:
            return jsonify({'success': False, 'error': 'Preferences not found'}), 404
        
        return jsonify({
            'success': True,
            'data': {
                'support_type': preferences.get('supportType') or preferences.get('support_type'),
                'conversation_tone': preferences.get('conversationTone') or preferences.get('conversation_tone'),
                'relationship_status': preferences.get('relationshipStatus') or preferences.get('relationship_status'),
                'topics_to_avoid': preferences.get('topicsToAvoid') or preferences.get('topics_to_avoid', [])
            }
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/messages/<session_id>', methods=['GET'])
def get_messages(session_id):
    """Get message history for a session"""
    try:
        messages = firebase_service.get_session_messages(session_id, limit=50)
        
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                'message': msg.get('message'),
                'type': msg.get('type'),
                'timestamp': str(msg.get('timestamp', ''))
            })
        
        return jsonify({
            'success': True,
            'data': {
                'messages': formatted_messages,
                'count': len(formatted_messages)
            }
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Main chat endpoint
    
    Request Body:
        {
            "user_id": "string" (required),
            "message": "string" (required),
            "chat_session_id": "string" (optional, for saving messages)
        }
    
    Response:
        {
            "success": true,
            "data": {
                "user_id": "string",
                "message": "AI response text"
            }
        }
    """
    try:
        # Validate API key
        if not validate_api_key():
            return jsonify({
                'success': False,
                'error': 'Invalid or missing API key'
            }), 401
        
        print("\n" + "="*60)
        print("New chat request received")
        
        # Get request data
        data = request.json
        user_id = data.get('user_id')
        chat_session_id = data.get('chat_session_id')  # Optional
        user_message = data.get('message')
        
        print(f" User ID: {user_id}")
        print(f" Session ID: {chat_session_id}")
        print(f" Message: {user_message}")
        
        # Validate input
        if not user_id or not user_message:
            print(" Missing required fields")
            return jsonify({
                'success': False,
                'error': 'user_id and message are required'
            }), 400
        
        # Get user data
        print(" Fetching user data from Firebase...")
        user_data = firebase_service.get_user(user_id)
        
        if not user_data:
            print(f" User not found: {user_id}")
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        print(f" User data retrieved: {user_data.get('name')}")
        
        #  Get user preferences
        print("Fetching user preferences...")
        preferences = firebase_service.get_user_preferences(user_id)
        
        if not preferences:
            print(" No preferences found, using defaults")
            preferences = {
                'conversation_tone': 'Gentle',
                'support_type': 'Supportive Friend',
                'relationship_status': 'Unknown',
                'topics_to_avoid': ''
            }
        else:
            print(f"✅ Preferences retrieved: {preferences.get('supportType') or preferences.get('support_type')}")
            print(f"   📋 Full preferences data: {preferences}")
        
        #  Get conversation history (last 10 messages for this user)
        print(" Fetching conversation history...")
        messages = firebase_service.get_user_messages(user_id, limit=10)
        print(f"Retrieved {len(messages)} messages from history")
        
        
        print(" Building AI prompt...")
        system_prompt = prompt_builder.build_system_prompt(user_data, preferences)
        conversation_history = prompt_builder.format_conversation_history(messages)
        print("✅ Prompt built successfully")
        
        # DEBUG: Print the full prompt and context
        print("\n" + "="*60)
        print("🔍 DEBUG: FULL SYSTEM PROMPT")
        print("="*60)
        print(system_prompt)
        print("="*60)
        print(f"📝 Conversation History: {len(conversation_history)} messages")
        for i, msg in enumerate(conversation_history[-3:]):  # Show last 3 messages
            print(f"   {i+1}. [{msg['role']}]: {msg['content'][:50]}...")
        print("="*60 + "\n")
        
        #  Get AI response
        print(" Calling Groq API...")
        ai_response = llm_service.get_ai_response(
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            user_message=user_message
        )
        print(f"AI response received ({len(ai_response)} chars)")
        
        #  Save user message to Firebase
        print(" Saving user message to Firebase...")
        user_msg_id = firebase_service.save_message(
            user_id=user_id,
            chat_session_id=chat_session_id,
            message_text=user_message,
            message_type='user'
        )
        if user_msg_id:
            print(f" User message saved (ID: {user_msg_id})")
        else:
            print("  Failed to save user message")
        
        # Save AI response to Firebase
        print(" Saving AI response to Firebase...")
        ai_msg_id = firebase_service.save_message(
            user_id=user_id,
            chat_session_id=chat_session_id,
            message_text=ai_response,
            message_type='ai'
        )
        if ai_msg_id:
            print(f" AI response saved (ID: {ai_msg_id})")
        else:
            print("  Failed to save AI response")
        
        #  Update session metadata
        print(" Updating session metadata...")
        firebase_service.update_session_metadata(chat_session_id)
        print(" Session metadata updated")
        
        print("="*60 + "\n")
        
        # Return simplified response
        return jsonify({
            'success': True,
            'data': {
                'user_id': user_id,
                'message': ai_response
            }
        }), 200
        
    except Exception as e:
        print("\n" + "="*60)
        print(f" ERROR: {type(e).__name__}")
        print(f" Message: {str(e)}")
        import traceback
        traceback.print_exc()
        print("="*60 + "\n")
        
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.errorhandler(404)
def not_found(error):
    
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    print(" Starting AI Chat Backend API...")
    print(f"Server running at: http://localhost:{port}")
    print(" API Endpoint: POST /api/chat")
    print(" Health Check: GET /health")
    app.run(debug=True, host='0.0.0.0', port=port)
