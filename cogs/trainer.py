# cogs/trainer.py
import discord
import asyncio
import time
import random
from discord.ext import commands
from config import inventory_collection, pokemon_collection, unique_id_collection
from utils.db_utils import get_user_data, update_user_data, get_pokemon_data
from utils.pokemon_utils import get_best_sprite_url, generate_nature, generate_iv, calculate_stat, search_pokemon_by_id
from utils.pokemon_utils import generate_ability, calculate_min_xp_for_level, prompt_for_nickname

class TrainerCog(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.trainer_cache = {}
        self.CACHE_TIMEOUT = 300  # 5 minutes
        
        # Dictionary of starter Pokémon by generation
        self.starter_pokemon_generations = {
            1: [1, 4, 7],         # Bulbasaur, Charmander, Squirtle
            2: [152, 155, 158],   # Chikorita, Cyndaquil, Totodile
            3: [252, 255, 258],   # Treecko, Torchic, Mudkip
            4: [387, 390, 393],   # Turtwig, Chimchar, Piplup
            5: [495, 498, 501],   # Snivy, Tepig, Oshawott
            6: [650, 653, 656],   # Chespin, Fennekin, Froakie
            7: [722, 725, 728],   # Rowlet, Litten, Popplio
            8: [810, 813, 816],   # Grookey, Scorbunny, Sobble
            9: [906, 909, 912]    # Sprigatito, Fuecoco, Quaxly
        }
    
    @commands.command()
    async def start(self, ctx):
        """Begin your Pokémon adventure"""
        user_id = str(ctx.author.id)
        
        try:
            # Check if user already exists
            user_data = await get_user_data(user_id)
            
            if user_data:
                await ctx.send("You have already begun your adventure! Start searching for wild Pokémon using `%search`")
                return
            
            # Start the introduction sequence
            message = await self.intro(ctx)
            
            # Let user choose trainer sprite first
            trainer_sprite = await self.select_trainer_sprite(ctx, message)
            
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
                "trainer_sprite": trainer_sprite,
                "settings": {
                    "environment_rendering": "off"
                }
            }
            
            chosen_generation = None
            chosen_starter = None
            
            # Outer loop: allow the user to reselect generation if needed
            while chosen_starter is None:
                chosen_generation = await self.select_generation(ctx, message)
                
                if chosen_generation is None:
                    return  # Generation selection timed out
                
                chosen_starter = await self.preview_and_select_starter(ctx, chosen_generation, message)
                
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
            
            # Create the Pokémon document
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
                    "hp": calculate_stat(full_pokemon_data["stats"]["hp"], ivs["hp"], 5, is_hp=True),
                    "attack": calculate_stat(full_pokemon_data["stats"]["attack"], ivs["attack"], 5),
                    "defense": calculate_stat(full_pokemon_data["stats"]["defense"], ivs["defense"], 5),
                    "special-attack": calculate_stat(full_pokemon_data["stats"]["special-attack"], ivs["special-attack"], 5),
                    "special-defense": calculate_stat(full_pokemon_data["stats"]["special-defense"], ivs["special-defense"], 5),
                    "speed": calculate_stat(full_pokemon_data["stats"]["speed"], ivs["speed"], 5)
                },
                "xp": starter_initial_xp,
                "ability": starter_ability_name
            }
            
            # Insert the Pokémon and update user data
            pokemon_collection.insert_one(pokemon_doc)
            user_data["caught_pokemon"].append(unique_id)
            user_data["partner_pokemon"] = unique_id
            inventory_collection.insert_one(user_data)
            
            # Create and send the starter summary embed
            starter_embed = await self.create_starter_summary_embed(ctx, chosen_starter, full_pokemon_data, unique_id, is_shiny)
            await asyncio.sleep(2)
            await message.edit(embed=starter_embed)
            
            # Prompt for nickname
            await prompt_for_nickname(ctx, chosen_starter['name'], unique_id)
            
            await ctx.send(f"Your adventure has just begun, Trainer {ctx.author.name}! You have received 25 Pokeballs and 5000 Pokedollars. Use `%search` to find a wild Pokémon!")
            
        except Exception as e:
            error_embed = discord.Embed(
                title="Error",
                description=f"An error occurred: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=error_embed)
    
    @commands.command(aliases=["p", "me"])
    async def profile(self, ctx, user: discord.Member = None):
        """Display trainer profile with avatar, stats and partner"""
        if user is None:
            user = ctx.author
        
        user_id = str(user.id)
        
        try:
            # Check cache first
            cache_key = f"profile_{user_id}"
            current_time = time.time()
            
            if cache_key in self.trainer_cache and current_time - self.trainer_cache[cache_key]["timestamp"] < self.CACHE_TIMEOUT:
                await ctx.send(embed=self.trainer_cache[cache_key]["embed"])
                return
            
            # Fetch user data
            user_data = await get_user_data(user_id)
            
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
            partner_sprite = None
            
            if partner_id:
                partner = await get_pokemon_data(partner_id)
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
            
            # Add gameplay settings if it's the user's own profile
            if user.id == ctx.author.id:
                settings = user_data.get("settings", {})
                environment_mode = settings.get("environment_rendering", "off")
                settings_info = f"**Environment Rendering:** {environment_mode.capitalize()}"
                embed.add_field(name="⚙️ Settings", value=settings_info, inline=False)
            
            embed.set_footer(text="Use %box to view your Pokémon | %changeavatar to change avatar")
            
            # Cache the profile embed
            self.trainer_cache[cache_key] = {
                "embed": embed,
                "timestamp": current_time
            }
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="Error",
                description=f"An error occurred: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=error_embed)
    
    @commands.command(aliases=["changeavatar", "ca"])
    async def change_avatar(self, ctx):
        """Change your trainer sprite"""
        user_id = str(ctx.author.id)
        
        try:
            # Check if user exists
            user_data = await get_user_data(user_id)
            
            if not user_data:
                await ctx.send("You have not begun your adventure! Start by using the `%start` command.")
                return
            
            # Get current sprite for comparison
            current_sprite = user_data.get("trainer_sprite", "red")
            
            # Initial message for avatar selection
            message = await ctx.send("Choose your new trainer avatar!")
            
            # Let user choose a new sprite
            new_sprite = await self.select_trainer_sprite(ctx, message)
            
            # Update the sprite in database
            await update_user_data(
                user_id,
                {"$set": {"trainer_sprite": new_sprite}}
            )
            
            # Invalidate cached profile
            if f"profile_{user_id}" in self.trainer_cache:
                del self.trainer_cache[f"profile_{user_id}"]
            
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
    
    async def intro(self, ctx):
        """Introduction sequence for new trainers"""
        oak_sprite = "https://play.pokemonshowdown.com/sprites/trainers/oak.png"
        pokeball = "https://play.pokemonshowdown.com/sprites/itemicons/poke-ball.png"
        
        # Choose a random partner Pokémon for Prof. Oak
        oak_partners = ['sylveon', 'pachirisu', 'froakie', 'squirtle']
        chosen_intro_partner = random.choice(oak_partners)
        oak_partner = f"https://play.pokemonshowdown.com/sprites/ani-shiny/{chosen_intro_partner}.gif"
        
        # Initial mystery message
        initial_embed = discord.Embed(
            title="???",
            description="Hello there! Welcome to the world of Pokémon!"
        )
        initial_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
        
        # Professor Oak introduction
        second_embed = discord.Embed(
            title="Professor Oak",
            description="My name is Oak! People call me the Pokémon Prof!"
        )
        second_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
        second_embed.set_thumbnail(url=oak_sprite)
        
        # World explanation
        third_embed = discord.Embed(
            title="Professor Oak",
            description="This world is inhabited by creatures called Pokémon! For some people, Pokémon are pets. Others use them for fights. Myself… I study Pokémon as a profession."
        )
        third_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
        third_embed.set_thumbnail(url=oak_sprite)
        third_embed.set_image(url=pokeball)
        
        # Show Oak's partner
        fourth_embed = discord.Embed(
            title="Professor Oak",
            description="This world is inhabited by creatures called Pokémon! For some people, Pokémon are pets. Others use them for fights. Myself… I study Pokémon as a profession."
        )
        fourth_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
        fourth_embed.set_thumbnail(url=oak_sprite)
        fourth_embed.set_image(url=oak_partner)
        
        # Send and update the message with a delay between updates
        message = await ctx.reply(embed=initial_embed)
        await asyncio.sleep(3)
        await message.edit(embed=second_embed)
        await asyncio.sleep(3)
        await message.edit(embed=third_embed)
        await asyncio.sleep(0.5)
        await message.edit(embed=fourth_embed)
        await asyncio.sleep(6)
        
        return message
    
    async def select_trainer_sprite(self, ctx, message):
        """Display and allow selection of trainer sprites by category"""
        oak_sprite = "https://play.pokemonshowdown.com/sprites/trainers/oak.png"
        
        # Organize sprites into categories
        SPRITE_CATEGORIES = {
            "Protagonists": ["red", "brendan", "lucas", "hilbert", "calem", "elio", "victor"],
            "Female Protagonists": ["leaf", "may", "dawn", "hilda", "serena", "selene", "gloria"],
            "Gym Leaders": ["brock", "misty", "surge", "erika", "sabrina", "koga", "blaine", "giovanni",
                           "falkner", "bugsy", "whitney", "morty", "chuck", "jasmine", "pryce", "clair"],
            "Elite Four": ["lorelei", "bruno", "agatha", "lance", "will", "koga-gen2", "karen"],
            "Champions": ["blue", "lance-champion", "steven", "wallace", "cynthia", "alder", "iris-champion"],
            "Special": ["n", "lillie", "gladion", "guzma", "lusamine", "mallow", "kiawe", "lana", "marnie", "leon"]
        }
        
        # Step 1: Create category selection dropdown
        category_select = discord.ui.Select(
            placeholder="Choose a category of trainer avatars",
            options=[
                discord.SelectOption(
                    label=category,
                    description=f"View {len(sprites)} trainer sprites",
                    value=category
                ) for category, sprites in SPRITE_CATEGORIES.items()
            ],
            min_values=1,
            max_values=1
        )
        
        category_view = discord.ui.View(timeout=60)
        category_view.add_item(category_select)
        
        chosen_sprite = None
        selection_complete = asyncio.Event()
        
        # Store the selected category and sprites
        selected_category = None
        selected_sprites = []
        
        # Step 2: Handle category selection
        async def category_callback(interaction):
            # First check if this interaction is from the original author
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("This is not your interaction! Please do `%start` if you wish to begin your own adventure!", ephemeral=True)
                return
            
            nonlocal selected_category, selected_sprites
            selected_category = category_select.values[0]
            selected_sprites = SPRITE_CATEGORIES[selected_category]
            
            # Create the sprite selection dropdown after category is chosen
            await show_sprite_selection(interaction)
        
        category_select.callback = category_callback
        
        # Step 3: Function to show sprite selection dropdown
        async def show_sprite_selection(interaction):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("This is not your interaction! Please do `%start` if you wish to begin your own adventure!", ephemeral=True)
                return
            
            sprite_select = discord.ui.Select(
                placeholder=f"Choose a {selected_category} sprite",
                options=[
                    discord.SelectOption(
                        label=sprite.split('-')[0].capitalize(),
                        description=f"Select {sprite} as your avatar",
                        value=sprite
                    ) for sprite in selected_sprites
                ],
                min_values=1,
                max_values=1
            )
            
            sprite_view = discord.ui.View(timeout=60)
            sprite_view.add_item(sprite_select)
            
            # Handle sprite selection
            async def sprite_callback(interaction):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("This is not your interaction! Please do `%start` if you wish to begin your own adventure!", ephemeral=True)
                    return
                
                nonlocal chosen_sprite
                chosen_sprite = sprite_select.values[0]
                
                # Show preview of selected sprite
                preview_embed = discord.Embed(
                    title="Professor Oak",
                    description=f"You've chosen **{chosen_sprite}** as your trainer avatar!"
                )
                
                sprite_url = f"https://play.pokemonshowdown.com/sprites/trainers/{chosen_sprite}.png"
                preview_embed.set_image(url=sprite_url)
                preview_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
                preview_embed.set_thumbnail(url=oak_sprite)
                
                await interaction.response.edit_message(embed=preview_embed, view=confirmation_view)
            
            sprite_select.callback = sprite_callback
            
            # Create confirmation buttons
            confirm_button = discord.ui.Button(style=discord.ButtonStyle.green, label="Confirm", custom_id="confirm")
            cancel_button = discord.ui.Button(style=discord.ButtonStyle.red, label="Cancel", custom_id="cancel")
            back_button = discord.ui.Button(style=discord.ButtonStyle.gray, label="Back to Categories", custom_id="back")
            
            confirmation_view = discord.ui.View(timeout=60)
            confirmation_view.add_item(confirm_button)
            confirmation_view.add_item(cancel_button)
            confirmation_view.add_item(back_button)
            
            # Handle confirmation
            async def confirm_callback(interaction):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("This is not your interaction! Please do `%start` if you wish to begin your own adventure!", ephemeral=True)
                    return
                
                nonlocal chosen_sprite
                confirm_embed = discord.Embed(
                    title="Professor Oak",
                    description=f"Excellent choice, {ctx.author.name}! This avatar suits you perfectly."
                )
                
                confirm_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
                confirm_embed.set_thumbnail(url=oak_sprite)
                sprite_url = f"https://play.pokemonshowdown.com/sprites/trainers/{chosen_sprite}.png"
                confirm_embed.set_image(url=sprite_url)
                
                await interaction.response.edit_message(embed=confirm_embed, view=None)
                await asyncio.sleep(3)
                selection_complete.set()
            
            async def cancel_callback(interaction):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("This is not your interaction! Please do `%start` if you wish to begin your own adventure!", ephemeral=True)
                    return
                
                nonlocal chosen_sprite
                chosen_sprite = "red"
                cancel_embed = discord.Embed(
                    title="Professor Oak",
                    description="No worries, young trainer! I'll set you up with the classic red outfit for now. Remember, you can always change your look later with the `%changeavatar` command."
                )
                
                cancel_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
                cancel_embed.set_thumbnail(url=oak_sprite)
                sprite_url = f"https://play.pokemonshowdown.com/sprites/trainers/{chosen_sprite}.png"
                cancel_embed.set_image(url=sprite_url)
                
                await interaction.response.edit_message(embed=cancel_embed, view=None)
                await asyncio.sleep(5)
                selection_complete.set()
            
            async def back_callback(interaction):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("This is not your interaction!", ephemeral=True)
                    return
                
                back_embed = discord.Embed(
                    title="Professor Oak",
                    description="Ah, second thoughts? No worries, young trainer! The path to becoming a Pokémon master often involves careful consideration. Let's review those categories once more!"
                )
                
                back_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
                back_embed.set_thumbnail(url=oak_sprite)
                
                await interaction.response.edit_message(embed=back_embed, view=category_view)
            
            confirm_button.callback = confirm_callback
            cancel_button.callback = cancel_callback
            back_button.callback = back_callback
            
            category_embed = discord.Embed(
                title=f"Professor Oak",
                description=f"Ah, the {selected_category} caught your eye! Excellent, young trainer! Choose the one that ignites your adventurous spirit."
            )
            
            category_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
            category_embed.set_thumbnail(url=oak_sprite)
            
            await interaction.response.edit_message(embed=category_embed, view=sprite_view)
        
        # Initial category selection message
        initial_embed = discord.Embed(
            title="Professor Oak",
            description="Young trainer! Your Pokémon journey begins with choosing your avatar. Behold the dropdown menu - your first step into the world of Pokémon awaits!"
        )
        
        initial_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
        initial_embed.set_thumbnail(url=oak_sprite)
        
        await message.edit(embed=initial_embed, view=category_view)
        
        # Wait for the selection to complete
        try:
            await asyncio.wait_for(selection_complete.wait(), timeout=60.0)
            return chosen_sprite
        except asyncio.TimeoutError:
            timeout_embed = discord.Embed(
                title="Professor Oak",
                description=f"Oh my, {ctx.author.name}! It seems you've been lost in thought for quite a while. No worries, it happens to the best of us when faced with such an important decision. I've gone ahead and selected the classic red outfit for you. Remember, you can always change your look later with the `%changeavatar` command."
            )
            
            timeout_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
            timeout_embed.set_thumbnail(url=oak_sprite)
            
            await message.edit(embed=timeout_embed, view=None)
            await asyncio.sleep(8)
            return "red"  # Default sprite if timeout
    
    async def select_generation(self, ctx, message):
        """Prompt the user to select a generation using a dropdown menu."""
        oak_sprite = "https://play.pokemonshowdown.com/sprites/trainers/oak.png"
        generations = list(self.starter_pokemon_generations.keys())
        
        # Create the dropdown
        generation_select = discord.ui.Select(
            placeholder="Choose a Generation",
            options=[
                discord.SelectOption(label=f"Generation {gen}", value=str(gen))
                for gen in generations
            ],
            min_values=1,
            max_values=1
        )
        
        # Create the view
        generation_view = discord.ui.View(timeout=60)
        generation_view.add_item(generation_select)
        
        # Track state
        chosen_generation = None
        selection_complete = asyncio.Event()
        
        # Callback for generation selection
        async def generation_callback(interaction):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("This is not your interaction! Please do `%start` if you wish to begin your own adventure!", ephemeral=True)
                return
            
            nonlocal chosen_generation
            chosen_generation = int(generation_select.values[0])
            selection_complete.set()
            
            # Create confirmation embed
            confirmation_embed = discord.Embed(
                title="Professor Oak",
                description=f"Ah, Generation {chosen_generation}! A fine choice, young trainer! Now it's time to select your very first Pokémon partner."
            )
            
            confirmation_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
            confirmation_embed.set_thumbnail(url=oak_sprite)
            
            await interaction.response.edit_message(embed=confirmation_embed, view=None)
        
        # Set the callback
        generation_select.callback = generation_callback
        
        # Create initial embed
        embed = discord.Embed(
            title="Professor Oak",
            description="Young trainer! It's time to choose your first Pokémon partner. First, select which generation of starters interests you the most!"
        )
        
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
        embed.set_thumbnail(url=oak_sprite)
        
        # Send the message with dropdown
        await message.edit(embed=embed, view=generation_view)
        
        # Wait for selection or timeout
        try:
            await asyncio.wait_for(selection_complete.wait(), timeout=60.0)
            return chosen_generation
        except asyncio.TimeoutError:
            timeout_embed = discord.Embed(
                title="Professor Oak",
                description=f"Oh my, {ctx.author.name}! It seems you've been lost in thought for quite a while. Let's try again when you're ready."
            )
            
            timeout_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
            timeout_embed.set_thumbnail(url=oak_sprite)
            
            await message.edit(embed=timeout_embed, view=None)
            await asyncio.sleep(3)
            return None
    
    async def preview_and_select_starter(self, ctx, chosen_generation, preview_message):
        """Allow selection of a starter Pokémon using a dropdown menu."""
        oak_sprite = "https://play.pokemonshowdown.com/sprites/trainers/oak.png"
        starter_ids = self.starter_pokemon_generations[chosen_generation]
        starters = []
        
        # Get data for each starter
        for sid in starter_ids:
            p = search_pokemon_by_id(sid)
            starter_name = p["name"].capitalize()
            sprite_url = await get_best_sprite_url(p, False)
            starter_types = ", ".join([t.capitalize() for t in p.get("types", [])]) if p.get("types") else "Unknown"
            description = p.get("description", "No description available.")
            starter_desc = description.split(".")[0] + "." if "." in description else description
            
            starters.append({
                "id": sid,
                "name": starter_name,
                "sprite": sprite_url,
                "types": starter_types,
                "description": starter_desc
            })
        
        # Create dropdown for starters
        starter_select = discord.ui.Select(
            placeholder="Choose your starter Pokémon",
            options=[
                discord.SelectOption(
                    label=starter["name"],
                    description=f"Type: {starter['types']}",
                    value=str(i)
                ) for i, starter in enumerate(starters)
            ],
            min_values=1,
            max_values=1
        )
        
        # Create buttons
        confirm_button = discord.ui.Button(style=discord.ButtonStyle.green, label="Confirm", custom_id="confirm")
        back_button = discord.ui.Button(style=discord.ButtonStyle.red, label="Back", custom_id="back")
        
        # Initial view with just the dropdown
        starter_view = discord.ui.View(timeout=60)
        starter_view.add_item(starter_select)
        
        # Variables to track state
        selected_starter_index = None
        selection_complete = asyncio.Event()
        final_choice = None
        
        # Callback for starter selection
        async def starter_callback(interaction):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("This is not your interaction! Please do `%start` if you wish to begin your own adventure!", ephemeral=True)
                return
            
            nonlocal selected_starter_index
            selected_starter_index = int(starter_select.values[0])
            starter = starters[selected_starter_index]
            
            # Create the confirmation view
            confirmation_view = discord.ui.View(timeout=60)
            confirmation_view.add_item(starter_select)  # Keep dropdown for changing selection
            confirmation_view.add_item(confirm_button)
            confirmation_view.add_item(back_button)
            
            desc = starter['description'].replace("\f", " ").replace("\n", " ")
            
            # Create preview embed
            preview_embed = discord.Embed(
                title="Professor Oak",
                description=f"Ah, **{starter['name']}**! An excellent choice. {desc}"
            )
            
            preview_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
            preview_embed.set_thumbnail(url=oak_sprite)
            preview_embed.set_image(url=starter["sprite"])
            preview_embed.add_field(name="Type", value=starter["types"], inline=True)
            preview_embed.set_footer(text="Confirm this Pokémon as your starter, or select another from the dropdown.")
            
            await interaction.response.edit_message(embed=preview_embed, view=confirmation_view)
        
        # Callback for confirm button
        async def confirm_callback(interaction):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("This is not your interaction!", ephemeral=True)
                return
            
            if selected_starter_index is None:
                await interaction.response.send_message("Please select a starter first!", ephemeral=True)
                return
            
            nonlocal final_choice
            final_choice = starters[selected_starter_index]
            
            # Create a simpler confirmation embed WITHOUT trying to create a summary yet
            final_embed = discord.Embed(
                title="Professor Oak",
                description=f"Excellent choice, {ctx.author.name}! **{final_choice['name']}** will be a wonderful partner on your journey!",
                color=discord.Color.green()
            )
            
            final_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
            final_embed.set_thumbnail(url=oak_sprite)
            final_embed.set_image(url=final_choice["sprite"])
            final_embed.add_field(name="Type", value=final_choice["types"], inline=True)
            
            await interaction.response.edit_message(embed=final_embed, view=None)
            selection_complete.set()
        
        # Callback for back button
        async def back_callback(interaction):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("This is not your interaction! Please do `%start` if you wish to begin your own adventure!", ephemeral=True)
                return
            
            # Create back embed
            back_embed = discord.Embed(
                title="Professor Oak",
                description="Let's take another look at the generations, shall we? It's an important decision after all!"
            )
            
            back_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
            back_embed.set_thumbnail(url=oak_sprite)
            
            await interaction.response.edit_message(embed=back_embed, view=None)
            await asyncio.sleep(2)
            selection_complete.set()
        
        # Set callbacks
        starter_select.callback = starter_callback
        confirm_button.callback = confirm_callback
        back_button.callback = back_callback
        
        # Create initial embed
        initial_embed = discord.Embed(
            title="Professor Oak",
            description=f"Now, young trainer, choose your Generation {chosen_generation} starter Pokémon! Each one has unique strengths that will shape your journey."
        )
        
        initial_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
        initial_embed.set_thumbnail(url=oak_sprite)
        
        await preview_message.edit(embed=initial_embed, view=starter_view)
        
        # Wait for selection or timeout
        try:
            await asyncio.wait_for(selection_complete.wait(), timeout=60.0)
            return final_choice
        except asyncio.TimeoutError:
            timeout_embed = discord.Embed(
                title="Professor Oak",
                description=f"Oh my, {ctx.author.name}! You seem to need more time. Choosing your first Pokémon is indeed an important decision."
            )
            
            timeout_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
            timeout_embed.set_thumbnail(url=oak_sprite)
            
            await preview_message.edit(embed=timeout_embed, view=None)
            await asyncio.sleep(3)
            return None
    
    async def create_starter_summary_embed(self, ctx, starter, full_data, unique_id, is_shiny):
        """Create a summary embed for the chosen starter Pokémon"""
        # Fetch the actual Pokémon data including the nature
        pokemon = await get_pokemon_data(unique_id)
        ability_name = pokemon.get("ability", "Unknown")
        
        # Create an actual Embed object
        embed = discord.Embed(
            title="Professor Oak",
            description=f"Congratulations, {ctx.author.name}! You've taken your first step into the world of Pokémon!",
            color=discord.Color.green()
        )
        
        # Add the fields to the embed directly
        embed.add_field(name="Your New Partner", value=f"**{starter['name']}**" + (" ⭐" if is_shiny else ""), inline=False)
        embed.add_field(name="Type", value=", ".join([t.capitalize() for t in full_data.get("types", [])]), inline=True)
        embed.add_field(name="Ability", value=ability_name.capitalize() if ability_name else "Unknown", inline=True)
        
        # Add nature field
        embed.add_field(name="Nature", value=pokemon.get("nature", "Unknown"), inline=True)
        
        # Add stats
        base_stats = full_data.get("stats", {})
        stats_str = "\n".join([f"{stat.capitalize()}: {value}" for stat, value in base_stats.items()])
        embed.add_field(name="Base Stats", value=stats_str, inline=False)
        
        # Add description
        embed.add_field(name="Professor Oak's Notes", 
                        value=full_data.get("description", "This Pokémon is full of mysteries to uncover!").replace("\f", " ").replace("\n", " "), 
                        inline=False)
        
        # Set author and image
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
        embed.set_thumbnail(url="https://play.pokemonshowdown.com/sprites/trainers/oak.png")
        
        # Set sprite
        if full_data.get("sprites"):
            sprite_url = await get_best_sprite_url(full_data, is_shiny)
            embed.set_image(url=sprite_url)
        
        # Set footer
        embed.set_footer(text=f"Pokédex ID: {full_data['id']} | Unique ID: {unique_id}")
        
        return embed
    
    def invalidate_cache(self, user_id=None):
        """Invalidate cache entries when data changes"""
        current_time = time.time()
        
        if user_id:
            # Invalidate specific user's cache
            cache_key = f"profile_{user_id}"
            if cache_key in self.trainer_cache:
                del self.trainer_cache[cache_key]
        else:
            # Clear expired cache entries
            keys_to_remove = []
            for key, data in self.trainer_cache.items():
                if current_time - data["timestamp"] > self.CACHE_TIMEOUT:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                if key in self.trainer_cache:
                    del self.trainer_cache[key]

async def setup(client):
    await client.add_cog(TrainerCog(client))