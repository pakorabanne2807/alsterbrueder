import streamlit as st
import pandas as pd
import json
import os
import re  # Für die präzise JSON-Extraktion
from datetime import datetime
import random
import requests
import plotly.express as px
import plotly.graph_objects as go  # Für das FUT-Radar-Chart

# --- GEMINI KI PAKET IMPORTER ---
try:
    import google.generativeai as genai
    HAS_GEMINI_LIB = True
except ImportError:
    HAS_GEMINI_LIB = False

# --- KONFIGURATION & SETUP ---
st.set_page_config(
    page_title="Alsterbrüder", 
    page_icon="⚽", 
    layout="wide"
)

DATA_FILE = "alsterbrueder_daten.json"
POSITIONS = [
    "TW", "IV", "LV", "RV", "ZDM", "ZM", "ZOM", "LM", "RM", "LF", "RF", "ST"
]
TRAINING_PHASES = [
    "1. Aufwärmen", 
    "2. Passspiel", 
    "3. Rondo", 
    "4. Torschuss / Spielform", 
    "5. Abschlussspiel"
]

# 🌍 GOOGLE CLOUD URL:
API_URL = "https://script.google.com/macros/s/AKfycbwC5946xV9qMBEiTkPYTt1sqP0n0ohPN_n2QqA1nPWurK63_QYs9WiTwUNIN2J0Qs9MPA/exec"

# --- UN SICHTBARE HINTERGRUND-HOLUNG DES GEMINI-KEYS ---
def get_background_gemini_key():
    """Liest den API-Key sicher und unsichtbar aus den Streamlit Secrets oder Systemvariablen."""
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"].strip()
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY", "").strip()

# --- HILFSFUNKTIONEN ---
def sind_verwandt(pos1, pos2):
    verwandte_paare = [
        {"ZM", "ZOM"},
        {"ZM", "ZDM"},
        {"RV", "LV"},
        {"RM", "LM"}
    ]
    return {pos1, pos2} in verwandte_paare

def berechne_level(punkte):
    if punkte >= 300: return "👑 Alsterbrüder-Legende"
    elif punkte >= 150: return "🟣 Team-Leader"
    elif punkte >= 50: return "🔵 Stammspieler"
    else: return "🟢 Jugend-Rookie"

# --- INTELLIGENTER JSON-SLICER ---
def extract_json_array(text):
    """Filtert exakt das erste gültige JSON-Array [...] heraus."""
    text = re.sub(r'```(?:json)?', '', text, flags=re.IGNORECASE).strip()
    start_idx = text.find('[')
    if start_idx != -1:
        bracket_count = 0
        in_string = False
        escape = False
        for i in range(start_idx, len(text)):
            char = text[i]
            if escape: escape = False; continue
            if char == '\\': escape = True; continue
            if char == '"': in_string = not in_string; continue
            if not in_string:
                if char == '[': bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                    if bracket_count == 0: return text[start_idx:i+1]
    return text

# --- DYNAMISCHE GEMINI-ABFRAGE ---
def get_gemini_json_text(prompt, api_key):
    genai.configure(api_key=api_key.strip())
    available_models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
    except Exception: pass
        
    if not available_models:
        available_models = ['models/gemini-1.5-flash', 'models/gemini-2.0-flash', 'models/gemini-2.5-flash', 'models/gemini-pro', 'gemini-1.5-flash']

    gen_config = {"response_mime_type": "application/json"}
    last_err = None
    for m in available_models:
        try:
            model = genai.GenerativeModel(m, generation_config=gen_config)
            res = model.generate_content(prompt)
            if res and res.text: return res.text
        except Exception:
            try:
                model = genai.GenerativeModel(m)
                res = model.generate_content(prompt)
                if res and res.text: return res.text
            except Exception as e: last_err = e; continue
            
    if last_err: raise last_err
    raise Exception("Kein aktives Gemini-Modell gefunden. Bitte prüfe deinen API-Key in den Secrets!")

# --- ECHTE GEMINI KI-GENERATOREN ---
def generiere_echte_ki_fragen(thema, api_key):
    if not HAS_GEMINI_LIB or not api_key: return None
    try:
        prompt = f"Erstelle 2 Multiple-Choice-Taktikfragen für U13-Fußballer zum Thema '{thema}' als JSON-Array mit question, options, correct, points."
        raw_text = get_gemini_json_text(prompt, api_key)
        return json.loads(extract_json_array(raw_text))
    except Exception as e: st.error(f"KI-Fehler: {e}"); return None

def generiere_echte_ki_challenges(thema, api_key):
    if not HAS_GEMINI_LIB or not api_key: return None
    try:
        prompt = f"Erstelle 2 Wochen-Challenges für U13-Fußballer zum Thema '{thema}' als JSON-Array mit title, points."
        raw_text = get_gemini_json_text(prompt, api_key)
        return json.loads(extract_json_array(raw_text))
    except Exception as e: st.error(f"KI-Fehler: {e}"); return None

# --- DATEN-MANAGEMENT ---
def generiere_testdaten():
    namen = ["Jannis", "Leo", "Tom", "Mats", "Finn", "Paul", "Luis", "Lasse", "Jonas", "Mika", "Emil", "Emilio", "Anton", "Noah", "Leon", "Elias", "Ben"]
    spieler_liste = []
    for i, name in enumerate(namen):
        pos = [random.choice(POSITIONS)]
        if random.random() > 0.4: pos.append(random.choice([p for p in POSITIONS if p != pos[0]]))
        spieler_liste.append({
            "id": i + 1, "name": name, "role": "Spieler", "number": str(random.randint(2, 99)), "positions": pos, 
            "training": [], "matches": [], "pin": str(random.randint(1000, 9999)), "video_url": "", "video_notes": "",
            "points": random.randint(10, 80), "completed_challenges": [], "solved_quizzes": [],
            "base_pac": 75, "base_sho": 60, "base_pas": 65, "base_dri": 70, "base_def": 55, "base_phy": 65
        })
    spieler_liste.append({"id": 999, "name": "Pascal (Trainer)", "role": "Trainer", "number": "", "positions": [], "training": [], "matches": []})
    
    uebungs_liste = [
        {"id": 1, "name": "Kognitives Einlaufen", "phase": "1. Aufwärmen", "schwerpunkt": "Passspiel", "spieler": "Alle", "aufbau": "Hütchenviereck. Einlaufen mit Richtungswechsel auf Signal.", "grafik": ""},
        {"id": 2, "name": "Y-Passform", "phase": "2. Passspiel", "schwerpunkt": "Passspiel", "spieler": "10-12", "aufbau": "Passen im Y-Muster mit Nachlaufen. Fokus auf offene Stellung.", "grafik": ""},
        {"id": 3, "name": "4 gegen 2 Rondo", "phase": "3. Rondo", "schwerpunkt": "Umschalten", "spieler": "6", "aufbau": "Klassisches Rondo im 10x10m Feld. Maximal 2 Kontakte.", "grafik": ""},
        {"id": 4, "name": "Flügelspiel mit Torschuss", "phase": "4. Torschuss / Spielform", "schwerpunkt": "Torschuss", "spieler": "Alle", "aufbau": "Pass in die Gasse, Flanke und Torschuss im Zentrum.", "grafik": ""},
        {"id": 5, "name": "Freies Spiel 8v8", "phase": "5. Abschlussspiel", "schwerpunkt": "Spielform", "spieler": "Alle", "aufbau": "Zwei Tore, freies Spiel im doppelten Strafraum.", "grafik": ""}
    ]
    
    challenge_katalog = [
        {"id": 1, "title": "⚽ 50x den Ball mit dem schwachen Fuß hochhalten!", "points": 25, "used_count": 1},
        {"id": 2, "title": "🎯 5x hintereinander aus 16m die Torlatte treffen", "points": 30, "used_count": 0}
    ]
    
    master_katalog = [
        {"id": 1, "question": "Was machen wir sofort bei Ballverlust im Zentrum?", "options": ["A) Stehen bleiben und meckern", "B) Sofort nachsetzen & Umschalten auf Gegenpressing", "C) Langsam zurücklaufen"], "correct": "B) Sofort nachsetzen & Umschalten auf Gegenpressing", "points": 10, "used_count": 1},
        {"id": 2, "question": "Wie verhalten sich die Außenbahnspieler (LM/RM) im eigenen Ballbesitz?", "options": ["A) Sie machen das Feld maximal breit", "B) Sie stellen sich alle in die Mitte", "C) Sie bleiben beim eigenen Torwart"], "correct": "A) Sie machen das Feld maximal breit", "points": 10, "used_count": 1}
    ]
    
    prinzipien_liste = [
        {"id": 1, "title": "⚡ 5-Sekunden-Gegenpressing", "category": "⚽ Auf dem Platz (Taktik)", "positions": ["Alle"], "desc": "Bei Ballverlust schalten wir SOFORT um. Die ersten 5 Sekunden gehören voll uns!"},
        {"id": 2, "title": "🎯 Minimales Kontaktespiel", "category": "⚽ Auf dem Platz (Taktik)", "positions": ["Alle"], "desc": "Der Ball ist schneller als jeder Gegenspieler. Max. 2-3 Kontakte im Zentrum!"},
        {"id": 3, "title": "🔥 100% Fokus ab Aufwärmen", "category": "🧠 Neben dem Platz (Einstellung)", "positions": ["Alle"], "desc": "Schuhe zu, Gürtel festziehen. Wenn das Aufwärmen startet, blendet jeder Quatsch aus."},
        {"id": 4, "title": "🗣️ Positives Coaching untereinander", "category": "🧠 Neben dem Platz (Einstellung)", "positions": ["Alle"], "desc": "Fehler passieren. Wir bauen uns gegenseitig auf und meckern nicht auf dem Platz!"},
        {"id": 5, "title": "🧤 Lautstarke Kommandos geben", "category": "📍 Positionsspezifisch", "positions": ["TW"], "desc": "Der Torwart sieht das ganze Feld! Kommandos wie 'KEEPER' oder 'LEO' laut herausrufen."},
        {"id": 6, "title": "🛡️ Offene Körperstellung in der Kette", "category": "📍 Positionsspezifisch", "positions": ["IV", "LV", "RV"], "desc": "Nie den Rücken zum Ball drehen. Immer so stehen, dass man Ball und Gegenspieler im Blick hat."},
        {"id": 7, "title": "🔄 Klatschen lassen & Aufdrehen", "category": "📍 Positionsspezifisch", "positions": ["ZM", "ZDM"], "desc": "Gegenpress-Druck mit einem Kontakt entweichen oder aufdrehen, wenn der Rücken frei ist."}
    ]
    
    return {
        "players": spieler_liste, 
        "exercises": uebungs_liste,
        "challenge_pool": challenge_katalog,
        "active_challenge_id": 1,
        "quiz_pool": master_katalog,
        "active_quiz_ids": [1, 2],
        "principles": prinzipien_liste
    }

