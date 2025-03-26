import discord
import asyncio
from discord.ui import View, Select

async def select_trainer_sprite(ctx, client):
    """Display and allow selection of trainer sprites by category"""
    
    # Organize sprites into categories
    SPRITE_CATEGORIES = {
        "Protagonists": ["red", "liko", "marnie"],
        "Gym Leaders": ["wallace-gen6", "jasmine-masters", "drayton"],
        "Special": ["miku-flying", "anabel"],
        "Generic": ["aquasuit", "aromalady"]
    }
    
    # Step 1: Create category selection dropdown
    category_select = Select(
        placeholder="Choose a sprite category",
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
    
    # Store the selected category and sprites
    selected_category = None
    selected_sprites = []
    
    # Step 2: Handle category selection
    async def category_callback(interaction):
        # First check if this interaction is from the original author
        if interaction.user.id != ctx.author.id:
            await interaction.response.send_message("Nigga get out", ephemeral=True)
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
            await interaction.response.send_message("Nigga get out", ephemeral=True)
            return
        
        sprite_select = Select(
            placeholder=f"Choose a {selected_category} sprite",
            options=[
                discord.SelectOption(
                    label=sprite.capitalize().replace('-', ' '),
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
                await interaction.response.send_message("Nigga get out", ephemeral=True)
                return
        
            nonlocal chosen_sprite
            chosen_sprite = sprite_select.values[0]
            
            # Show preview of selected sprite
            preview_embed = discord.Embed(
                title="Selected Trainer Avatar",
                description=f"You've chosen **{chosen_sprite}** as your trainer avatar!"
            )
            sprite_url = f"https://play.pokemonshowdown.com/sprites/trainers/{chosen_sprite}.png"
            preview_embed.set_image(url=sprite_url)
            
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
                await interaction.response.send_message("Nigga get out", ephemeral=True)
                return
            
            nonlocal chosen_sprite
            await interaction.response.edit_message(content=f"Avatar set to **{chosen_sprite}**!", embed=None, view=None)
            return chosen_sprite  # Return only the sprite name
            
        async def cancel_callback(interaction):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("Nigga get out", ephemeral=True)
                return
            
            nonlocal chosen_sprite
            await interaction.response.edit_message(content="Selection cancelled. Default 'red' sprite selected.", embed=None, view=None)
            chosen_sprite = "red"
            return chosen_sprite
            
        async def back_callback(interaction):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("Nigga get out", ephemeral=True)
                return
            
            await interaction.response.edit_message(content="Select a sprite category:", embed=None, view=category_view)
        
        confirm_button.callback = confirm_callback
        cancel_button.callback = cancel_callback
        back_button.callback = back_callback
        
        category_embed = discord.Embed(
            title=f"Choose a {selected_category} Sprite",
            description="Select a sprite from the dropdown menu below."
        )
        
        await interaction.response.edit_message(embed=category_embed, view=sprite_view)
    
    # Initial category selection message
    initial_embed = discord.Embed(
        title="Choose Your Trainer Avatar",
        description="First, select a category of trainer sprites from the dropdown menu below."
    )
    
    selection_message = await ctx.send(embed=initial_embed, view=category_view)
    
    # Wait for the selection to complete
    try:
        interaction = await asyncio.wait_for(
            client.wait_for(
                "interaction",
                check=lambda i: i.user == ctx.author and i.data.get("custom_id") in ["confirm", "cancel"]
            ),
            timeout=60.0
        )
        
        if interaction.data.get("custom_id") == "confirm":
            final_sprite = chosen_sprite  # Use the chosen_sprite variable directly
            await selection_message.delete()
            return final_sprite
        else:
            await selection_message.delete()
            return "red"  # Default sprite
        
    except asyncio.TimeoutError:
        await selection_message.delete()
        await ctx.send("Sprite selection timed out. Default 'red' sprite selected.")
        return "red"  # Default sprite if timeout
    
    except asyncio.TimeoutError:
        await selection_message.delete()
        await ctx.send("Sprite selection timed out. Default 'red' sprite selected.")
        return "red"  # Default sprite if timeout
