#!/bin/bash

# Run the Python scripts
python3 Updateindex.py
python3 encrypt.py --zstd -k public.key -i index.json -o index.tfl

# Remove the games.json file
rm index.json

# Remove the existing games.tfl file
rm /var/www/public/index.tfl

# Move the new games.tfl file to the target directory
mv index.tfl /var/www/public/index.tfl