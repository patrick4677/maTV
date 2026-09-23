import gzip
import os
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom
import urllib.request

CHANNEL_ID = "ina70.fr"
OUTPUT_FILE = "coulisses/ina70.xml"

# Mots-clés d'identification de la chaîne dans le fichier XML global
MATCH_KEYWORDS = ["ina70", "ina-70", "ina 70", "plutotvina70"]

def fetch_from_epgshare():
    """Récupère et décompresse l'EPG global FR d'EPGShare."""
    url = "https://epgshare01.online/epgshare01/epg_ripper_FR1.xml.gz"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    try:
        print("Téléchargement de la grille EPGShare FR...")
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=40) as resp:
            compressed_data = resp.read()
            return gzip.decompress(compressed_data)
    except Exception as e:
        print(f"Échec du téléchargement EPGShare : {e}")
        return None

def main():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    xml_bytes = fetch_from_epgshare()
    if not xml_bytes:
        print("Erreur : Impossible de télécharger l'EPG.")
        sys.exit(1)

    try:
        print("Analyse du fichier XML...")
        root = ET.fromstring(xml_bytes)
    except Exception as e:
        print(f"Erreur de lecture du XML : {e}")
        sys.exit(1)

    # 1. Identification de l'ID exact attribué à INA 70 dans le XML source
    target_channel_ids = set()
    for channel in root.findall('channel'):
        ch_id = channel.get('id', '')
        display_names = [dn.text.lower() for dn in channel.findall('display-name') if dn.text]
        
        # Test sur l'ID ou le nom d'affichage
        if any(kw in ch_id.lower() for kw in MATCH_KEYWORDS) or any(any(kw in dn for kw in MATCH_KEYWORDS) for dn in display_names):
            target_channel_ids.add(ch_id)
            print(f"Chaîne INA 70 identifiée dans le XML source (ID : {ch_id})")

    tv = ET.Element('tv', {
        'generator-info-name': 'INA70-EPG-Generator',
        'source-info-name': 'EPGShare FR'
    })

    channel_elem = ET.SubElement(tv, 'channel', id=CHANNEL_ID)
    display_name = ET.SubElement(channel_elem, 'display-name', lang="fr")
    display_name.text = "INA 70"

    count = 0
    # 2. Extraire tous les programmes associés
    for prog in root.findall('programme'):
        prog_ch = prog.get('channel', '')
        
        # Si la chaîne correspond à un ID trouvé ou contient ina70
        if prog_ch in target_channel_ids or any(kw in prog_ch.lower() for kw in MATCH_KEYWORDS):
            prog.set('channel', CHANNEL_ID)
            tv.append(prog)
            count += 1

    if count == 0:
        print("Erreur : La chaîne INA 70 n'a pas été trouvée dans la grille EPGShare.")
        sys.exit(1)

    xml_out = ET.tostring(tv, encoding='utf-8')
    parsed = minidom.parseString(xml_out)
    pretty_xml = parsed.toprettyxml(indent="  ")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(pretty_xml)

    print(f"Succès : {count} programmes inscrits dans {OUTPUT_FILE}.")

if __name__ == "__main__":
    main()
