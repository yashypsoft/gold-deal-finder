<?php

// ---------------- CONFIG ----------------
const API_URL = "https://data-asg.goldprice.org/dbXRates/INR";

const CACHE_FILE = __DIR__ . "/bullion_cache.json";
const CACHE_TTL  = 60;

const OZ_TO_GRAM = 31.1035;

const LANDED_MULTIPLIER = 1.11;

// Dealer spreads (₹ per 10g)
const RETAIL_SPREAD = 700;
const RTGS_DISCOUNT = 600;

// Jewellery premium for 22K (₹/10g)
const JEWELLERY_PREMIUM_22K = 1200;

const GST = 3;

// ---------------- CACHE ----------------
if (
    file_exists(CACHE_FILE) &&
    (time() - filemtime(CACHE_FILE) < CACHE_TTL)
) {
    header("Content-Type: application/json");
    echo file_get_contents(CACHE_FILE);
    exit;
}

// ---------------- FETCH ----------------
$ch = curl_init(API_URL);
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TIMEOUT => 10,
]);

$response = curl_exec($ch);
curl_close($ch);

$data = json_decode($response, true);
$item = $data['items'][0];

$xau = $item['xauPrice'];
$xag = $item['xagPrice'];

// ---------------- CORE ----------------

// Gold & Silver per gram
$goldPerGram = $xau / OZ_TO_GRAM;
$silverPerGram = $xag / OZ_TO_GRAM;

// Spot 10g
$spot10g = $goldPerGram * 10;

// Landed 999
$landed10g = $spot10g * LANDED_MULTIPLIER;

// 999 prices
$retail999 = $landed10g + RETAIL_SPREAD;
$rtgs999   = $landed10g - RTGS_DISCOUNT;
$gst999    = $rtgs999 * 1.03;

// ---------------- 22K CALC ----------------

// Base 22K from 999
$base22k = $landed10g * 0.9167;

// Retail 22K jewellery price
$retail22k =
    $base22k + JEWELLERY_PREMIUM_22K;

// GST on 22K
$retail22kGst =
    $retail22k * 1.03;

// ---------------- OUTPUT ----------------
$output = [
    "timestamp" => date("c"),

    "gold" => [
        "spot_10g" => round($spot10g),

        "retail_999_10g" => round($retail999),
        "rtgs_999_10g" => round($rtgs999),
        "999_with_gst_10g" => round($gst999),

        "retail_22k_10g" => round($retail22k),
        "retail_22k_with_gst_10g" => round($retail22kGst),

        "per_gram" => [
            "999" => round($goldPerGram * LANDED_MULTIPLIER),
            "22K" => round(($goldPerGram * 0.9167) * LANDED_MULTIPLIER),
        ]
    ],

    "silver" => [
        "per_gram" => round($silverPerGram),
        "per_kg" => round($silverPerGram * 1000)
    ]
];

// ---------------- SAVE CACHE ----------------
file_put_contents(
    CACHE_FILE,
    json_encode($output)
);

// ---------------- RETURN ----------------
header("Content-Type: application/json");
echo json_encode($output, JSON_PRETTY_PRINT);