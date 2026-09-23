import json
import os
import sys
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET
from xml.dom import minidom
import urllib.request

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

def main():
    # 1. Création du dossier de destination s'il n'existe pas
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    # 2. Construction de l'URL avec plage de temps obligatoire pour Pluto TV
    now = datetime.now(timezone.utc)
    start_time = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:00:00.000Z")
    stop_time = (now + timedelta(hours=48)).strftime("%Y-%m-%dT%H:00:00.000Z")

    api_url = f"https://api.pluto.tv/v2/channels?start={start_time}&stop={stop_time}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }

    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req) as response:
            channels_data = json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Erreur lors de la requête API Pluto TV ({api_url}) : {e}")
        sys.exit(1)

    # 3. Recherche de la chaîne INA 70
    ina_channel = None
    for ch in channels_data:
        if ch.get('_id') == PLUTO_CHANNEL_ID or "INA 70" in ch.get('name', '').upper():
            ina_channel = ch
            break

    if not ina_channel:
        print("Erreur : Chaîne INA 70 introuvable dans le flux Pluto TV.")
        sys.exit(1)

    epg_data = ina_channel.get('timelines', [])

    # 4. Génération de l'arborescence XMLTV
    tv = ET.Element('tv', {
        'generator-info-name': 'INA70-EPG-Generator',
        'source-info-name': 'Pluto TV'
    })

    channel = ET.SubElement(tv, 'channel', id=CHANNEL_ID)
    display_name = ET.SubElement(channel, 'display-name', lang="fr")
    display_name.text = "INA 70"

    icon_url = ina_channel.get('featuredImage', {}).get('path', '')
    if icon_url:
        ET.SubElement(channel, 'icon', src=icon_url)

    # 5. Traitement des programmes
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

    # 6. Écriture du fichier
    xml_bytes = ET.tostring(tv, encoding='utf-8')
    parsed = minidom.parseString(xml_bytes)
    pretty_xml = parsed.toprettyxml(indent="  ")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(pretty_xml)

    print(f"Succès : {len(epg_data)} programmes générés dans {OUTPUT_FILE}.")

if __name__ == "__main__":
    main()
