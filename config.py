import os
from pymongo import MongoClient

# MongoDB connection
client = MongoClient(os.getenv('Mongo_API'))
db = client.flapple

# Collections
inventory_collection = db.inventory
pokemon_collection = db.caught_pokemon
unique_id_collection = db.unique_id
move_collection = db.moves
config_collection = db.config

# Constants
starter_pokemon_generations = {
    1: [1, 4, 7],  # Bulbasaur, Charmander, Squirtle
    2: [152, 155, 158],  # Chikorita, Cyndaquil, Totodile
    3: [252, 255, 258],  # Treecko, Torchic, Mudkip
    4: [387, 390, 393],  # Turtwig, Chimchar, Piplup
    5: [495, 498, 501],  # Snivy, Tepig, Oshawott
    6: [650, 653, 656],  # Chespin, Fennekin, Froakie
    7: [722, 725, 728],  # Rowlet, Litten, Popplio
    8: [810, 813, 816],  # Grookey, Scorbunny, Sobble
    9: [906, 909, 912] # Sprigatito, Fuecoco, Quaxly
}

# Active user tracking (shared between cogs)
active_catchers = set()
user_cooldowns = {}

# Export all variables
__all__ = [
    'db', 'inventory_collection', 'pokemon_collection', 'unique_id_collection',
    'move_collection', 'config_collection', 'starter_pokemon_generations',
    'active_catchers', 'user_cooldowns'
]