def lade_daten():
    data = None
    if API_URL:
        try:
            res = requests.get(API_URL, timeout=15)
            if res.text.strip().startswith("<!DOCTYPE") or "html" in res.text.lower(): data = None
            else: data = res.json()
        except Exception: data = None
            
    if data is None:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f: data = json.load(f)
        else: data = generiere_testdaten()

    if "players" not in data: data["players"] = []
    if "exercises" not in data: data["exercises"] = []
    if "principles" not in data or not data["principles"]: data["principles"] = generiere_testdaten()["principles"]
    
    # MIGRATIONS-LOGIK FÜR NEUES PRINZIPIEN-FORMAT
    for pr in data.get("principles", []):
        if "supporters" in pr: del pr["supporters"]
        if "is_focus" in pr: del pr["is_focus"]
        if "type" in pr: del pr["type"]
        if "position" in pr:
            old_p = pr.pop("position")
            if isinstance(old_p, str):
                if "TW" in old_p: pr["positions"] = ["TW"]
                elif "Abwehr" in old_p: pr["positions"] = ["IV", "LV", "RV"]
                elif "Mittelfeld" in old_p: pr["positions"] = ["ZDM", "ZM", "ZOM"]
                elif "Flügel" in old_p: pr["positions"] = ["LM", "RM", "LF", "RF"]
                elif "Sturm" in old_p: pr["positions"] = ["ST"]
                else: pr["positions"] = ["Alle"]
        if "positions" not in pr or not isinstance(pr["positions"], list):
            pr["positions"] = ["Alle"]

    if "challenge_pool" not in data or not data["challenge_pool"]: data["challenge_pool"] = generiere_testdaten()["challenge_pool"]
    if "active_challenge_id" not in data: data["active_challenge_id"] = data["challenge_pool"][0]["id"]
        
    if "quiz_pool" not in data or not data["quiz_pool"]: data["quiz_pool"] = generiere_testdaten()["quiz_pool"]
    if "active_quiz_ids" not in data: data["active_quiz_ids"] = [q["id"] for q in data["quiz_pool"][:2]]

    for p in data.get("players", []):
        if "role" not in p: p["role"] = "Spieler"
        if "number" not in p: p["number"] = ""
        if "positions" not in p: p["positions"] = ["ZM"]
        if "pin" not in p: p["pin"] = ""
        if "video_url" not in p: p["video_url"] = ""
        if "video_notes" not in p: p["video_notes"] = ""
        if "points" not in p: p["points"] = 0
        if "completed_challenges" not in p: p["completed_challenges"] = []
        if "solved_quizzes" not in p: p["solved_quizzes"] = []
        if p["role"] == "Spieler" and "base_pac" not in p:
            pos_main = p["positions"][0] if p["positions"] else "ZM"
            if pos_main in ["TW"]: p["base_pac"], p["base_sho"], p["base_pas"], p["base_dri"], p["base_def"], p["base_phy"] = 62, 30, 60, 58, 85, 60
            elif pos_main in ["IV", "LV", "RV"]: p["base_pac"], p["base_sho"], p["base_pas"], p["base_dri"], p["base_def"], p["base_phy"] = 74, 45, 62, 66, 84, 75
            elif pos_main in ["ZDM", "ZM", "ZOM", "LM", "RM"]: p["base_pac"], p["base_sho"], p["base_pas"], p["base_dri"], p["base_def"], p["base_phy"] = 77, 65, 75, 81, 70, 68
            else: p["base_pac"], p["base_sho"], p["base_pas"], p["base_dri"], p["base_def"], p["base_phy"] = 88, 78, 64, 84, 38, 70
    return data

def speichere_daten(data):
    if API_URL:
        try:
            res = requests.post(API_URL, data=json.dumps(data), headers={"Content-Type": "application/json"}, timeout=30)
            if res.status_code in [200, 302]: return True
            else: st.error(f"Fehler beim Sichern in der Cloud. Status: {res.status_code}"); return False
        except Exception as e: st.error(f"Verbindung zur Google-Cloud unterbrochen: {e}"); return False
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)
        return True
    except Exception as e: st.error(f"Lokaler Speicherfehler: {e}"); return False

# --- INITIALISIERUNG DER SPEICHERRÄUME ---
if "data" not in st.session_state: st.session_state.data = lade_daten()
if "zuweisungen" not in st.session_state: st.session_state.zuweisungen = {}

nur_spieler = [p for p in st.session_state.data["players"] if p.get("role", "Spieler") == "Spieler"]

# --- PERSISTENT LOGIN BERECHNUNG AUS DER URL ---
qp_trainer = st.query_params.get("trainer") == "1"
qp_player = st.query_params.get("player")
qp_pin = st.query_params.get("pin")

# KEY UNSICHTBAR IN HINTERGRUND-VARIABLE LADEN
gemini_key = get_background_gemini_key()

# --- SIDEBAR: PASSWORT-SCHUTZ & PERSISTENTER SPIELER LOGIN ---
with st.sidebar:
    st.markdown("### 🔐 Trainer-Bereich")
    default_pass = "fcalster" if qp_trainer else ""
    passwort_eingabe = st.text_input(
        "Trainer-Passwort für Schreibrechte:", 
        type="password",
        value=default_pass,
        key="trainer_auth"
    )
    is_trainer = (passwort_eingabe == "fcalster")
    
    if is_trainer:
        st.query_params["trainer"] = "1"
        st.success("👨‍🍳 Trainer-Modus aktiv")
    else:
        if "trainer" in st.query_params: del st.query_params["trainer"]
        st.info("👪 Eltern-Modus active")
        
    st.markdown("---")
    st.markdown("### 🏃‍♂️ Spieler-Login")
    
    logged_in_player = None
    if nur_spieler:
        spieler_namen_liste = ["-- Bitte wählen --"] + sorted([sp["name"] for sp in nur_spieler])
        default_idx = spieler_namen_liste.index(qp_player) if qp_player in spieler_namen_liste else 0
        gewaehlter_spieler_login = st.selectbox("Wer bist du?", spieler_namen_liste, index=default_idx, key="player_select_login")
        eingabe_pin = st.text_input("Deine 4-stellige PIN:", type="password", value=qp_pin if qp_pin else "", key="player_pin_login")
        
        if gewaehlter_spieler_login != "-- Bitte wählen --" and eingabe_pin:
            target_p = next((x for x in nur_spieler if x["name"] == gewaehlter_spieler_login), None)
            if target_p and target_p.get("pin") == eingabe_pin.strip():
                logged_in_player = target_p
                st.query_params["player"] = gewaehlter_spieler_login
                st.query_params["pin"] = eingabe_pin.strip()
                st.success(f"Hi {gewaehlter_spieler_login}! 👋")
            elif target_p and not target_p.get("pin"):
                st.warning("Für dich wurde noch keine PIN hinterlegt. Frage deinen Trainer!")
            else: st.error("Falsche PIN! ❌")

def berechne_statistiken(spieler, erlaubte_typen=None):
    alle_events = spieler.get("training", [])
    if erlaubte_typen is not None: alle_events = [t for t in alle_events if t.get("type", "Training") in erlaubte_typen]
    gesamt_tr = len(alle_events)
    anwesend_tr = [t for t in alle_events if t["present"]]
    beteiligungs_quote = (len(anwesend_tr) / gesamt_tr * 100) if gesamt_tr > 0 else 0

    spiele = spieler.get("matches", [])
    tore_gesamt, vorlagen_gesamt, spiele_gesamt = 0, 0, 0
    for m in spiele:
        if m.get("played", True) and m.get("team", "Blau") in ["Blau", "Gelb", "Ersatz"]:
            spiele_gesamt += 1
            if "goals" in m: tore_gesamt += int(m["goals"])
            elif "goalsStr" in m:
                g_str = str(m["goalsStr"]).strip()
                if g_str: tore_gesamt += len(g_str.split(","))
            vorlagen_gesamt += int(m.get("assists", 0))

    nr_val = spieler.get("number", "")
    nr = int(nr_val) if str(nr_val).isdigit() else None
    club = "🥇 Gold-Club" if beteiligungs_quote >= 90 else ("🥈 Silber-Club" if beteiligungs_quote >= 75 else ("🥉 Bronze-Club" if beteiligungs_quote >= 50 else "-"))

    badges = []
    if beteiligungs_quote >= 85 and gesamt_tr >= 5: badges.append("🔥 Dauerbrenner")
    if tore_gesamt >= 5: badges.append("⚽ Tormaschine")
    if vorlagen_gesamt >= 5: badges.append("🅰️ Vorlagen-Gott")
    if (tore_gesamt + vorlagen_gesamt) >= 8: badges.append("🌟 Top-Scorer")
    if club == "🥇 Gold-Club": badges.append("👑 Trainingskönig")

    return {
        "Nr.": nr, "Name": spieler["name"], "Positionen": ", ".join(spieler["positions"]),
        "Beteiligung": round(beteiligungs_quote), "🏃‍♂️ Spiele": spiele_gesamt, "Meilenstein": club,
        "⚽ Tore": tore_gesamt, "🅰️ Vorlagen": vorlagen_gesamt, "🌟 Scorer": tore_gesamt + vorlagen_gesamt,
        "Badges": badges
    }

def generiere_pitch_html(aufstellung_dict, ersatzbank_liste, team_name):
    html_code = f"""
    <style>
    .pitch-layout {{ display: flex; gap: 15px; justify-content: center; align-items: flex-start; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    .field {{ width: 330px; height: 440px; background-color: #2e7d32; background-image: linear-gradient(#388e3c 50%, #2e7d32 50%); background-size: 100% 40px; border: 4px solid #ffffff; border-radius: 8px; position: relative; box-shadow: 0 4px 10px rgba(0,0,0,0.3); }}
    .field::before {{ content: ''; position: absolute; top: 50%; left: 0; width: 100%; height: 2px; background: rgba(255,255,255,0.5); }}
    .center-circle {{ position: absolute; top: 50%; left: 50%; width: 70px; height: 70px; border: 2px solid rgba(255,255,255,0.5); border-radius: 50%; transform: translate(-50%, -50%); }}
    .slot {{ position: absolute; width: 80px; height: 50px; border: 1px dashed rgba(255,255,255,0.3); border-radius: 5px; transform: translateX(-50%); display: flex; align-items: center; justify-content: center; }}
    .slot-label {{ position: absolute; top: -12px; width: 100%; text-align: center; font-size: 9px; color: rgba(255,255,255,0.4); font-weight: bold; }}
    .player {{ width: 74px; height: 44px; background: #facc15; color: #1e3a8a; border: 1px solid #eab308; border-radius: 4px; font-size: 11px; font-weight: bold; text-align: center; display: flex; flex-direction: column; justify-content: center; align-items: center; cursor: move; box-shadow: 0 2px 4px rgba(0,0,0,0.2); padding: 1px; box-sizing: border-box; }}
    .player .nr {{ font-size: 9px; color: #ffffff; background: #1e3a8a; padding: 0px 3px; border-radius: 2px; margin-bottom: 1px; }}
    .player .name-text {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; width: 100%; }}
    .bench {{ width: 150px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); max-height: 440px; overflow-y: auto; }}
    .bench-title {{ font-size: 12px; font-weight: bold; color: #64748b; text-align: center; margin-bottom: 8px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; }}
    .bench-zone {{ min-height: 380px; display: flex; flex-direction: column; gap: 6px; }}
    </style>
    <script>
    function allowDrop(ev) {{ ev.preventDefault(); }}
    function drag(ev) {{ ev.dataTransfer.setData("text", ev.target.id); }}
    function drop(ev) {{
        ev.preventDefault();
        var data = ev.dataTransfer.getData("text");
        var draggedEl = document.getElementById(data);
        var target = ev.target;
        if (target.classList.contains('player') || target.parentNode.classList.contains('player')) {{
            var slot = target.closest('.slot') || target.closest('.bench-zone');
            if (slot) slot.appendChild(draggedEl);
        }} else if (target.classList.contains('slot') || target.classList.contains('bench-zone')) {{
            target.appendChild(draggedEl);
        }}
    }}
    </script>
    <div class="pitch-layout">
        <div class="field">
            <div class="center-circle"></div>
            <div class="slot" style="left: 50%; top: 12%;" ondragover="allowDrop(event)" ondrop="drop(event)"><span class="slot-label">ST</span>{aufstellung_dict.get('ST', '')}</div>
            <div class="slot" style="left: 18%; top: 38%;" ondragover="allowDrop(event)" ondrop="drop(event)"><span class="slot-label">LM</span>{aufstellung_dict.get('LM', '')}</div>
            <div class="slot" style="left: 50%; top: 38%;" ondragover="allowDrop(event)" ondrop="drop(event)"><span class="slot-label">ZM</span>{aufstellung_dict.get('ZM', '')}</div>
            <div class="slot" style="left: 82%; top: 38%;" ondragover="allowDrop(event)" ondrop="drop(event)"><span class="slot-label">RM</span>{aufstellung_dict.get('RM', '')}</div>
            <div class="slot" style="left: 28%; top: 65%;" ondragover="allowDrop(event)" ondrop="drop(event)"><span class="slot-label">IV (L)</span>{aufstellung_dict.get('IV (L)', '')}</div>
            <div class="slot" style="left: 72%; top: 65%;" ondragover="allowDrop(event)" ondrop="drop(event)"><span class="slot-label">IV (R)</span>{aufstellung_dict.get('IV (R)', '')}</div>
            <div class="slot" style="left: 50%; top: 85%;" ondragover="allowDrop(event)" ondrop="drop(event)"><span class="slot-label">TW</span>{aufstellung_dict.get('TW', '')}</div>
        </div>
        <div class="bench"><div class="bench-title">🔄 Ersatzbank</div><div class="bench-zone" ondragover="allowDrop(event)" ondrop="drop(event)">{ersatzbank_liste}</div></div>
    </div>
    """
    return html_code

