import json
import os
from datetime import datetime
from typing import List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import openai
from collections import defaultdict, deque
from dotenv import load_dotenv


class NPCMood(Enum):
    NEUTRAL = "neutral"
    FRIENDLY = "friendly"
    ANGRY = "angry"
    HELPFUL = "helpful"
    CONFUSED = "confused"

@dataclass
class PlayerMessage:
    player_id: int
    text: str
    timestamp: datetime
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlayerMessage':
        return cls(
            player_id=data['player_id'],
            text=data['text'],
            timestamp=datetime.fromisoformat(data['timestamp'])
        )

@dataclass
class NPCState:
    mood: NPCMood = NPCMood.NEUTRAL
    conversation_history: deque = None
    
    def __post_init__(self):
        if self.conversation_history is None:
            self.conversation_history = deque(maxlen=3)

class NPCChatSystem:
    def __init__(self, api_key: str = None):
        """
        Initialize the NPC Chat System
        
        Args:
            api_key: OpenAI API key. If None, will try to get from environment
        """
        if api_key:
            openai.api_key = api_key
        else:
            #openai.api_key = os.getenv('OPENAI_API_KEY')
            load_dotenv()
            
        if not openai.api_key:
            raise ValueError("OpenAI API key not found. Please set OPENAI_API_KEY environment variable or pass it directly.")
        
        # Track NPC state per player
        self.player_states: Dict[int, NPCState] = defaultdict(NPCState)
        
        # Store all processed interactions for logging
        self.interaction_logs: List[Dict[str, Any]] = []
        
    def analyze_mood_from_message(self, message_text: str, current_mood: NPCMood) -> NPCMood:
        """
        Analyze the player's message to determine NPC mood change
        """
        message_lower = message_text.lower()
        
        # Mood triggers
        friendly_triggers = ['hello', 'hi', 'thank you', 'thanks', 'please', 'help', 'quest', 'village', 'nice']
        angry_triggers = ['stupid', 'useless', 'idiot', 'hate', 'suck', 'terrible', 'awful', 'damn']
        helpful_triggers = ['where', 'how', 'what', 'quest', 'direction', 'guide', 'help']
        
        # Check for mood changes
        if any(trigger in message_lower for trigger in angry_triggers):
            return NPCMood.ANGRY
        elif any(trigger in message_lower for trigger in helpful_triggers):
            return NPCMood.HELPFUL
        elif any(trigger in message_lower for trigger in friendly_triggers):
            return NPCMood.FRIENDLY
        else:
            # Gradually return to neutral if no strong triggers
            if current_mood == NPCMood.ANGRY:
                return NPCMood.NEUTRAL
            return current_mood
    
    def build_conversation_context(self, player_id: int, current_message: str) -> str:
        """
        Build conversation context from the last 3 messages
        """
        state = self.player_states[player_id]
        context_parts = []
        
        # Add conversation history
        if state.conversation_history:
            context_parts.append("Recent conversation:")
            for i, msg in enumerate(state.conversation_history, 1):
                context_parts.append(f"{i}. Player: {msg}")
        
        # Add current message
        context_parts.append(f"Current message: {current_message}")
        
        return "\n".join(context_parts)
    
    def generate_npc_response(self, player_id: int, message_text: str) -> str:
        """
        Generate NPC response using OpenAI GPT API
        """
        state = self.player_states[player_id]
        context = self.build_conversation_context(player_id, message_text)
        
        # Create mood-specific system prompt
        mood_descriptions = {
            NPCMood.NEUTRAL: "You are a neutral, balanced NPC. Be polite but not overly enthusiastic.",
            NPCMood.FRIENDLY: "You are a friendly, welcoming NPC. Be warm and enthusiastic in your responses.",
            NPCMood.ANGRY: "You are an irritated NPC. Be curt and slightly hostile, but still helpful.",
            NPCMood.HELPFUL: "You are an eager-to-help NPC. Be informative and offer assistance.",
            NPCMood.CONFUSED: "You are a confused NPC. Be uncertain and ask clarifying questions."
        }
        
        system_prompt = f"""You are a medieval fantasy NPC (Non-Player Character) in a village. 
{mood_descriptions[state.mood]}

Keep responses short (1-2 sentences max). You can:
- Give directions around the village
- Offer simple quests or tasks
- Share basic village lore
- React to the player's tone

Current mood: {state.mood.value}
"""
        
        try:
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context}
                ],
                max_tokens=100,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
            return f"*The NPC seems distracted and doesn't respond clearly* (Error: {str(e)})"
    
    def process_message(self, message: PlayerMessage) -> Dict[str, Any]:
        """
        Process a single player message and generate NPC response
        """
        player_id = message.player_id
        state = self.player_states[player_id]
        
        # Update mood based on message content
        new_mood = self.analyze_mood_from_message(message.text, state.mood)
        state.mood = new_mood
        
        # Get conversation history for logging
        conversation_state = list(state.conversation_history)
        
        # Generate NPC response
        npc_reply = self.generate_npc_response(player_id, message.text)
        
        # Update conversation history
        state.conversation_history.append(message.text)
        
        # Create interaction log
        interaction = {
            'player_id': player_id,
            'message_text': message.text,
            'npc_reply': npc_reply,
            'conversation_state': conversation_state,
            'npc_mood': state.mood.value,
            'timestamp': message.timestamp.isoformat()
        }
        
        self.interaction_logs.append(interaction)
        return interaction
    
    def process_messages_from_file(self, filename: str) -> None:
        """
        Process all messages from a JSON file in chronological order
        """
        # Load messages from file
        with open(filename, 'r') as f:
            messages_data = json.load(f)
        
        # Convert to PlayerMessage objects
        messages = [PlayerMessage.from_dict(msg_data) for msg_data in messages_data]
        
        # Sort by timestamp to ensure chronological processing
        messages.sort(key=lambda x: x.timestamp)
        
        print(f"Processing {len(messages)} messages in chronological order...")
        print("-" * 80)
        
        # Process each message
        for i, message in enumerate(messages, 1):
            print(f"[{i}/{len(messages)}] Processing message from Player {message.player_id}")
            interaction = self.process_message(message)
            self.log_interaction(interaction)
            print()
    
    def log_interaction(self, interaction: Dict[str, Any]) -> None:
        """
        Log a single interaction to console
        """
        print(f"Player ID: {interaction['player_id']}")
        print(f"Message: {interaction['message_text']}")
        print(f"NPC Reply: {interaction['npc_reply']}")
        print(f"Conversation State: {interaction['conversation_state']}")
        print(f"NPC Mood: {interaction['npc_mood']}")
        print(f"Timestamp: {interaction['timestamp']}")
    
    def save_logs_to_file(self, filename: str = "npc_chat_logs.json") -> None:
        """
        Save all interaction logs to a JSON file
        """
        with open(filename, 'w') as f:
            json.dump(self.interaction_logs, f, indent=2)
        print(f"Logs saved to {filename}")
    
    def print_summary(self) -> None:
        """
        Print a summary of all interactions
        """
        print("\n" + "="*80)
        print("INTERACTION SUMMARY")
        print("="*80)
        
        total_messages = len(self.interaction_logs)
        unique_players = len(self.player_states)
        
        print(f"Total messages processed: {total_messages}")
        print(f"Unique players: {unique_players}")
        
        # Mood distribution
        mood_counts = defaultdict(int)
        for log in self.interaction_logs:
            mood_counts[log['npc_mood']] += 1
        
        print("\nFinal NPC mood distribution:")
        for mood, count in mood_counts.items():
            print(f"  {mood}: {count} interactions")
        
        print("\nPlayer conversation lengths:")
        for player_id, state in self.player_states.items():
            print(f"  Player {player_id}: {len(state.conversation_history)} messages in history")

def main():
    """
    Main function to run the NPC Chat System
    """
    print("🤖 AI-Powered NPC Chat System")
    print("=" * 50)
    
    # Check if players.json exists, create sample if not
    if not os.path.exists('players.json'):
        print("players.json not found. ")
    
    try:
        # Initialize the NPC chat system
        # Make sure to set your OPENAI_API_KEY environment variable
      npc_system = NPCChatSystem('Enter Your API Key Here')
        
        # Process all messages from the JSON file
        npc_system.process_messages_from_file('players.json')
        
        # Save logs to file
        npc_system.save_logs_to_file()
        
        # Print summary
        npc_system.print_summary()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()

        
