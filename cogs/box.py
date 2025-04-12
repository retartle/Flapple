# cogs/box.py (updated with discord.ui buttons)
import discord
import time
import asyncio
from discord.ext import commands
from utils.db_utils import get_user_data, get_pokemon_bulk, get_pokemon_data, update_pokemon_data, update_user_data

class BoxView(discord.ui.View):
    def __init__(self, ctx, cog, user_id, user, current_page, total_pages, caught_id_list, total_pokemon, box_color):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.cog = cog
        self.user_id = user_id
        self.user = user
        self.current_page = current_page
        self.total_pages = total_pages
        self.caught_id_list = caught_id_list
        self.total_pokemon = total_pokemon
        self.box_color = box_color
        self.message = None
        
        # Don't update button states here - buttons aren't added yet
    
    # Add a proper update method to be called AFTER the view is sent
    async def update_buttons(self):
        """Update button states based on current page"""
        # Properly disable buttons based on current page
        for child in self.children:
            if child.custom_id in ["first_page", "prev_page"]:
                child.disabled = (self.current_page == 1)
            elif child.custom_id in ["next_page", "last_page"]:
                child.disabled = (self.current_page == self.total_pages)
        
        # Update the message with new button states
        if self.message:
            await self.message.edit(view=self)

    async def interaction_check(self, interaction):
        """Only allow the original command user to use the buttons"""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("You cannot control this box view!", ephemeral=True)
            return False
        return True

    @discord.ui.button(emoji="⏪", style=discord.ButtonStyle.primary, custom_id="first_page")
    async def first_page(self, interaction, button):
        # CRITICAL: Acknowledge interaction immediately
        await interaction.response.defer()
        
        # Update page number
        self.current_page = 1
        
        # Get new embed
        embed = await self.cog.get_page_embed(
            self.user_id, self.user, self.current_page,
            self.total_pages, self.caught_id_list,
            self.total_pokemon, self.box_color
        )
        
        # Update button states directly
        for child in self.children:
            if child.custom_id in ["first_page", "prev_page"]:
                child.disabled = True
            elif child.custom_id in ["next_page", "last_page"]:
                child.disabled = (self.current_page == self.total_pages)
        
        # Update the message
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.primary, custom_id="prev_page")
    async def prev_page(self, interaction, button):
        await interaction.response.defer()
        
        self.current_page = max(1, self.current_page - 1)
        
        embed = await self.cog.get_page_embed(
            self.user_id, self.user, self.current_page,
            self.total_pages, self.caught_id_list, 
            self.total_pokemon, self.box_color
        )
        
        # Update button states directly
        for child in self.children:
            if child.custom_id in ["first_page", "prev_page"]:
                child.disabled = (self.current_page == 1)
            elif child.custom_id in ["next_page", "last_page"]:
                child.disabled = (self.current_page == self.total_pages)
        
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.primary, custom_id="next_page")
    async def next_page(self, interaction, button):
        await interaction.response.defer()
        
        self.current_page = min(self.total_pages, self.current_page + 1)
        
        embed = await self.cog.get_page_embed(
            self.user_id, self.user, self.current_page,
            self.total_pages, self.caught_id_list, 
            self.total_pokemon, self.box_color
        )
        
        # Update button states directly
        for child in self.children:
            if child.custom_id in ["first_page", "prev_page"]:
                child.disabled = (self.current_page == 1)
            elif child.custom_id in ["next_page", "last_page"]:
                child.disabled = (self.current_page == self.total_pages)
        
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(emoji="⏩", style=discord.ButtonStyle.primary, custom_id="last_page")
    async def last_page(self, interaction, button):
        await interaction.response.defer()
        
        self.current_page = self.total_pages
        
        embed = await self.cog.get_page_embed(
            self.user_id, self.user, self.current_page,
            self.total_pages, self.caught_id_list, 
            self.total_pokemon, self.box_color
        )
        
        # Update button states directly
        for child in self.children:
            if child.custom_id in ["first_page", "prev_page"]:
                child.disabled = (self.current_page == 1)
            elif child.custom_id in ["next_page", "last_page"]:
                child.disabled = True
        
        await interaction.message.edit(embed=embed, view=self)

    async def on_timeout(self):
        """Disable all buttons when the view times out"""
        for child in self.children:
            child.disabled = True
        
        try:
            if self.message:
                await self.message.edit(view=self)
        except discord.errors.NotFound:
            pass

