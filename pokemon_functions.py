import json
import random
from random import randint
import asyncio
import aiohttp
import discord



# Simple cache to store URL validity checks
sprite_cache = {}

async def update_embed_title(message, new_title):
    embed = message.embeds[0]  # Get the existing embed
    embed.title = new_title  # Change the title
    await message.edit(embed=embed)  # Edit the message with the updated embed

def initialize_wild_pool():
    with open('all_pokemon_data_v2.json', 'r') as file:
        pokemon_data = json.load(file)
    
    normal_ID_list = [pokemon["id"] for pokemon in pokemon_data if pokemon['rarity'] == "Normal"]
    mythical_ID_list =  [pokemon["id"] for pokemon in pokemon_data if pokemon['rarity'] == "Mythical"]
    legendary_ID_list = [pokemon["id"] for pokemon in pokemon_data if pokemon['rarity'] == "Legendary"]

    return normal_ID_list, mythical_ID_list, legendary_ID_list

def load_pokemon_into_dict():
    with open('all_pokemon_data_v2.json', 'r') as file:
        pokemon_data = json.load(file)

    pokemon_dict = {pokemon["name"]: pokemon for pokemon in pokemon_data}
    return pokemon_dict

def load_pokemon_into_dict_id():
    with open('all_pokemon_data_v2.json', 'r') as file:
        pokemon_data = json.load(file)

    pokemon_dict = {pokemon["id"]: pokemon for pokemon in pokemon_data}
    return pokemon_dict

def search_pokemon_by_name(pokemon):
    dict = load_pokemon_into_dict()
    pokemon = pokemon.lower().capitalize() #standardizes the case.
    for key in dict:
      if key.lower().capitalize() == pokemon:
        return dict[key]
    return None

def search_pokemon_by_id(pokemon):
    dict = load_pokemon_into_dict_id()
    results = dict.get(pokemon, None)
    return results

def search_pokemon_by_unique_id(id):
    with open('caught_pokemon_data.json', 'r') as file:
        pokemon_data = json.load(file)
        results = pokemon_data[id]
    return results

def get_next_evolution(evolution_line, current_pokemon):
    if not evolution_line:
        return "-"
    
    try:
        current_index = evolution_line.index(current_pokemon)
        # If it's the last evolution, return "-"
        if current_index == len(evolution_line) - 1:
            return "-"
        # Return the next evolution
        return evolution_line[current_index + 1]
    except ValueError:
        # If the current Pokémon is not found in the evolution line, return "-"
        return "-"
    
async def check_url(url):
    # Return the cached result if available
    if url in sprite_cache:
        return sprite_cache[url]
    async with aiohttp.ClientSession() as session:
        try:
            async with session.head(url) as response:
                is_valid = response.status == 200
                sprite_cache[url] = is_valid
                return is_valid
        except Exception:
            sprite_cache[url] = False
            return False

async def get_best_sprite_url(pokemon_data, shiny=False):
    """
    Get the best available sprite URL from the pokemon data by checking 
    each candidate URL for validity (status 200).
    """
    if not pokemon_data or "sprites" not in pokemon_data:
        return None

    sprites = pokemon_data["sprites"]

    # Define sprite priority order based on shiny or not
    if shiny:
        sprite_priority = [
            "front_shiny",
            "front_shiny_pokemondb",
            "front_shiny_pokeapi",
            "front_default_pokemondb",
            "front_default_pokeapi"
        ]
    else:
        sprite_priority = [
            "front_default",
            "front_default_pokemondb",
            "front_default_pokemondb_3d",
            "front_default_pokeapi",
            "official_artwork",
            "home_artwork"
        ]

    # Check each sprite URL in priority order
    for key in sprite_priority:
        url = sprites.get(key)
        if url:
            if await check_url(url):
                return url

    return None
    
def get_type_colour(type):
    if type[0] == "Grass":
        colour = 0x7AC74C
    elif type[0] == "Fire":
        colour = 0xEE8130
    elif type[0] == "Water":
        colour = 0x6390F0
    elif type[0] == "Electric":
        colour = 0xF7D02C
    elif type[0] == "Flying":
        colour = 0xA98FF3
    elif type[0] == "Bug":
        colour = 0xA6B91A
    elif type[0] == "Steel":
        colour = 0xB7B7CE
    elif type[0] == "Fairy":
        colour = 0xD685AD
    elif type[0] == "Poison":
        colour = 0xA33EA1
    elif type[0] == "Dragon":
        colour = 0x6F35FC
    elif type[0] == "Psychic":
        colour = 0xF95587
    elif type[0] == "Dark":
        colour = 0x705746
    elif type[0] == "Ghost":
        colour = 0x735797
    elif type[0] == "Rock":
        colour = 0xB6A136
    elif type[0] == "Ground":
        colour = 0xE2BF65
    elif type[0] == "Fighting":
        colour = 0xC22E28
    elif type[0] == "Ice":
        colour = 0x96D9D6
    elif type[0] == "Normal":
        colour = 0xA8A77A

    return colour

