# Flapple/showdown_integration/showdown_client.py

import asyncio # Required for asynchronous programming with poke-env
import random   # For making random choices
import os
import sys
import json
import datetime

from poke_env.player import Player, BattleOrder
#from poke_env.data import POKEDEX # For accessing Pokémon data if needed later
from poke_env.environment.battle import Battle
from poke_env import AccountConfiguration #ShowdownServerConfiguration
from poke_env import ServerConfiguration

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ai.llm_interface import LLMInterface

from typing import List, Dict, Any

# --- Configuration ---
# If you have a local Showdown server, you can use:
# LOCAL_SHOWDOWN_SERVER_URL = "localhost:8000" 
# For testing, you can use the official Smogon server:
SMOGON_SHOWDOWN_SERVER_URL = "https://localhost.psim.us"
# It's good practice to have a unique bot name. 
# You might need to register this name on the Showdown server if it requires authentication.
BOT_NAME = "WoopieAI" 
# You can leave password as None if the server doesn't require it for guest accounts,
# or if your bot name isn't registered.
BOT_PASSWORD = os.getenv("Showdown_AI_Password") # "your_bot_password_if_registered"

# --- Player Class ---
class ShowdownPlayerAI(Player):
    def __init__(self, *args, use_llm=True, model_name="gemma3:12b-it-qat", **kwargs):
        """Initialize the ShowdownPlayerAI."""
        super().__init__(*args, **kwargs)
        self.use_llm = use_llm
        
        if self.use_llm:
            self.llm_interface = LLMInterface(model_name=model_name)
        
        # Initialize battle history tracking
        self.battle_history = {}
        
        print(f"ShowdownPlayerAI initialized for user: {self.username}")
        print(f"LLM-based decision making: {'Enabled' if self.use_llm else 'Disabled'}")

    def _battle_started_callback(self, battle: Battle) -> None:
        """Called when a battle starts. Initialize battle history."""
        self.battle_history[battle.battle_tag] = {
            "turns": 0,
            "last_moves": [],
            "opponent_last_moves": []
        }
        super()._battle_started_callback(battle)

    def get_battle_state(self, battle: Battle) -> dict:
        """Extract a comprehensive battle state dictionary for LLM consumption."""
        return {
            "active_pokemon": {
                "name": battle.active_pokemon.species,
                "hp": battle.active_pokemon.current_hp_fraction,
                "moves": [move.id for move in battle.available_moves],
                "status": battle.active_pokemon.status,
                "types": battle.active_pokemon.types
            },
            "opponent_active": {
                "name": battle.opponent_active_pokemon.species,
                "hp": battle.opponent_active_pokemon.current_hp_fraction,
                "possible_moves": self._predict_opponent_moves(battle),
                "status": battle.opponent_active_pokemon.status,
                "types": battle.opponent_active_pokemon.types
            },
            "weather": battle.weather,
            "field": battle.fields,
            "team_status": self._get_team_status(battle),
            "opponent_team": self._get_opponent_team_status(battle)
        }
    
    def _update_battle_history(self, battle: Battle, move_used: str = None) -> None:
        """Update the battle history with the latest move information."""
        if battle.battle_tag not in self.battle_history:
            self.battle_history[battle.battle_tag] = {
                "turns": 0,
                "last_moves": [],
                "opponent_last_moves": []
            }
        
        # Update turn count
        self.battle_history[battle.battle_tag]["turns"] = battle.turn
        
        # Add our move to history if provided
        if move_used:
            self.battle_history[battle.battle_tag]["last_moves"].append({
                "turn": battle.turn,
                "pokemon": battle.active_pokemon.species,
                "move": move_used
            })
            # Keep only last 5 moves
            if len(self.battle_history[battle.battle_tag]["last_moves"]) > 5:
                self.battle_history[battle.battle_tag]["last_moves"].pop(0)
                
        # Try to extract opponent's last move from battle log
        self._extract_opponent_moves(battle)

    def choose_move(self, battle: Battle) -> BattleOrder:
        """Choose the best move for the current battle state."""
        print(f"\n--- {self.username}'s Turn in battle: {battle.battle_tag} ---")
        print(f"Active Pokemon: {battle.active_pokemon} (HP: {battle.active_pokemon.current_hp_fraction * 100:.2f}%)")
        print(f"Opponent's Active Pokemon: {battle.opponent_active_pokemon} (HP: {battle.opponent_active_pokemon.current_hp_fraction * 100:.2f}%)")
        
        # Get the battle state for LLM decision making
        battle_state = self.get_battle_state(battle)
        
        # Add battle history to the state
        if battle.battle_tag in self.battle_history:
            battle_state["battle_history"] = self.battle_history[battle.battle_tag]
        else:
            # Initialize battle history if it doesn't exist
            self.battle_history[battle.battle_tag] = {
                "turns": battle.turn,
                "last_moves": [],
                "opponent_last_moves": []
            }
            battle_state["battle_history"] = self.battle_history[battle.battle_tag]
        
        # If we're using the LLM for decisions and there are available moves
        if self.use_llm and battle.available_moves:
            # Get move recommendation from LLM with lower temperature for more consistent responses
            llm_move = self.llm_interface.get_move_decision(battle_state)
            
            # If LLM returned a valid move, use it
            if llm_move:
                # Find the actual move object
                for move in battle.available_moves:
                    if move.id == llm_move:
                        print(f"LLM chose move: {move.id}")
                        
                        # Update our move history
                        self._update_battle_history(battle, move.id)
                        
                        return self.create_order(move)
            
            # If we got here, LLM failed to provide a valid move
            print("LLM did not return a valid move, falling back to random selection")
        
        # Simple fallback AI: Choose a random available move
        if battle.available_moves:
            chosen_move = random.choice(battle.available_moves)
            print(f"Choosing random move: {chosen_move.id}")
            
            # Update our move history even for random moves
            self._update_battle_history(battle, chosen_move.id)
            
            return self.create_order(chosen_move)
        
        # If no moves are available, try to switch
        if battle.available_switches:
            valid_switches = [pokemon for pokemon in battle.available_switches if not pokemon.fainted]
            if valid_switches:
                chosen_switch = random.choice(valid_switches)
                print(f"No valid moves, choosing random switch: {chosen_switch.species}")
                
                # Update history for switching
                self._update_battle_history(battle, f"switch:{chosen_switch.species}")
                
                return self.create_order(chosen_switch)
            else:
                print("No valid switches available.")
        
        # If absolutely no action can be taken, pass
        print("No moves or switches available. Passing.")
        return self.choose_default_move()
    
    def _extract_opponent_moves(self, battle: Battle) -> None:
        """Extract opponent moves from battle logs."""
        # This method extracts opponent moves from battle.request_json
        # Each time a move is used, it's recorded in the request data
        if not hasattr(battle, 'request_json') or not battle.request_json:
            return
            
        try:
            # Get the last turn information from the request JSON
            if 'turns' in battle.request_json and battle.request_json['turns'] > 0:
                # Check if there's info about the opponent's last move
                if 'lastMove' in battle.request_json and battle.request_json['lastMove']:
                    last_move = battle.request_json['lastMove']
                    
                    # Only add if it's not already the last recorded move
                    existing_moves = self.battle_history[battle.battle_tag]["opponent_last_moves"]
                    if not existing_moves or existing_moves[-1].get('move') != last_move:
                        self.battle_history[battle.battle_tag]["opponent_last_moves"].append({
                            "turn": battle.turn - 1,  # It was used in the previous turn
                            "pokemon": battle.opponent_active_pokemon.species,
                            "move": last_move
                        })
                        # Keep only last 5 moves
                        if len(self.battle_history[battle.battle_tag]["opponent_last_moves"]) > 5:
                            self.battle_history[battle.battle_tag]["opponent_last_moves"].pop(0)
        except Exception as e:
            print(f"Error extracting opponent moves: {e}")

    def teampreview(self, battle: Battle):
        """
        This method is called during teampreview.
        You can implement logic here to choose your starting Pokemon.
        For now, we'll just let poke-env choose the default (first Pokemon).
        """
        print(f"Teampreview for battle: {battle.battle_tag}")
        # Example: send /team 123456 (where 123456 is the order of your pokemon)
        # For now, let poke-env handle the default order.
        # You can create a teampreview order like this:
        # return "/team " + "".join([str(i+1) for i in range(len(battle.team))]) # Default order
        pass # Let poke-env handle default teampreview order


    def _predict_opponent_moves(self, battle: Battle) -> List[str]:
        """Predict possible moves the opponent's Pokemon might have."""
        # A simple implementation that could be expanded later
        # For now, just return some common moves based on the opponent's Pokemon species
        # This would be a good place to use a database of Pokemon moves
        return ["unknown"]  # Placeholder

    def _get_team_status(self, battle: Battle) -> Dict[str, Any]:
        """Get the status of your team Pokemon."""
        team_status = {}
        for pokemon in battle.team.values():
            if not pokemon.active:  # Skip active Pokemon as it's handled separately
                team_status[pokemon.species] = {
                    "hp": pokemon.current_hp_fraction,
                    "status": pokemon.status,
                    "fainted": pokemon.fainted
                }
        return team_status

    def _get_opponent_team_status(self, battle: Battle) -> Dict[str, Any]:
        """Get the status of opponent's team Pokemon that we've seen."""
        opponent_team = {}
        for pokemon in battle.opponent_team.values():
            if not pokemon.active:  # Skip active Pokemon as it's handled separately
                opponent_team[pokemon.species] = {
                    "hp": pokemon.current_hp_fraction,
                    "status": pokemon.status,
                    "fainted": pokemon.fainted
                }
        return opponent_team

    def _battle_finished_callback(self, battle: Battle) -> None:
        """Called when a battle ends. Saves battle logs for future analysis."""
        print(f"Battle {battle.battle_tag} finished.")
        
        # Log the outcome
        if battle.won:
            print(f"Congratulations! {self.username} won the battle!")
            outcome = "win"
        elif battle.lost:
            print(f"Hard luck! {self.username} lost the battle.")
            outcome = "loss"
        else:
            print(f"The battle {battle.battle_tag} ended in a draw or was inconclusive.")
            outcome = "draw"
        
        # Extract format from battle tag (e.g., "battle-gen9randombattle-34" -> "gen9randombattle")
        battle_format = battle.battle_tag.split('-')[1] if len(battle.battle_tag.split('-')) > 1 else "unknown"
        
        # Create the log directory if it doesn't exist
        log_dir = "battle_logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Create a detailed battle log
        battle_log = {
            "battle_id": battle.battle_tag,
            "timestamp": datetime.datetime.now().isoformat(),
            "format": battle_format,  # Using the extracted format
            "player": self.username,
            "opponent": battle.opponent_username,
            "outcome": outcome,
            "turns": battle.turn,
            "history": self.battle_history.get(battle.battle_tag, {}),
            "team": {
                "active": {
                    "species": battle.active_pokemon.species if battle.active_pokemon else None,
                    "types": [str(t) for t in battle.active_pokemon.types] if battle.active_pokemon else [],
                    "moves": [m.id for m in battle.available_moves]
                },
                "pokemon": [{
                    "species": p.species,
                    "types": [str(t) for t in p.types],
                    "fainted": p.fainted,
                    "status": str(p.status)
                } for p in battle.team.values()]
            },
            "opponent_team": {
                "active": {
                    "species": battle.opponent_active_pokemon.species if battle.opponent_active_pokemon else None,
                    "types": [str(t) for t in battle.opponent_active_pokemon.types] if battle.opponent_active_pokemon else []
                },
                "pokemon": [{
                    "species": p.species,
                    "types": [str(t) for t in p.types],
                    "fainted": p.fainted,
                    "status": str(p.status)
                } for p in battle.opponent_team.values()]
            }
        }
        
        # Save as JSON for later analysis
        log_path = os.path.join(log_dir, f"{battle.battle_tag}_{self.username}_{outcome}.json")
        try:
            with open(log_path, "w") as f:
                json.dump(battle_log, f, indent=2)
            print(f"Battle log saved to {log_path}")
        except Exception as e:
            print(f"Failed to save battle log: {e}")
        
        # Clean up battle history
        if battle.battle_tag in self.battle_history:
            del self.battle_history[battle.battle_tag]


