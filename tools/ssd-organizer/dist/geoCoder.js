"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.calculateHaversineDistance = calculateHaversineDistance;
exports.reverseGeocode = reverseGeocode;
exports.sanitizeFolderName = sanitizeFolderName;
const citiesData_js_1 = require("./citiesData.js");
// Cache to prevent recalculating distances for photos taken in the same area
const geoCache = new Map();
/**
 * Calculates Great-Circle distance between two coordinates in kilometers using Haversine formula
 */
function calculateHaversineDistance(lat1, lon1, lat2, lon2) {
    const R = 6371; // Earth's radius in kilometers
    const dLat = ((lat2 - lat1) * Math.PI) / 180;
    const dLon = ((lon2 - lon1) * Math.PI) / 180;
    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos((lat1 * Math.PI) / 180) *
            Math.cos((lat2 * Math.PI) / 180) *
            Math.sin(dLon / 2) *
            Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
}
/**
 * Offline reverse geocoder: finds the nearest city and country for given coordinates
 */
function reverseGeocode(latitude, longitude) {
    if (typeof latitude !== 'number' || typeof longitude !== 'number') {
        return null;
    }
    if (isNaN(latitude) || isNaN(longitude)) {
        return null;
    }
    // Cache key rounded to 2 decimals (~1.1 km area)
    const cacheKey = `${latitude.toFixed(2)},${longitude.toFixed(2)}`;
    if (geoCache.has(cacheKey)) {
        return geoCache.get(cacheKey) || null;
    }
    let closestCity = null;
    let minDistance = Infinity;
    for (const city of citiesData_js_1.CITIES_DATA) {
        const dist = calculateHaversineDistance(latitude, longitude, city.lat, city.lng);
        if (dist < minDistance) {
            minDistance = dist;
            closestCity = {
                city: city.name,
                region: city.region,
                country: city.country,
                distanceKm: Math.round(dist)
            };
        }
    }
    // If closest city is within reasonable distance (e.g. 150 km)
    if (closestCity && minDistance <= 150) {
        geoCache.set(cacheKey, closestCity);
        return closestCity;
    }
    // If further away (e.g. remote national park), still return the closest region/country
    if (closestCity) {
        const regionalLocation = {
            city: closestCity.city,
            region: closestCity.region,
            country: closestCity.country,
            distanceKm: Math.round(minDistance)
        };
        geoCache.set(cacheKey, regionalLocation);
        return regionalLocation;
    }
    geoCache.set(cacheKey, null);
    return null;
}
/**
 * Sanitizes a string for safe use in folder names across Mac, Windows, and Linux
 */
function sanitizeFolderName(name) {
    return name
        .replace(/[<>:"/\\|?*\x00-\x1F]/g, '')
        .replace(/\s+/g, '_')
        .trim();
}
