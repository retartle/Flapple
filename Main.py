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
import asyncio

load_dotenv()

Admins = [786083062172745770]

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
    print('Flapple is online, Wild pokemon pool initialized.')

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

    with open("Inventory.json", "r+") as file:
        try:
            data = json.load(file)
        except json.JSONDecodeError:
            data = {"users": {}}

        if "users" not in data:
            data = {"users": {}}

        if "users" in data and user_id in data["users"]:
            partner_id = data["users"][user_id]["partner_pokemon"]
            if partner_id:
                with open("caught_pokemon_data.json", 'r+') as caught_file:
                    try:
                        caught_data = json.load(caught_file)
                    except json.JSONDecodeError:
                        caught_data = {}

                    if partner_id in caught_data:
                        caught_data[partner_id]["xp"] = caught_data[partner_id].get("xp", 0) + xp_reward
                        level = caught_data[partner_id]["level"]
                        xp = caught_data[partner_id]["xp"]
                        next_level_xp = int((6/5) * ((level + 1)**3) - (15 * ((level + 1)**2)) + (100 * (level + 1)) - 140)

                        if xp >= next_level_xp:
                            excess_xp = xp - next_level_xp #calculate excess xp
                            caught_data[partner_id]["level"] += 1
                            caught_data[partner_id]["xp"] = excess_xp #carry over excess xp
                            await message.channel.send(f"{message.author.mention}'s partner, {caught_data[partner_id]['name'].capitalize()}, leveled up to level {level + 1}!")
                        caught_file.seek(0)
                        json.dump(caught_data, caught_file, indent=1)
                        caught_file.truncate()

            file.seek(0)
            json.dump(data, file, indent=1)
            file.truncate()

        await client.process_commands(message)

@client.command()
async def ping(ctx):
    await ctx.send(f'The current ping is {round(client.latency * 1000)}ms!')

@client.command()
async def start(ctx):
    inventory_file = "Inventory.json"
    # Ensure the file exists with the correct structure
    if not os.path.exists(inventory_file):
        with open(inventory_file, 'w') as file:
            json.dump({"users": {}}, file)

    try:
        with open(inventory_file, 'r+') as file:
            data = json.load(file)
            if "users" not in data:
                data = {"users": {}}

            if str(ctx.author.id) not in data["users"]:
                # New user setup
                data["users"][str(ctx.author.id)] = {
                    "Pokeballs": 20,
                    "Greatballs": 0,
                    "Ultraballs": 0,
                    "Masterballs": 0,
                    "Pokedollars": 10000,
                    "caught_pokemon": [],
                    "partner_pokemon": None
                }

                # Import our new module for starter selection
                import starter_functions

                chosen_generation = None
                chosen_starter = None

                # Outer loop: allow the user to reselect generation if needed
                while chosen_starter is None:
                    chosen_generation = await starter_functions.select_generation(ctx, client, starter_pokemon_generations)
                    if chosen_generation is None:
                        return # Generation selection timed out

                    chosen_starter = await starter_functions.preview_and_select_starter(ctx, client, chosen_generation, starter_pokemon_generations)
                    if chosen_starter is None:
                        # User opted to reselect generation; loop again
                        continue

                # Set and store the chosen starter as the user's partner Pokémon
                full_pokemon_data = search_pokemon_by_id(chosen_starter["id"])
                is_shiny = random.choices([True, False], weights=[1, 4095], k=1)[0]
                unique_id = starter_functions.store_caught_pokemon(full_pokemon_data, str(ctx.author.id), is_shiny, 5)
                data["users"][str(ctx.author.id)]["caught_pokemon"].append(unique_id)
                data["users"][str(ctx.author.id)]["partner_pokemon"] = unique_id

                # Create and send the starter summary embed
                starter_embed = await starter_functions.create_starter_summary_embed(ctx, chosen_starter, full_pokemon_data, unique_id, is_shiny)
                await ctx.send(embed=starter_embed)
                
                # Add nickname prompt
                nickname_embed = discord.Embed(
                    title="Name Your Starter Pokémon",
                    description=f"Would you like to nickname your new {chosen_starter['name']}? Type a name or 'no' to skip.",
                    color=discord.Color.blue()
                )
                nickname_embed.set_footer(text="You have 30 seconds to respond")
                await ctx.send(embed=nickname_embed)
                
                # Wait for nickname response
                def check(msg):
                    return msg.author == ctx.author and msg.channel == ctx.channel and not msg.content.startswith("%")
                
                try:
                    nickname_msg = await client.wait_for("message", check=check, timeout=30.0)
                    nickname = nickname_msg.content.strip()
                    
                    # Skip if user declines
                    if nickname.lower() in ["no", "n", "skip"]:
                        skip_embed = discord.Embed(
                            title="Nickname Skipped",
                            description=f"Keeping the name as {chosen_starter['name']}!",
                            color=discord.Color.blue()
                        )
                        await ctx.send(embed=skip_embed)
                    else:
                        # Try to rename the Pokemon
                        if await rename_pokemon(ctx, unique_id, nickname):
                            success_embed = discord.Embed(
                                title="Pokémon Nicknamed",
                                description=f"Successfully renamed your {chosen_starter['name']} to \"{nickname}\"!",
                                color=discord.Color.green()
                            )
                            await ctx.send(embed=success_embed)
                
                except asyncio.TimeoutError:
                    timeout_embed = discord.Embed(
                        title="Nickname Timed Out",
                        description=f"No nickname was provided in time. Keeping the name as {chosen_starter['name']}!",
                        color=discord.Color.orange()
                    )
                    await ctx.send(embed=timeout_embed)

                file.seek(0)
                json.dump(data, file, indent=1)
                file.truncate()

                await ctx.send(f"Your adventure has just begun, Trainer {ctx.author.name}! You have received 20 Pokeballs and 10000 Pokedollars. Use `%search` to find a wild Pokémon!")
            else:
                await ctx.send("You have already begun your adventure! Start searching for wild Pokémon using `%search`")

    except json.JSONDecodeError:
        print("Error loading or saving Inventory.json")
    except FileNotFoundError:
        print("Inventory.json not found")

