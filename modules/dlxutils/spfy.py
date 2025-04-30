#Copyright @ISmartDevs
#Channel t.me/TheSmartDev
import os
import logging
import time
import requests
import aiohttp
import re
import asyncio
import aiofiles
from concurrent.futures import ThreadPoolExecutor
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from typing import Optional
from config import COMMAND_PREFIX
import urllib.parse  # Added for URL encoding

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ThreadPoolExecutor for blocking I/O operations
executor = ThreadPoolExecutor(max_workers=10)

async def sanitize_filename(title: str) -> str:
    """Sanitize file name by removing invalid characters."""
    title = re.sub(r'[<>:"/\\|?*]', '', title)
    title = title.replace(' ', '_')
    return f"{title[:50]}_{int(time.time())}"

async def download_image(url: str, output_path: str) -> Optional[str]:
    """Download image from a URL."""
    logger.info(f"Starting download of image from {url}")
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            async with aiofiles.open(output_path, 'wb') as file:
                for chunk in response.iter_content(1024):
                    await file.write(chunk)
            logger.info(f"Image downloaded successfully to {output_path}")
            return output_path
        else:
            logger.error(f"Failed to download image: HTTP status {response.status_code}")
    except Exception as e:
        logger.error(f"Failed to download image: {e}")
    return None

