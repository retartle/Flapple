import discord
import os
import json
import time
from random import randint
from dotenv import load_dotenv
from discord.ext import commands

from move_functions import *
from pokemon_functions import *
from pokemon_stat_generation import *
from trainer_functions import *

import asyncio
from pymongo import MongoClient

load_dotenv()

Admins = [786083062172745770]

# MongoDB connection
client = MongoClient(os.getenv('Mongo_API'))
db = client.flapple
inventory_collection = db.inventory
pokemon_collection = db.caught_pokemon
unique_id_collection = db.unique_id
move_collection = db.moves  
config_collection = db.config

__all__ = ['inventory_collection', 'pokemon_collection', 'unique_id_collection', 'move_collection', 'config_collection']

# Place the starter_pokemon_generations dictionary here, at the top level
starter_pokemon_generations = {
    1: [1, 4, 7],  # Bulbasaur, Charmander, Squirtle
    2: [152, 155, 158],  # Chikorita, Cyndaquil, Totodile
    3: [252, 255, 258],  # Treecko, Torchic, Mudkip
    4: [387, 390, 393],  # Turtwig, Chimchar, Piplup
    5: [495, 498, 501],  # Snivy, Tepig, Oshawott
    6: [650, 653, 656],  # Chespin, Fennekin, Froakie
    7: [722, 725, 728],  # Rowlet, Litten, Popplio
    8: [810, 813, 816],  # Grookey, Scorbunny, Sobble
    9: [906, 909, 912] # Sprigatito, Fuecoco, Quaxly
}

client = commands.Bot(command_prefix=('%'),
                      case_insensitive=True,
                      intents=discord.Intents.all())

normal_ID_list, mythical_ID_list, legendary_ID_list = initialize_wild_pool()

@client.event
async def on_ready():
    await initialize_session()
    print('Flapple is online, Wild pokemon pool initialized.')

@client.event
async def on_close():
    session = get_session()
    if session:
        await session.close()

user_cooldowns = {}  # Dictionary to store user cooldowns

active_catchers = set() # Dictionary to track users currently in a catch sequence


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    cooldown_seconds = 2
    xp_reward = 10

    current_time = time.time()
    user_id = str(message.author.id)

    if user_id in user_cooldowns and current_time - user_cooldowns[user_id] < cooldown_seconds:
        await client.process_commands(message)
        return

    user_cooldowns[user_id] = current_time

    user_data = inventory_collection.find_one({"_id": user_id})
    if user_data and "partner_pokemon" in user_data:
        partner_id = user_data["partner_pokemon"]
        if partner_id:
            partner_pokemon = pokemon_collection.find_one({"_id": partner_id})
            if partner_pokemon:
                new_xp = partner_pokemon.get("xp", 0) + xp_reward
                pokemon_collection.update_one(
                    {"_id": partner_id},
                    {"$set": {"xp": new_xp}}
                )
                
                level = partner_pokemon["level"]
                next_level_xp = int((6/5) * ((level + 1)**3) - (15 * ((level + 1)**2)) + (100 * (level + 1)) - 140)
                
                if new_xp >= next_level_xp:
                    excess_xp = new_xp - next_level_xp
                    pokemon_collection.update_one(
                        {"_id": partner_id},
                        {
                            "$inc": {"level": 1},
                            "$set": {"xp": excess_xp}
                        }
                    )
                    await message.channel.send(f"{message.author.mention}'s partner, {partner_pokemon['name'].capitalize()}, leveled up to level {level + 1}!")

    await client.process_commands(message)

@client.command()
async def ping(ctx):
    await ctx.send(f'The current ping is {round(client.latency * 1000)}ms!')