async def rename_pokemon(ctx, unique_id, new_name):
    """
    Rename a Pokemon in the caught_pokemon_data.json file
    
    Parameters:
    ctx - Discord context
    unique_id - Unique ID of the Pokemon to rename
    new_name - New name for the Pokemon
    
    Returns:
    bool - True if successful, False otherwise
    """
    try:
        with open('caught_pokemon_data.json', 'r+') as file:
            pokemon_data = json.load(file)
            
            # Make sure the Pokemon exists
            if unique_id not in pokemon_data:
                error_embed = discord.Embed(
                    title="Pokémon Not Found",
                    description=f"Pokémon with ID {unique_id} not found!",
                    color=discord.Color.red()
                )
                await ctx.send(embed=error_embed)
                return False
            
            # Limit name length to prevent abuse
            if len(new_name) > 20:
                error_embed = discord.Embed(
                    title="Name Too Long",
                    description="Pokémon name must be 20 characters or less!",
                    color=discord.Color.red()
                )
                await ctx.send(embed=error_embed)
                return False
                
            # Store original name for reference
            original_name = pokemon_data[unique_id]["name"]
            
            # Add nickname field
            pokemon_data[unique_id]["nickname"] = new_name
            
            # Write back to file
            file.seek(0)
            json.dump(pokemon_data, file, indent=1)
            file.truncate()
            
            return True
            
    except Exception as e:
        error_embed = discord.Embed(
            title="Error",
            description=f"Error renaming Pokémon: {str(e)}",
            color=discord.Color.red()
        )
        await ctx.send(embed=error_embed)
        return False

def choose_random_wild(normal_ID_list, mythical_ID_list, legendary_ID_list):
    rarity_choice = random.choices(
        ["normal", "mythical", "legendary"],
        weights=[98.95, 0.01, 0.0004],
        k=1
    )[0]

    shiny = random.choices(
        [True, False],
        weights=[1, 8191],
        k=1
    )[0]

    if rarity_choice == "normal":
        chosen_id = random.choice(normal_ID_list)
    elif rarity_choice == "mythical":
        chosen_id = random.choice(mythical_ID_list)
    else:
        chosen_id = random.choice(legendary_ID_list)

    pokemon = search_pokemon_by_id(chosen_id)

    return pokemon, shiny

