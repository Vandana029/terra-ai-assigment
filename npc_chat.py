#from langchain.llms import OpenAI
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationSummaryBufferMemory
from langchain.memory import ConversationBufferWindowMemory
from langchain.chains import ConversationChain
from langchain.prompts import PromptTemplate
from langchain.schema import BaseMemory
import json
import os
from typing import Dict, Any, List
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from dotenv import load_dotenv


# -----------------------------
# NPC Enums and Personality
# -----------------------------

class NPCMood(Enum):
    NEUTRAL = "neutral"
    FRIENDLY = "friendly" 
    ANGRY = "angry"
    HELPFUL = "helpful"
    CONFUSED = "confused"

@dataclass
class NPCPersonality:
    name: str
    role: str
    background: str
    quirks: List[str]
    mood: NPCMood = NPCMood.NEUTRAL

# -----------------------------
# NPC System
# -----------------------------

class EnhancedNPCSystem:
    def __init__(self, api_key: str):
        self.llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.7,
            api_key=api_key,
            max_tokens=150
        )
        
        # Different NPC personalities
        self.npc_personalities = {
            "village_guard": NPCPersonality(
                name="Marcus",
                role="Village Guard",
                background="A veteran soldier who protects the village",
                quirks=["Always mentions his war stories", "Suspicious of strangers"]
            ),
            "merchant": NPCPersonality(
                name="Elena",
                role="Merchant",
                background="A traveling trader with exotic goods",
                quirks=["Always trying to make a sale", "Knows gossip from other towns"]
            ),
            "blacksmith": NPCPersonality(
                name="Thorin",
                role="Blacksmith",
                background="Master craftsman who forges weapons and tools",
                quirks=["Speaks in short sentences", "Proud of his work"]
            )
        }
        
        self.player_conversations: Dict[int, ConversationChain] = {}
        self.player_npc_assignments: Dict[int, str] = {}
        
    def get_npc_prompt_template(self, npc_key: str) -> PromptTemplate:
        npc = self.npc_personalities[npc_key]
        
        template = f"""=== GAME WORLD CONTEXT ===
You are an NPC (Non-Player Character) in "Chronicles of Aethermoor," a medieval fantasy RPG set in a bustling village at the crossroads of ancient kingdoms. This village serves as a safe haven for adventurers, traders, and travelers seeking quests, supplies, and information.

The village contains:
- Market Square (merchants, traders, gossips)
- Blacksmith Quarter (crafters, weapon smiths, armorers) 
- Guard Barracks (soldiers, captains, veterans)
- Tavern District (innkeepers, bards, locals)
- Temple Grounds (clerics, healers, wise folk)
- Mysterious ruins and ancient forests nearby

Players are adventurers who arrive seeking glory, treasure, knowledge, or simply a place to rest. They may be complete novices or seasoned heroes. Your interactions shape their journey.

=== YOUR CHARACTER ===
Name: {npc.name}
Role: {npc.role}
Background: {npc.background}
Personality Quirks: {', '.join(npc.quirks)}

Current Emotional State: {npc.mood.value}

=== MOOD-BASED BEHAVIOR GUIDE ===

When NEUTRAL:
- Be professional but not overly warm
- Give straightforward, helpful information
- Maintain character-appropriate mannerisms
- Show mild interest in the player's goals
- Example tone: "I can help with that. The blacksmith's shop is just down the cobblestone path, past the fountain."

When FRIENDLY:
- Be welcoming and enthusiastic
- Offer additional help or information
- Share personal anecdotes or local gossip
- Use warm, inviting language
- Show genuine interest in the player's journey
- Example tone: "Well hello there, friend! You look like you could use some guidance - and perhaps a good meal too!"

When HELPFUL:
- Be eager to assist and provide detailed information
- Offer practical advice and warnings
- Share useful tips about the village or surrounding areas
- Be patient with questions
- Show expertise in your field
- Example tone: "Ah, you're looking for supplies? Let me tell you exactly what you'll need and where to find the best prices..."

When ANGRY:
- Be curt and somewhat hostile, but not completely unhelpful
- Show irritation through short responses
- May mention what's bothering you
- Still provide basic information (you have a job to do)
- Use gruff or impatient language
- Example tone: "What do you want? I'm busy here... *sighs heavily* Fine, the inn is that way. Now leave me be."

When CONFUSED:
- Be uncertain and ask for clarification
- Show puzzlement about the player's request
- May ramble or give incomplete information
- Ask follow-up questions
- Show your character is trying to understand
- Example tone: "I'm not quite sure what you mean by that... Could you explain it differently? Are you talking about the old ruins or the new merchant district?"

=== ROLEPLAY GUIDELINES ===

1. **Stay in Character**: Never break the fourth wall or mention you're an AI/game mechanic
2. **Be Concise**: Keep responses to 1-2 sentences maximum (this is crucial for game flow)
3. **Show, Don't Tell**: Express mood through word choice and tone, not by stating "I am angry"
4. **Include Character Quirks**: Naturally weave in your personality traits
5. **Maintain Consistency**: Remember previous interactions with this player
6. **Provide Value**: Always give the player something useful - information, direction, quest hint, or roleplay flavor
7. **Use Medieval Fantasy Language**: Avoid modern slang, but keep it understandable

=== INTERACTION HISTORY ===
Previous conversation with this adventurer:
{{history}}

=== CURRENT INTERACTION ===
The adventurer approaches you and says: {{input}}

*{npc.name} {npc.mood.value.replace('_', ' ')} responds:*"""

        return PromptTemplate(
            input_variables=["history", "input"],
            template=template
        )
    
    def assign_npc_to_player(self, player_id: int) -> str:
        """Assign an NPC to a player (round-robin style)"""
        if player_id not in self.player_npc_assignments:
            npc_keys = list(self.npc_personalities.keys())
            npc_key = npc_keys[player_id % len(npc_keys)]
            self.player_npc_assignments[player_id] = npc_key
        
        return self.player_npc_assignments[player_id]
    
    def create_conversation_chain(self, player_id: int) -> ConversationChain:
        npc_key = self.assign_npc_to_player(player_id)
        prompt = self.get_npc_prompt_template(npc_key)
        
        memory = ConversationSummaryBufferMemory(
            llm=self.llm,
            max_token_limit=200,
            return_messages=True
        )
        
        chain = ConversationChain(
            llm=self.llm,
            prompt=prompt,
            memory=memory,
            verbose=True
        )
        
        return chain
    
    def update_npc_mood(self, player_id: int, message: str):
        """Update NPC mood based on player message"""
        npc_key = self.player_npc_assignments[player_id]
        npc = self.npc_personalities[npc_key]
        
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['stupid', 'useless', 'hate', 'idiot']):
            npc.mood = NPCMood.ANGRY
        elif any(word in message_lower for word in ['help', 'please', 'quest', 'thank']):
            npc.mood = NPCMood.HELPFUL
        elif any(word in message_lower for word in ['hello', 'hi', 'nice', 'good']):
            npc.mood = NPCMood.FRIENDLY
        elif any(word in message_lower for word in ['confused', 'lost', 'understand']):
            npc.mood = NPCMood.CONFUSED
        else:
            # Gradually return to neutral
            if npc.mood == NPCMood.ANGRY:
                npc.mood = NPCMood.NEUTRAL
    
    def process_message(self, player_id: int, message: str, timestamp: str) -> Dict[str, Any]:
        # Create conversation chain if doesn't exist
        if player_id not in self.player_conversations:
            self.player_conversations[player_id] = self.create_conversation_chain(player_id)
        
        # Update mood
        self.update_npc_mood(player_id, message)
        
        # Generate response
        chain = self.player_conversations[player_id]
        npc_key = self.player_npc_assignments[player_id]
        npc = self.npc_personalities[npc_key]
        
        # Update the prompt with current mood
        chain.prompt = self.get_npc_prompt_template(npc_key)
        
        try:
            response = chain.predict(input=message)
        except Exception as e:
            print(f"Error generating response: {e}")
            response = f"*{npc.name} seems distracted and doesn't respond clearly*"
        
        # Get conversation history (last few messages)
        conversation_history = []
        if hasattr(chain.memory, 'chat_memory') and hasattr(chain.memory.chat_memory, 'messages'):
            messages = chain.memory.chat_memory.messages[-6:]  # Last 3 exchanges
            for i in range(0, len(messages), 2):
                if i + 1 < len(messages):
                    conversation_history.append({
                        'player': messages[i].content if hasattr(messages[i], 'content') else str(messages[i]),
                        'npc': messages[i+1].content if hasattr(messages[i+1], 'content') else str(messages[i+1])
                    })
        
        return {
            'timestamp': timestamp,
            'player_id': player_id,
            'player_message': message,
            'npc_name': npc.name,
            'npc_role': npc.role,
            'npc_mood': npc.mood.value,
            'npc_response': response.strip(),
            #'conversation_history': str(chain.memory.buffer)
            'conversation_history': [
                {"player": msg.content} if msg.type == "human" else {"npc": msg.content}
                for msg in chain.memory.chat_memory.messages
            ]
        }

