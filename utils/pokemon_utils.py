# utils/pokemon_utils.py
import discord
import random
import asyncio
import aiohttp
from config import db

# ---- Functions imported from pokemon_functions.py ----

def search_pokemon_by_id(pokemon_id):
    """Search for a Pokémon by ID"""
    result = db.pokemon.find_one({"id": pokemon_id})
    return result

def search_pokemon_by_name(pokemon_name):
    """Search for a Pokémon by name"""
    pokemon_name = pokemon_name.lower()
    result = db.pokemon.find_one({"name": pokemon_name})
    return result

def get_type_colour(type_list):
    """Get a color for a Pokémon based on its primary type"""
    if not type_list:
        return discord.Color.blue().value
    
    type_colours = {
        "grass": 0x7AC74C,
        "fire": 0xEE8130,
        "water": 0x6390F0,
        "electric": 0xF7D02C,
        "flying": 0xA98FF3,
        "bug": 0xA6B91A,
        "steel": 0xB7B7CE,
        "fairy": 0xD685AD,
        "poison": 0xA33EA1,
        "dragon": 0x6F35FC,
        "psychic": 0xF95587,
        "dark": 0x705746,
        "ghost": 0x735797,
        "rock": 0xB6A136,
        "ground": 0xE2BF65,
        "fighting": 0xC22E28,
        "ice": 0x96D9D6,
        "normal": 0xA8A77A
    }
    
    primary_type = type_list[0].lower()
    return type_colours.get(primary_type, discord.Color.blue().value)

# Add to utils/pokemon_utils.py
def get_next_evolution(evolution_line, current_pokemon_name):
    """Get the next evolution in the evolution line for a Pokémon"""
    if not evolution_line or current_pokemon_name not in evolution_line:
        return "-"
    
    current_index = evolution_line.index(current_pokemon_name)
    if current_index < len(evolution_line) - 1:
        return evolution_line[current_index + 1]
    else:
        return "-"  # No further evolution


