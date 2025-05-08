# Flapple/ai/llm_interface.py

import json
import requests
from typing import Dict, Any, Optional, List

class LLMInterface:
    def __init__(self, model_name="gemma3:12b-it-qat", api_url="http://localhost:11434/api/generate"):
        """
        Initialize the LLM interface for communicating with Ollama.
        
        Args:
            model_name: The name of the model to use in Ollama
            api_url: The URL for Ollama's API endpoint
        """
        self.model_name = model_name
        self.api_url = api_url
    
    def generate_response(self, prompt: str, temperature: float = 0.7, max_tokens: int = 1000) -> Optional[str]:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: The prompt to send to the LLM
            temperature: Controls randomness (lower = more deterministic)
            max_tokens: Maximum tokens to generate
            
        Returns:
            The LLM's response as a string, or None if there was an error
        """
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            response = requests.post(self.api_url, json=payload)
            response.raise_for_status()  # Raise exception for HTTP errors
            
            # Ollama returns streaming responses, need to accumulate them
            result = ""
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    if 'response' in data:
                        result += data['response']
            
            return result
        
        except Exception as e:
            print(f"Error communicating with LLM: {e}")
            return None
    
    def get_move_decision(self, battle_state: Dict[str, Any]) -> Optional[str]:
        """
        Query the LLM for a move decision based on the battle state.
        
        Args:
            battle_state: Dictionary containing the current battle state
            
        Returns:
            A string representing the chosen move ID, or None if no valid move was returned
        """
        # Create a prompt that explains the battle situation and available moves
        prompt = self._create_battle_prompt(battle_state)
        
        # Get response from LLM
        response = self.generate_response(prompt)
        
        # Extract the move from the response
        if response:
            move = self._parse_move_from_response(response, battle_state)
            return move
        
        return None
    
    def _create_battle_prompt(self, battle_state: Dict[str, Any]) -> str:
        """Create a detailed prompt with battle history and strategic information."""
        active_pokemon = battle_state.get("active_pokemon", {})
        opponent_active = battle_state.get("opponent_active", {})
        available_moves = active_pokemon.get("moves", [])
        battle_history = battle_state.get("battle_history", {"turns": 0, "last_moves": [], "opponent_last_moves": []})
        
        # Create move history string
        move_history_str = ""
        for move in battle_history.get("last_moves", []):
            move_history_str += f"Turn {move['turn']}: {move['pokemon']} used {move['move']}\n"
        
        # Create opponent move history string
        opponent_history_str = ""
        for move in battle_history.get("opponent_last_moves", []):
            opponent_history_str += f"Turn {move['turn']}: {move['pokemon']} used {move['move']}\n"
        
        # Format team information
        team_status_str = ""
        for pokemon, status in battle_state.get("team_status", {}).items():
            hp_percent = status.get("hp", 0) * 100 if status.get("hp") is not None else "unknown"
            hp_display = f"{hp_percent:.1f}%" if hp_percent != "unknown" else "unknown"
            team_status_str += f"- {pokemon}: HP {hp_display}, Status: {status.get('status', 'None')}\n"
        
        opponent_team_str = ""
        for pokemon, status in battle_state.get("opponent_team", {}).items():
            hp_percent = status.get("hp", 0) * 100 if status.get("hp") is not None else "unknown"
            hp_display = f"{hp_percent:.1f}%" if hp_percent != "unknown" else "unknown"
            opponent_team_str += f"- {pokemon}: HP {hp_display}, Status: {status.get('status', 'None')}\n"
        
        prompt = f"""
    You are a Pokemon battle expert AI. Analyze this battle situation carefully and choose the best move.

    BATTLE TURN: {battle_history.get('turns', 0)}

    YOUR ACTIVE POKEMON:
    - Name: {active_pokemon.get('name')}
    - HP: {active_pokemon.get('hp', 0) * 100:.1f}%
    - Types: {', '.join(str(type_) for type_ in active_pokemon.get('types', []))}
    - Status: {active_pokemon.get('status', 'None')}

    OPPONENT'S ACTIVE POKEMON:
    - Name: {opponent_active.get('name')}
    - HP: {opponent_active.get('hp', 0) * 100:.1f}%
    - Types: {', '.join(str(type_) for type_ in opponent_active.get('types', []))}
    - Status: {opponent_active.get('status', 'None')}

    TYPE MATCHUP ANALYSIS:
    Your {active_pokemon.get('name')} ({', '.join(str(type_) for type_ in active_pokemon.get('types', []))}) vs 
    opponent's {opponent_active.get('name')} ({', '.join(str(type_) for type_ in opponent_active.get('types', []))})

    YOUR TEAM:
    {team_status_str if team_status_str else "No additional Pokemon information."}

    OPPONENT'S TEAM (Known):
    {opponent_team_str if opponent_team_str else "No additional opponent Pokemon information."}

    AVAILABLE MOVES:
    {', '.join(available_moves)}

    BATTLE CONDITIONS:
    - Weather: {battle_state.get('weather', 'None')}
    - Field Effects: {', '.join(battle_state.get('field', []))}

    YOUR RECENT MOVES:
    {move_history_str if move_history_str else "No moves yet."}

    OPPONENT'S RECENT MOVES:
    {opponent_history_str if opponent_history_str else "No moves observed yet."}

    Based on this situation, which move should I use? Consider:
    1. Type effectiveness against the opponent
    2. Current HP of both Pokemon
    3. Battle conditions and weather
    4. Potential opponent strategies based on their past moves
    5. Team synergy and switching options if necessary

    IMPORTANT: Respond with ONLY the exact move name from the available moves list.
    """
        return prompt

    
    def _parse_move_from_response(self, response: str, battle_state: Dict[str, Any]) -> Optional[str]:
        """Extract a valid move ID from the LLM's response with improved parsing."""
        # Clean up the response
        response = response.strip().lower()
        
        # Get available moves from battle state
        available_moves = battle_state.get("active_pokemon", {}).get("moves", [])
        available_moves_lower = [move.lower() for move in available_moves]
        
        # First try: exact match
        if response in available_moves_lower:
            index = available_moves_lower.index(response)
            return available_moves[index]
        
        # Second try: check if response contains any of the available moves as distinct words
        for i, move in enumerate(available_moves_lower):
            # Check if move is a whole word in the response
            if f" {move} " in f" {response} " or response.startswith(f"{move} ") or response.endswith(f" {move}") or response == move:
                return available_moves[i]
        
        # Third try: check word by word if any matches a move
        response_words = response.split()
        for word in response_words:
            if word in available_moves_lower:
                index = available_moves_lower.index(word)
                return available_moves[index]
        
        # No valid move found
        return None