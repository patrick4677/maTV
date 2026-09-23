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

def fetch_data(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
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

    # URLs d'API à tester
    urls = [
        f"https://api.pluto.tv/v2/channels/{PLUTO_CHANNEL_ID}/guide?start={start_time}&stop={stop_time}",
        f"https://api.pluto.tv/v2/channels?start={start_time}&stop={stop_time}",
        "https://api.pluto.tv/v2/channels"
    ]

    epg_data = []
    ina_channel = None

    for url in urls:
        try:
            print(f"Tentative de connexion à : {url}")
            data = fetch_data(url)
            
            if isinstance(data, list):
                # Réponse sous forme de liste de chaînes
                for ch in data:
                    if ch.get('_id') == PLUTO_CHANNEL_ID or "INA" in ch.get('name', '').upper():
                        ina_channel = ch
                        epg_data = ch.get('timelines', [])
                        break
            elif isinstance(data, dict):
                # Réponse directe pour une seule chaîne
                epg_data = data.get('timelines', data.get('programs', []))
                ina_channel = data

            if epg_data:
                print(f"Données récupérées avec succès depuis {url}")
                break
        except Exception as e:
            print(f"Avertissement ({url}) : {e}")

    # Génération du XMLTV
    tv = ET.Element('tv', {
        'generator-info-name': 'INA70-EPG-Generator',
        'source-info-name': 'Pluto TV'
    })

    channel = ET.SubElement(tv, 'channel', id=CHANNEL_ID)
    display_name = ET.SubElement(channel, 'display-name', lang="fr")
    display_name.text = "INA 70"

    if ina_channel and isinstance(ina_channel, dict):
        icon_url = ina_channel.get('featuredImage', {}).get('path', '')
        if icon_url:
            ET.SubElement(channel, 'icon', src=icon_url)

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
        count += 1

    xml_bytes = ET.tostring(tv, encoding='utf-8')
    parsed = minidom.parseString(xml_bytes)
    pretty_xml = parsed.toprettyxml(indent="  ")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(pretty_xml)

    print(f"Terminé : {count} programmes inscrits dans {OUTPUT_FILE}.")

if __name__ == "__main__":
    main()
