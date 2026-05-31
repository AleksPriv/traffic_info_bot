import os
import requests
import polyline
from dotenv import load_dotenv
import json
import time
from datetime import datetime

load_dotenv()

# Config
GOOGLE_KEY = os.getenv("GOOGLE_MAPS_KEY")
TG_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HOME = os.getenv("HOME_ADDRESS")
WORK = os.getenv("WORK_ADDRESS")
STATE_FILE = os.getenv("STATE_FILE_PATH", "state.json")

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    # Default state
    return {"last_sent": 0, "last_date": "", "current_window": "", "traffic_jam": ""}

def save_state(last_sent, last_date, current_window, traffic_jam):
    with open(STATE_FILE, "w") as f:
        json.dump({
            "last_sent": last_sent, 
            "last_date": last_date, 
            "current_window": current_window,
            "traffic_jam": traffic_jam
        }, f)

def get_current_window():
    """Determines if we are in the morning or evening commute window based on the hour."""
    current_hour = datetime.now().hour
    if 6 <= current_hour <= 9:
        return "morning"
    elif 15 <= current_hour <= 19: # 3 PM to 7 PM
        return "evening"
    return "outside"

def get_traffic_color(speed):
    """Maps Google speed categories to hex colors for the map."""
    colors = {
        "NORMAL": "0x0000ffff",      # Blue
        "SLOW": "0xffa500ff",        # Orange
        "TRAFFIC_JAM": "0xff0000ff"  # Red
    }
    return colors.get(speed, "0x0000ffff") # Default to Blue

def get_multi_segment_route(origin_address, destination_address):
    # 1. Request from the modern Routes API
    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_KEY,
        "X-Goog-FieldMask": "routes.duration,routes.staticDuration,routes.distanceMeters,routes.polyline,routes.travelAdvisory.speedReadingIntervals"
    }
    
    payload = {
        "origin": {"address": origin_address},
        "destination": {"address": destination_address},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
        "extraComputations": ["TRAFFIC_ON_POLYLINE"]
    }

    response = requests.post(url, json=payload, headers=headers).json()
    traffic_jam = False

    if not response.get('routes'):
        return None, None, False, None
    
    route = response['routes'][0]
    full_polyline = route['polyline']['encodedPolyline']
    intervals = route.get('travelAdvisory', {}).get('speedReadingIntervals', [])
    
    # 2. Decode the polyline into coordinates
    all_points = polyline.decode(full_polyline)
    
    # 3. Build multiple 'path' parameters for Static Maps
    static_map_url = (
        f"https://maps.googleapis.com/maps/api/staticmap?"
        f"size=600x400&scale=2&maptype=roadmap&"
        f"markers=color:red|label:A|{origin_address}&"
        f"markers=color:green|label:B|{destination_address}&"
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

        if interval.get('speed') == "TRAFFIC_JAM":
            traffic_jam = True


    duration = int(int(route['duration'][:-1]) / 60)
    static_duration = int(int(route['staticDuration'][:-1]) / 60)
    
    
    return duration, static_duration, traffic_jam, static_map_url

def send_telegram(caption, image_url):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
    requests.post(url, data={"chat_id": CHAT_ID, "photo": image_url, "caption": caption, "parse_mode": "Markdown"})


if __name__ == "__main__":

    INFORM_THRESHOLD = 5  
    today_date = datetime.now().strftime("%Y-%m-%d")
    current_time = time.time()
    
    active_window = get_current_window()
    
    if active_window == "outside":
        print("Outside of scheduled commute windows. Exiting quietly.")
        exit()

    origin_address = os.getenv("WORK_ADDRESS") if active_window == "evening" else os.getenv("HOME_ADDRESS")
    destination_address = os.getenv("HOME_ADDRESS") if active_window == "evening" else os.getenv("WORK_ADDRESS")

    state = load_state()
    is_new_window = (state["last_date"] != today_date) or (state["current_window"] != active_window)

    # ---------------------------------------------------------
    # 1. THE GATEKEEPER: Do we need to query the API?
    # ---------------------------------------------------------
    should_query = False
    
    if active_window == "morning":
        # Morning: Only query if it's the first run OR if we are already tracking a jam
        if is_new_window or state["traffic_jam"]:
            should_query = True
    elif active_window == "evening":
        # Evening: Always keep querying because return time is non-deterministic
        should_query = True

    if not should_query:
        exit()

    # ---------------------------------------------------------
    # 2. THE FETCH: Call Google API only ONCE
    # ---------------------------------------------------------
    duration, static_duration, traffic_jam, map_img = get_multi_segment_route(origin_address, destination_address)

    if duration is None:
        print("Failed to fetch route data from Google API. Exiting.")
        exit()

    # Combine both triggers into one single "is_heavy" boolean for a cleaner state machine
    is_heavy = duration >= (static_duration + INFORM_THRESHOLD) or traffic_jam

    # ---------------------------------------------------------
    # 3. THE DECISION: Formulate the message if necessary
    # ---------------------------------------------------------
    should_send = False
    caption = ""

    if is_heavy:
        if not state["traffic_jam"]:
            # Newly detected traffic
            caption = f"⚠️ **Commute Alert - Traffic Detected:**\nEst. Time: **{duration} mins**\nNormal Time: **{static_duration} mins**"
            should_send = True
        else:
            # Ongoing traffic (Addendum)
            interval = "15" if active_window == "morning" else "30"
            caption = f"🔄 **Traffic Update:**\nEst. Time: **{duration} mins**\nTraffic still high. Next update in {interval} mins."
            should_send = True
            
    elif state["traffic_jam"]:
        # Traffic just cleared up
        caption = f"🎉 **Traffic Update:**\nEst. Time: **{duration} mins**\nTraffic resolved. No further updates if traffic stays low."
        should_send = True

    # Note: If it is NOT heavy, and state["traffic_jam"] is False, should_send remains False (Silent Baseline).

    if should_send:
        send_telegram(caption, map_img)

    # ---------------------------------------------------------
    # 4. THE MEMORY: Save state only ONCE at the very end
    # ---------------------------------------------------------
    save_state(last_sent=current_time, last_date=today_date, current_window=active_window, traffic_jam=is_heavy)