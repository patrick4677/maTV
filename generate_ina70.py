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
PLUTO_CHANNEL_ID = "639b54404cfdf7000729b3c1"
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

def fetch_data_with_boot():
    """Tente d'obtenir un jeton JWT via l'API v4 boot."""
    device_id = str(uuid.uuid4())
    client_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    params = urllib.parse.urlencode({
        'appName': 'web',
        'appVersion': '8.0.0-assets',
        'deviceType': 'web',
        'deviceId': device_id,
        'clientModelNumber': 'chrome',
        'serverSide': 'true',
        'clientTime': client_time
    })
    
    url = f"https://boot.pluto.tv/v4/start?{params}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        boot_data = json.loads(resp.read().decode('utf-8'))
        token = boot_data.get('sessionToken')
        return token

def fetch_epg_direct(start_time, stop_time, jwt_token=None):
    """Interroge l'API des chaînes avec ou sans jeton."""
    url = f"https://api.pluto.tv/v2/channels?start={start_time}&stop={stop_time}&lang=fr&clientRegion=FR"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'fr-FR,fr;q=0.9'
    }
    
    if jwt_token:
        headers['Authorization'] = f'Bearer {jwt_token}'

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode('utf-8'))

def fetch_timeline_direct(start_time, stop_time):
    """Recherche spécifique sur la chaîne INA 70 via endpoint direct timeline."""
    url = f"https://api.pluto.tv/v2/channels/{PLUTO_CHANNEL_ID}/timeline?start={start_time}&stop={stop_time}&lang=fr"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode('utf-8'))

def main():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    now = datetime.now(timezone.utc)
    start_time = urllib.parse.quote((now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:00:00.000Z"))
    stop_time = urllib.parse.quote((now + timedelta(hours=48)).strftime("%Y-%m-%dT%H:00:00.000Z"))

    jwt_token = None
    try:
        jwt_token = fetch_data_with_boot()
        print("Jeton JWT récupéré avec succès.")
    except Exception as e:
        print(f"Information : Impossible d'obtenir le token boot ({e}), passage en mode direct.")

    channels_data = None
    try:
        print("Téléchargement du guide des chaînes...")
        channels_data = fetch_epg_direct(start_time, stop_time, jwt_token)
    except Exception as e:
        print(f"Avertissement : Échec de la récupération globale ({e}). Tentative via Timeline direct...")

    epg_data = []
    ina_channel = None

    if isinstance(channels_data, list):
        for ch in channels_data:
            name = ch.get('name', '').upper()
            ch_id = str(ch.get('_id') or ch.get('id') or '')
            if "INA 70" in name or "INA - 70" in name or ch_id == PLUTO_CHANNEL_ID:
                ina_channel = ch
                print(f"Chaîne trouvée : {ch.get('name')}")
                break

    if ina_channel:
        epg_data = ina_channel.get('timelines', [])
    else:
        # Secours via timeline directe
        try:
            timeline_res = fetch_timeline_direct(start_time, stop_time)
            if isinstance(timeline_res, dict):
                epg_data = timeline_res.get('timelines', [])
                ina_channel = timeline_res
                print("Données récupérées via l'API timeline spécifique.")
        except Exception as e:
            print(f"Erreur timeline secours : {e}")

    if not epg_data:
        print("Erreur : Aucun programme trouvé pour la chaîne INA 70.")
        sys.exit(1)

    tv = ET.Element('tv', {
        'generator-info-name': 'INA70-EPG-Generator',
        'source-info-name': 'Pluto TV FR'
    })

    channel = ET.SubElement(tv, 'channel', id=CHANNEL_ID)
    display_name = ET.SubElement(channel, 'display-name', lang="fr")
    display_name.text = "INA 70"

    logo_url = None
    if isinstance(ina_channel, dict):
        logo_url = ina_channel.get('featuredImage', {}).get('path') or ina_channel.get('logo', {}).get('path')
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