# --- UI: NAVIGATION REORGANISIEREN ---
available_tabs = ["📊 Übersicht", "📜 Team-DNA", "🔍 Spieler-Profile", "📖 Spielübersicht", "🎮 Challenge & Quiz"]

if logged_in_player or is_trainer: available_tabs += ["🎥 Videoanalyse"]
if is_trainer: available_tabs += ["🏃‍♂️ Kader", "⚽ Spiel loggen", "🤖 KI Twin-Teams", "📥 Import (SpielerPlus)", "📋 Trainingsplaner"]
available_tabs += ["🏆 Liga-Tabelle"]

tab_slugs = {
    "📊 Übersicht": "uebersicht", "📜 Team-DNA": "dna", "🔍 Spieler-Profile": "profile", "📖 Spielübersicht": "spieluebersicht", 
    "🎮 Challenge & Quiz": "challenge", "🎥 Videoanalyse": "video", "🏃‍♂️ Kader": "kader", "⚽ Spiel loggen": "spiel-loggen", 
    "🤖 KI Twin-Teams": "ki-teams", "📥 Import (SpielerPlus)": "import", "📋 Trainingsplaner": "planer", "🏆 Liga-Tabelle": "liga"
}
slug_to_tab = {v: k for k, v in tab_slugs.items()}
url_slug = st.query_params.get("tab", "uebersicht")
default_tab = slug_to_tab.get(url_slug, "📊 Übersicht")

if default_tab not in available_tabs: default_index = 0
else: default_index = available_tabs.index(default_tab)

selected_tab = st.radio("Navigation", options=available_tabs, index=default_index, horizontal=True, label_visibility="collapsed")
neuer_slug = tab_slugs[selected_tab]

if st.query_params.get("tab") != neuer_slug:
    st.query_params["tab"] = neuer_slug
    st.rerun()

st.write("")

# --- TAB 1: ÜBERSICHT ---
if selected_tab == "📊 Übersicht":
    st.subheader("🏆 Team Übersicht")
    if nur_spieler:
        typen_set = set()
        for p in nur_spieler:
            for t in p.get("training", []): typen_set.add(t.get("type", "Training"))
        alle_event_typen = sorted(list(typen_set))
        if not alle_event_typen: alle_event_typen = ["Training"]
        gewaehlte_typen = st.multiselect("Beteiligung filtern nach Event-Typ:", alle_event_typen, default=alle_event_typen)
        
        statistiken = [berechne_statistiken(p, gewaehlte_typen) for p in nur_spieler]
        statistiken.sort(key=lambda x: x["Beteiligung"], reverse=True)
        df = pd.DataFrame(statistiken)
        
        st.dataframe(df.drop(columns=["Badges"]), column_config={
            "Nr.": st.column_config.NumberColumn("Nr.", format="%d"), "Name": st.column_config.TextColumn("Spielername"), 
            "Positionen": st.column_config.TextColumn("Positionen"), "Beteiligung": st.column_config.ProgressColumn("Trainingsbeteiligung", min_value=0, max_value=100, format="%d%%"), 
            "🏃‍♂️ Spiele": st.column_config.NumberColumn("🏃‍♂️ Spiele", format="%d"), "Meilenstein": st.column_config.TextColumn("Meilenstein-Status"), 
            "⚽ Tore": st.column_config.NumberColumn("⚽ Tore", format="%d"), "🅰️ Vorlagen": st.column_config.NumberColumn("🅰️ Vorlagen", format="%d"), "🌟 Scorer": st.column_config.NumberColumn("🌟 Scorer", format="%d")
        }, hide_index=True, use_container_width=True)
        
        st.divider(); st.markdown("### 🥇 Der Trainings-Meilenstein-Club")
        mc1, mc2, mc3 = st.columns(3)
        with mc1:
            st.success("**🥇 Gold-Club (90%+)**")
            for s in statistiken:
                if s["Meilenstein"] == "🥇 Gold-Club": st.write(f"• {s['Name']}")
        with mc2:
            st.warning("**🥈 Silber-Club (75%+)**")
            for s in statistiken:
                if s["Meilenstein"] == "🥈 Silber-Club": st.write(f"• {s['Name']}")
        with mc3:
            st.error("**🥉 Bronze-Club (50%+)**")
            for s in statistiken:
                if s["Meilenstein"] == "🥉 Bronze-Club": st.write(f"• {s['Name']}")
        
        st.write(""); st.divider(); st.markdown("### 👑 Alsterbrüder Leaderboard")
        h_col1, h_col2, h_col3 = st.columns(3)
        top_tr = df.sort_values(by="Beteiligung", ascending=False).iloc[0]
        top_go = df.sort_values(by="⚽ Tore", ascending=False).iloc[0]
        top_sc = df.sort_values(by="🌟 Scorer", ascending=False).iloc[0]
        
        h_col1.metric("🔥 Trainings-König", top_tr["Name"], f"{top_tr['Beteiligung']}% Beteiligung")
        h_col2.metric("🎯 Top-Torjäger", top_go["Name"], f"{top_go['⚽ Tore']} Tore")
        h_col3.metric("🌟 Scorer-König", top_sc["Name"], f"{top_sc['🌟 Scorer']} Pkt ({top_sc['⚽ Tore']}T / {top_sc['🅰️ Vorlagen']}V)")

        st.write(""); st.divider(); st.markdown("### 📊 Team-Statistiken (Fokus-Ansicht)")
        fca_blue = "#1e3a8a"
        fca_yellow = "#facc15"
        fca_colors = ["#1e3a8a", "#facc15", "#2563eb", "#eab308", "#3b82f6"]
        
        df_bet_top5 = df.sort_values(by="Beteiligung", ascending=False).head(5)
        df_tore_top5 = df.sort_values(by="⚽ Tore", ascending=False).head(5)
        df_scorer_top5 = df[df["🌟 Scorer"] > 0].sort_values(by="🌟 Scorer", ascending=False).head(5)
        
        c_col1, c_col2, c_col3 = st.columns(3)
        
        with c_col1:
            fig_bet = px.bar(df_bet_top5, x="Name", y="Beteiligung", text=df_bet_top5["Beteiligung"].apply(lambda x: f"{x}%"), color_discrete_sequence=[fca_blue])
            fig_bet.update_traces(textposition="outside")
            fig_bet.update_layout(xaxis_title=None, yaxis_title=None, margin=dict(l=10, r=10, t=10, b=10), height=280, plot_bgcolor="rgba(0,0,0,0)")
            fig_bet.update_yaxes(showgrid=True, gridcolor="rgba(200,200,200,0.15)", range=[0, 110])
            st.markdown("<p style='text-align:center;'><b>📈 Trainingsbeteiligung (Top 5)</b></p>", unsafe_allow_html=True)
            st.plotly_chart(fig_bet, use_container_width=True, config={'displayModeBar': False})
            
        with c_col2:
            fig_tore = px.bar(df_tore_top5, x="Name", y="⚽ Tore", text="⚽ Tore", color_discrete_sequence=[fca_yellow])
            fig_tore.update_traces(textposition="outside")
            fig_tore.update_layout(xaxis_title=None, yaxis_title=None, margin=dict(l=10, r=10, t=10, b=10), height=280, plot_bgcolor="rgba(0,0,0,0)")
            fig_tore.update_yaxes(showgrid=True, gridcolor="rgba(200,200,200,0.15)", range=[0, max(df_tore_top5["⚽ Tore"].max() + 1 if not df_tore_top5.empty else 5, 5)])
            st.markdown("<p style='text-align:center;'><b>⚽ Top Torschützen (Top 5)</b></p>", unsafe_allow_html=True)
            st.plotly_chart(fig_tore, use_container_width=True, config={'displayModeBar': False})
            
        with c_col3:
            if not df_scorer_top5.empty:
                fig_pie = px.pie(df_scorer_top5, values="🌟 Scorer", names="Name", hole=0.4, color_discrete_sequence=fca_colors)
                fig_pie.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=280, legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
                st.markdown("<p style='text-align:center;'><b>🌟 Scorer-Verteilung (Top 5)</b></p>", unsafe_allow_html=True)
                st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})
            else: 
                st.markdown("<p style='text-align:center;'><b>🌟 Scorer-Verteilung</b></p>", unsafe_allow_html=True)
                st.info("Noch keine Scorer registriert.")
    else: st.info("Keine Spieler im Kader.")

