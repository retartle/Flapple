import discord
import os
import asyncio
from dotenv import load_dotenv
from discord.ext import commands

load_dotenv()

# Initialize bot
intents = discord.Intents.all()
client = commands.Bot(command_prefix=('%'), case_insensitive=True, intents=intents)

# Global tracking variables
active_catchers = set()
user_cooldowns = {}

@client.event
async def on_ready():
    """Initialize resources when bot is ready"""
    print('Flapple is online. Beginning initialization...')
    
    # Initialize session for HTTP requests
    from utils.encounter_utils import initialize_session
    await initialize_session()
    
    print('All systems initialized successfully!')

async def load_cogs():
    """Load all cogs from the cogs directory"""
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and not filename.startswith('_'):
            try:
                await client.load_extension(f'cogs.{filename[:-3]}')
                print(f'Loaded cog: {filename[:-3]}')
            except Exception as e:
                print(f'Failed to load cog {filename[:-3]}: {e}')

# Setup and run bot
async def main():
    async with client:
        await load_cogs()
        await client.start(os.getenv('API_Key'))

if __name__ == "__main__":
    asyncio.run(main())