import os
import time
import aiohttp
import asyncio
import json
from feedgen.feed import FeedGenerator
from bs4 import BeautifulSoup
import logging

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Path of the directory to be monitored
directory_path = '/var/www/public/storage/'

# Site base URL
base_url = 'https://nx.server.domain/'

# File extensions to monitor
extensions_to_watch = {'.nsp', '.xci', '.nsz', '.xcz'}

# Cache file path
description_cache_file = 'description_cache.json'

def format_size(size_bytes):
    """Convert bytes to a human-readable string."""
    for unit in ['B', 'KiB', 'MiB', 'GiB', 'TiB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024

def get_game_info(file_name):
    """Extract game info from the file name."""
    import re
    match = re.match(r"^(.*)\s+\[(0100[0-9A-F]{12})\](?:\[(v\d+)\])?.*\.(nsp|xci|nsz|xcz)$", file_name)
    if match:
        game_name = match.group(1).strip()
        title_id = match.group(2)
        version = match.group(3) if match.group(3) else "v0"
        file_format = match.group(4).upper()
        return game_name, title_id, version, file_format
    else:
        # Parsing from the file name if it does not match the usual pattern
        base_name, ext = os.path.splitext(file_name)
        parts = base_name.split('[')
        game_name = parts[0].strip()
        title_id = None
        version = "v0"
        if len(parts) > 1:
            for part in parts[1:]:
                if 'DLC' in part.upper():
                    continue  # skip DLC text
                elif '0100' in part:
                    title_id = part.strip(']')
                elif 'v' in part:
                    version = part.strip(']')
        file_format = ext[1:].upper()
        
        # Extract full DLC name from filename if it contains additional details
        full_name = base_name.strip()
        return full_name, title_id, version, file_format

def load_description_cache():
    """Load the description cache from a file."""
    if os.path.exists(description_cache_file):
        with open(description_cache_file, 'r') as file:
            return json.load(file)
    return {}

def save_description_cache(cache):
    """Save the description cache to a file."""
    with open(description_cache_file, 'w') as file:
        json.dump(cache, file)

async def get_game_description(title_id, session, cache):
    """Get the game description from Tinfoil.io using the title ID, with caching."""
    if title_id in cache:
        logging.info(f"Description for {title_id} found in cache.")
        return cache[title_id]

    url = f"https://tinfoil.io/Title/{title_id}"
    try:
        logging.info(f"Fetching description for {title_id} from {url}.")
        async with session.get(url) as response:
            if response.status == 200:
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
                meta_description = soup.find('meta', {'property': 'og:description'})
                if meta_description and 'content' in meta_description.attrs:
                    description = meta_description['content']
                    cache[title_id] = description
                    save_description_cache(cache)
                    logging.info(f"Description for {title_id} retrieved successfully.")
                    return description
    except aiohttp.ClientError as e:
        logging.error(f"Failed to fetch description for {title_id}: {e}")
    return None

def collect_files(directory_path):
    """Collect files from directory and subdirectories."""
    files = {}
    for root, _, filenames in os.walk(directory_path):
        for filename in filenames:
            if filename.endswith(tuple(extensions_to_watch)):
                file_path = os.path.join(root, filename)
                files[file_path] = os.path.getmtime(file_path)
    return files

def determine_type(file_path):
    """Determine the type of the file based on its path."""
    relative_path = os.path.relpath(file_path, directory_path)
    parts = relative_path.split(os.sep)
    logging.info(f"Determining type for file: {relative_path}")
    if 'forwarders' in parts:
        try:
            index = parts.index('forwarders') + 1
            retro_type = parts[index]
            return f"retro > {retro_type}"
        except IndexError:
            return "retro > unknown"
    else:
        try:
            return parts[1].capitalize()  # Assuming the type is the second part of the path
        except IndexError:
            return "Unknown"

def adjust_title_id_for_icon(title_id):
    """Adjust the title ID to find the correct icon on Tinfoil."""
    if title_id.endswith('800'):
        return title_id[:-3] + '000'
    elif title_id.endswith('000'):
        return title_id
    else:
        # Decrement the fourth character from the end and set the last three to '000'
        prefix = title_id[:-4]
        third_last_char = title_id[-4]
        new_char = chr(ord(third_last_char) - 1)
        adjusted_title_id = prefix + new_char + '000'
        return adjusted_title_id

def ensure_directory_exists(path):
    """Ensure the directory for the given path exists."""
    directory = os.path.dirname(path)
    if not os.path.exists(directory):
        logging.info(f"Creating directory: {directory}")
        os.makedirs(directory)

async def fetch_icon(session, adjusted_title_id, retries=3, delay=1):
    """Attempt to fetch the icon with retries and back-off."""
    icon_url = f"https://tinfoil.media/ti/{adjusted_title_id}/256/256/"
    for attempt in range(retries):
        try:
            async with session.head(icon_url) as response:
                if response.status == 200:
                    return icon_url
        except aiohttp.ClientError as e:
            logging.error(f"Failed to fetch icon for {adjusted_title_id} (Attempt {attempt+1}): {e}")
            if attempt < retries - 1:
                await asyncio.sleep(delay)
                delay *= 2  # Exponential back-off
    return None

def extract_dlc_title(full_name):
    """Extract DLC title from the full file name."""
    import re
    # Match pattern to remove [TitleID] and [version] parts
    dlc_title = re.sub(r"\[\d{16}\]|\[v\d+\]", "", full_name).strip()
    return dlc_title

async def process_file(file_path, session, cache, feed_generator):
    """Process a file and add an entry to the given FeedGenerator."""
    logging.info(f"Processing file: {file_path}")
    size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    game_name, title_id, version, file_format = get_game_info(file_name)
    file_type = determine_type(file_path)

    # Determine the type for NSP and NSZ files
    if file_format in ['NSP', 'NSZ']:
        if title_id and title_id.endswith('000'):
            file_type = 'Base' if file_format == 'NSP' else 'Base [Compressed]'
        elif title_id and title_id.endswith('800'):
            file_type = 'Updates'
        else:
            file_type = 'DLC'
    elif file_format == 'XCI':
        file_type = 'Cartridge Dump'
    elif file_format == 'XCZ':
        file_type = 'Compressed Cartridge Dump'

    # Adjust title for updates
    if file_type == "Updates" and version:
        update_number = int(version[1:]) // 65536
        game_name = f"{game_name} [Update {update_number}]"

    # Extract proper title for DLCs
    if "DLC" in file_name.upper():
        game_name = extract_dlc_title(game_name)

    fe = feed_generator.add_entry()
    fe.title(game_name)

    if title_id:
        description = await get_game_description(title_id, session, cache)
        info = (f"Game: {game_name}<br>"
                f"Title ID: {title_id}<br>"
                f"Size: {format_size(size)}<br>"
                f"Version: {version}<br>"
                f"Type: {file_type}<br>"
                f"Format: {file_format}")
        
        fe.content(content=info, type='html')
        
        if description:
            fe.description(description)
    else:
        # Handle case where title_id is None
        info = (f"File: {file_name}<br>"
                f"Size: {format_size(size)}<br>"
                f"Type: {file_type}<br>"
                f"Format: {file_format}")
        fe.content(content=info, type='html')
        fe.description("Description not available")

    pub_date = time.strftime('%a, %d %b %Y %H:%M:%S +0000', time.gmtime(os.path.getmtime(file_path)))
    fe.pubDate(pub_date)

    # Icon URL handling - use adjusted title_id for icon lookup only if title_id is available
    if title_id:
        adjusted_title_id = adjust_title_id_for_icon(title_id)
        icon_url = await fetch_icon(session, adjusted_title_id)
        if icon_url:
            fe.link(href=icon_url)

    logging.info(f"Added entry for {file_name}")

async def generate_rss_feed(title, path, files):
    """Generate RSS feed for a given list of files."""
    fg = FeedGenerator()
    fg.title(title)
    fg.link(href=base_url)
    fg.description(f'RSS feed for {title.lower()}')
    fg.generator('python-feedgen')
    fg.lastBuildDate(time.strftime('%a, %d %b %Y %H:%M:%S +0000', time.gmtime()))

    description_cache = load_description_cache()

    async with aiohttp.ClientSession() as session:
        tasks = [process_file(file, session, description_cache, fg) for file in files]
        await asyncio.gather(*tasks)

    # Ensure the directory exists
    ensure_directory_exists(path)

    rss_file_path = path
    fg.rss_file(rss_file_path, pretty=True)
    logging.info(f"RSS feed written to {rss_file_path}.")

async def main():
    description_cache = load_description_cache()

    current_files = collect_files(directory_path)
    logging.info(f"Found {len(current_files)} files in directory and subdirectories.")

    forwarder_files = {f: mtime for f, mtime in current_files.items() if 'forwarders' in f.split(os.sep)}
    other_files = {f: mtime for f, mtime in current_files.items() if 'forwarders' not in f.split(os.sep)}

    sorted_forwarder_files = sorted(forwarder_files.keys(), key=lambda x: forwarder_files[x], reverse=True)[:250]
    sorted_other_files = sorted(other_files.keys(), key=lambda x: other_files[x], reverse=True)[:250]

    logging.info(f"Selected {len(sorted_forwarder_files)} forwarder files and {len(sorted_other_files)} other files.")

    base_files = [f for f in sorted_other_files if 'update' not in determine_type(f).lower() and 'dlc' not in determine_type(f).lower()]
    update_files = [f for f in sorted_other_files if 'update' in determine_type(f).lower()]
    dlc_files = [f for f in sorted_other_files if 'dlc' in determine_type(f).lower()]

    retro_files = sorted_forwarder_files

    # Generate all RSS feeds
    await asyncio.gather(
        generate_rss_feed('NX RSS', '/var/www/data/rss/feed.xml', sorted_other_files),
        generate_rss_feed('NX RSS - Base', '/var/www/data/rss/feed_base.xml', base_files),
        generate_rss_feed('NX RSS - Updates', '/var/www/data/rss/feed_updates.xml', update_files),
        generate_rss_feed('NX RSS - DLC', '/var/www/data/rss/feed_dlc.xml', dlc_files),
        generate_rss_feed('NX RSS - Retro', '/var/www/data/rss/feed_retro.xml', retro_files)
    )

# Run the main function
asyncio.run(main())