# --- 📜 TAB 1.5: ALSTERBRÜDER TEAM-DNA & PRINZIPIEN ---
if selected_tab == "📜 Team-DNA":
    st.subheader("📜 Alsterbrüder U13 Team-DNA & Leitprinzipien")
    st.caption("Unsere gemeinsamen Taktikregeln, Werthaltungen und positionsspezifischen Aufgaben!")
    
    prinzipien = st.session_state.data.get("principles", [])
    
    def render_prinzip_card(p):
        pos_list = p.get("positions", ["Alle"])
        pos_str = ", ".join(pos_list) if isinstance(pos_list, list) else str(pos_list)
        
        with st.container(border=True):
            col_t1, col_t2 = st.columns([3, 1])
            with col_t1:
                st.markdown(f"#### {p['title']}")
            with col_t2:
                if pos_str != "Alle":
                    st.caption(f"📍 **{pos_str}**")
            st.write(p["desc"])

    dna_tab1, dna_tab2, dna_tab3 = st.tabs([
        "⚽ Auf dem Platz (Taktik)", 
        "🧠 Neben dem Platz (Einstellung)", 
        "📍 Positionsspezifische Aufgaben"
    ])
    
    with dna_tab1:
        kat_platz = [p for p in prinzipien if "Platz" in p.get("category", "")]
        if not kat_platz: st.info("Noch keine taktischen Prinzipien hinterlegt.")
        for p in kat_platz: render_prinzip_card(p)

    with dna_tab2:
        kat_geist = [p for p in prinzipien if "Neben" in p.get("category", "") or "Einstellung" in p.get("category", "")]
        if not kat_geist: st.info("Noch keine Einstellungs-Prinzipien hinterlegt.")
        for p in kat_geist: render_prinzip_card(p)

    with dna_tab3:
        kat_pos = [p for p in prinzipien if "Position" in p.get("category", "")]
        if not kat_pos: 
            st.info("Noch keine positionsspezifischen Aufgaben hinterlegt.")
        else:
            selected_pos = st.selectbox("Position filtern:", ["Alle Positionen"] + POSITIONS)
            
            if selected_pos == "Alle Positionen":
                gefilderte_pos_p = kat_pos
            else:
                gefilderte_pos_p = [p for p in kat_pos if selected_pos in p.get("positions", []) or "Alle" in p.get("positions", [])]
            
            if not gefilderte_pos_p:
                st.info(f"Keine spezifischen Prinzipien für Position '{selected_pos}' gefunden.")
            else:
                for p in gefilderte_pos_p: render_prinzip_card(p)

    # TRAINER-VERWALTUNG
    if is_trainer:
        st.divider()
        st.markdown("### 🛠️ Trainer-Verwaltung: Team-DNA bearbeiten")
        
        tr_p1, tr_p2, tr_p3 = st.tabs([
            "➕ Neues Prinzip hinzufügen", 
            "✏️ Prinzip bearbeiten", 
            "🗑️ Prinzip löschen"
        ])
        
        CAT_OPTIONS = ["⚽ Auf dem Platz (Taktik)", "🧠 Neben dem Platz (Einstellung)", "📍 Positionsspezifisch"]

        with tr_p1:
            with st.form("add_principle_form"):
                p_title = st.text_input("Name des Prinzips (z.B. '⚡ 5-Sekunden-Gegenpressing'):")
                p_cat = st.selectbox("Kategorie:", CAT_OPTIONS)
                p_pos = st.multiselect("Betroffene Positionen (leer lassen = für ALLE Positionen):", POSITIONS, default=[])
                p_desc = st.text_area("Kurze, knackige Erklärung für die Jungs:")
                
                if st.form_submit_button("💾 In die Team-DNA aufnehmen", type="primary"):
                    if not p_title.strip() or not p_desc.strip():
                        st.error("Titel und Beschreibung dürfen nicht leer sein!")
                    else:
                        neue_id = max([p["id"] for p in prinzipien] + [0]) + 1
                        prinzipien.append({
                            "id": neue_id,
                            "title": p_title.strip(),
                            "category": p_cat,
                            "positions": p_pos if p_pos else ["Alle"],
                            "desc": p_desc.strip()
                        })
                        st.session_state.data["principles"] = prinzipien
                        if speichere_daten(st.session_state.data):
                            st.success("Neues Prinzip gespeichert!")
                            st.rerun()

        with tr_p2:
            if not prinzipien:
                st.info("Keine Prinzipien zum Bearbeiten vorhanden.")
            else:
                p_options = {f"[{p['id']}] {p['title']} ({p.get('category', '-')})": p["id"] for p in prinzipien}
                sel_p_label = st.selectbox("Wähle ein Prinzip zum Bearbeiten aus:", list(p_options.keys()))
                sel_p_id = p_options[sel_p_label]
                edit_p = next((x for x in prinzipien if x["id"] == sel_p_id), None)
                
                if edit_p:
                    with st.form("edit_principle_form"):
                        e_title = st.text_input("Titel anpassen:", value=edit_p.get("title", ""))
                        
                        cur_cat_idx = CAT_OPTIONS.index(edit_p["category"]) if edit_p.get("category") in CAT_OPTIONS else 0
                        e_cat = st.selectbox("Kategorie anpassen:", CAT_OPTIONS, index=cur_cat_idx)
                        
                        cur_pos = edit_p.get("positions", ["Alle"])
                        default_pos_selection = [x for x in cur_pos if x in POSITIONS]
                        e_pos = st.multiselect("Positionen anpassen (leer = für ALLE):", POSITIONS, default=default_pos_selection)
                        
                        e_desc = st.text_area("Beschreibung anpassen:", value=edit_p.get("desc", ""), height=100)
                        
                        if st.form_submit_button("💾 Änderungen speichern", type="primary"):
                            edit_p["title"] = e_title.strip()
                            edit_p["category"] = e_cat
                            edit_p["positions"] = e_pos if e_pos else ["Alle"]
                            edit_p["desc"] = e_desc.strip()
                            
                            st.session_state.data["principles"] = prinzipien
                            if speichere_daten(st.session_state.data):
                                st.success("Prinzip erfolgreich aktualisiert!")
                                st.rerun()

        with tr_p3:
            st.markdown("##### 🗂️ Prinzipien unwiderruflich löschen:")
            for p in prinzipien:
                col_d1, col_d2 = st.columns([4, 1])
                pos_info = ", ".join(p.get("positions", ["Alle"]))
                col_d1.write(f"**[{p['id']}] {p['title']}** (`{p.get('category','-')}` | `{pos_info}`)")
                if col_d2.button("🗑️ Löschen", key=f"del_p_{p['id']}"):
                    st.session_state.data["principles"] = [x for x in prinzipien if x["id"] != p["id"]]
                    if speichere_daten(st.session_state.data):
                        st.success("Prinzip gelöscht!")
                        st.rerun()

# --- 🔍 TAB 2: SPIELER-PROFILE (FUT + RADAR-CHART + BADGES + FORMKURVE) ---
if selected_tab == "🔍 Spieler-Profile":
    st.subheader("🔍 Alsterbrüder Spieler-Profile, FUT-Cards & Radar")
    if not nur_spieler:
        st.info("Keine Spieler im Kader hinterlegt.")
    else:
        spieler_namen = sorted([p["name"] for p in nur_spieler])
        selected_player_name = st.selectbox("Wähle einen Spieler aus der U13:", spieler_namen)
        
        p = next(x for x in nur_spieler if x["name"] == selected_player_name)
        stats = berechne_statistiken(p)
        
        pac = int(p.get("base_pac", 75))
        sho = min(int(p.get("base_sho", 60)) + stats["⚽ Tore"], 99)
        pas = min(int(p.get("base_pas", 65)) + stats["🅰️ Vorlagen"], 99)
        dri = int(p.get("base_dri", 70))
        df_val = int(p.get("base_def", 55))
        att_bonus = int((stats["Beteiligung"] - 70) / 4) if stats["Beteiligung"] > 70 else -5
        phy = min(max(int(p.get("base_phy", 65)) + att_bonus, 1), 99)
        ovr = int((pac + sho + pas + dri + df_val + phy) / 6)
        pos_main = p["positions"][0] if p["positions"] else "ZM"
        
        avg_pac = int(sum([sp.get("base_pac", 75) for sp in nur_spieler]) / len(nur_spieler))
        avg_sho = int(sum([sp.get("base_sho", 60) for sp in nur_spieler]) / len(nur_spieler))
        avg_pas = int(sum([sp.get("base_pas", 65) for sp in nur_spieler]) / len(nur_spieler))
        avg_dri = int(sum([sp.get("base_dri", 70) for sp in nur_spieler]) / len(nur_spieler))
        avg_def = int(sum([sp.get("base_def", 55) for sp in nur_spieler]) / len(nur_spieler))
        avg_phy = int(sum([sp.get("base_phy", 65) for sp in nur_spieler]) / len(nur_spieler))

        card_html = f"""
        <div style="background: linear-gradient(135deg, #1e3a8a 0%, #172554 40%, #eab308 100%); 
                    width: 260px; height: 350px; border-radius: 14px; padding: 20px; 
                    color: white; font-family: 'Arial Black', -apple-system, sans-serif; box-shadow: 0 12px 24px rgba(0,0,0,0.4);
                    margin: auto; border: 3px solid #facc15; position: relative; box-sizing: border-box;">
            <div style="font-size: 42px; font-weight: 900; line-height: 36px; float: left; text-align: center; width: 60px; color: #facc15;">
                {ovr}<br><span style="font-size: 13px; font-weight: bold; color: white; background: #1e3a8a; padding: 1px 5px; border-radius: 3px;">{pos_main}</span>
            </div>
            <div style="font-size: 45px; position: absolute; right: 20px; top: 15px; opacity: 0.25;">⚽</div>
            <div style="clear: both; height: 10px;"></div>
            <div style="text-align: center; font-size: 20px; margin-bottom: 12px; border-bottom: 2px solid #facc15; padding-bottom: 4px; text-transform: uppercase; letter-spacing: 1px;">
                {p['name']}
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 13px; line-height: 24px;">
                <div style="width: 45%; text-align: left;">
                    <div><span style="color:#facc15;">{pac}</span> PAC</div>
                    <div><span style="color:#facc15;">{sho}</span> SHO</div>
                    <div><span style="color:#facc15;">{pas}</span> PAS</div>
                </div>
                <div style="width: 45%; text-align: left; border-left: 1px solid rgba(255,255,255,0.2); padding-left: 15px; box-sizing: border-box;">
                    <div><span style="color:#facc15;">{dri}</span> DRI</div>
                    <div><span style="color:#facc15;">{df_val}</span> DEF</div>
                    <div><span style="color:#facc15;">{phy}</span> PHY</div>
                </div>
            </div>
            <div style="position: absolute; bottom: 10px; left: 0; width: 100%; text-align: center; font-size: 11px; font-family: sans-serif; color: rgba(255,255,255,0.7); letter-spacing: 0.5px;">
                FC Alsterbrüder U13 • Nr. {p.get('number', '-')}
            </div>
        </div>
        """
        
        c_card, c_right = st.columns([1, 2])
        with c_card:
            st.components.v1.html(card_html, height=360)
            st.markdown("##### 🎖️ Erfolge & Auszeichnungen:")
            if stats["Badges"]:
                st.write(" ".join([f"`{b}`" for b in stats["Badges"]]))
            else: st.caption("Noch keine Spezial-Badges freigeschaltet.")
            st.info(f"**Alsterbrüder-Rang:** {berechne_level(p.get('points', 0))} (`{p.get('points', 0)} EP`)")

        with c_right:
            st.markdown("### 🕸️ Skill-Profile vs. Team-Durchschnitt")
            categories = ['PAC', 'SHO', 'PAS', 'DRI', 'DEF', 'PHY']
            fig_radar = go.Figure()
            fig_radar.add_trace(go.Scatterpolar(
                r=[pac, sho, pas, dri, df_val, phy, pac],
                theta=categories + [categories[0]], fill='toself', name=p['name'], line_color='#facc15'
            ))
            fig_radar.add_trace(go.Scatterpolar(
                r=[avg_pac, avg_sho, avg_pas, avg_dri, avg_def, avg_phy, avg_pac],
                theta=categories + [categories[0]], fill='toself', name='Team-Schnitt', line_color='#1e3a8a', opacity=0.35
            ))
            fig_radar.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                showlegend=True, height=270, margin=dict(l=20, r=20, t=10, b=10), plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_radar, use_container_width=True, config={'displayModeBar': False})
            
            st.markdown("### 📈 Formkurve (Letzte 5 Einheiten)")
            tr_history = p.get("training", [])
            if tr_history:
                last_5 = tr_history[-5:]
                chart_data = pd.DataFrame({
                    "Datum": [t.get("date", f"E-{i+1}") for i, t in enumerate(last_5)],
                    "Status": [100 if t["present"] else 0 for t in last_5]
                })
                fig_curve = px.line(chart_data, x="Datum", y="Status", markers=True, color_discrete_sequence=["#1e3a8a"])
                fig_curve.update_layout(yaxis=dict(title=None, tickmode="array", tickvals=[0, 100], ticktext=["Abwesend ❌", "Anwesend ⚽"], range=[-15, 115]), xaxis_title=None, height=180, plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=0,r=0,t=10,b=0))
                st.plotly_chart(fig_curve, use_container_width=True, config={'displayModeBar': False})
            else: st.caption("Noch keine Trainingsdaten geloggt.")

