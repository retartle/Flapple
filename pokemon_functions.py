import json
import random
from random import randint
import asyncio
import aiohttp


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

async def search_cmd_handler(client, ctx, name, SHembed_editor):
    code = 0
    rate = None
    catch_result = None
    catch = None
    earnings = None

    file = open("inventory.json", "r+")
    data = json.load(file)
    file.seek(0)

    pokedollars = data["users"][str(ctx.author.id)]["Pokedollars"]
    pokeballs = data["users"][str(ctx.author.id)]["Pokeballs"]
    greatballs = data["users"][str(ctx.author.id)]["Greatballs"]
    ultraballs = data["users"][str(ctx.author.id)]["Ultraballs"]
    masterballs = data["users"][str(ctx.author.id)]["Masterballs"]

    if pokeballs <= 0 and greatballs <= 0 and ultraballs <= 0 and masterballs <= 0:
        await ctx.send(f"You don't have any Pokeballs! You could only watch as {name} fled.")
        await update_embed_title(SHembed_editor, f"{name} fled!")
        return code, catch_result, catch, rate, earnings

    ball_file = open("pokeballs.json", "r")
    ball_data = json.load(ball_file)
    ball_file.close()

    pokemon_data = search_pokemon_by_name(name)

    if pokemon_data is None:
        await ctx.send(f"Could not find a Pokémon named '{name}'. Please check the spelling.")
        await update_embed_title(SHembed_editor, f"{name} fled!")
        return 0, None, None, None, None

    base_catch_rate = pokemon_data["catch_rate"]

    earnings = random.randint(50, 150)
    flee_chance = 40

    while True:
        def check(msg):
            return msg.author == ctx.author and msg.channel == ctx.channel and msg.content

        try:
            msg = await client.wait_for("message", check=check, timeout=60.0)
        except asyncio.TimeoutError:
            await ctx.send(f"You took too long to throw a ball! {name} fled!")
            await update_embed_title(SHembed_editor, f"{name} fled!")
            return code, catch_result, catch, rate, earnings

        if msg.content.lower() in ["pokeball", "pb"]:
            if pokeballs <= 0:
                await ctx.send("You don't have enough Pokeballs!")
                continue
            pokeballs -= 1
            ball_multiplier = ball_data["Pokeball"]

        elif msg.content.lower() in ["greatball", "gb"]:
            if greatballs <= 0:
                await ctx.send("You don't have enough Greatballs!")
                continue
            greatballs -= 1
            ball_multiplier = ball_data["Greatball"]

        elif msg.content.lower() in ["ultraball", "ub"]:
            if ultraballs <= 0:
                await ctx.send("You don't have enough Ultraballs!")
                continue
            ultraballs -= 1
            ball_multiplier = ball_data["Ultraball"]

        elif msg.content.lower() in ["masterball", "mb"]:
            if masterballs <= 0:
                await ctx.send("You don't have enough Masterballs!")
                continue
            masterballs -= 1
            ball_multiplier = ball_data["Masterball"]

        elif msg.content.lower() in ["run"]:
            await update_embed_title(SHembed_editor, f"Got away from {name} safely.")
            code = 1
            file.seek(0)
            json.dump(data, file, indent=1)
            file.truncate()
            file.close()
            catch_result = "ran"
            return code, catch_result, catch, rate, earnings

        else:
            await ctx.send("Enter a pokeball name to use it.")
            continue

        data["users"][str(ctx.author.id)]["Pokeballs"] = pokeballs
        data["users"][str(ctx.author.id)]["Greatballs"] = greatballs
        data["users"][str(ctx.author.id)]["Ultraballs"] = ultraballs
        data["users"][str(ctx.author.id)]["Masterballs"] = masterballs

        modified_catch_rate = base_catch_rate * ball_multiplier
        catch = random.randint(0, 255)

        if catch <= modified_catch_rate:
            catch_result = True
            data["users"][str(ctx.author.id)]["Pokedollars"] = pokedollars + earnings
            json.dump(data, file, indent=1)
            code = 1
            break
        elif random.randint(1, 100) <= flee_chance:
            await update_embed_title(SHembed_editor, f"{name} fled!")
            catch_result = "ran"
            json.dump(data, file, indent=1)
            code = 1
            break
        else:
            random_retry_msg = random.choice([f"Argh so close! {name} broke free!", f"Not even close! {name} broke free!"])
            await update_embed_title(SHembed_editor, random_retry_msg)

    file.seek(0)
    json.dump(data, file, indent=1)
    file.truncate()
    file.close()
    return code, catch_result, catch, modified_catch_rate, earnings