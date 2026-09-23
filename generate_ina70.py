import gzip
import json
import os
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

CHANNEL_ID = "ina70.fr"
OUTPUT_FILE = "coulisses/ina70.xml"

def format_xmltv_date(date_str):
    if not date_str:
        return ""
    try:
        dt = datetime.strptime(date_str.split('.')[0], "%Y-%m-%dT%H:%M:%S")
        return dt.strftime("%Y%m%d%H%M%S +0000")
    except Exception as e:
        return ""

def fetch_from_pluto():
    """Tente de récupérer le guide Pluto TV FR via l'API v2."""
    now = datetime.now(timezone.utc)
    start_time = urllib.parse.quote((now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:00:00.000Z"))
    stop_time = urllib.parse.quote((now + timedelta(hours=48)).strftime("%Y-%m-%dT%H:00:00.000Z"))
    
    url = f"https://api.pluto.tv/v2/channels?start={start_time}&stop={stop_time}&clientRegion=FR"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': 'application/json',
        'Accept-Language': 'fr-FR,fr;q=0.9'
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            channels = json.loads(resp.read().decode('utf-8'))
            for ch in channels:
                name = str(ch.get('name', '')).upper()
                if "INA 70" in name or "INA - 70" in name:
                    print(f"Chaîne FR trouvée sur Pluto TV : {ch.get('name')}")
                    return ch.get('timelines', []), ch.get('featuredImage', {}).get('path')
    except Exception as e:
        print(f"Échec Pluto API direct : {e}")
    return None, None

def fetch_from_epgshare():
    """Récupère et décompresse l'EPG global FR."""
    url = "https://epgshare01.online/epgshare01/epg_ripper_FR1.xml.gz"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            compressed_data = resp.read()
            decompressed_data = gzip.decompress(compressed_data)
            return decompressed_data
    except Exception as e:
        print(f"Échec EPGShare : {e}")
        return None

def main():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    tv = ET.Element('tv', {
        'generator-info-name': 'INA70-EPG-Generator',
        'source-info-name': 'INA 70 FR'
    })

    channel = ET.SubElement(tv, 'channel', id=CHANNEL_ID)
    display_name = ET.SubElement(channel, 'display-name', lang="fr")
    display_name.text = "INA 70"

    # 1. Premier essai : API Pluto TV avec filtre strict
    epg_data, logo_url = fetch_from_pluto()
    count = 0

    if epg_data:
        if logo_url:
            ET.SubElement(channel, 'icon', src=logo_url)

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
            title.text = item.get('title') or "Archives INA 70"

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

    # 2. Deuxième essai si Pluto échoue : EPGShare décompressé
    if count == 0:
        print("Bascule sur le miroir EPGShare...")
        xml_bytes = fetch_from_epgshare()
        if xml_bytes:
            try:
                root = ET.fromstring(xml_bytes)
                for prog in root.findall('programme'):
                    prog_ch = prog.get('channel', '').lower()
                    if 'ina' in prog_ch and ('70' in prog_ch or 'ina70' in prog_ch):
                        prog.set('channel', CHANNEL_ID)
                        tv.append(prog)
                        count += 1
            except Exception as e:
                print(f"Erreur d'analyse XML EPGShare : {e}")

    if count == 0:
        print("Erreur : Aucun programme récupéré.")
        sys.exit(1)

    xml_out = ET.tostring(tv, encoding='utf-8')
    parsed = minidom.parseString(xml_out)
    pretty_xml = parsed.toprettyxml(indent="  ")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(pretty_xml)

    print(f"Succès : {count} programmes inscrits dans {OUTPUT_FILE}.")

if __name__ == "__main__":
    main()
