import requests, zipfile, io, os, sys

UPDATE_URL = "https://xvlivemanager.fr/updates/version.txt"
ZIP_URL    = "https://xvlivemanager.fr/updates/latest.zip"


IGNORED_FOLDERS = [
    "user_settings",
    "static/logos_partners",
    "static/logos_teams",
    "archives"
]

def get_local_version():
    try:
        with open("version.txt", "r") as f:
            return f.read().strip()
    except:
        return "0"

def get_remote_version():
    try:
        r = requests.get(UPDATE_URL, timeout=10)
        return r.text.strip()
    except:
        return None

def should_skip(member):
    for folder in IGNORED_FOLDERS:
        # Toujours normaliser en slash
        if member.filename.replace("\\", "/").startswith(folder + "/"):
            return True
    return False

def download_and_extract_zip():
    print("Téléchargement de la mise à jour...")
    r = requests.get(ZIP_URL, stream=True)
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        for member in z.infolist():
            if should_skip(member):
                print(f"→ Ignoré : {member.filename}")
                continue
            z.extract(member, os.getcwd())
    print("Mise à jour terminée !")

def main():
    local_ver = get_local_version()
    remote_ver = get_remote_version()
    if not remote_ver:
        print("Impossible de vérifier la version distante.")
        sys.exit(1)
    if local_ver == remote_ver:
        print("Aucune mise à jour disponible (version actuelle).")
        sys.exit(0)
    print(f"Mise à jour disponible : {remote_ver} (vous avez {local_ver})")
    download_and_extract_zip()
    with open("version.txt", "w") as f:
        f.write(remote_ver)

if __name__ == "__main__":
    main()
