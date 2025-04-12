# cogs/misc.py
import discord
import asyncio
import time
from discord.ext import commands
from config import inventory_collection, user_cooldowns, config_collection, pokemon_collection
from utils.db_utils import get_user_data, update_user_data, get_pokemon_data, update_pokemon_data

class MiscCog(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.cooldown_seconds = 2  # Message cooldown for XP gain
    
    @commands.command()
    async def ping(self, ctx):
        """Check the bot's latency"""
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"The current ping is {round(self.client.latency * 1000)}ms!",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)
    
    @commands.command(aliases=["bal"])
    async def balance(self, ctx):
        """Check your Pokédollar balance"""
        user_id = str(ctx.author.id)
        user_data = await get_user_data(user_id)
        
        if not user_data:
            await ctx.send("You have not begun your adventure! Start by using the `%start` command.")
            return
        
        pokedollars = user_data.get("Pokedollars", 0)
        
        embed = discord.Embed(
            title="💰 Pokédollar Balance",
            description=f"You have **{pokedollars:,}** Pokédollars",
            color=discord.Color.gold()
        )
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
        embed.set_footer(text="Use %pokemart to purchase items")
        
        await ctx.send(embed=embed)
    
    @commands.command(aliases=["settings", "prefs"])
    async def set_preferences(self, ctx, setting=None, value=None):
        """Change user preferences and settings"""
        user_id = str(ctx.author.id)
        
        # Get user data
        user_data = await get_user_data(user_id)
        
        if not user_data:
            await ctx.send("You haven't started your adventure yet. Use `%start` to begin!")
            return
        
        # Initialize settings if they don't exist
        if "settings" not in user_data:
            await update_user_data(
                user_id,
                {"$set": {
                    "settings": {
                        "environment_rendering": "off"  # off, static, animated
                    }
                }}
            )
            user_data = await get_user_data(user_id)
        
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
                      "Change with: `%settings environment [off/static/animated]`",
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
            await update_user_data(
                user_id,
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
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Handle XP gain for partner Pokémon"""
        # Ignore messages from the bot itself
        if message.author == self.client.user:
            return
        
        # Check cooldown to prevent XP farming
        user_id = str(message.author.id)
        current_time = time.time()
        
        if user_id in user_cooldowns and current_time - user_cooldowns[user_id] < self.cooldown_seconds:
            return
        
        # Update the cooldown
        user_cooldowns[user_id] = current_time
        
        # Get user data and check for partner Pokémon
        user_data = await get_user_data(user_id)
        if not user_data or "partner_pokemon" not in user_data or not user_data["partner_pokemon"]:
            return
        
        partner_id = user_data["partner_pokemon"]
        partner_pokemon = await get_pokemon_data(partner_id)
        
        if not partner_pokemon:
            return
        
        # Award XP
        xp_reward = 10
        new_xp = partner_pokemon.get("xp", 0) + xp_reward
        
        # Update the Pokémon's XP
        await update_pokemon_data(
            partner_id,
            {"$set": {"xp": new_xp}}
        )
        
        # Check for level up
        level = partner_pokemon["level"]
        next_level_xp = int((6/5) * ((level + 1)**3) - (15 * ((level + 1)**2)) + (100 * (level + 1)) - 140)
        
        if new_xp >= next_level_xp:
            # Level up the Pokémon
            excess_xp = new_xp - next_level_xp
            
            # Update the Pokémon's level and set XP to excess
            await update_pokemon_data(
                partner_id,
                {
                    "$inc": {"level": 1},
                    "$set": {"xp": excess_xp}
                }
            )
            
            # Recalculate stats after level up
            from utils.pokemon_utils import calculate_stat
            
            # Get the Pokémon's base stats and IVs
            base_stats = partner_pokemon["base_stats"]
            ivs = partner_pokemon["ivs"]
            new_level = level + 1
            
            # Calculate new final stats
            new_final_stats = {
                "hp": calculate_stat(base_stats["hp"], ivs["hp"], new_level, is_hp=True),
                "attack": calculate_stat(base_stats["attack"], ivs["attack"], new_level),
                "defense": calculate_stat(base_stats["defense"], ivs["defense"], new_level),
                "special-attack": calculate_stat(base_stats["special-attack"], ivs["special-attack"], new_level),
                "special-defense": calculate_stat(base_stats["special-defense"], ivs["special-defense"], new_level),
                "speed": calculate_stat(base_stats["speed"], ivs["speed"], new_level)
            }
            
            # Update the Pokémon's final stats
            await update_pokemon_data(
                partner_id,
                {"$set": {"final_stats": new_final_stats}}
            )
            
            # Get Pokémon name for level up message
            name = partner_pokemon["name"].capitalize().replace('-', ' ')
            nickname = partner_pokemon.get("nickname")
            display_name = f"{nickname} ({name})" if nickname else name
            
            if partner_pokemon.get("shiny"):
                display_name += " ⭐"
            
            # Send level up message
            level_up_embed = discord.Embed(
                title="🎉 Level Up!",
                description=f"{message.author.mention}'s partner **{display_name}** leveled up to level {new_level}!",
                color=discord.Color.green()
            )
            
            # Try to get sprite URL
            from utils.pokemon_utils import search_pokemon_by_id, get_best_sprite_url
            
            pokemon_data = search_pokemon_by_id(partner_pokemon["pokedex_id"])
            if pokemon_data:
                sprite_url = await get_best_sprite_url(pokemon_data, partner_pokemon.get("shiny", False))
                if sprite_url:
                    level_up_embed.set_thumbnail(url=sprite_url)
            
            await message.channel.send(embed=level_up_embed)
    
    @commands.command()
    async def cooldowns(self, ctx):
        """View your active cooldowns"""
        user_id = str(ctx.author.id)
        current_time = time.time()
        
        user_data = await get_user_data(user_id)
        if not user_data:
            await ctx.send("You have not begun your adventure! Start by using the `%start` command.")
            return
        
        # Get cooldown data
        cooldown_data = user_data.get("cooldowns", {})
        
        # Create embed
        embed = discord.Embed(
            title="⏱️ Active Cooldowns",
            description="Your current command cooldowns:",
            color=discord.Color.blue()
        )
        
        # Check message cooldown for XP
        message_cooldown = 0
        if user_id in user_cooldowns:
            time_since = current_time - user_cooldowns[user_id]
            if time_since < self.cooldown_seconds:
                message_cooldown = self.cooldown_seconds - time_since
        
        # Add message cooldown to embed if active
        if message_cooldown > 0:
            embed.add_field(
                name="Message XP",
                value=f"Ready in {message_cooldown:.1f} seconds",
                inline=True
            )
        else:
            embed.add_field(
                name="Message XP",
                value="Ready!",
                inline=True
            )
        
        # If no cooldowns, show a message
        if len(embed.fields) == 0:
            embed.description = "You have no active cooldowns!"
        
        embed.set_footer(text=f"Requested by {ctx.author}")
        await ctx.send(embed=embed)

async def setup(client):
    await client.add_cog(MiscCog(client))