# --- TAB 3: SPIELÜBERSICHT ---
if selected_tab == "📖 Spielübersicht":
    st.subheader("📖 Historische Spielübersicht")
    spiele_set = set()
    for p in st.session_state.data["players"]:
        for m in p.get("matches", []):
            if m.get("opponent", "Unbekannt") != "Unbekannt": spiele_set.add((m.get("date", "Unbekannt"), m.get("opponent", "Unbekannt"), m.get("type", "Spiel")))
    spiele_liste = sorted(list(spiele_set), key=lambda x: x[0], reverse=True)
    
    if not spiele_liste: st.info("Es wurden noch keine detaillierten Spiele geloggt.")
    else:
        gewaehltes_spiel_idx = st.selectbox("Wähle ein Match aus:", range(len(spiele_liste)), format_func=lambda i: f"📅 {spiele_liste[i][0]} | [{spiele_liste[i][2]}] gegen {spiele_liste[i][1]}")
        sel_datum, sel_gegner, sel_art = spiele_liste[gewaehltes_spiel_idx]
        sel_res_blau, sel_res_gelb = ["-"]*4, ["-"]*4
        for p in st.session_state.data["players"]:
            p_match = next((m for m in p.get("matches", []) if m.get("date") == sel_datum and m.get("opponent") == sel_gegner), None)
            if p_match:
                sel_res_blau = p_match.get("team_blau_results", p_match.get("team_a_results", ["-"]*4))
                sel_res_gelb = p_match.get("team_gelb_results", p_match.get("team_b_results", ["-"]*4))
                break
        st.divider(); st.markdown(f"### ⚽ {sel_art} gegen **{sel_gegner}**\nSpieltag vom: **{sel_datum}**")
        res_col1, res_col2 = st.columns(2)
        with res_col1:
            st.markdown("<div style='color:#1e3a8a; font-weight:bold; margin-bottom:5px;'>🔵 Team Blau (4 Spiele):</div>", unsafe_allow_html=True)
            txt_blau = " | ".join([f'<b>Sp. {i+1}:</b> {r}' for i, r in enumerate(sel_res_blau)])
            st.markdown(f"<div style='background-color:#eff6ff; border-left:4px solid #1e3a8a; padding:8px; border-radius:4px;'>{txt_blau}</div>", unsafe_allow_html=True)
        with res_col2:
            st.markdown("<div style='color:#b45309; font-weight:bold; margin-bottom:5px;'>🟡 Team Gelb (4 Spiele):</div>", unsafe_allow_html=True)
            txt_gelb = " | ".join([f'<b>Sp. {i+1}:</b> {r}' for i, r in enumerate(sel_res_gelb)])
            st.markdown(f"<div style='background-color:#fffbef; border-left:4px solid #b45309; padding:8px; border-radius:4px;'>{txt_gelb}</div>", unsafe_allow_html=True)
        match_details = []
        for p in nur_spieler:
            p_match = next((m for m in p.get("matches", []) if m.get("date") == sel_datum and m.get("opponent") == sel_gegner), None)
            if p_match:
                t_val = p_match.get("team", "Blau" if p_match.get("played", True) else "Abwesend")
                lbl = "🔵 Team Blau" if t_val == "Blau" else ("🟡 Team Gelb" if t_val == "Gelb" else ("🔄 Ersatzbank" if t_val == "Ersatz" else "❌ Nicht im Kader"))
                match_details.append({"Nr.": int(p["number"]) if str(p["number"]).isdigit() else None, "Name": p["name"], "Team / Status": lbl, "⚽ Tore": p_match.get("goals", 0), "Vorlagen": p_match.get("assists", 0)})
        if match_details:
            df_details = pd.DataFrame(match_details).sort_values(by=["Team / Status", "Nr."], ascending=[True, True], na_position="last").reset_index(drop=True)
            st.write("")
            c1, c2, c3 = st.columns(3)
            c1.metric("Erzielte Tore (Gesamt)", df_details["⚽ Tore"].sum())
            c2.metric("Gesamtvorlagen", df_details["Vorlagen"].sum())
            c3.metric("Spieler aktiv", (df_details["Team / Status"] != "❌ Nicht im Kader").sum())
            st.dataframe(df_details, column_config={"Nr.": st.column_config.NumberColumn("Nr.", format="%d"), "Name": st.column_config.TextColumn("Spielername"), "Team / Status": st.column_config.TextColumn("Einteilung"), "⚽ Tore": st.column_config.NumberColumn("Tore", format="%d"), "Vorlagen": st.column_config.NumberColumn("Vorlagen", format="%d")}, hide_index=True, use_container_width=True)

# --- TAB 3.5: CHALLENGE & TAKTIK-QUIZ (INKLUSIVE ECHTER GEMINI KI) ---
if selected_tab == "🎮 Challenge & Quiz":
    st.subheader("🎮 Alsterbrüder Skill-Challenges & Dynamisches Taktik-Quiz")
    c_sub1, c_sub2 = st.tabs(["⚡ Wochen-Challenge", "🧩 Taktik-Quiz"])
    
    # --- SUBTAB 1: WOCHEN-CHALLENGES ---
    with c_sub1:
        challenge_katalog = st.session_state.data.get("challenge_pool", [])
        active_ch_id = st.session_state.data.get("active_challenge_id", 1)
        aktive_challenge = next((c for c in challenge_katalog if c["id"] == active_ch_id), None)
        if not aktive_challenge and challenge_katalog:
            aktive_challenge = challenge_katalog[0]
            
        if aktive_challenge:
            st.markdown(f"### 🎯 Aktuelle Wochen-Aufgabe: {aktive_challenge['title']}")
            st.markdown(f"**Belohnung:** `+{aktive_challenge.get('points', 25)} EP` für deinen Alsterbrüder-Rang!")
        else:
            st.info("Aktuell ist keine Challenge aktiv.")

        # 👨‍🍳 TRAINER-PANEL FÜR CHALLENGES
        if is_trainer:
            st.markdown("---")
            st.markdown("#### 🛠️ Trainer-Verwaltung für Wochen-Challenges")
            ch_tr_1, ch_tr_2, ch_tr_3, ch_tr_4 = st.tabs([
                "🗓️ Wochen-Challenge aus Katalog wählen", 
                "🤖 Live Gemini-KI nach Ideen fragen",
                "✏️ Neue Challenge manuell erstellen", 
                "🗂️ Challenge-Katalog verwalten"
            ])
            
            with ch_tr_1:
                st.markdown("##### 🗓️ Aktive Wochen-Challenge festlegen")
                if not challenge_katalog: st.warning("Katalog ist leer.")
                else:
                    options_dict = {}
                    for c in challenge_katalog:
                        status = f"⚠️ Bereits {c.get('used_count', 0)}x genutzt" if c.get("used_count", 0) > 0 else "🟢 Neu"
                        label = f"[{c['id']}] {c['title']} ({c.get('points', 25)} EP) | {status}"
                        options_dict[label] = c["id"]
                    
                    cur_label = next((k for k, v in options_dict.items() if v == active_ch_id), list(options_dict.keys())[0])
                    sel_ch_label = st.selectbox("Wähle eine Challenge aus deinem Katalog:", list(options_dict.keys()), index=list(options_dict.keys()).index(cur_label))
                    
                    if st.button("💾 Ausgewählte Challenge für die Woche freischalten", type="primary"):
                        chosen_id = options_dict[sel_ch_label]
                        st.session_state.data["active_challenge_id"] = chosen_id
                        chosen_c = next((c for c in challenge_katalog if c["id"] == chosen_id), None)
                        if chosen_c: chosen_c["used_count"] = chosen_c.get("used_count", 0) + 1
                        if speichere_daten(st.session_state.data):
                            st.success("Wochen-Challenge ist live geschaltet!")
                            st.rerun()

            with ch_tr_2:
                st.markdown("##### 🤖 Echte Google Gemini-KI um neue Challenges bitten")
                if gemini_key:
                    st.caption("🟢 Live Gemini KI aktiv & einsatzbereit")
                else:
                    st.warning("⚠️ Kein Gemini API Key hinterlegt.")
                    
                ch_thema = st.selectbox("Kategorie für die KI:", ["Technik & Ballgefühl", "Kondition & Schnelligkeit", "Teamgeist & Ernährung", "Torschuss & Abschluss"])
                
                if st.button("✨ Live Gemini-KI nach 2 frischen Challenges fragen"):
                    gem_res = generiere_echte_ki_challenges(ch_thema, gemini_key)
                    if gem_res:
                        st.session_state.fresh_gemini_challenges = gem_res
                        st.toast("Echte KI-Challenges empfangen!")

                if "fresh_gemini_challenges" in st.session_state and st.session_state.fresh_gemini_challenges:
                    st.markdown("---")
                    st.markdown("**Die KI schlägt vor:**")
                    for idx, ki_c in enumerate(st.session_state.fresh_gemini_challenges):
                        st.info(f"**Aufgabe:** {ki_c['title']}\n\n• **Belohnung:** `{ki_c.get('points', 25)} EP`")
                        if st.button(f"➕ Challenge #{idx+1} dauerhaft in den Katalog übernehmen", key=f"add_gem_c_{idx}"):
                            neue_id = max([c["id"] for c in challenge_katalog] + [0]) + 1
                            challenge_katalog.append({"id": neue_id, "title": ki_c["title"], "points": int(ki_c.get("points", 25)), "used_count": 0})
                            st.session_state.data["challenge_pool"] = challenge_katalog
                            if speichere_daten(st.session_state.data):
                                st.success("Challenge in deinen Katalog gespeichert!")
                                st.rerun()

            with ch_tr_3:
                st.markdown("##### ✏️ Eigenen Challenge-Entwurf erstellen")
                with st.form("neue_ch_form"):
                    m_title = st.text_input("Aufgabe für die Jungs (z.B. '100x Ball hochhalten'):")
                    m_pts = st.number_input("Punkte (EP):", min_value=5, max_value=100, value=25)
                    if st.form_submit_button("💾 Im Katalog speichern", type="primary"):
                        if not m_title.strip(): st.error("Titel fehlt!")
                        else:
                            neue_id = max([c["id"] for c in challenge_katalog] + [0]) + 1
                            challenge_katalog.append({"id": neue_id, "title": m_title.strip(), "points": int(m_pts), "used_count": 0})
                            st.session_state.data["challenge_pool"] = challenge_katalog
                            if speichere_daten(st.session_state.data):
                                st.success("Neue Challenge im Katalog gespeichert!")
                                st.rerun()

            with ch_tr_4:
                st.markdown("##### 🗂️ Gesamter Challenge-Katalog:")
                for c in challenge_katalog:
                    status = f"⚠️ {c.get('used_count',0)}x genutzt" if c.get('used_count',0) > 0 else "🟢 Neu"
                    is_active = " (🟢 AKTUEL ACTIVE)" if c["id"] == active_ch_id else ""
                    c_col1, c_col2 = st.columns([4, 1])
                    c_col1.write(f"**[{c['id']}] {c['title']}** `{status}`{is_active} (`{c.get('points',25)} EP`)")
                    if c_col2.button("🗑️ Löschen", key=f"del_c_{c['id']}"):
                        st.session_state.data["challenge_pool"] = [x for x in challenge_katalog if x["id"] != c["id"]]
                        if speichere_daten(st.session_state.data):
                            st.success("Challenge gelöscht!")
                            st.rerun()

        # 🏃‍♂️ SPIELER-ABHAKEN
        if logged_in_player and aktive_challenge:
            st.divider()
            c_id_key = f"ch_id_{aktive_challenge['id']}"
            already_done = c_id_key in logged_in_player.get("completed_challenges", [])
            if already_done:
                st.success("🎉 Du hast diese Wochen-Challenge bereits erfolgreich abgehakt! Starker Einsatz!")
            else:
                if st.button("🔥 Ich habe die Challenge geschafft!", type="primary"):
                    logged_in_player["points"] = logged_in_player.get("points", 0) + int(aktive_challenge.get("points", 25))
                    if "completed_challenges" not in logged_in_player: logged_in_player["completed_challenges"] = []
                    logged_in_player["completed_challenges"].append(c_id_key)
                    if speichere_daten(st.session_state.data): st.balloons(); st.success("Punkte gutgeschrieben!"); st.rerun()
        elif not logged_in_player: st.info("🔒 Logge dich in der Sidebar als Spieler ein, um die Challenge abzuhaken.")

    # --- SUBTAB 2: TAKTIK-QUIZ ---
    with c_sub2:
        st.markdown("### 🧩 Taktik-Quiz & Punkte-Konto")
        master_katalog = st.session_state.data.get("quiz_pool", [])
        aktive_ids = st.session_state.data.get("active_quiz_ids", [])
        
        # 🤖 TRAINER-PANEL FÜR QUIZ
        if is_trainer:
            st.markdown("#### 🛠️ Trainer-Verwaltung für Quiz & Fragenkatalog")
            tr_q_tab1, tr_q_tab2, tr_q_tab3, tr_q_tab4 = st.tabs([
                "🗓️ Wochen-Fragen aus Katalog wählen", 
                "🤖 Live Gemini-KI nach Fragen fragen",
                "✏️ Neue Frage manuell erstellen", 
                "🗂️ Gesamten Katalog verwalten"
            ])
            
            with tr_q_tab1:
                st.markdown("##### 🗓️ Aktive Wochen-Fragen auswählen")
                if not master_katalog:
                    st.warning("Dein Fragenkatalog ist noch leer.")
                else:
                    katalog_dict = {}
                    for q in master_katalog:
                        status = f"⚠️ Bereits {q.get('used_count',0)}x genutzt" if q.get('used_count',0) > 0 else "🟢 Neu"
                        lbl = f"[{q['id']}] {q['question']} | {status}"
                        katalog_dict[lbl] = q["id"]
                    
                    default_selected = [k for k, v in katalog_dict.items() if v in aktive_ids]
                    gewaehlte_fragen_labels = st.multiselect(
                        "Aktive Fragen aus dem Katalog für diese Woche bestimmen:", 
                        options=list(katalog_dict.keys()),
                        default=default_selected
                    )
                    
                    if st.button("💾 Wochen-Fragen aktivieren", type="primary"):
                        neue_aktive_ids = [katalog_dict[lbl] for lbl in gewaehlte_fragen_labels]
                        st.session_state.data["active_quiz_ids"] = neue_aktive_ids
                        
                        for n_id in neue_aktive_ids:
                            q_obj = next((x for x in master_katalog if x["id"] == n_id), None)
                            if q_obj: q_obj["used_count"] = q_obj.get("used_count", 0) + 1
                            
                        if speichere_daten(st.session_state.data):
                            st.success(f"Erfolgreich {len(neue_aktive_ids)} Fragen für die Woche aktiviert!")
                            st.rerun()

            with tr_q_tab2:
                st.markdown("##### 🤖 Echte Google Gemini-KI um Taktikfragen bitten")
                if gemini_key:
                    st.caption("🟢 Live Gemini KI aktiv & einsatzbereit")
                else:
                    st.warning("⚠️ Kein Gemini API Key hinterlegt.")
                    
                fokus_thema = st.selectbox("Taktischer Schwerpunkt:", ["Umschaltspiel & Gegenpressing", "Spielaufbau & Raumaufteilung", "Defensivverhalten & Zweikampf", "Flügelspiel & Flanken", "Chancenauswertung"])
                
                if st.button("✨ Live Gemini-KI nach 2 neuen Taktikfragen fragen"):
                    gem_q_res = generiere_echte_ki_fragen(fokus_thema, gemini_key)
                    if gem_q_res:
                        st.session_state.fresh_gemini_questions = gem_q_res
                        st.toast("Echte KI-Taktikfragen empfangen!")

                if "fresh_gemini_questions" in st.session_state and st.session_state.fresh_gemini_questions:
                    st.markdown("---")
                    st.markdown("**Die KI schlägt vor:**")
                    for idx, ki_q in enumerate(st.session_state.fresh_gemini_questions):
                        st.info(f"**Frage:** {ki_q['question']}\n\n• **Optionen:** {', '.join(ki_q['options'])}\n\n• **Lösung:** {ki_q['correct']}")
                        if st.button(f"➕ KI-Frage #{idx+1} dauerhaft in den Katalog speichern", key=f"add_gem_q_{idx}"):
                            neue_id = max([q["id"] for q in master_katalog] + [0]) + 1
                            master_katalog.append({
                                "id": neue_id,
                                "question": ki_q["question"],
                                "options": ki_q["options"],
                                "correct": ki_q["correct"],
                                "points": ki_q.get("points", 10),
                                "used_count": 0
                            })
                            st.session_state.data["quiz_pool"] = master_katalog
                            if speichere_daten(st.session_state.data):
                                st.success("Frage in deinen Katalog gespeichert!")
                                st.rerun()

            with tr_q_tab3:
                st.markdown("##### ✏️ Eigenen Frage-Entwurf zum Katalog hinzufügen")
                with st.form("neue_frage_form"):
                    m_q = st.text_input("Deine Taktikfrage:")
                    m_a = st.text_input("Antwort A:")
                    m_b = st.text_input("Antwort B:")
                    m_c = st.text_input("Antwort C:")
                    m_correct = st.selectbox("Richtige Option:", [m_a, m_b, m_c])
                    m_pts = st.number_input("Punkte für richtige Antwort:", min_value=5, max_value=50, value=10)
                    
                    if st.form_submit_button("💾 Im Katalog speichern", type="primary"):
                        if not m_q or not m_a or not m_b or not m_c:
                            st.error("Bitte alle Felder ausfüllen!")
                        else:
                            neue_id = max([q["id"] for q in master_katalog] + [0]) + 1
                            master_katalog.append({
                                "id": neue_id,
                                "question": m_q.strip(),
                                "options": [f"A) {m_a.strip()}", f"B) {m_b.strip()}", f"C) {m_c.strip()}"],
                                "correct": m_correct.strip() if m_correct.startswith("A)") or m_correct.startswith("B)") or m_correct.startswith("C)") else f"A) {m_correct.strip()}",
                                "points": int(m_pts),
                                "used_count": 0
                            })
                            st.session_state.data["quiz_pool"] = master_katalog
                            if speichere_daten(st.session_state.data):
                                st.success("Neue Frage im Katalog gespeichert!")
                                st.rerun()

            with tr_q_tab4:
                st.markdown("##### 🗂️ Alle Fragen im Gesamtkatalog:")
                if not master_katalog: st.write("Katalog ist leer.")
                else:
                    for q in master_katalog:
                        status = f"⚠️ {q.get('used_count',0)}x genutzt" if q.get('used_count',0) > 0 else "🟢 Neu"
                        is_active_str = " (🟢 DIESE WOCHE AKTIV)" if q["id"] in aktive_ids else ""
                        col_q1, col_q2 = st.columns([4, 1])
                        col_q1.write(f"**[{q['id']}] {q['question']}** `{status}`{is_active_str} (`{q.get('points', 10)} EP`) - *Lösung:* {q['correct']}")
                        if col_q2.button("🗑️ Löschen", key=f"del_q_{q['id']}"):
                            st.session_state.data["quiz_pool"] = [x for x in master_katalog if x["id"] != q["id"]]
                            st.session_state.data["active_quiz_ids"] = [x for x in aktive_ids if x != q["id"]]
                            if speichere_daten(st.session_state.data):
                                st.success("Frage gelöscht!")
                                st.rerun()
            st.divider()

        # 🏃‍♂️ SPIELER-ANSICHT (NUR AKTIVE WOCHEN-FRAGEN BEANTWORTEN)
        aktive_fragen = [q for q in master_katalog if q["id"] in aktive_ids]
        
        if not aktive_fragen:
            st.info("Für diese Woche stehen noch keine aktiven Taktik-Fragen bereit. Schau bald wieder rein!")
        else:
            if logged_in_player:
                solved_ids = logged_in_player.get("solved_quizzes", [])
                unsolved_questions = [q for q in aktive_fragen if q["id"] not in solved_ids]
                
                if not unsolved_questions:
                    st.success("🏆 Du hast bereits ALLE aktiven Taktikfragen für diese Woche gelöst! Super gemacht!")
                else:
                    st.markdown(f"**Hi {logged_in_player['name']}, hier sind deine offenen Wochen-Fragen:**")
                    
                    user_answers = {}
                    for q in unsolved_questions:
                        st.markdown(f"##### ❓ {q['question']} (`+{q.get('points', 10)} EP`)")
                        user_answers[q["id"]] = st.radio("Wähle deine Antwort:", q["options"], key=f"user_q_{q['id']}", index=None)
                        st.write("")
                    
                    if st.button("🎯 Antworten auswerten & EP kassieren", type="primary"):
                        neue_punkte = 0
                        neu_geloest = []
                        
                        for q in unsolved_questions:
                            ans = user_answers.get(q["id"])
                            if ans and ans.strip().lower() == q["correct"].strip().lower():
                                neue_punkte += q.get("points", 10)
                                neu_geloest.append(q["id"])
                        
                        if neue_punkte > 0:
                            logged_in_player["points"] = logged_in_player.get("points", 0) + neue_punkte
                            if "solved_quizzes" not in logged_in_player: logged_in_player["solved_quizzes"] = []
                            logged_in_player["solved_quizzes"].extend(neu_geloest)
                            
                            if speichere_daten(st.session_state.data):
                                st.balloons()
                                st.success(f"🎉 Richtig gewusst! Du hast `{neue_punkte} EP` erhalten! Dein neues Level liegt bei `{berechne_level(logged_in_player['points'])}`.")
                                st.rerun()
                        else:
                            st.error("❌ Das war leider noch nicht ganz richtig. Lies dir die Fragen nochmal genau durch!")
            else:
                st.info("🔒 Logge dich in der Sidebar als Spieler ein, um die Taktikfragen zu beantworten und Erfahrungspunkte zu sammeln.")

