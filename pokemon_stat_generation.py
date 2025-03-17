import json
import random
import os

def generate_iv():
    return random.randint(0, 31)

def calculate_stat(base, iv, level, ev=0, nature=1):
    return int((((2 * base + iv + (ev // 4)) * level) // 100 + 5) * nature) #got this calculation from chatgpt dont ask me what this is

def generate_unique_id():
    # Path to the file storing the last used ID
    last_id_file = "last_unique_id.txt"
    
    # Read the last used ID
    if os.path.exists(last_id_file):
        with open(last_id_file, "r") as file:
            last_id = int(file.read().strip())
    else:
        last_id = 0

    # Increment the last used ID
    new_id = last_id + 1

    # Update the last used ID in the file
    with open(last_id_file, "w") as file:
        file.write(str(new_id).zfill(6))  # Ensure the ID is zero-padded to 6 digits

    return str(new_id).zfill(6)  # Return the new ID as a zero-padded string

def store_caught_pokemon(pokemon_data, user_id, shiny, level):
    ivs = {
        "hp": generate_iv(),
        "attack": generate_iv(),
        "defense": generate_iv(),
        "special-attack": generate_iv(),
        "special-defense": generate_iv(),
        "speed": generate_iv()
    }

    unique_id = generate_unique_id()  # Generate a new unique identifier

    # Store full Pokémon data separately in "caught_pokemon_data.json"
    caught_pokemon = {
        "unique_id": unique_id,
        "pokedex_id": pokemon_data["id"],
        "name": pokemon_data["name"],
        "shiny": shiny,
        "level": level,
        "ivs": ivs,
        "base_stats": pokemon_data["stats"],
        "final_stats": {
            "hp": calculate_stat(pokemon_data["stats"]["hp"], ivs["hp"], level),
            "attack": calculate_stat(pokemon_data["stats"]["attack"], ivs["attack"], level),
            "defense": calculate_stat(pokemon_data["stats"]["defense"], ivs["defense"], level),
            "special-attack": calculate_stat(pokemon_data["stats"]["special-attack"], ivs["special-attack"], level),
            "special-defense": calculate_stat(pokemon_data["stats"]["special-defense"], ivs["special-defense"], level),
            "speed": calculate_stat(pokemon_data["stats"]["speed"], ivs["speed"], level)
        }
    }

    # Save the caught Pokémon data in "caught_pokemon_data.json"
    with open("caught_pokemon_data.json", "r+") as file:
        try:
            data = json.load(file)
        except json.JSONDecodeError:
            data = {}  # If the file is empty or invalid, start with an empty dictionary
        data[unique_id] = caught_pokemon
        file.seek(0)
        json.dump(data, file, indent=1)
        file.truncate()

    # Update the user's inventory in "Inventory.json"
    with open("Inventory.json", "r+") as file:
        try:
            inventory = json.load(file)
        except json.JSONDecodeError:
            inventory = {"users": {}}  # Ensure a valid structure

        # Ensure the user's data exists
        if "users" not in inventory:
            inventory["users"] = {}

        if str(user_id) not in inventory["users"]:
            inventory["users"][str(user_id)] = {"caught_pokemon": []}

        # Store only the unique_id inside "caught_pokemon"
        if "caught_pokemon" not in inventory["users"][str(user_id)]:
            inventory["users"][str(user_id)]["caught_pokemon"] = []

        inventory["users"][str(user_id)]["caught_pokemon"].append(unique_id)

        file.seek(0)
        json.dump(inventory, file, indent=1)
        file.truncate()

    return unique_id  # Return the unique ID of the caught Pokémon