# --- Main Asynchronous Function ---
async def run_battle(player: Player, opponent_username: str = "Guest", battle_format: str = "gen9randombattle", team=None):
    """
    Starts a battle against a specified opponent or challenges a random player.

    Args:
        player: The Player instance for your bot.
        opponent_username: The username of the opponent to challenge. 
                           If "Guest", it might pick a random guest or default opponent.
                           For random battles, this often isn't directly used for matchmaking.
        battle_format: The battle format (e.g., "gen9randombattle", "gen9ou").
        team: A packed team string. If None, a random team will be used for formats like randombattle.
              For other formats, you MUST provide a team.
    """
    print(f"\nStarting battle for {player.username} in format {battle_format}...")
    
    if battle_format != "gen9randombattle" and not team:
        print(f"Warning: A team is usually required for formats other than randombattle. Attempting to proceed...")
        # You would typically load a team here for OU, Ubers, etc.
        # Example packed team (replace with your actual team generation/loading logic)
        # team = "bulbasaur|||Tackle,Growl|||||]charmander|||Scratch,Growl|||||]squirtle|||Tackle,Tail Whip|||||"
    
    # Challenge a specific user (less reliable for random matchmaking, better for specific challenges)
    # await player.send_challenges(opponent_username, n_challenges=1, to_wait=player.ChallengeChecker(1))
    
    # Or, for random battles, it's often better to just start searching for a game:
    if "randombattle" in battle_format.lower():
        print(f"Searching for a {battle_format} game...")
        if opponent_username and opponent_username != "Guest":
            print(f"Challenging {opponent_username} to a {battle_format} battle...")
            await player.send_challenges(opponent_username, n_challenges=1)
        else:
            print(f"Accepting any challenges in format {battle_format}...")
            await player.accept_challenges(None, 1)
    else:
        # For non-random formats, you'd typically challenge a specific user or have a system
        # to accept challenges. For now, let's assume you want to challenge a generic opponent.
        # This might not always work as expected without a more robust challenge handling system.
        print(f"Attempting to challenge a generic opponent in {battle_format} (this might not always find a match easily).")
        await player.challenge(opponent_username, battle_format, team=team)

    print(f"{player.username} is now in {len(player.battles)} battles.")
    
    # You can add logic here to wait for battles to finish or handle multiple battles.
    # For this example, we'll just let it run and print updates from the callbacks.
    # If you want the script to stay alive until battles are done:
    while player.battles: # or a specific battle_tag
        await asyncio.sleep(1)
        # print(f"Still in {len(player.battles)} battles...") # Optional: for debugging
    
    print("All battles for this run seem to be finished or the player is no longer in any active battles.")


