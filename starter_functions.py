import discord
import asyncio
import random
from pokemon_functions import search_pokemon_by_id, get_best_sprite_url
from pokemon_stat_generation import store_caught_pokemon

async def select_generation(ctx, client, starter_pokemon_generations):
    """Prompt the user to select a generation and return the chosen generation."""
    generations = list(starter_pokemon_generations.keys())
    embed = discord.Embed(
        title="Choose a Generation!",
        description="React with the corresponding number to choose a Generation."
    )
    reactions = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
    gen_reactions = reactions[:len(generations)]
    
    for i, gen in enumerate(generations):
        embed.add_field(name=f"{i+1}. Generation {gen}", value=" ", inline=False)
    message = await ctx.send(embed=embed)
    
    for r in gen_reactions:
        await message.add_reaction(r)
    
    def check(reaction, user):
        return (user == ctx.author and 
                str(reaction.emoji) in gen_reactions and 
                reaction.message.id == message.id)

    try:
        reaction, _ = await client.wait_for('reaction_add', timeout=60.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send("You took too long to choose a generation!")
        return None

    generation_index = gen_reactions.index(str(reaction.emoji))
    chosen_generation = generations[generation_index]
    await message.delete()
    return chosen_generation

async def preview_and_select_starter(ctx, client, chosen_generation, starter_pokemon_generations):
    """
    Show a paginated preview of the starters from the chosen generation.
    Each page displays extra details (type and a short description).
    Returns the chosen starter dictionary or None if the user opts to reselect generation.
    """
    starter_ids = starter_pokemon_generations[chosen_generation]
    starters = []
    for sid in starter_ids:
        p = search_pokemon_by_id(sid)
        starter_name = p["name"].capitalize()
        sprite_url = await get_best_sprite_url(p, False)
        starter_types = ", ".join([t.capitalize() for t in p.get("types", [])]) if p.get("types") else "Unknown"
        # Get the first sentence of the description (if available)
        description = p.get("description", "No description available.")
        starter_desc = description.split(".")[0] + "." if "." in description else description
        starters.append({
            "id": sid,
            "name": starter_name,
            "sprite": sprite_url,
            "types": starter_types,
            "description": starter_desc
        })
    
    current_page = 0
    total_pages = len(starters)

    def get_embed(page):
        starter = starters[page]
        embed = discord.Embed(
            title=f"Generation {chosen_generation} Starter Preview",
            description=f"Starter {page + 1} of {total_pages}: **{starter['name']}**"
        )
        if starter["sprite"]:
            embed.set_image(url=starter["sprite"])
        embed.add_field(name="Type", value=starter["types"], inline=True)
        embed.add_field(name="Description", value=starter["description"], inline=False)
        embed.set_footer(text="React with ◀️/▶️ to navigate, ✅ to select, or 🔙 to reselect generation.")
        return embed

    preview_message = await ctx.send(embed=get_embed(current_page))
    control_reactions = ["◀️", "▶️", "✅", "🔙"]
    for emoji in control_reactions:
        await preview_message.add_reaction(emoji)

    while True:
        try:
            reaction, _ = await client.wait_for(
                'reaction_add',
                timeout=60.0,
                check=lambda r, u: u == ctx.author and r.message.id == preview_message.id and str(r.emoji) in control_reactions
            )
        except asyncio.TimeoutError:
            await ctx.send("You took too long to select a starter!")
            return None

        await preview_message.remove_reaction(reaction, ctx.author)
        emoji = str(reaction.emoji)

        if emoji == "◀️" and current_page > 0:
            current_page -= 1
            await preview_message.edit(embed=get_embed(current_page))
        elif emoji == "▶️" and current_page < total_pages - 1:
            current_page += 1
            await preview_message.edit(embed=get_embed(current_page))
        elif emoji == "🔙":
            await preview_message.delete()
            return None  # Signal to reselect generation
        elif emoji == "✅":
            chosen_starter = starters[current_page]
            await preview_message.delete()
            return chosen_starter

def set_user_starter(ctx, starter):
    from main import inventory_collection
    is_shiny = random.choices([True, False], weights=[1, 4095], k=1)[0]
    full_starter_data = search_pokemon_by_id(starter["id"])
    unique_id = store_caught_pokemon(full_starter_data, str(ctx.author.id), is_shiny, 5)
    
    # Update user's inventory in MongoDB
    inventory_collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$push": {"caught_pokemon": unique_id}, "$set": {"partner_pokemon": unique_id}},
        upsert=True
    )
    
    return unique_id

async def create_starter_summary_embed(ctx, starter, full_data, unique_id, is_shiny):
    """
    Creates an embed summary of the chosen starter, including type, catch rate, description,
    and indicates if it is shiny.
    """
    embed = discord.Embed(
        title="Your New Partner!" + (" ⭐" if is_shiny else ""),
        description=f"{ctx.author.mention}, you have chosen **{starter['name']}** as your starter!",
        color=discord.Color.blue()
    )
    starter_types = ", ".join([t.capitalize() for t in full_data.get("types", [])]) if full_data.get("types") else "Unknown"
    embed.add_field(name="Type", value=starter_types, inline=True)
    embed.add_field(name="Catch Rate", value=full_data.get("catch_rate", "Unknown"), inline=True)
    embed.add_field(name="Description", value=full_data.get("description", "No description available."), inline=False)
    if full_data.get("sprites"):
        sprite_url = await get_best_sprite_url(full_data, is_shiny)
        embed.set_thumbnail(url=sprite_url)
    embed.set_footer(text=f"Unique ID: {unique_id}")
    return embed
