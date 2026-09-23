import json
import os
import sys
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET
from xml.dom import minidom
import urllib.request
import urllib.error

CHANNEL_ID = "ina70.fr"
PLUTO_CHANNEL_ID = "651fe0613099fc00084bd30e"
OUTPUT_FILE = "coulisses/ina70.xml"

def format_xmltv_date(date_str):
    if not date_str:
        return ""
    try:
        dt = datetime.strptime(date_str.split('.')[0], "%Y-%m-%dT%H:%M:%S")
        return dt.strftime("%Y%m%d%H%M%S +0000")
    except Exception as e:
        print(f"Erreur date ({date_str}): {e}")
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
    if isinstance(series_info.get('featuredImage'), dict) and series_info['featuredImage'].get('path'):
        return series_info['featuredImage']['path']
    if isinstance(item.get('featuredImage'), dict) and item['featuredImage'].get('path'):
        return item['featuredImage']['path']
    return None

def fetch_data(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'fr-FR,fr;q=0.9',
        'Origin': 'https://pluto.tv',
        'Referer': 'https://pluto.tv/'
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode('utf-8'))

def main():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    now = datetime.now(timezone.utc)
    start_time = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:00:00.000Z")
    stop_time = (now + timedelta(hours=48)).strftime("%Y-%m-%dT%H:00:00.000Z")

    # Ajout explicite des paramètres de région FR et langue fr
    urls = [
        f"https://api.pluto.tv/v2/channels?start={start_time}&stop={stop_time}&serverSideParams=region%3DFR%26clientLang%3Dfr&clientCountry=FR&lang=fr",
        f"https://api.pluto.tv/v2/channels/{PLUTO_CHANNEL_ID}/guide?start={start_time}&stop={stop_time}&lang=fr&region=FR"
    ]

    epg_data = []
    ina_channel = None

    for url in urls:
        try:
            data = fetch_data(url)
            if isinstance(data, list):
                for ch in data:
                    if ch.get('_id') == PLUTO_CHANNEL_ID or "INA" in ch.get('name', '').upper():
                        ina_channel = ch
                        epg_data = ch.get('timelines', [])
                        break
            elif isinstance(data, dict):
                epg_data = data.get('timelines', data.get('programs', []))
                ina_channel = data

            if epg_data:
                break
        except Exception as e:
            print(f"Avertissement ({url}) : {e}")

    tv = ET.Element('tv', {
        'generator-info-name': 'INA70-EPG-Generator',
        'source-info-name': 'Pluto TV FR'
    })

    channel = ET.SubElement(tv, 'channel', id=CHANNEL_ID)
    display_name = ET.SubElement(channel, 'display-name', lang="fr")
    display_name.text = "INA 70"

    if ina_channel and isinstance(ina_channel, dict):
        logo_url = (
            ina_channel.get('featuredImage', {}).get('path') or 
            ina_channel.get('logo', {}).get('path')
        )
        if logo_url:
            ET.SubElement(channel, 'icon', src=logo_url)

    count = 0
    for item in epg_data:
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
        title.text = item.get('title') or "Programme INA 70"

        episode_info = item.get('episode') if isinstance(item.get('episode'), dict) else {}
        if episode_info.get('name'):
            sub_title = ET.SubElement(prog, 'sub-title', lang="fr")
            sub_title.text = str(episode_info['name'])

        desc_text = item.get('description') or episode_info.get('description') or "Archives INA"
        desc = ET.SubElement(prog, 'desc', lang="fr")
        desc.text = str(desc_text)

        category = ET.SubElement(prog, 'category', lang="fr")
        category.text = str(item.get('category') or "Archives")

        image_url = extract_image_url(item, episode_info)
        if image_url:
            ET.SubElement(prog, 'icon', src=image_url)

        count += 1

    xml_bytes = ET.tostring(tv, encoding='utf-8')
    parsed = minidom.parseString(xml_bytes)
    pretty_xml = parsed.toprettyxml(indent="  ")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(pretty_xml)

    print(f"Terminé : {count} programmes générés (Région FR).")

if __name__ == "__main__":
    main()
