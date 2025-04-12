# cogs/shop.py
import discord
import asyncio
import time
from discord.ext import commands
from config import config_collection
from utils.db_utils import get_user_data, update_user_data
from utils.encounter_utils import get_emoji

class ShopItemSelect(discord.ui.Select):
    """Dropdown for selecting shop items"""
    def __init__(self, shop_data, user_data):
        self.shop_data = shop_data
        self.user_data = user_data
        
        # Create options from shop data
        options = [
            discord.SelectOption(
                label="Poké Ball",
                description=f"{shop_data.get('Pokeball', 200)}₽ • You have: {user_data.get('Pokeballs', 0)}",
                value="Pokeball",
                emoji=f"{get_emoji("pokeball")},"
            ),
            discord.SelectOption(
                label="Great Ball",
                description=f"{shop_data.get('Greatball', 600)}₽ • You have: {user_data.get('Greatballs', 0)}",
                value="Greatball",
                emoji=f"{get_emoji("greatball")},"
            ),
            discord.SelectOption(
                label="Ultra Ball",
                description=f"{shop_data.get('Ultraball', 1200)}₽ • You have: {user_data.get('Ultraballs', 0)}",
                value="Ultraball",
                emoji=f"{get_emoji("ultraball")},"
            ),
            discord.SelectOption(
                label="Master Ball",
                description=f"{shop_data.get('Masterball', 50000)}₽ • You have: {user_data.get('Masterballs', 0)}",
                value="Masterball",
                emoji=f"{get_emoji("masterball")},"
            )
        ]  # Fixed: Added closing bracket
        
        # Initialize the select with the options
        super().__init__(
            placeholder="Select an item to purchase...",
            min_values=1,
            max_values=1,
            options=options
        )  # Fixed: Added closing parenthesis

class QuantitySelect(discord.ui.Select):
    """Dropdown for selecting quantity to purchase"""
    def __init__(self):
        options = [
            discord.SelectOption(label="1", value="1", emoji="1️⃣"),
            discord.SelectOption(label="5", value="5", emoji="5️⃣"),
            discord.SelectOption(label="10", value="10", emoji="🔟"),
            discord.SelectOption(label="25", value="25", emoji="📊"),
            discord.SelectOption(label="50", value="50", emoji="🔝")
        ]
        
        super().__init__(
            placeholder="Select quantity...",
            min_values=1,
            max_values=1,
            options=options
        )

