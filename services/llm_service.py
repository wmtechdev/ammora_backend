import os
import time
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class LLMService:
    """Service for LLM interactions using OpenAI Assistants API (Threads)"""

    def __init__(self):
        """Initialize OpenAI client and ensure Assistant exists"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        self.client = OpenAI(api_key=api_key)
        self.assistant_id = os.getenv("OPENAI_ASSISTANT_ID")
        self.model = "gpt-4-turbo-preview" # Use a model that supports tools/threads well
        
        # If no assistant ID is set, create a basic one (or handle error)
        if not self.assistant_id:
            print("⚠️ No OPENAI_ASSISTANT_ID found. Creating a new Assistant...")
            assistant = self.client.beta.assistants.create(
                name="Ammora Chatbot",
                instructions="You are a supportive AI companion. Use the context provided in the thread.",
                model=self.model
            )
            self.assistant_id = assistant.id
            print(f"✅ Created new Assistant: {self.assistant_id}")
            print("❗ IMPORTANT: Add create OPENAI_ASSISTANT_ID=" + self.assistant_id + " to your .env file to persist this.")
            
    def create_thread(self):
        """Create a new empty thread"""
        thread = self.client.beta.threads.create()
        return thread.id

    def add_message(self, thread_id, content, role="user"):
        """Add a message to the thread"""
        try:
            self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role=role,
                content=content
            )
        except Exception as e:
            print(f"Error adding message to thread {thread_id}: {e}")
            raise e

    def get_ai_response(self, user_message, thread_id=None, system_prompt=None):
        """
        Main method to interact with AI.
        - If thread_id is None, creates a NEW thread.
        - If system_prompt is provided (Event Trigger), it is added as a MESSAGE to the thread context.
        - Adds user message.
        - Runs assistant (with truncation).
        """
        try:
            # 1. Manage Thread
            current_thread_id = thread_id
            
            if not current_thread_id:
                print("🧵 Creating new Empty Thread...")
                current_thread_id = self.create_thread()
                # If it's a new thread, we likely have a system_prompt to inject immediately
            
            # 2. Inject Context (If triggered by App Logic)
            if system_prompt:
                print(" 💉 Injecting Persistent Context Message...")
                context_msg = f"SYSTEM_CONTEXT: The following are the user's confirmed preferences. Please allow them to guide your personality dynamics:\n\n{system_prompt}"
                self.add_message(current_thread_id, context_msg)
            
            # 3. Add User Message
            self.add_message(current_thread_id, user_message)

            # 4. Run Assistant
            print(f"🏃 Starting Run on Thread {current_thread_id}...")
            
            # We NO LONGER use additional_instructions for preferences.
            # They are now in the thread history.
            
            run = self.client.beta.threads.runs.create(
                thread_id=current_thread_id,
                assistant_id=self.assistant_id,
                # Truncation Strategy: Keep last 50 messages.
                # Since we re-inject context when hitting 50, this is safe.
                truncation_strategy={
                    "type": "last_messages",
                    "last_messages": 50
                }
            )

            # 5. Poll for Completion
            while True:
                time.sleep(1) # Wait 1s between checks
                run_status = self.client.beta.threads.runs.retrieve(
                    thread_id=current_thread_id,
                    run_id=run.id
                )

                if run_status.status == 'completed':
                    break
                elif run_status.status in ['failed', 'cancelled', 'expired']:
                    raise Exception(f"Run failed with status: {run_status.status}")

            # 6. Retrieve Messages
            messages = self.client.beta.threads.messages.list(
                thread_id=current_thread_id
            )
            
            # Get the latest message from AI
            latest_message = messages.data[0]

            # Extract text
            if latest_message.role == "assistant":
                response_text = ""
                for content in latest_message.content:
                    if hasattr(content, 'text'):
                        response_text += content.text.value
                return response_text, current_thread_id
            else:
                return "Error: No response from AI", current_thread_id
            
        except Exception as e:
            print(f"Error in LLM Service: {str(e)}")
            raise Exception(f"Failed to get AI response: {str(e)}")
