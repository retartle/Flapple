import json
import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

def connect_to_mongodb():
    """Connect to MongoDB and return the database object"""
    try:
        mongo_uri = os.getenv('Mongo_API')
        if not mongo_uri:
            raise ValueError("Mongo_API environment variable is not set or empty")
        print(f"Connecting to MongoDB...")
        
        # Check if using SRV connection string
        if 'mongodb+srv://' in mongo_uri:
            print("Using SRV connection format")
            # SRV connection strings don't use port numbers
            if ':27017' in mongo_uri:
                print("Warning: SRV connection strings should not include port numbers.")
                mongo_uri = mongo_uri.replace(':27017', '')
        
        client = MongoClient(mongo_uri)
        # Verify connection works
        client.admin.command('ping')
        print("Successfully connected to MongoDB")
        return client.flapple
    
    except Exception as e:
        print(f"Error connecting to MongoDB: {str(e)}")
        print("\nTips to fix connection issues:")
        print("1. Check if your Mongo_API environment variable is correctly set")
        print("2. Make sure your MongoDB Atlas cluster is running")
        print("3. Verify your IP address is allowlisted in MongoDB Atlas")
        print("4. If using mongodb+srv://, verify your cluster hostname is correct")
        sys.exit(1)

def initialize_emoji_collection():
    """Upload custom emoji data to MongoDB"""
    db = connect_to_mongodb()
    
    try:
        # Define emoji data - just ID and emoji (Discord emoji ID format)
        emoji_data = [
            {"_id": "pokeball", "emoji": "<:pokeball:1355407403046146161>"},
            {"_id": "greatball", "emoji": "<:greatball:1355407398961021150>"},
            {"_id": "ultraball", "emoji": "<:ultraball:1355407404975656970>"},
            {"_id": "masterball", "emoji": "<:masterball:1355407400978354186>"}
        ]
        
        # Clear existing emoji data first
        db.emojis.delete_many({})
        
        # Insert new emoji data
        result = db.emojis.insert_many(emoji_data)
        print(f"✅ Uploaded {len(result.inserted_ids)} emoji mappings to MongoDB")
        
        return True
    except Exception as e:
        print(f"❌ Error uploading emoji data: {str(e)}")
        return False