@client.command()
async def start(ctx):
    user_id = str(ctx.author.id)
    try:
        # Check if user already exists
        user_data = inventory_collection.find_one({"_id": user_id})
        
        if not user_data:
            message = await intro(ctx,client)
            # Let user choose trainer sprite first
            trainer_sprite = await select_trainer_sprite(ctx, client, message)
            
            # New user setup with trainer sprite
            user_data = {
                "_id": user_id,
                "Pokeballs": 25,
                "Greatballs": 0,
                "Ultraballs": 0,
                "Masterballs": 0,
                "Pokedollars": 5000,
                "caught_pokemon": [],
                "partner_pokemon": None,
                "trainer_sprite": trainer_sprite
            }
            
            # Import starter functions module
            import starter_functions
            
            chosen_generation = None
            chosen_starter = None
            
            # Outer loop: allow the user to reselect generation if needed
            while chosen_starter is None:
                chosen_generation = await starter_functions.select_generation(ctx, client, starter_pokemon_generations, message)
                if chosen_generation is None:
                    return # Generation selection timed out
                
                chosen_starter = await starter_functions.preview_and_select_starter(ctx, client, chosen_generation, starter_pokemon_generations, message)
                if chosen_starter is None:
                    # User opted to reselect generation; loop again
                    continue
            
            # Set and store the chosen starter as the user's partner Pokémon
            full_pokemon_data = search_pokemon_by_id(chosen_starter["id"])
            is_shiny = random.choices([True, False], weights=[1, 4095], k=1)[0]
            
            # Get a unique ID
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

            nature = generate_nature()
            starter_ability_name = generate_ability(full_pokemon_data)
            starter_initial_xp = calculate_min_xp_for_level(5)
            
            # Create the Pokemon document
            pokemon_doc = {
                "_id": unique_id,
                "pokedex_id": full_pokemon_data["id"],
                "name": full_pokemon_data["name"],
                "nickname": None,
                "shiny": is_shiny,
                "level": 5,
                "nature": nature,
                "ivs": ivs,
                "base_stats": full_pokemon_data["stats"],
                "final_stats": {
                    "hp": calculate_stat(full_pokemon_data["stats"]["hp"], ivs["hp"], 5),
                    "attack": calculate_stat(full_pokemon_data["stats"]["attack"], ivs["attack"], 5),
                    "defense": calculate_stat(full_pokemon_data["stats"]["defense"], ivs["defense"], 5),
                    "special-attack": calculate_stat(full_pokemon_data["stats"]["special-attack"], ivs["special-attack"], 5),
                    "special-defense": calculate_stat(full_pokemon_data["stats"]["special-defense"], ivs["special-defense"], 5),
                    "speed": calculate_stat(full_pokemon_data["stats"]["speed"], ivs["speed"], 5)
                },
                "xp": starter_initial_xp,
                "ability": starter_ability_name
            }
            
            # Insert the Pokemon
            pokemon_collection.insert_one(pokemon_doc)
            
            # Update user's inventory
            user_data["caught_pokemon"].append(unique_id)
            user_data["partner_pokemon"] = unique_id
            
            # Insert the user data
            inventory_collection.insert_one(user_data)
            
            # Create and send the starter summary embed
            starter_embed = await starter_functions.create_starter_summary_embed(ctx, chosen_starter, full_pokemon_data, unique_id, is_shiny)
            await asyncio.sleep(2)
            await message.edit(embed=starter_embed)
            
            await prompt_for_nickname(ctx, chosen_starter['name'], unique_id)
            
            await ctx.send(f"Your adventure has just begun, Trainer {ctx.author.name}! You have received 20 Pokeballs and 10000 Pokedollars. Use `%search` to find a wild Pokémon!")
        else:
            await ctx.send("You have already begun your adventure! Start searching for wild Pokémon using `%search`")
    
    except Exception as e:
        error_embed = discord.Embed(
            title="Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red()
        )
        await ctx.send(embed=error_embed)

@client.command(aliases=["p", "me"])
async def profile(ctx, user: discord.Member = None):
    """Display trainer profile with avatar, stats and partner"""
    if user is None:
        user = ctx.author
    
    user_id = str(user.id)
    
    try:
        # Fetch user data from MongoDB
        user_data = inventory_collection.find_one({"_id": user_id})
        
        if not user_data:
            await ctx.send(f"{user.name} has not begun their adventure yet!")
            return
        
        # Get trainer info
        pokedollars = user_data.get("Pokedollars", 0)
        caught_pokemon = user_data.get("caught_pokemon", [])
        trainer_sprite = user_data.get("trainer_sprite", "red")  # Default if not set
        
        # Get partner Pokémon info
        partner_id = user_data.get("partner_pokemon")
        partner_info = "None"
        
        if partner_id:
            partner = pokemon_collection.find_one({"_id": partner_id})
            if partner:
                name = partner["name"].capitalize().replace('-', ' ')
                nickname = partner.get("nickname")
                level = partner["level"]
                
                display_name = f"{nickname} ({name})" if nickname else name
                if partner.get("shiny"):
                    display_name += " ⭐"
                
                partner_info = f"{display_name} (Level {level})"
                
                # Get partner sprite for embed
                pokemon_data = search_pokemon_by_id(partner["pokedex_id"])
                partner_sprite = await get_best_sprite_url(pokemon_data, partner.get("shiny", False))
        
        # Create profile embed
        embed = discord.Embed(
            title=f"{user.name}'s Trainer Profile",
            color=discord.Color.blue()
        )
        
        # Set the trainer sprite as the thumbnail
        sprite_url = f"https://play.pokemonshowdown.com/sprites/trainers/{trainer_sprite}.png"
        embed.set_thumbnail(url=sprite_url)
        
        # Add user stats
        embed.add_field(name="💰 Balance", value=f"{pokedollars:,} Pokedollars", inline=True)
        embed.add_field(name="🏆 Pokémon Caught", value=f"{len(caught_pokemon)}", inline=True)
        embed.add_field(name="🤝 Partner Pokémon", value=partner_info, inline=False)
        
        # Add partner sprite if available
        if partner_id and partner_sprite:
            embed.set_image(url=partner_sprite)
        
        # Add inventory section
        inventory = f"**Pokeballs:** {user_data.get('Pokeballs', 0)}\n" \
                   f"**Greatballs:** {user_data.get('Greatballs', 0)}\n" \
                   f"**Ultraballs:** {user_data.get('Ultraballs', 0)}\n" \
                   f"**Masterballs:** {user_data.get('Masterballs', 0)}"
        embed.add_field(name="🎒 Inventory", value=inventory, inline=False)
        
        embed.set_footer(text="Use %box to view your Pokémon | %changesprite to change avatar")
        
        await ctx.send(embed=embed)
    
    except Exception as e:
        error_embed = discord.Embed(
            title="Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red()
        )
        await ctx.send(embed=error_embed)

