import json
import os
import sys
from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom
import urllib.request

CHANNEL_ID = "ina70.fr"
PLUTO_CHANNEL_ID = "651fe0613099fc00084bd30e"
API_URL = f"https://api.pluto.tv/v2/channels/{PLUTO_CHANNEL_ID}/guide"
OUTPUT_FILE = "coulisses/ina70.xml"

def format_xmltv_date(date_str):
    try:
        dt = datetime.strptime(date_str.split('.')[0], "%Y-%m-%dT%H:%M:%S")
        return dt.strftime("%Y%m%d%H%M%S +0000")
    except Exception as e:
        print(f"Erreur de conversion de date ({date_str}): {e}")
        return ""

def main():
    # 1. Création explicite du dossier de destination
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    # 2. Requête avec User-Agent complet
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }
    
    try:
        req = urllib.request.Request(API_URL, headers=headers)
        with urllib.request.urlopen(req) as response:
            epg_data = json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Erreur lors de la récupération de l'API Pluto TV: {e}")
        sys.exit(1)

    # 3. Construction de l'arborescence XMLTV
    tv = ET.Element('tv', {
        'generator-info-name': 'INA70-EPG-Generator',
        'source-info-name': 'Pluto TV'
    })

    channel = ET.SubElement(tv, 'channel', id=CHANNEL_ID)
    display_name = ET.SubElement(channel, 'display-name', lang="fr")
    display_name.text = "INA 70"
    ET.SubElement(channel, 'icon', src="https://images.pluto.tv/series/651fe0613099fc00084bd30e/featuredImage.jpg")

    for item in epg_data:
        start_date = format_xmltv_date(item.get('start', ''))
        stop_date = format_xmltv_date(item.get('end', ''))
        
        if not start_date or not stop_date:
            continue

        prog = ET.SubElement(tv, 'programme', {
            'start': start_date,
            'stop': stop_date,
            'channel': CHANNEL_ID
        })

        title = ET.SubElement(prog, 'title', lang="fr")
        title.text = item.get('title') or "Programme INA 70"

        episode_info = item.get('episode') or {}
        if episode_info.get('name'):
            sub_title = ET.SubElement(prog, 'sub-title', lang="fr")
            sub_title.text = episode_info['name']

        desc_text = item.get('description') or episode_info.get('description') or "Archives INA"
        desc = ET.SubElement(prog, 'desc', lang="fr")
        desc.text = desc_text

        category = ET.SubElement(prog, 'category', lang="fr")
        category.text = item.get('category') or "Archives"

        tile = item.get('tile', {}).get('path') if isinstance(item.get('tile'), dict) else None
        if not tile and isinstance(episode_info.get('series'), dict):
            tile = episode_info.get('series', {}).get('tile', {}).get('path')
            
        if tile:
            ET.SubElement(prog, 'icon', src=tile)

    # 4. Écriture dans le fichier XML
    xml_bytes = ET.tostring(tv, encoding='utf-8')
    parsed = minidom.parseString(xml_bytes)
    pretty_xml = parsed.toprettyxml(indent="  ")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(pretty_xml)

    print(f"Succès : {len(epg_data)} programmes enregistrés dans {OUTPUT_FILE}.")

if __name__ == "__main__":
    main()
