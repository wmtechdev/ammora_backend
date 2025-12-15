"""
Firebase Service Module
Handles all Firebase Firestore read operations
"""

from config.firebase_config import db

class FirebaseService:
   
    
    @staticmethod
    def get_user(user_id):
        """
        Get user from users_mimik collection
        """
        try:
            user_doc = db.collection('users').document(user_id).get()
            
            if not user_doc.exists:
                return None
            
            return user_doc.to_dict()
        except Exception as e:
            print(f"Error fetching user {user_id}: {str(e)}")
            return None

    @staticmethod
    def get_thread_id(user_id):
        """
        Get the active OpenAI Thread ID for a user
        """
        try:
            doc = db.collection('users').document(user_id).collection('metadata').document('openai_thread').get()
            if doc.exists:
                return doc.to_dict().get('thread_id')
            return None
        except Exception as e:
            print(f"Error fetching thread ID for {user_id}: {str(e)}")
            return None

    @staticmethod
    def save_thread_id(user_id, thread_id):
        """
        Save the OpenAI Thread ID for a user and initialize msg_count
        """
        try:
            from datetime import datetime
            db.collection('users').document(user_id).collection('metadata').document('openai_thread').set({
                'thread_id': thread_id,
                'msg_count': 0,
                'updated_at': datetime.now()
            }, merge=True)
            return True
        except Exception as e:
            print(f"Error saving thread ID for {user_id}: {str(e)}")
            return False

    @staticmethod
    def get_thread_data(user_id):
        """
        Get thread_id and current message count
        """
        try:
            doc = db.collection('users').document(user_id).collection('metadata').document('openai_thread').get()
            if doc.exists:
                data = doc.to_dict()
                return {
                    'thread_id': data.get('thread_id'),
                    'msg_count': data.get('msg_count', 0)
                }
            return None
        except Exception:
            return None

    @staticmethod
    def increment_thread_count(user_id):
        """
        Increment the message count for the user's thread
        """
        try:
            from firebase_admin import firestore
            ref = db.collection('users').document(user_id).collection('metadata').document('openai_thread')
            ref.update({'msg_count': firestore.Increment(1)})
        except Exception as e:
            print(f"Error incrementing thread count: {e}")
    
    @staticmethod
    def get_user_preferences(user_id):
        """
        Get user preferences from subcollection under users_mimik/{user_id}/preferences
        """
        try:
            # Get preferences from subcollection
            prefs_docs = list(db.collection('users').document(user_id).collection('preferences').limit(1).stream())
            
            if prefs_docs:
                return prefs_docs[0].to_dict()
            
            return None
        except Exception as e:
            print(f"Error fetching preferences for user {user_id}: {str(e)}")
            return None
    
    @staticmethod
    def get_user_messages(user_id, limit=10):
        """
        Get last N messages for a user (filtered by user_id)
        """
        try:
            # Query messages for this user
            messages_query = db.collection('messages')\
                .where('userId', '==', user_id)\
                .stream()
            
            # Collect all messages
            messages = []
            for msg_doc in messages_query:
                msg_data = msg_doc.to_dict()
                messages.append({
                    'type': msg_data.get('type'),
                    'message': msg_data.get('text'),   # FIX
                    'timestamp': msg_data.get('timestamp')
                })
            
            # Sort by timestamp (oldest first)
            messages.sort(key=lambda x: x.get('timestamp') or 0)
            
            # Return last N messages
            return messages[-limit:] if len(messages) > limit else messages
            
        except Exception as e:
            print(f"Error fetching messages for user {user_id}: {str(e)}")
            return []
    
    @staticmethod
    def get_chat_session(session_id):
      
        try:
            session_doc = db.collection('chat_sessions').document(session_id).get()
            
            if not session_doc.exists:
                return None
            
            return session_doc.to_dict()
        except Exception as e:
            print(f"Error fetching session {session_id}: {str(e)}")
            return None
    
    @staticmethod
    def save_message(user_id, chat_session_id, message_text, message_type):
       
        try:
            from datetime import datetime
            
            message_data = {
                'userId': user_id,
                'chatSessionId': chat_session_id,
                'text': message_text,
                'type': message_type,
                'timestamp': datetime.now(),
                'isTyping': False,
                'metadata': {}
            }
            
            # Add message to collection
            doc_ref = db.collection('messages').add(message_data)
            message_id = doc_ref[1].id
            
            # Update message with its own ID
            db.collection('messages').document(message_id).update({'id': message_id})
            
            return message_id
            
        except Exception as e:
            print(f"Error saving message: {str(e)}")
            return None
    
    @staticmethod
    def update_session_metadata(chat_session_id):
      
        try:
            from datetime import datetime
            
            # Get current message count
            messages = list(db.collection('messages').where('chatSessionId', '==', chat_session_id).stream())
            message_count = len(messages)
            
            # Update session
            # db.collection('chat_sessions').document(chat_session_id).update({
            #     'last_message_at': datetime.now(),
            #     'updated_at': datetime.now(),
            #     'message_count': message_count
            # })
            
        except Exception as e:
            print(f"Error updating session metadata: {str(e)}")