@client.command(aliases=["changeavatar", "ca"])
async def change_avatar(ctx):
    """Change your trainer sprite"""
    user_id = str(ctx.author.id)
    
    try:
        # Check if user exists
        user_data = inventory_collection.find_one({"_id": user_id})
        
        if not user_data:
            await ctx.send("You have not begun your adventure! Start by using the `%start` command.")
            return
        
        # Get current sprite for comparison
        current_sprite = user_data.get("trainer_sprite", "red")
        
        # Let user choose a new sprite
        await ctx.send("Choose your new trainer avatar!")
        new_sprite = await select_trainer_sprite(ctx, client)
        
        # Update the sprite in MongoDB
        inventory_collection.update_one(
            {"_id": user_id},
            {"$set": {"trainer_sprite": new_sprite}}
        )
        
        # Confirmation message with new sprite
        embed = discord.Embed(
            title="Avatar Changed!",
            description=f"Your trainer avatar has been updated to **{new_sprite}**.",
            color=discord.Color.green()
        )
        
        sprite_url = f"https://play.pokemonshowdown.com/sprites/trainers/{new_sprite}.png"
        embed.set_image(url=sprite_url)
        
        await ctx.send(embed=embed)
    
    except Exception as e:
        error_embed = discord.Embed(
            title="Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red()
        )
        await ctx.send(embed=error_embed)

@client.command(aliases=["setpartner", "sp"])
async def set_partner(ctx, number: int = None):
    """Set a new partner Pokémon from your caught Pokémon."""
    
    user_id = str(ctx.author.id)
    
    try:
        # Check if user exists in MongoDB
        user_data = inventory_collection.find_one({"_id": user_id})
        
        # Check if user has an account
        if not user_data:
            await ctx.send("You have not begun your adventure! Start by using the `%start` command.")
            return
            
        # Get the list of caught Pokémon
        caught_id_list = user_data.get("caught_pokemon", [])
        
        # If no Pokémon are caught, inform the user
        if not caught_id_list:
            await ctx.send("You haven't caught any Pokémon yet! Use the `%search` command to find and catch Pokémon.")
            return
            
        # If no number is provided, show a list of caught Pokémon
        if number is None:
            # Create an embed with instructions
            embed = discord.Embed(
                title="🔄 Set a New Partner",
                description="Choose one of your Pokémon to be your new adventure buddy!",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="📋 How to Use",
                value="Use `%setpartner [number]` with the Pokémon's box number.\nExample: `%sp 3` to set your 3rd Pokémon as partner.",
                inline=False
            )
            
            embed.add_field(
                name="📦 Your Pokémon",
                value="Check your Pokémon with the `%box` command to see their numbers.",
                inline=False
            )
            
            # Show current partner if one exists
            current_partner_id = user_data.get("partner_pokemon")
            if current_partner_id:
                current_partner = pokemon_collection.find_one({"_id": current_partner_id})
                
                if current_partner:
                    current_name = current_partner["name"].capitalize().replace('-', ' ')
                    current_nickname = current_partner.get("nickname")
                    current_shiny = current_partner["shiny"]
                    
                    if current_nickname:
                        current_display = f"{current_nickname} ({current_name})"
                    else:
                        current_display = current_name
                        
                    if current_shiny:
                        current_display += " ⭐"
                        
                    embed.add_field(
                        name="🤝 Current Partner",
                        value=f"Your current partner is: **{current_display}** (Level {current_partner['level']})",
                        inline=False
                    )
            
            await ctx.send(embed=embed)
            return
            
        # Validate the Pokémon number
        total_pokemon = len(caught_id_list)
        if number < 1 or number > total_pokemon:
            error_embed = discord.Embed(
                title="❌ Invalid Pokémon Number",
                description=f"Pokémon #{number} doesn't exist in your box. You have {total_pokemon} Pokémon (numbered 1-{total_pokemon}).",
                color=discord.Color.red()
            )
            await ctx.send(embed=error_embed)
            return
            
        # Get the Pokémon ID and data
        pokemon_id = caught_id_list[number - 1]
        pokemon = pokemon_collection.find_one({"_id": pokemon_id})
        
        if not pokemon:
            await ctx.send("Pokémon data could not be found.")
            return
            
        # Get the current partner for comparison
        current_partner_id = user_data.get("partner_pokemon")
        
        # Check if the selected Pokémon is already the partner
        if pokemon_id == current_partner_id:
            already_embed = discord.Embed(
                title="❓ Already Your Partner",
                description=f"This Pokémon is already your partner!",
                color=discord.Color.gold()
            )
            await ctx.send(embed=already_embed)
            return
            
        # Get Pokémon details for the embed
        name = pokemon["name"].capitalize().replace('-', ' ')
        nickname = pokemon.get("nickname")
        shiny = pokemon["shiny"]
        level = pokemon["level"]
        
        # Format display name
        if nickname:
            display_name = f"{nickname} ({name})"
        else:
            display_name = name
            
        if shiny:
            display_name += " ⭐"
            
        # Get sprite URL
        result = search_pokemon_by_id(pokemon["pokedex_id"])
        sprite_url = await get_best_sprite_url(result, shiny) if result else None
        
        # Get types for color
        type_list = result["types"] if result and "types" in result else []
        type_str = ", ".join([t.capitalize() for t in type_list])
        colour = get_type_colour(type_str.split(',')) if type_str else discord.Color.blue().value
        
        # Create confirmation embed
        confirm_embed = discord.Embed(
            title="🔄 Confirm New Partner",
            description=f"Do you want to set **{display_name}** (Level {level}) as your new partner?",
            color=colour
        )
        
        if sprite_url:
            confirm_embed.set_thumbnail(url=sprite_url)
            
        # Add extra details
        if "ivs" in pokemon and isinstance(pokemon["ivs"], dict):
            total_iv = sum(pokemon["ivs"].values())
            confirm_embed.add_field(name="Total IV", value=f"{total_iv}/186", inline=True)
            
        confirm_embed.add_field(name="Type", value=type_str, inline=True)
        confirm_embed.set_footer(text="React with ✅ to confirm or ❌ to cancel")
            
        # Add reaction options
        confirm_msg = await ctx.send(embed=confirm_embed)
        await confirm_msg.add_reaction("✅")  # Checkmark
        await confirm_msg.add_reaction("❌")  # X mark
        
        # Wait for reaction response
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == confirm_msg.id
            
        try:
            reaction, user = await client.wait_for("reaction_add", timeout=30.0, check=check)
            
            if str(reaction.emoji) == "✅":
                # Update the partner_pokemon field in MongoDB
                inventory_collection.update_one(
                    {"_id": user_id},
                    {"$set": {"partner_pokemon": pokemon_id}}
                )
                
                # Create success embed
                success_embed = discord.Embed(
                    title="✅ Partner Changed!",
                    description=f"**{display_name}** is now your partner Pokémon!",
                    color=discord.Color.green()
                )
                
                if sprite_url:
                    success_embed.set_image(url=sprite_url)
                    
                success_embed.set_footer(text=f"Your partner will gain XP as you chat in Discord")
                
                await ctx.send(embed=success_embed)
            else:
                # User cancelled
                cancel_embed = discord.Embed(
                    title="❌ Partner Change Cancelled",
                    description="You decided to keep your current partner.",
                    color=discord.Color.red()
                )
                
                await ctx.send(embed=cancel_embed)
                
        except asyncio.TimeoutError:
            # Timeout
            timeout_embed = discord.Embed(
                title="⏰ Partner Change Timed Out",
                description="You took too long to respond. Your partner was not changed.",
                color=discord.Color.orange()
            )
            
            await ctx.send(embed=timeout_embed)
            
    except Exception as e:
        error_embed = discord.Embed(
            title="Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red()
        )
        await ctx.send(embed=error_embed)


