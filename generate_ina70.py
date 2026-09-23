import json
import os
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

CHANNEL_ID = "ina70.fr"
# ID exact Pluto TV FR pour INA 70
INA70_PLUTO_ID = "639b54404cfdf7000729b3c1"
OUTPUT_FILE = "coulisses/ina70.xml"

def format_xmltv_date(date_str):
    if not date_str:
        return ""
    try:
        # Nettoyage de la chaîne de date d'origine
        clean_str = date_str.split('.')[0].replace("Z", "")
        dt_utc = datetime.strptime(clean_str, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        
        # Conversion automatique vers le fuseau horaire local (Europe/Paris)
        # Gère automatiquement le passage heure d'été (+0200) / heure d'hiver (+0100)
        dt_local = dt_utc.astimezone()
        
        return dt_local.strftime("%Y%m%d%H%M%S %z")
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
    return None

def main():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    now = datetime.now(timezone.utc)
    start_time = urllib.parse.quote((now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:00:00.000Z"))
    stop_time = urllib.parse.quote((now + timedelta(hours=48)).strftime("%Y-%m-%dT%H:00:00.000Z"))

    # Utilisation des API de contenu Pluto TV FR avec contournement IP
    endpoints = [
        f"https://service-channels.clusters.pluto.tv/v2/guide/channels?start={start_time}&stop={stop_time}&channelIds={INA70_PLUTO_ID}&clientRegion=FR",
        f"https://api.pluto.tv/v2/channels?start={start_time}&stop={stop_time}&channelIds={INA70_PLUTO_ID}&clientRegion=FR",
        f"https://service-channels.clusters.pluto.tv/v2/guide/channels?start={start_time}&stop={stop_time}"
    ]

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'fr-FR,fr;q=0.9',
        'X-Forwarded-For': '185.24.184.1',
        'CF-IPCountry': 'FR'
    }

    epg_data = []
    logo_url = None

    for url in endpoints:
        print(f"Tentative de connexion : {url[:75]}...")
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                
                channels = []
                if isinstance(data, list):
                    channels = data
                elif isinstance(data, dict):
                    channels = data.get('channels', [data])

                for ch in channels:
                    ch_id = str(ch.get('_id') or ch.get('id') or '')
                    ch_name = str(ch.get('name', '')).upper()

                    if ch_id == INA70_PLUTO_ID or ("INA" in ch_name and "INAZUMA" not in ch_name):
                        epg_data = ch.get('timelines', [])
                        logo_url = ch.get('featuredImage', {}).get('path') or ch.get('logo', {}).get('path')
                        print(f"Chaîne FR trouvée ({ch.get('name')}) - {len(epg_data)} programmes récupérés.")
                        break

                if epg_data:
                    break
        except Exception as e:
            print(f"Erreur endpoint : {e}")

    if not epg_data:
        print("Erreur : Impossible d'obtenir la grille INA 70 depuis Pluto TV.")
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
    for item in epg_data:
        title_text = str(item.get('title', ''))
        
        # Filtre de sécurité
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

    print(f"Succès : {count} programmes inscrits dans {OUTPUT_FILE}.")

if __name__ == "__main__":
    main()