class ShopView(discord.ui.View):
    """Main shop view with item selection and quantity"""
    def __init__(self, ctx, client, user_data):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.client = client
        self.user_data = user_data
        self.selected_item = None
        self.selected_quantity = 1
        self.shop_data = None
        
        # Initialize item selector (will be added after shop data is fetched)
        self.shop_data = None
        self.item_select = None
        self.quantity_select = None
        
        # Purchase button (disabled initially)
        self.purchase_button = discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label="Purchase",
            emoji="🛒",
            disabled=True,
            row=1
        )
        self.purchase_button.callback = self.purchase_callback
        
        # Daily claim button (smaller and moved to row 1)
        self.daily_claim = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="Daily",
            emoji="💰",
            custom_id="daily_reward",
            row=1
        )
        self.daily_claim.callback = self.daily_callback
    
    async def initialize(self):
        """Fetch shop data and initialize selectors"""
        # Get shop data from database or cache
        cache_key = "shop_data"
        current_time = time.time()
        
        # Check if shop data is cached by the cog
        if hasattr(self.client.get_cog("ShopCog"), "shop_cache"):
            shop_cache = self.client.get_cog("ShopCog").shop_cache
            if cache_key in shop_cache and current_time - shop_cache[cache_key]["timestamp"] < 300:
                self.shop_data = shop_cache[cache_key]["data"]
            else:
                self.shop_data = await self.fetch_shop_data()
        else:
            self.shop_data = await self.fetch_shop_data()

        if not self.shop_data:
            self.shop_data = {
                "Pokeball": 200,
                "Greatball": 600,
                "Ultraball": 1200,
                "Masterball": 50000
            }
        
        # Create item selector (row 0)
        self.item_select = ShopItemSelect(self.shop_data, self.user_data)
        self.item_select.callback = self.item_callback
        self.item_select.row = 0
        self.add_item(self.item_select)
        
        # Add quantity selector (row 1)
        self.quantity_select = QuantitySelect()
        self.quantity_select.callback = self.quantity_callback
        self.quantity_select.disabled = True
        self.quantity_select.row = 1  # Changed from 0 to 1
        self.add_item(self.quantity_select)
        
        # Add the buttons to row 2
        self.purchase_button.row = 2  # Changed from 1 to 2
        self.daily_claim.row = 2      # Changed from 1 to 2
        self.add_item(self.purchase_button)
        self.add_item(self.daily_claim)
        
        return self
    
    async def fetch_shop_data(self):
        """Fetch shop data from database"""
        shop_data = config_collection.find_one({"_id": "shop"})
        if not shop_data:
            # Fallback to default prices
            shop_data = {
                "Pokeball": 200,
                "Greatball": 600,
                "Ultraball": 1200,
                "Masterball": 50000
            }
        
        # Cache the shop data in the cog
        shop_cog = self.client.get_cog("ShopCog")
        if shop_cog and hasattr(shop_cog, "shop_cache"):
            shop_cog.shop_cache["shop_data"] = {
                "data": shop_data,
                "timestamp": time.time()
            }
        
        return shop_data
    
    async def item_callback(self, interaction):
        """Handle item selection"""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your shop menu!", ephemeral=True)
            return
        
        self.selected_item = self.item_select.values[0]
        
        # Update the placeholder to show selected item
        self.item_select.placeholder = f"Selected: {self.selected_item}"
        
        # Enable quantity selection
        self.quantity_select.disabled = False
        
        # Update UI with item details and preview
        await self.update_purchase_preview(interaction)

    async def quantity_callback(self, interaction):
        """Handle quantity selection"""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your shop menu!", ephemeral=True)
            return
        
        self.selected_quantity = int(self.quantity_select.values[0])
        
        # Update the placeholder to show selected quantity
        self.quantity_select.placeholder = f"Quantity: {self.selected_quantity}"
        
        # Enable purchase button
        self.purchase_button.disabled = False
        
        # Update UI with quantity details and preview
        await self.update_purchase_preview(interaction)
    
    async def update_purchase_preview(self, interaction):
        """Update the shop UI with purchase preview"""
        item_price = self.shop_data.get(self.selected_item, 0)
        total_price = item_price * self.selected_quantity
        pokedollars = self.user_data.get("Pokedollars", 0)
        
        # Build preview embed
        embed = discord.Embed(
            title="🛒 Pokémart",
            description=f"Shopping for {self.selected_item}s",
            color=discord.Color.blue()
        )
        
        # Item image
        item_images = {
            "Pokeball": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/poke-ball.png",
            "Greatball": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/great-ball.png",
            "Ultraball": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/ultra-ball.png",
            "Masterball": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/master-ball.png"
        }
        
        if self.selected_item in item_images:
            embed.set_thumbnail(url=item_images[self.selected_item])
        
        # Purchase details
        embed.add_field(
            name="Item Details",
            value=f"**{self.selected_item}**\nPrice: {item_price} Pokédollars each",
            inline=True
        )
        
        embed.add_field(
            name="Purchase Summary",
            value=(
                f"Quantity: **{self.selected_quantity}**\n"
                f"Total Cost: **{total_price:,}** Pokédollars"
            ),
            inline=True
        )
        
        # Affordability check
        can_afford = pokedollars >= total_price
        
        embed.add_field(
            name="Your Balance",
            value=(
                f"Current: **{pokedollars:,}** Pokédollars\n"
                f"After Purchase: **{pokedollars - total_price:,}** Pokédollars\n"
                f"{'✅ You can afford this!' if can_afford else '❌ Not enough Pokédollars!'}"
            ),
            inline=False
        )
        
        # Update purchase button status based on affordability
        self.purchase_button.disabled = not can_afford
        
        # Update the message
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def purchase_callback(self, interaction):
        """Handle the purchase button click"""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your shop menu!", ephemeral=True)
            return
        
        item_price = self.shop_data.get(self.selected_item, 0)
        total_price = item_price * self.selected_quantity
        pokedollars = self.user_data.get("Pokedollars", 0)
        
        # Double-check if the user can afford the purchase
        if pokedollars < total_price:
            await interaction.response.send_message(
                "You don't have enough Pokédollars for this purchase!",
                ephemeral=True
            )
            return
        
        # Map item names to database fields
        db_field_mapping = {
            "Pokeball": "Pokeballs",
            "Greatball": "Greatballs",
            "Ultraball": "Ultraballs",
            "Masterball": "Masterballs"
        }
        
        db_field = db_field_mapping.get(self.selected_item)
        
        # Process the purchase - Fixed: Added braces around the update query
        await update_user_data(
            str(self.ctx.author.id),
            {  # Added opening brace
                "$inc": {
                    "Pokedollars": -total_price,
                    db_field: self.selected_quantity
                }
            }  # Added closing brace
        )
        
        # Create success embed
        success_embed = discord.Embed(
            title="✅ Purchase Successful",
            description=f"You bought {self.selected_quantity} {self.selected_item}(s) for {total_price:,} Pokédollars!",
            color=discord.Color.green()
        )
        
        # Item image
        item_images = {
            "Pokeball": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/poke-ball.png",
            "Greatball": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/great-ball.png",
            "Ultraball": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/ultra-ball.png",
            "Masterball": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/master-ball.png"
        }
        
        if self.selected_item in item_images:
            success_embed.set_thumbnail(url=item_images[self.selected_item])
        
        # Show new balance
        new_balance = pokedollars - total_price
        success_embed.set_footer(text=f"Your new balance: {new_balance:,} Pokédollars")
        
        # Disable all buttons
        for child in self.children:
            child.disabled = True
        
        await interaction.response.edit_message(embed=success_embed, view=self)
        self.stop()
    
    async def daily_callback(self, interaction):
        """Handle the daily claim button"""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your shop menu!", ephemeral=True)
            return
        
        # Create a new context from the interaction for the command
        ctx = await self.client.get_context(interaction.message)
        ctx.author = interaction.user
        
        # IMPORTANT: Defer the response to prevent "interaction failed"
        await interaction.response.defer()
        
        # Disable the button to prevent multiple claims
        self.daily_claim.disabled = True
        
        # Now invoke the command after deferring
        daily_command = self.client.get_command('claim_daily')
        await ctx.invoke(daily_command)
        
        # Update the shop view with disabled daily button
        await interaction.message.edit(view=self)
    
    async def interaction_check(self, interaction):
        """Only allow the original command user to use the buttons"""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your shop menu!", ephemeral=True)
            return False
        return True

