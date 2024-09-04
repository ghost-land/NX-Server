#!/bin/bash

# Run the Python scripts
python3 Updateindex.py
python3 encrypt.py --zstd -k public.key -i index.json -o index.tfl

# Remove the games.json file
rm "index.json"

# Remove the existing games.tfl file
tlf_path="/var/www/public/index.tfl"
if [ -e "$tlf_path" ]; then
    rm "$tlf_path"
fi

# Move the new games.tfl file to the target directory
mv -f "index.tfl" "$tlf_path"