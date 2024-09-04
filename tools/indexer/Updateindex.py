#!/usr/bin/env python3
# MobCat-2021

import os  # Import lib for file handling. In our case reading and writing files.
import socket  # Import web sockets lib for getting the system IP.
import json  # Import JSON lib for handling JSON data.
import requests  # Import requests lib for fetching remote JSON.
from datetime import datetime

# Variables for getting and setting local IP
hostname = socket.gethostname()
local_ip = socket.gethostbyname(hostname)
urlHead = 'http://' + local_ip + '/'

# Filter for only switch file extensions
ext = (".nsp", ".nsz", ".xci", ".xcz")

# Variables for counting files and size
fileCount = 0
sizeCount = 0

# Splash screen / header logo.
print("""
            +:            :+           
          +****:        :****+         
        +********:    :********+       
        *********:    :*********       
    :#+   *****:  :**:  :*****   +#:   
  :#####+   *:  :******:  :*   +#####: 
:#########+   :**********:   +#########
 *#######=-     +******+     -=#######*
   *###=- -=##*   +**+   *##=- -=###*  
     +- -=######*      *######=- -+    
       +##########-  -##########+      
         *######:  **  :######*        
           *##:  *####*  :##*          
               *########*              
               +########+              
                 +####+                
                   ++                  
      Tinfoil local server updater
""")

print("\nUpdating index.json for server...")

index_data = {
    "files": [],
    "headers": ["1111111111111111: 2222222222222222"],
    "directories": ["https://nx-saves.ghostland.at/"],
    "success": ""
}

# List all files in the files folder
# Saves our URL directory list and how big the file is in our index file
paths = ["/var/www/public/"]
for path in paths:
    for root, dirs, files in os.walk(path):
        for file in files:
            if file.endswith(ext):
                fileDir = os.path.join(root, file)
                fileSizeBytes = os.stat(fileDir).st_size
                filter1 = fileDir.replace(" ", "%20")  # Making the directory string HTML friendly
                filter2 = filter1.replace("\\", "/")
                filter3 = filter2.replace(path, "https://nx.server.domain/")
                index_data["files"].append({
                    "url": filter3,
                    "size": fileSizeBytes
                })
                fileCount += 1
                sizeCount += fileSizeBytes

sizeCountGB = sizeCount / 1073741824
sizeCountGB = round(sizeCountGB, 2)  # Otherwise it shows the value to the 9th decimal place

# Pop up message of the day
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
index_data["success"] = (
    f"Welcome to NX Server!!\n"
    f"This server has {fileCount} files totaling {sizeCountGB} GB\n"
    f"Last Updated: {timestamp}"
)

# Add titledb data from remote JSON
try:
    response = requests.get("https://raw.githubusercontent.com/ghost-land/NX-DB/main/fulldb.json")
    response.raise_for_status()  # Raise an error for bad responses (4xx or 5xx)
    remote_content = response.json()  # Assuming fulldb.json is a JSON file

    index_data["titledb"] = {}
    for game_id, game_data in remote_content["titledb"].items():
        game_entry = {}

        # Check and add each field if it exists
        if "id" in game_data:
            game_entry["id"] = game_data["id"]
        if "name" in game_data:
            game_entry["name"] = game_data["name"]
        if "releaseDate" in game_data:
            game_entry["releaseDate"] = game_data["releaseDate"]
        if "version" in game_data:
            game_entry["version"] = game_data["version"]
        if "description" in game_data and game_data["description"] is not None:
            game_entry["description"] = game_data["description"].replace("\n", " ")
        else:
            game_entry["description"] = ""
        if "publisher" in game_data:
            game_entry["publisher"] = game_data["publisher"]
        if "region" in game_data:
            game_entry["region"] = game_data["region"]
        if "size" in game_data:
            game_entry["size"] = game_data["size"]

        index_data["titledb"][game_id] = game_entry

except requests.exceptions.RequestException as e:
    print(f"Failed to fetch remote content: {e}")

# Write JSON data to index.json
with open("index.json", "w", encoding='utf-8') as txt:
    json.dump(index_data, txt, indent=4)

# Script completion message
print(f"Done!\n{fileCount} files totaling {sizeCountGB} GB were updated or added\n")
print(f"Server IP was set to: {local_ip}\n")
