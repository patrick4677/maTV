import re

# Chemin vers votre fichier M3U de Pluto TV local
m3u_file = "coulisses/pluto_fr.m3u" # Remplacez par votre chemin

target_channels = {}

with open(m3u_file, "r", encoding="utf-8") as f:
    content = f.read()

# Expression régulière pour capturer le nom de la chaîne et l'ID dans le M3U (selon le format standard Pluto)
# On recherche par exemple tvg-id ou l'ID dans l'URL du flux
entries = content.split("#EXTINF:")

for entry in entries:
    if not entry.strip():
        continue
        
    # Extraire le nom de la chaîne (après la dernière virgule de la ligne tvg)
    lines = entry.split("\n")
    meta_line = lines[0]
    
    # Recherche du nom de la chaîne (souvent à la fin après la virgule)
    name_match = re.search(r',(.+)$', meta_line)
    channel_name = name_match.group(1).strip() if name_match else "Inconnu"
    
    # Recherche de l'ID (souvent dans tvg-id="..." ou dans l'URL du flux un peu plus bas)
    id_match = re.search(r'tvg-id="([^"]+)"', meta_line)
    channel_id = None
    
    if id_match:
        channel_id = id_match.group(1)
    else:
        # Si pas de tvg-id, on cherche l'ID dans l'URL du flux (ex: .../channels/ID/...)
        for line in lines:
            url_match = re.search(r'/channels/([a-f0-9]{24})/', line)
            if url_match:
                channel_id = url_match.group(1)
                break
                
    if channel_id and channel_name:
        # Nettoyage optionnel du nom pour en faire un identifiant propre (ex: "ina70.fr")
        clean_key = channel_name.lower().replace(" ", "").replace("-", "") + ".fr"
        target_channels[channel_id] = clean_key

# Affichage du résultat formaté pour votre fichier de config
print("    \"target_channels\": {")
items = [f'        "{ch_id}": "{name}"' for ch_id, name in target_channels.items()]
print(",\n".join(items))
print("    }")