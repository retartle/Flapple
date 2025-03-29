import json
import random
from random import randint
import asyncio
import aiohttp
import discord
import os
from pymongo import MongoClient

# Simple cache to store URL validity checks
sprite_cache = {}

async def update_embed_title(message, new_title):
    # This function doesn't interact with the database, so it remains unchanged
    embed = message.embeds[0]
    embed.title = new_title
    await message.edit(embed=embed)

def initialize_wild_pool():
    # MongoDB version
    from pymongo import MongoClient
    from main import db
    
    # Get all pokemon data from MongoDB
    pokemon_list = list(db.pokemon.find({}, {"id": 1, "rarity": 1}))
    
    normal_ID_list = [pokemon["id"] for pokemon in pokemon_list if pokemon.get('rarity') == "Normal"]
    mythical_ID_list = [pokemon["id"] for pokemon in pokemon_list if pokemon.get('rarity') == "Mythical"]
    legendary_ID_list = [pokemon["id"] for pokemon in pokemon_list if pokemon.get('rarity') == "Legendary"]
    
    return normal_ID_list, mythical_ID_list, legendary_ID_list

def search_pokemon_by_name(pokemon):
    # MongoDB version
    from main import db
    
    pokemon_name = pokemon.lower()
    result = db.pokemon.find_one({"name": pokemon_name})
    return result

def search_pokemon_by_id(pokemon_id):
    # MongoDB version
    from main import db
    
    result = db.pokemon.find_one({"id": pokemon_id})
    return result

def search_pokemon_by_unique_id(id):
    # MongoDB version
    from main import pokemon_collection
    
    result = pokemon_collection.find_one({"_id": id})
    return result

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

def get_emoji(ball_type):
    """Retrieve an emoji for a given ball type"""
    from main import db
    emoji_data = db.emojis.find_one({"_id": ball_type})
    return emoji_data["emoji"] if emoji_data else None
    
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