@client.command(aliases=["settings", "prefs"])
async def set_preferences(ctx, setting=None, value=None):
    user_id = str(ctx.author.id)
    
    # Get user data or initialize if not exists
    user_data = inventory_collection.find_one({"_id": user_id})
    if not user_data:
        await ctx.send("You haven't started your adventure yet. Use `%start` to begin!")
        return
    
    # Initialize settings if they don't exist
    if "settings" not in user_data:
        inventory_collection.update_one(
            {"_id": user_id},
            {"$set": {
                "settings": {
                    "environment_rendering": "off"  # off, static, animated
                }
            }}
        )
        user_data = inventory_collection.find_one({"_id": user_id})
    
    # If no setting specified, show current settings
    if not setting:
        settings = user_data.get("settings", {})
        embed = discord.Embed(
            title="🔧 User Preferences",
            description="Your current preference settings:",
            color=discord.Color.blue()
        )
        
        # Environment rendering setting
        env_setting = settings.get("environment_rendering", "off")
        if env_setting == "off":
            env_desc = "Off (Standard sprites only)"
        elif env_setting == "static":
            env_desc = "Static (Efficient mode with background)"
        elif env_setting == "animated":
            env_desc = "Animated (May be slower but supports GIFs)"
        
        embed.add_field(
            name="Environment Rendering",
            value=f"Currently: **{env_desc}**\n" +
                  "Change with: `%settings environment static`",
            inline=False
        )
        
        embed.set_footer(text="Use %settings environment [off/static/animated]")
        await ctx.send(embed=embed)
        return
    
    # Handle environment_rendering setting
    if setting.lower() in ["environment", "env", "background"]:
        valid_values = ["off", "static", "animated"]
        
        if not value or value.lower() not in valid_values:
            await ctx.send(f"Invalid value. Please choose from: {', '.join(valid_values)}")
            return
        
        # Update the setting in the database
        inventory_collection.update_one(
            {"_id": user_id},
            {"$set": {"settings.environment_rendering": value.lower()}}
        )
        
        # Confirmation message with descriptions
        mode_descriptions = {
            "off": "Standard sprites without backgrounds",
            "static": "Static sprites with backgrounds (efficient)",
            "animated": "Animated sprites with backgrounds (may be slower)"
        }
        
        embed = discord.Embed(
            title="✅ Setting Updated",
            description=f"Environment Rendering is now set to: **{value.lower()}**\n" +
                        f"({mode_descriptions[value.lower()]})",
            color=discord.Color.green()
        )
        
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"Unknown setting: {setting}. Available settings: environment")

