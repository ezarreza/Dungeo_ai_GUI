# game_logic.py
import re
import logging
import datetime
import subprocess
import requests
import sounddevice as sd
import numpy as np
from collections import defaultdict
from constants import MAX_CONTEXT_TOKENS, ALLTALK_API_URL
from game_data import PLAYER_CHOICES_TEMPLATE

def get_installed_models():
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, check=True
        )
        lines = result.stdout.strip().splitlines()
        models = []
        for line in lines[1:]:
            parts = line.split()
            if parts:
                models.append(parts[0])
        return models
    except Exception as e:
        logging.error(f"Error getting installed models: {e}")
        return []

def count_tokens(text):
    return max(1, int(len(text) / 3.5))

def get_current_state(player_choices):
    state = [
        f"### Current World State ###",
        f"Allies: {', '.join(player_choices['allies']) if player_choices['allies'] else 'None'}",
        f"Enemies: {', '.join(player_choices['enemies']) if player_choices['enemies'] else 'None'}",
        f"Reputation: {player_choices['reputation']}",
        f"Active Quests: {', '.join(player_choices['active_quests']) if player_choices['active_quests'] else 'None'}",
        f"Completed Quests: {', '.join(player_choices['completed_quests']) if player_choices['completed_quests'] else 'None'}",
    ]
    
    if player_choices['resources']:
        state.append("Resources:")
        for resource, amount in player_choices['resources'].items():
            state.append(f"  - {resource}: {amount}")
    
    if player_choices['factions']:
        state.append("Faction Relationships:")
        for faction, level in player_choices['factions'].items():
            state.append(f"  - {faction}: {'+' if level > 0 else ''}{level}")
    
    if player_choices['world_events']:
        state.append("Recent World Events:")
        for event in player_choices['world_events'][-3:]:
            state.append(f"  - {event}")
    
    if player_choices['consequences']:
        state.append("Recent Consequences:")
        for cons in player_choices['consequences'][-3:]:
            state.append(f"  - {cons}")
    
    return "\n".join(state)

def get_ai_response(prompt, model):
    try:
        # Add emphasis to the most important rules
        emphasis_prompt = (
            "IMPORTANT: Describe ONLY consequences. Never narrate player actions. "
            "Never offer choices. Never ask questions. Keep response under 3 sentences.\n\n"
            + prompt
        )
        
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": emphasis_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_ctx": 4096,
                    "stop": ["\n\n", "Player:", "Dungeon Master:"],
                    "min_p": 0.05,
                    "top_k": 40,
                    "repeat_penalty": 1.2
                }
            },
            timeout=90
        )
        response.raise_for_status()
        json_resp = response.json()
        return json_resp.get("response", "").strip()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error connecting to Ollama: {e}")
        return ""
    except Exception as e:
        logging.error(f"Unexpected error in get_ai_response: {e}")
        return ""

def speak(text, voice="FemaleBritishAccent_WhyLucyWhy_Voice_2.wav"):
    try:
        if not text.strip():
            return

        payload = {
            "text_input": text,
            "character_voice_gen": voice,
            "narrator_enabled": "true",
            "narrator_voice_gen": "narrator.wav",
            "text_filtering": "none",
            "output_file_name": "output",
            "autoplay": "true",
            "autoplay_volume": "0.8"
        }
        response = requests.post(ALLTALK_API_URL, data=payload, timeout=20)
        response.raise_for_status()

        if response.headers.get("Content-Type", "").startswith("audio/"):
            audio_data = np.frombuffer(response.content, dtype=np.int16)
            sd.play(audio_data, samplerate=22050)
            sd.wait()
        else:
            logging.error(f"Unexpected response content type: {response.headers.get('Content-Type')}")
    except Exception as e:
        logging.error(f"Error in speech generation: {e}")

def remove_last_ai_response(conversation):
    pos = conversation.rfind("Dungeon Master:")
    if pos == -1:
        return conversation
    return conversation[:pos].strip()

def sanitize_response(response):
    if not response:
        return "The story continues..."

    # Remove any explicit player action descriptions
    player_action_patterns = [
        r"you (?:try to|attempt to|begin to|start to|decide to) .+?\.", 
        r"you (?:successfully|carefully|quickly) .+?\.", 
        r"you (?:manage to|fail to) .+?\.",
        r"you (?:are|were) .+?\.", 
        r"you (?:have|had) .+?\.",
        r"you (?:feel|felt) .+?\.",
        r"you (?:see|saw) .+?\.",
        r"you (?:notice|noticed) .+?\.",
        r"you (?:hear|heard) .+?\."
    ]
    
    for pattern in player_action_patterns:
        response = re.sub(pattern, '', response, flags=re.IGNORECASE)

    # Remove choice prompts and labels
    structure_phrases = [
        r"a\)", r"b\)", r"c\)", r"d\)", r"e\)", 
        r"option [a-e]:", r"immediate consequence:", r"new situation:", 
        r"next challenges:", r"choices:", r"options:"
    ]
    for phrase in structure_phrases:
        pattern = re.compile(phrase, re.IGNORECASE)
        response = pattern.sub('', response)

    # Remove player direction prompts
    question_phrases = [
        r"what will you do", r"how do you respond", r"what do you do",
        r"what is your next move", r"what would you like to do",
        r"what would you like to say", r"how will you proceed",
        r"do you:", r"choose one", r"select an option", r"pick one"
    ]
    for phrase in question_phrases:
        pattern = re.compile(rf'{phrase}.*?$', re.IGNORECASE)
        response = pattern.sub('', response)

    # Clean up formatting
    response = re.sub(r'\s{2,}', ' ', response).strip()
    
    # Ensure proper sentence endings
    if response and response[-1] not in ('.', '!', '?', ':', ','):
        response += '.'
    
    # Remove state tracking placeholders
    response = re.sub(r'\[[^\]]*State Tracking[^\]]*\]', '', response)
    
    # Final cleanup
    response = re.sub(r'\.\.+', '.', response)
    response = response.replace(' ,', ',').replace(' .', '.')
    
    return response

