# utils/db_utils.py
import time
from config import inventory_collection, pokemon_collection

# Cache for database queries
user_cache = {}
pokemon_cache = {}
pokemon_bulk_cache = {}

# Cache timeout in seconds (5 minutes)
CACHE_TIMEOUT = 300

async def get_user_data(user_id):
    """Get user data with caching"""
    current_time = time.time()
    
    # Check cache first
    if user_id in user_cache and current_time - user_cache[user_id]["timestamp"] < CACHE_TIMEOUT:
        return user_cache[user_id]["data"]
    
    # Fetch from database
    user_data = inventory_collection.find_one({"_id": user_id})
    
    # Cache the result if found
    if user_data:
        user_cache[user_id] = {
            "data": user_data,
            "timestamp": current_time
        }
    
    return user_data

async def get_pokemon_data(pokemon_id):
    """Get a single Pokémon's data with caching"""
    current_time = time.time()
    
    # Check cache first
    if pokemon_id in pokemon_cache and current_time - pokemon_cache[pokemon_id]["timestamp"] < CACHE_TIMEOUT:
        return pokemon_cache[pokemon_id]["data"]
    
    # Fetch from database
    pokemon_data = pokemon_collection.find_one({"_id": pokemon_id})
    
    # Cache the result if found
    if pokemon_data:
        pokemon_cache[pokemon_id] = {
            "data": pokemon_data,
            "timestamp": current_time
        }
    
    return pokemon_data

async def get_pokemon_bulk(pokemon_ids):
    """Get multiple Pokémon in a single query with caching"""
    current_time = time.time()
    
    # Create a cache key from the sorted list of IDs to ensure consistency
    cache_key = ",".join(sorted(pokemon_ids))
    
    # Check cache first
    if cache_key in pokemon_bulk_cache and current_time - pokemon_bulk_cache[cache_key]["timestamp"] < CACHE_TIMEOUT:
        return pokemon_bulk_cache[cache_key]["data"]
    
    # Check which IDs are not in individual cache
    missing_ids = []
    result_dict = {}
    
    for pokemon_id in pokemon_ids:
        if pokemon_id in pokemon_cache and current_time - pokemon_cache[pokemon_id]["timestamp"] < CACHE_TIMEOUT:
            # Use cached data
            result_dict[pokemon_id] = pokemon_cache[pokemon_id]["data"]
        else:
            # Need to fetch this ID
            missing_ids.append(pokemon_id)
    
    # OPTIMIZATION: Fetch missing Pokémon data in a single query
    if missing_ids:
        pokemon_list = list(pokemon_collection.find({"_id": {"$in": missing_ids}}))
        
        # Add to individual cache and result dict
        for pokemon in pokemon_list:
            pokemon_id = pokemon["_id"]
            pokemon_cache[pokemon_id] = {
                "data": pokemon,
                "timestamp": current_time
            }
            result_dict[pokemon_id] = pokemon
    
    # Cache the bulk result
    pokemon_bulk_cache[cache_key] = {
        "data": result_dict,
        "timestamp": current_time
    }
    
    return result_dict

def invalidate_cache(user_id=None, pokemon_id=None):
    """Invalidate cache entries when data changes"""
    if user_id and user_id in user_cache:
        del user_cache[user_id]
    
    if pokemon_id and pokemon_id in pokemon_cache:
        del pokemon_cache[pokemon_id]
        
        # Also invalidate any bulk caches that might contain this Pokémon
        keys_to_remove = []
        for key in pokemon_bulk_cache:
            if pokemon_id in key.split(","):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            if key in pokemon_bulk_cache:
                del pokemon_bulk_cache[key]
    
    # Clear all cache if no specific ID is provided
    if not user_id and not pokemon_id:
        user_cache.clear()
        pokemon_cache.clear()
        pokemon_bulk_cache.clear()

async def update_user_data(user_id, update_query):
    """Update user data and invalidate cache"""
    result = inventory_collection.update_one({"_id": user_id}, update_query)
    invalidate_cache(user_id=user_id)
    return result

async def update_pokemon_data(pokemon_id, update_query):
    """Update Pokémon data and invalidate cache"""
    result = pokemon_collection.update_one({"_id": pokemon_id}, update_query)
    invalidate_cache(pokemon_id=pokemon_id)
    return result