@client.command()
async def partner(ctx):
    user_id = str(ctx.author.id)
    
    try:
        # Fetch user data from MongoDB
        user_data = inventory_collection.find_one({"_id": user_id})
        
        if not user_data:
            await ctx.send("You haven't started your adventure yet. Use `%start` to begin!")
            return
        
        partner_id = user_data.get("partner_pokemon")
        
        if not partner_id:
            await ctx.send("You don't have a partner Pokémon yet!")
            return
        
        # Fetch partner Pokémon data from MongoDB
        partner_pokemon = pokemon_collection.find_one({"_id": partner_id})
        
        if not partner_pokemon:
            await ctx.send("Your partner Pokémon's data could not be found.")
            return
        
        name = partner_pokemon["name"].capitalize()
        nickname = partner_pokemon.get("nickname")
        level = partner_pokemon["level"]
        xp = partner_pokemon.get("xp", 0)
        pokemon_id = partner_pokemon["pokedex_id"]
        shiny = partner_pokemon["shiny"]
        
        # Calculate XP required for the next level
        next_level_xp = int((6/5) * ((level + 1)**3) - (15 * ((level + 1)**2)) + (100 * (level + 1)) - 140)
        xp_needed = next_level_xp - xp
        
        # Create embed
        embed = discord.Embed(title=f"{nickname} ({name})" if nickname else name, color=discord.Color.blue())
        embed.add_field(name="Level", value=level, inline=True)
        embed.add_field(name="XP", value=f"{xp}/{next_level_xp} (Need {xp_needed} more)", inline=True)
        
        # Get sprite URL
        result = search_pokemon_by_id(pokemon_id)
        if result:
            sprite_url = await get_best_sprite_url(result, shiny)
            if sprite_url:
                embed.set_thumbnail(url=sprite_url)
        
        # Add shiny indicator
        if shiny:
            embed.set_footer(text="⭐ This Pokémon is shiny!")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red()
        )
        await ctx.send(embed=error_embed)

@client.command(aliases=["pd", "dex"])
async def pokedex(ctx, *, pokemon):
    try:
        if pokemon.isdigit():
            pokemon = int(pokemon)
            results = db.pokemon.find_one({"id": pokemon})
        else:
            pokemon = pokemon.lower().replace(' ', '-')
            results = db.pokemon.find_one({"name": pokemon})

        if not results:
            error_embed = discord.Embed(
                title="Pokémon Not Found",
                description=f"No data found for '{pokemon}'. Please check the spelling or ID.",
                color=discord.Color.red()
            )
            await ctx.send(embed=error_embed)
            return

        id = results["id"]
        name = results["name"].capitalize().replace('-', ' ')
        type_list = [t.capitalize() for t in results["types"]]
        type_str = " | ".join(type_list)
        sprite_url = await get_best_sprite_url(results, False)
        evolution_line = results["evolution_line"]
        next_evolution = get_next_evolution(evolution_line, results["name"]).capitalize()
        description = results["description"].replace("\n", " ").replace("POK\u00e9MON", "Pokémon")
        colour = get_type_colour(type_list)

        embed = discord.Embed(title=f"#{id} {name}", colour=colour)
        embed.set_thumbnail(url=sprite_url)
        embed.add_field(name="Type", value=type_str, inline=False)
        embed.add_field(name="Next Evolution", value=next_evolution if next_evolution != "-" else "Final Form", inline=True)
        embed.add_field(name="Base Stats", value="\n".join([f"{stat.capitalize()}: {value}" for stat, value in results["stats"].items()]), inline=True)
        embed.add_field(name="Description", value=description, inline=False)
        
        if "height" in results and "weight" in results:
            embed.add_field(name="Height", value=f"{results['height']/10} m", inline=True)
            embed.add_field(name="Weight", value=f"{results['weight']/10} kg", inline=True)
        
        if "abilities" in results:
            abilities = " | ".join(results["abilities"])
            embed.add_field(name="Abilities", value=abilities, inline=False)

        embed.set_footer(text=f"Pokédex Entry • Requested by {ctx.author}")

        await ctx.send(embed=embed)

    except Exception as e:
        error_embed = discord.Embed(
            title="Error",
            description=f"An error occurred while retrieving Pokédex data: {str(e)}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        

@client.command(aliases=["mv"])
async def move(ctx, *, move_name):
    try:
        move = move_name.lower().replace(' ', '-')
        
        # Query MongoDB for the move
        results = move_collection.find_one({"name": move})
        
        if not results:
            error_embed = discord.Embed(
                title="Move Not Found",
                description=f"Move '{move_name}' could not be found in the database.",
                color=discord.Color.red()
            )
            await ctx.send(embed=error_embed)
            return
        
        id = results.get("id", "Unknown")
        name = results.get("name", "Unknown").capitalize().replace('-', ' ')
        type = results.get("type", "Unknown").capitalize()
        pp = results.get("pp", "Unknown")
        power = results.get("power", "Unknown")
        accuracy = results.get("accuracy", "Unknown")
        effect = results.get("effect", "Unknown")
        short_effect = results.get("short_effect", "Unknown")
        
        MVembed = discord.Embed(title=f"{name} - Move ID {id}", colour=0xffffff)
        MVembed.add_field(name="Type", value=type, inline=True)
        MVembed.add_field(name="Power", value=power, inline=True)
        MVembed.add_field(name="PP", value=pp, inline=True)
        MVembed.add_field(name="Accuracy", value=accuracy, inline=True)
        MVembed.add_field(name="Effect", value=effect, inline=False)
        MVembed.add_field(name="Short Effect", value=short_effect, inline=False)
        MVembed.set_footer(text=f"Move Entry retrieval by {ctx.author}")
        
        await ctx.send(embed=MVembed)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="Error",
            description=f"An error occurred while retrieving move data: {str(e)}",
            color=discord.Color.red()
        )
        await ctx.send(embed=error_embed)

