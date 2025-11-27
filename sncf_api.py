import os
from datetime import datetime
import pandas as pd
import requests



TOKEN = "46044c39-b224-418c-a4a8-60c880909bcd"
BASE_URL = "https://api.sncf.com/v1/coverage/sncf"




def fetch_tgv_data_routes(stop_from, stop_to, DATE_SEARCH):

    
    TIME_START  = "040000"
    TIME_END    = "235900"
    
    DATETIME_START = f"{DATE_SEARCH}T{TIME_START}"
    DATETIME_END   = f"{DATE_SEARCH}T{TIME_END}"

    url = f"{BASE_URL}/journeys"
    params = {
    "from": stop_from,
    "to": stop_to,
    "datetime":  DATETIME_START,
    "count": 200,
    "data_freshness": "realtime"
    }


    resp = requests.get(url, auth=(TOKEN, ""), params=params, timeout=30)
    resp.raise_for_status()
    journeys = resp.json().get("journeys", [])


    rows = []
    for j in journeys:
        dep_dt = datetime.strptime(j["departure_date_time"], "%Y%m%dT%H%M%S")
        if dep_dt < datetime.strptime(DATETIME_START, "%Y%m%dT%H%M%S") or \
            dep_dt > datetime.strptime(DATETIME_END,   "%Y%m%dT%H%M%S"):
            continue

        sections = j.get("sections", [])

        # Exclude journeys with transfer/walk sections
        if any(s.get("type") in ("transfer", "street_network") for s in sections):
            continue

        public_sections = [s for s in sections if s.get("type") == "public_transport"]

        # Keep only single public_transport section (direct)
        if len(public_sections) != 1:
            continue

        # Check commercial_mode of that section
        s = public_sections[0]
        info = s.get("display_informations") or {}
        commercial_mode = (info.get("commercial_mode") or "").upper()



        train_id = info.get("trip_short_name") or info.get("headsign") or "N/A"
        duration_min = j.get("duration", 0) // 60

        rows.append({
            "Train": train_id,
            "Depart": dep_dt.strftime("%H:%M"),
            "Arrivee": datetime.strptime(j["arrival_date_time"], "%Y%m%dT%H%M%S").strftime("%H:%M"),
            "Duree(min)": duration_min,
            "Statut": j.get("status", ""),
            "Modes": commercial_mode,
        })
    return pd.DataFrame(rows)