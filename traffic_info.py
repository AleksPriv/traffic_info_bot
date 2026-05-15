import os
import requests
import polyline
from dotenv import load_dotenv

load_dotenv()

# Config
GOOGLE_KEY = os.getenv("GOOGLE_MAPS_KEY")
TG_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HOME = os.getenv("HOME_ADDRESS")
WORK = os.getenv("WORK_ADDRESS")

def get_traffic_color(speed):
    """Maps Google speed categories to hex colors for the map."""
    colors = {
        "NORMAL": "0x0000ffff",      # Blue
        "SLOW": "0xffa500ff",        # Orange
        "TRAFFIC_JAM": "0xff0000ff"  # Red
    }
    return colors.get(speed, "0x0000ffff") # Default to Blue

def get_multi_segment_route():
    # 1. Request from the modern Routes API
    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_KEY,
        "X-Goog-FieldMask": "routes.duration,routes.staticDuration,routes.distanceMeters,routes.polyline,routes.travelAdvisory.speedReadingIntervals"
    }
    
    payload = {
        "origin": {"address": HOME},
        "destination": {"address": WORK},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
        "extraComputations": ["TRAFFIC_ON_POLYLINE"]
    }

    response = requests.post(url, json=payload, headers=headers).json()
    
    if not response.get('routes'):
        return "Error: No route found.", None

    route = response['routes'][0]
    full_polyline = route['polyline']['encodedPolyline']
    intervals = route.get('travelAdvisory', {}).get('speedReadingIntervals', [])
    
    # 2. Decode the polyline into coordinates
    all_points = polyline.decode(full_polyline)
    
    # 3. Build multiple 'path' parameters for Static Maps
    static_map_url = (
        f"https://maps.googleapis.com/maps/api/staticmap?"
        f"size=600x400&scale=2&maptype=roadmap&"
        f"markers=color:red|label:A|{HOME}&"
        f"markers=color:green|label:B|{WORK}&"
        f"key={GOOGLE_KEY}"
    )

    # Add each traffic segment as a separate colored path
    for interval in intervals:
        start = interval.get('startPolylinePointIndex', 0)
        end = interval.get('endPolylinePointIndex', len(all_points))
        segment_points = all_points[start:end+1]
        
        if segment_points:
            color = get_traffic_color(interval.get('speed', 'NORMAL'))
            enc_segment = polyline.encode(segment_points)
            static_map_url += f"&path=color:{color}|weight:5|enc:{enc_segment}"

    duration = int(int(route['duration'][:-1]) / 60)
    static_duration = int(int(route['staticDuration'][:-1]) / 60)
    caption = f"🚗 **Commute Update:**\nEst. Time: **{duration} mins**\nNormal Time: **{static_duration} mins**"
    
    return caption, static_map_url

def send_telegram(caption, image_url):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
    requests.post(url, data={"chat_id": CHAT_ID, "photo": image_url, "caption": caption, "parse_mode": "Markdown"})

if __name__ == "__main__":
    text, map_img = get_multi_segment_route()
    send_telegram(text, map_img)