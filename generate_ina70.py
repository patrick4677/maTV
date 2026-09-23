import json
import os
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

CHANNEL_ID = "ina70.fr"
INA70_PLUTO_ID = "639b54404cfdf7000729b3c1"
OUTPUT_FILE = "coulisses/ina70.xml"

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

def format_xmltv_date(date_str):
    if not date_str:
        return ""
    try:
        clean_str = date_str.split('.')[0].replace("Z", "")
        dt_utc = datetime.strptime(clean_str, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        dt_paris = dt_utc.astimezone(PARIS_TZ)
        return dt_paris.strftime("%Y%m%d%H%M%S") + f" {PARIS_OFFSET_STR}"
    except Exception:
        return ""

def extract_image_url(item, episode_info):
    if isinstance(item.get('tile'), dict) and item['tile'].get('path'):
        return item['tile']['path']
    if isinstance(episode_info.get('poster'), dict) and episode_info['poster'].get('path'):
        return episode_info['poster']['path']
    if isinstance(episode_info.get('thumbnail'), dict) and episode_info['thumbnail'].get('path'):
        return episode_info['thumbnail']['path']
    series_info = episode_info.get('series') if isinstance(episode_info.get('series'), dict) else {}
    if isinstance(series_info.get('tile'), dict) and series_info['tile'].get('path'):
        return series_info['tile']['path']
    return None

def fetch_chunk(start_dt, stop_dt, headers):
    start_str = urllib.parse.quote(start_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"))
    stop_str = urllib.parse.quote(stop_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"))
    
    # Endpoint public v2/channels sans besoin de token Bearer
    url = f"https://api.pluto.tv/v2/channels?start={start_str}&stop={stop_str}&channelIds={INA70_PLUTO_ID}&clientRegion=FR"
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            channels = data if isinstance(data, list) else data.get('channels', [data])
            for ch in channels:
                ch_id = str(ch.get('_id') or ch.get('id') or '')
                if ch_id == INA70_PLUTO_ID or "INA" in str(ch.get('name', '')).upper():
                    return ch.get('timelines', []), ch.get('featuredImage', {}).get('path') or ch.get('logo', {}).get('path')
    except Exception as e:
        print(f"Créneau {start_dt.strftime('%d/%m %H:%M')} : {e}", flush=True)
    return [], None

def main():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'fr-FR,fr;q=0.9',
        'X-Forwarded-For': '185.24.184.1',
        'CF-IPCountry': 'FR'
    }

    now = datetime.now(timezone.utc)
    all_programmes = {}
    logo_url = None

    # Requêtes par tranches de 12 heures sur 48h
    for i in range(4):
        start_dt = now + timedelta(hours=i * 12)
        stop_dt = start_dt + timedelta(hours=12)
        print(f"Récupération tranche {i+1}/4 ({start_dt.strftime('%d/%m %H:%M')} -> {stop_dt.strftime('%d/%m %H:%M')})...", flush=True)
        
        timelines, icon = fetch_chunk(start_dt, stop_dt, headers)
        if icon and not logo_url:
            logo_url = icon
            
        for item in timelines:
            prog_key = f"{item.get('start')}_{item.get('title')}"
            all_programmes[prog_key] = item

    if not all_programmes:
        print("Erreur : Aucun programme récupéré.", flush=True)
        sys.exit(1)

    tv = ET.Element('tv', {
        'generator-info-name': 'INA70-EPG-Generator',
        'source-info-name': 'Pluto TV FR'
    })

    channel = ET.SubElement(tv, 'channel', id=CHANNEL_ID)
    display_name = ET.SubElement(channel, 'display-name', lang="fr")
    display_name.text = "INA 70"

    if logo_url:
        ET.SubElement(channel, 'icon', src=logo_url)

    count = 0
    for item in all_programmes.values():
        title_text = str(item.get('title', ''))
        if "INAZUMA" in title_text.upper():
            continue

        start_date = format_xmltv_date(item.get('start'))
        stop_date = format_xmltv_date(item.get('stop') or item.get('end'))

        if not start_date or not stop_date:
            continue

        prog = ET.SubElement(tv, 'programme', {
            'start': start_date,
            'stop': stop_date,
            'channel': CHANNEL_ID
        })

        title = ET.SubElement(prog, 'title', lang="fr")
        title.text = title_text or "Programme INA 70"

        episode_info = item.get('episode') if isinstance(item.get('episode'), dict) else {}
        if episode_info.get('name'):
            sub_title = ET.SubElement(prog, 'sub-title', lang="fr")
            sub_title.text = str(episode_info['name'])

        desc_text = item.get('description') or episode_info.get('description') or "Archives INA"
        desc = ET.SubElement(prog, 'desc', lang="fr")
        desc.text = str(desc_text)

        category = ET.SubElement(prog, 'category', lang="fr")
        category.text = str(item.get('category') or "Archives")

        img_url = extract_image_url(item, episode_info)
        if img_url:
            ET.SubElement(prog, 'icon', src=img_url)

        count += 1

    xml_out = ET.tostring(tv, encoding='utf-8')
    parsed = minidom.parseString(xml_out)
    pretty_xml = parsed.toprettyxml(indent="  ")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(pretty_xml)

    print(f"Succès : {count} programmes inscrits dans {OUTPUT_FILE}.", flush=True)

if __name__ == "__main__":
    main()