def update_world_state(action, response, player_choices):
    new_consequence = f"After '{action}': {response.split('.')[0]}"
    if new_consequence not in player_choices['consequences']:
        player_choices['consequences'].append(new_consequence)
    
    if len(player_choices['consequences']) > 5:
        player_choices['consequences'] = player_choices['consequences'][-5:]
    
    ally_matches = re.findall(
        r'(\b[A-Z][a-z]+\b) (?:joins|helps|saves|allies with|becomes your ally|supports you)',
        response, 
        re.IGNORECASE
    )
    for ally in ally_matches:
        if ally not in player_choices['allies']:
            player_choices['allies'].append(ally)
            if ally in player_choices['enemies']:
                player_choices['enemies'].remove(ally)
    
    enemy_matches = re.findall(
        r'(\b[A-Z][a-z]+\b) (?:dies|killed|falls|perishes|becomes your enemy|turns against you|hates you)',
        response, 
        re.IGNORECASE
    )
    for enemy in enemy_matches:
        if enemy not in player_choices['enemies']:
            player_choices['enemies'].append(enemy)
        if enemy in player_choices['allies']:
            player_choices['allies'].remove(enemy)
    
    resource_matches = re.findall(
        r'(?:get|find|acquire|obtain|receive|gain|steal|take) (\d+) (\w+)',
        response, 
        re.IGNORECASE
    )
    for amount, resource in resource_matches:
        resource = resource.lower()
        player_choices['resources'].setdefault(resource, 0)
        player_choices['resources'][resource] += int(amount)
    
    lost_matches = re.findall(
        r'(?:lose|drop|spend|use|expend|give|donate|surrender) (\d+) (\w+)',
        response, 
        re.IGNORECASE
    )
    for amount, resource in lost_matches:
        resource = resource.lower()
        if resource in player_choices['resources']:
            player_choices['resources'][resource] = max(0, player_choices['resources'][resource] - int(amount))

    world_event_matches = re.findall(
        r'(?:The|A|An) (\w+ \w+) (?:is|has been|becomes) (destroyed|created|changed|revealed|altered|ruined|rebuilt)',
        response, 
        re.IGNORECASE
    )
    for location, event in world_event_matches:
        event_text = f"{location} {event}"
        if event_text not in player_choices['world_events']:
            player_choices['world_events'].append(event_text)
    
    if "quest completed" in response.lower() or "completed the quest" in response.lower():
        quest_match = re.search(r'quest ["\']?(.*?)["\']? (?:is|has been) completed', response, re.IGNORECASE)
        if quest_match:
            quest_name = quest_match.group(1)
            if quest_name in player_choices['active_quests']:
                player_choices['active_quests'].remove(quest_name)
                player_choices['completed_quests'].append(quest_name)
    
    if "new quest" in response.lower() or "quest started" in response.lower():
        quest_match = re.search(r'quest ["\']?(.*?)["\']? (?:is|has been) (?:given|started)', response, re.IGNORECASE)
        if quest_match:
            quest_name = quest_match.group(1)
            if quest_name not in player_choices['active_quests'] and quest_name not in player_choices['completed_quests']:
                player_choices['active_quests'].append(quest_name)
    
    if "reputation increases" in response.lower() or "reputation improved" in response.lower():
        player_choices['reputation'] += 1
    elif "reputation decreases" in response.lower() or "reputation damaged" in response.lower():
        player_choices['reputation'] = max(-5, player_choices['reputation'] - 1)
    
    faction_matches = re.findall(
        r'(?:The|Your) (\w+) faction (?:likes|respects|trusts|appreciates) you more', 
        response, 
        re.IGNORECASE
    )
    for faction in faction_matches:
        player_choices['factions'][faction] += 1
    
    faction_loss_matches = re.findall(
        r'(?:The|Your) (\w+) faction (?:dislikes|distrusts|hates|condemns) you more', 
        response, 
        re.IGNORECASE
    )
    for faction in faction_loss_matches:
        player_choices['factions'][faction] -= 1
        
    discovery_matches = re.findall(
        r'(?:discover|find|uncover|learn about|reveal) (?:a |an |the )?(.+?)\.', 
        response, 
        re.IGNORECASE
    )
    for discovery in discovery_matches:
        if discovery not in player_choices['discoveries']:
            player_choices['discoveries'].append(discovery)