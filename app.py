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
                'topics_to_avoid': preferences.get('topicsToAvoid') or preferences.get('topics_to_avoid', []),
                'ai_communication': preferences.get('aiCommunication') or preferences.get('ai_communication'),
                'ai_honesty': preferences.get('aiHonesty') or preferences.get('ai_honesty'),
                'ai_tools_familiarity': preferences.get('aiToolsFamiliarity') or preferences.get('ai_tools_familiarity'),
                'daily_routine': preferences.get('dailyRoutine') or preferences.get('daily_routine'),
                'biggest_challenge': preferences.get('biggestChallenge') or preferences.get('biggest_challenge'),
                'stress_response': preferences.get('stressResponse') or preferences.get('stress_response'),
                'interested_in': preferences.get('interestedIn') or preferences.get('interested_in'),
                'sexual_orientation': preferences.get('sexualOrientation') or preferences.get('sexual_orientation'),
                'time_dedication': preferences.get('timeDedication') or preferences.get('time_dedication')
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
        
        # print(f" User ID: {user_id}")
        # print(f" Session ID: {chat_session_id}")
        # print(f" Message: {user_message}")
        
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
        
        # print(f" User data retrieved: {user_data.get('name')}")
        
        #  Get user preferences
        # Preferences will be fetched lazily if needed
        preferences = {}
        
        #  Get conversation history
        #  (New Thread Architecture: We DO NOT fetch history for the AI, only for the "Mirror" if needed)
        
        # Check for existing Thread ID and Message Count
        print(" Fetching OpenAI Thread Data...")
        thread_data = firebase_service.get_thread_data(user_id)
        
        thread_id = None
        msg_count = 0
        
        if thread_data:
            thread_id = thread_data.get('thread_id')
            msg_count = thread_data.get('msg_count', 0)

        # LOGIC: When to inject System Context?
        # 1. Start of Thread (thread_id is None)
        # 2. Limit Hit (msg_count > 0 and multiple of 50)
        
        should_inject_context = False
        if not thread_id:
             print(" No active thread found. Context injection REQUIRED.")
             should_inject_context = True
        elif msg_count > 0 and msg_count % 50 == 0:
             print(f" Message limit hit ({msg_count}). Context refresh REQUIRED.")
             should_inject_context = True
        else:
             print(f" Context active. Message count: {msg_count}")
        
        system_prompt = None
        if should_inject_context:
            print(" Fetching user preferences (Context Refresh)...")
            preferences = firebase_service.get_user_preferences(user_id)
            if not preferences:
                 preferences = {
                    'support_type': 'Supportive Friend',
                    'relationship_status': 'Unknown',
                    'topics_to_avoid': ''
                 }
            print(f"✅ Preferences retrieved: {preferences.get('supportType')}")
            
            print(" Building System Prompt (Context)...")
            system_prompt = prompt_builder.build_system_prompt(user_data, preferences)

        #  Get AI response (using Threads)
        print(" Calling OpenAI Assistant (Threads)...")
        
        try:
            ai_response, active_thread_id = llm_service.get_ai_response(
                user_message=user_message,
                thread_id=thread_id,
                system_prompt=system_prompt 
            )
        except Exception as e:
            # Fallback for invalid thread
            print(f"⚠️ Run failed. Retrying with NEW thread...")
            # If run failed, force new thread creation which implicitly injects context
            system_prompt = prompt_builder.build_system_prompt(user_data, preferences)
            ai_response, active_thread_id = llm_service.get_ai_response(
                user_message=user_message,
                thread_id=None,
                system_prompt=system_prompt
            )

        print(f"AI response received ({len(ai_response)} chars)")
        
        # 3. BACKGROUND TASK: Save to Firestore (Fire and Forget)
        def save_to_firestore_background(uid, session_id, user_text, ai_text, thread_id_val, active_thread):
            try:
                # Save Thread ID if changed (New Thread Created)
                # save_thread_id will initialize msg_count to 0
                if active_thread != thread_id_val:
                    print(f" [Background] Saving new Thread ID: {active_thread}")
                    firebase_service.save_thread_id(uid, active_thread)
                else:
                    # If same thread, increment the count
                    # We increment once per interaction (User + AI turn)
                    firebase_service.increment_thread_count(uid)
                
                # Save User Message
                firebase_service.save_message(uid, session_id, user_text, 'user')
                print(" [Background] User message saved")
                
                # Save AI Message
                firebase_service.save_message(uid, session_id, ai_text, 'ai')
                print(" [Background] AI message saved")
                
                # Update Session Metadata
                firebase_service.update_session_metadata(session_id)
            except Exception as bg_e:
                print(f" [Background] Error saving to Firestore: {bg_e}")

        # Start the background thread
        import threading
        save_thread = threading.Thread(
            target=save_to_firestore_background,
            args=(user_id, chat_session_id, user_message, ai_response, thread_id, active_thread_id)
        )
        save_thread.start()
        print(" Background save task started")
        
        # 4. Return simplified response INSTANTLY
        return jsonify({
            'success': True,
            'data': {
                'user_id': user_id,
                'user_name': user_data.get('name'),
                'message': ai_response,
                'preferences': preferences,
                'thread_id': active_thread_id 
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