@client.command(aliases=["setpartner", "sp"])
async def set_partner(ctx, number: int = None):
    """Set a new partner Pokémon from your caught Pokémon."""
    
    # Open and read the user's inventory data
    with open("Inventory.json", "r+") as file:
        data = json.load(file)
        
        # Check if user has an account
        if str(ctx.author.id) not in data["users"]:
            await ctx.send("You have not begun your adventure! Start by using the `%start` command.")
            return
            
        # Get the list of caught Pokémon
        caught_id_list = data["users"][str(ctx.author.id)]["caught_pokemon"]
        
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
            if "partner_pokemon" in data["users"][str(ctx.author.id)] and data["users"][str(ctx.author.id)]["partner_pokemon"]:
                current_partner_id = data["users"][str(ctx.author.id)]["partner_pokemon"]
                current_partner = search_pokemon_by_unique_id(str(current_partner_id))
                
                current_name = current_partner["name"].capitalize().replace('-', ' ')
                current_nickname = current_partner.get("nickname", None)
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
            
        # Get the Pokémon data
        pokemon_id = caught_id_list[number - 1]
        pokemon = search_pokemon_by_unique_id(str(pokemon_id))
        
        # Get the current partner for comparison
        current_partner_id = data["users"][str(ctx.author.id)].get("partner_pokemon", None)
        
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
        nickname = pokemon.get("nickname", None)
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
                # Update the partner_pokemon field
                data["users"][str(ctx.author.id)]["partner_pokemon"] = pokemon_id
                
                # Save the updated data
                file.seek(0)
                json.dump(data, file, indent=1)
                file.truncate()
                
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

