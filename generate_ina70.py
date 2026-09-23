import os
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom
import urllib.request

CHANNEL_ID = "ina70.fr"
OUTPUT_FILE = "coulisses/ina70.xml"

# Sources EPG françaises hébergeant le guide d'INA 70
EPG_SOURCES = [
    "https://raw.githubusercontent.com/iptv-org/epg/master/sites/tv.pourtous.org/ina70.fr.epg.xml",
    "https://epgshare01.online/epgshare01/epg_ripper_FR1.xml.gz"
]

def main():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    xml_content = None
    for source in EPG_SOURCES:
        print(f"Téléchargement du guide depuis : {source}")
        try:
            req = urllib.request.Request(source, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                xml_content = resp.read()
                if xml_content:
                    print("Guide récupéré avec succès.")
                    break
        except Exception as e:
            print(f"Échec sur {source} : {e}")

    if not xml_content:
        print("Erreur : Impossible de récupérer le guide depuis les sources FR.")
        sys.exit(1)

    try:
        root = ET.fromstring(xml_content)
    except Exception as e:
        print(f"Erreur d'analyse XML : {e}")
        sys.exit(1)

    # Reconstruction d'un fichier XMLTV propre et ciblé pour INA 70
    tv = ET.Element('tv', {
        'generator-info-name': 'INA70-EPG-Generator',
        'source-info-name': 'EPG FR'
    })

    channel = ET.SubElement(tv, 'channel', id=CHANNEL_ID)
    display_name = ET.SubElement(channel, 'display-name', lang="fr")
    display_name.text = "INA 70"

    count = 0
    for prog in root.findall('programme'):
        # On vérifie si le programme appartient à INA 70
        prog_channel = prog.get('channel', '').lower()
        if 'ina70' in prog_channel or 'ina' in prog_channel:
            # Réécriture avec l'ID de chaîne local
            prog.set('channel', CHANNEL_ID)
            tv.append(prog)
            count += 1

    # Si aucun programme spécifique n'est filtré, on copie tous les programmes de la source dédiée
    if count == 0 and len(root.findall('programme')) > 0:
        for prog in root.findall('programme'):
            prog.set('channel', CHANNEL_ID)
            tv.append(prog)
            count += 1

    xml_bytes = ET.tostring(tv, encoding='utf-8')
    parsed = minidom.parseString(xml_bytes)
    pretty_xml = parsed.toprettyxml(indent="  ")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(pretty_xml)

    print(f"Succès : {count} programmes en français écrits dans {OUTPUT_FILE}.")

if __name__ == "__main__":
    main()
