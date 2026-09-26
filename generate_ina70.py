import os
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom
import urllib.request
from datetime import datetime, timedelta, timezone

OUTPUT_FILE = "coulisses/ina70.xml"
PLUTO_XML_URL = "https://raw.githubusercontent.com/matthuisman/i.mjh.nz/refs/heads/master/PlutoTV/fr.xml"

# Mapping des ID Pluto TV réels vers les ID cibles de votre application
TARGET_CHANNELS = {
    "639b54404cfdf7000729b3c1": "ina70.fr",              # INA 70[span_1](start_span)[span_1](end_span)
    "63b579961bdba100071214cb": "cestpassorcier.fr",      # C'est pas sorcier[span_2](start_span)[span_2](end_span)
    "6245ccd0c6cdb800074632e4": "macgyver.fr",            # MacGyver
    "6671b21ffc3a46000857fe75": "missionimpossible.fr",  # Mission Impossible
    "691b332aa4385c191ee44b57": "rex.fr",                 # Rex, chien flic
    "60afa749ac7f3200078adb40": "walkertexasranger.fr"    # Walker Texas Ranger
}

def get_paris_tz():
    now = datetime.now(timezone.utc)
    year = now.year
    march_last_sun = max(day for day in range(25, 32) if datetime(year, 3, day).weekday() == 6)
    oct_last_sun = max(day for day in range(25, 32) if datetime(year, 10, day).weekday() == 6)
    
    dst_start = datetime(year, 3, march_last_sun, 1, tzinfo=timezone.utc)
    dst_end = datetime(year, 10, oct_last_sun, 1, tzinfo=timezone.utc)
    
    if dst_start <= now < dst_end:
        return timezone(timedelta(hours=2)), "+0200"
    else:
        return timezone(timedelta(hours=1)), "+0100"

PARIS_TZ, PARIS_OFFSET_STR = get_paris_tz()

def convert_date(date_str):
    if not date_str:
        return ""
    try:
        clean = date_str.split()[0]
        dt_utc = datetime.strptime(clean, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        dt_paris = dt_utc.astimezone(PARIS_TZ)
        return dt_paris.strftime("%Y%m%d%H%M%S") + f" {PARIS_OFFSET_STR}"
    except Exception:
        return date_str

def main():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    print("Téléchargement du flux Pluto TV...")

    try:
        req = urllib.request.Request(PLUTO_XML_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            xml_data = resp.read()
    except Exception as e:
        print(f"Erreur de téléchargement : {e}")
        sys.exit(1)

    print("Extraction des programmes (INA 70, C'est pas sorcier, MacGyver, Mission Impossible, Rex, Walker)...")
    root = ET.fromstring(xml_data)

    tv = ET.Element('tv', {
        'generator-info-name': 'FAST-EPG-Generator',
        'source-info-name': 'Pluto TV FR'
    })

    for channel in root.findall('channel'):
        ch_id = channel.get('id')
        if ch_id in TARGET_CHANNELS:
            channel.set('id', TARGET_CHANNELS[ch_id])
            tv.append(channel)

    count = 0
    now = datetime.now(timezone.utc)
    min_date = now - timedelta(hours=12)
    max_date = now + timedelta(days=2)

    for prog in root.findall('programme'):
        ch_id = prog.get('channel')
        if ch_id in TARGET_CHANNELS:
            start_str = prog.get('start')
            stop_str = prog.get('stop')
            
            if start_str:
                try:
                    clean = start_str.split()[0]
                    dt_prog = datetime.strptime(clean, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
                    if not (min_date <= dt_prog <= max_date):
                        continue
                except Exception:
                    pass

            prog.set('channel', TARGET_CHANNELS[ch_id])
            if start_str: prog.set('start', convert_date(start_str))
            if stop_str: prog.set('stop', convert_date(stop_str))

            tv.append(prog)
            count += 1

    xml_out = ET.tostring(tv, encoding='utf-8')
    parsed = minidom.parseString(xml_out)
    pretty_xml = parsed.toprettyxml(indent="  ")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(pretty_xml)

    print(f"Succès : {count} programmes extraits dans {OUTPUT_FILE}.")

if __name__ == "__main__":
    main()