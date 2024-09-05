#!/bin/bash

# Run the Python scripts
python3 Updateindex.py
python3 encrypt.py --zstd -k public.key -i index.json -o index.tfl

# Remove the games.json file
rm "index.json"

# Define the paths
tlf_path="/var/www/public/index.tfl"
new_tlf_path="index.tfl"

# Check if the new file was created successfully
if [ -e "$new_tlf_path" ]; then
    # Move the existing file to a temporary backup location first
    if [ -e "$tlf_path" ]; then
        mv "$tlf_path" "${tlf_path}.bak"
    fi

    # Move the new file to the target directory
    mv "$new_tlf_path" "$tlf_path"

    # Remove the backup if the new file was moved successfully
    if [ $? -eq 0 ]; then
        rm -f "${tlf_path}.bak"
    fi
else
    echo "New index.tfl file not found, operation aborted."
fi