def upload_initial_data():
    """Upload all initial data to MongoDB"""
    db = connect_to_mongodb()
    
    # Track successful operations
    successes = 0
    
    try:
        # Upload Pokemon data
        with open('./fresh_data/all_pokemon_data_v3.json', 'r') as f:
            pokemon_data = json.load(f)
        
        # Clear existing data first
        db.pokemon.delete_many({})
        result = db.pokemon.insert_many(pokemon_data)
        print(f"✅ Uploaded {len(result.inserted_ids)} Pokémon to MongoDB")
        successes += 1
    except Exception as e:
        print(f"❌ Error uploading Pokémon data: {str(e)}")
    
    try:
        # Upload Move data
        with open('./fresh_data/all_move_data.json', 'r') as f:
            move_data = json.load(f)
        
        # Clear existing data first
        db.moves.delete_many({})
        result = db.moves.insert_many(move_data)
        print(f"✅ Uploaded {len(result.inserted_ids)} moves to MongoDB")
        successes += 1
    except Exception as e:
        print(f"❌ Error uploading move data: {str(e)}")
    
    try:
        # Upload Pokeball data
        with open('./fresh_data/config.json', 'r') as f:
            pokeball_data = json.load(f)
        
        # Clear existing data first
        db.config.delete_one({"_id": "pokeballs"})
        db.config.insert_one({"_id": "pokeballs", **pokeball_data})
        print(f"✅ Uploaded configuration to MongoDB")
        successes += 1
    except Exception as e:
        print(f"❌ Error uploading pokeball data: {str(e)}")
    
    try:
        # Upload last unique ID
        with open('./fresh_data/last_unique_id.txt', 'r') as f:
            last_id = f.read().strip()
        
        # Clear existing data first
        db.unique_id.delete_one({"_id": "last_id"})
        db.unique_id.insert_one({"_id": "last_id", "value": int(last_id)})
        print(f"✅ Uploaded last unique ID ({last_id}) to MongoDB")
        successes += 1
    except Exception as e:
        print(f"❌ Error uploading last unique ID: {str(e)}")
    
    try:
        # Upload inventory data
        with open('./fresh_data/Inventory.json', 'r') as f:
            inventory_data = json.load(f)
        
        # Fixed: Correctly format user data for MongoDB
        user_docs = []
        for user_id, user_data in inventory_data["users"].items():
            user_doc = user_data.copy()
            user_doc["_id"] = user_id
            user_docs.append(user_doc)
        
        # Clear existing data first
        db.inventory.delete_many({})
        if user_docs:
            result = db.inventory.insert_many(user_docs)
            print(f"✅ Uploaded {len(result.inserted_ids)} user inventories to MongoDB")
        else:
            print("⚠️ No user inventory data to upload")
        successes += 1
    except Exception as e:
        print(f"❌ Error uploading inventory data: {str(e)}")
    
    try:
        # Upload caught Pokémon data
        with open('./fresh_data/caught_pokemon_data.json', 'r') as f:
            caught_pokemon_data = json.load(f)
        
        # Convert the JSON object into a list of documents with proper _id field
        caught_pokemon_docs = []
        for unique_id, pokemon in caught_pokemon_data.items():
            pokemon_doc = pokemon.copy()
            pokemon_doc['_id'] = unique_id
            caught_pokemon_docs.append(pokemon_doc)
        
        # Clear existing data first
        db.caught_pokemon.delete_many({})
        if caught_pokemon_docs:
            result = db.caught_pokemon.insert_many(caught_pokemon_docs)
            print(f"✅ Uploaded {len(result.inserted_ids)} caught Pokémon to MongoDB")
        else:
            print("⚠️ No caught Pokémon data to upload")
        successes += 1
    except Exception as e:
        print(f"❌ Error uploading caught Pokémon data: {str(e)}")
    
    try:
        # Initialize emoji collection
        initialize_emoji_collection()
        print(f"✅ Uploaded emoji data to MongoDB")
        successes += 1
    except Exception as e:
        print(f"❌ Error in emoji collection initialization: {str(e)}")
    
    if successes == 7:  # Updated from 6 to 7 since we added emoji operation
        print("\n🎉 Initial data upload complete successfully!")
    else:
        print(f"\n⚠️ Initial data upload partially completed ({successes}/7 operations successful)")