class BoxCog(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.box_cache = {}
        self.BOX_CACHE_TIMEOUT = 300  # Cache timeout in seconds (5 minutes)
        self.pokemon_per_page = 12
    
    @commands.command()
    async def box(self, ctx, page: int = 1, user: discord.Member = None):
        """Display your Pokémon box with pagination"""
        if user is None:
            user = ctx.author
        
        user_id = str(user.id)
        
        # Get user data
        user_data = await get_user_data(user_id)
        
        if not user_data:
            await ctx.send("You have not begun your adventure! Start by using the `%start` command.")
            return
        
        caught_id_list = user_data.get("caught_pokemon", [])
        
        if not caught_id_list:
            await ctx.send("You have not caught any Pokémon! Try using the `%search` command.")
            return
        
        total_pokemon = len(caught_id_list)
        total_pages = max(1, (total_pokemon + self.pokemon_per_page - 1) // self.pokemon_per_page)
        current_page = max(1, min(page, total_pages))
        
        # Generate a consistent color based on user ID
        color_seed = int(user.id) % 0xFFFFFF
        box_color = discord.Colour(color_seed)
        
        # Get the embed for the current page
        embed = await self.get_page_embed(user_id, user, current_page, total_pages, caught_id_list, total_pokemon, box_color)
        
        # Create and send the view for pagination
        if total_pages > 1:
            view = BoxView(ctx, self, user_id, user, current_page, total_pages, caught_id_list, total_pokemon, box_color)
            
            # IMPORTANT: Send message first, then update the view's message reference
            message = await ctx.send(embed=embed, view=view)
            view.message = message

            await view.update_buttons()
        else:
            # If there's only one page, no need for pagination buttons
            await ctx.send(embed=embed)

    
    async def get_page_embed(self, user_id, user, page_num, total_pages, caught_id_list, total_pokemon, box_color):
        """Generate embed for a specific page with bulk data loading and caching"""
        current_time = time.time()
        
        # Check if page data is cached
        cache_key = f"{user_id}_page_{page_num}"
        if cache_key in self.box_cache and current_time - self.box_cache[cache_key]["timestamp"] < self.BOX_CACHE_TIMEOUT:
            return self.box_cache[cache_key]["embed"]
        
        # Calculate range for current page
        start_idx = (page_num - 1) * self.pokemon_per_page
        end_idx = min(start_idx + self.pokemon_per_page, total_pokemon)
        current_page_pokemon_ids = caught_id_list[start_idx:end_idx]
        
        # OPTIMIZATION: Bulk fetch all Pokémon for this page in ONE query
        pokemon_dict = await get_pokemon_bulk(current_page_pokemon_ids)
        
        # Create the embed
        embed = discord.Embed(
            title=f"🎒 {user.name}'s Pokémon Box",
            description=f"Page {page_num}/{total_pages}",
            color=box_color
        )
        
        # Add Pokémon to the embed
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
        
        embed.set_footer(text="Use buttons to navigate | %view [number] for details")
        
        # Cache the embed
        self.box_cache[cache_key] = {
            "embed": embed,
            "timestamp": current_time
        }
        
        return embed
    
    @commands.command(aliases=["v", "info", "pokemon"])
    async def view(self, ctx, number: int = None, user: discord.Member = None):
        """View detailed information about a specific Pokémon"""
        if user is None:
            user = ctx.author
        
        user_id = str(user.id)
        
        # If no number provided, show usage instructions
        if number is None:
            usage_embed = discord.Embed(
                title="Pokémon View Command Usage",
                description="Use this command to view detailed information about a specific Pokémon in your box.",
                color=discord.Colour.blue()
            )
            
            usage_embed.add_field(
                name="How to Use",
                value="`%view [number]` - View details of Pokémon by its box number\n" +
                    "Example: `%view 7` to view Pokémon #7\n\n" +
                    "You can find Pokémon numbers in your box view (`%box` command).\n" +
                    "Each Pokémon is numbered sequentially across all pages.",
                inline=False
            )
            
            usage_embed.add_field(
                name="Aliases",
                value="You can also use `%v`, `%info`, or `%pokemon` instead of `%view`.",
                inline=False
            )
            
            await ctx.send(embed=usage_embed)
            return
        
        # Fetch user data
        user_data = await get_user_data(user_id)
        
        if not user_data:
            await ctx.send("You have not begun your adventure! Start by using the `%start` command.")
            return
        
        caught_id_list = user_data.get("caught_pokemon", [])
        
        if not caught_id_list:
            await ctx.send("You have not caught any Pokémon! Try using the `%search` command")
            return
        
        total_pokemon = len(caught_id_list)
        
        # Validate the number
        if number < 1 or number > total_pokemon:
            await ctx.send(f"Pokémon #{number} doesn't exist in your box. You have {total_pokemon} Pokémon (numbered 1-{total_pokemon}).")
            return
        
        # Get the Pokémon unique ID (adjusting for 0-based indexing)
        pokemon_id = caught_id_list[number - 1]
        pokemon = await get_pokemon_data(pokemon_id)
        
        if not pokemon:
            await ctx.send("Pokémon data could not be found.")
            return
        
        # Calculate which page this Pokémon is on (for reference)
        pokemon_per_page = self.pokemon_per_page
        page = ((number - 1) // pokemon_per_page) + 1
        
        # Get Pokémon details
        from utils.pokemon_utils import search_pokemon_by_id, get_best_sprite_url, get_type_colour, get_next_evolution
        
        name = pokemon["name"].capitalize().replace('-', ' ')
        nickname = pokemon.get("nickname")
        shiny = pokemon["shiny"]
        level = pokemon["level"]
        pokedex_id = pokemon["pokedex_id"]
        
        result = search_pokemon_by_id(pokedex_id)
        
        # Format display name with original species in parentheses
        if nickname:
            display_name = f"{nickname} ({name})"
        else:
            display_name = name
        
        # Add shiny star if needed
        if shiny:
            display_name = f"{display_name} ⭐"
        
        # Get sprite URL from the original Pokémon data
        sprite_url = await get_best_sprite_url(result, shiny) if result else None
        
        # Get types and color from the original Pokémon data
        type_list = result.get("types", []) if result else []
        type_str = ", ".join([t.capitalize() for t in type_list])
        colour = get_type_colour(type_list)
        
        # Create embed
        view_embed = discord.Embed(
            title=f"{display_name} - Level {level}",
            color=colour
        )
        
        if sprite_url:
            view_embed.set_image(url=sprite_url)
        
        # Add Pokémon info
        view_embed.add_field(name="Type", value=type_str or "Unknown", inline=True)
        view_embed.add_field(name="Pokédex ID", value=f"#{pokedex_id}", inline=True)
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
            view_embed.add_field(name="Total IV", value=f"{total_iv}/186 ({round((total_iv/186)*100, 2)}%)", inline=True)
        
        # Add moves if available
        if "moves" in pokemon and isinstance(pokemon["moves"], list) and len(pokemon["moves"]) > 0:
            moves_str = ", ".join([m.capitalize().replace('-', ' ') for m in pokemon["moves"]])
            view_embed.add_field(name="Moves", value=moves_str, inline=False)
        
        # Add the description if available
        if result and "description" in result:
            description = result["description"].replace("\n", " ")
            view_embed.add_field(name="Description", value=description, inline=False)
        
        # Add evolution information if available
        if result and "evolution_line" in result:
            evolution_line = result["evolution_line"]
            next_evo = get_next_evolution(evolution_line, pokemon["name"])
            
            if next_evo != "-":
                view_embed.add_field(name="Evolves Into", value=next_evo.capitalize(), inline=True)
            else:
                view_embed.add_field(name="Evolution", value="Final Form", inline=True)
        
        view_embed.set_footer(text=f"Pokémon of {user.name} | Use '%box {page}' to return to the box view")
        
        await ctx.send(embed=view_embed)

    @commands.command()
    async def partner(self, ctx):
        """Display information about your partner Pokémon"""
        user_id = str(ctx.author.id)
        
        try:
            # Fetch user data
            user_data = await get_user_data(user_id)
            
            if not user_data:
                await ctx.send("You haven't started your adventure yet. Use `%start` to begin!")
                return
            
            partner_id = user_data.get("partner_pokemon")
            if not partner_id:
                await ctx.send("You don't have a partner Pokémon yet!")
                return
            
            # Fetch partner Pokémon data
            partner_pokemon = await get_pokemon_data(partner_id)
            
            if not partner_pokemon:
                await ctx.send("Your partner Pokémon's data could not be found.")
                return
            
            from utils.pokemon_utils import search_pokemon_by_id, get_best_sprite_url, calculate_min_xp_for_level
            
            name = partner_pokemon["name"].capitalize().replace('-', ' ')
            nickname = partner_pokemon.get("nickname")
            level = partner_pokemon["level"]
            xp = partner_pokemon.get("xp", 0)
            pokedex_id = partner_pokemon["pokedex_id"]
            shiny = partner_pokemon["shiny"]
            
            # Calculate XP required for the next level
            next_level_xp = calculate_min_xp_for_level(level + 1)
            xp_needed = next_level_xp - xp
            
            # Format the display name
            if nickname:
                display_name = f"{nickname} ({name})"
            else:
                display_name = name
                
            if shiny:
                display_name += " ⭐"
            
            # Get Pokémon data
            result = search_pokemon_by_id(pokedex_id)
            
            # Create embed with type color
            type_list = result.get("types", []) if result else []
            from utils.pokemon_utils import get_type_colour
            color = get_type_colour(type_list)
            
            embed = discord.Embed(title=display_name, color=color)
            
            # Add basic stats
            embed.add_field(name="Level", value=level, inline=True)
            embed.add_field(name="XP", value=f"{xp}/{next_level_xp} (Need {xp_needed} more)", inline=True)
            
            # Add type information
            if type_list:
                type_str = ", ".join([t.capitalize() for t in type_list])
                embed.add_field(name="Type", value=type_str, inline=True)
            
            # Get sprite URL
            if result:
                sprite_url = await get_best_sprite_url(result, shiny)
                if sprite_url:
                    embed.set_image(url=sprite_url)
            
            # Add IV information if available
            if "ivs" in partner_pokemon and isinstance(partner_pokemon["ivs"], dict):
                ivs = partner_pokemon["ivs"]
                total_iv = sum(ivs.values())
                iv_percent = round((total_iv / 186) * 100, 2)
                
                embed.add_field(
                    name="IVs",
                    value=f"Total: {total_iv}/186 ({iv_percent}%)",
                    inline=True
                )
            
            # Add ability if available
            if "ability" in partner_pokemon:
                embed.add_field(
                    name="Ability",
                    value=partner_pokemon["ability"].capitalize(),
                    inline=True
                )
            
            embed.set_footer(text="Your partner Pokémon gains XP as you chat in Discord")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="Error",
                description=f"An error occurred: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=error_embed)


    @commands.command(aliases=["setpartner", "sp"])
    async def set_partner(self, ctx, number: int = None):
        """Set a new partner Pokémon from your caught Pokémon"""
        user_id = str(ctx.author.id)
        
        try:
            # Check if user exists
            user_data = await get_user_data(user_id)
            
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
                    current_partner = await get_pokemon_data(current_partner_id)
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
            pokemon = await get_pokemon_data(pokemon_id)
            
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
            from utils.pokemon_utils import search_pokemon_by_id, get_best_sprite_url, get_type_colour
            
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
            type_list = result.get("types", []) if result else []
            type_str = ", ".join([t.capitalize() for t in type_list])
            colour = get_type_colour(type_list)
            
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
            confirm_embed.set_footer(text="Use the buttons below to confirm or cancel")
            
            # Create confirmation view
            class ConfirmView(discord.ui.View):
                def __init__(self, ctx):
                    super().__init__(timeout=30)
                    self.ctx = ctx
                    self.value = None
                    self.message = None  # Will store the message reference
                
                async def interaction_check(self, interaction):
                    """Verify that only the command author can use the buttons"""
                    if interaction.user.id != self.ctx.author.id:
                        await interaction.response.send_message("This is not your decision to make!", ephemeral=True)
                        return False
                    return True
                
                @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, emoji="✅", custom_id="confirm")
                async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                    print(f"Confirm button clicked by {interaction.user.name}")
                    
                    # Acknowledge interaction immediately
                    await interaction.response.defer()
                    
                    # Set the result value
                    self.value = True
                    
                    # Disable all buttons
                    for child in self.children:
                        child.disabled = True
                    
                    # Edit the message with disabled buttons
                    try:
                        await interaction.message.edit(view=self)
                        print("Successfully updated message with disabled buttons")
                    except Exception as e:
                        print(f"Error updating message: {e}")
                    
                    # Stop the view
                    self.stop()
                
                @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="❌", custom_id="cancel")
                async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                    print(f"Cancel button clicked by {interaction.user.name}")
                    
                    # Acknowledge interaction immediately
                    await interaction.response.defer()
                    
                    # Set the result value
                    self.value = False
                    
                    # Disable all buttons
                    for child in self.children:
                        child.disabled = True
                    
                    # Edit the message with disabled buttons
                    try:
                        await interaction.message.edit(view=self)
                        print("Successfully updated message with disabled buttons")
                    except Exception as e:
                        print(f"Error updating message: {e}")
                    
                    # Stop the view
                    self.stop()
                
                async def on_timeout(self):
                    """Handle timeout by disabling buttons"""
                    for child in self.children:
                        child.disabled = True
                    
                    try:
                        # Try to edit the original message
                        if self.message:
                            await self.message.edit(view=self)
                            print("Timeout: Successfully disabled buttons")
                    except Exception as e:
                        print(f"Error in timeout handler: {e}")
            
            # Send the confirmation message with view
            view = ConfirmView(ctx)
            message = await ctx.send(embed=confirm_embed, view=view)
            view.message = message  # Store message reference in the view

            # Print debug info
            print(f"Set Partner: View created and message sent with ID {message.id}")

            # Wait for user interaction with timeout
            await view.wait()

            # Check the result
            if view.value is True:
                # User confirmed - update the partner_pokemon field
                print("User confirmed partner change")
                result = await update_user_data(
                    user_id,
                    {"$set": {"partner_pokemon": pokemon_id}}
                )
                print(f"Database update result: {result}")
                
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
                
            elif view.value is False:
                # User cancelled
                print("User cancelled partner change")
                cancel_embed = discord.Embed(
                    title="❌ Partner Change Cancelled",
                    description="You decided to keep your current partner.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=cancel_embed)
                
            else:
                # Timeout
                print("Partner change timed out")
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




async def setup(client):
    await client.add_cog(BoxCog(client))
