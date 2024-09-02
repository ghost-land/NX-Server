<?php
// List of files to check
$files = [
    './rss/feed.xml',
    './rss/feed_base.xml',
    './rss/feed_dlc.xml',
    './rss/feed_retro.xml',
    './rss/feed_updates.xml'
];

// Array to track missing files
$missingFiles = [];

// Check for the existence of each file
foreach ($files as $file) {
    if (!file_exists($file)) {
        $missingFiles[] = $file;
    }
}

// Display the result
if (empty($missingFiles)) {
    echo "OK";
} else {
    echo "Error: Missing file(s) - " . implode(', ', $missingFiles);
}
?>