async def process_search(ctx, temp_message):
    try:
        user_data = inventory_collection.find_one({"_id": str(ctx.author.id)})
        if not user_data:
            error_embed = discord.Embed(
                title="No User Data",
                description="You have not started your adventure! Use `%start` to begin.",
                color=discord.Color.red()
            )
            await temp_message.edit(embed=error_embed)
            return

        user_settings = user_data.get("settings", {})
        environment_mode = user_settings.get("environment_rendering", "off")

        # Get your ball counts and validate that the user has at least one ball.
        pokeballs = user_data.get("Pokeballs", 0)
        greatballs = user_data.get("Greatballs", 0)
        ultraballs = user_data.get("Ultraballs", 0)
        masterballs = user_data.get("Masterballs", 0)
        if pokeballs <= 0 and greatballs <= 0 and ultraballs <= 0 and masterballs <= 0:
            error_embed = discord.Embed(
                title="No Pokéballs",
                description="You don't have any Pokéballs! You need to buy some first.",
                color=discord.Color.red()
            )
            await temp_message.edit(embed=error_embed)
            return

        # ------------------
        # Heavy Processing:
        # ------------------
        # Choose a wild Pokémon
        results, shiny = choose_random_wild(normal_ID_list, mythical_ID_list, legendary_ID_list)
        level = random.randint(3, 20)
        type_str = ", ".join([t.capitalize() for t in results["types"]])
        colour = get_type_colour(type_str.split(','))
        name = results["name"].capitalize().replace('-', ' ')

        # Get sprite URL using environment settings (this call awaits on network I/O)
        sprite_url = await get_best_sprite_url(results, shiny, environment_mode)
    
        image_buffer = None
        is_animated = False
        if environment_mode in ["static", "animated"] and sprite_url:
            is_animated_allowed = (environment_mode == "animated")
            # Use your image generation function to produce a composite encounter image
            image_buffer, is_animated = await generate_encounter_image(
                sprite_url=sprite_url,
                background_folder="assets/backgrounds",
                static_sprite_scale=0.4,
                animated_sprite_scale=1.0,
                position="center-bottom",
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

        # Send final message with embed and view.
        if environment_mode in ["static", "animated"] and image_buffer:
            SHembed_editor = await ctx.send(embed=SHembed, file=generated_file, view=view)
            await temp_message.delete()
            view.is_using_attachment = True
        else:
            SHembed_editor = await ctx.send(embed=SHembed, view=view)
            view.original_sprite_url = sprite_url

        view.SHembed_editor = SHembed_editor

        # Wait for the encounter interaction to complete (this is another await on view.wait())
        code, catch_result, catch, rate, earnings = await search_cmd_handler(client, ctx, active_catchers, view=view)

        if catch_result is True:
            # Generate nature (with synchronize ability consideration if applicable)
            partner_nature = None
            has_synchronize = False
            
            if "partner_pokemon" in user_data and user_data["partner_pokemon"]:
                partner = pokemon_collection.find_one({"_id": user_data["partner_pokemon"]})
                if partner:
                    partner_nature = partner.get("nature")
                    partner_pokemon_data = search_pokemon_by_id(partner["pokedex_id"])
                    if partner_pokemon_data and "abilities" in partner_pokemon_data:
                        has_synchronize = "synchronize" in [a.get("name", "").lower() for a in partner_pokemon_data.get("abilities", [])]
            
            # Store the caught Pokémon
            from pokemon_stat_generation import generate_nature, generate_iv, calculate_stat, generate_ability
            
            # Get nature (with synchronize consideration if implemented)
            nature = generate_nature()
            
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
                    "hp": calculate_stat(results["stats"]["hp"], ivs["hp"], level),
                    "attack": calculate_stat(results["stats"]["attack"], ivs["attack"], level),
                    "defense": calculate_stat(results["stats"]["defense"], ivs["defense"], level),
                    "special-attack": calculate_stat(results["stats"]["special-attack"], ivs["special-attack"], level),
                    "special-defense": calculate_stat(results["stats"]["special-defense"], ivs["special-defense"], level),
                    "speed": calculate_stat(results["stats"]["speed"], ivs["speed"], level)
                },
                "xp": 0,
                "ability": ability_name
            }
            
            # Insert Pokémon into collection
            pokemon_collection.insert_one(pokemon_doc)
            
            # Add to user's caught Pokémon list
            inventory_collection.update_one(
                {"_id": str(ctx.author.id)},
                {"$push": {"caught_pokemon": unique_id}}
            )
            
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


@client.command(aliases=["s"])
async def search(ctx):
    # Prevent multiple simultaneous catch encounters for the same user
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
    asyncio.create_task(process_search(ctx, temp_message))
        
# At the top of your file
box_cache = {}
BOX_CACHE_TIMEOUT = 60  # Cache timeout in seconds

