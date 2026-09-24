import os
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom
import urllib.request
from datetime import datetime, timedelta, timezone

OUTPUT_FILE = "coulisses/ina70.xml"
PLUTO_XML_URL = "https://raw.githubusercontent.com/matthuisman/i.mjh.nz/refs/heads/master/PlutoTV/fr.xml"
TARGET_ID = "639b54404cfdf7000729b3c1"

def get_paris_tz():
    now = datetime.now(timezone.utc)
    year = now.year
    march_last_sun = max(day for day in range(25, 32) if datetime(year, 3, day).weekday() == 6)
    oct_last_sun = max(day for day in range(25, 32) if datetime(year, 10, day).weekday() == 6)
    
    dst_start = datetime(year, 3, march_last_sun, 1, tzinfo=timezone.utc)
    dst_end = datetime(year, 10, oct_last_sun, 1, tzinfo=timezone.utc)
    
    if dst_start <= now < dst_end:
        return timezone(timedelta(hours=2)), "+0200"
    else:
        return timezone(timedelta(hours=1)), "+0100"

PARIS_TZ, PARIS_OFFSET_STR = get_paris_tz()

def convert_date(date_str):
    if not date_str:
        return ""
    try:
        clean = date_str.split()[0]
        dt_utc = datetime.strptime(clean, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        dt_paris = dt_utc.astimezone(PARIS_TZ)
        return dt_paris.strftime("%Y%m%d%H%M%S") + f" {PARIS_OFFSET_STR}"
    except Exception:
        return date_str

def main():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    print("Téléchargement du fichier pluto.xml global...")

    try:
        req = urllib.request.Request(PLUTO_XML_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            xml_data = resp.read()
    except Exception as e:
        print(f"Erreur de téléchargement : {e}")
        sys.exit(1)

    print("Extraction des programmes INA 70...")
    root = ET.fromstring(xml_data)

    tv = ET.Element('tv', {
        'generator-info-name': 'INA70-EPG-Generator',
        'source-info-name': 'Pluto TV FR'
    })

    # Recherche du canal
    for channel in root.findall('channel'):
        if channel.get('id') == TARGET_ID:
            channel.set('id', 'ina70.fr')
            tv.append(channel)
            break

    count = 0
    # Extraction des programmes
    for prog in root.findall('programme'):
        if prog.get('channel') == TARGET_ID:
            prog.set('channel', 'ina70.fr')
            
            # Conversion des heures vers le fuseau français
            start = prog.get('start')
            stop = prog.get('stop')
            if start: prog.set('start', convert_date(start))
            if stop: prog.set('stop', convert_date(stop))

            tv.append(prog)
            count += 1

    xml_out = ET.tostring(tv, encoding='utf-8')
    parsed = minidom.parseString(xml_out)
    pretty_xml = parsed.toprettyxml(indent="  ")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(pretty_xml)

    print(f"Succès : {count} programmes INA 70 extraits du XML Pluto.")

if __name__ == "__main__":
    main()