async def handle_spotify_request(client, message, input_text):
    # Check if input_text is a Spotify URL or a search query
    is_url = input_text and ('open.spotify.com/track/' in input_text or 'spotify.link/' in input_text)

    if not input_text:
        await client.send_message(
            chat_id=message.chat.id,
            text="**Please provide a track Spotify URL or a search query ❌**",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    status_message = await client.send_message(
        chat_id=message.chat.id,
        text="**Searching The Music**",
        parse_mode=ParseMode.MARKDOWN
    )

    try:
        async with aiohttp.ClientSession() as session:
            if is_url:
                # Handle Spotify URL
                logger.info(f"Processing Spotify URL: {input_text}")
                api_url = f"https://abirthetech.serv00.net/sp.php?url={input_text}"
                async with session.get(api_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Track API response: {data}")
                        if data["status"]:
                            await status_message.edit("**Found ☑️ Downloading...**")
                        else:
                            await status_message.edit("**Please Provide A Valid Spotify URL ❌**")
                            return
                    else:
                        await status_message.edit("**❌ Song Not Available On Spotify**")
                        return
            else:
                # Handle search query
                logger.info(f"Processing Spotify search query: {input_text}")
                encoded_query = urllib.parse.quote(input_text)
                api_url = f"https://abirthetech.serv00.net/sps.php?q={encoded_query}"
                async with session.get(api_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Search API response: {data}")
                        if data["type"] == "search" and data["data"]:
                            await status_message.edit("**Found ☑️ Downloading...**")
                            # Use the first result
                            track = data["data"][0]
                            # Fetch track details using the Spotify URL
                            track_url = track["external_urls"]["spotify"]
                            logger.info(f"Selected track: {track['name']} (URL: {track_url})")
                            track_api_url = f"https://abirthetech.serv00.net/sp.php?url={track_url}"  # Fixed API endpoint
                            async with session.get(track_api_url) as track_response:
                                if track_response.status == 200:
                                    data = await track_response.json()
                                    logger.info(f"Track API response: {data}")
                                    if not data["status"]:
                                        await status_message.edit("**Song Metadata Unavailable**")
                                        return
                                else:
                                    await status_message.edit("**❌Song Unavailable Bro Try Later**")
                                    return
                        else:
                            await status_message.edit("**Sorry No Songs Matched To Your Search!**")
                            return
                    else:
                        await status_message.edit("**❌ Sorry Bro Spotify Search API Dead**")
                        return

            # Extract track details from API response
            title = data["title"]
            artists = data["artist"]
            duration = data["duration"]
            album = data["album"]
            release_date = data["releaseDate"]
            spotify_url = data["spotify_url"]
            download_url = data["download_link"]
            cover_url = data.get("image") or data.get("cover")

            # Download cover image
            cover_path = None
            if cover_url:
                os.makedirs("temp_media", exist_ok=True)
                cover_path = f"temp_media/{await sanitize_filename(title)}.jpg"
                downloaded_path = await download_image(cover_url, cover_path)
                if downloaded_path:
                    logger.info(f"Cover image downloaded to {downloaded_path}")
                else:
                    logger.warning("Failed to download cover image")
                    cover_path = None

            # Download audio
            safe_title = await sanitize_filename(title)
            output_filename = f"temp_media/{safe_title}.mp3"
            logger.info(f"Starting download of audio file from {download_url}")
            async with session.get(download_url) as response:
                if response.status == 200:
                    async with aiofiles.open(output_filename, 'wb') as file:
                        await file.write(await response.read())
                    logger.info(f"Audio file downloaded successfully to {output_filename}")
                else:
                    await status_message.edit("**❌ Sorry Bro Spotify DL API Dead**")
                    return

            # Prepare user info for caption
            if message.from_user:
                user_full_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
                user_info = f"[{user_full_name}](tg://user?id={message.from_user.id})"
            else:
                group_name = message.chat.title or "this group"
                group_url = f"https://t.me/{message.chat.username}" if message.chat.username else "this group"
                user_info = f"[{group_name}]({group_url})"

            # Format caption without the Spotify URL text link
            audio_caption = (
                f"🌟 **Title** `{title}`\n"
                f"💥 **Artist** `{artists}`\n"
                f"✨ **Duration** `{duration}`\n"
                f"👀 **Album** `{album}`\n"
                f"🎵 **Release Date** `{release_date}`\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"**Downloaded By** {user_info}"
            )

            # Create inline button for Spotify URL
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎸 Listen On Spotify", url=spotify_url)]
            ])

            last_update_time = [0]
            start_time = time.time()

            logger.info("Starting upload of audio file to Telegram")
            await client.send_audio(
                chat_id=message.chat.id,
                audio=output_filename,
                caption=audio_caption,
                title=title,
                performer=artists,
                parse_mode=ParseMode.MARKDOWN,
                thumb=cover_path if cover_path else None,
                reply_markup=reply_markup,  # Add the inline button
                progress=progress_bar,
                progress_args=(status_message, start_time, last_update_time)
            )
            logger.info("Upload of audio file to Telegram completed")

            os.remove(output_filename)
            if cover_path:
                os.remove(cover_path)

            await status_message.delete()  # Delete the progress message after completion
    except Exception as e:
        await status_message.edit("**❌ Sorry Bro Spotify DL API Dead**")
        logger.error(f"Error processing Spotify request: {e}")

async def progress_bar(current, total, status_message, start_time, last_update_time):
    """Display a progress bar for uploads."""
    elapsed_time = time.time() - start_time
    percentage = (current / total) * 100
    progress = "▓" * int(percentage // 5) + "░" * (20 - int(percentage // 5))
    speed = current / elapsed_time / 1024 / 1024  # Speed in MB/s
    uploaded = current / 1024 / 1024  # Uploaded size in MB
    total_size = total / 1024 / 1024  # Total size in MB

    # Throttle updates: Only update if at least 2 seconds have passed since the last update
    if time.time() - last_update_time[0] < 2:
        return
    last_update_time[0] = time.time()  # Update the last update time

    text = (
        f"📥 Upload Progress 📥\n\n"
        f"{progress}\n\n"
        f"🚧 Percentage: {percentage:.2f}%\n"
        f"⚡️ Speed: {speed:.2f} MB/s\n"
        f"📶 Uploaded: {uploaded:.2f} MB of {total_size:.2f} MB"
    )
    try:
        await status_message.edit(text)
    except Exception as e:
        logger.error(f"Error updating progress: {e}")

def setup_spotify_handler(app: Client):
    # Create a regex pattern from the COMMAND_PREFIX list
    command_prefix_regex = f"[{''.join(map(re.escape, COMMAND_PREFIX))}]"

    @app.on_message(filters.regex(rf"^{command_prefix_regex}sp(\s+.*)?$") & (filters.private | filters.group))
    async def spotify_command(client, message):
        # Check if the message contains a Spotify URL or query
        command_parts = message.text.split(maxsplit=1)
        input_text = command_parts[1].strip() if len(command_parts) > 1 else None
        await handle_spotify_request(client, message, input_text)
