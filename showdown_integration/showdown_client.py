# Flapple/showdown_integration/showdown_client.py

import asyncio # Required for asynchronous programming with poke-env
import random   # For making random choices
import os

from poke_env.player import Player, BattleOrder
#from poke_env.data import POKEDEX # For accessing Pokémon data if needed later
from poke_env.environment.battle import Battle
from poke_env import AccountConfiguration #ShowdownServerConfiguration
from poke_env import ServerConfiguration

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
BOT_NAME="returlte"
BOT_PASSWORD="Peepee21"

# --- Player Class ---
class ShowdownPlayerAI(Player):
    """
    This is the core class for your AI that will interact with Pokemon Showdown.
    It extends the Player class from poke-env.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the ShowdownPlayerAI.
        You can add any custom initialization logic here.
        """
        super().__init__(*args, **kwargs)
        # Example: you could load pre-trained models or other resources here
        print(f"ShowdownPlayerAI initialized for user: {self.username}")

    def choose_move(self, battle: Battle) -> BattleOrder:
        """
        This is the most important method to implement.
        It's called by poke-env whenever it's your AI's turn to make a move.

        Args:
            battle: The Battle object representing the current state of the battle.

        Returns:
            A BattleOrder object representing the chosen action (move, switch, etc.).
        """
        print(f"\n--- {self.username}'s Turn in battle: {battle.battle_tag} ---")
        print(f"Active Pokemon: {battle.active_pokemon} (HP: {battle.active_pokemon.current_hp_fraction * 100:.2f}%)")
        print(f"Opponent's Active Pokemon: {battle.opponent_active_pokemon} (HP: {battle.opponent_active_pokemon.current_hp_fraction * 100:.2f}%)")

        # Simple AI: Choose a random available move
        if battle.available_moves:
            # Available moves should already be moves that can be used
            chosen_move = random.choice(battle.available_moves)
            print(f"Choosing random move: {chosen_move.id}")
            return self.create_order(chosen_move)
        
        # If no moves are available (e.g., Choice-locked into a disabled move, or all moves have 0 PP),
        # try to switch.
        if battle.available_switches:
            valid_switches = [pokemon for pokemon in battle.available_switches if not pokemon.fainted]
            if valid_switches:
                chosen_switch = random.choice(valid_switches)
                print(f"No valid moves, choosing random switch: {chosen_switch.species}")
                return self.create_order(chosen_switch)
            else:
                print("No valid switches available.")

        # If absolutely no action can be taken (should be rare), pass.
        # This can also happen if you are trapped and all moves are out of PP.
        print("No moves or switches available. Passing.")
        return self.choose_default_move() # Or BattleOrder(None) for a pass

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

    def _battle_finished_callback(self, battle: Battle) -> None:
        """
        This method is called when a battle your player participated in ends.
        You can use this to log results, update stats, etc.
        """
        print(f"Battle {battle.battle_tag} finished.")
        if battle.won:
            print(f"Congratulations! {self.username} won the battle!")
        elif battle.lost:
            print(f"Hard luck! {self.username} lost the battle.")
        else:
            print(f"The battle {battle.battle_tag} ended in a draw or was inconclusive.")
        
        # You might want to disconnect or perform other cleanup here if this was a one-off battle.


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

    # Configure the server (use local or Smogon)
    # server_config = ShowdownServerConfiguration(LOCAL_SHOWDOWN_SERVER_URL, account_config.player_description)
    server_config = ServerConfiguration("ws://localhost:8000/showdown/websocket", "https://play.pokemonshowdown.com/action.php?")
    
    # Create our AI player instance
    # We pass server_configuration and account_configuration to the constructor
    ai_player = ShowdownPlayerAI(
        account_configuration=account_config,
        battle_format="gen9randombattle", # Default format, can be overridden
        server_configuration=server_config,
        # Optionally, you can set a team here if not doing random battles
        # team=your_packed_team_string 
    )

    # Start a battle
    # For a random battle, the opponent_username is less critical as matchmaking handles it.
    # You can try challenging a known bot that accepts random battles, e.g., "BotName"
    # or just let it find a random opponent.
    try:
        await run_battle(ai_player, opponent_username="changiairport", battle_format="gen9randombattle")
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