async def search_cmd_handler(client, ctx, name, SHembed_editor, active_catchers):
    try:
        code = 0
        rate = None
        catch_result = None
        catch = None
        earnings = None
        
        # Use with statement for better file handling
        with open("Inventory.json", "r+") as file:
            data = json.load(file)
            
            pokedollars = data["users"][str(ctx.author.id)]["Pokedollars"]
            pokeballs = data["users"][str(ctx.author.id)]["Pokeballs"]
            greatballs = data["users"][str(ctx.author.id)]["Greatballs"]
            ultraballs = data["users"][str(ctx.author.id)]["Ultraballs"]
            masterballs = data["users"][str(ctx.author.id)]["Masterballs"]
            
            if pokeballs <= 0 and greatballs <= 0 and ultraballs <= 0 and masterballs <= 0:
                error_embed = discord.Embed(
                    title="No Pokéballs",
                    description=f"You don't have any Pokéballs! You could only watch as {name} fled.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=error_embed)
                await update_embed_title(SHembed_editor, f"{name} fled!")
                return code, catch_result, catch, rate, earnings
            
            # Load ball data
            with open("pokeballs.json", "r") as ball_file:
                ball_data = json.load(ball_file)
            
            pokemon_data = search_pokemon_by_name(name)
            if pokemon_data is None:
                error_embed = discord.Embed(
                    title="Pokémon Not Found",
                    description=f"Could not find a Pokémon named '{name}'. Please check the spelling.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=error_embed)
                await update_embed_title(SHembed_editor, f"{name} fled!")
                return 0, None, None, None, None
            
            base_catch_rate = pokemon_data["catch_rate"]
            earnings = random.randint(50, 150)
            flee_chance = 40
            
            while True:
                def check(msg):
                    # Modified check to ignore command messages
                    return (
                        msg.author == ctx.author and
                        msg.channel == ctx.channel and
                        msg.content and
                        not msg.content.startswith("%")  # Ignore command messages
                    )
                
                try:
                    msg = await client.wait_for("message", check=check, timeout=60.0)
                except asyncio.TimeoutError:
                    error_embed = discord.Embed(
                        title="Timeout",
                        description=f"You took too long to throw a ball! {name} fled!",
                        color=discord.Color.red()
                    )
                    await ctx.send(embed=error_embed)
                    await update_embed_title(SHembed_editor, f"{name} fled!")
                    return code, catch_result, catch, rate, earnings
                
                # Process pokeball selection
                if msg.content.lower() in ["pokeball", "pb"]:
                    if pokeballs <= 0:
                        error_embed = discord.Embed(
                            title="Not Enough Pokéballs",
                            description="You don't have enough Pokéballs!",
                            color=discord.Color.red()
                        )
                        await ctx.send(embed=error_embed)
                        continue
                    pokeballs -= 1
                    ball_multiplier = ball_data["Pokeball"]
                elif msg.content.lower() in ["greatball", "gb"]:
                    if greatballs <= 0:
                        error_embed = discord.Embed(
                            title="Not Enough Greatballs",
                            description="You don't have enough Greatballs!",
                            color=discord.Color.red()
                        )
                        await ctx.send(embed=error_embed)
                        continue
                    greatballs -= 1
                    ball_multiplier = ball_data["Greatball"]
                elif msg.content.lower() in ["ultraball", "ub"]:
                    if ultraballs <= 0:
                        error_embed = discord.Embed(
                            title="Not Enough Ultraballs",
                            description="You don't have enough Ultraballs!",
                            color=discord.Color.red()
                        )
                        await ctx.send(embed=error_embed)
                        continue
                    ultraballs -= 1
                    ball_multiplier = ball_data["Ultraball"]
                elif msg.content.lower() in ["masterball", "mb"]:
                    if masterballs <= 0:
                        error_embed = discord.Embed(
                            title="Not Enough Masterballs",
                            description="You don't have enough Masterballs!",
                            color=discord.Color.red()
                        )
                        await ctx.send(embed=error_embed)
                        continue
                    masterballs -= 1
                    ball_multiplier = ball_data["Masterball"]
                elif msg.content.lower() in ["run"]:
                    await update_embed_title(SHembed_editor, f"Got away from {name} safely.")
                    code = 1
                    # Properly save before exiting
                    file.seek(0)
                    json.dump(data, file, indent=1)
                    file.truncate()
                    catch_result = "ran"
                    return code, catch_result, catch, rate, earnings
                else:
                    # Only show this message during a valid catch sequence, not during errors
                    error_embed = discord.Embed(
                        title="Invalid Input",
                        description="Enter a pokeball name to use it (pokeball, greatball, ultraball, masterball or run to flee).",
                        color=discord.Color.red()
                    )
                    await ctx.send(embed=error_embed)
                    continue
                
                # Update user's inventory with new ball counts
                data["users"][str(ctx.author.id)]["Pokeballs"] = pokeballs
                data["users"][str(ctx.author.id)]["Greatballs"] = greatballs
                data["users"][str(ctx.author.id)]["Ultraballs"] = ultraballs
                data["users"][str(ctx.author.id)]["Masterballs"] = masterballs
                
                # Calculate catch chance
                modified_catch_rate = base_catch_rate * ball_multiplier
                catch = random.randint(0, 255)
                
                # Handle catch outcome
                if catch <= modified_catch_rate:
                    catch_result = True
                    data["users"][str(ctx.author.id)]["Pokedollars"] = pokedollars + earnings
                    # Always save changes to file
                    file.seek(0)
                    json.dump(data, file, indent=1)
                    file.truncate()
                    code = 1
                    break
                elif random.randint(1, 100) <= flee_chance:
                    await update_embed_title(SHembed_editor, f"{name} fled!")
                    catch_result = "ran"
                    # Always save changes to file
                    file.seek(0)
                    json.dump(data, file, indent=1)
                    file.truncate()
                    code = 1
                    break
                else:
                    random_retry_msg = random.choice([f"Argh so close! {name} broke free!", f"Not even close! {name} broke free!"])
                    await update_embed_title(SHembed_editor, random_retry_msg)
                
                # Always save after each action
                file.seek(0)
                json.dump(data, file, indent=1)
                file.truncate()
            
            # Final save before returning
            file.seek(0)
            json.dump(data, file, indent=1)
            file.truncate()
        
        return code, catch_result, catch, modified_catch_rate, earnings
    
    except Exception as e:
        # Handle any unexpected errors
        error_embed = discord.Embed(
            title="Error Occurred",
            description=f"An error occurred during your catch attempt: {str(e)}",
            color=discord.Color.red()
        )
        await ctx.send(embed=error_embed)
        return 0, None, None, None, None
    
    finally:
        # Always remove the user from active catchers, regardless of outcome
        active_catchers.discard(ctx.author.id)