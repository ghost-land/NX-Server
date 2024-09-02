<?php

// Extract configuration values
$expectedHauth = '___________YOUR_HAUTH___________'; //Adjust expected HAUTH header if neccessary
$jsonFilePath = 'https://nx.server.domain/index.tfl'; // Adjust the path to your TFL file if necessary
$defaultHtml = 'index.html'; //Default homepage if HAUTH is incorrect

// Get headers
$headers = getallheaders();

// Check for HAUTH header using $_SERVER superglobal
$hauth = isset($_SERVER['HTTP_HAUTH']) ? $_SERVER['HTTP_HAUTH'] : null;

// Check for HAUTH header using Apache
$hauth = isset($headers["HAUTH"]) ? $headers["HAUTH"] : null;

// Check if HAUTH is present and matches
if (empty($hauth) || $hauth !== $expectedHauth) {
    // Serve HTML if HAUTH is not present or doesn't match
    header("Location: " . $defaultHtml);
    exit();
} else {
    $response = array("directories" => ["$jsonFilePath"]);
    echo json_encode($response);
    exit();
}
?>