# -----------------------------
# Runner: process players.json
# -----------------------------
# Usage example
def main():
    # Load .env file
    load_dotenv()

    # Load API key from env
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Please set OPENAI_API_KEY in your environment or .env file")
    
    system = EnhancedNPCSystem(api_key)

    json_filename = "players.json"

    # Load players.json
    try:
        with open(json_filename, "r") as f:
            messages = json.load(f)
    except FileNotFoundError:
        print(f"Could not find {json_filename}.")
        

    # Sort by timestamp
    messages.sort(key=lambda x: datetime.fromisoformat(x["timestamp"]))

    # Create logs directory
    os.makedirs("logs", exist_ok=True)
    log_file = "logs/run.jsonl"

    print(f"Processing {len(messages)} messages...")
    print("=" * 60)
    
    try:
        with open(log_file, "w") as log:
            for i, msg in enumerate(messages, 1):
                print(f"[{i}/{len(messages)}] Processing message from Player {msg['player_id']}...")
                
                result = system.process_message(
                    player_id=msg["player_id"],
                    message=msg["text"],
                    timestamp=msg["timestamp"]
                )
                
                # Write to log file
                log.write(json.dumps(result) + "\n")
                
                # Print to console
                print(f"Player {result['player_id']}: {result['player_message']}")
                print(f"→ {result['npc_name']} ({result['npc_role']}, {result['npc_mood']}): {result['npc_response']}")
                print(f"Time: {result['timestamp']}")
                print("-" * 40)
                
        print(f"\nProcessing complete! Logs saved to {log_file}")
        
    except Exception as e:
        print(f"Error during processing: {e}")
        print("Make sure your OpenAI API key is valid and you have sufficient credits.")

    
    # Process a sample message
    # result = system.process_message(1, "Hello! Can you help me find the blacksmith?")
    # print(f"{result['npc_name']} ({result['npc_role']}): {result['response']}")
    # print(f"Mood: {result['mood']}")

if __name__ == "__main__":
    main()
