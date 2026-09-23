import json
import os
import sys
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET
from xml.dom import minidom
import urllib.request
import urllib.parse
import uuid

CHANNEL_ID = "ina70.fr"
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

def get_pluto_jwt():
    """Récupère un jeton JWT valide via l'API boot de Pluto TV."""
    device_id = str(uuid.uuid4())
    url = f"https://boot.pluto.tv/v4/start?appName=web&appVersion=8.0.0&deviceType=web&deviceId={device_id}&deviceMake=Chrome&deviceModel=Web&sid={device_id}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Origin': 'https://pluto.tv',
        'Referer': 'https://pluto.tv/'
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get('sessionToken')
    except Exception as e:
        print(f"Erreur lors de la récupération du jeton JWT : {e}")
        return None

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

def main():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    jwt_token = get_pluto_jwt()
    if not jwt_token:
        print("Échec d'obtention du token d'accès.")
        sys.exit(1)

    now = datetime.now(timezone.utc)
    start_time = urllib.parse.quote((now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:00:00.000Z"))
    stop_time = urllib.parse.quote((now + timedelta(hours=48)).strftime("%Y-%m-%dT%H:00:00.000Z"))

    # API v2 avec le jeton valide
    api_url = f"https://api.pluto.tv/v2/channels?start={start_time}&stop={stop_time}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Authorization': f'Bearer {jwt_token}',
        'Accept': 'application/json'
    }

    print("Téléchargement de la grille TV...")
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as response:
            channels_data = json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Erreur API ({api_url}) : {e}")
        sys.exit(1)

    ina_channel = None
    if isinstance(channels_data, list):
        for ch in channels_data:
            name = ch.get('name', '').upper()
            if "INA 70" in name or "INA - 70" in name:
                ina_channel = ch
                print(f"Chaîne trouvée : {ch.get('name')}")
                break

    if not ina_channel and isinstance(channels_data, list):
        for ch in channels_data:
            if "INA" in ch.get('name', '').upper():
                ina_channel = ch
                print(f"Chaîne trouvée (recherche souple) : {ch.get('name')}")
                break

    if not ina_channel:
        print("Erreur : Chaîne INA introuvable.")
        sys.exit(1)

    epg_data = ina_channel.get('timelines', [])

    tv = ET.Element('tv', {
        'generator-info-name': 'INA70-EPG-Generator',
        'source-info-name': 'Pluto TV FR'
    })

    channel = ET.SubElement(tv, 'channel', id=CHANNEL_ID)
    display_name = ET.SubElement(channel, 'display-name', lang="fr")
    display_name.text = "INA 70"

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

    print(f"Succès : {count} programmes INA 70 générés avec succès.")

if __name__ == "__main__":
    main()
