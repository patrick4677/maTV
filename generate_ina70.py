import os
import sys
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
import urllib.request
from datetime import datetime, timedelta, timezone

# Fichiers dans le même répertoire que le script
OUTPUT_FILE = "coulisses/ina70.xml"
CHANNELS_CONFIG_FILE = "coulisses/channels.json"

def load_config():
    """Charge l'URL et le dictionnaire des chaînes depuis le JSON local."""
    if os.path.exists(CHANNELS_CONFIG_FILE):
        try:
            with open(CHANNELS_CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                url = config.get("pluto_xml_url")
                channels = config.get("target_channels", {})
                return url, channels
        except Exception as e:
            print(f"Erreur de lecture du JSON : {e}")
    
    print(f"Erreur : Impossible de trouver le fichier {CHANNELS_CONFIG_FILE} dans le répertoire courant.")
    sys.exit(1)

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
    pluto_xml_url, target_channels = load_config()
    
    if not pluto_xml_url or not target_channels:
        print("Erreur : Configuration incomplète dans le JSON.")
        sys.exit(1)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    print(f"Téléchargement du flux depuis : {pluto_xml_url}")

    try:
        req = urllib.request.Request(pluto_xml_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            xml_data = resp.read()
    except Exception as e:
        print(f"Erreur de téléchargement : {e}")
        sys.exit(1)

    channel_names = ", ".join(target_channels.values())
    print(f"Extraction des programmes pour : {channel_names}...")
    root = ET.fromstring(xml_data)

    tv = ET.Element('tv', {
        'generator-info-name': 'FAST-EPG-Generator',
        'source-info-name': 'Pluto TV FR'
    })

    for channel in root.findall('channel'):
        ch_id = channel.get('id')
        if ch_id in target_channels:
            channel.set('id', target_channels[ch_id])
            tv.append(channel)

    count = 0
    now = datetime.now(timezone.utc)
    min_date = now - timedelta(hours=12)
    max_date = now + timedelta(days=2)

    for prog in root.findall('programme'):
        ch_id = prog.get('channel')
        if ch_id in target_channels:
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

            prog.set('channel', target_channels[ch_id])
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