class RenameModal(discord.ui.Modal):
    def __init__(self, pokemon_name, unique_id, **kwargs):
        super().__init__(**kwargs)  # Make sure title and other kwargs are passed
        self.pokemon_name = pokemon_name
        self.unique_id = unique_id
        self.interaction = None
        self.add_item(discord.ui.TextInput(
            label=f"New name for {pokemon_name}",
            placeholder="Enter a nickname (16 characters max)",
            max_length=16,
            required=True
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        self.interaction = interaction
        nickname = self.children[0].value

        try:
            client = MongoClient(os.getenv('Mongo_API'))
            pokemon_collection = client.flapple.caught_pokemon
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
        except Exception as e:
            print(f"Error in on_submit: {str(e)}")
            error_embed = discord.Embed(
                title="Error",
                description=f"Error renaming Pokémon: {str(e)}",
                color=discord.Color.red()
            )
            error_embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar)
            await interaction.response.edit_message(embed=error_embed, view=None)


async def prompt_for_nickname(ctx, pokemon_name, unique_id):
    nickname_complete = asyncio.Event()
    rename_button = discord.ui.Button(style=discord.ButtonStyle.primary, label="Nickname this Pokémon")
    skip_button = discord.ui.Button(style=discord.ButtonStyle.secondary, label="Skip Naming")

    async def rename_callback(interaction):
        if interaction.user.id != ctx.author.id:
            await interaction.response.send_message("This is not your Pokémon to name!", ephemeral=True)
            return
        print(f"Opening RenameModal for Pokémon ID: {unique_id}")
        modal = RenameModal(
            title="Name Your Pokémon",
            pokemon_name=pokemon_name,
            unique_id=unique_id
        )
        await interaction.response.send_modal(modal)
        nickname_complete.set()
        

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

    rename_button.callback = rename_callback
    skip_button.callback = skip_callback

    view = discord.ui.View(timeout=60)
    view.add_item(rename_button)
    view.add_item(skip_button)

    nickname_embed = discord.Embed(
        title="Name Your Pokémon",
        description=f"Would you like to nickname your new {pokemon_name}?",
        color=discord.Color.blue()
    )
    nickname_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
    message = await ctx.send(embed=nickname_embed, view=view)

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

class PokemonEncounterView(discord.ui.View):
    def __init__(self, ctx, name, pokeballs, greatballs, ultraballs, masterballs, 
                 base_catch_rate, ball_data, SHembed_editor, earnings, flee_chance):
        super().__init__(timeout=60)  # 60 second timeout
        self.ctx = ctx
        self.name = name
        self.pokeballs = pokeballs
        self.greatballs = greatballs
        self.ultraballs = ultraballs
        self.masterballs = masterballs
        self.base_catch_rate = base_catch_rate
        self.ball_data = ball_data
        self.SHembed_editor = SHembed_editor
        self.earnings = earnings
        self.flee_chance = flee_chance
        self.code = 0
        self.catch_result = None
        self.catch = None
        self.rate = None

        self.emojis = {
            "pokeball": get_emoji("pokeball"),
            "greatball": get_emoji("greatball"),
            "ultraball": get_emoji("ultraball"),
            "masterball": get_emoji("masterball")
        }
        
        # Add buttons dynamically based on inventory
        self._setup_buttons()
    
    def _setup_buttons(self):
        """Add ball buttons based on what's in inventory using loop to reduce duplication"""
        ball_types = [
            ("pokeball", self.pokeballs, self.pokeball_callback),
            ("greatball", self.greatballs, self.greatball_callback),
            ("ultraball", self.ultraballs, self.ultraball_callback),
            ("masterball", self.masterballs, self.masterball_callback)
        ]
        
        for ball_type, count, callback in ball_types:
            if count > 0:
                button = discord.ui.Button(
                    style=discord.ButtonStyle.secondary,
                    custom_id=ball_type,
                    emoji=self.emojis[ball_type]
                )
                button.callback = callback
                self.add_item(button)
        
        # Add run button
        run_button = discord.ui.Button(
            style=discord.ButtonStyle.danger,
            label="Run",
            custom_id="run"
        )
        run_button.callback = self.run_callback
        self.add_item(run_button)

    async def _update_embed(self, title=None, update_footer=False):
        """Update multiple parts of the embed in a single edit operation"""
        embed = self.SHembed_editor.embeds[0]
        
        # Update title if provided
        if title is not None:
            embed.title = title
        
        # Update footer if requested
        if update_footer:
            footer_text = self._get_footer_text()
            embed.set_footer(text=footer_text)
        
        # Perform a single edit operation
        await self.SHembed_editor.edit(embed=embed)

    def _get_footer_text(self):
        """Generate consistent footer text"""
        ball_counts = []
        if self.pokeballs > 0:
            ball_counts.append(f"Pokeball: {self.pokeballs}")
        if self.greatballs > 0:
            ball_counts.append(f"Greatball: {self.greatballs}")
        if self.ultraballs > 0:
            ball_counts.append(f"Ultraball: {self.ultraballs}")
        if self.masterballs > 0:
            ball_counts.append(f"Masterball: {self.masterballs}")
        
        return f"{self.ctx.author.name}'s Battle | " + " | ".join(ball_counts)

    async def pokeball_callback(self, interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your Pokémon battle!", ephemeral=True)
            return
        
        self.pokeballs -= 1
        await self._process_catch_attempt(interaction, self.ball_data["Pokeball"], "Pokeball")
    
    async def greatball_callback(self, interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your Pokémon battle!", ephemeral=True)
            return
        
        self.greatballs -= 1
        await self._process_catch_attempt(interaction, self.ball_data["Greatball"], "Greatball")
    
    async def ultraball_callback(self, interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your Pokémon battle!", ephemeral=True)
            return
        
        self.ultraballs -= 1
        await self._process_catch_attempt(interaction, self.ball_data["Ultraball"], "Ultraball")
    
    async def masterball_callback(self, interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your Pokémon battle!", ephemeral=True)
            return
        
        self.masterballs -= 1
        await self._process_catch_attempt(interaction, self.ball_data["Masterball"], "Masterball")
    
    async def run_callback(self, interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your Pokémon battle!", ephemeral=True)
            return

        # Disable all buttons
        for item in self.children:
            item.disabled = True

        # Update title and view in ONE operation
        await self._update_embed(title=f"Got away from {self.name} safely.")

        # Ensure the view is updated with disabled buttons
        await interaction.response.edit_message(embed=self.SHembed_editor.embeds[0], view=self)

        self.code = 1
        self.catch_result = "ran"
        self.stop()

    async def _process_catch_attempt(self, interaction, ball_multiplier, ball_name):
        """Process a catch attempt with the given ball multiplier"""
        from main import inventory_collection
        
        # Update inventory in MongoDB
        inventory_collection.update_one(
            {"_id": str(self.ctx.author.id)},
            {"$set": {
                "Pokeballs": self.pokeballs,
                "Greatballs": self.greatballs,
                "Ultraballs": self.ultraballs,
                "Masterballs": self.masterballs
            }}
        )
        
        # Calculate catch chance
        modified_catch_rate = self.base_catch_rate * ball_multiplier
        catch = random.randint(0, 255)
        
        # Clear the view and recreate the buttons with updated counts
        self.clear_items()
        self._setup_buttons()
        
        # Handle catch outcome and update embed in a single operation
        if catch <= modified_catch_rate:
            # Successful catch
            self.catch_result = True
            inventory_collection.update_one(
                {"_id": str(self.ctx.author.id)},
                {"$inc": {"Pokedollars": self.earnings}}
            )
            
            # Update both title and footer in one operation
            await self._update_embed(
                title=f"{self.name} was caught! You earned {self.earnings} Pokedollars",
                update_footer=True
            )
            
            # Disable all buttons after successful catch
            for item in self.children:
                item.disabled = True
                
            self.code = 1
            self.catch = catch
            self.rate = modified_catch_rate
            
            await interaction.response.edit_message(view=self)
            self.stop()
            
        elif random.randint(1, 100) <= self.flee_chance:
            # Pokémon fled
            await self._update_embed(
                title=f"{self.name} fled!",
                update_footer=True
            )
            
            # Disable all buttons after the Pokémon flees
            for item in self.children:
                item.disabled = True
                
            self.catch_result = "ran"
            self.code = 1
            self.catch = catch
            self.rate = modified_catch_rate
            
            await interaction.response.edit_message(view=self)
            self.stop()
            
        else:
            # Failed catch, but Pokémon didn't flee
            random_retry_msg = random.choice([
                f"Argh so close! {self.name} broke free!", 
                f"Not even close! {self.name} broke free!"
            ])
            
            await self._update_embed(
                title=random_retry_msg,
                update_footer=True
            )
            
            self.catch = catch
            self.rate = modified_catch_rate
            
            await interaction.response.edit_message(view=self)
    
    async def on_timeout(self):
        """Handle timeout (user didn't interact within the timeout period)"""
        for item in self.children:
            item.disabled = True

        try:
            embed = self.SHembed_editor.embeds[0]
            embed.title = f"{self.name} fled!"
            await self.SHembed_editor.edit(embed=embed, view=self)
        except Exception as e:
            print(f"Error in timeout handler: {e}")

        self.catch_result = "timeout"
        self.stop()
        
async def search_cmd_handler(client, ctx, active_catchers, view):
    """Simplified handler with only necessary parameters"""
    try:
        await view.wait()
        return view.code, view.catch_result, view.catch, view.rate, view.earnings
    except Exception as e:
        print(f"Error in search command handler: {str(e)}")
        return 0, None, None, None, None
    finally:
        active_catchers.discard(ctx.author.id)