class ShopCog(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.shop_cache = {
            "shop_data": {
                "data": {
                    "Pokeball": 200,
                    "Greatball": 600,
                    "Ultraball": 1200,
                    "Masterball": 50000
                },
                "timestamp": time.time()
            }
        }
        self.CACHE_TIMEOUT = 300  # 5 minutes cache timeout
    
    @commands.command(aliases=["pm", "mart"])
    async def pokemart(self, ctx):
        """Visit the Pokémart to buy items using an interactive UI"""
        print(f"Pokemart command called by {ctx.author.name}")
        try:
            # Get user data
            user_id = str(ctx.author.id)
            user_data = await get_user_data(user_id)
            
            if not user_data:
                await ctx.send("You have not begun your adventure! Start by using the `%start` command.")
                return
            
            print(f"User data fetched: {user_data.keys()}")
            
            # Create shop embed
            embed = discord.Embed(
                title="🛒 Pokémart",
                description="Welcome to the Pokémart! Use the dropdown menu below to browse our selection of items.",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Instructions",
                value=(
                    "1. Select an item from the dropdown menu\n"
                    "2. Choose the quantity you wish to purchase\n"
                    "3. Click the Purchase button to confirm"
                ),
                inline=False
            )
            
            # Show user's balance
            pokedollars = user_data.get("Pokedollars", 0)
            embed.set_footer(text=f"Your balance: {pokedollars:,} Pokédollars • Use %daily to claim your daily reward")
            
            # Create and initialize shop view
            view = await ShopView(ctx, self.client, user_data).initialize()
            await ctx.send(embed=embed, view=view)
        except Exception as e:
            print(f"ERROR in pokemart command: {type(e).__name__}: {e}")
            await ctx.send(f"An error occurred while opening the shop: {str(e)}")
    
    @commands.command(aliases=["daily"])
    async def claim_daily(self, ctx):
        """Claim your daily Pokédollars reward"""
        user_id = str(ctx.author.id)
        user_data = await get_user_data(user_id)
        
        if not user_data:
            await ctx.send("You have not begun your adventure! Start by using the `%start` command.")
            return
        
        # Check if user has already claimed their daily reward
        current_time = int(time.time())
        last_claim = user_data.get("last_daily_claim", 0)
        
        # Calculate time since last claim
        time_difference = current_time - last_claim
        seconds_in_day = 86400  # 24 hours in seconds
        
        if time_difference < seconds_in_day:
            # User already claimed today
            time_remaining = seconds_in_day - time_difference
            hours = time_remaining // 3600
            minutes = (time_remaining % 3600) // 60
            
            cooldown_embed = discord.Embed(
                title="⏰ Daily Reward on Cooldown",
                description=f"You've already claimed your daily reward!\nCome back in **{hours} hours and {minutes} minutes**.",
                color=discord.Color.orange()
            )
            cooldown_embed.set_footer(text="Daily rewards reset at midnight UTC")
            await ctx.send(embed=cooldown_embed)
            return
        
        # Calculate the reward amount (base + streak bonus)
        current_streak = user_data.get("daily_streak", 0)
        
        # Check if the streak should continue or reset
        if time_difference <= seconds_in_day * 2:  # Within 48 hours of last claim
            new_streak = current_streak + 1
        else:
            new_streak = 1  # Reset streak
        
        # Calculate reward based on streak
        base_reward = 1000
        streak_bonus = min(new_streak * 100, 1000)  # Cap streak bonus at 1000
        total_reward = base_reward + streak_bonus
        
        # Update user data - Fixed: Added braces around the update query
        await update_user_data(
            user_id,
            {  # Added opening brace
                "$inc": {"Pokedollars": total_reward},
                "$set": {
                    "last_daily_claim": current_time,
                    "daily_streak": new_streak
                }
            }  # Added closing brace
        )
        
        # Create reward embed
        reward_embed = discord.Embed(
            title="💰 Daily Reward Claimed!",
            description=f"You received **{total_reward:,} Pokédollars**!",
            color=discord.Color.gold()
        )
        
        reward_embed.add_field(
            name="Reward Breakdown",
            value=f"Base reward: {base_reward:,} Pokédollars\n" +
                  f"Streak bonus: {streak_bonus:,} Pokédollars",
            inline=False
        )
        
        reward_embed.add_field(
            name="Current Streak",
            value=f"**{new_streak} day{'' if new_streak == 1 else 's'}**",
            inline=True
        )
        
        # Get updated balance
        updated_data = await get_user_data(user_id)
        new_balance = updated_data.get("Pokedollars", 0)
        
        reward_embed.set_footer(text=f"Your new balance: {new_balance:,} Pokédollars")
        
        await ctx.send(embed=reward_embed)
    
    @commands.command(aliases=["sh", "store"])
    async def shop(self, ctx):
        """Alias for pokemart command"""
        await self.pokemart(ctx)

async def setup(client):
    await client.add_cog(ShopCog(client))