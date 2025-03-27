import discord
import asyncio
import random
from discord.ui import View, Select

oak_sprite = "https://play.pokemonshowdown.com/sprites/trainers/oak.png"
pokeball = "https://play.pokemonshowdown.com/sprites/itemicons/poke-ball.png"

async def choose_random_intro_partner():
    oak_partners = ['sylveon', 'pachirisu', 'froakie', 'squirtle']

    chosen_intro_partner = random.choice(oak_partners)
    url = f"https://play.pokemonshowdown.com/sprites/ani-shiny/{chosen_intro_partner}.gif"

    return url

async def intro(ctx, client):

    initial_embed = discord.Embed(
        title="???",
        description="Hello there! Welcome to the world of Pokémon!"
    )
    initial_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)

    second_embed = discord.Embed(
        title="Professor Oak",
        description="My name is Oak! People call me the Pokémon Prof!"
    )
    second_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
    second_embed.set_thumbnail(url=oak_sprite)

    third_embed = discord.Embed(
        title="Professor Oak",
        description="This world is inhabited by creatures called Pokémon! For some people, Pokémon are pets. Other use them for fights. Myself… I study Pokémon as a profession."
    )
    third_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
    third_embed.set_thumbnail(url=oak_sprite)
    third_embed.set_image(url=pokeball)

    oak_partner = await choose_random_intro_partner()

    fourth_embed = discord.Embed(
        title="Professor Oak",
        description="This world is inhabited by creatures called Pokémon! For some people, Pokémon are pets. Other use them for fights. Frbueduen uses them for self pleasure. Myself… I study Pokémon as a profession."
    )
    fourth_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
    fourth_embed.set_thumbnail(url=oak_sprite)
    fourth_embed.set_image(url=oak_partner)

    message = await ctx.reply(embed=initial_embed)
    await asyncio.sleep(3)
    await message.edit(embed=second_embed)
    await asyncio.sleep(3)
    await message.edit(embed=third_embed)
    await asyncio.sleep(0.5)
    await message.edit(embed=fourth_embed)
    await asyncio.sleep(6)
    

    return message

async def select_trainer_sprite(ctx, client, selection_message):
    """Display and allow selection of trainer sprites by category"""
    
    # Organize sprites into categories
    SPRITE_CATEGORIES = {
        "Protagonists": ["red", "liko", "marnie"],
        "Gym Leaders": ["wallace-gen6", "jasmine-masters", "drayton","elesa-gen5bw2"],
        "Special": ["miku-flying", "anabel"],
        "Generic": ["aquasuit", "aromalady"]
    }

    
    # Step 1: Create category selection dropdown
    category_select = Select(   
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
    
    category_view = View(timeout=60)
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
        
        sprite_select = Select(
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
        
        sprite_view = View(timeout=60)
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
        
        confirmation_view = View(timeout=60)
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
                await interaction.response.send_message("Nigga get out", ephemeral=True)
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
        
        await interaction.response.edit_message(embed=category_embed, view=sprite_view)
    
    # Initial category selection message
    initial_embed = discord.Embed(
        title="Professor Oak",
        description="Young trainer! Your Pokémon journey begins with choosing your avatar. Behold the dropdown menu - your first step into the world of Pokémon awaits!"
    )
    initial_embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
    initial_embed.set_thumbnail(url=oak_sprite)
    
    await selection_message.edit(embed=initial_embed, view=category_view)
    
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

        await selection_message.edit(embed=timeout_embed, view=None)
        await asyncio.sleep(8)
        return "red"  # Default sprite if timeout