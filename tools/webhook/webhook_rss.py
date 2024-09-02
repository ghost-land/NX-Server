import asyncio
import aiohttp
import xml.etree.ElementTree as ET
import os
import re
import logging
import json
from bs4 import BeautifulSoup

# Configure the logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# File paths
config_file = './config.txt'
sent_items_file = './sent_items.txt'

# Constants
max_items_to_send = 1000
max_embeds_per_request = 10
initial_wait_time = 1
max_wait_time = 60

GREEN_COLOR = 0x00FF00  # Green color for availability

async def fetch_rss_feed(session, url):
    """Fetch RSS feed content from a given URL."""
    logging.info(f"Fetching RSS feed from {url}")
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.text()
    except aiohttp.ClientError as e:
        logging.error(f"Failed to fetch RSS feed from {url}: {e}")
        return None

def parse_rss_feed(rss_content):
    """Parse RSS feed content and return a list of items."""
    items = []
    try:
        root = ET.fromstring(rss_content)
        for item in root.findall('.//item')[-max_items_to_send:]:
            title = item.find('title').text if item.find('title') is not None else 'Unknown Title'
            pub_date = item.find('pubDate').text if item.find('pubDate') is not None else 'Unknown Date'
            link = item.find('link').text if item.find('link') is not None else None
            
            # Extract and clean content from <content:encoded> or <description>
            content_encoded = item.find('{http://purl.org/rss/1.0/modules/content/}encoded')
            description = item.find('description').text if item.find('description') is not None else ''
            
            if content_encoded is not None:
                content_encoded_text = BeautifulSoup(content_encoded.text, 'html.parser').get_text()
                description = content_encoded_text.strip()
            else:
                description = BeautifulSoup(description, 'html.parser').get_text().strip()
            
            if not description:
                description = "No description available."
            
            # Extract other fields from the description text or encoded content
            title_id_match = re.search(r"Title ID:\s*([0-9A-Z]+)", description)
            size_match = re.search(r"Size:\s*([\d\.]+\s\w+)", description)
            version_match = re.search(r"Version:\s*v?([\d]+)", description)
            type_match = re.search(r"Type:\s*([\w\s\[\]]+)", description)
            format_match = re.search(r"Format:\s*([\w]+)", description)

            items.append({
                'title': title,
                'pubDate': pub_date,
                'content': description,
                'link': link,
                'title_id': title_id_match.group(1) if title_id_match else 'N/A',
                'size': size_match.group(1) if size_match else 'N/A',
                'version': version_match.group(1) if version_match else 'N/A',
                'type': type_match.group(1) if type_match else 'N/A',
                'format': format_match.group(1) if format_match else 'N/A'
            })
    except ET.ParseError as e:
        logging.error(f"Failed to parse RSS feed: {e}")
    
    return items

def load_sent_items(file_path):
    """Load sent items from a file."""
    sent_items = set()
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                sent_items = {line.strip() for line in file}
        except Exception as e:
            logging.error(f"Failed to load sent items from {file_path}: {e}")
    logging.info(f"Loaded {len(sent_items)} sent items from {file_path}")
    return sent_items

def save_sent_items(file_path, sent_items):
    """Save sent items to a file."""
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            for item in sent_items:
                file.write(f"{item}\n")
        logging.info(f"Saved {len(sent_items)} sent items to {file_path}")
    except Exception as e:
        logging.error(f"Failed to save sent items to {file_path}: {e}")