async def get_best_sprite_url(pokemon_data, shiny=False, environment_mode="off"):
    """Get the best sprite URL based on environment rendering preference"""
    if not pokemon_data or "sprites" not in pokemon_data:
        return None
    
    sprites = pokemon_data["sprites"]
    
    # For static environment mode, prioritize static PNG sprites
    if environment_mode == "static":
        if shiny:
            sprite_priority = [
                "front_shiny_pokemondb",  # Static shiny from PokemonDB
                "front_shiny_pokeapi",    # Static shiny from PokeAPI
                "front_shiny",            # Any shiny (possibly animated)
                "front_default_pokemondb" # Fallback to non-shiny static
            ]
        else:
            sprite_priority = [
                "front_default_pokemondb", # Static from PokemonDB
                "front_default_pokeapi",   # Static from PokeAPI
                "front_default"            # Any default (possibly animated)
            ]
    # For animated or disabled environment, use standard priority
    else:
        if shiny:
            sprite_priority = [
                "front_shiny",
                "front_shiny_pokemondb",
                "front_shiny_pokeapi",
                "front_default",
                "front_default_pokemondb"
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
    sprite_cache = {}
    
    for key in sprite_priority:
        url = sprites.get(key)
        if url:
            if key in sprite_cache:
                return url
            try:
                # Simple check if URL exists
                async with aiohttp.ClientSession() as session:
                    async with session.head(url, timeout=2) as response:
                        if response.status == 200:
                            sprite_cache[key] = True
                            return url
            except Exception:
                continue
    
    return None

# ---- Additional utility functions for Pokémon generation ----

def generate_iv():
    """Generate a random IV between 0 and 31"""
    return random.randint(0, 31)

def calculate_stat(base, iv, level, ev=0, nature=1, is_hp=False):
    """Calculate a Pokémon stat based on base stat, IV, level, etc."""
    if is_hp:
        # HP formula: floor((2 * B + I + E) * L / 100 + L + 10)
        return int((2 * base + iv + (ev // 4)) * level // 100 + level + 10)
    else:
        # Other stats: floor(floor((2 * B + I + E) * L / 100 + 5) * N)
        return int((((2 * base + iv + (ev // 4)) * level) // 100 + 5) * nature)

def calculate_min_xp_for_level(level):
    """Calculate the minimum total XP required to reach a given level"""
    if level <= 1:
        return 0
    
    # Formula for medium slow growth rate
    total_xp = int((6/5) * (level**3) - (15 * (level**2)) + (100 * level) - 140)
    
    # Ensure XP is not negative for low levels
    return max(0, total_xp)

def generate_ability(pokemon_base_data):
    """Generate an ability for a Pokémon based on its possible abilities"""
    if "abilities" not in pokemon_base_data or not pokemon_base_data["abilities"]:
        return None  # No abilities listed for this Pokémon
    
    possible_abilities = pokemon_base_data["abilities"]
    hidden_ability = None
    non_hidden_abilities = []
    
    for ability_info in possible_abilities:
        if ability_info.get("is_hidden", False):
            hidden_ability = ability_info.get("name")
        else:
            non_hidden_abilities.append(ability_info.get("name"))
    
    chosen_ability = None
    hidden_ability_chance = 1 / 150  # Adjust as needed (e.g., 1/150)
    
    # Check for hidden ability first
    if hidden_ability and random.random() < hidden_ability_chance:
        chosen_ability = hidden_ability
    # If hidden ability didn't proc or doesn't exist, choose from non-hidden
    elif non_hidden_abilities:
        chosen_ability = random.choice(non_hidden_abilities)
    # Fallback if only a hidden ability exists but didn't proc (should be rare)
    elif hidden_ability:
        chosen_ability = hidden_ability
    
    return chosen_ability

def generate_nature(partner_nature=None, has_synchronize=False):
    """Generate a Pokémon nature with synchronize ability support"""
    natures = [
        "Adamant", "Bashful", "Bold", "Brave", "Calm", "Careful", "Docile", "Gentle", "Hardy", "Hasty",
        "Impish", "Jolly", "Lax", "Lonely", "Mild", "Modest", "Naive", "Naughty", "Quiet", "Quirky",
        "Rash", "Relaxed", "Sassy", "Serious", "Timid"
    ]
    
    # If partner has Synchronize and a valid nature, 50% chance to match
    if has_synchronize and partner_nature in natures:
        if random.random() < 0.5:
            return partner_nature
    
    # Otherwise, select a random nature with equal probability
    return random.choice(natures)

async def prompt_for_nickname(ctx, pokemon_name, unique_id):
    """Prompt user to nickname their newly caught Pokémon"""
    from config import pokemon_collection
    
    nickname_complete = asyncio.Event()
    
    # Create buttons for options
    rename_button = discord.ui.Button(style=discord.ButtonStyle.primary, label="Nickname this Pokémon")
    skip_button = discord.ui.Button(style=discord.ButtonStyle.secondary, label="Skip Naming")
    
    # Create modal for nickname entry
    class RenameModal(discord.ui.Modal):
        def __init__(self, pokemon_name, unique_id):
            super().__init__(title="Name Your Pokémon")
            self.pokemon_name = pokemon_name
            self.unique_id = unique_id
            
            self.add_item(discord.ui.TextInput(
                label=f"New name for {pokemon_name}",
                placeholder="Enter a nickname (16 characters max)",
                max_length=16,
                required=True
            ))
        
        async def on_submit(self, interaction):
            nickname = self.children[0].value
            
            # Update the nickname in the database
            result = pokemon_collection.update_one(
                {"_id": self.unique_id},
                {"$set": {"nickname": nickname}}
            )
            
            if result.modified_count > 0:
                success_embed = discord.Embed(
                    title="Pokémon Nicknamed",
                    description=f"Successfully renamed your {self.pokemon_name} to \"{nickname}\"!",
                    color=discord.Color.green()
                )
                success_embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar)
                await interaction.response.edit_message(embed=success_embed, view=None)
            else:
                error_embed = discord.Embed(
                    title="Update Failed",
                    description=f"Failed to update the nickname for Pokémon with ID {self.unique_id}.",
                    color=discord.Color.red()
                )
                error_embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar)
                await interaction.response.edit_message(embed=error_embed, view=None)
            
            nickname_complete.set()
    
    # Button callbacks
    async def rename_callback(interaction):
        if interaction.user.id != ctx.author.id:
            await interaction.response.send_message("This is not your Pokémon to name!", ephemeral=True)
            return
        
        modal = RenameModal(pokemon_name, unique_id)
        await interaction.response.send_modal(modal)
    
    async def skip_callback(interaction):
        if interaction.user.id != ctx.author.id:
            await interaction.response.send_message("This is not your Pokémon!", ephemeral=True)
            return
        
        skip_embed = discord.Embed(
            title="Nickname Skipped",
            description=f"Keeping the name as {pokemon_name}!",
            color=discord.Color.blue()
        )
        skip_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
        await interaction.response.edit_message(embed=skip_embed, view=None)
        nickname_complete.set()
    
    # Set callbacks
    rename_button.callback = rename_callback
    skip_button.callback = skip_callback
    
    # Create view and add buttons
    view = discord.ui.View(timeout=60)
    view.add_item(rename_button)
    view.add_item(skip_button)
    
    # Create embed for nickname prompt
    nickname_embed = discord.Embed(
        title="Name Your Pokémon",
        description=f"Would you like to nickname your new {pokemon_name}?",
        color=discord.Color.blue()
    )
    nickname_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
    
    # Send message with view
    message = await ctx.send(embed=nickname_embed, view=view)
    
    # Wait for interaction or timeout
    try:
        await asyncio.wait_for(nickname_complete.wait(), timeout=60.0)
    except asyncio.TimeoutError:
        timeout_embed = discord.Embed(
            title="Name Your Pokemon",
            description=f"You took too long to respond, keeping the name as {pokemon_name}",
            color=discord.Color.red()
        )
        timeout_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
        await message.edit(embed=timeout_embed, view=None)