@client.command()
async def partner(ctx):
    inventory_file = "Inventory.json"
    caught_file_path = "caught_pokemon_data.json"

    try:
        with open(inventory_file, 'r') as inv_file, open(caught_file_path, 'r') as caught_file:
            inventory_data = json.load(inv_file)
            caught_data = json.load(caught_file)

            user_id = str(ctx.author.id)

            if user_id not in inventory_data["users"]:
                await ctx.send("You haven't started your adventure yet. Use `%start` to begin!")
                return

            if "partner_pokemon" not in inventory_data["users"][user_id] or inventory_data["users"][user_id]["partner_pokemon"] is None:
                await ctx.send("You don't have a partner Pokémon yet!")
                return

            partner_id = inventory_data["users"][user_id]["partner_pokemon"]

            if partner_id not in caught_data:
                await ctx.send("Your partner Pokémon's data could not be found.")
                return

            partner_pokemon = caught_data[partner_id]

            name = partner_pokemon["name"].capitalize()
            level = partner_pokemon["level"]
            xp = partner_pokemon["xp"]
            pokemon_id = partner_pokemon["pokedex_id"]
            shiny = partner_pokemon["shiny"]

            # Calculate XP required for the next level
            next_level_xp = int((6/5) * ((level + 1)**3) - (15 * ((level + 1)**2)) + (100 * (level + 1)) - 140)
            xp_needed = next_level_xp - partner_pokemon["xp"]

            embed = discord.Embed(title=f"{name}'s Info", color=discord.Color.blue())
            embed.add_field(name="Level", value=level, inline=False)
            embed.add_field(name="XP", value=f"{xp}/{next_level_xp} (Need {xp_needed} more)", inline=False)

            # Get sprite URL from local Pokemon data
            result = search_pokemon_by_id(pokemon_id)  # Assuming you have this function
            if result:
                sprite_url = await get_best_sprite_url(result, shiny)
                
            if shiny and sprite_url:
                name = f"{name} ⭐"
                
            if sprite_url:
                embed.set_thumbnail(url=sprite_url)

            await ctx.send(embed=embed)

    except FileNotFoundError:
        await ctx.send("Data files not found. Please contact an administrator.")
    except json.JSONDecodeError:
        await ctx.send("Data files are corrupted. Please contact an administrator.")
    except Exception as e:
        await ctx.send(f"An error occurred: {e}")

@client.command(aliases= ["pd", "dex"])
async def pokedex(ctx,*, pokemon):
    
    if pokemon.isdigit():
        pokemon = int(pokemon)
        results = search_pokemon_by_id(pokemon)
        if not results:     
            await ctx.send(f"Pokemon #'{pokemon}' not found.")
            return

        id = results["id"]
        name = results["name"].capitalize().replace('-', ' ')
        type = ", ".join([t.capitalize() for t in results["types"]])
    
    else:
        pokemon = pokemon.lower().replace(' ', '-')
        results = search_pokemon_by_name(pokemon)
        if not results:     
            await ctx.send(f"Pokemon '{pokemon}' not found.")
            return

        id = results["id"]
        name = results["name"].capitalize().replace('-', ' ')
        type = ", ".join([t.capitalize() for t in results["types"]])
    
    sprite_url = await get_best_sprite_url(results, False)

    evolution_line = results["evolution_line"]
    next_evolution = get_next_evolution(evolution_line,results["name"]).capitalize()

    description = results["description"].replace("\n", " ").replace("POK\u00e9MON", "PokÃ©mon")

    colour = get_type_colour(type.split(","))


    PDembed = discord.Embed (title=f"{name} - Pokedex No. {id}",colour = colour)

    PDembed.set_thumbnail(url=sprite_url)
    PDembed.add_field(name = "Type", value = type, inline=False)
    PDembed.add_field(name = "Evolves into", value = f"{next_evolution}",inline=False)
    PDembed.add_field(name = "Description", value = description, inline=False)
    PDembed.set_footer(text=f"Pokedex Entry retrieval by {ctx.author}")
    await ctx.send(embed=PDembed)
        

@client.command(aliases= ["mv"])
async def move(ctx, *,move_name):
    move = move_name.lower().replace(' ', '-')
    results = search_move_by_name(move)
    if not results:     
        await ctx.send(f"Move '{move}' not found.")
        return

    id = results["id"]
    name = results["name"].capitalize().replace('-', ' ')
    type = results["type"].capitalize()
    pp = results["pp"]
    power = results["power"]
    accuracy = results["accuracy"]
    effect = results["effect"]
    short_effect = results["short_effect"]

    MVembed = discord.Embed (title=f"{name} - Move ID {id}",colour = 0xffffff)
    MVembed.add_field(name = "Type", value = type, inline=True)
    MVembed.add_field(name = "Power", value = power, inline=True)
    MVembed.add_field(name = "PP", value = pp, inline=True)
    MVembed.add_field(name = "Accuracy", value = accuracy, inline=True)
    MVembed.add_field(name = "Effect", value = effect, inline=False)
    MVembed.add_field(name = "Short Effect", value = short_effect, inline=False)
    MVembed.set_footer(text=f"Move Entry retrieval by {ctx.author}")
    await ctx.send(embed=MVembed)


