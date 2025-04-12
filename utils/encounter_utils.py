# utils/encounter_utils.py
import discord
import random
import io
import os
import aiohttp
import asyncio
from PIL import Image
import cv2
import numpy as np
from config import inventory_collection, db, move_collection

# Cache for sprite validation
sprite_cache = {}
session = None

async def initialize_session():
    """Initialize and return an aiohttp session"""
    global session
    if session is None:
        session = aiohttp.ClientSession()
    return session

def get_emoji(emoji_type):
    """Retrieve emoji for a given type"""
    emoji_data = db.emojis.find_one({"_id": emoji_type})
    return emoji_data["emoji"] if emoji_data else "🔍"

def initialize_wild_pool():
    """Initialize pools of Pokémon IDs by rarity"""
    pokemon_list = list(db.pokemon.find({}, {"id": 1, "rarity": 1}))
    normal_ID_list = [pokemon["id"] for pokemon in pokemon_list if pokemon.get('rarity') == "Normal"]
    mythical_ID_list = [pokemon["id"] for pokemon in pokemon_list if pokemon.get('rarity') == "Mythical"]
    legendary_ID_list = [pokemon["id"] for pokemon in pokemon_list if pokemon.get('rarity') == "Legendary"]
    return normal_ID_list, mythical_ID_list, legendary_ID_list

def choose_random_wild(normal_ID_list, mythical_ID_list, legendary_ID_list):
    """Choose a random wild Pokémon with appropriate rarity and shiny chances"""
    from utils.pokemon_utils import search_pokemon_by_id
    
    # Choose rarity with appropriate weights
    rarity_choice = random.choices(
        ["normal", "mythical", "legendary"],
        weights=[98.95, 1.0, 0.05],  # Adjusted for better balance
        k=1
    )[0]
    
    # Determine if shiny (1/4096 chance)
    shiny = random.choices(
        [True, False],
        weights=[1, 4095],
        k=1
    )[0]
    
    # Select Pokémon based on rarity
    if rarity_choice == "normal":
        chosen_id = random.choice(normal_ID_list)
    elif rarity_choice == "mythical":
        chosen_id = random.choice(mythical_ID_list)
    else:  # legendary
        chosen_id = random.choice(legendary_ID_list)
    
    # Get the full Pokémon data
    pokemon = search_pokemon_by_id(chosen_id)
    return pokemon, shiny

