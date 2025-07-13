import os
import sys
import hashlib
import json
import time
import locale
import shutil
import difflib
import re
import uuid
import base64
import importlib
import requests
import websocket
import json
import threading
import time
import os
import zipfile
import tempfile
from datetime import datetime, timedelta

from flask import (
    Flask,
    render_template,
    render_template_string,
    request,
    redirect,
    url_for,
    send_from_directory,
    jsonify,
    Response,
    abort
)
from werkzeug.utils import secure_filename
from bs4 import BeautifulSoup



import socket

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
ARCHIVES_DIR     = os.path.join(BASE_DIR, "archives")
HTML_OUT_DIR     = os.path.join(BASE_DIR, "html_out")
OBS_LAYOUTS_DIR  = os.path.join(BASE_DIR, "obs_layouts")
STATIC_DIR       = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR    = BASE_DIR
ADMIN_DATA       = os.path.join(BASE_DIR, "admin_data.json")
JSON_PATH        = ADMIN_DATA
BUTEURS_DATA     = os.path.join(BASE_DIR, "buteurs.json")
COMMENTAIRES     = os.path.join(BASE_DIR, "commentaires.json")
COMPOSITION      = os.path.join(BASE_DIR, "composition.json")
DATA_FILE        = os.path.join(BASE_DIR, "data.json")
EVTS_DATA        = os.path.join(BASE_DIR, "evenements.json")
OVERLAY_LAYOUT   = os.path.join(BASE_DIR, "overlay_layout.json")
REMPLACANTS      = os.path.join(BASE_DIR, "remplacants.json")
TERRAIN_AWAY     = os.path.join(BASE_DIR, "terrain_away.json")
TERRAIN_HOME     = os.path.join(BASE_DIR, "terrain_home.json")
TIMER_STATE      = os.path.join(BASE_DIR, "timer_state.json")
VERSION_FILE     = os.path.join(BASE_DIR, "version.json")
FORM_TEMPLATE    = os.path.join(BASE_DIR, "form_template.html")
USER_DIR         = os.path.join(BASE_DIR, "user")
USER_SETTINGS_DIR = os.path.join(BASE_DIR, "user_settings")
os.makedirs(USER_SETTINGS_DIR, exist_ok=True)
USER_SETTINGS_JSON = os.path.join(USER_SETTINGS_DIR, "settings.json")
HTML_OUTPUT_DIR  = HTML_OUT_DIR
TIMER_FILE       = TIMER_STATE
UPLOAD_FOLDER    = "obs_layouts"

os.makedirs(HTML_OUT_DIR, exist_ok=True)

app = Flask(
    __name__,
    template_folder=TEMPLATES_DIR,
    static_folder=STATIC_DIR
)
app.secret_key = "xvlivemanager"

from obsws_python import ReqClient

OBS_HOST     = "localhost"
OBS_PORT     = 4455
OBS_PASSWORD = "xvlivemanager"

OBS_SOURCES = [
    "layout-01",
    "layout-02",
    "layout-03",
    "layout-04"
]

OBS_LABELS = {
    "layout-01": "Avant-match",
    "layout-02": "Résumé 1re mi-temps",
    "layout-03": "Résumé du match",
    "layout-04": "Match en direct"
}

# NE PAS créer ws au global !

def get_ws_client():
    try:
        return ReqClient(host=OBS_HOST, port=OBS_PORT, password=OBS_PASSWORD)
    except Exception as e:
        print("[OBS] Connexion échouée :", e)
        return None

def obs_get_version():
    ws = get_ws_client()
    if ws is None:
        return False, "OBS WebSocket non connecté"
    try:
        v = ws.get_version()
        return True, v.obs_version
    except Exception as e:
        return False, str(e)

def obs_get_current_scene_name():
    ws = get_ws_client()
    if ws is None:
        return None, "OBS WebSocket non connecté"
    try:
        resp = ws.get_current_program_scene()
        return resp.scene_name, None
    except Exception as e:
        print("DEBUG: Exception in obs_get_current_scene_name:", e)
        return None, str(e)

def obs_get_scene_item_list(scene_name):
    ws = get_ws_client()
    if ws is None:
        return None, "OBS WebSocket non connecté"
    try:
        resp = ws.get_scene_item_list(scene_name)  # Argument positionnel !
        # On filtre les vrais sources, version CamelCase pour OBS Windows
        items = [
            item for item in resp.scene_items
            if isinstance(item, dict)
            and 'sourceName' in item and 'sceneItemEnabled' in item and 'sceneItemId' in item
        ]
        return items, None
    except Exception as e:
        return None, str(e)

def obs_set_scene_item_enabled(scene_name, source_name, visible):
    ws = get_ws_client()
    if ws is None:
        return False, "OBS WebSocket non connecté"
    try:
        items, err = obs_get_scene_item_list(scene_name)
        if err or items is None:
            return False, err
        for item in items:
            sname = item['sourceName']
            iid   = item['sceneItemId']
            if sname == source_name:
                ws.set_scene_item_enabled(scene_name, iid, visible)
                return True, None
        return False, "Item non trouvé"
    except Exception as e:
        return False, str(e)

def get_source_visibility(source_name, scene_name=""):
    scene_name, err = obs_get_current_scene_name()
    if err or not scene_name:
        print(f"[OBS] Impossible de déterminer la scène courante : {err}")
        return None
    items, err2 = obs_get_scene_item_list(scene_name)
    if err2 or items is None:
        print(f"[OBS] Impossible d’obtenir les scene items pour '{scene_name}' : {err2}")
        return None
    for item in items:
        sname = item['sourceName']
        enabled = item['sceneItemEnabled']
        if sname == source_name:
            return enabled
    print(f"[OBS] La source '{source_name}' n’existe pas dans la scène '{scene_name}'.")
    return None

def set_source_visibility(source_name, visible=True, scene_name=""):
    scene_name, err = obs_get_current_scene_name()
    if err or not scene_name:
        print(f"[OBS] Impossible de déterminer la scène courante pour set_source_visibility : {err}")
        return
    success, err2 = obs_set_scene_item_enabled(scene_name, source_name, visible)
    if not success:
        print(f"[OBS] Échec SetSceneItemEnabled : {err2}")

@app.route("/obs/ping", methods=["GET"])
def obs_ping():
    ok, version = obs_get_version()
    if not ok:
        return "Erreur de connexion OBS ou échec : " + str(version)
    return "Connexion OK ! Version OBS WebSocket : " + str(version)

@app.route("/obs/debug", methods=["GET"])
def obs_debug():
    scene_name, err = obs_get_current_scene_name()
    if err or not scene_name:
        return jsonify({"scene": "<inconnu>", "sources": []})
    items, err2 = obs_get_scene_item_list(scene_name)
    if err2 or items is None:
        return jsonify({"scene": scene_name, "sources": []})
    sources = []
    for item in items:
        sname = item['sourceName']
        enabled = item['sceneItemEnabled']
        sources.append({"name": sname, "enabled": enabled})
    return jsonify({"scene": scene_name, "sources": sources})

@app.route("/obs/interface", methods=["GET"])
def interface_obs():
    states = []
    for name in OBS_SOURCES:
        is_on = get_source_visibility(name)
        states.append((name, is_on))
    return jsonify({
        "states": [
            {
                "name":    source_name,
                "visible": is_on,
                "label":   OBS_LABELS.get(source_name, source_name)
            }
            for source_name, is_on in states
        ]
    })

@app.route("/obs/toggle/<source_name>", methods=["POST"])
def toggle_source(source_name):
    current = get_source_visibility(source_name)
    if current is not None:
        set_source_visibility(source_name, not current)
    return ("", 204)


def protect_placeholders(html):
    def repl(match):
        code = match.group(0)
        return f'<span class="placeholder" contenteditable="false" draggable="true" data-code="{code}">{code}</span>'
    return re.sub(r"\{.*?\}", repl, html)

def unprotect_placeholders(html):
    soup = BeautifulSoup(html, "html.parser")
    for span in soup.select("span.placeholder"):
        code = span.get("data-code", "")
        span.replace_with(code)
    return str(soup)