@client.command(aliases=["s"])
async def search(ctx):
    # Check if user is already catching a Pokémon - this happens BEFORE cooldown check
    if ctx.author.id in active_catchers:
        error_embed = discord.Embed(
            title="Error: Already in Battle",
            description="You're already trying to catch a Pokémon! Complete your current encounter first.",
            color=discord.Color.red()
        )
        await ctx.send(embed=error_embed)
        return
    
    # Check if the command is on cooldown manually
    bucket = commands.CooldownMapping.from_cooldown(1, 7, commands.BucketType.user)
    retry_after = bucket.get_bucket(ctx).update_rate_limit()
    if retry_after:
        error_embed = discord.Embed(
            title="Command on Cooldown",
            description=f"Please retry in {round(retry_after)} seconds.",
            color=discord.Color.red()
        )
        await ctx.send(embed=error_embed)
        return
    
    # Add user to active catchers set
    active_catchers.add(ctx.author.id)
    
    try:
        # Existing search code...
        results, shiny = choose_random_wild(normal_ID_list, mythical_ID_list, legendary_ID_list)
        level = random.randint(3, 20)
        type = ", ".join([t.capitalize() for t in results["types"]])
        colour = get_type_colour(type.split(','))
        name = results["name"].capitalize().replace('-', ' ')
        if results:
            sprite_url = await get_best_sprite_url(results, shiny)
            
            if shiny:
                name = f"{name} ⭐"
        
        with open("Inventory.json", "r") as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError:
                data = {"users": {}} #if the file is empty, create the correct structure.

            if "users" in data and str(ctx.author.id) in data["users"]: #check if the users key is present.
                pb = data["users"][str(ctx.author.id)]["Pokeballs"]
                gb = data["users"][str(ctx.author.id)]["Greatballs"]
                ub = data["users"][str(ctx.author.id)]["Ultraballs"]
                mb = data["users"][str(ctx.author.id)]["Masterballs"]
            else:
                await ctx.send("You have not begun your adventure! Start by using the `%start` command.")
                active_catchers.discard(ctx.author.id)
                return
        
        SHembed = discord.Embed (title=f"{ctx.author.name} found a Lvl {level} {name} !",colour = colour)
        SHembed.add_field(name="Select a ball to use", value=f"Number of Pokeballs:{pb}\nNumber of Greatballs:{gb}\nNumber of Ultraballs:{ub}\nNumber of Masterballs:{mb}")
        SHembed.set_footer(text=f"{ctx.author.name}'s Battle")
        SHembed.set_image(url=sprite_url)
        SHembed_editor = await ctx.send(embed=SHembed)
        
        code, catch_result, catch, rate, earnings = await search_cmd_handler(client, ctx, name, SHembed_editor, active_catchers) #can consider removing catch and rate, only there for testing purposes
                
        if code == 0:
            print("Returned with code 0")
        elif catch_result == "ran":
            active_catchers.discard(ctx.author.id)
            return
        elif catch_result:
            await update_embed_title(SHembed_editor, f"{name} was caught! You earned {earnings} Pokedollars")
            unique_id = store_caught_pokemon(results, str(ctx.author.id), shiny, level)
            pokemon = search_pokemon_by_unique_id(unique_id)
            
            # Create initial catch summary embed
            RESULTembed = discord.Embed(title=f"Catch Summary", description=f"Lvl. {pokemon['level']} {name}", colour=colour)
            RESULTembed.set_thumbnail(url=sprite_url)
            RESULTembed.add_field(name="Type", value=type, inline=False)
            for iv_stat in pokemon["ivs"]:
                RESULTembed.add_field(name=f"{iv_stat.capitalize()} IV", value=pokemon["ivs"][iv_stat], inline=True)
            RESULTembed.set_footer(text=f"Caught by {ctx.author} | ID: {pokemon['unique_id']}")
            
            # Send catch summary first
            result_message = await ctx.send(embed=RESULTembed)
            
            # Create nickname prompt embed
            nickname_embed = discord.Embed(
                title="Name Your Pokémon", 
                description=f"Would you like to nickname your new {name}? Type a name or 'no' to skip.", 
                color=discord.Color.blue()
            )
            nickname_embed.set_footer(text="You have 30 seconds to respond")
            await ctx.send(embed=nickname_embed)
            
            # Wait for nickname response
            def check(msg):
                return msg.author == ctx.author and msg.channel == ctx.channel and not msg.content.startswith("%")
            
            try:
                nickname_msg = await client.wait_for("message", check=check, timeout=30.0)
                nickname = nickname_msg.content.strip()
                
                # Skip if user declines
                if nickname.lower() in ["no", "n", "skip"]:
                    skip_embed = discord.Embed(
                        title="Nickname Skipped",
                        description=f"Keeping the name as {name}!",
                        color=discord.Color.blue()
                    )
                    await ctx.send(embed=skip_embed)
                else:
                    # Try to rename the Pokemon
                    if await rename_pokemon(ctx, unique_id, nickname):
                        success_embed = discord.Embed(
                            title="Pokémon Nicknamed",
                            description=f"Successfully renamed your {name} to \"{nickname}\"!",
                            color=discord.Color.green()
                        )
                        await ctx.send(embed=success_embed)
            
            except asyncio.TimeoutError:
                timeout_embed = discord.Embed(
                    title="Nickname Timed Out",
                    description=f"No nickname was provided in time. Keeping the name as {name}!",
                    color=discord.Color.orange()
                )
                await ctx.send(embed=timeout_embed)
        else:
            await update_embed_title(SHembed_editor, f"{name} escaped... It rolled a {catch} but you only had {rate}")
        
    except Exception as e:
        # Remove user from active catchers if an error occurs
        active_catchers.discard(ctx.author.id)
        error_embed = discord.Embed(
            title="Error Occurred",
            description=f"An error occurred during your search: {str(e)}",
            color=discord.Color.red()
        )
        await ctx.send(embed=error_embed)
        