async def main():
    """
    Main entry point for the poke-env client.
    """
    print("Setting up Poke-Env client...")

    # Configure the player
    account_config = AccountConfiguration(BOT_NAME, BOT_PASSWORD)

    account_config2= AccountConfiguration("changiairport", "changiairport")

    # Configure the server (use local or Smogon)
    # server_config = ShowdownServerConfiguration(LOCAL_SHOWDOWN_SERVER_URL, account_config.player_description)
    server_config = ServerConfiguration("ws://localhost:8000/showdown/websocket", "https://play.pokemonshowdown.com/action.php?")
    
    # Create our AI player instance
    # We pass server_configuration and account_configuration to the constructor
    ai_player1 = ShowdownPlayerAI(
        account_configuration=account_config,
        battle_format="gen9randombattle", # Default format, can be overridden
        server_configuration=server_config,
        save_replays=True
        # Optionally, you can set a team here if not doing random battles
        # team=your_packed_team_string 
    )

    ai_player2 = ShowdownPlayerAI(
        account_configuration=account_config2,
        battle_format="gen9randombattle",
        server_configuration=server_config,
        save_replays=True
    )

    # Start a battle
    # For a random battle, the opponent_username is less critical as matchmaking handles it.
    # You can try challenging a known bot that accepts random battles, e.g., "BotName"
    # or just let it find a random opponent.
    from poke_env import cross_evaluate

    try:
        print("Starting self-play battles...")
        cross_evaluation = await cross_evaluate([ai_player1, ai_player2], n_challenges=3)
        print(f"Battle results: {cross_evaluation}")
        #await run_battle(ai_player, opponent_username="changiairport", battle_format="gen9randombattle")
        # To test with a specific format and team (you'll need a team_parser later):
        # example_ou_team = "dragapult|||dracometeor,shadowball,uturn,flamethrower|Focus Sash|Infiltrator|Timid|252SpA,4SpD,252Spe|||||]garchomp|||swordsdance,scalehsot,earthquake,stoneedge|LoadedDice|RoughSkin|Jolly|252Atk,4SpD,252Spe||,20,,,,," # Incomplete example
        # await run_battle(ai_player, opponent_username="SomeOUBotOrPlayer", battle_format="gen9ou", team=example_ou_team)

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        print("Player session ended.")

if __name__ == "__main__":
    # This is the standard way to run an asyncio program.
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted by user. Shutting down...")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        print("Cleanup complete.")