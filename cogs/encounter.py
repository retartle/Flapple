# cogs/encounter.py
import discord
import asyncio
import random
import time
import os
from discord.ext import commands
from config import inventory_collection, pokemon_collection, active_catchers, config_collection, unique_id_collection
from utils.encounter_utils import choose_random_wild, PokemonEncounterView, generate_encounter_image, get_emoji
from utils.pokemon_utils import search_pokemon_by_id, get_best_sprite_url, get_type_colour, prompt_for_nickname
from utils.db_utils import get_user_data, update_user_data, get_pokemon_data, update_pokemon_data

class EncounterCog(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.encounter_cache = {}
        self.CACHE_TIMEOUT = 300  # 5 minutes
        self.background_folder = os.path.join(os.getcwd(), "assets", "backgrounds")
        # Initialize wild pools on startup
        from utils.encounter_utils import initialize_wild_pool
        self.normal_ID_list, self.mythical_ID_list, self.legendary_ID_list = initialize_wild_pool()
    
    @commands.command(aliases=["s"])
    async def search(self, ctx):
        """Search for wild Pokémon to catch"""
        # Prevent multiple simultaneous catch encounters
        if ctx.author.id in active_catchers:
            error_embed = discord.Embed(
                title="Error: Already in Battle",
                description="You're already trying to catch a Pokémon! Complete your current encounter first.",
                color=discord.Color.red()
            )
            error_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
            await ctx.send(embed=error_embed)
            return
        
        active_catchers.add(ctx.author.id)
        
        # Immediately respond with a temporary message
        temp_message = await ctx.send(f"Searching for a wild pokemon... {get_emoji('grass')}")
        
        # Offload the heavy processing to a background task
        asyncio.create_task(self.process_search(ctx, temp_message))
    
    async def process_search(self, ctx, temp_message):
        """Process the search command (heavy lifting)"""
        try:
            # Get user data (with caching)
            user_data = await get_user_data(str(ctx.author.id))
            
            if not user_data:
                error_embed = discord.Embed(
                    title="No User Data",
                    description="You have not started your adventure! Use `%start` to begin.",
                    color=discord.Color.red()
                )
                await temp_message.edit(embed=error_embed)
                return
            
            # Get user environment rendering preferences
            user_settings = user_data.get("settings", {})
            environment_mode = user_settings.get("environment_rendering", "off")
            
            # Check if the user has at least one type of ball
            pokeballs = user_data.get("Pokeballs", 0)
            greatballs = user_data.get("Greatballs", 0)
            ultraballs = user_data.get("Ultraballs", 0)
            masterballs = user_data.get("Masterballs", 0)
            
            if pokeballs <= 0 and greatballs <= 0 and ultraballs <= 0 and masterballs <= 0:
                error_embed = discord.Embed(
                    title="No Pokéballs",
                    description="You don't have any Pokéballs! You need to buy some first with `%pokemart`.",
                    color=discord.Color.red()
                )
                await temp_message.edit(embed=error_embed)
                return
            
            # ----- Heavy Processing: Choose a wild Pokémon -----
            results, shiny = choose_random_wild(
                self.normal_ID_list, 
                self.mythical_ID_list, 
                self.legendary_ID_list
            )
            
            level = random.randint(3, 20)
            type_list = results["types"]
            type_str = ", ".join([t.capitalize() for t in type_list])
            colour = get_type_colour(type_list)
            name = results["name"].capitalize().replace('-', ' ')
            
            # Get sprite URL using environment settings
            sprite_url = await get_best_sprite_url(results, shiny, environment_mode)
            
            image_buffer = None
            is_animated = False
            
            # Generate environment image if enabled
            if environment_mode in ["static", "animated"] and sprite_url:
                is_animated_allowed = (environment_mode == "animated")
                # Use image generation function to produce a composite encounter image
                image_buffer, is_animated = await generate_encounter_image(
                    sprite_url=sprite_url,
                    background_folder=self.background_folder,
                    static_sprite_scale=0.4,
                    animated_sprite_scale=1.0,
                    position="bottom_center",
                    bg_size=(256, 144),
                    is_animated_allowed=is_animated_allowed
                )
            
            # Prepare additional encounter parameters
            ball_data = config_collection.find_one({"_id": "pokeballs"})
            base_catch_rate = results["catch_rate"]
            earnings = random.randint(50, 150)
            flee_chance = 20
            
            # Format the footer with ball counts
            ball_counts = []
            if pokeballs > 0:
                ball_counts.append(f"Pokeball: {pokeballs}")
            if greatballs > 0:
                ball_counts.append(f"Greatball: {greatballs}")
            if ultraballs > 0:
                ball_counts.append(f"Ultraball: {ultraballs}")
            if masterballs > 0:
                ball_counts.append(f"Masterball: {masterballs}")
            
            footer_text = f"{ctx.author.name}'s Battle | " + " | ".join(ball_counts)
            
            # Build the encounter embed
            SHembed = discord.Embed(
                title=f"{ctx.author.name} found a Lvl {level} {name}!",
                colour=colour
            )
            
            # If using generated image, attach it as a file
            if environment_mode in ["static", "animated"] and image_buffer:
                file_ext = 'gif' if is_animated else 'png'
                generated_file = discord.File(image_buffer, filename=f"encounter.{file_ext}")
                SHembed.set_image(url=f"attachment://encounter.{file_ext}")
            else:
                SHembed.set_image(url=sprite_url)
            
            SHembed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
            SHembed.set_footer(text=footer_text)
            
            # Create a view for the encounter (handles ball buttons, run, etc.)
            view = PokemonEncounterView(
                ctx=ctx,
                name=name + (" ⭐" if shiny else ""),
                pokeballs=pokeballs,
                greatballs=greatballs,
                ultraballs=ultraballs,
                masterballs=masterballs,
                base_catch_rate=base_catch_rate,
                ball_data=ball_data,
                SHembed_editor=None,  # Will be set later
                earnings=earnings,
                flee_chance=flee_chance
            )
            
            # Send final message with embed and view
            if environment_mode in ["static", "animated"] and image_buffer:
                SHembed_editor = await ctx.send(embed=SHembed, file=generated_file, view=view)
                await temp_message.delete()
                view.is_using_attachment = True
            else:
                SHembed_editor = await ctx.send(embed=SHembed, view=view)
                await temp_message.delete()
                view.original_sprite_url = sprite_url
            
            # Set the message reference in the view
            view.SHembed_editor = SHembed_editor
            
            # Wait for the encounter interaction to complete
            code, catch_result, catch, rate, earnings = await self.search_cmd_handler(ctx, view)
            
            if catch_result is True:
                # Store the caught Pokémon
                await self.store_caught_pokemon(ctx, results, shiny, level, sprite_url, type_str, colour)
        
        except Exception as e:
            error_embed = discord.Embed(
                title="Error Occurred",
                description=f"An error occurred during your search: {str(e)}",
                color=discord.Color.red()
            )
            try:
                await temp_message.edit(embed=error_embed)
            except discord.errors.NotFound:
                # Message was already deleted, send a new one
                await ctx.send(embed=error_embed)
        finally:
            # Always remove the user from the active catchers set
            active_catchers.discard(ctx.author.id)
    
    async def search_cmd_handler(self, ctx, view):
        """Handler for search command interaction results"""
        try:
            await view.wait()
            # Make sure these attributes are properly set by the view
            return view.code, view.catch_result, view.catch, view.rate, view.earnings
        except Exception as e:
            print(f"Error in search command handler: {str(e)}")
            return 0, None, None, None, None
        finally:
            active_catchers.discard(ctx.author.id)
    
    async def store_caught_pokemon(self, ctx, results, shiny, level, sprite_url, type_str, colour):
        """Store a caught Pokémon and show summary"""
        # Get user data
        user_id = str(ctx.author.id)
        user_data = await get_user_data(user_id)
        
        # Generate nature (with synchronize ability consideration if applicable)
        partner_nature = None
        has_synchronize = False
        
        if "partner_pokemon" in user_data and user_data["partner_pokemon"]:
            partner = await get_pokemon_data(user_data["partner_pokemon"])
            if partner:
                partner_nature = partner.get("nature")
                partner_pokemon_data = search_pokemon_by_id(partner["pokedex_id"])
                if partner_pokemon_data and "abilities" in partner_pokemon_data:
                    has_synchronize = "synchronize" in [a.get("name", "").lower() for a in partner_pokemon_data.get("abilities", [])]
        
        # Import necessary generation functions
        from utils.pokemon_utils import generate_nature, generate_iv, calculate_stat, generate_ability
        
        # Get nature (with synchronize consideration)
        nature = generate_nature(partner_nature, has_synchronize)
        
        # Get a unique ID for the Pokémon
        unique_id_doc = unique_id_collection.find_one_and_update(
            {},
            {"$inc": {"last_id": 1}},
            upsert=True,
            return_document=True
        )
        
        unique_id = str(unique_id_doc["last_id"]).zfill(6)
        
        # Generate IVs
        ivs = {
            "hp": generate_iv(),
            "attack": generate_iv(),
            "defense": generate_iv(),
            "special-attack": generate_iv(),
            "special-defense": generate_iv(),
            "speed": generate_iv()
        }
        
        # Generate ability
        ability_name = generate_ability(results)
        
        # Calculate initial XP based on level
        from utils.pokemon_utils import calculate_min_xp_for_level
        initial_xp = calculate_min_xp_for_level(level)
        
        # Create Pokémon document
        pokemon_doc = {
            "_id": unique_id,
            "pokedex_id": results["id"],
            "name": results["name"],
            "nickname": None,
            "shiny": shiny,
            "level": level,
            "nature": nature,
            "ivs": ivs,
            "base_stats": results["stats"],
            "final_stats": {
                "hp": calculate_stat(results["stats"]["hp"], ivs["hp"], level, is_hp=True),
                "attack": calculate_stat(results["stats"]["attack"], ivs["attack"], level),
                "defense": calculate_stat(results["stats"]["defense"], ivs["defense"], level),
                "special-attack": calculate_stat(results["stats"]["special-attack"], ivs["special-attack"], level),
                "special-defense": calculate_stat(results["stats"]["special-defense"], ivs["special-defense"], level),
                "speed": calculate_stat(results["stats"]["speed"], ivs["speed"], level)
            },
            "xp": initial_xp,
            "ability": ability_name
        }
        
        # Insert Pokémon into collection
        pokemon_collection.insert_one(pokemon_doc)
        
        # Add to user's caught Pokémon list
        await update_user_data(user_id, {"$push": {"caught_pokemon": unique_id}})
        
        # Create and send the catch summary embed
        pokemon_name = results["name"].capitalize().replace('-', ' ')
        if shiny:
            pokemon_name += " ⭐"
        
        RESULTembed = discord.Embed(
            title="Catch Summary",
            description=f"Lvl. {level} {pokemon_name}",
            colour=colour
        )
        
        RESULTembed.set_thumbnail(url=sprite_url)
        RESULTembed.add_field(name="Type", value=type_str, inline=False)
        RESULTembed.add_field(name="Ability", value=ability_name.capitalize(), inline=True)
        RESULTembed.add_field(name="Nature", value=nature, inline=True)
        
        # Display stats
        for stat, value in pokemon_doc["final_stats"].items():
            RESULTembed.add_field(
                name=f"{stat.capitalize()}",
                value=f"{value} (IV: {ivs[stat]})",
                inline=True
            )
        
        RESULTembed.set_footer(text=f"Caught by {ctx.author} | ID: {unique_id}")
        await ctx.send(embed=RESULTembed)
        
        # Prompt for nickname
        await prompt_for_nickname(ctx, pokemon_name, unique_id)
    
    def invalidate_cache(self, user_id=None):
        """Invalidate cache entries when data changes"""
        current_time = time.time()
        keys_to_remove = []
        
        for key in self.encounter_cache:
            # If user_id is specified, invalidate all caches for that user
            if user_id and key.startswith(f"{user_id}_"):
                keys_to_remove.append(key)
            
            # Remove expired cache entries
            elif current_time - self.encounter_cache[key]["timestamp"] > self.CACHE_TIMEOUT:
                keys_to_remove.append(key)
        
        # Remove the identified keys
        for key in keys_to_remove:
            if key in self.encounter_cache:
                del self.encounter_cache[key]

async def setup(client):
    await client.add_cog(EncounterCog(client))