def create_embed(item):
    """Create a single embed dictionary from an item."""
    
    # Properly formatted description with line breaks
    description = (f"Title: {item['title']}\n"
                   f"Title ID: {item['title_id']}\n"
                   f"Size: {item['size']}\n"
                   f"Version: {item['version']}\n"
                   f"Type: {item['type']}\n"
                   f"Format: {item['format']}\n")

    # Determine the type of content (Update, DLC, Base)
    if "Update" in item['title']:
        title_prefix = "🟢 Update Available"
        color = 7506394  # Green color for updates
    elif "DLC" in item['title']:
        title_prefix = "🟢 New DLC Available"
        color = 7506394  # Green color for DLCs
    else:
        title_prefix = "🟢 New Game Available"
        color = 7506394  # Green color for base games

    # Enhanced formatting for the embed
    embed = {
        "title": f"{title_prefix}: {item['title']}",
        "description": description,
        "color": color,
        "footer": {
            "text": f"Published on: {item['pubDate']}"
        }
    }

    # Add a thumbnail if the link is valid
    if item['link']:
        embed["thumbnail"] = {"url": item['link']}
    
    return embed

async def send_to_guilded(session, webhook_url, items, sent_items):
    """Send items to Guilded webhook and manage rate limits."""
    new_sent_items = sent_items.copy()
    sent_count = 0
    wait_time = initial_wait_time

    masked_webhook_url = f"{webhook_url[:30]}...{webhook_url[-10:]}"
    logging.info(f"Sending data to webhook: {masked_webhook_url}")

    for i in range(0, len(items), max_embeds_per_request):
        batch = items[i:i + max_embeds_per_request]
        embeds = [create_embed(item) for item in batch if item['title'] not in sent_items]

        if not embeds:
            continue

        data = {"embeds": embeds}

        while True:
            try:
                async with session.post(webhook_url, json=data) as response:
                    if response.status == 200:
                        logging.info(f"Successfully sent batch to Guilded.")
                        new_sent_items.update(item['title'] for item in batch)
                        sent_count += len(batch)
                        wait_time = initial_wait_time
                        break
                    elif response.status == 429:
                        logging.error(f"Rate limit exceeded. Status code: 429. Waiting for {wait_time} seconds.")
                        await asyncio.sleep(wait_time)
                        wait_time = min(wait_time * 2, max_wait_time)
                    elif response.status == 400:
                        logging.error(f"Failed to send data to Guilded. Status code: 400. Payload: {json.dumps(data)}")
                        break
                    else:
                        logging.error(f"Failed to send data to Guilded. Status code: {response.status}")
                        break
            except aiohttp.ClientError as e:
                logging.error(f"Error sending data to webhook {masked_webhook_url}: {e}")
                await asyncio.sleep(wait_time)
                wait_time = min(wait_time * 2, max_wait_time)
    
    return new_sent_items

def load_config(file_path):
    """Load RSS-Webhook pairs from the config file."""
    config_pairs = []
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                for line in file:
                    try:
                        rss_url, webhook_url = line.strip().split(';')
                        config_pairs.append((rss_url, webhook_url))
                    except ValueError:
                        logging.error(f"Invalid line in config file: {line}")
        except Exception as e:
            logging.error(f"Failed to load config file {file_path}: {e}")
    logging.info(f"Loaded {len(config_pairs)} config pairs from {file_path}")
    return config_pairs

async def process_rss_feed(rss_url, webhook_url, sent_items):
    """Process RSS feed and send new items to Guilded."""
    async with aiohttp.ClientSession() as session:
        rss_content = await fetch_rss_feed(session, rss_url)
        if rss_content:
            items = parse_rss_feed(rss_content)
            new_sent_items = await send_to_guilded(session, webhook_url, items, sent_items)
            return new_sent_items
        else:
            logging.error(f"Skipping processing for {rss_url} due to failed fetch.")
            return sent_items

async def main():
    """Main function to load configuration, process RSS feeds, and send data."""
    config_pairs = load_config(config_file)
    sent_items = load_sent_items(sent_items_file)

    tasks = [
        process_rss_feed(rss_url, webhook_url, sent_items)
        for rss_url, webhook_url in config_pairs
    ]
    
    results = await asyncio.gather(*tasks)
    
    for new_sent_items in results:
        sent_items.update(new_sent_items)
    
    save_sent_items(sent_items_file, sent_items)

if __name__ == "__main__":
    asyncio.run(main())