# --- TAB 3.6: GESCHÜTZTE VIDEOANALYSE ---
if selected_tab == "🎥 Videoanalyse":
    st.subheader("🎥 Taktische Videoanalyse & Coaching-Notizen")
    
    if is_trainer and not logged_in_player:
        st.markdown("#### 👨‍🍳 Trainer-Panel: Video für Spieler hinterlegen")
        sel_v_player = st.selectbox("Wähle den Spieler aus:", sorted([sp["name"] for sp in nur_spieler]))
        p_obj = next(x for x in nur_spieler if x["name"] == sel_v_player)
        
        v_url = st.text_input("Video-URL (YouTube, Vimeo oder MP4-Link):", value=p_obj.get("video_url", ""))
        v_notes = st.text_area("Deine Coaching-Notizen für ihn:", value=p_obj.get("video_notes", ""), height=150)
        
        if st.button("🎥 Videoanalyse für Spieler speichern", type="primary"):
            p_obj["video_url"] = v_url.strip()
            p_obj["video_notes"] = v_notes.strip()
            if speichere_daten(st.session_state.data):
                st.success(f"Videoanalyse für {sel_v_player} erfolgreich gesichert!")
                st.rerun()
                
    elif logged_in_player:
        st.markdown(f"#### 👋 Hi {logged_in_player['name']}, hier ist deine persönliche Analyse:")
        
        c_v1, c_v2 = st.columns([2, 1])
        with c_v1:
            VIDEO_DIR = "videos"
            lokales_video = os.path.join(VIDEO_DIR, f"{logged_in_player['name'].lower()}.mp4")
            if os.path.exists(lokales_video):
                st.video(lokales_video)
            elif logged_in_player.get("video_url"):
                try: st.video(logged_in_player["video_url"])
                except: st.error("Das Video konnte nicht geladen werden. Bitte prüfe den Link.")
            else:
                st.info("Für dich wurde aktuell noch kein neues Video hochgeladen. Schau nach dem nächsten Spiel wieder rein!")
                
        with c_v2:
            st.markdown("##### 📝 Trainer-Notizen für dich:")
            if logged_in_player.get("video_notes"):
                st.info(logged_in_player["video_notes"])
            else:
                st.write("Noch keine Notizen eingetragen.")

