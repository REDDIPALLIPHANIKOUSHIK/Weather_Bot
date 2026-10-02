/**
 * Reverse geocodes coordinates to a clean human-readable city/region name.
 * Uses Google Maps API if NEXT_PUBLIC_GOOGLE_MAPS_API_KEY is available,
 * otherwise falls back to free high-accuracy client-side reverse geocoding.
 */
export async function reverseGeocodeCoordinates(
  lat: number,
  lon: number
): Promise<string> {
  // 1. Google Maps Geocoding API if configured
  const gmapsKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
  if (gmapsKey) {
    try {
      const res = await fetch(
        `https://maps.googleapis.com/maps/api/geocode/json?latlng=${lat},${lon}&key=${gmapsKey}`
      );
      if (res.ok) {
        const data = await res.json();
        if (data.results && data.results.length > 0) {
          // Look for locality or administrative area
          return data.results[0].formatted_address;
        }
      }
    } catch (err) {
      console.warn("Google Maps reverse geocoding error, falling back:", err);
    }
  }

  // 2. High-accuracy locality reverse geocoding (free, zero API key required)
  try {
    const res = await fetch(
      `https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${lat}&longitude=${lon}&localityLanguage=en`
    );
    if (res.ok) {
      const data = await res.json();
      const locality = data.locality || data.city;
      const admin = data.principalSubdivision;
      const country = data.countryName;
      const parts = [locality, admin, country].filter(Boolean);
      if (parts.length > 0) {
        return parts.join(", ");
      }
    }
  } catch (err) {
    console.warn("Client reverse geocoding error:", err);
  }

  // 3. OpenStreetMap Nominatim fallback
  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`
    );
    if (res.ok) {
      const data = await res.json();
      if (data.display_name) {
        const parts = data.display_name.split(",").slice(0, 3).map((s: string) => s.trim());
        return parts.join(", ");
      }
    }
  } catch {}

  return "Your current location";
}