def backup_data():
    """Backup all MongoDB data to local JSON files"""
    db = connect_to_mongodb()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"./backups/backup_{timestamp}"
    
    try:
        # Create backup directory
        os.makedirs(backup_dir, exist_ok=True)
        print(f"Created backup directory: {backup_dir}")
    except Exception as e:
        print(f"Error creating backup directory: {str(e)}")
        return
    
    # Track successful operations
    successes = 0
    
    try:
        # Backup Pokemon data
        pokemon_data = list(db.pokemon.find({}, {'_id': 0}))
        backup_file = f"{backup_dir}/backup_pokemon_data.json"
        with open(backup_file, 'w') as f:
            json.dump(pokemon_data, f, indent=2)
        print(f"✅ Backed up {len(pokemon_data)} Pokémon to {backup_file}")
        successes += 1
    except Exception as e:
        print(f"❌ Error backing up Pokémon data: {str(e)}")
    
    try:
        # Backup Move data
        move_data = list(db.moves.find({}, {'_id': 0}))
        backup_file = f"{backup_dir}/backup_move_data.json"
        with open(backup_file, 'w') as f:
            json.dump(move_data, f, indent=2)
        print(f"✅ Backed up {len(move_data)} moves to {backup_file}")
        successes += 1
    except Exception as e:
        print(f"❌ Error backing up move data: {str(e)}")
    
    try:
        # Backup Inventory data - Fixed format to match original JSON structure
        inventory_data = list(db.inventory.find({}))
        inventory_output = {"users": {}}
        for user in inventory_data:
            user_id = user.pop("_id")
            inventory_output["users"][user_id] = user
        
        backup_file = f"{backup_dir}/backup_inventory_data.json"
        with open(backup_file, 'w') as f:
            json.dump(inventory_output, f, indent=2)
        print(f"✅ Backed up {len(inventory_data)} user inventories to {backup_file}")
        successes += 1
    except Exception as e:
        print(f"❌ Error backing up inventory data: {str(e)}")
    
    try:
        # Backup Caught Pokemon data - Fixed format to match original JSON structure
        caught_pokemon_data = list(db.caught_pokemon.find({}))
        caught_pokemon_output = {}
        for pokemon in caught_pokemon_data:
            pokemon_id = pokemon.pop("_id")
            caught_pokemon_output[pokemon_id] = pokemon
        
        backup_file = f"{backup_dir}/backup_caught_pokemon_data.json"
        with open(backup_file, 'w') as f:
            json.dump(caught_pokemon_output, f, indent=2)
        print(f"✅ Backed up {len(caught_pokemon_data)} caught Pokémon to {backup_file}")
        successes += 1
    except Exception as e:
        print(f"❌ Error backing up caught Pokémon data: {str(e)}")
    
    try:
        # Backup last unique ID
        last_id_doc = db.unique_id.find_one({"_id": "last_id"})
        if last_id_doc:
            backup_file = f"{backup_dir}/backup_last_unique_id.txt"
            with open(backup_file, 'w') as f:
                f.write(str(last_id_doc['value']))
            print(f"✅ Backed up last unique ID to {backup_file}")
            successes += 1
        else:
            print("⚠️ No last unique ID found in database")
    except Exception as e:
        print(f"❌ Error backing up last unique ID: {str(e)}")
    
    try:
        # Backup config data
        config_data = list(db.config.find({}))
        backup_file = f"{backup_dir}/backup_config_data.json"
        with open(backup_file, 'w') as f:
            json.dump(config_data, f, indent=2)
        print(f"✅ Backed up {len(config_data)} config documents to {backup_file}")
        successes += 1
    except Exception as e:
        print(f"❌ Error backing up config data: {str(e)}")
    
    try:
        # Backup emoji data
        emoji_data = list(db.emojis.find({}))
        emoji_output = {}
        
        for emoji in emoji_data:
            emoji_id = emoji.pop("_id")
            emoji_output[emoji_id] = emoji
            
        backup_file = f"{backup_dir}/backup_emoji_data.json"
        with open(backup_file, 'w') as f:
            json.dump(emoji_output, f, indent=2)
        
        print(f"✅ Backed up {len(emoji_data)} emoji mappings to {backup_file}")
        successes += 1
    except Exception as e:
        print(f"❌ Error backing up emoji data: {str(e)}")
    
    if successes == 7:  # Updated from 6 to 7 since we added emoji backup
        print(f"\n🎉 Backup completed successfully to directory: {backup_dir}")
    else:
        print(f"\n⚠️ Backup partially completed ({successes}/7 operations successful) to directory: {backup_dir}")

def main():
    """Run the backup task"""
    print("Starting database backup...")
    backup_data()
    print(f"Backup completed at {datetime.now()}")

if __name__ == "__main__":
    # Interactive menu for better usability
    print("Welcome to the Pokémon Discord Bot Database Manager")
    print("---------------------------------------------------")
    print("1. Upload initial data to MongoDB")
    print("2. Backup data from MongoDB")
    print("3. Exit")
    
    choice = input("Enter your choice (1-3): ")
    
    if choice == "1":
        upload_initial_data()
    elif choice == "2":
        backup_data()
    else:
        print("Exiting program.")