# --- TAB 4: KADER (TRAINER ONLY) ---
if selected_tab == "🏃‍♂️ Kader" and is_trainer:
    st.subheader("🏃‍♂️ Kader, Positions-Prios & PIN-Verwaltung")
    st.info("💡 Tipp: In der Spalte **PIN** kannst du jedem Spieler ein 4-stelliges Geheim-Passwort für sein Video- & Challenge-Login zuteilen.")
    kader_liste = []
    for p in st.session_state.data["players"]:
        pos = p.get("positions", [])
        kader_liste.append({
            "ID": str(p["id"]), "Nr.": int(p.get("number", "")) if str(p.get("number", "")).isdigit() else None, 
            "Name": p["name"], "Rolle": p.get("role", "Spieler"), 
            "Prio 1": pos[0] if len(pos) > 0 else "-", "Prio 2": pos[1] if len(pos) > 1 else "-", 
            "Prio 3": pos[2] if len(pos) > 2 else "-", "Prio 4": pos[3] if len(pos) > 3 else "-", 
            "Prio 5": pos[4] if len(pos) > 4 else "-",
            "PAC": int(p.get("base_pac", 75)), "SHO": int(p.get("base_sho", 60)), 
            "PAS": int(p.get("base_pas", 65)), "DRI": int(p.get("base_dri", 70)), 
            "DEF": int(p.get("base_def", 55)), "PHY": int(p.get("base_phy", 65)),
            "PIN": p.get("pin", "")
        })
    kader_df = pd.DataFrame(kader_liste)
    if not kader_df.empty: kader_df = kader_df.sort_values(by="Nr.", na_position="last").reset_index(drop=True)
    
    editiertes_kader = st.data_editor(kader_df, hide_index=True, column_config={
        "ID": None, "Rolle": st.column_config.SelectboxColumn(options=["Spieler", "Trainer"], required=True), 
        "Nr.": st.column_config.NumberColumn("Nr.", format="%d"), 
        "Prio 1": st.column_config.SelectboxColumn(options=["-"] + POSITIONS), 
        "Prio 2": st.column_config.SelectboxColumn(options=["-"] + POSITIONS),
        "Prio 3": st.column_config.SelectboxColumn(options=["-"] + POSITIONS),
        "Prio 4": st.column_config.SelectboxColumn(options=["-"] + POSITIONS),
        "Prio 5": st.column_config.SelectboxColumn(options=["-"] + POSITIONS),
        "PIN": st.column_config.TextColumn("PIN (Login)", max_chars=10)
    }, num_rows="dynamic", use_container_width=True)
    
    if st.button("💾 Alle Änderungen im Kader speichern", type="primary"):
        neuer_kader = []
        for index, row in editiertes_kader.iterrows():
            row_id, pos_liste = row.get("ID"), []
            for col in ["Prio 1", "Prio 2", "Prio 3", "Prio 4", "Prio 5"]:
                if row.get(col, "-") != "-": pos_liste.append(row.get(col))
            nr_str = str(int(float(row.get("Nr.")))) if pd.notna(row.get("Nr.")) else ""
            orig = next((p for p in st.session_state.data["players"] if str(p["id"]) == str(row_id)), None) if pd.notna(row_id) else None
            
            if orig:
                orig["name"], orig["role"], orig["number"], orig["positions"] = str(row["Name"]), str(row["Rolle"]), nr_str, (pos_liste if row["Rolle"] == "Spieler" else [])
                orig["pin"] = str(row["PIN"]).strip()
                if row["Rolle"] == "Spieler":
                    orig["base_pac"], orig["base_sho"], orig["base_pas"] = int(row["PAC"]), int(row["SHO"]), int(row["PAS"])
                    orig["base_dri"], orig["base_def"], orig["base_phy"] = int(row["DRI"]), int(row["DEF"]), int(row["PHY"])
                neuer_kader.append(orig)
            elif str(row["Name"]).strip():
                neuer_kader.append({
                    "id": max([p["id"] for p in neuer_kader] + [p["id"] for p in st.session_state.data["players"]] + [0]) + 1, 
                    "name": str(row["Name"]), "role": str(row["Rolle"]), "number": nr_str, "positions": pos_liste, "training": [], "matches": [],
                    "pin": str(row["PIN"]).strip(), "video_url": "", "video_notes": "", "points": 0, "completed_challenges": [], "solved_quizzes": [],
                    "base_pac": int(row["PAC"] or 75), "base_sho": int(row["SHO"] or 60), "base_pas": int(row["PAS"] or 65),
                    "base_dri": int(row["DRI"] or 70), "base_def": int(row["DEF"] or 55), "base_phy": int(row["PHY"] or 65)
                })
        st.session_state.data["players"] = neuer_kader
        if speichere_daten(st.session_state.data): st.success("Kader erfolgreich in der Cloud aktualisiert!")

# --- TAB 5: SPIEL LOGGEN ---
if selected_tab == "⚽ Spiel loggen" and is_trainer:
    st.subheader("⚽ Spieltag Statistiken loggen")
    c_meta1, c_meta2, c_meta3 = st.columns(3); m_datum = c_meta1.date_input("Datum Spiel", datetime.today()); m_type = c_meta2.selectbox("Spielart", ["Ligaspiel", "Testspiel"]); m_opponent = c_meta3.text_input("Gegner", placeholder="z.B. VfL Hamburg")
    col_blau, col_gelb = st.columns(2)
    with col_blau: st.markdown("<b>🔵 Team Blau Ergebnisse</b>", unsafe_allow_html=True); sub_b = st.columns(4); m_b1 = sub_b[0].text_input("Sp. 1", "0:0", key="b1"); m_b2 = sub_b[1].text_input("Sp. 2", "0:0", key="b2"); m_b3 = sub_b[2].text_input("Sp. 3", "0:0", key="b3"); m_b4 = sub_b[3].text_input("Sp. 4", "0:0", key="b4")
    with col_gelb: st.markdown("<b>🟡 Team Gelb Ergebnisse</b>", unsafe_allow_html=True); sub_g = st.columns(4); m_g1 = sub_g[0].text_input("Sp. 1", "0:0", key="g1"); m_g2 = sub_g[1].text_input("Sp. 2", "0:0", key="g2"); m_g3 = sub_g[2].text_input("Sp. 3", "0:0", key="g3"); m_g4 = sub_g[3].text_input("Sp. 4", "0:0", key="g4")
    st.divider(); spiel_liste = []
    for p in nur_spieler:
        planung = st.session_state.zuweisungen.get(str(p["id"]), "🤖 KI entscheidet")
        default_status = "❌ Nicht in Kader" if planung == "❌ Abwesend" else ("🔵 Team Blau" if planung == "🤖 KI entscheidet" else planung)
        spiel_liste.append({"ID": str(p["id"]), "Nr.": int(p["number"]) if str(p["number"]).isdigit() else None, "Name": p["name"], "Team / Status": default_status, "⚽ Tore": 0, "Vorlagen": 0})
    spiel_df = pd.DataFrame(spiel_liste)
    if not spiel_df.empty: spiel_df = spiel_df.sort_values(by="Nr.", na_position="last").reset_index(drop=True)
    editiertes_spiel = st.data_editor(spiel_df, disabled=["ID", "Nr.", "Name"], hide_index=True, column_config={"ID": None, "Nr.": st.column_config.NumberColumn("Nr.", format="%d"), "Team / Status": st.column_config.SelectboxColumn(options=["🔵 Team Blau", "🟡 Team Gelb", "🔄 Ersatzbank", "❌ Nicht in Kader"], required=True), "⚽ Tore": st.column_config.NumberColumn(min_value=0, format="%d"), "Vorlagen": st.column_config.NumberColumn(min_value=0, format="%d")}, use_container_width=True)
    if st.button("Spieltag speichern", type="primary"):
        if not m_opponent.strip(): st.error("Gegner fehlt!")
        else:
            r_blau = [m_b1.strip() or "-", m_b2.strip() or "-", m_b3.strip() or "-", m_b4.strip() or "-"]
            r_gelb = [m_g1.strip() or "-", m_g2.strip() or "-", m_g3.strip() or "-", m_g4.strip() or "-"]
            for index, row in editiertes_spiel.iterrows():
                spieler = next(p for p in st.session_state.data["players"] if str(p["id"]) == str(row["ID"]))
                if "matches" not in spieler: spieler["matches"] = []
                status = row["Team / Status"]
                db_team = "Blau" if status == "🔵 Team Blau" else ("Gelb" if status == "🟡 Team Gelb" else ("Ersatz" if status == "🔄 Ersatzbank" else "Abwesend"))
                act = db_team in ["Blau", "Gelb", "Ersatz"]
                spieler["matches"].append({"date": str(m_datum), "opponent": m_opponent.strip(), "type": m_type, "team_blau_results": r_blau, "team_gelb_results": r_gelb, "played": act, "team": db_team, "goals": int(row["⚽ Tore"]) if act else 0, "assists": int(row["Vorlagen"]) if act else 0})
            if speichere_daten(st.session_state.data): st.success("Spieltag erfolgreich in der Cloud archiviert!")

# --- TAB 6: KI TWIN-TEAMS + VOLLSTÄNDIGE ALGORITHMIK ---
if selected_tab == "🤖 KI Twin-Teams" and is_trainer:
    st.subheader("🤖 KI Twin-Aufstellung")
    st.markdown("#### 📋 Kader-Zuweisung")
    zuweisungs_liste = []
    for p in nur_spieler:
        zuweisungs_liste.append({"ID": str(p["id"]), "Nr.": int(p["number"]) if str(p["number"]).isdigit() else None, "Name": p["name"], "Hauptposition": p["positions"][0] if p["positions"] else "-", "Zuweisung / Status": st.session_state.zuweisungen.get(str(p["id"]), "🤖 KI entscheidet")})
    df_zuweisung = pd.DataFrame(zuweisungs_liste)
    if not df_zuweisung.empty: df_zuweisung = df_zuweisung.sort_values(by="Nr.", na_position="last").reset_index(drop=True)
    editiertes_kader_zuweisung = st.data_editor(df_zuweisung, hide_index=True, disabled=["ID", "Nr.", "Name", "Hauptposition"], column_config={"ID": None, "Nr.": st.column_config.NumberColumn("Nr.", format="%d"), "Zuweisung / Status": st.column_config.SelectboxColumn(options=["🤖 KI entscheidet", "🔵 Team Blau", "🟡 Team Gelb", "🔄 Ersatzbank", "❌ Abwesend"], required=True)}, use_container_width=True)

    btn_col1, btn_col2 = st.columns(2)
    berechnen_klick = btn_col1.button("🤖 KI Aufstellung berechnen", type="primary", use_container_width=True)
    alternative_klick = btn_col2.button("🔄 Alternative Variante berechnen", type="secondary", use_container_width=True)

    if berechnen_klick or alternative_klick:
        blau_fest, gelb_fest, ki_pool, bench_fest = [], [], [], []
        for index, row in editiertes_kader_zuweisung.iterrows():
            p_id, status = int(row["ID"]), row["Zuweisung / Status"]
            st.session_state.zuweisungen[str(p_id)] = status
            if status == "❌ Abwesend": continue
            p_data = next((p for p in nur_spieler if p["id"] == p_id), None)
            if p_data:
                stats = berechne_statistiken(p_data); c_info = {"id": p_id, "name": p_data["name"], "nr": p_data.get("number", ""), "positions": p_data.get("positions", ["ZM"]), "beteiligung": stats["Beteiligung"]}
                if status == "🔵 Team Blau": blau_fest.append(c_info)
                elif status == "🟡 Team Gelb": gelb_fest.append(c_info)
                elif status == "🤖 KI entscheidet": ki_pool.append(c_info)
                elif status == "🔄 Ersatzbank": bench_fest.append(c_info)

        if alternative_klick: random.shuffle(blau_fest); random.shuffle(gelb_fest); random.shuffle(ki_pool); st.toast("Alternative geladen!")
        else: blau_fest.sort(key=lambda x: x["beteiligung"], reverse=True); gelb_fest.sort(key=lambda x: x["beteiligung"], reverse=True); ki_pool.sort(key=lambda x: x["beteiligung"], reverse=True)

        def waehle_spieler_taktik_mix(praeferenzen, team_id, rollen_name, is_alt):
            hoechster_score, bester = -1, None
            pool = (blau_fest + ki_pool) if team_id == "Blau" else (gelb_fest + ki_pool)
            for c in pool:
                if c["name"] in genutzte_namen: continue
                max_b = 0
                for pr in praeferenzen:
                    if pr in c["positions"]: b = 100 - (c["positions"].index(pr) * 20); max_b = max(max_b, b)
                    else:
                        for al in c["positions"]:
                            if sind_verwandt(pr, al): b = 100 - (c["positions"].index(al) * 20) - 25; max_b = max(max_b, b)
                score = (c["beteiligung"] * 0.55) + (max_b * 0.45)
                if c in (blau_fest if team_id == "Blau" else gelb_fest): score += 1000
                if is_alt: score += random.uniform(-3, 3)
                if score > hoechster_score: hoechster_score = score; bester = c
            if bester:
                genutzte_namen.add(bester["name"])
                st.session_state[f"raw_{team_id.lower()[0]}_{rollen_name}"] = bester["name"]
                nr_b = f'<span class="nr">#{bester["nr"]}</span>' if bester["nr"] else ''
                return f'<div class="player" id="{team_id}_{rollen_name}" draggable="true" ondragstart="drag(event)">{nr_b}<span class="name-text">{bester["name"]}</span></div>'
            st.session_state[f"raw_{team_id.lower()[0]}_{rollen_name}"] = "-"
            return ""

        rollen = [("TW", ["TW"]), ("ST", ["ST", "LF", "RF", "ZOM"]), ("LM", ["LM", "LF", "ZM"]), ("ZM", ["ZM", "ZDM", "ZOM"]), ("RM", ["RM", "RF", "ZM"]), ("IV (L)", ["IV", "LV", "ZDM"]), ("IV (R)", ["IV", "RV", "ZDM"])]
        t_blau, t_gelb, genutzte_namen = {}, {}, set(); is_alt = bool(alternative_klick)
        for i, (r_name, pr) in enumerate(rollen):
            if i % 2 == 0: t_blau[r_name] = waehle_spieler_taktik_mix(pr, "Blau", r_name, is_alt); t_gelb[r_name] = waehle_spieler_taktik_mix(pr, "Gelb", r_name, is_alt)
            else: t_gelb[r_name] = waehle_spieler_taktik_mix(pr, "Gelb", r_name, is_alt); t_blau[r_name] = waehle_spieler_taktik_mix(pr, "Blau", r_name, is_alt)

        ersatz = [c for c in blau_fest + gelb_fest + ki_pool + bench_fest if c["name"] not in genutzte_namen]
        b_blau_list = [f'<div class="player" id="bBlau_{i}" draggable="true" ondragstart="drag(event)">{"#"+x["nr"] if x["nr"] else ""}<span class="name-text">{x["name"]}</span></div>' for i, x in enumerate(ersatz)]
        b_gelb_list = [f'<div class="player" id="bGelb_{i}" draggable="true" ondragstart="drag(event)">{"#"+x["nr"] if x["nr"] else ""}<span class="name-text">{x["name"]}</span></div>' for i, x in enumerate(ersatz)]
        
        st.session_state.pitch_blau_html = generiere_pitch_html(t_blau, "".join(b_blau_list), "Team Blau")
        st.session_state.pitch_gelb_html = generiere_pitch_html(t_gelb, "".join(b_gelb_list), "Team Gelb")

    if "pitch_blau_html" in st.session_state:
        st.info("💡 Taktikboard aktiv: Karten können per Drag & Drop verschoben werden.")
        c_p1, c_p2 = st.columns(2)
        with c_p1: st.markdown("### 🔵 Team Blau"); st.components.v1.html(st.session_state.pitch_blau_html, height=460)
        with c_p2: st.markdown("### 🟡 Team Gelb"); st.components.v1.html(st.session_state.pitch_gelb_html, height=460)
    else: st.warning("Aufstellung muss berechnet werden.")

