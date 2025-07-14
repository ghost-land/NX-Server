import os
import json

# Path to the JSON file
json_file = "games.json"
roms_directory = "Z:/forwarders"

# Load the JSON file
with open(json_file, 'r', encoding='utf-8') as file:
    data = json.load(file)

# Iterate through folders in the ROMs directory
for folder in os.listdir(roms_directory):
    folder_path = os.path.join(roms_directory, folder)
    
    if os.path.isdir(folder_path) and folder in data:
        # Existing list of games
        games_list = data[folder].get("games", [])
        
        # Iterate through files in the folder
        for game_file in os.listdir(folder_path):
            game_name = os.path.splitext(game_file)[0]
            
            # Add the game if it's not already in the list
            if game_name not in games_list:
                games_list.append(game_name)
        
        # Sort the list for readability and update the JSON
        data[folder]["games"] = sorted(games_list)

# Save the updated JSON file
with open(json_file, 'w', encoding='utf-8') as file:
    json.dump(data, file, indent=4, ensure_ascii=False)

print("JSON file successfully updated.")