@client.command()
async def box(ctx, page: int = 1, user: discord.Member = None):
    if user is None:
        user = ctx.author
    
    user_id = str(user.id)
    
    # Check cache first
    cache_key = f"{user_id}_data"
    current_time = time.time()
    
    if cache_key in box_cache and current_time - box_cache[cache_key]["timestamp"] < BOX_CACHE_TIMEOUT:
        user_data = box_cache[cache_key]["data"]
    else:
        user_data = inventory_collection.find_one({"_id": user_id})
        if user_data:
            box_cache[cache_key] = {
                "data": user_data,
                "timestamp": current_time
            }
    
    if not user_data:
        await ctx.send("You have not begun your adventure! Start by using the `%start` command.")
        return
    
    caught_id_list = user_data.get("caught_pokemon", [])
    
    if not caught_id_list:
        await ctx.send("You have not caught any Pokémon! Try using the `%search` command.")
        return
    
    total_pokemon = len(caught_id_list)
    pokemon_per_page = 12
    total_pages = max(1, (total_pokemon + pokemon_per_page - 1) // pokemon_per_page)
    current_page = max(1, min(page, total_pages))
    
    color_seed = int(user.id) % 0xFFFFFF
    box_color = discord.Colour(color_seed)
    
    # Cache for Pokémon data by page
    async def get_page_embed(page_num):
        # Check if page data is cached
        page_cache_key = f"{user_id}_page_{page_num}"
        if page_cache_key in box_cache and current_time - box_cache[page_cache_key]["timestamp"] < BOX_CACHE_TIMEOUT:
            return box_cache[page_cache_key]["embed"]
        
        start_idx = (page_num - 1) * pokemon_per_page
        end_idx = min(start_idx + pokemon_per_page, total_pokemon)
        current_page_pokemon_ids = caught_id_list[start_idx:end_idx]
        
        # Bulk fetch all Pokémon for this page
        pokemon_list = list(pokemon_collection.find({"_id": {"$in": current_page_pokemon_ids}}))
        pokemon_dict = {pokemon["_id"]: pokemon for pokemon in pokemon_list}
        
        embed = discord.Embed(
            title=f"🎒 {user.name}'s Pokémon Box",
            description=f"Page {page_num}/{total_pages}",
            color=box_color
        )
        
        for i, pokemon_id in enumerate(current_page_pokemon_ids):
            if pokemon_id in pokemon_dict:
                pokemon = pokemon_dict[pokemon_id]
                name = pokemon["name"].capitalize().replace('-', ' ')
                nickname = pokemon.get("nickname")
                shiny = pokemon["shiny"]
                level = pokemon["level"]
                global_number = start_idx + i + 1
                display_name = f"{nickname} ({name})" if nickname else name
                if shiny:
                    display_name = f"⭐ {display_name}"
                total_iv = sum(pokemon["ivs"].values()) if "ivs" in pokemon else 0
                iv_percentage = round((total_iv / 186) * 100, 2)
                field_name = f"`#{global_number:03d}` {display_name}"
                value = f"Lv. {level} | IV: {iv_percentage}%"
                embed.add_field(name=field_name, value=value, inline=True)
        
        embed.set_footer(text="Use reactions to navigate | %view [number] for details")
        
        # Cache the embed
        box_cache[page_cache_key] = {
            "embed": embed,
            "timestamp": current_time
        }
        
        return embed

@client.command(aliases=["v", "info", "pokemon"])
async def view(ctx, number: int = None, user: discord.Member = None):
    if user is None:
        user = ctx.author

    user_id = str(user.id)

    # If no number provided, show usage instructions
    if number is None:
        usage_embed = discord.Embed(
            title="Pokemon View Command Usage",
            description="Use this command to view detailed information about a specific Pokemon in your box.",
            color=discord.Colour.blue()
        )
        usage_embed.add_field(
            name="How to Use",
            value="`%view [number]` - View details of Pokemon by its box number\n" +
                "Example: `%view 7` to view Pokemon #7\n\n" +
                "You can find Pokemon numbers in your box view (`%box` command).\n" +
                "Each Pokemon is numbered sequentially across all pages.",
            inline=False
        )
        usage_embed.add_field(
            name="Alternatives",
            value="You can also use `%v`, `%info`, or `%pokemon` instead of `%view`.",
            inline=False
        )
        await ctx.send(embed=usage_embed)
        return

    # Fetch user data from MongoDB
    user_data = inventory_collection.find_one({"_id": user_id})
    
    if not user_data:
        await ctx.send("You have not begun your adventure! Start by using the `%start` command.")
        return
    
    caught_id_list = user_data.get("caught_pokemon", [])
    
    if not caught_id_list:
        await ctx.send("You have not caught any pokemon! Try using the `%s` command")
        return

    total_pokemon = len(caught_id_list)

    # Validate the number
    if number < 1 or number > total_pokemon:
        await ctx.send(f"Pokemon #{number} doesn't exist in your box. You have {total_pokemon} Pokemon (numbered 1-{total_pokemon}).")
        return

    # Get the Pokemon unique ID (adjusting for 0-based indexing)
    pokemon_id = caught_id_list[number - 1]
    pokemon = pokemon_collection.find_one({"_id": pokemon_id})

    if not pokemon:
        await ctx.send("Pokemon data could not be found.")
        return

    # Calculate which page this Pokemon is on (for reference)
    pokemon_per_page = 12
    page = ((number - 1) // pokemon_per_page) + 1

    # Get Pokemon details
    name = pokemon["name"].capitalize().replace('-', ' ')
    nickname = pokemon.get("nickname")
    shiny = pokemon["shiny"]
    level = pokemon["level"]
    result = search_pokemon_by_id(pokemon["pokedex_id"])

    # Format display name with original species in parentheses
    if nickname:
        display_name = f"{nickname} ({name})"
    else:
        display_name = name

    # Add shiny star if needed
    if shiny:
        display_name = f"{display_name} ⭐"

    # Get sprite URL from the original Pokemon data
    sprite_url = await get_best_sprite_url(result, shiny) if result else None

    # Get types and color from the original Pokemon data
    type_list = result["types"] if result and "types" in result else []
    type_str = ", ".join([t.capitalize() for t in type_list])
    colour = get_type_colour(type_str.split(','))

    # Create embed
    view_embed = discord.Embed(
        title=f"{display_name} - Level {level}",
        color=colour
    )

    if sprite_url:
        view_embed.set_image(url=sprite_url)

    # Add Pokemon info
    view_embed.add_field(name="Type", value=type_str or "Unknown", inline=True)
    view_embed.add_field(name="Pokedex ID", value=f"#{pokemon['pokedex_id']}", inline=True)
    view_embed.add_field(name="Unique ID", value=pokemon_id, inline=True)

    # Add IVs if available
    if "ivs" in pokemon and isinstance(pokemon["ivs"], dict):
        ivs = pokemon["ivs"]
        final_stats = pokemon["final_stats"]
        stats_str = ""
        total_iv = 0
        for stat, value in final_stats.items():
            iv = ivs[stat]
            stats_str += f"{stat.capitalize()}: {value} (IV: {iv})\n"
            total_iv += iv
        view_embed.add_field(name="Stats (Final / IV)", value=stats_str, inline=False)
        view_embed.add_field(name="Total IV", value=f"{total_iv}/186", inline=True)

    # Add moves if available
    if "moves" in pokemon and isinstance(pokemon["moves"], list) and len(pokemon["moves"]) > 0:
        moves_str = ", ".join([m.capitalize().replace('-', ' ') for m in pokemon["moves"]])
        view_embed.add_field(name="Moves", value=moves_str, inline=False)

    # Add the description if available
    if "description" in result:
        description = result["description"].replace("\n", " ")
        view_embed.add_field(name="Description", value=description, inline=False)

    # Add evolution information if available
    if "evolution_line" in result:
        evolution_line = result["evolution_line"]
        next_evolution = get_next_evolution(evolution_line, pokemon["name"]).capitalize()
        view_embed.add_field(name="Evolves Into", value=next_evolution, inline=True)

    view_embed.set_footer(text=f"Caught by {user.name} | Use '%box {page}' to return to the box view")

    await ctx.send(embed=view_embed)

@client.command(aliases=["bal"])
async def balance(ctx):
    user_id = str(ctx.author.id)
    user_data = inventory_collection.find_one({"_id": user_id})
    
    if not user_data:
        await ctx.send("You haven't started your adventure yet. Use `%start` to begin!")
        return
    
    balance = user_data.get("Pokedollars", 0)
    
    embed = discord.Embed(
        title="🪙 Your Balance",
        description=f"You currently have **{balance:,} Pokedollars**!",
        color=discord.Color.gold()
    )
    embed.set_footer(text=f"Requested by {ctx.author.name}")
    
    await ctx.send(embed=embed)

@client.command(aliases=["pm", "mart"])
async def pokemart(ctx, buy=None, item=None, amount: int = 1):
    user_id = str(ctx.author.id)
    user_data = inventory_collection.find_one({"_id": user_id})
    
    if not user_data:
        await ctx.send("You haven't started your adventure yet. Use `%start` to begin!")
        return
    
    if buy in ["buy", "b"]:
        pokedollars = user_data.get("Pokedollars", 0)
        
        item_data = {
            "pokeball": {"cost": 100, "field": "Pokeballs"},
            "greatball": {"cost": 250, "field": "Greatballs"},
            "ultraball": {"cost": 600, "field": "Ultraballs"}
        }
        
        if item.lower() not in item_data:
            await ctx.send("Invalid item. Please choose pokeball, greatball, or ultraball.")
            return
        
        item_info = item_data[item.lower()]
        cost = item_info["cost"] * amount
        
        if cost > pokedollars:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You need {cost:,} Pokedollars to buy {amount} {item}(s). You only have {pokedollars:,} Pokedollars!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        inventory_collection.update_one(
            {"_id": user_id},
            {
                "$inc": {
                    "Pokedollars": -cost,
                    item_info["field"]: amount
                }
            }
        )
        
        embed = discord.Embed(
            title="✅ Purchase Successful",
            description=f"You purchased {amount} {item}(s) for {cost:,} Pokedollars.",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Your new balance: {pokedollars - cost:,} Pokedollars")
        await ctx.send(embed=embed)
    
    else:
        embed = discord.Embed(title="🏪 Pokemart", color=discord.Color.blue())
        embed.add_field(name="Pokeballs", value="Cost: 100 Pokedollars", inline=False)
        embed.add_field(name="Greatballs", value="Cost: 250 Pokedollars", inline=False)
        embed.add_field(name="Ultraballs", value="Cost: 600 Pokedollars", inline=False)
        embed.set_footer(text="Use '%pokemart buy <item> <amount>' to purchase")
        await ctx.send(embed=embed)

client.run(os.getenv('API_Key'))