# --- TAB 7: SPIELERPLUS IMPORT (TRAINER ONLY) ---
if selected_tab == "📥 Import (SpielerPlus)" and is_trainer:
    st.subheader("📥 Massen-Import (SpielerPlus CSV)")
    hochgeladene_datei = st.file_uploader("Datei auswählen", type=["csv", "xlsx"])
    if hochgeladene_datei is not None:
        try:
            df_import = pd.read_csv(hochgeladene_datei, sep=";") if hochgeladene_datei.name.endswith('.csv') else pd.read_excel(hochgeladene_datei)
            st.dataframe(df_import.head(2)); spalten = df_import.columns.tolist()
            
            def f_sp(w):
                for i, s in enumerate(spalten):
                    if s.lower() in w: return i
                for i, s in enumerate(spalten):
                    if any(x in s.lower() for x in w) and "team" not in s.lower(): return i
                return 0
                
            c1, c2, c3, c4 = st.columns(4)
            name_sp = c1.selectbox("Name", spalten, index=f_sp(["user_name", "spielername", "spieler", "name"]))
            tail_sp = c2.selectbox("Beteiligung", spalten, index=f_sp(["user_participation", "zusage", "status"]))
            dat_sp = c3.selectbox("Datum", spalten, index=f_sp(["event_date_start", "datum", "date"]))
            typ_sp = c4.selectbox("Event-Typ", spalten, index=f_sp(["event_type", "typ", "art"]))
            
            if st.button("Verarbeiten", type="primary"):
                imp = 0
                for index, row in df_import.iterrows():
                    p_n, p_t, p_d, p_y = str(row[name_sp]).strip(), str(row[tail_sp]).strip().lower(), str(row[dat_sp]).strip().split(" ")[0], str(row[typ_sp]).strip()
                    erfolgs_woerter = ["status_confirmed", "ja", "zugesagt", "anwesend", "erschienen", "teilgenommen", "1", "true", "yes"]
                    anw = any(wort in p_t for wort in erfolgs_woerter)
                    
                    sp = next((x for x in st.session_state.data["players"] if p_n.lower() == x["name"].lower()), None)
                    if not sp: 
                        sp = {"id": max([x["id"] for x in st.session_state.data["players"]]+[0])+1, "name": p_n, "role": "Spieler", "number": "", "positions": ["ZM"], "training": [], "matches": [], "pin": "", "video_url": "", "video_notes": "", "points": 0, "completed_challenges": [], "solved_quizzes": []}
                        st.session_state.data["players"].append(sp)
                    if "training" not in sp: sp["training"] = []
                    bestehender_eintrag = next((t for t in sp["training"] if t.get('date') == p_d and t.get('type') == p_y), None)
                    if bestehender_eintrag: bestehender_eintrag["present"] = anw
                    else: sp["training"].append({"date": p_d, "type": p_y, "present": anw})
                    imp += 1
                if speichere_daten(st.session_state.data): st.toast("🎉 Daten erfolgreich aktualisiert!", icon="🚀"); st.success(f"🎉 Erfolg! {imp} Einträge wurden verarbeitet.")
        except Exception as e: st.error(f"Fehler: {e}")

    st.write(""); st.divider(); st.markdown("### ⚠️ Gefahrenzone")
    if st.button("💥 Alle Trainingsdaten unwiderruflich löschen", type="secondary"):
        for p in st.session_state.data["players"]: p["training"] = []
        if speichere_daten(st.session_state.data): st.toast("🔥 Gelöscht!", icon="🗑️"); st.success("Trainingszähler steht wieder auf 0%!")

# --- TAB 8: TRAININGSPLANER + ÜBUNGSDATENBANK VERWALTUNG ---
if selected_tab == "📋 Trainingsplaner" and is_trainer:
    st.subheader("📋 Interaktiver Alsterbrüder 5-Phasen-Trainingsplaner")
    planer_sub_tabs = ["⚽ Einheit generieren", "🗂️ Übungsdatenbank verwalten"]
    p_tab_gen, p_tab_db = st.tabs(planer_sub_tabs)
    with p_tab_gen:
        st.markdown("#### 🤖 Nächste Trainingseinheit zusammenwürfeln")
        alle_schwerpunkte = sorted(list(set(u.get("schwerpunkt", "Allgemein") for u in st.session_state.data["exercises"])))
        if not alle_schwerpunkte: alle_schwerpunkte = ["Passspiel", "Torschuss", "Umschalten", "Defensive"]
        gewaehlter_schwerpunkt = st.selectbox("Fokus/Schwerpunkt für das heutige Training:", alle_schwerpunkte)
        if st.button("🎲 Einheit auswürfeln", type="primary"):
            generierter_plan = {}
            for phase in TRAINING_PHASES:
                pool = [u for u in st.session_state.data["exercises"] if u["phase"] == phase]
                schwerpunkt_pool = [u for u in pool if u.get("schwerpunkt", "").lower() == gewaehlter_schwerpunkt.lower()]
                finaler_pool = schwerpunkt_pool if schwerpunkt_pool else pool
                if finaler_pool: generierter_plan[phase] = random.choice(finaler_pool)
            st.session_state.aktueller_trainingsplan = generierter_plan
        if "aktueller_trainingsplan" in st.session_state:
            st.success(f"🔥 Fertig! Schwerpunkt: **{gewaehlter_schwerpunkt}**")
            for phase in TRAINING_PHASES:
                if phase in st.session_state.aktueller_trainingsplan:
                    u = st.session_state.aktueller_trainingsplan[phase]
                    with st.expander(f"➔ {phase}: {u['name']} ({u.get('spieler', 'Alle')} Spieler)", expanded=True):
                        col_text, col_gfx = st.columns([1, 1])
                        with col_text:
                            st.markdown(f"**🎯 Schwerpunkt:** {u.get('schwerpunkt', '-')}\n\n**🛠️ Aufbau & Regeln:**\n{u['aufbau']}")
                        with col_gfx:
                            gfx_url = u.get("grafik", "").strip()
                            if gfx_url:
                                if "[docs.google.com/presentation](https://docs.google.com/presentation)" in gfx_url: st.components.v1.html(f'<iframe src="{gfx_url}" frameborder="0" width="100%" height="220" allowfullscreen="true"></iframe>', height=230)
                                elif "drive.google.com" in gfx_url or gfx_url.lower().endswith(".pdf"): st.components.v1.html(f'<iframe src="{gfx_url}" width="100%" height="280" style="border:none;" allowfullscreen="true"></iframe>', height=290)
                                else: st.image(gfx_url, caption="Übungsgrafik", use_container_width=True)
                            else: st.info("Keine Grafik hinterlegt.")
                else: st.warning(f"Keine Übung für Phase '{phase}' gefunden.")
    with p_tab_db:
        st.markdown("#### 🗂️ Eure Übungssammlung")
        with st.expander("➕ Neue Übung zur Liste hinzufügen", expanded=False):
            with st.form("neue_uebung_form"):
                u_name = st.text_input("Name der Übung:")
                u_phase = st.selectbox("Trainings-Phase:", TRAINING_PHASES)
                u_focus = st.text_input("Schwerpunkt (Tag):")
                u_players = st.text_input("Spieleranzahl / Organisation:")
                u_setup = st.text_area("Aufbau, Ablauf und Coaching-Punkte:")
                u_gfx = st.text_input("Google Slides Embed-Link / Google Drive PDF-Vorschau:")
                if st.form_submit_button("💾 Übung dauerhaft speichern", type="primary"):
                    if not u_name.strip(): st.error("Der Name der Übung fehlt!")
                    else:
                        neue_id = max([x["id"] for x in st.session_state.data["exercises"]] + [0]) + 1
                        st.session_state.data["exercises"].append({"id": neue_id, "name": u_name.strip(), "phase": u_phase, "schwerpunkt": u_focus.strip(), "spieler": u_players.strip(), "aufbau": u_setup.strip(), "grafik": u_gfx.strip()})
                        if speichere_daten(st.session_state.data): st.success("Übung hinzugefügt!"); st.rerun()
        if st.session_state.data["exercises"]:
            ex_df = pd.DataFrame(st.session_state.data["exercises"])
            editiere_db = st.data_editor(ex_df, disabled=["id"], hide_index=True, use_container_width=True, num_rows="dynamic")
            if st.button("💾 Tabellen-Änderungen in der Datenbank sichern"):
                neue_liste = []
                for index, row in editiere_db.iterrows():
                    if str(row["name"]).strip(): neue_liste.append({"id": int(row["id"]) if pd.notna(row["id"]) else random.randint(1000,9999), "name": str(row["name"]), "phase": str(row["phase"]), "schwerpunkt": str(row["schwerpunkt"]), "spieler": str(row["spieler"]), "aufbau": str(row["aufbau"]), "grafik": str(row["grafik"])})
                st.session_state.data["exercises"] = neue_liste
                if speichere_daten(st.session_state.data): st.success("Übungsdatenbank aktualisiert!"); st.rerun()
        else: st.info("Übungsdatenbank leer.")

# --- TAB 9: LIGA-ZENTRALE ---
if selected_tab == "🏆 Liga-Tabelle":
    st.subheader("🏆 Liga-Zentrale (U12 Bezirksliga 36)")
    st.link_button("🌐 Offizielle fussball.de Tabelle öffnen", "[https://www.fussball.de/spieltagsuebersicht/u12-bzl-36-fruehjahr-bezirksebene-hamburg-d-junioren-bezirksliga-d-junioren-saison2526-hamburg/-/staffel/0306E7FA78000005VS5489BUVV5FEO72-G#!/](https://www.fussball.de/spieltagsuebersicht/u12-bzl-36-fruehjahr-bezirksebene-hamburg-d-junioren-bezirksliga-d-junioren-saison2526-hamburg/-/staffel/0306E7FA78000005VS5489BUVV5FEO72-G#!/)", type="primary")
