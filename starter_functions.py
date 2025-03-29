import discord
import asyncio
import random
from discord.ui import Select, View
from pokemon_functions import search_pokemon_by_id, get_best_sprite_url
from pokemon_stat_generation import store_caught_pokemon

async def select_generation(ctx, client, starter_pokemon_generations, message):
    """Prompt the user to select a generation using a dropdown menu."""
    generations = list(starter_pokemon_generations.keys())
    
    # Create the dropdown
    generation_select = Select(
        placeholder="Choose a Generation",
        options=[
            discord.SelectOption(label=f"Generation {gen}", value=str(gen))
            for gen in generations
        ],
        min_values=1,
        max_values=1
    )
    
    # Create the view
    generation_view = View(timeout=60)
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
        confirmation_embed.set_thumbnail(url="https://play.pokemonshowdown.com/sprites/trainers/oak.png")
        
        await interaction.response.edit_message(embed=confirmation_embed, view=None)
    
    # Set the callback
    generation_select.callback = generation_callback
    
    # Create initial embed
    embed = discord.Embed(
        title="Professor Oak",
        description="Young trainer! It's time to choose your first Pokémon partner. First, select which generation of starters interests you the most!"
    )
    embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
    embed.set_thumbnail(url="https://play.pokemonshowdown.com/sprites/trainers/oak.png")
    
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
        timeout_embed.set_thumbnail(url="https://play.pokemonshowdown.com/sprites/trainers/oak.png")
        
        await message.edit(embed=timeout_embed, view=None)
        await asyncio.sleep(3)
        return None

async def preview_and_select_starter(ctx, client, chosen_generation, starter_pokemon_generations, preview_message):
    """Allow selection of a starter Pokémon using a dropdown menu."""
    starter_ids = starter_pokemon_generations[chosen_generation]
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
    starter_select = Select(
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
    starter_view = View(timeout=60)
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
        confirmation_view = View(timeout=60)
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
        preview_embed.set_thumbnail(url="https://play.pokemonshowdown.com/sprites/trainers/oak.png")
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
        final_embed.set_thumbnail(url="https://play.pokemonshowdown.com/sprites/trainers/oak.png")
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
        back_embed.set_thumbnail(url="https://play.pokemonshowdown.com/sprites/trainers/oak.png")
        
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
    initial_embed.set_thumbnail(url="https://play.pokemonshowdown.com/sprites/trainers/oak.png")
    
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
        timeout_embed.set_thumbnail(url="https://play.pokemonshowdown.com/sprites/trainers/oak.png")
        
        await preview_message.edit(embed=timeout_embed, view=None)
        await asyncio.sleep(3)
        return None

async def create_starter_summary_embed(ctx, starter, full_data, unique_id, is_shiny):
    # Fetch the actual Pokemon data including the nature
    from main import pokemon_collection
    pokemon = pokemon_collection.find_one({"_id": unique_id})
    
    # Create an actual Embed object instead of a dictionary
    embed = discord.Embed(
        title="Professor Oak",
        description=f"Congratulations, {ctx.author.name}! You've taken your first step into the world of Pokémon!",
        color=discord.Color.green()
    )
    
    # Add the fields to the embed directly
    embed.add_field(name="Your New Partner", value=f"**{starter['name']}**" + (" ⭐" if is_shiny else ""), inline=False)
    embed.add_field(name="Type", value=", ".join([t.capitalize() for t in full_data.get("types", [])]), inline=True)
    embed.add_field(name="Ability", value=full_data.get("abilities", ["Unknown"])[0].capitalize(), inline=True)
    
    # Add nature field
    embed.add_field(name="Nature", value=pokemon.get("nature", "Unknown"), inline=True)
    
    # Add stats
    base_stats = full_data.get("stats", {})
    stats_str = "\n".join([f"{stat.capitalize()}: {value}" for stat, value in base_stats.items()])
    embed.add_field(name="Base Stats", value=stats_str, inline=False)
    
    # Add description
    embed.add_field(name="Professor Oak's Notes", value=full_data.get("description", "This Pokémon is full of mysteries to uncover!").replace("\f", " ").replace("\n", " "), inline=False)
    
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