def extract_placeholders(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    placeholders = set()

    for tag in soup.find_all(True):
        if tag.name in ["style", "script"]:
            continue
        if tag.string:
            matches = re.findall(r"\{.*?\}", tag.string)
            placeholders.update(matches)
        elif tag.text:
            matches = re.findall(r"\{.*?\}", tag.text)
            placeholders.update(matches)

    return placeholders

def read_file_content(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            html = f.read()
            soup = BeautifulSoup(html, 'html.parser')
            container = soup.find('div', class_='container')
            if container:
                return container.get_text().strip()
    return ""

def read_json(filename):
    import os
    if not os.path.isabs(filename):
        path = os.path.join(BASE_DIR, filename)
    else:
        path = filename
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return {}

def write_json(filename, data):
    import os
    if not os.path.isabs(filename):
        path = os.path.join(BASE_DIR, filename)
    else:
        path = filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_data():
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}

    if "timer" not in data:
        data["timer"] = {
            "elapsed_seconds": 0,
            "running": False,
            "start_timestamp": None
        }
    return data

def save_data(data):
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_timer():
    if os.path.exists(TIMER_FILE):
        with open(TIMER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "start_time": None,
        "paused": False,
        "paused_at": None,
        "initial_minute": 0
    }

def save_timer(timer_data):
    with open(TIMER_FILE, "w", encoding="utf-8") as f:
        json.dump(timer_data, f)

def add_apostrophe_to_minute(entry):
    if not isinstance(entry, str):
        return entry
    parts = entry.split(" - ")
    if parts and len(parts[0]) <= 3 and (parts[0].isdigit() or "+" in parts[0]):
        parts[0] += "’"
    return " - ".join(parts)

def redirect_to_admin_with_anchor():
    anchor = request.args.get("anchor", "")
    return redirect(url_for("admin") + (f"#{anchor}" if anchor else ""))

def get_admin_version():
    admin_path = os.path.join(BASE_DIR, "admin.py")
    if os.path.exists(admin_path):
        mtime = os.path.getmtime(admin_path)
        version_str = time.strftime("Version %Y,%m%d%H%M", time.localtime(mtime))
        return version_str
    return "Version inconnue"

def get_available_players(data, remplacants):
    def update_available(joueurs, remplaçants, remplacements):
        sortants = set(joueurs + remplaçants)
        entrants = set()
        for remplacement in remplacements:
            try:
                _, action = remplacement.split(" - ")
                out, inn = action.split(" 🔁 ")
                if out in sortants:
                    sortants.discard(out)
                    entrants.add(out)
                if inn in remplaçants or inn in joueurs:
                    sortants.add(inn)
                    entrants.discard(inn)
            except:
                continue
        return {
            "sortants": sorted(sortants),
            "entrants": sorted(entrants)
        }

    home = update_available(
        data.get("compo_home", {}).get("joueurs", []),
        data.get("compo_home", {}).get("remplacants", []),
        remplacants.get("home", [])
    )
    away = update_available(
        data.get("compo_away", {}).get("joueurs", []),
        data.get("compo_away", {}).get("remplacants", []),
        remplacants.get("away", [])
    )
    return home, away

def get_remplacement_disponibles(compo_home, compo_away, remplacants):
    def analyse(joueurs, remplaçants, remps):
        sortis = []
        entres = []
        for ligne in remps:
            try:
                _, rest = ligne.split(" - ")
                out, in_ = rest.split(" 🔁 ")
                sortis.append(out.strip())
                entres.append(in_.strip())
            except:
                continue
        dispo_sortants = [j for j in joueurs if j and j not in sortis] + entres
        dispo_entrants = [r for r in remplaçants if r and r not in entres] + sortis
        return sorted(set(dispo_sortants)), sorted(set(dispo_entrants))

    dispo_out_home, dispo_in_home = analyse(compo_home["joueurs"], compo_home["remplacants"], remplacants.get("home", []))
    dispo_out_away, dispo_in_away = analyse(compo_away["joueurs"], compo_away["remplacants"], remplacants.get("away", []))

    return dispo_out_home, dispo_in_home, dispo_out_away, dispo_in_away

def get_disponibles(joueurs_initiaux, remplacants_initiaux, remplacements):
    titulaires = set(joueurs_initiaux)
    remplacants = set(remplacants_initiaux)
    sortis = set()
    entres = set()

    for remp in remplacements:
        try:
            _, action = remp.split(" - ")
            out, in_ = action.split(" 🔁 ")
            sortis.add(out.strip())
            entres.add(in_.strip())
        except:
            continue

    joueurs_disponibles = (titulaires | entres) - sortis
    remplacants_disponibles = (remplacants | sortis) - entres

    return sorted(joueurs_disponibles), sorted(remplacants_disponibles)

def generate_archive_resume():
    from markupsafe import escape
    from datetime import datetime
    import os
    import re

    os.makedirs(ARCHIVES_DIR, exist_ok=True)

    horodatage_affiche = datetime.now().strftime("%d/%m/%Y à %H:%M")
    horodatage_nom = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    date_obj = datetime.now()
    filename = f"match_{date_obj.day:02d}-{date_obj.month:02d}-{date_obj.year}_{date_obj.hour:02d}h{date_obj.minute:02d}.html"
    path = os.path.join(ARCHIVES_DIR, filename)

    data        = read_json(ADMIN_DATA)
    buteurs     = read_json(BUTEURS_DATA)
    evenements  = read_json(EVTS_DATA)
    remplacants = read_json(REMPLACANTS)

    home      = data.get("compo_home", {})
    away      = data.get("compo_away", {})
    arbitres  = data.get("arbitres", {})
    score     = data.get("score", {"home": "0", "away": "0"})

    def render_team_compo(side, team):
        out = f'<div class="team {side}">'
        out += f'<h3>{escape(team.get("nom", ""))}</h3>'
        out += f'<h4>Titulaires</h4>'
        for j in team.get("joueurs", []):
            out += f'<p>{escape(j)}</p>'
        if team.get("remplacants"):
            out += f'<h4>Remplaçants</h4>'
            for r in team.get("remplacants", []):
                out += f'<p>{escape(r)}</p>'
        out += '</div>'
        return out

    compo_html = "".join([
        render_team_compo("home", home),
        render_team_compo("away", away)
    ])

    def render_buteurs(side, blist):
        # Mapping inclus dans la fonction
        def clean_but_label(label):
            mapping = [
                ("Essai", "Essai"),
                ("🏉", "Essai"),
                ("Transfo", "Transformation"),
                ("🎯", "Transformation"),
                ("Drop", "Drop"),
                ("🦶", "Drop"),
                ("Pénalité", "Pénalité"),
                ("Penalty", "Pénalité"),
            ]
            for key, val in mapping:
                if key in label:
                    return val
            return re.sub(r'[^\w\s-]', '', label).strip()
        team_name = home.get("nom") if side == "home" else away.get("nom")
        out = f'<div class="team {side}">'
        out += f'<h3>{escape(team_name)}</h3>'
        for b in blist:
            if isinstance(b, str):
                parts = [x.strip() for x in b.split(" - ")]
                minute = parts[0] if len(parts) > 0 else ""
                joueur = parts[1] if len(parts) > 1 else ""
                action = parts[2] if len(parts) > 2 else ""
            elif isinstance(b, dict):
                minute = b.get("minute", "")
                joueur = b.get("joueur", "")
                action = b.get("action", "")
            else:
                minute = joueur = action = ""
            action_affiche = clean_but_label(action)
            out += f"<p>{escape(str(minute))}’ {escape(joueur)}, {escape(action_affiche)}</p>"
        out += '</div>'
        return out

    buteurs_html = "".join([
        render_buteurs("home", buteurs.get("home", [])),
        render_buteurs("away", buteurs.get("away", [])),
    ])

    def render_evenements(side, elist):
        # Mapping inclus dans la fonction
        def clean_evt_label(label):
            mapping = [
                ("🟨", "Carton jaune"),
                ("🟥", "Carton rouge"),
                ("Carton jaune", "Carton jaune"),
                ("Carton rouge", "Carton rouge"),
                ("Blessure", "Blessure"),
                ("🚑", "Blessure"),
                ("Remplacement", "Remplacement"),
                ("🔁", "Remplacement"),
            ]
            for key, val in mapping:
                if key in label:
                    return val
            return re.sub(r'[^\w\s-]', '', label).strip()
        team_name = home.get("nom") if side == "home" else away.get("nom")
        out = f'<div class="team {side}">'
        out += f'<h3>{escape(team_name)}</h3>'
        for ev in elist:
            if isinstance(ev, str):
                parts = [x.strip() for x in ev.split(" - ")]
                minute = parts[0] if len(parts) > 0 else ""
                joueur = parts[1] if len(parts) > 1 else ""
                action = parts[2] if len(parts) > 2 else ""
            elif isinstance(ev, dict):
                minute = ev.get("minute", "")
                joueur = ev.get("joueur", "")
                action = ev.get("action", "")
            else:
                minute = joueur = action = ""
            action_affiche = clean_evt_label(action)
            out += f"<p>{escape(str(minute))}’ {escape(joueur)}, {escape(action_affiche)}</p>"
        out += '</div>'
        return out

    evenements_html = "".join([
        render_evenements("home", evenements.get("home", [])),
        render_evenements("away", evenements.get("away", [])),
    ])

    def render_remplacements(side, rlist):
        team_name = home.get("nom") if side == "home" else away.get("nom")
        out = f'<div class="team {side}">'
        out += f'<h3>{escape(team_name)}</h3>'
        for r in rlist:
            if isinstance(r, str):
                match = re.match(r"^(\d+)'?\s+(.+)\s+🔁\s+(.+)$", r)
                if match:
                    minute, out_player, in_player = match.groups()
                else:
                    parts = r.replace("'", "").split(" ")
                    minute = parts[0] if len(parts) > 0 else ""
                    try:
                        idx = parts.index("🔁")
                        out_player = " ".join(parts[1:idx])
                        in_player = " ".join(parts[idx+1:])
                    except ValueError:
                        out_player = in_player = ""
            elif isinstance(r, dict):
                minute = r.get("minute", "")
                out_player = r.get("out", "")
                in_player = r.get("in", "")
            else:
                minute = out_player = in_player = ""
            out += f"<p>{escape(str(minute))}’ {escape(out_player)} S/E {escape(in_player)}</p>"
        out += '</div>'
        return out

    remplacants_html = "".join([
        render_remplacements("home", remplacants.get("home", [])),
        render_remplacements("away", remplacants.get("away", [])),
    ])

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Résumé du match — {horodatage_affiche}</title>
  <style>
    html, body {{
      margin: 0; padding: 0;
      font-family: 'Segoe UI', Arial, sans-serif;
      background: #f8f9fa; color: #212529;
    }}
    .container {{
      max-width: 900px;
      margin: 36px auto;
      background: #fff;
      border-radius: 14px;
      box-shadow: 0 3px 28px rgba(0,0,0,0.08);
      padding: 38px 42px;
    }}
    header {{
      display: grid;
      grid-template-areas:
        "button ."
        "title  title"
        "stamp  stamp";
      grid-template-columns: auto 1fr;
      row-gap: 0.5em;
      margin-bottom: 1em;
    }}
    .btn-link {{
      grid-area: button;
      justify-self: end;
      background: none; border: none;
      color: #1656b6; text-decoration: underline;
      cursor: pointer; font-size: 1em;
      padding: 0; margin: 0;
    }}
    header h1 {{
      grid-area: title;
      font-size: 2.7em; margin: 0;
      text-align: center; color: #1656b6;
      font-weight: 700;
    }}
    .timestamp {{
      grid-area: stamp;
      text-align: center; font-size: 1em;
      color: #555;
    }}

    h2 {{
      font-size: 1.5em; margin-top: 2em; margin-bottom: 0.5em;
      border-left: 6px solid #1656b6; padding-left: 13px;
      background: #f6faff; color: #1656b6;
      font-weight: 700; text-align: left;
    }}
    h3 {{
      color: #22314a; margin: 0.6em 0;
      font-size: 1.3em; font-weight: 600;
      text-align: center;
    }}
    h4 {{
      margin: 0.5em 0 0.3em;
      font-size: 1.1em; font-weight: 600;
      text-align: center;
    }}
    p {{
      margin: 0.2em 0; font-size: 1.03em;
    }}

    .teams-grid, .info-grid {{
      position: relative;
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 24px; margin-top: 1em;
    }}
    .teams-grid::before, .info-grid::before {{
      content: "";
      position: absolute;
      top: 0; bottom: 0;
      left: 50%; width: 1px;
      background-color: #dee2e6;
      pointer-events: none;
    }}
    .team, .info-item {{
      padding: 0 1.5rem; margin: 0;
    }}

    .final-score {{
      margin-top: 2rem;
    }}
    .score-grid {{
      display: flex; width: 100%;
      justify-content: center; align-items: center;
      gap: 2rem;
    }}
    .team-score {{
      display: flex; flex-direction: column;
      align-items: center;
    }}
    .score-number {{
      font-size: 3rem; font-weight: 700;
      color: #1656b6; margin: 0.2em 0;
    }}
    .separator {{
      font-size: 2rem; color: #212529;
    }}

    .footer {{
      text-align: center; color: #777;
      font-size: 0.97em; margin-top: 3em;
    }}

    @media print {{
      body {{ background: #fff; }}
      .container {{ box-shadow: none; border-radius: 0; padding: 0; margin: 0; }}
      header h1, .timestamp {{ color: #000 !important; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <button class="btn-link" onclick="window.print()">Imprimer / PDF</button>
      <h1>Résumé du match</h1>
      <div class="timestamp">Généré automatiquement le {horodatage_affiche}</div>
    </header>

    <section class="final-score">
      <h2>Score final</h2>
      <div class="score-grid">
        <div class="team-score">
          <h3>{escape(home.get('nom','Équipe Domicile'))}</h3>
          <div class="score-number">{escape(str(score.get('home','0')))}</div>
        </div>
        <div class="separator"> </div>
        <div class="team-score">
          <h3>{escape(away.get('nom','Équipe Extérieure'))}</h3>
          <div class="score-number">{escape(str(score.get('away','0')))}</div>
        </div>
      </div>
    </section>

    <section>
      <h2>Composition des équipes</h2>
      <div class="teams-grid">
        {compo_html}
      </div>
    </section>

    <section>
      <h2>Buteurs</h2>
      <div class="teams-grid">
        {buteurs_html}
      </div>
    </section>

    <section>
      <h2>Événements</h2>
      <div class="teams-grid">
        {evenements_html}
      </div>
    </section>

    <section>
      <h2>Remplacements</h2>
      <div class="teams-grid">
        {remplacants_html}
      </div>
    </section>

    <section>
      <h2>Informations du match</h2>
      <div class="info-grid">
        <div class="info-item">
          <h3>Détails</h3>
          <p><strong>Date :</strong> {escape(data.get('date',''))} à {escape(data.get('heure',''))}</p>
          <p><strong>Lieu :</strong> {escape(data.get('ville',''))}, {escape(data.get('stade',''))}</p>
        </div>
        <div class="info-item">
          <h3>Arbitres</h3>
          <p><strong>Central :</strong> {escape(arbitres.get('central',''))}</p>
          <p><strong>Touche 1 :</strong> {escape(arbitres.get('touche_1',''))}</p>
          <p><strong>Touche 2 :</strong> {escape(arbitres.get('touche_2',''))}</p>
          <p><strong>Vidéo :</strong> {escape(arbitres.get('video',''))}</p>
        </div>
      </div>
    </section>

    <footer class="footer">
      Généré avec XVLIVEMANAGER
    </footer>
  </div>
</body>
</html>
"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    return path

@app.route('/changelog')
def changelog_route():
    
    generate_changelog()
    return send_from_directory(os.path.dirname(__file__), 'changelog.html')

@app.route('/guide')
def guide():
    return send_from_directory(os.path.dirname(__file__), 'guide.html')

@app.route('/user/<path:filename>')
def serve_user_file(filename):
    return send_from_directory(USER_DIR, filename)

@app.route("/")
def admin():
    data = load_data()
    data["version_note"] = get_admin_version()


    data["logo_home"] = data.get("logo_home", "")
    data["logo_away"] = data.get("logo_away", "")

    data.setdefault("arbitres", {
        "central": "", "touche_1": "", "touche_2": "", "video": ""
    })

    data.setdefault("compo_home", {"nom": "", "joueurs": [], "remplacants": []})
    data.setdefault("compo_away", {"nom": "", "joueurs": [], "remplacants": []})

    data["compo_home"].setdefault("remplacants", [])
    data["compo_away"].setdefault("remplacants", [])

    def joueurs_disponibles(joueurs, remplacants):
        tous = list(dict.fromkeys(joueurs + remplacants))
        return tous, tous

    data["dispo_out_home"], data["dispo_in_home"] = joueurs_disponibles(
        data["compo_home"]["joueurs"],
        data["compo_home"]["remplacants"]
    )
    data["dispo_out_away"], data["dispo_in_away"] = joueurs_disponibles(
        data["compo_away"]["joueurs"],
        data["compo_away"]["remplacants"]
    )

    data["timestamp"] = int(time.time())

    data["local_ip"] = get_local_ip()

    data["select_players_home"] = sorted(set(
        data["compo_home"]["joueurs"] + data["compo_home"]["remplacants"]
    ))
    data["select_players_away"] = sorted(set(
        data["compo_away"]["joueurs"] + data["compo_away"]["remplacants"]
    ))

    timer_state     = load_timer()
    is_timer_paused = timer_state.get("paused", False)

    template = open(os.path.join(os.path.dirname(__file__), "form_template.html"), encoding="utf-8").read()

    print("DEBUG compo_home.remplacants:", data["compo_home"]["remplacants"])
    print("DEBUG compo_away.remplacants:", data["compo_away"]["remplacants"])

    return render_template_string(template, **data, is_timer_paused=is_timer_paused)

@app.route("/update_infos_match", methods=["POST"])
def update_infos_match():

    data = load_data()

    
    data["competition"] = request.form.get("competition", "")
    data["date"]        = request.form.get("date", "")
    data["heure"]       = request.form.get("heure", "")
    data["ville"]       = request.form.get("ville", "")
    data["stade"]       = request.form.get("stade", "")
    data["arbitres"]    = {
        "central":  request.form.get("arbitre_central",  "").strip(),
        "touche_1": request.form.get("arbitre_touche_1", "").strip(),
        "touche_2": request.form.get("arbitre_touche_2", "").strip(),
        "video":    request.form.get("arbitre_video",   "").strip()
    }

    save_data(data)

    try:
        locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, '')
    raw_date = data["date"].strip()
    formatted_date = raw_date
    try:
        if "-" in raw_date:
            d = datetime.strptime(raw_date, "%Y-%m-%d")
        elif "/" in raw_date:
            d = datetime.strptime(raw_date, "%d/%m/%Y")
        else:
            d = None
        if d:
            formatted_date = d.strftime("%A %d %B %Y")
    except ValueError:
        pass

    role_labels = {
        'central':  'Arbitre central',
        'touche':   'Juge de touche',
        'video':    'Arbitre vidéo'
    }

    central = data["arbitres"].get("central")
    touches = [
        data["arbitres"].get("touche_1"),
        data["arbitres"].get("touche_2")
    ]
    video = data["arbitres"].get("video")

    
    try:
        html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <title>Infos Match</title>
  <link rel="stylesheet" href="/static/css/infos_match.css">
</head>
<body>
  <section>
    <h2>Informations du Match</h2>
    <div class="info-block"><span class="info-label">Compétition :</span> {data.get('competition')}</div>
    <div class="info-block"><span class="info-label">Date :</span> {formatted_date}</div>
    <div class="info-block"><span class="info-label">Heure :</span> {data.get('heure')}</div>
    <div class="info-block"><span class="info-label">Ville :</span> {data.get('ville')}</div>
    <div class="info-block"><span class="info-label">Stade :</span> {data.get('stade')}</div>
  </section>

  <section>
    <h2>Arbitres de la Rencontre</h2>

    {f"<div class='info-block central'><span class='info-label'>{role_labels['central']} :</span> {central}</div>" if central else ''}


    {''.join(
        f"<div class='info-block touche'><span class='info-label'>{role_labels['touche']} {i+1} :</span> {name}</div>"
        for i, name in enumerate(touches) if name
    )}


    {f"<div class='info-block video'><span class='info-label'>{role_labels['video']} :</span> {video}</div>" if video else ''}
  </section>
</body>
</html>"""
        
        os.makedirs(HTML_OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(HTML_OUTPUT_DIR, "infos_match.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
    except Exception as e:
        print(f"[ERREUR génération infos_match.html] {e}")

    return redirect(url_for("admin") + "#infos")

@app.route("/update_equipes", methods=["POST"])
def update_equipes():
    data = load_data()

    postes = [
        "1 - Pilier gauche", "2 - Talonneur", "3 - Pilier droit",
        "4 - Deuxième ligne", "5 - Deuxième ligne",
        "6 - 3e ligne aile (fermé)", "7 - 3e ligne aile (ouvert)", "8 - Numéro 8",
        "9 - Demi de mêlée", "10 - Demi d'ouverture",
        "11 - Ailier gauche", "12 - Premier centre", "13 - Deuxième centre",
        "14 - Ailier droit", "15 - Arrière"
    ]

    joueurs_home = [request.form.get(f"poste_home_{i}", "").upper() for i in range(1, 16)]
    joueurs_away = [request.form.get(f"poste_away_{i}", "").upper() for i in range(1, 16)]
    remplaçants_home = [request.form.get(f"remplaçant_home_{i}", "").upper() for i in range(1, 9)]
    remplaçants_away = [request.form.get(f"remplaçant_away_{i}", "").upper() for i in range(1, 9)]

    data["compo_home"] = {
        "nom": request.form.get("nom_home", "").upper(),
        "joueurs": joueurs_home,
        "remplacants": remplaçants_home
    }

    data["compo_away"] = {
        "nom": request.form.get("nom_away", "").upper(),
        "joueurs": joueurs_away,
        "remplacants": remplaçants_away
    }

    file_home = request.files.get("logo_home")
    if file_home and file_home.filename:
        logos_teams_dir = os.path.join(STATIC_DIR, "logos_teams")
        os.makedirs(logos_teams_dir, exist_ok=True)
        filename = secure_filename("logo_home.png")
        path = os.path.join(logos_teams_dir, filename)
        file_home.save(path)
        data["logo_home"] = path

    file_away = request.files.get("logo_away")
    if file_away and file_away.filename:
        logos_teams_dir = os.path.join(STATIC_DIR, "logos_teams")
        os.makedirs(logos_teams_dir, exist_ok=True)
        filename = secure_filename("logo_away.png")
        path = os.path.join(logos_teams_dir, filename)
        file_away.save(path)
        data["logo_away"] = path

    save_data(data)

    return redirect(url_for("admin") + "#compos")

from werkzeug.utils import secure_filename

@app.route("/update_overlay", methods=["POST"])
def update_overlay():
    data = load_data()
    data["overlay"] = data.get("overlay", {})

    
    data["overlay"]["last_matches"] = []
    for i in range(1, 4):
        match = {
            "date":     request.form.get(f"match_date_{i}", ""),
            "stade":    request.form.get(f"match_stadium_{i}", ""),
            "opponent": request.form.get(f"match_opponent_{i}", ""),
            "score":    request.form.get(f"match_score_{i}", ""),
            "winner":   request.form.get(f"match_winner_{i}", "")
        }
        data["overlay"]["last_matches"].append(match)

    
    old_logos = data["overlay"].get("logos", [None]*6)
    new_logos = []
    upload_dir = os.path.join(STATIC_DIR, "logos_partners")
    os.makedirs(upload_dir, exist_ok=True)

    for i in range(1, 7):
        remove_flag = request.form.get(f"remove_logo_partenaire_{i}", "0")
        file_field  = request.files.get(f"logo_partenaire_{i}")
        filename    = f"logo_partenaire_{i}.png"
        filepath    = os.path.join(upload_dir, filename)

        if remove_flag == "1":

            new_logos.append(None)

            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except OSError:
                pass

        elif file_field and file_field.filename:

            safe_name = secure_filename(file_field.filename)

            _, ext = os.path.splitext(safe_name)
            dest = os.path.splitext(filename)[0] + ext
            full_path = os.path.join(upload_dir, dest)
            file_field.save(full_path)
            new_logos.append(f"/static/logos_partners/{dest}")

        else:

            new_logos.append(old_logos[i-1] if i-1 < len(old_logos) else None)

    data["overlay"]["logos"] = new_logos

    
    data["overlay"]["message"] = request.form.get("scrolling_message", "")

    
    data["overlay"]["countdown"] = {
        "message":  request.form.get("overlay_message", ""),
        "duration": request.form.get("overlay_duration", "5")
    }

    save_data(data)



    last_matches = data["overlay"]["last_matches"]
    with open(os.path.join(HTML_OUTPUT_DIR, "last_matches.html"), "w", encoding="utf-8") as f:
        f.write("""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="300">
  <title>Derniers matchs</title>
  <link rel="stylesheet" href="static/css/last_matches.css">
</head>
<body>
  <div class="container">
        <h2 class="matches-title">Informations des 3 derniers matchs</h2>
""")
        for match in last_matches:
            f.write(f"""\
        <div class="match">
            <div><strong>Date :</strong> <span>{match['date']}</span></div>
            <div><strong>Stade :</strong> <span>{match['stade']}</span></div>
            <div><strong>Adversaire :</strong> <span>{match['opponent']}</span></div>
            <div><strong>Score :</strong> <span>{match['score']}</span></div>
            <div><strong>Vainqueur :</strong> <span>{match['winner']}</span></div>
        </div>

""")
        f.write("""    </div>
</body>
</html>
""")

    
    message = data["overlay"]["message"]
    with open(os.path.join(HTML_OUTPUT_DIR, "obs_message.html"), "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="300">
  <title>Message OBS</title>
  <link rel="stylesheet" href="/static/css/obs_message.css">
</head>
<body>
  <div id="message">{message}</div>
</body>
</html>""")

    
    countdown      = data["overlay"]["countdown"]
    message        = countdown.get("message", "")
    total_seconds  = int(countdown.get("duration", 0)) * 60

    with open(os.path.join(HTML_OUTPUT_DIR, "overlay_countdown.html"), "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="300">
  <title>Compte à rebours</title>
  <link rel="stylesheet" href="/static/css/overlay_countdown.css">
</head>
<body>
  <div id="message">{message}</div>
  <div id="countdown"></div>
  <script>
    let remaining = {total_seconds};
    const el = document.getElementById("countdown");
    function pad(n) {{ return n.toString().padStart(2, "0"); }}
    function update() {{
      const m = Math.floor(remaining / 60);
      const s = remaining % 60;
      el.textContent = `${{pad(m)}}:${{pad(s)}}`;
      if (remaining <= 0) clearInterval(timer);
      else remaining--;
    }}
    update();
    const timer = setInterval(update, 1000);
  </script>
</body>
</html>""")

    
    logos = data["overlay"]["logos"]
    os.makedirs(HTML_OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(HTML_OUTPUT_DIR, "logos_partners.html"), "w", encoding="utf-8") as f:
        f.write("""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="300">
  <title>Partenaires</title>
  <link rel="stylesheet" href="/static/css/logos_partners.css">
</head>
<body>
  <h2 class="title">Logos partenaires</h2>
  <div class="logos-grid">
""")
        for logo_url in logos:
            if logo_url:
                f.write(f'    <div class="logo-item"><img src="{logo_url}" alt="Logo partenaire"></div>\n')
        f.write("""  </div>
</body>
</html>
""")

    
    return redirect_to_admin_with_anchor()

BUT_TYPES = [
    "Essai 🏉", "Transfo 🎯", "Drop 🦶", "Pénalité 🎯"
]

EVT_TYPES = [
    "Carton (🟨)", "Carton (🟥)", "Blessure (🚑)"
]

@app.route("/update_score", methods=["POST"])
def update_score():
    data = load_data()

    data["score"] = {
        "home": request.form.get("score_home", "0"),
        "away": request.form.get("score_away", "0")
    }

    save_data(data)

    
    with open(os.path.join(HTML_OUTPUT_DIR, "score.html"), "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="5">
  <title>Score en direct</title>
  <link rel="stylesheet" href="/static/css/score.css">
</head>
<body>

<h2>Score en direct</h2>
<div class="columns">
    <div class="col">
        <h3>Équipe domicile</h3>
        <div class="score">{data["score"]["home"]}</div>
    </div>
    <div class="col">
        <h3>Équipe extérieure</h3>
        <div class="score">{data["score"]["away"]}</div>
    </div>
</div>

</body>
</html>""")

    return redirect(url_for("admin") + "#score")

@app.route("/score.html")
def show_score():
    return send_from_directory(os.path.join(BASE_DIR, "html_out"), "score.html")

@app.route("/update_score_js", methods=["POST"])
def update_score_js():
    data = load_data()
    if "score" not in data:
        data["score"] = {"home": 0, "away": 0}

    payload = request.get_json()
    team = payload.get("team")
    amount = int(payload.get("amount", 0))

    if team in ["home", "away"]:
        data["score"][team] = max(0, data["score"][team] + amount)

    save_data(data)
    return jsonify(data["score"])

@app.route("/update_buteurs", methods=["POST"])
def update_buteurs():
    try:
        with open(BUTEURS_DATA, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {"home": [], "away": []}


    minute = request.form.get("buteur_minute_home")
    joueur = request.form.get("buteur_joueur_home")
    type_but = request.form.get("buteur_type_home")
    # Vérifier la validité du type
    if minute and joueur and type_but and type_but in BUT_TYPES:
        new_entry = f"{minute} - {joueur} - {type_but}"
        if new_entry not in data["home"]:
            data["home"].append(new_entry)


    minute = request.form.get("buteur_minute_away")
    joueur = request.form.get("buteur_joueur_away")
    type_but = request.form.get("buteur_type_away")
    if minute and joueur and type_but and type_but in BUT_TYPES:
        new_entry = f"{minute} - {joueur} - {type_but}"
        if new_entry not in data["away"]:
            data["away"].append(new_entry)


    data["home"] = list(dict.fromkeys(data["home"]))
    data["away"] = list(dict.fromkeys(data["away"]))

    with open(BUTEURS_DATA, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    generate_buteurs_html()
    return redirect(url_for("admin") + "#buteurs")

@app.route("/buteurs.html")
def show_buteurs():
    return send_from_directory(os.path.join(BASE_DIR, "html_out"), "buteurs.html")

@app.route("/delete_buteur/<team>/<int:index>", methods=["POST"])
def delete_buteur(team, index):
    with open(BUTEURS_DATA, "r", encoding="utf-8") as f:
        data = json.load(f)
    if team in data and 0 <= index < len(data[team]):
        del data[team][index]
        with open(BUTEURS_DATA, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        generate_buteurs_html()
    return "", 204

@app.route("/update_evenements", methods=["POST"])
def update_evenements():
    anchor = request.args.get("anchor", "evenements")

    data = {"home": [], "away": []}
    if os.path.exists(EVTS_DATA):
        with open(EVTS_DATA, "r", encoding="utf-8") as f:
            data = json.load(f)


    minute = request.form.get("event_minute_home")
    joueur = request.form.get("event_player_home")
    action = request.form.get("event_action_home")
    if minute and joueur and action and action in EVT_TYPES:
        new_entry = f"{minute} - {joueur} - {action}"
        if new_entry not in data["home"]:
            data["home"].append(new_entry)


    minute = request.form.get("event_minute_away")
    joueur = request.form.get("event_player_away")
    action = request.form.get("event_action_away")
    if minute and joueur and action and action in EVT_TYPES:
        new_entry = f"{minute} - {joueur} - {action}"
        if new_entry not in data["away"]:
            data["away"].append(new_entry)


    data["home"] = list(dict.fromkeys(data["home"]))
    data["away"] = list(dict.fromkeys(data["away"]))

    with open(EVTS_DATA, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    generate_evenements_html()
    return redirect(url_for("admin") + f"#{anchor}")

@app.route("/evenements.html")
def show_evenements():
    generate_evenements_html()
    return send_from_directory(os.path.join(BASE_DIR, "html_out"), "evenements.html")

@app.route("/delete_event/<team>/<int:index>", methods=["POST"])
def delete_event(team, index):
    with open(EVTS_DATA, "r", encoding="utf-8") as f:
        data = json.load(f)
    if team in data and 0 <= index < len(data[team]):
        del data[team][index]
        with open(EVTS_DATA, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        generate_evenements_html()
    return "", 204

@app.route("/update_remplacants", methods=["POST"])
def update_remplacants():
    data  = read_json(ADMIN_DATA)
    histor= read_json(REMPLACANTS)  

    data.setdefault("compo_home",   {"joueurs": [], "remplacants": []})
    data.setdefault("compo_away",   {"joueurs": [], "remplacants": []})
    histor.setdefault("home", [])
    histor.setdefault("away", [])

    def do_swap(team):
        m   = request.form.get(f"remp_min_{team}", "").strip()
        out = request.form.get(f"remp_out_{team}", "").strip()
        inn = request.form.get(f"remp_in_{team}",  "").strip()
        if not (m and out and inn):
            return

        joueurs = data[f"compo_{team}"]["joueurs"]
        remplacants = data[f"compo_{team}"]["remplacants"]

        if out in joueurs:
            joueurs.remove(out)
            remplacants.append(out)
        if inn in remplacants:
            remplacants.remove(inn)
            joueurs.append(inn)

        entry = f"{m}' {out} 🔁 {inn}"
        if entry not in histor[team]:
            histor[team].append(entry)

    do_swap("home")
    do_swap("away")

    histor["home"] = list(dict.fromkeys(histor["home"]))
    histor["away"] = list(dict.fromkeys(histor["away"]))

    write_json(ADMIN_DATA, data)      
    write_json(REMPLACANTS, histor)

    with open(os.path.join(HTML_OUT_DIR, "remplacants.html"), "w", encoding="utf-8") as f:
        f.write(generate_remplacants_html(histor))

    return redirect(url_for("admin") + "#rotation")

@app.route("/remplacants.html")
def show_remplacants():
    remplacants = read_json(REMPLACANTS)
    with open(os.path.join(HTML_OUTPUT_DIR, "remplacants.html"), "w", encoding="utf-8") as f:
        f.write(generate_remplacants_html(remplacants))
    return send_from_directory(os.path.join(BASE_DIR, "html_out"), "remplacants.html")

@app.route("/delete_remplacant/<team>/<int:index>", methods=["POST"])
def delete_remplacant(team, index):
    remplacants = read_json(REMPLACANTS)
    if team in remplacants and 0 <= index < len(remplacants[team]):
        del remplacants[team][index]
        write_json(REMPLACANTS, remplacants)
        with open(os.path.join(HTML_OUTPUT_DIR, "remplacants.html"), "w", encoding="utf-8") as f:
            f.write(generate_remplacants_html(remplacants))
    return "", 204

@app.route("/update_timer", methods=["POST"])
def update_timer():
    timer = load_timer()
    action = request.form.get("action")

    if action == "start":
        try:
            initial_minute = int(request.form.get("start_minute", "0"))
        except (TypeError, ValueError):
            initial_minute = 0

        timer["start_time"] = time.time()
        timer["initial_minute"] = initial_minute
        timer["paused"] = False
        timer["paused_at"] = None

    elif action == "pause":
        if timer.get("paused"):
            
            paused_duration = time.time() - timer["paused_at"]
            timer["start_time"] += paused_duration
            timer["paused"] = False
            timer["paused_at"] = None
        else:
            
            timer["paused"] = True
            timer["paused_at"] = time.time()

    elif action == "stop":
        timer = {
            "start_time": None,
            "paused": False,
            "paused_at": None,
            "initial_minute": 0
        }

    elif action == "reset":
        timer["start_time"] = time.time()
        timer["paused"] = False
        timer["paused_at"] = None
        timer["initial_minute"] = 0

    save_timer(timer)
    return redirect(url_for("admin") + "#timer")

@app.route("/timer")
def timer_page():
    timer = load_timer()

    offset = timer.get("offset", 0)
    initial_minute = timer.get("initial_minute", 0)

    if timer["start_time"] and not timer["paused"]:
        elapsed = time.time() - timer["start_time"]
    elif timer["paused"] and timer["paused_at"]:
        elapsed = timer["paused_at"] - timer["start_time"]
    else:
        elapsed = 0

    total_seconds = int(elapsed + offset + initial_minute * 60)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    display = f"{minutes:02d}:{seconds:02d}"

    timer["display"] = display

    return render_template_string(
        open(os.path.join(HTML_OUTPUT_DIR, "timer.html"), encoding="utf-8").read(),
        timer=timer
    )

@app.route("/timer.html")
def show_timer():
    return send_from_directory(os.path.join(BASE_DIR, "html_out"), "timer.html")

@app.route("/save_positions", methods=["POST"])
def save_positions():
    data = request.get_json()
    if not data:
        return "", 400

    write_json(TERRAIN_HOME, data.get("terrain_home", []))
    write_json(TERRAIN_AWAY, data.get("terrain_away", []))

    return "", 204

@app.route("/delete_logo/<int:index>", methods=["POST"])
def delete_logo(index):
    data = load_data()
    if "overlay" in data and "logos" in data["overlay"]:
        if 0 <= index < len(data["overlay"]["logos"]):
            logo_path = data["overlay"]["logos"][index]
            logo_full_path = os.path.join(BASE_DIR, logo_path.lstrip("/"))
            if os.path.exists(logo_full_path):
                os.remove(logo_full_path)
            del data["overlay"]["logos"][index]
            save_data(data)
    return redirect(url_for("admin") + "#overlay")

@app.route("/delete_logo_home", methods=["POST"])
def delete_logo_home():
    data = load_data()
    if "logo_home" in data and data["logo_home"]:
        try:
            logo_path = os.path.join(BASE_DIR, data["logo_home"].lstrip("/"))
            if os.path.exists(logo_path):
                os.remove(logo_path)
        except Exception as e:
            print(f"Erreur suppression logo_home : {e}")
        data["logo_home"] = ""
        save_data(data)
    return redirect(url_for("admin") + "#compos")

@app.route("/delete_logo_away", methods=["POST"])
def delete_logo_away():
    data = load_data()
    if "logo_away" in data and data["logo_away"]:
        try:
            logo_path = os.path.join(BASE_DIR, data["logo_away"].lstrip("/"))
            if os.path.exists(logo_path):
                os.remove(logo_path)
        except Exception as e:
            print(f"Erreur suppression logo_away : {e}")
        data["logo_away"] = ""
        save_data(data)
    return redirect(url_for("admin") + "#compos")

@app.route("/terrain")
def terrain():
    data = load_data()

    terrain_home = read_json(TERRAIN_HOME)
    terrain_away = read_json(TERRAIN_AWAY)
    remplacants = read_json(REMPLACANTS)

    if not terrain_home:
        terrain_home = []
        for i, nom in enumerate(data.get("compo_home", {}).get("joueurs", [])):
            if nom.strip():
                terrain_home.append({
                    "nom": nom.strip(),
                    "x": 10 + (i % 5) * 18,
                    "y": 70 + (i // 5) * 8
                })
        write_json(TERRAIN_HOME, terrain_home)

    if not terrain_away:
        terrain_away = []
        for i, nom in enumerate(data.get("compo_away", {}).get("joueurs", [])):
            if nom.strip():
                terrain_away.append({
                    "nom": nom.strip(),
                    "x": 10 + (i % 5) * 18,
                    "y": 10 + (i // 5) * 8
                })
        write_json(TERRAIN_AWAY, terrain_away)

    with open(os.path.join(HTML_OUTPUT_DIR, "terrain_template.html"), encoding="utf-8") as f:
        template = f.read()

    return render_template_string(template,
                                  terrain_home=terrain_home,
                                  terrain_away=terrain_away,
                                  arrows=[],
                                  noms_entres=[])

@app.route("/regen_terrain_manuel", methods=["GET", "POST"])
def regen_terrain_manuel():
    data = load_data()

    formation = [
        {"poste": 1, "x": 20, "y_home": 80, "y_away": 20},
        {"poste": 2, "x": 40, "y_home": 80, "y_away": 20},
        {"poste": 3, "x": 60, "y_home": 80, "y_away": 20},
        {"poste": 4, "x": 30, "y_home": 75, "y_away": 25},
        {"poste": 5, "x": 50, "y_home": 75, "y_away": 25},
        {"poste": 6, "x": 15, "y_home": 70, "y_away": 30},
        {"poste": 7, "x": 65, "y_home": 70, "y_away": 30},
        {"poste": 8, "x": 40, "y_home": 70, "y_away": 30},
        {"poste": 9, "x": 50, "y_home": 65, "y_away": 35},
        {"poste": 10, "x": 30, "y_home": 65, "y_away": 35},
        {"poste": 11, "x": 10, "y_home": 60, "y_away": 40},
        {"poste": 12, "x": 20, "y_home": 55, "y_away": 45},
        {"poste": 13, "x": 60, "y_home": 55, "y_away": 45},
        {"poste": 14, "x": 70, "y_home": 60, "y_away": 40},
        {"poste": 15, "x": 40, "y_home": 50, "y_away": 50}
    ]

    terrain_home = []
    terrain_away = []

    joueurs_home = data.get("compo_home", {}).get("joueurs", [])
    joueurs_away = data.get("compo_away", {}).get("joueurs", [])

    for i, poste in enumerate(formation):
        if i < len(joueurs_home) and joueurs_home[i].strip():
            terrain_home.append({
                "nom": joueurs_home[i].strip(),
                "x": poste["x"],
                "y": poste["y_home"]
            })
        if i < len(joueurs_away) and joueurs_away[i].strip():
            terrain_away.append({
                "nom": joueurs_away[i].strip(),
                "x": poste["x"],
                "y": poste["y_away"]
            })

    write_json(TERRAIN_HOME, terrain_home)
    write_json(TERRAIN_AWAY, terrain_away)

    with open(os.path.join(HTML_OUTPUT_DIR, "terrain_template.html"), encoding="utf-8") as f:
        template = f.read()
    with open(os.path.join(HTML_OUTPUT_DIR, "terrain.html"), "w", encoding="utf-8") as f:
        f.write(render_template_string(template,
                                       terrain_home=terrain_home,
                                       terrain_away=terrain_away,
                                       arrows=[],
                                       noms_entres=[]))
    return "Terrain réaliste mis à jour avec succès"

@app.route("/delete_all_remplacants", methods=["POST"])
def delete_all_remplacants():
    write_json(REMPLACANTS, {"home": [], "away": []})
    write_json(TERRAIN_HOME, [])
    write_json(TERRAIN_AWAY, [])

    with open(os.path.join(HTML_OUTPUT_DIR, "remplacants.html"), "w", encoding="utf-8") as f:
        f.write(generate_remplacants_html({"home": [], "away": []}))

    data = load_data()
    terrain_home = []
    terrain_away = []

    for i, nom in enumerate(data.get("compo_home", {}).get("joueurs", [])):
        if nom.strip():
            terrain_home.append({
                "nom": nom.strip(),
                "x": 10 + (i % 5) * 18,
                "y": 70 + (i // 5) * 8
            })

    for i, nom in enumerate(data.get("compo_away", {}).get("joueurs", [])):
        if nom.strip():
            terrain_away.append({
                "nom": nom.strip(),
                "x": 10 + (i % 5) * 18,
                "y": 10 + (i // 5) * 8
            })

    write_json(TERRAIN_HOME, terrain_home)
    write_json(TERRAIN_AWAY, terrain_away)

    with open(os.path.join(HTML_OUTPUT_DIR, "terrain_template.html"), "r", encoding="utf-8") as f:
        template = f.read()
    with open(os.path.join(HTML_OUTPUT_DIR, "terrain.html"), "w", encoding="utf-8") as f:
        f.write(render_template_string(template,
                                       terrain_home=terrain_home,
                                       terrain_away=terrain_away,
                                       arrows=[]))

    return redirect(url_for("admin") + "#remplacants")

@app.route("/debug_terrain_json")
def debug_terrain_json():
    return {
        "terrain_home": read_json(TERRAIN_HOME),
        "terrain_away": read_json(TERRAIN_AWAY),
        "remplacants": read_json(REMPLACANTS)
    }

@app.route("/terrain.html")
def terrain_static():
    return send_from_directory(os.path.join(BASE_DIR, "html_out"), "terrain.html")

@app.route("/livecomments.html")
def show_livecomments():
    return send_from_directory(os.path.join(BASE_DIR, "html_out"), "livecomments.html")

@app.route("/remplacants_home.html")
def show_remplacants_home():
    return send_from_directory(os.path.join(BASE_DIR, "html_out"), "remplacants_home.html")

@app.route("/remplacants_away.html")
def show_remplacants_away():
    return send_from_directory(os.path.join(BASE_DIR, "html_out"), "remplacants_away.html")

@app.route("/last_matches.html")
def show_last_matches():
    return send_from_directory(os.path.join(BASE_DIR, "html_out"), "last_matches.html")

@app.route("/infos_match.html")
def show_infos_match():
    return send_from_directory(os.path.join(BASE_DIR, "html_out"), "infos_match.html")

@app.route("/overlay_countdown.html")
def show_overlay_countdown():
    return send_from_directory(os.path.join(BASE_DIR, "html_out"), "overlay_countdown.html")

@app.route("/logos_partners.html")
def show_logos_partners():
    return send_from_directory(os.path.join(BASE_DIR, "html_out"), "logos_partners.html")

@app.route("/obs_message.html")
def show_obs_message():
    return send_from_directory(os.path.join(BASE_DIR, "html_out"), "obs_message.html")

def generate_buteurs_html():
    def format_nom(nom):
        nom = nom.strip().upper()
        if len(nom) <= 10:
            return nom
        return nom[:10] + "."

    data = read_json(BUTEURS_DATA)

    with open(os.path.join(HTML_OUTPUT_DIR, "buteurs.html"), "w", encoding="utf-8") as f:
        f.write("""<html>
<head>
  <meta http-equiv='refresh' content='5'>
  <link rel="stylesheet" href="/static/css/buteurs.css">
  <title>Buteurs en direct</title>
</head>
<body>
<div class="columns"><div class="col">
<div class='buteurs-list'>
""")
        for i, item in enumerate(data.get("home", [])):
            try:
                minute, nom, type_ = item.split(" - ")
                nom_formatte = format_nom(nom)
                f.write(f"<div class='buteur'><span class='home-text'>{minute}’ {nom_formatte} ({type_})</span><button onclick=\"supprimerButeur('home', {i})\">✖</button></div>\n")
            except:
                f.write(f"<div class='buteur'><span class='home-text'>{item}</span><button onclick=\"supprimerButeur('home', {i})\">✖</button></div>\n")
        f.write("</div></div><div class='col'><div class='buteurs-list'>\n")
        for i, item in enumerate(data.get("away", [])):
            try:
                minute, nom, type_ = item.split(" - ")
                nom_formatte = format_nom(nom)
                f.write(f"<div class='buteur'><span class='away-text'>{minute}’ {nom_formatte} ({type_})</span><button onclick=\"supprimerButeur('away', {i})\">✖</button></div>\n")
            except:
                f.write(f"<div class='buteur'><span class='away-text'>{item}</span><button onclick=\"supprimerButeur('away', {i})\">✖</button></div>\n")
        f.write("""</div></div></div>

<script>
function supprimerButeur(team, index) {
  fetch('/delete_buteur/' + team + '/' + index, { method: 'POST' }).then(() => location.reload());
}
</script>
</body></html>
""")

def generate_evenements_html():
    def format_nom(nom):
        nom = nom.strip().upper()
        if len(nom) <= 10:
            return nom
        return nom[:10] + "."

    data = read_json(EVTS_DATA)

    with open(os.path.join(HTML_OUTPUT_DIR, "evenements.html"), "w", encoding="utf-8") as f:
        f.write("""<html>
<head>
  <meta http-equiv='refresh' content='5'>
  <link rel="stylesheet" href="/static/css/evenements.css">
  <title></title>
</head>
<body>
<h2></h2>
<div class="columns"><div class="col">
<h3></h3><div class='events-list'>
""")
        for i, item in enumerate(data.get("home", [])):
            try:
                minute, nom, action = item.split(" - ")
                nom_formatte = format_nom(nom)
                f.write(f"<div class='event'><span class='home-text'>{minute}’ {nom_formatte}, {action}</span><button onclick=\"supprimerEvent('home', {i})\">✖</button></div>\n")
            except:
                f.write(f"<div class='event'><span class='home-text'>{item}</span><button onclick=\"supprimerEvent('home', {i})\">✖</button></div>\n")
        f.write("</div></div><div class='col'><h3></h3><div class='events-list'>\n")
        for i, item in enumerate(data.get("away", [])):
            try:
                minute, nom, action = item.split(" - ")
                nom_formatte = format_nom(nom)
                f.write(f"<div class='event'><span class='away-text'>{minute}’ {nom_formatte}, {action}</span><button onclick=\"supprimerEvent('away', {i})\">✖</button></div>\n")
            except:
                f.write(f"<div class='event'><span class='away-text'>{item}</span><button onclick=\"supprimerEvent('away', {i})\">✖</button></div>\n")
        f.write("""</div></div></div>

<script>
function supprimerEvent(team, index) {
  fetch('/delete_event/' + team + '/' + index, { method: 'POST' }).then(() => location.reload());
}
</script>
</body></html>""")

def generate_remplacants_html(remplacants):
    def format_nom(nom):
        nom = nom.strip().upper()
        if len(nom) <= 10:
            return nom
        return nom[:10] + "."

    html = """<html>
<head>
  <meta http-equiv='refresh' content='5'>
  <link rel="stylesheet" href="/static/css/remplacants.css">
  <title>Remplacements en direct</title>
</head>
<body>
<h2></h2>
<div class="columns"><div class="col">
<h3></h3><div class='remp-list'>
"""
    for i, r in enumerate(remplacants.get("home", [])):
        try:
            minute, action = r.split(" - ")
            out, inn = action.split(" 🔁 ")
            nom_out = format_nom(out.strip())
            nom_in = format_nom(inn.strip())
            html += f"<div class='remp'><span class='home-text'>{minute}’ {nom_out} 🔁 {nom_in}</span><button onclick=\"supprimer('home', {i})\">✖</button></div>\n"
        except:
            html += f"<div class='remp'><span class='home-text'>{r}</span><button onclick=\"supprimer('home', {i})\">✖</button></div>\n"

    html += "</div></div><div class='col'><h3></h3><div class='remp-list'>\n"

    for i, r in enumerate(remplacants.get("away", [])):
        try:
            minute, action = r.split(" - ")
            out, inn = action.split(" 🔁 ")
            nom_out = format_nom(out.strip())
            nom_in = format_nom(inn.strip())
            html += f"<div class='remp'><span class='away-text'>{minute}’ {nom_out} 🔁 {nom_in}</span><button onclick=\"supprimer('away', {i})\">✖</button></div>\n"
        except:
            html += f"<div class='remp'><span class='away-text'>{r}</span><button onclick=\"supprimer('away', {i})\">✖</button></div>\n"

    html += """</div></div></div>
<script>
function supprimer(team, index) {
  fetch('/delete_remplacant/' + team + '/' + index, { method: 'POST' }).then(() => location.reload());
}
</script>
</body></html>"""

    return html

@app.route("/update_commentaires", methods=["POST"])
def update_commentaires():
    data = load_data()
    data.setdefault("commentaires", [])

    if "submit_comment" in request.form:
        minute = request.form.get("comment_minute", "")
        joueur = request.form.get("comment_joueur", "").strip()

        texte = (
            request.form.get('comment_debut_live') or
            request.form.get('comment_meteo') or
            request.form.get('comment_premiere_mitemps') or
            request.form.get('comment_mitemps') or
            request.form.get('comment_deuxieme_mitemps') or
            request.form.get('comment_arbitrage') or
            request.form.get('comment_score_vous') or
            request.form.get('comment_score_adversaire') or
            request.form.get('comment_fin_match') or
            request.form.get('comment_expressions') or
            request.form.get('comment_custom')
        ).strip()

        texte_normalisé = texte.replace("’", "'").strip()

        if texte:
            if joueur:
                data["commentaires"].append(f"{minute} - {joueur} : {texte}")
            else:
                data["commentaires"].append(f"{minute} - {texte}")

            commentaire_score_domicile = {
                "ESSAI !!! Magnifique enchaînement collectif, tout en puissance.": 5,
                "ESSAI !!! Percée fulgurante, quelle action individuelle !": 5,
                "ESSAI sur interception, quelle lecture du jeu incroyable !": 5,
                "Transformation réussie, deux points supplémentaires au compteur.": 2,
                "Pénalité réussie, l’écart se creuse au score.": 3,
                "DROP !!! Trois points supplémentaires dans la besace !": 3,
            }

            commentaire_score_adverse = {
                "Essai inscrit après plusieurs temps de jeu.": 5,
                "Essai marqué après une interception.": 5,
                "Transformation réussie suite à l'essai.": 2,
                "Pénalité réussie sur faute au sol.": 3,
                "Drop réussi pour ajouter trois points.": 3,
            }

            score = data.get("score", {"home": "0", "away": "0"})
            home_score = int(score.get("home", 0))
            away_score = int(score.get("away", 0))

            if texte_normalisé in commentaire_score_domicile:
                home_score += commentaire_score_domicile[texte_normalisé]
            elif texte_normalisé in commentaire_score_adverse:
                away_score += commentaire_score_adverse[texte_normalisé]

            data["score"]["home"] = str(home_score)
            data["score"]["away"] = str(away_score)

            with open(os.path.join(HTML_OUTPUT_DIR, "score.html"), "w", encoding="utf-8") as f:
                f.write(f"""<!DOCTYPE html>
<html lang='fr'>
<head><meta charset='UTF-8'><meta http-equiv='refresh' content='5'><title>Score en direct</title><link rel='stylesheet' href='/static/css/score.css'></head>
<body><h2>Score en direct</h2><div class='columns'><div class='col'><h3>Équipe domicile</h3><div class='score'>{data["score"]["home"]}</div></div>
<div class='col'><h3>Équipe extérieure</h3><div class='score'>{data["score"]["away"]}</div></div></div></body></html>""")

        buteur_actions = {
            "ESSAI !!! Magnifique enchaînement collectif, tout en puissance.": ("Essai (🏉)", "home"),
            "ESSAI !!! Percée fulgurante, quelle action individuelle !": ("Essai (🏉)", "home"),
            "ESSAI sur interception, quelle lecture du jeu incroyable !": ("Essai (🏉)", "home"),
            "Transformation réussie, deux points supplémentaires au compteur.": ("Transfo. (🎯)", "home"),
            "Pénalité réussie, l’écart se creuse au score.": ("Pénalité (🎯)", "home"),
            "DROP !!! Trois points supplémentaires dans la besace !": ("Drop (🦶)", "home"),
            "Essai inscrit après plusieurs temps de jeu.": ("Essai (🏉)", "away"),
            "Essai marqué après une interception.": ("Essai (🏉)", "away"),
            "Transformation réussie suite à l'essai.": ("Transfo. (🎯)", "away"),
            "Pénalité réussie sur faute au sol.": ("Pénalité (🎯)", "away"),
            "Drop réussi pour ajouter trois points.": ("Drop (🦶)", "away")
        }

        if joueur and texte_normalisé in buteur_actions:
            action_type, equipe = buteur_actions[texte_normalisé]
            try:
                with open(BUTEURS_DATA, "r", encoding="utf-8") as f:
                    buteurs_data = json.load(f)
            except FileNotFoundError:
                buteurs_data = {"home": [], "away": []}

            buteurs_data.setdefault(equipe, [])
            buteurs_data[equipe].append(f"{minute} - {joueur} - {action_type}")

            with open(BUTEURS_DATA, "w", encoding="utf-8") as f:
                json.dump(buteurs_data, f, ensure_ascii=False, indent=2)

            generate_buteurs_html()

        commentaire_evenements = {
            "Carton jaune pour faute répétée.": ("Carton (🟨)", "home"),
            "Carton rouge direct ! L'équipe est réduite à 14.": ("Carton (🟥)", "home"),
            "Notre joueur sort sur blessure.": ("Blessure (🚑)", "home"),
            "Carton jaune contre un joueur adverse pour anti-jeu.": ("Carton (🟨)", "away"),
            "Carton rouge pour un geste dangereux côté adverse.": ("Carton (🟥)", "away"),
            "Joueur de l'équipe adverse sort sur blessure.": ("Blessure (🚑)", "away")
        }

        if texte_normalisé in commentaire_evenements:
            action, equipe = commentaire_evenements[texte_normalisé]
            try:
                with open(EVTS_DATA, "r", encoding="utf-8") as f:
                    events = json.load(f)
            except FileNotFoundError:
                events = {"home": [], "away": []}

            events.setdefault(equipe, [])
            if joueur:
                events[equipe].append(f"{minute}′ {joueur} ({action})")
            else:
                events[equipe].append(f"{minute}′ ({action})")

            with open(EVTS_DATA, "w", encoding="utf-8") as f:
                json.dump(events, f, ensure_ascii=False, indent=2)

            generate_evenements_html()

        
        phrases_pause_timer = [
            "Arret du temps", "Arrêt du temps",
            "Et c'est la mi-temps ! 40 minutes de haute intensité dans ce premier acte.",
            "Coup de sifflet final, fin de la rencontre."
        ]
        phrases_reprise_timer = [
            "Reprise du temps"
        ]
        phrase_deuxieme_mitemps = ""
        phrase_premiere_mitemps = "Le coup d'envoi vient d'être donné, c'est parti pour 40 premières minutes intenses !"

        timer_data = load_timer()

        if any(phrase in texte_normalisé for phrase in phrases_pause_timer):
            if not timer_data.get("paused", False):
                timer_data["paused"] = True
                timer_data["paused_at"] = time.time()
        elif any(phrase in texte_normalisé for phrase in phrases_reprise_timer):
            if timer_data.get("paused", False) and timer_data.get("paused_at"):
                paused_duration = time.time() - timer_data["paused_at"]
                timer_data["start_time"] += paused_duration
                timer_data["paused"] = False
                timer_data["paused_at"] = None
        elif texte_normalisé == phrase_premiere_mitemps:
            timer_data["start_time"] = time.time()
            timer_data["paused"] = False
            timer_data["paused_at"] = None
            timer_data["offset"] = 0
        elif texte_normalisé == phrase_deuxieme_mitemps:
            timer_data["start_time"] = time.time()
            timer_data["paused"] = False
            timer_data["paused_at"] = None
            timer_data["offset"] = 40 * 60

        save_timer(timer_data)
        save_data(data)

    commentaires = data.get("commentaires", [])

    def format_nom(nom):
        parts = nom.strip().split()
        if len(parts) >= 2:
            return f"{parts[0][0].upper()}. {parts[1]}"
        return nom[:7]

    with open(os.path.join(HTML_OUTPUT_DIR, "livecomments.html"), "w", encoding="utf-8") as f:
        f.write("""<html>
<head>
  <meta http-equiv="refresh" content="5">
  <link rel="stylesheet" href="/static/css/livecomments.css">
  <title>Commentaires en direct</title>
  <script>
   
    function supprimerCommentaire(index) {
      fetch('/delete_commentaire/' + index, { method: 'POST' })
        .then(() => location.reload());
    }
  </script>
</head>
<body>
""")

        for i, comment in enumerate(reversed(commentaires)):
            real_index = len(commentaires) - 1 - i

            if " - " in comment:
                minute, reste = comment.split(" - ", 1)
                if " : " in reste:
                    try:
                        nom, texte = reste.split(" : ", 1)
                        nom_formatte = format_nom(nom)
                        display = f"{minute}’ {nom_formatte} : {texte.strip()}"
                    except ValueError:
                        display = f"{minute}’ {reste.strip()}"
                else:
                    display = f"{minute}’ {reste.strip()}"
            else:
                display = comment.strip()

            f.write(
                f"<div class='comment'><span>{display}</span>"
                f"<button onclick=\"supprimerCommentaire({real_index})\">✖</button></div>\n"
            )

        f.write("</body>\n</html>")

    
    return redirect(url_for("admin") + "#commentaires")

@app.route("/delete_commentaire/<int:index>", methods=["POST"])
def delete_commentaire(index):
    data = load_data()
    commentaires = data.get("commentaires", [])

    
    if 0 <= index < len(commentaires):
        commentaires.pop(index)  
        data["commentaires"] = commentaires  
        save_data(data)  

    
    def format_nom(nom):
        parts = nom.strip().split()
        if len(parts) >= 2:
            return f"{parts[0][0].upper()}. {parts[1]}"
        return nom[:7]

    
    with open(os.path.join(HTML_OUTPUT_DIR, "livecomments.html"), "w", encoding="utf-8") as f:
        f.write("""<html>
<head>
  <meta http-equiv="refresh" content="5">
  <link rel="stylesheet" href="/static/css/livecomments.css">
  <script>
  function supprimerCommentaire(index) {
      fetch('/delete_commentaire/' + index, { method: 'POST' })
          .then(() => location.reload());  
  }
  </script>
  <title>Commentaires en direct</title>
</head>
<body>
""")

        for i, comment in enumerate(reversed(commentaires)):
            real_index = len(commentaires) - 1 - i  
            if " - " in comment:
                minute, reste = comment.split(" - ", 1)
                if " : " in reste:
                    try:
                        nom, texte = reste.split(" : ", 1)
                        nom_formatte = format_nom(nom)
                        display = f"{minute}’ {nom_formatte} : {texte.strip()}"
                    except ValueError:
                        display = f"{minute}’ {reste.strip()}"
                else:
                    display = f"{minute}’ {reste.strip()}"
            else:
                display = comment.strip()

            
            f.write(f"<div class='comment'><span>{display}</span>"
                    f"<button onclick=\"supprimerCommentaire({real_index})\">✖</button></div>\n")

        f.write("</body>\n</html>")

    return "", 204

@app.route("/reset_all", methods=["POST"])
def reset_all():
    
    generate_archive_resume()  

    
    data = {
        "date": "",
        "heure": "",
        "ville": "",
        "stade": "",
        "arbitres": {
            "central": "",
            "touche_1": "",
            "touche_2": "",
            "video": ""
        },
        "overlay": {
            "last_matches": [{"date": "", "stade": "", "score": "", "winner": ""} for _ in range(3)],
            "logos": [f"/static/logos_partners/logo_partenaire_{i}.png" for i in range(1, 7)],
            "message": "",
            "countdown": {
                "message": "",
                "duration": "5"
            }
        },
        "compo_home": {
            "nom": "",
            "joueurs": ["" for _ in range(15)],
            "remplacants": ["" for _ in range(8)]
        },
        "compo_away": {
            "nom": "",
            "joueurs": ["" for _ in range(15)],
            "remplacants": ["" for _ in range(8)]
        },
        "score": {
            "home": "0",
            "away": "0"
        },
        "buteurs": {
            "home": [],
            "away": []
        },
        "evenements": {
            "home": [],
            "away": []
        },
        "remplacants": {
            "home": [],
            "away": []
        },
        "commentaires": [],
        "timer": {
            "elapsed_seconds": 0,
            "running": False,
            "start_timestamp": None
        }
    }

    save_data(data)

    
    write_json(BUTEURS_DATA, {"home": [], "away": []})
    write_json(EVTS_DATA, {"home": [], "away": []})
    write_json(REMPLACANTS, {"home": [], "away": []})
    write_json(TERRAIN_HOME, [])
    write_json(TERRAIN_AWAY, [])

    
    for html_name in ["buteurs.html", "evenements.html", "remplacants.html", "livecomments.html", "score.html"]:
        with open(os.path.join(HTML_OUTPUT_DIR, html_name), "w", encoding="utf-8") as f:
            f.write("<html><body></body></html>")

    
    return redirect(url_for("admin") + "#reset")

@app.route("/overlay_data")
def overlay_data():
    data = load_data()

    def format_minute_joueur(data_list, remplacement=False):
        formatted_list = []
        for item in data_list:
            if item.strip():
                parts = item.split(' - ')
                if remplacement:
                    if len(parts) == 2:
                        minute = parts[0].strip()
                        joueurs = parts[1].strip()  # format "OUT 🔁 IN"
                        formatted_list.append(f"{minute}' {joueurs}")
                    else:
                        formatted_list.append(item)
                else:
                    if len(parts) == 3:
                        minute = parts[0].strip()
                        joueur = parts[1].strip()
                        action = parts[2].strip()
                        formatted_list.append(f"{minute}' {joueur} {action}")
                    else:
                        formatted_list.append(item)
        return ' // '.join(formatted_list)

    with open(ADMIN_DATA, encoding='utf-8') as f:
        admin_data = json.load(f)

    def safe_load(path):
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    buteurs = safe_load('buteurs.json')
    remplacants = safe_load('remplacants.json')
    evenements = safe_load('evenements.json')

    
    date_str = admin_data.get('date', '')
    heure_str = admin_data.get('heure', '')
    stade = admin_data.get('stade', '')
    ville = admin_data.get('ville', '')
    arbitres = admin_data.get('arbitres', {})

    try:
        locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
    except:
        try:
            locale.setlocale(locale.LC_TIME, 'fr_FR')
        except:
            pass

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        date_finale = date_obj.strftime("%A %d %B %Y")
        
        date_finale = date_finale[0].lower() + date_finale[1:]
    except:
        date_finale = date_str

    infos_match = (f"Le {date_finale} à {heure_str} heures au stade {stade}, à {ville}. "
                   f"Arbitres de la rencontre : {arbitres.get('central', 'N/A')} (arbitre central), "
                   f"{arbitres.get('touche_1', 'N/A')} (arbitre de touche 1), "
                   f"{arbitres.get('touche_2', 'N/A')} (arbitre de touche 2) "
                   f"et {arbitres.get('video', 'N/A')} (arbitre vidéo).")

    last_matches_data = admin_data.get('overlay', {}).get('last_matches', [])
    last_matches_list = []
    for match in last_matches_data:
        date_match = match.get('date', '')
        stade_match = match.get('stade', '')
        score = match.get('score', '')
        winner = match.get('winner', '')

        try:
            date_obj = datetime.strptime(date_match, "%Y-%m-%d")
            date_finale = date_obj.strftime("%A %d %B %Y")
            date_finale = date_finale[0].lower() + date_finale[1:]
        except:
            date_finale = date_match

        match_text = (f"En date du {date_finale}, au stade de {stade_match}, "
                      f"le score final a été de {score} et {winner} sort gagnant.")
        last_matches_list.append(match_text)

    last_matches = ' // '.join(last_matches_list)

    buteurs_home = format_minute_joueur(buteurs.get('home', []))
    buteurs_away = format_minute_joueur(buteurs.get('away', []))
    remplacants_home = format_minute_joueur(remplacants.get('home', []), remplacement=True)
    remplacants_away = format_minute_joueur(remplacants.get('away', []), remplacement=True)
    evenements_home = format_minute_joueur(evenements.get('home', []))
    evenements_away = format_minute_joueur(evenements.get('away', []))

    message_obs = admin_data.get('overlay', {}).get('message_obs', 'Bienvenue sur le live !')

    elapsed_seconds = admin_data.get('timer', {}).get('elapsed_seconds', 0)
    minutes = elapsed_seconds // 60
    seconds = elapsed_seconds % 60
    timer = f"{minutes:02}:{seconds:02}"

    return f"""
    <div style='font-size:65px; background:; color: white; font-weight: 900; text-align:center; margin-bottom:40px;'> {admin_data.get('compo_home', {}).get('nom', '')} </div>
    <div style='font-size:65px; background:; color: white; font-weight: 900; text-align:center; margin-bottom:40px;'> {admin_data.get('compo_away', {}).get('nom', '')} </div>
    <div style='font-size:85px; color: black; font-weight: 900; text-align:center; margin-bottom:40px;'> {admin_data.get('score', {}).get('home', 0)} </div>
    <div style='font-size:85px; color: black; font-weight: 900; text-align:center; margin-bottom:40px;'> {admin_data.get('score', {}).get('away', 0)} </div>

    <div class='scrolling-text' style='font-size:18px; background:; color : black; text-align:left; margin-bottom:40px;'> {infos_match} </div>
    <div class='scrolling-text' style='font-size:24px; background:; color : black; text-align:left; font-weight: 500; margin-bottom:40px;'> {last_matches} </div>

    <div class='scrolling-text' style='font-size:24px; background:; color: white; font-weight: 500; text-align:left; margin-bottom:40px;'> {buteurs_home} </div>
    <div class='scrolling-text' style='font-size:24px; background:; color: white; font-weight: 500; text-align:left; margin-bottom:40px;'> {buteurs_away} </div>

    <div class='scrolling-text' style='font-size:22px; background:; color: white; font-weight: 500; text-align:left; margin-bottom:40px;'> {remplacants_home} </div>
    <div class='scrolling-text' style='font-size:22px; background:; color: white; font-weight: 500; text-align:left; margin-bottom:40px;'> {remplacants_away} </div>

    <div class='scrolling-text' style='font-size:20px; background:; color: white; font-weight: 500; text-align:left; margin-bottom:40px;'> {evenements_home} </div>
    <div class='scrolling-text' style='font-size:20px; background:; color: white; font-weight: 500; text-align:left; margin-bottom:40px;'> {evenements_away} </div>

    <div class='scrolling-text' style='font-size:24px; background:white; color:black; margin-top:60px; padding:10px; text-align:left;'>
      [ {message_obs} ]
    </div>
"""

@app.route('/compo_home.html')
def show_compo_home():
    with open(ADMIN_DATA, "r", encoding="utf-8") as f:
        data = json.load(f)
    compo = data.get("compo_home", {})
    logo = data.get("logo_home", "").replace("\\", "/")
    joueurs = compo.get("joueurs", [""] * 15)
    remplacants = compo.get("remplacants", [""] * 8)

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Compo Équipe Domicile</title>
    <link rel="stylesheet" href="/static/css/compo_home.css">
</head>
<body>
<div class="container">
    <h1>{compo.get("nom", "Équipe Domicile")}</h1>
    {f'<img src="/{logo}" alt="Logo Équipe Domicile" class="logo">' if logo else ''}
    <div class="player-list">
        <h2>Titulaires</h2>
        {"".join([f'<div class="player"><span class="position">{i+1}.</span> {joueurs[i]}</div>' for i in range(15) if joueurs[i]])}
        <h2 style="margin-top: 30px;">Remplaçants</h2>
        {"".join([f'<div class="player"><span class="position">R{i+1}.</span> {remplacants[i]}</div>' for i in range(8) if remplacants[i]])}
    </div>
</div>
</body>
</html>"""
    return html

@app.route('/compo_away.html')
def show_compo_away():
    with open(ADMIN_DATA, "r", encoding="utf-8") as f:
        data = json.load(f)
    compo = data.get("compo_away", {})
    logo = data.get("logo_away", "").replace("\\", "/")
    joueurs = compo.get("joueurs", [""] * 15)
    remplacants = compo.get("remplacants", [""] * 8)

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Compo Équipe Extérieure</title>
    <link rel="stylesheet" href="/static/css/compo_away.css">
</head>
<body>
<div class="container">
    <h1>{compo.get("nom", "Équipe Extérieure")}</h1>
    {f'<img src="/{logo}" alt="Logo Équipe Extérieure" class="logo">' if logo else ''}
    <div class="player-list">
        <h2>Titulaires</h2>
        {"".join([f'<div class="player"><span class="position">{i+1}.</span> {joueurs[i]}</div>' for i in range(15) if joueurs[i]])}
        <h2 style="margin-top: 30px;">Remplaçants</h2>
        {"".join([f'<div class="player"><span class="position">R{i+1}.</span> {remplacants[i]}</div>' for i in range(8) if remplacants[i]])}
    </div>
</div>
</body>
</html>"""
    return html

def format_buteurs(buteurs):
    if not buteurs:
        return ""
    lignes = []
    for b in buteurs:
        parts = b.split(" - ")
        if len(parts) == 3:
            lignes.append(f"{parts[0]}' {parts[1]}, {parts[2]}")
        elif len(parts) == 2:
            lignes.append(f"{parts[0]}' {parts[1]}")
        else:
            lignes.append(b)
    return " — ".join(lignes) + " —"

def format_evenements(events):
    if not events:
        return ""
    lignes = []
    for e in events:
        parts = e.split(" - ")
        if len(parts) == 3:
            lignes.append(f"{parts[0]}' {parts[1]}, {parts[2]}")
        elif len(parts) == 2:
            lignes.append(f"{parts[0]}' {parts[1]}")
        else:
            lignes.append(e)
    return " — ".join(lignes) + " —"

def format_remplacants(remplacants):
    if not remplacants:
        return ""
    return " — ".join(remplacants) + " —"

def format_timer(seconds):
    minutes = seconds // 60
    secondes = seconds % 60
    return f"{minutes:02}:{secondes:02}"

def generate_infos_scroll():
    import locale
    from datetime import datetime

    data = load_data()

    
    try:
        locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
    except:
        try:
            locale.setlocale(locale.LC_TIME, 'fr_FR')
        except:
            locale.setlocale(locale.LC_TIME, '')  

    date_str = data.get("date", "")
    heure_str = data.get("heure", "")
    stade = data.get("stade", "")
    ville = data.get("ville", "")
    arbitres = data.get("arbitres", {})

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        date_finale = date_obj.strftime("%A %d %B %Y")
        date_finale = date_finale[0].lower() + date_finale[1:]  
    except:
        date_finale = date_str

    return (
        f"Le {date_finale} à {heure_str} heures au stade {stade}, à {ville}. "
        f"Arbitres : {arbitres.get('central', 'N/A')} (central), "
        f"{arbitres.get('touche_1', 'N/A')} et {arbitres.get('touche_2', 'N/A')} (touches), "
        f"{arbitres.get('video', 'N/A')} (vidéo)."
    )

def generate_marquee_html(filename, text, color="white", big=False):
    with open(f"static/{filename}", "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <style>
    body {{
      margin: 0;
      padding: 0;
      background: transparent;
      overflow: hidden;
    }}
    .marquee {{
      white-space: nowrap;
      display: inline-block;
      animation: scroll 40s linear infinite;
      font-size: {26 if big else 20}px;
      font-weight: {700 if big else 600};
      color: {color};
    }}
    @keyframes scroll {{
      0% {{ transform: translateX(100%); }}
      100% {{ transform: translateX(-100%); }}
    }}
  </style>
</head>
<body>
  <div class="marquee">
    {text}
  </div>
</body>
</html>
""")

@app.route('/get_panel_data')
def get_panel_data():
    with open(ADMIN_DATA, 'r', encoding='utf-8') as f:
        data = json.load(f)

    with open(TIMER_STATE, 'r', encoding='utf-8') as f:
        timer = json.load(f)

    return jsonify({
        'home_name': data.get('compo_home', {}).get('nom', ''),
        'away_name': data.get('compo_away', {}).get('nom', ''),
        'logo_home': data.get('logo_home', ''),
        'logo_away': data.get('logo_away', ''),
        'score': data.get('score', {'home': 0, 'away': 0}),
        'timer': {
            'display': format_timer(timer.get('elapsed_seconds', 0))
    },

        'infos_match': data.get('infos_match', ''),
        'last_matches': " — ".join(
            f"En date du {m['date']}, au stade {m['stade']}, score : {m['score']}, gagnant : {m['winner']}"
            for m in data.get('overlay', {}).get('last_matches', [])
        ) + " —" if data.get('overlay', {}).get('last_matches') else '',
        'message_obs': data.get('overlay', {}).get('message', ''),

        'buteurs_home': format_buteurs(data.get('buteurs', {}).get('home', [])),
        'buteurs_away': format_buteurs(data.get('buteurs', {}).get('away', [])),

        'remp_home': format_remplacants(data.get('remplacants', {}).get('home', [])),
        'remp_away': format_remplacants(data.get('remplacants', {}).get('away', [])),

        'event_home': format_evenements(data.get('evenements', {}).get('home', [])),
        'event_away': format_evenements(data.get('evenements', {}).get('away', [])),
    })

@app.route("/timer_value")
def timer_value():
    import time
    timer = load_timer()

    
    if timer.get("start_time") and not timer.get("paused", False):
        elapsed = int(time.time() - timer["start_time"])
    elif timer.get("paused") and timer.get("paused_at"):
        elapsed = int(timer["paused_at"] - timer["start_time"])
    else:
        elapsed = 0

    total_seconds = timer.get("initial_minute", 0) * 60 + elapsed
    minutes = total_seconds // 60
    seconds = total_seconds % 60

    
    return jsonify(minute=minutes, second=seconds)

@app.route("/get_timer_minute")
def get_timer_minute():
    timer = load_timer()

    if timer["start_time"] is None:
        return jsonify({"minute": 0})

    now = timer["paused_at"] if timer.get("paused") else time.time()
    start = timer.get("start_time", now)
    offset = timer.get("offset", 0)
    initial_minute = timer.get("initial_minute", 0)

    elapsed = now - start
    total_seconds = elapsed + offset + initial_minute * 60
    minute = int(total_seconds // 60)

    return jsonify({"minute": minute})

@app.route('/layout-<int:num>')
def serve_layout(num):
    if not (1 <= num <= 81):
        return abort(404)
    folder = f"layout-{num:02d}"
    layout_dir = os.path.join("obs_layouts", folder)


    if num == 4 and request.args.get("no_comment") == "1":
        index_sans = os.path.join(layout_dir, "index_sans_commentaires.html")
        if os.path.isfile(index_sans):
            return send_from_directory(layout_dir, "index_sans_commentaires.html")

    return send_from_directory(layout_dir, "index.html")

@app.route('/replace-layouts', methods=['POST'])
def replace_layouts():
    file = request.files.get('layouts_zip')
    if not file or file.filename == '' or not file.filename.endswith('.zip'):
        return "Aucun fichier ZIP sélectionné", 400

    with tempfile.TemporaryDirectory() as tempdir:
        zip_path = os.path.join(tempdir, secure_filename(file.filename))
        file.save(zip_path)

        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(tempdir)
        except Exception as e:
            return f"Erreur à l'extraction : {e}", 400

        for i in range(1, 5):
            src_dir = os.path.join(tempdir, f'layout-0{i}')
            dest_dir = os.path.join(UPLOAD_FOLDER, f'layout-0{i}')
            os.makedirs(dest_dir, exist_ok=True)
            if i == 4:

                index_html = os.path.join(src_dir, 'index.html')
                index_sans = os.path.join(src_dir, 'index_sans_commentaires.html')
                copied_any = False
                if os.path.isfile(index_html):
                    shutil.copy2(index_html, os.path.join(dest_dir, 'index.html'))
                    copied_any = True
                if os.path.isfile(index_sans):
                    shutil.copy2(index_sans, os.path.join(dest_dir, 'index_sans_commentaires.html'))
                    copied_any = True
                if not copied_any:
                    return f"Fichier(s) manquant(s) dans l'archive : layout-04/index.html ou index_sans_commentaires.html", 400
            else:
                src = os.path.join(src_dir, 'index.html')
                dest = os.path.join(dest_dir, 'index.html')
                if os.path.isfile(src):
                    shutil.copy2(src, dest)
                else:
                    return f"Fichier manquant dans l'archive : layout-0{i}/index.html", 400

    return "Installation de l’interface réussie !", 200

@app.route('/html_out/<path:filename>')
def serve_html_out(filename):
    return send_from_directory('html_out', filename)

@app.route('/api/compo_home')
def api_compo_home():
    
    with open(os.path.join(BASE_DIR, "compo_home.html"), encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    title = soup.find('h1').text.strip()
    joueurs = [p.get_text(strip=True) for p in soup.select('.player-list .player')]
    return jsonify({'title': title, 'players': joueurs})

@app.route('/api/compo_away')
def api_compo_away():
    with open(os.path.join(BASE_DIR, "compo_away.html"), encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    title = soup.find('h1').text.strip()
    joueurs = [p.get_text(strip=True) for p in soup.select('.player-list .player')]
    return jsonify({'title': title, 'players': joueurs})

@app.route('/render/compo_home')
def render_compo_home():
    
    tmpl_path = os.path.join(app.root_path, 'html_out', 'compo_home.html')
    with open(tmpl_path, 'r', encoding='utf-8') as f:
        tmpl_str = f.read()
    
    nom_home = "Dom." 
    joueurs_home = ["Joueur A", "Joueur B", "Joueur C"]  
    
    rendered = app.jinja_env.from_string(tmpl_str).render(
        nom_home=nom_home,
        joueurs_home=joueurs_home
    )
    return Response(rendered, mimetype='text/html')

@app.route('/render/compo_away')
def render_compo_away():
    tmpl_path = os.path.join(app.root_path, 'html_out', 'compo_away.html')
    with open(tmpl_path, 'r', encoding='utf-8') as f:
        tmpl_str = f.read()
    nom_away = "Ext."
    joueurs_away = ["Joueur X", "Joueur Y", "Joueur Z"]
    rendered = app.jinja_env.from_string(tmpl_str).render(
        nom_away=nom_away,
        joueurs_away=joueurs_away
    )
    return Response(rendered, mimetype='text/html')

@app.route("/archives")
def archives():
    os.makedirs(ARCHIVES_DIR, exist_ok=True)
    fichiers = sorted(os.listdir(ARCHIVES_DIR), reverse=True)

    def format_date(nom_fichier):
        try:
            brut = nom_fichier.replace("resume_", "").replace(".html", "")
            dt = datetime.strptime(brut, "%Y-%m-%d %Hh%M")

            mois_fr = {
                "January": "janvier", "February": "février", "March": "mars", "April": "avril",
                "May": "mai", "June": "juin", "July": "juillet", "August": "août",
                "September": "septembre", "October": "octobre", "November": "novembre", "December": "décembre"
            }

            mois_anglais = dt.strftime("%B")
            mois = mois_fr.get(mois_anglais, mois_anglais)
            return dt.strftime(f"%d {mois} %Y à %Hh%M")
        except:
            return nom_fichier

    rows = ""
    for nom in fichiers:
        if nom.endswith(".html"):
            date_affichee = format_date(nom)
            rows += f"""
            <div style="
              background-color: #1e293b;
              border-left: 4px solid var(--rouge);
              border-radius: 10px;
              padding: 20px 24px;
              margin-bottom: 24px;
              box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            ">
              <h3 style="
                margin: 0 0 6px;
                font-size: 1.25rem;
                color: var(--text);
              ">📄 Résumé du {date_affichee}</h3>

              <p style="margin-top: 2px; color: #9ca3af; font-size: 0.85rem;">
                Fichier généré automatiquement – prêt à consulter ou supprimer.
              </p>

              <p style="margin-top: 12px; font-size: 0.95rem;">
                Contient les informations du match : date, lieu, arbitres, compositions, score, buteurs, événements et remplacements.
              </p>

              <div style="margin-top: 14px;">
                <a href="/archives/{nom}" target="_blank" style="
                  display: inline-block;
                  background-color: #3b82f6;
                  color: white;
                  padding: 14px 28px;
                  border: none;
                  border-radius: 10px;
                  font-weight: 600;
                  font-family: 'Inter', sans-serif;
                  text-decoration: none;
                  cursor: pointer;
                  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3);
                  transition: all 0.2s ease;
                  margin-right: 1rem;
                " onmouseover="this.style.backgroundColor='#2563eb'" onmouseout="this.style.backgroundColor='#3b82f6'">🕵️‍♂️ Consulter</a>

                <form action="/delete_archive/{nom}" method="post" style="display:inline;" onsubmit="return confirm('🗑️ Supprimer ce résumé ? Cette action est irréversible.')">
                  <button type="submit" style="
                    background-color: #ef4444;
                    color: white;
                    padding: 14px 28px;
                    border: none;
                    border-radius: 10px;
                    font-weight: 600;
                    font-family: 'Inter', sans-serif;
                    cursor: pointer;
                    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3);
                    transition: all 0.2s ease;
                  " onmouseover="this.style.backgroundColor='#dc2626'" onmouseout="this.style.backgroundColor='#ef4444'">🗑️ Supprimer</button>
                </form>
              </div>
            </div>
            """

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <title>Archives – Résumés - XV LIVE MANAGER</title>
  <link rel="stylesheet" href="/static/css/guide.css">
</head>
<body>
  <header>
    <h1>XV LIVE MANAGER - Archives</h1>
    <p>Consultez ou supprimez les anciens résumés générés automatiquement.</p>
    <a href="/" class="button">⬅ Retour</a>
  </header>
  <main class="container">
    {rows if rows else "<p>Aucune archive disponible.</p>"}
  </main>
</body>
</html>"""
    return html

@app.route("/archives/<path:filename>")
def serve_archive(filename):
    return send_from_directory(ARCHIVES_DIR, filename)

@app.route("/delete_archive/<filename>", methods=["POST"])
def delete_archive(filename):
    archive_path = os.path.join(ARCHIVES_DIR, filename)
    if os.path.exists(archive_path):
        os.remove(archive_path)
    return redirect("/")

@app.route("/new")
def show_new():
    return send_from_directory(os.path.join(BASE_DIR, "."), new.html)

@app.route("/update_score_js", methods=["POST"])
def update_score_js_api():    
    data = load_data()
    data.setdefault("score", {"home": "0", "away": "0"})
    payload = request.get_json(silent=True) or {}
    team    = payload.get("team")
    amount  = int(payload.get("amount", 0))
    current = int(data["score"].get(team, "0"))
    data["score"][team] = str(current + amount)
    save_data(data)
    return jsonify(home=data["score"]["home"], away=data["score"]["away"])

@app.route('/api/save_settings', methods=['POST'])
def api_save_settings():
    username = request.form.get('username', '').strip()
    tagline = request.form.get('tagline', '').strip()
    logo_file = request.files.get('logo')
    logo_filename = None

    if logo_file:
        logo_filename = "logo_user.png"
        logo_file.save(os.path.join(USER_SETTINGS_DIR, logo_filename))

    # Relire pour garder l'ancien logo si aucun upload
    settings = {}
    if os.path.exists(USER_SETTINGS_JSON):
        with open(USER_SETTINGS_JSON, "r", encoding="utf-8") as f:
            try:
                settings = json.load(f)
            except:
                settings = {}

    settings["username"] = username
    settings["tagline"] = tagline
    settings["logo"] = logo_filename if logo_file else settings.get("logo")

    with open(USER_SETTINGS_JSON, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

    return jsonify({"success": True, "settings": settings})

@app.route('/api/get_settings', methods=['GET'])
def api_get_settings():
    if os.path.exists(USER_SETTINGS_JSON):
        with open(USER_SETTINGS_JSON, "r", encoding="utf-8") as f:
            try:
                settings = json.load(f)
            except:
                settings = {}
    else:
        settings = {"username": "", "tagline": "", "logo": None}
    return jsonify(settings)

@app.route('/api/get_logo')
def api_get_logo():
    logo_filename = "logo_user.png"
    logo_path = os.path.join(USER_SETTINGS_DIR, logo_filename)
    if os.path.exists(logo_path):
        return send_from_directory(USER_SETTINGS_DIR, logo_filename)
    return abort(404)

@app.route('/api/delete_logo', methods=['POST'])
def api_delete_logo():

    logo_path = os.path.join(USER_SETTINGS_DIR, "logo_user.png")

    if os.path.exists(logo_path):
        os.remove(logo_path)

    settings_file = os.path.join(USER_SETTINGS_DIR, "settings.json")
    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
            settings["logo"] = None
            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Suppression logo utilisateur] Erreur : {e}")
    return jsonify({"success": True})

@app.route("/get_local_version")
def get_local_version():
    try:
        with open("version.txt", "r", encoding="utf-8") as f:
            version = f.read().strip()
        return version, 200, {"Content-Type": "text/plain; charset=utf-8"}
    except Exception:
        return "0", 200, {"Content-Type": "text/plain; charset=utf-8"}

import subprocess

@app.route("/run_update_script", methods=["POST"])
def run_update_script():
    try:
        result = subprocess.run(
            ["python\\python.exe", "update_xvlivemanager.py"],
            cwd=os.getcwd(),
            capture_output=True,
            timeout=120,
            text=True
        )
        if result.returncode == 0:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": result.stderr}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

import os

@app.route("/shutdown", methods=["POST"])
def shutdown():
    app.logger.info("Demande d'arrêt reçue (shutdown route appelée).")
    os._exit(0)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