async def generate_encounter_image(
    sprite_url: str,
    background_folder: str = "assets/backgrounds",
    static_sprite_scale: float = 2.0,
    animated_sprite_scale: float = 3.0,
    position: str = "bottom_center",
    bg_size: tuple = (640, 360),
    is_animated_allowed: bool = False
) -> tuple[io.BytesIO, bool]:
    """Generate a composite image for encounters with Pokémon sprite on background"""
    try:
        # Get a random background
        background_files = [f for f in os.listdir(background_folder)
                          if os.path.isfile(os.path.join(background_folder, f))]
        chosen_background_path = os.path.join(background_folder, random.choice(background_files))
        
        # Fetch sprite data
        async with aiohttp.ClientSession() as session:
            async with session.get(sprite_url) as response:
                if response.status != 200:
                    return None, False
                sprite_data = await response.read()
        
        # Check if sprite is GIF and if animated processing is allowed
        sprite_image = Image.open(io.BytesIO(sprite_data))
        is_animated = sprite_image.format == "GIF" and getattr(sprite_image, "is_animated", False)
        
        # For animated GIFs, use Pillow
        if is_animated and is_animated_allowed:
            # Use higher scale factor for animated
            sprite_scale = animated_sprite_scale
            
            # Process with Pillow (existing animated GIF code)
            background = Image.open(chosen_background_path).convert("RGBA")
            background = background.resize(bg_size, Image.LANCZOS)
            bg_width, bg_height = background.size
            
            frame_count = sprite_image.n_frames
            frames = []
            durations = []
            
            # Process each frame
            for frame_idx in range(frame_count):
                sprite_image.seek(frame_idx)
                frame_duration = sprite_image.info.get('duration', 100)
                durations.append(frame_duration)
                
                frame = sprite_image.convert("RGBA")
                original_size = frame.size
                new_size = (int(original_size[0] * sprite_scale), int(original_size[1] * sprite_scale))
                frame = frame.resize(new_size, Image.LANCZOS)
                
                # Calculate position
                spr_width, spr_height = frame.size
                if position == "center":
                    paste_x = (bg_width - spr_width) // 2
                    paste_y = (bg_height - spr_height) // 2
                elif position == "bottom_center":
                    paste_x = (bg_width - spr_width) // 2
                    paste_y = bg_height - spr_height - (bg_height // 10)
                else:
                    # Default to bottom center
                    paste_x = (bg_width - spr_width) // 2
                    paste_y = bg_height - spr_height - (bg_height // 10)
                
                new_frame = background.copy()
                new_frame.paste(frame, (paste_x, paste_y), frame)
                frames.append(new_frame)
            
            # Save as animated GIF
            final_buffer = io.BytesIO()
            frames[0].save(
                final_buffer,
                format="GIF",
                save_all=True,
                append_images=frames[1:],
                optimize=True,
                duration=durations,
                loop=0,
                disposal=2
            )
            final_buffer.seek(0)
            return final_buffer, True
        
        else:
            # Use OpenCV for static images with smaller scale factor
            sprite_scale = static_sprite_scale
            
            # Convert sprite to numpy array for OpenCV
            if is_animated:
                # Using first frame of GIF
                sprite_image.seek(0)
                sprite_pil = sprite_image.convert("RGBA")
                sprite_array = np.array(sprite_pil)
                # Convert RGBA to BGRA (OpenCV uses BGR ordering)
                sprite_array = cv2.cvtColor(sprite_array, cv2.COLOR_RGBA2BGRA)
            else:
                # For static images, decode directly with OpenCV
                sprite_bytes = np.frombuffer(sprite_data, np.uint8)
                sprite_array = cv2.imdecode(sprite_bytes, cv2.IMREAD_UNCHANGED)
                
                # Add alpha channel if missing
                if sprite_array.shape[2] == 3:
                    sprite_array = cv2.cvtColor(sprite_array, cv2.COLOR_BGR2BGRA)
            
            # Read background with OpenCV (much faster than PIL)
            bg = cv2.imread(chosen_background_path)
            bg = cv2.resize(bg, bg_size)
            bg_height, bg_width = bg.shape[:2]
            
            # Resize sprite
            h, w = sprite_array.shape[:2]
            sprite_array = cv2.resize(sprite_array, (int(w * sprite_scale), int(h * sprite_scale)))
            
            # Calculate position
            spr_height, spr_width = sprite_array.shape[:2]
            if position == "center":
                paste_x = (bg_width - spr_width) // 2
                paste_y = (bg_height - spr_height) // 2
            elif position == "bottom_center":
                paste_x = (bg_width - spr_width) // 2
                paste_y = bg_height - spr_height - (bg_height // 10)
            else:
                paste_x = (bg_width - spr_width) // 2
                paste_y = bg_height - spr_height - (bg_height // 10)
            
            # Convert background to BGRA if needed
            if bg.shape[2] == 3:
                bg = cv2.cvtColor(bg, cv2.COLOR_BGR2BGRA)
            
            # Create ROI and handle edge cases
            roi_y_start = max(0, paste_y)
            roi_y_end = min(bg_height, paste_y + spr_height)
            roi_x_start = max(0, paste_x)
            roi_x_end = min(bg_width, paste_x + spr_width)
            
            # Adjust sprite selection if paste position is negative
            sprite_y_start = abs(min(0, paste_y))
            sprite_x_start = abs(min(0, paste_x))
            sprite_y_end = sprite_y_start + (roi_y_end - roi_y_start)
            sprite_x_end = sprite_x_start + (roi_x_end - roi_x_start)
            
            # Alpha blending (much faster than PIL paste)
            roi = bg[roi_y_start:roi_y_end, roi_x_start:roi_x_end]
            sprite_part = sprite_array[sprite_y_start:sprite_y_end, sprite_x_start:sprite_x_end]
            
            # Apply alpha blending
            alpha = sprite_part[:, :, 3] / 255.0
            for c in range(0, 3):
                roi[:, :, c] = sprite_part[:, :, c] * alpha + roi[:, :, c] * (1 - alpha)
            
            # Encode to PNG
            final_buffer = io.BytesIO()
            _, encoded_img = cv2.imencode('.png', bg, [cv2.IMWRITE_PNG_COMPRESSION, 6])
            final_buffer.write(encoded_img)
            final_buffer.seek(0)
            return final_buffer, False
    
    except Exception as e:
        print(f"Error generating encounter image: {e}")
        return None, False

class PokemonEncounterView(discord.ui.View):
    """Interactive view for Pokémon encounters and catching"""
    def __init__(self, ctx, name, pokeballs, greatballs, ultraballs, masterballs,
                 base_catch_rate, ball_data, SHembed_editor, earnings, flee_chance):
        super().__init__(timeout=60)  # 60 second timeout
        self.ctx = ctx
        self.name = name
        self.pokeballs = pokeballs
        self.greatballs = greatballs
        self.ultraballs = ultraballs
        self.masterballs = masterballs
        self.base_catch_rate = base_catch_rate
        self.ball_data = ball_data
        self.SHembed_editor = SHembed_editor
        self.earnings = earnings
        self.flee_chance = flee_chance
        self.code = 0
        self.catch_result = None
        self.catch = None
        self.rate = None
        self.is_using_attachment = False
        self.original_sprite_url = None
        self.emojis = {
            "pokeball": get_emoji("pokeball"),
            "greatball": get_emoji("greatball"),
            "ultraball": get_emoji("ultraball"),
            "masterball": get_emoji("masterball")
        }
        
        # Add buttons dynamically based on inventory
        self._setup_buttons()
    
    def _setup_buttons(self):
        """Add ball buttons based on what's in inventory"""
        ball_types = [
            ("pokeball", self.pokeballs, self.pokeball_callback),
            ("greatball", self.greatballs, self.greatball_callback),
            ("ultraball", self.ultraballs, self.ultraball_callback),
            ("masterball", self.masterballs, self.masterball_callback)
        ]
        
        for ball_type, count, callback in ball_types:
            if count > 0:
                button = discord.ui.Button(
                    style=discord.ButtonStyle.secondary,
                    custom_id=ball_type,
                    emoji=self.emojis[ball_type]
                )
                button.callback = callback
                self.add_item(button)
        
        # Add run button
        run_button = discord.ui.Button(
            style=discord.ButtonStyle.danger,
            label="Run",
            custom_id="run"
        )
        run_button.callback = self.run_callback
        self.add_item(run_button)
    
    async def _update_embed(self, title=None, update_footer=False):
        embed = self.SHembed_editor.embeds[0]
        if title is not None:
            embed.title = title
        if update_footer:
            footer_text = self._get_footer_text()
            embed.set_footer(text=footer_text)
        
        # Clear attachments to avoid duplicates
        await self.SHembed_editor.edit(embed=embed, attachments=[])
    
    def _get_footer_text(self):
        """Generate consistent footer text"""
        ball_counts = []
        if self.pokeballs > 0:
            ball_counts.append(f"Pokeball: {self.pokeballs}")
        if self.greatballs > 0:
            ball_counts.append(f"Greatball: {self.greatballs}")
        if self.ultraballs > 0:
            ball_counts.append(f"Ultraball: {self.ultraballs}")
        if self.masterballs > 0:
            ball_counts.append(f"Masterball: {self.masterballs}")
        return f"{self.ctx.author.name}'s Battle | " + " | ".join(ball_counts)
    
    async def pokeball_callback(self, interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your Pokémon battle!", ephemeral=True)
            return
        
        self.pokeballs -= 1
        await self._process_catch_attempt(interaction, self.ball_data["Pokeball"], "Pokeball")
    
    async def greatball_callback(self, interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your Pokémon battle!", ephemeral=True)
            return
        
        self.greatballs -= 1
        await self._process_catch_attempt(interaction, self.ball_data["Greatball"], "Greatball")
    
    async def ultraball_callback(self, interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your Pokémon battle!", ephemeral=True)
            return
        
        self.ultraballs -= 1
        await self._process_catch_attempt(interaction, self.ball_data["Ultraball"], "Ultraball")
    
    async def masterball_callback(self, interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your Pokémon battle!", ephemeral=True)
            return
        
        self.masterballs -= 1
        await self._process_catch_attempt(interaction, self.ball_data["Masterball"], "Masterball")
    
    async def run_callback(self, interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your Pokémon battle!", ephemeral=True)
            return
        
        # Disable all buttons
        for item in self.children:
            item.disabled = True
        
        # Update title and view in ONE operation
        await self._update_embed(title=f"Got away from {self.name} safely.")
        
        # Ensure the view is updated with disabled buttons
        await interaction.response.edit_message(embed=self.SHembed_editor.embeds[0], view=self)
        
        self.code = 1
        self.catch_result = "ran"
        self.stop()
    
    async def _process_catch_attempt(self, interaction, ball_multiplier, ball_name):
        """Process a catch attempt with the given ball multiplier"""
        try:
            print(f"Processing catch with {ball_name}, multiplier: {ball_multiplier}")
            
            # Update inventory in MongoDB
            from utils.db_utils import update_user_data
            
            await update_user_data(
                str(self.ctx.author.id),
                {"$set": {
                    "Pokeballs": self.pokeballs,
                    "Greatballs": self.greatballs,
                    "Ultraballs": self.ultraballs,
                    "Masterballs": self.masterballs
                }}
            )
            
            # Calculate catch chance
            modified_catch_rate = self.base_catch_rate * ball_multiplier
            catch = random.randint(0, 255)
            
            # Clear the view and recreate the buttons with updated counts
            self.clear_items()
            self._setup_buttons()
            
            # Handle catch outcome and update embed in a single operation
            if catch <= modified_catch_rate:
                # Successful catch
                self.catch_result = True
                
                # Award Pokedollars
                await update_user_data(
                    str(self.ctx.author.id),
                    {"$inc": {"Pokedollars": self.earnings}}
                )
                
                # Update both title and footer in one operation
                await self._update_embed(
                    title=f"{self.name} was caught! You earned {self.earnings} Pokedollars",
                    update_footer=True
                )
                
                # Disable all buttons after successful catch
                for item in self.children:
                    item.disabled = True
                
                self.code = 1
                self.catch = catch
                self.rate = modified_catch_rate
                
                await interaction.response.edit_message(view=self)
                self.stop()
                
            elif random.randint(1, 100) <= self.flee_chance:
                # Pokémon fled
                await self._update_embed(
                    title=f"{self.name} fled!",
                    update_footer=True
                )
                
                # Disable all buttons after the Pokémon flees
                for item in self.children:
                    item.disabled = True
                
                self.catch_result = "ran"
                self.code = 1
                self.catch = catch
                self.rate = modified_catch_rate
                
                await interaction.response.edit_message(view=self)
                self.stop()
                
            else:
                # Failed catch, but Pokémon didn't flee
                random_retry_msg = random.choice([
                    f"Argh so close! {self.name} broke free!",
                    f"Not even close! {self.name} broke free!"
                ])
                
                await self._update_embed(
                    title=random_retry_msg,
                    update_footer=True
                )
                
                self.catch = catch
                self.rate = modified_catch_rate
                
                await interaction.response.edit_message(view=self)
        except Exception as e:
            # Log the error and respond to avoid interaction timeout
            print(f"Error in catch attempt: {str(e)}")
            try:
                await interaction.response.send_message(
                    f"An error occurred while using {ball_name}. Please try again.", 
                    ephemeral=True
                )
            except discord.errors.InteractionResponded:
                # If already responded, edit the original message
                try:
                    await self._update_embed(
                        title=f"Error using {ball_name}. Please try again.",
                        update_footer=True
                    )
                    await interaction.edit_original_response(view=self)
                except:
                    pass
    
    async def on_timeout(self):
        """Handle timeout (user didn't interact within the timeout period)"""
        for item in self.children:
            item.disabled = True
        
        try:
            embed = self.SHembed_editor.embeds[0]
            embed.title = f"{self.name} fled!"
            await self.SHembed_editor.edit(embed=embed, view=self)
        except Exception as e:
            print(f"Error in timeout handler: {e}")
        
        self.catch_result = "timeout"
        self.stop()