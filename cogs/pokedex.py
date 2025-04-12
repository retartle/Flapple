# cogs/pokedex.py
import discord
import time
import asyncio
from discord.ext import commands
from config import db, move_collection
from utils.pokemon_utils import get_best_sprite_url, get_type_colour, get_next_evolution

class PokedexCog(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.pokedex_cache = {}
        self.move_cache = {}
        self.CACHE_TIMEOUT = 1800  # 30 minutes cache timeout (longer than other caches since data rarely changes)
    
    @commands.command(aliases=["pd", "dex"])
    async def pokedex(self, ctx, *, pokemon=None):
        """Look up a Pokémon in the Pokédex by name or ID"""
        if not pokemon:
            embed = discord.Embed(
                title="Pokédex Command Usage",
                description="Look up information about any Pokémon by name or number.",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="How to Use",
                value="`%pokedex [name/number]`\n" +
                      "Example: `%pokedex pikachu` or `%pokedex 25`",
                inline=False
            )
            embed.add_field(
                name="Aliases",
                value="You can also use `%pd` or `%dex` as shorter alternatives.",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        # Check cache first
        cache_key = f"pokedex_{pokemon.lower() if isinstance(pokemon, str) else pokemon}"
        current_time = time.time()
        
        if cache_key in self.pokedex_cache and current_time - self.pokedex_cache[cache_key]["timestamp"] < self.CACHE_TIMEOUT:
            await ctx.send(embed=self.pokedex_cache[cache_key]["embed"])
            return
        
        try:
            # Search by ID if input is a number
            if isinstance(pokemon, str) and pokemon.isdigit():
                pokemon = int(pokemon)
                results = db.pokemon.find_one({"id": pokemon})
            else:
                # Search by name
                normalized_name = str(pokemon).lower().replace(' ', '-')
                results = db.pokemon.find_one({"name": normalized_name})
            
            if not results:
                error_embed = discord.Embed(
                    title="Pokémon Not Found",
                    description=f"No data found for '{pokemon}'. Please check the spelling or ID.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=error_embed)
                return
            
            # Create a detailed embed with all available information
            embed = await self.create_pokedex_embed(results, ctx.author)
            
            # Cache the embed
            self.pokedex_cache[cache_key] = {
                "embed": embed,
                "timestamp": current_time
            }
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="Error",
                description=f"An error occurred while retrieving Pokédex data: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=error_embed)
    
    async def create_pokedex_embed(self, pokemon_data, author):
        """Create a detailed Pokédex embed from Pokémon data"""
        pokemon_id = pokemon_data["id"]
        name = pokemon_data["name"].capitalize().replace('-', ' ')
        
        # Get types
        type_list = [t.capitalize() for t in pokemon_data["types"]]
        type_str = " | ".join(type_list)
        
        # Get sprite URL
        sprite_url = await get_best_sprite_url(pokemon_data, False)
        
        # Get evolution info
        evolution_line = pokemon_data.get("evolution_line", [])
        next_evolution = get_next_evolution(evolution_line, pokemon_data["name"]).capitalize()
        
        # Get description
        description = pokemon_data.get("description", "No description available.")
        description = description.replace("\n", " ").replace("POK\u00e9MON", "Pokémon")
        
        # Get color based on primary type
        colour = get_type_colour(type_list)
        
        # Create the embed
        embed = discord.Embed(title=f"#{pokemon_id} {name}", colour=colour)
        
        if sprite_url:
            embed.set_thumbnail(url=sprite_url)
        
        embed.add_field(name="Type", value=type_str, inline=False)
        
        # Add evolution information
        if evolution_line:
            if next_evolution != "-":
                embed.add_field(name="Next Evolution", value=next_evolution, inline=True)
            else:
                embed.add_field(name="Evolution", value="Final Form", inline=True)
            
            # Show full evolution line if it exists
            if len(evolution_line) > 1:
                evo_line_str = " → ".join([name.capitalize() for name in evolution_line])
                embed.add_field(name="Evolution Line", value=evo_line_str, inline=False)
        
        # Add base stats
        if "stats" in pokemon_data:
            stats_str = "\n".join([f"{stat.capitalize()}: {value}" for stat, value in pokemon_data["stats"].items()])
            embed.add_field(name="Base Stats", value=stats_str, inline=True)
        
        # Add physical attributes if available
        if "height" in pokemon_data and "weight" in pokemon_data:
            embed.add_field(name="Height", value=f"{pokemon_data['height']/10} m", inline=True)
            embed.add_field(name="Weight", value=f"{pokemon_data['weight']/10} kg", inline=True)
        
        # Add abilities
        if "abilities" in pokemon_data:
            ability_list = []
            for ability in pokemon_data["abilities"]:
                ability_name = ability.get("name", "").capitalize().replace('-', ' ')
                if ability.get("is_hidden"):
                    ability_list.append(f"{ability_name} (Hidden)")
                else:
                    ability_list.append(ability_name)
            
            abilities = " | ".join(ability_list)
            embed.add_field(name="Abilities", value=abilities, inline=False)
        
        # Add description
        if description:
            embed.add_field(name="Description", value=description, inline=False)
        
        # Add catch rate, egg groups, etc. if available
        if "catch_rate" in pokemon_data:
            embed.add_field(name="Catch Rate", value=f"{pokemon_data['catch_rate']}/255", inline=True)
        
        if "egg_groups" in pokemon_data:
            egg_groups = ", ".join([group.capitalize() for group in pokemon_data["egg_groups"]])
            embed.add_field(name="Egg Groups", value=egg_groups, inline=True)
        
        if "growth_rate" in pokemon_data:
            embed.add_field(name="Growth Rate", value=pokemon_data["growth_rate"].capitalize(), inline=True)
        
        # Get official artwork if available for the footer
        artwork_url = None
        if "sprites" in pokemon_data:
            sprites = pokemon_data["sprites"]
            if "official_artwork" in sprites and sprites["official_artwork"]:
                artwork_url = sprites["official_artwork"]
        
        if artwork_url:
            embed.set_image(url=artwork_url)
        
        embed.set_footer(text=f"Pokédex Entry • Requested by {author.name}")
        
        return embed
    
    @commands.command(aliases=["mv"])
    async def move(self, ctx, *, move_name=None):
        """Look up a move in the Pokédex"""
        if not move_name:
            embed = discord.Embed(
                title="Move Command Usage",
                description="Look up information about any Pokémon move.",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="How to Use",
                value="`%move [name]`\n" +
                      "Example: `%move thunderbolt`",
                inline=False
            )
            embed.add_field(
                name="Aliases",
                value="You can also use `%mv` as a shorter alternative.",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        # Check cache first
        cache_key = f"move_{move_name.lower()}"
        current_time = time.time()
        
        if cache_key in self.move_cache and current_time - self.move_cache[cache_key]["timestamp"] < self.CACHE_TIMEOUT:
            await ctx.send(embed=self.move_cache[cache_key]["embed"])
            return
        
        try:
            # Normalize move name
            normalized_move = move_name.lower().replace(' ', '-')
            
            # Query MongoDB for the move
            results = move_collection.find_one({"name": normalized_move})
            
            if not results:
                error_embed = discord.Embed(
                    title="Move Not Found",
                    description=f"Move '{move_name}' could not be found in the database.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=error_embed)
                return
            
            # Extract move data
            move_id = results.get("id", "Unknown")
            name = results.get("name", "Unknown").capitalize().replace('-', ' ')
            move_type = results.get("type", "Unknown").capitalize()
            pp = results.get("pp", "Unknown")
            power = results.get("power", "Unknown")
            accuracy = results.get("accuracy", "Unknown")
            effect = results.get("effect", "Unknown")
            short_effect = results.get("short_effect", "Unknown")
            damage_class = results.get("damage_class", "Unknown").capitalize()
            target = results.get("target", "Unknown").capitalize().replace('-', ' ')
            
            # Determine color based on move type
            type_colors = {
                "Normal": 0xA8A77A, "Fire": 0xEE8130, "Water": 0x6390F0, "Electric": 0xF7D02C,
                "Grass": 0x7AC74C, "Ice": 0x96D9D6, "Fighting": 0xC22E28, "Poison": 0xA33EA1,
                "Ground": 0xE2BF65, "Flying": 0xA98FF3, "Psychic": 0xF95587, "Bug": 0xA6B91A,
                "Rock": 0xB6A136, "Ghost": 0x735797, "Dragon": 0x6F35FC, "Dark": 0x705746,
                "Steel": 0xB7B7CE, "Fairy": 0xD685AD
            }
            
            color = type_colors.get(move_type, 0xFFFFFF)
            
            # Create embed
            embed = discord.Embed(
                title=f"{name} - Move #{move_id}",
                description=short_effect,
                color=color
            )
            
            # Add primary move information
            embed.add_field(name="Type", value=move_type, inline=True)
            embed.add_field(name="Category", value=damage_class, inline=True)
            embed.add_field(name="PP", value=pp, inline=True)
            
            # Add battle stats
            embed.add_field(name="Power", value=power if power not in [None, "None", "Unknown"] else "—", inline=True)
            embed.add_field(name="Accuracy", value=f"{accuracy}%" if accuracy not in [None, "None", "Unknown"] else "—", inline=True)
            embed.add_field(name="Target", value=target, inline=True)
            
            # Add detailed effect description
            if effect and effect not in [None, "Unknown"]:
                embed.add_field(name="Effect Details", value=effect, inline=False)
            
            # Add footer
            embed.set_footer(text=f"Move data • Requested by {ctx.author.name}")
            
            # Cache the embed
            self.move_cache[cache_key] = {
                "embed": embed,
                "timestamp": current_time
            }
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="Error",
                description=f"An error occurred while retrieving move data: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=error_embed)
    
    @commands.command()
    async def ability(self, ctx, *, ability_name=None):
        """Look up information about a Pokémon ability"""
        if not ability_name:
            embed = discord.Embed(
                title="Ability Command Usage",
                description="Look up information about any Pokémon ability.",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="How to Use",
                value="`%ability [name]`\n" +
                      "Example: `%ability static`",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        try:
            # Normalize ability name
            normalized_ability = ability_name.lower().replace(' ', '-')
            
            # Query MongoDB for the ability
            ability_data = db.abilities.find_one({"name": normalized_ability})
            
            if not ability_data:
                error_embed = discord.Embed(
                    title="Ability Not Found",
                    description=f"Ability '{ability_name}' could not be found in the database.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=error_embed)
                return
            
            # Extract ability data
            name = ability_data.get("name", "Unknown").capitalize().replace('-', ' ')
            effect = ability_data.get("effect", "No description available.")
            short_effect = ability_data.get("short_effect", "No short description available.")
            
            # Create embed
            embed = discord.Embed(
                title=f"{name} Ability",
                description=short_effect,
                color=discord.Color.blue()
            )
            
            # Add detailed effect description
            if effect:
                embed.add_field(name="Effect Details", value=effect, inline=False)
            
            # Find Pokémon with this ability
            pokemon_with_ability = list(db.pokemon.find(
                {"abilities.name": normalized_ability},
                {"id": 1, "name": 1, "abilities": 1}
            ).limit(15))  # Limit to prevent too large embeds
            
            if pokemon_with_ability:
                pokemon_list = []
                for pokemon in pokemon_with_ability:
                    pokemon_name = pokemon["name"].capitalize().replace('-', ' ')
                    # Check if it's a hidden ability for this Pokémon
                    is_hidden = False
                    for ability in pokemon.get("abilities", []):
                        if ability.get("name") == normalized_ability and ability.get("is_hidden", False):
                            is_hidden = True
                            break
                    
                    if is_hidden:
                        pokemon_list.append(f"{pokemon_name} (Hidden)")
                    else:
                        pokemon_list.append(pokemon_name)
                
                # If there are more than 15 Pokémon, add a note
                if len(pokemon_with_ability) == 15:
                    pokemon_list.append("... and more")
                
                embed.add_field(
                    name="Pokémon with this Ability",
                    value=", ".join(pokemon_list),
                    inline=False
                )
            
            # Add footer
            embed.set_footer(text=f"Ability data • Requested by {ctx.author.name}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="Error",
                description=f"An error occurred while retrieving ability data: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=error_embed)
    
    @commands.command()
    async def type(self, ctx, *, type_name=None):
        """Look up information about a Pokémon type"""
        if not type_name:
            embed = discord.Embed(
                title="Type Command Usage",
                description="Look up information about any Pokémon type, including effectiveness.",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="How to Use",
                value="`%type [name]`\n" +
                      "Example: `%type fire`",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        try:
            # Normalize type name
            normalized_type = type_name.lower()
            
            # Type effectiveness data
            type_effectiveness = {
                "normal": {
                    "weak_to": ["fighting"],
                    "resistant_to": [],
                    "immune_to": ["ghost"],
                    "color": 0xA8A77A
                },
                "fire": {
                    "weak_to": ["water", "ground", "rock"],
                    "resistant_to": ["fire", "grass", "ice", "bug", "steel", "fairy"],
                    "immune_to": [],
                    "color": 0xEE8130
                },
                "water": {
                    "weak_to": ["electric", "grass"],
                    "resistant_to": ["fire", "water", "ice", "steel"],
                    "immune_to": [],
                    "color": 0x6390F0
                },
                "electric": {
                    "weak_to": ["ground"],
                    "resistant_to": ["electric", "flying", "steel"],
                    "immune_to": [],
                    "color": 0xF7D02C
                },
                "grass": {
                    "weak_to": ["fire", "ice", "poison", "flying", "bug"],
                    "resistant_to": ["water", "electric", "grass", "ground"],
                    "immune_to": [],
                    "color": 0x7AC74C
                },
                "ice": {
                    "weak_to": ["fire", "fighting", "rock", "steel"],
                    "resistant_to": ["ice"],
                    "immune_to": [],
                    "color": 0x96D9D6
                },
                "fighting": {
                    "weak_to": ["flying", "psychic", "fairy"],
                    "resistant_to": ["bug", "rock", "dark"],
                    "immune_to": [],
                    "color": 0xC22E28
                },
                "poison": {
                    "weak_to": ["ground", "psychic"],
                    "resistant_to": ["grass", "fighting", "poison", "bug", "fairy"],
                    "immune_to": [],
                    "color": 0xA33EA1
                },
                "ground": {
                    "weak_to": ["water", "grass", "ice"],
                    "resistant_to": ["poison", "rock"],
                    "immune_to": ["electric"],
                    "color": 0xE2BF65
                },
                "flying": {
                    "weak_to": ["electric", "ice", "rock"],
                    "resistant_to": ["grass", "fighting", "bug"],
                    "immune_to": ["ground"],
                    "color": 0xA98FF3
                },
                "psychic": {
                    "weak_to": ["bug", "ghost", "dark"],
                    "resistant_to": ["fighting", "psychic"],
                    "immune_to": [],
                    "color": 0xF95587
                },
                "bug": {
                    "weak_to": ["fire", "flying", "rock"],
                    "resistant_to": ["grass", "fighting", "ground"],
                    "immune_to": [],
                    "color": 0xA6B91A
                },
                "rock": {
                    "weak_to": ["water", "grass", "fighting", "ground", "steel"],
                    "resistant_to": ["normal", "fire", "poison", "flying"],
                    "immune_to": [],
                    "color": 0xB6A136
                },
                "ghost": {
                    "weak_to": ["ghost", "dark"],
                    "resistant_to": ["poison", "bug"],
                    "immune_to": ["normal", "fighting"],
                    "color": 0x735797
                },
                "dragon": {
                    "weak_to": ["ice", "dragon", "fairy"],
                    "resistant_to": ["fire", "water", "electric", "grass"],
                    "immune_to": [],
                    "color": 0x6F35FC
                },
                "dark": {
                    "weak_to": ["fighting", "bug", "fairy"],
                    "resistant_to": ["ghost", "dark"],
                    "immune_to": ["psychic"],
                    "color": 0x705746
                },
                "steel": {
                    "weak_to": ["fire", "fighting", "ground"],
                    "resistant_to": ["normal", "grass", "ice", "flying", "psychic", "bug", "rock", "dragon", "steel", "fairy"],
                    "immune_to": ["poison"],
                    "color": 0xB7B7CE
                },
                "fairy": {
                    "weak_to": ["poison", "steel"],
                    "resistant_to": ["fighting", "bug", "dark"],
                    "immune_to": ["dragon"],
                    "color": 0xD685AD
                }
            }
            
            if normalized_type not in type_effectiveness:
                error_embed = discord.Embed(
                    title="Type Not Found",
                    description=f"'{type_name}' is not a valid Pokémon type. Please check the spelling.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=error_embed)
                return
            
            type_data = type_effectiveness[normalized_type]
            
            # Create embed
            embed = discord.Embed(
                title=f"{normalized_type.capitalize()} Type",
                color=type_data["color"]
            )
            
            # Add type effectiveness
            if type_data["weak_to"]:
                embed.add_field(
                    name="Weak to (2x damage)",
                    value=", ".join([t.capitalize() for t in type_data["weak_to"]]),
                    inline=False
                )
            
            if type_data["resistant_to"]:
                embed.add_field(
                    name="Resistant to (0.5x damage)",
                    value=", ".join([t.capitalize() for t in type_data["resistant_to"]]),
                    inline=False
                )
            
            if type_data["immune_to"]:
                embed.add_field(
                    name="Immune to (0x damage)",
                    value=", ".join([t.capitalize() for t in type_data["immune_to"]]),
                    inline=False
                )
            
            # Count Pokémon of this type
            pokemon_count = db.pokemon.count_documents({"types": normalized_type})
            embed.add_field(name="Pokémon Count", value=f"{pokemon_count} Pokémon", inline=True)
            
            # Get some example Pokémon
            sample_pokemon = list(db.pokemon.find(
                {"types": normalized_type},
                {"name": 1, "_id": 0}
            ).limit(10))
            
            if sample_pokemon:
                examples = ", ".join([p["name"].capitalize() for p in sample_pokemon])
                if pokemon_count > 10:
                    examples += f", and {pokemon_count - 10} more"
                embed.add_field(name="Examples", value=examples, inline=False)
            
            # Add footer
            embed.set_footer(text=f"Type data • Requested by {ctx.author.name}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="Error",
                description=f"An error occurred while retrieving type data: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=error_embed)
    
    def invalidate_cache(self, entity_type=None, entity_name=None):
        """Invalidate cache entries"""
        current_time = time.time()
        
        # Remove expired cache entries
        expired_pokedex = [key for key, data in self.pokedex_cache.items() 
                          if current_time - data["timestamp"] > self.CACHE_TIMEOUT]
        for key in expired_pokedex:
            if key in self.pokedex_cache:
                del self.pokedex_cache[key]
        
        expired_moves = [key for key, data in self.move_cache.items() 
                        if current_time - data["timestamp"] > self.CACHE_TIMEOUT]
        for key in expired_moves:
            if key in self.move_cache:
                del self.move_cache[key]
        
        # Invalidate specific cache if requested
        if entity_type == "pokemon" and entity_name:
            for key in list(self.pokedex_cache.keys()):
                if entity_name.lower() in key.lower():
                    del self.pokedex_cache[key]
        elif entity_type == "move" and entity_name:
            for key in list(self.move_cache.keys()):
                if entity_name.lower() in key.lower():
                    del self.move_cache[key]
        elif entity_type == "all":
            self.pokedex_cache.clear()
            self.move_cache.clear()

async def setup(client):
    await client.add_cog(PokedexCog(client))