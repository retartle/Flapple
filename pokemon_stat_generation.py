import json
import random
import os
from pymongo import MongoClient

def generate_iv():
    return random.randint(0, 31)

def calculate_stat(base, iv, level, ev=0, nature=1, is_hp=False):
    if is_hp:
        # HP formula: floor((2 * B + I + E) * L / 100 + L + 10)
        return int((2 * base + iv + (ev // 4)) * level // 100 + level + 10)
    else:
        # Other stats: floor(floor((2 * B + I + E) * L / 100 + 5) * N)
        return int((((2 * base + iv + (ev // 4)) * level) // 100 + 5) * nature)

def generate_unique_id():
    from main import unique_id_collection
    result = unique_id_collection.find_one_and_update(
        {},
        {"$inc": {"last_id": 1}},
        upsert=True,
        return_document=True
    )
    return str(result["last_id"]).zfill(6)

def calculate_min_xp_for_level(level):
        """
        Calculates the minimum total XP required to reach a given level.
        Based on the Medium Slow growth rate formula variation found in the project.
        T(L) = floor( (6/5)L³ - 15L² + 100L - 140 )

        Args:
            level (int): The target level.

        Returns:
            int: The minimum total XP required to reach that level.
        """
        if level <= 1:
            return 0
        # Formula derived from the level-up check in main.py (appears to be Medium Slow group)
        total_xp = int((6/5) * (level**3) - (15 * (level**2)) + (100 * level) - 140)
        # Ensure XP is not negative for low levels if the formula dips below zero
        return max(0, total_xp)

def generate_ability(pokemon_base_data):
    """
    Generates an ability for a Pokémon based on its possible abilities.
    Handles hidden ability chance and equal probability for non-hidden ones.

    :param pokemon_base_data: The dictionary containing the base data for the Pokémon species,
                              including the 'abilities' list.
    :return: The name of the chosen ability (str) or None if no abilities are found.
    """
    if "abilities" not in pokemon_base_data or not pokemon_base_data["abilities"]:
        return None # No abilities listed for this Pokémon

    possible_abilities = pokemon_base_data["abilities"]
    hidden_ability = None
    non_hidden_abilities = []

    for ability_info in possible_abilities:
        if ability_info.get("is_hidden", False):
            hidden_ability = ability_info.get("name")
        else:
            non_hidden_abilities.append(ability_info.get("name"))

    chosen_ability = None
    hidden_ability_chance = 1 / 150  # Adjust as needed (e.g., 1/150)

    # Check for hidden ability first
    if hidden_ability and random.random() < hidden_ability_chance:
        chosen_ability = hidden_ability
    # If hidden ability didn't proc or doesn't exist, choose from non-hidden
    elif non_hidden_abilities:
        chosen_ability = random.choice(non_hidden_abilities)
    # Fallback if only a hidden ability exists but didn't proc (should be rare)
    elif hidden_ability:
         chosen_ability = hidden_ability


    return chosen_ability

def generate_nature(partner_nature=None, has_synchronize=False):
    """
    Generate a Pokémon nature based on the following rules:
    - If partner has Synchronize ability, 50% chance to match partner's nature
    - Otherwise, randomly select from 25 available natures with equal probability
    
    :param partner_nature: The nature of the partner Pokémon (if applicable)
    :param has_synchronize: Whether the partner Pokémon has the Synchronize ability
    :return: The generated nature as a string
    """
    natures = [
        "Adamant", "Bashful", "Bold", "Brave", "Calm", "Careful", "Docile", "Gentle", "Hardy", "Hasty",
        "Impish", "Jolly", "Lax", "Lonely", "Mild", "Modest", "Naive", "Naughty", "Quiet", "Quirky",
        "Rash", "Relaxed", "Sassy", "Serious", "Timid"
    ]
    
    # If partner has Synchronize and a valid nature, 50% chance to match
    if has_synchronize and partner_nature in natures:
        if random.random() < 0.5:
            return partner_nature
    
    # Otherwise, select a random nature with equal probability
    return random.choice(natures)


def store_caught_pokemon(pokemon_data, user_id, shiny, level, nature):
    from main import inventory_collection, pokemon_collection
    ivs = {
        "hp": generate_iv(),
        "attack": generate_iv(),
        "defense": generate_iv(),
        "special-attack": generate_iv(),
        "special-defense": generate_iv(),
        "speed": generate_iv()
    }

    unique_id = generate_unique_id()

    generated_ability_name = generate_ability(pokemon_data) 

    initial_xp = calculate_min_xp_for_level(level)

    caught_pokemon = {
        "_id": unique_id,
        "pokedex_id": pokemon_data["id"],
        "name": pokemon_data["name"],
        "nickname": None,
        "shiny": shiny,
        "level": level,
        "nature": nature,  
        "ivs": ivs,
        "base_stats": pokemon_data["stats"],
        "final_stats": {
            "hp": calculate_stat(pokemon_data["stats"]["hp"], ivs["hp"], level, is_hp=True),
            "attack": calculate_stat(pokemon_data["stats"]["attack"], ivs["attack"], level),
            "defense": calculate_stat(pokemon_data["stats"]["defense"], ivs["defense"], level),
            "special-attack": calculate_stat(pokemon_data["stats"]["special-attack"], ivs["special-attack"], level),
            "special-defense": calculate_stat(pokemon_data["stats"]["special-defense"], ivs["special-defense"], level),
            "speed": calculate_stat(pokemon_data["stats"]["speed"], ivs["speed"], level)
        },
        "xp": initial_xp,
        "ability": generated_ability_name
    }

    # Insert the caught Pokémon data into MongoDB
    pokemon_collection.insert_one(caught_pokemon)

    # Update the user's inventory in MongoDB
    inventory_collection.update_one(
        {"_id": str(user_id)},
        {"$push": {"caught_pokemon": unique_id}},
        upsert=True
    )

    return unique_id