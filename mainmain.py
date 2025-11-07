import requests, os, json
from datetime import datetime, date, timedelta
from icalendar import Calendar

# --- CONFIG ---
API_KEY = "qhiuNS17hvxxODKhdDOBIAiJYE7ViFzQ"
SOURCE_URL_ICAL = "https://yummytutel.github.io/ical/filtr%C3%A9.ics"
HOME = [48.91591740393165, 2.226859988192813]   # Home (lat, lon)
DEST = [48.82498550415039, 2.330345630645752]    # Destination (lat, lon)

# 📅 --- SET YOUR DATE HERE ---
TARGET_DATE = date.today()  # or date(2025, 11, 7), etc.
SAFETY_OFFSET_MINUTES = 7   # leave 7 min earlier

# --- FUNCTIONS ---

def get_first_event_start(ical_content: bytes, target_date: date):
    """Return the datetime of the first event of a given date."""
    cal = Calendar.from_ical(ical_content)
    events = []
    for component in cal.walk():
        if component.name == "VEVENT":
            start = component.get("DTSTART").dt
            if hasattr(start, "date") and start.date() == target_date:
                events.append(start)
    return min(events) if events else None


def get_journey(url, api_key):
    """Call IDFM API and return parsed JSON."""
    r = requests.get(url, headers={"apikey": api_key})
    r.raise_for_status()
    data = r.json()
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print("✅ API call success:", r.status_code)
    return data


def get_duration_from_response(data):
    """Extract duration (in minutes) from the API response."""
    try:
        duration_seconds = data["journeys"][0]["duration"]
        return duration_seconds // 60
    except (KeyError, IndexError):
        return None


def print_directions(data):
    """Print the complete step-by-step directions."""
    try:
        journey = data["journeys"][0]
        print("\n🧭 Journey details:")
        for section in journey["sections"]:
            mode = section.get("mode", "UNKNOWN")
            from_name = section.get("from", {}).get("name", "Unknown")
            to_name = section.get("to", {}).get("name", "Unknown")
            start = section.get("departure_date_time", "")
            end = section.get("arrival_date_time", "")
            dep = format_time(start)
            arr = format_time(end)

            if mode == "walking":
                print(f" 🚶 Walk from {from_name} to {to_name} ({dep} → {arr})")
            elif mode == "bus":
                line = section.get("display_informations", {}).get("code", "")
                print(f" 🚌 Bus {line}: {from_name} → {to_name} ({dep} → {arr})")
            elif mode in ["metro", "tramway", "train", "rer"]:
                line = section.get("display_informations", {}).get("code", "")
                net = section.get("display_informations", {}).get("network", "")
                print(f" 🚆 {net} {line}: {from_name} → {to_name} ({dep} → {arr})")
            else:
                # generic fallback
                print(f" ➡️ {mode.capitalize()} from {from_name} to {to_name} ({dep} → {arr})")

        print()  # blank line at the end
    except Exception as e:
        print("⚠️ Could not parse detailed directions:", e)


def format_time(dt_string):
    """Format Navitia datetime strings (YYYYMMDDTHHMMSS) to HH:MM."""
    try:
        dt = datetime.strptime(dt_string, "%Y%m%dT%H%M%S")
        return dt.strftime("%H:%M")
    except Exception:
        return "??:??"


# --- MAIN ---

print(f"📆 Searching events for {TARGET_DATE}...")

# Download iCal
ical_response = requests.get(SOURCE_URL_ICAL)
ical_response.raise_for_status()

# Find the first event of the day
first_event = get_first_event_start(ical_response.content, TARGET_DATE)

if not first_event:
    print("❌ No events found for this date.")
else:
    print("📅 First event starts at:", first_event)

    # Format datetime for IDFM API (YYYYMMDDTHHMMSS)
    DT = first_event.strftime("%Y%m%dT%H%M%S")

    # Build the IDFM request URL
    url = (
        f"https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia/journeys?"
        f"to={DEST[1]}%3B{DEST[0]}"
        f"&from={HOME[1]}%3B{HOME[0]}"
        f"&datetime_represents=arrival"
        f"&datetime={DT}"
    )

    print("🌐 Calling IDFM API with datetime:", DT)
    data = get_journey(url, API_KEY)

    # Get duration and compute departure time
    duration = get_duration_from_response(data)
    if duration is not None:
        print(f"🕒 Estimated travel time: {duration} minutes")

        total_offset = duration + SAFETY_OFFSET_MINUTES
        departure_time = first_event - timedelta(minutes=total_offset)

        print(f"🚶 Leave at: {departure_time.strftime('%H:%M')} "
              f"to arrive for {first_event.strftime('%H:%M')} "
              f"(includes {SAFETY_OFFSET_MINUTES} min margin)")

        # Print detailed step-by-step itinerary
        print_directions(data)

    else:
        print("⚠️ Could not extract travel duration from response.")