@client.command()
async def box(ctx, page: int = 1, user: discord.Member = None):
    if user == None:
        user = ctx.author

    with open("Inventory.json", "r") as file:
        data = json.load(file)
        if str(user.id) not in data["users"]:
            await ctx.send("You have not begun your adventure! Start by using the `%start` command.")
            return
        elif data["users"][str(user.id)]["caught_pokemon"] == []:
            await ctx.send("You have not caught any pokemon! Try using the `%s` command")
            return

        caught_id_list = data["users"][str(user.id)]["caught_pokemon"]

        # Calculate total pages needed (12 pokemon per page)
        total_pokemon = len(caught_id_list)
        pokemon_per_page = 12
        total_pages = max(1, (total_pokemon + pokemon_per_page - 1) // pokemon_per_page) # Ceiling division

        # Generate a fixed color for this user's box
        # Using the user ID ensures same user always gets same color
        color_seed = int(user.id) % 0xFFFFFF
        box_color = discord.Colour(color_seed)

        # Validate and limit page number
        current_page = max(1, min(page, total_pages))

        # Function to get embed for a specific page
        def get_page_embed(page_num):
            start_idx = (page_num - 1) * pokemon_per_page
            end_idx = min(start_idx + pokemon_per_page, total_pokemon)
            current_page_pokemon = caught_id_list[start_idx:end_idx]

            embed = discord.Embed(
                title=f"{user.name}'s Pokemon Box - Page {page_num}/{total_pages}",
                color=box_color # Using the fixed color for consistency
            )

            for i, pokemon_id in enumerate(current_page_pokemon):
                pokemon = search_pokemon_by_unique_id(str(pokemon_id))
                name = pokemon["name"].capitalize().replace('-', ' ')
                nickname = pokemon.get("nickname", None)
                shiny = pokemon["shiny"]
                level = pokemon["level"]
                
                # Calculate the global number
                global_number = start_idx + i + 1
                
                # Format display name with nickname and original species
                if nickname:
                    display_name = f"{nickname} ({name})"
                else:
                    display_name = name
                
                # Add shiny star at the end
                if shiny:
                    display_name = f"{display_name} ⭐"
                
                # Remove the separate species field since we're showing it in the name now
                value = f"Level: {level}"
                
                # Add IV total if available
                if "ivs" in pokemon and isinstance(pokemon["ivs"], dict):
                    total_iv = sum(pokemon["ivs"].values())
                    value += f" | IV: {total_iv}/186"
                
                # Add the global number to the name for easier reference
                field_name = f"#{global_number}. {display_name}"
                embed.add_field(name=field_name, value=value, inline=True)

            embed.set_footer(text=f"Page {page_num}/{total_pages} | Use reactions to navigate | Use '%view [number]' to view details")
            return embed

        # Send initial embed
        message = await ctx.send(embed=get_page_embed(current_page))

        # Don't add reactions if there's only one page
        if total_pages <= 1:
            return

        # Add navigation reactions
        reactions = ['⏪', '⬅️', '➡️', '⏩']
        for reaction in reactions:
            await message.add_reaction(reaction)

        # Define check function for reactions
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in reactions and reaction.message.id == message.id

        # Reaction handler
        while True:
            try:
                reaction, user = await client.wait_for('reaction_add', timeout=60.0, check=check)
                
                # Remove user's reaction
                await message.remove_reaction(reaction, user)
                
                # Update page based on reaction
                if str(reaction.emoji) == '⬅️' and current_page > 1:
                    current_page -= 1
                    await message.edit(embed=get_page_embed(current_page))
                elif str(reaction.emoji) == '➡️' and current_page < total_pages:
                    current_page += 1
                    await message.edit(embed=get_page_embed(current_page))
                elif str(reaction.emoji) == '⏪': # First page
                    current_page = 1
                    await message.edit(embed=get_page_embed(current_page))
                elif str(reaction.emoji) == '⏩': # Last page
                    current_page = total_pages
                    await message.edit(embed=get_page_embed(current_page))
            except asyncio.TimeoutError:
                # Remove reactions after timeout
                try:
                    await message.clear_reactions()
                except:
                    pass # If bot doesn't have permissions to clear reactions
                break


@client.command(aliases=["v", "info", "pokemon"])
async def view(ctx, number: int = None, user: discord.Member = None):
    if user == None:
        user = ctx.author

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

    with open("Inventory.json", "r") as file:
        data = json.load(file)
        if str(user.id) not in data["users"]:
            await ctx.send("You have not begun your adventure! Start by using the `%start` command.")
            return
        elif data["users"][str(user.id)]["caught_pokemon"] == []:
            await ctx.send("You have not caught any pokemon! Try using the `%s` command")
            return

        caught_id_list = data["users"][str(user.id)]["caught_pokemon"]
        total_pokemon = len(caught_id_list)

        # Validate the number
        if number < 1 or number > total_pokemon:
            await ctx.send(f"Pokemon #{number} doesn't exist in your box. You have {total_pokemon} Pokemon (numbered 1-{total_pokemon}).")
            return

        # Get the Pokemon unique ID (adjusting for 0-based indexing)
        pokemon_id = caught_id_list[number - 1]
        pokemon = search_pokemon_by_unique_id(str(pokemon_id))

        # Calculate which page this Pokemon is on (for reference)
        pokemon_per_page = 12
        page = ((number - 1) // pokemon_per_page) + 1
        position = ((number - 1) % pokemon_per_page) + 1

        # Get Pokemon details
        name = pokemon["name"].capitalize().replace('-', ' ')
        nickname = pokemon.get("nickname", None)  # Get nickname if available
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
        if result:
            sprite_url = await get_best_sprite_url(result, shiny)
        else:
            sprite_url = None

        # Get types and color from the original Pokemon data
        type_list = result["types"] if "types" in result else []
        type_str = ", ".join([t.capitalize() for t in type_list])
        colour = get_type_colour(type_str.split(','))

        # Create embed
        view_embed = discord.Embed(
            title=f"{display_name} - Level {level}",
            color=colour
        )

        # Add sprite as the main image rather than thumbnail for better visibility
        if sprite_url:
            view_embed.set_image(url=sprite_url)

        # Add Pokemon info
        view_embed.add_field(name="Type", value=type_str or "Unknown", inline=True)
        view_embed.add_field(name="Pokedex ID", value=f"#{pokemon['pokedex_id']}" if "pokedex_id" in pokemon else "Unknown", inline=True)
        view_embed.add_field(name="Unique ID", value=pokemon_id, inline=True)

        # Add IVs if available
        if "ivs" in pokemon and isinstance(pokemon["ivs"], dict):
            ivs = pokemon["ivs"]
            iv_str = ""
            total_iv = 0
            for stat, value in ivs.items():
                iv_str += f"{stat.capitalize()}: {value}\n"
                total_iv += value
            view_embed.add_field(name="IVs", value=iv_str, inline=True)
            view_embed.add_field(name="Total IV", value=f"{total_iv}/186", inline=True)

        # Add moves if available
        if "moves" in pokemon and isinstance(pokemon["moves"], list) and len(pokemon["moves"]) > 0:
            moves_str = ", ".join([m.capitalize().replace('-', ' ') for m in pokemon["moves"]])
            view_embed.add_field(name="Moves", value=moves_str, inline=False)

        # Add the description if available
        if "description" in pokemon:
            description = pokemon["description"].replace("\n", " ")
            view_embed.add_field(name="Description", value=description, inline=False)

        # Add evolution information if available
        if "evolution_line" in pokemon:
            evolution_line = pokemon["evolution_line"]
            next_evolution = get_next_evolution(evolution_line, pokemon["name"]).capitalize() if callable(get_next_evolution) else "Unknown"
            view_embed.add_field(name="Evolves Into", value=next_evolution, inline=True)

        # Simplified footer since the original species is now in the title
        view_embed.set_footer(text=f"Caught by {user.name} | Use '%box {page}' to return to the box view")

        await ctx.send(embed=view_embed)

@client.command(aliases = ["bal"])
async def balance(ctx):
    with open("Inventory.json", "r") as file:
        data = json.load(file)
    Balance = data["users"][str(ctx.author.id)]["Pokedollars"]
    await ctx.send(f"You currently have {Balance} Pokedollars!")

@client.command(aliases = ["pm", "mart"])
async def pokemart(ctx, buy = None, item = None, amount = 1):
    if buy in ["buy", "b"]:
        file = open("Inventory.json", "r+")
        data = json.load(file)
        file.seek(0)
        pokedollars = data["users"][str(ctx.author.id)]["Pokedollars"]
        pokeballs = data["users"][str(ctx.author.id)]["Pokeballs"]
        greatballs = data["users"][str(ctx.author.id)]["Greatballs"]
        ultraballs = data["users"][str(ctx.author.id)]["Ultraballs"]
        if item in ["pokeball","pokeballs" ,"pb" ]:
            cost = 100 * amount
            if cost <= pokedollars:
                data["users"][str(ctx.author.id)]["Pokeballs"] = pokeballs + amount
                data["users"][str(ctx.author.id)]["Pokedollars"] = pokedollars - cost
                json.dump(data, file, indent = 1)
                await ctx.send(f"You purchased {amount} Pokeballs for {cost}.")
            else:
                await ctx.send(f"You need {cost} to buy {amount} of Pokeballs. You only have {pokedollars}!")
        elif item in ["greatball","greatballs", "gb"]:
            cost = 250 * amount
            if cost <= pokedollars:
                data["users"][str(ctx.author.id)]["Greatballs"] = greatballs + amount
                data["users"][str(ctx.author.id)]["Pokedollars"] = pokedollars - cost
                json.dump(data, file, indent = 1)
                await ctx.send(f"You purchased {amount} Greatballs for {cost}.")
        elif item in ["ultraball", "ultraballs", "ub"]:
            cost = 600 * amount
            if cost <= pokedollars:
                data["users"][str(ctx.author.id)]["Ultraballs"] = ultraballs + amount
                data["users"][str(ctx.author.id)]["Pokedollars"] = pokedollars - cost
                json.dump(data, file, indent = 1)
                await ctx.send(f"You purchased {amount} Ultraballs for {cost}.")
        else:
            await ctx.send("Not added")
    else:
        Shopembed = discord.Embed (title="Pokemart", colour = discord.Colour.random())
        Shopembed.add_field(name="Pokeballs", value="Cost: 100")
        Shopembed.add_field(name="Greatballs", value="Cost: 250")
        Shopembed.add_field(name="Ultraballs", value="Cost: 600")
        await ctx.send(embed=Shopembed)
        

client.run(os.getenv('API_Key'))