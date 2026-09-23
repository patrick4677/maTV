import json
import os
import sys
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from xml.dom import minidom
import urllib.request
import urllib.parse

CHANNEL_ID = "ina70.fr"
OUTPUT_FILE = "coulisses/ina70.xml"

def format_xmltv_date(timestamp):
    if not timestamp:
        return ""
    try:
        if isinstance(timestamp, (int, float)):
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        return dt.strftime("%Y%m%d%H%M%S +0000")
    except Exception as e:
        print(f"Erreur format date : {e}")
        return ""

def fetch_ina70_epg():
    """Récupère la grille INA 70 via la source alternative française."""
    url = "https://apiv2.telerama.fr/v1/programmes/grille?channel_ids=2182&date=" + datetime.now().strftime("%Y-%m-%d")
    
    # Header d'identification standard
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get('donnees', [])
    except Exception as e:
        print(f"Échec Télérama ({e}), tentative via source miroir EPG...")
        
    # Source de secours FR directe
    fallback_url = "https://raw.githubusercontent.com/iptv-org/epg/master/sites/tv.pourtous.org/ina70.fr.epg.xml"
    try:
        req = urllib.request.Request(fallback_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode('utf-8')
    except Exception as e:
        print(f"Erreur source miroir : {e}")
        return None

def main():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    print("Récupération des vrais programmes d'INA 70...")
    
    # 1. Essai via l'API Pluto TV FR avec proxy / headers stricts d'isolation de canal
    url = "https://service-channels.clusters.pluto.tv/v2/guide/channels?start=" + urllib.parse.quote(datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00.000Z")) + "&stop=" + urllib.parse.quote(datetime.now(timezone.utc).strftime("%Y-%m-%dT23:59:59.000Z"))
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'fr-FR,fr;q=0.9'
    }

    epg_items = []
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            res = json.loads(resp.read().decode('utf-8'))
            channels = res if isinstance(res, list) else res.get('channels', [])
            for ch in channels:
                name = str(ch.get('name', '')).upper()
                # Filtrage strict sur les mots "INA" et exclusion d'anime/inazuma
                if "INA" in name and "INAZUMA" not in name:
                    print(f"Chaîne identifiée : {ch.get('name')}")
                    epg_items = ch.get('timelines', [])
                    break
    except Exception as e:
        print(f"Erreur lors du filtrage : {e}")

    # Si Pluto continue de renvoyer Inazuma à cause de l'IP US, reconstruction XML direct
    tv = ET.Element('tv', {
        'generator-info-name': 'INA70-EPG-Generator',
        'source-info-name': 'INA 70 France'
    })

    channel = ET.SubElement(tv, 'channel', id=CHANNEL_ID)
    display_name = ET.SubElement(channel, 'display-name', lang="fr")
    display_name.text = "INA 70"

    count = 0
    for item in epg_items:
        title_text = str(item.get('title', ''))
        
        # Sécurité anti-Inazuma Eleven
        if "INAZUMA" in title_text.upper() or "ZOOLAN" in title_text.upper():
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

        desc_text = item.get('description') or episode_info.get('description') or "Archives INA 70"
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

    print(f"Terminé : {count} programmes d'archives validés dans {OUTPUT_FILE}.")

if __name__ == "__main__":
    main()
