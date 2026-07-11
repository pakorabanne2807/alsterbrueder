import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
import random
import requests
import plotly.express as px  # Für hochmoderne, interaktive Diagramme

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
# Die 5 festen Phasen für dein Alsterbrüder-Training:
TRAINING_PHASES = [
    "1. Aufwärmen", 
    "2. Passspiel", 
    "3. Rondo", 
    "4. Torschuss / Spielform", 
    "5. Abschlussspiel"
]

# 🌍 DEINE FEST HINTERLEGTE GOOGLE CLOUD URL:
API_URL = "https://script.google.com/macros/s/AKfycbwC5946xV9qMBEiTkPYTt1sqP0n0ohPN_n2QqA1nPWurK63_QYs9WiTwUNIN2J0Qs9MPA/exec"

# --- SIDEBAR: PASSWORT-SCHUTZ (TRAINER VS. ELTERN) ---
with st.sidebar:
    st.markdown("### 🔐 Bereichs-Zugang")
    passwort_eingabe = st.text_input(
        "Trainer-Passwort für Schreibrechte:", 
        type="password", 
        help="Ohne Passwort bleibt die App im schreibgeschützten Eltern-Modus."
    )
    
    is_trainer = (passwort_eingabe == "fcalster")
    
    if is_trainer:
        st.success("👨‍🍳 Trainer-Modus active (Schreibrechte freigeschaltet)")
    else:
        st.info("👪 Eltern-Modus active (Schreibgeschützte Ansicht)")

# --- HILFSFUNKTION: FUSSBALLERISCHE POSITIONS-VERWANDTSCHAFT ---
def sind_verwandt(pos1, pos2):
    verwandte_paare = [
        {"ZM", "ZOM"},
        {"ZM", "ZDM"},
        {"RV", "LV"},
        {"RM", "LM"}
    ]
    return {pos1, pos2} in verwandte_paare

# --- DATEN-MANAGEMENT ---
def generiere_testdaten():
    namen = [
        "Jannis", "Leo", "Tom", "Mats", "Finn", "Paul", "Luis", 
        "Lasse", "Jonas", "Mika", "Emil", "Anton", "Noah", "Leon", 
        "Elias", "Ben"
    ]
    spieler_liste = []
    for i, name in enumerate(namen):
        pos = [random.choice(POSITIONS)]
        if random.random() > 0.4:
            pos.append(random.choice([p for p in POSITIONS if p != pos[0]]))
        if random.random() > 0.6:
            pos.append(random.choice([p for p in POSITIONS if p not in pos]))
        spieler_liste.append({
            "id": i + 1, "name": name, "role": "Spieler", 
            "number": str(random.randint(2, 99)), "positions": pos, 
            "training": [], "matches": []
        })
    spieler_liste.append({
        "id": 999, "name": "Pascal (Trainer)", "role": "Trainer", 
        "number": "", "positions": [], "training": [], "matches": []
    })
    
    uebungs_liste = [
        {"id": 1, "name": "Kognitives Einlaufen", "phase": "1. Aufwärmen", "schwerpunkt": "Passspiel", "spieler": "Alle", "aufbau": "Hütchenviereck. Einlaufen mit Richtungswechsel auf Signal.", "grafik": ""},
        {"id": 2, "name": "Y-Passform", "phase": "2. Passspiel", "schwerpunkt": "Passspiel", "spieler": "10-12", "aufbau": "Passen im Y-Muster mit Nachlaufen. Fokus auf offene Stellung.", "grafik": ""},
        {"id": 3, "name": "4 gegen 2 Rondo", "phase": "3. Rondo", "schwerpunkt": "Umschalten", "spieler": "6", "aufbau": "Klassisches Rondo im 10x10m Feld. Maximal 2 Kontakte.", "grafik": ""},
        {"id": 4, "name": "Flügelspiel mit Torschuss", "phase": "4. Torschuss / Spielform", "schwerpunkt": "Torschuss", "spieler": "Alle", "aufbau": "Pass in die Gasse, Flanke und Torschuss im Zentrum.", "grafik": ""},
        {"id": 5, "name": "Freies Spiel 8v8", "phase": "5. Abschlussspiel", "schwerpunkt": "Spielform", "spieler": "Alle", "aufbau": "Zwei Tore, freies Spiel im doppelten Strafraum.", "grafik": ""}
    ]
    return {"players": spieler_liste, "exercises": uebungs_liste}

def lade_daten():
    data = None
    if API_URL:
        try:
            res = requests.get(API_URL, timeout=15)
            if res.text.strip().startswith("<!DOCTYPE") or "html" in res.text.lower():
                st.error("⚠️ Google verweigert den Zugriff! Cloud-URL prüfen.")
                data = None
            else: data = res.json()
        except Exception as e:
            st.error(f"Cloud-Fehler ({e}). Lade lokalen Speicher...")
            data = None
            
    if data is None:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f: data = json.load(f)
        else: data = generiere_testdaten()

    if "players" not in data: data["players"] = []
    if "exercises" not in data: data["exercises"] = []
    if "messages" not in data: data["messages"] = []

    for p in data.get("players", []):
        if "role" not in p: p["role"] = "Spieler"
        if "number" not in p: p["number"] = ""
        if "positions" not in p: p["positions"] = ["ZM"]
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

# --- LOGIK: STATISTIKEN BERECHNEN ---
def berechne_statistiken(spieler, erlaubte_typen=None):
    alle_events = spieler.get("training", [])
    if erlaubte_typen is not None:
        alle_events = [t for t in alle_events if t.get("type", "Training") in erlaubte_typen]
        
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

    club = "-"
    if gesamt_tr > 0:
        if beteiligungs_quote >= 90: club = "🥇 Gold-Club"
        elif beteiligungs_quote >= 75: club = "🥈 Silber-Club"
        elif beteiligungs_quote >= 50: club = "🥉 Bronze-Club"

    return {
        "Nr.": nr, "Name": spieler["name"], "Positionen": ", ".join(spieler["positions"]),
        "Beteiligung": round(beteiligungs_quote), "🏃‍♂️ Spiele": spiele_gesamt, "Meilenstein": club,
        "⚽ Tore": tore_gesamt, "🅰️ Vorlagen": vorlagen_gesamt, "🌟 Scorer": tore_gesamt + vorlagen_gesamt
    }

# --- GENERATOR FÜR DAS INTERAKTIVE DRAG & DROP SPIELFELD ---
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

# --- UI: NAVIGATION ---
available_tabs = ["📊 Übersicht", "🔍 Spieler-Profile", "📖 Spielübersicht"]
if is_trainer: 
    available_tabs += ["🏃‍♂️ Kader", "⚽ Spiel loggen", "🤖 KI Twin-Teams", "📥 Import (SpielerPlus)", "📋 Trainingsplaner"]
available_tabs += ["🏆 Liga-Tabelle"]

tab_slugs = {
    "📊 Übersicht": "uebersicht", "🔍 Spieler-Profile": "profile", "📖 Spielübersicht": "spieluebersicht", 
    "🏃‍♂️ Kader": "kader", "⚽ Spiel loggen": "spiel-loggen", "🤖 KI Twin-Teams": "ki-teams", 
    "📥 Import (SpielerPlus)": "import", "📋 Trainingsplaner": "planer", "🏆 Liga-Tabelle": "liga"
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

# --- GLOBAL LOAD FOR ALL TABS ---
nur_spieler = [p for p in st.session_state.data["players"] if p.get("role", "Spieler") == "Spieler"]

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
        
        st.dataframe(df, column_config={
            "Nr.": st.column_config.NumberColumn("Nr.", format="%d"), "Name": st.column_config.TextColumn("Spielername"), 
            "Positionen": st.column_config.TextColumn("Positionen"), "Beteiligung": st.column_config.ProgressColumn("Trainingsbeteiligung", min_value=0, max_value=100, format="%d%%"), 
            "🏃‍♂️ Spiele": st.column_config.NumberColumn("🏃‍♂️ Spiele", format="%d"), "Meilenstein": st.column_config.TextColumn("Meilenstein-Status"), 
            "⚽ Tore": st.column_config.NumberColumn("⚽ Tore", format="%d"), "🅰️ Vorlagen": st.column_config.NumberColumn("🅰️ Vorlagen", format="%d"), "🌟 Scorer": st.column_config.NumberColumn("🌟 Scorer", format="%d")
        }, hide_index=True, use_container_width=True)
        
        # 🥇 MEILENSTEIN-CLUBS (Prozentwerte wunschgemäß entfernt ❌)
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
        
        # 👑 LEADER-CARDS
        st.write(""); st.divider(); st.markdown("### 👑 Alsterbrüder Leaderboard")
        h_col1, h_col2, h_col3 = st.columns(3)
        top_tr = df.sort_values(by="Beteiligung", ascending=False).iloc[0]
        top_go = df.sort_values(by="⚽ Tore", ascending=False).iloc[0]
        top_sc = df.sort_values(by="🌟 Scorer", ascending=False).iloc[0]
        
        h_col1.metric("🔥 Trainings-König", top_tr["Name"], f"{top_tr['Beteiligung']}% Beteiligung")
        h_col2.metric("🎯 Top-Torjäger", top_go["Name"], f"{top_go['⚽ Tore']} Tore")
        h_col3.metric("🌟 Scorer-König", top_sc["Name"], f"{top_sc['🌟 Scorer']} Pkt ({top_sc['⚽ Tore']}T / {top_sc['🅰️ Vorlagen']}V)")

        # 📊 PLOTLY DIAGRAMME
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

# --- 🔍 TAB 2: SPIELER-PROFILE (U13 UPDATE & RESPONSIVE DESIGN) ---
if selected_tab == "🔍 Spieler-Profile":
    st.subheader("🔍 Alsterbrüder Spieler-Profile & FUT-Cards")
    if not nur_spieler:
        st.info("Keine Spieler im Kader hinterlegt.")
    else:
        spieler_namen = sorted([p["name"] for p in nur_spieler])
        selected_player_name = st.selectbox("Wähle einen Spieler aus der U13:", spieler_namen)
        
        p = next(x for x in nur_spieler if x["name"] == selected_player_name)
        stats = berechne_statistiken(p)
        
        pos_main = p["positions"][0] if p["positions"] else "ZM"
        if pos_main in ["TW"]: base_pac, base_dri, base_def = 62, 58, 85
        elif pos_main in ["IV", "LV", "RV"]: base_pac, base_dri, base_def = 74, 66, 84
        elif pos_main in ["ZDM", "ZM", "ZOM", "LM", "RM"]: base_pac, base_dri, base_def = 77, 81, 70
        else: base_pac, base_dri, base_def = 88, 84, 38
            
        sho_rating = min(52 + stats["⚽ Tore"] * 6, 99)
        pas_rating = min(55 + stats["🅰️ Vorlagen"] * 6, 99)
        phy_rating = min(45 + int(stats["Beteiligung"] * 0.52), 99)
        pac_rating = min(base_pac + stats["🏃‍♂️ Spiele"], 99)
        dri_rating = min(base_dri + stats["🅰️ Vorlagen"] * 2, 99)
        def_rating = base_def
        ovr_rating = int((pac_rating + sho_rating + pas_rating + dri_rating + def_rating + phy_rating) / 6)
        
        if stats["Beteiligung"] >= 90:
            st.balloons()
            st.success(f"👑 {p['name']} thronisiert im Gold-Club! Absoluter Trainings-Weltmeister!")

        # ⚡ OPTIMIERTES RESPONSIVES LAYOUT: box-sizing hinzugefügt, Breite angepasst gegen Abschneiden!
        card_html = f"""
        <div style="background: linear-gradient(135deg, #1e3a8a 0%, #172554 40%, #eab308 100%); 
                    width: 260px; height: 360px; border-radius: 14px; padding: 20px; 
                    color: white; font-family: 'Arial Black', -apple-system, sans-serif; box-shadow: 0 12px 24px rgba(0,0,0,0.4);
                    margin: auto; border: 3px solid #facc15; position: relative; box-sizing: border-box;">
            <div style="font-size: 42px; font-weight: 900; line-height: 36px; float: left; text-align: center; width: 60px; color: #facc15;">
                {ovr_rating}<br><span style="font-size: 13px; font-weight: bold; color: white; background: #1e3a8a; padding: 1px 5px; border-radius: 3px;">{pos_main}</span>
            </div>
            <div style="font-size: 45px; position: absolute; right: 20px; top: 15px; opacity: 0.25;">⚽</div>
            <div style="clear: both; height: 15px;"></div>
            <div style="text-align: center; font-size: 20px; margin-bottom: 15px; border-bottom: 2px solid #facc15; padding-bottom: 6px; text-transform: uppercase; letter-spacing: 1px;">
                {p['name']}
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 13px; line-height: 25px;">
                <div style="width: 45%; text-align: left;">
                    <div><span style="color:#facc15;">{pac_rating}</span> PAC</div>
                    <div><span style="color:#facc15;">{sho_rating}</span> SHO</div>
                    <div><span style="color:#facc15;">{pas_rating}</span> PAS</div>
                </div>
                <div style="width: 45%; text-align: left; border-left: 1px solid rgba(255,255,255,0.2); padding-left: 15px; box-sizing: border-box;">
                    <div><span style="color:#facc15;">{dri_rating}</span> DRI</div>
                    <div><span style="color:#facc15;">{def_rating}</span> DEF</div>
                    <div><span style="color:#facc15;">{phy_rating}</span> PHY</div>
                </div>
            </div>
            <div style="position: absolute; bottom: 12px; left: 0; width: 100%; text-align: center; font-size: 11px; font-family: sans-serif; color: rgba(255,255,255,0.7); letter-spacing: 0.5px;">
                FC Alsterbrüder U13 • Nr. {p.get('number', '-')}
            </div>
        </div>
        """
        
        c_card, c_curve = st.columns([1, 2])
        with c_card:
            st.components.v1.html(card_html, height=390)
            
        with c_curve:
            st.markdown("### 📈 Aktuelle Formkurve")
            tr_history = p.get("training", [])
            if not tr_history:
                st.info("Noch keine Trainingsdaten erfasst. Sobald Daten über den SpielerPlus-Import vorliegen, siehst du hier die Kurve.")
            else:
                last_5 = tr_history[-5:]
                chart_data = pd.DataFrame({
                    "Datum": [t.get("date", f"E-{i+1}") for i, t in enumerate(last_5)],
                    "Status": [100 if t["present"] else 0 for t in last_5]
                })
                
                fig_curve = px.line(chart_data, x="Datum", y="Status", markers=True, color_discrete_sequence=["#1e3a8a"])
                fig_curve.update_layout(yaxis=dict(title=None, tickmode="array", tickvals=[0, 100], ticktext=["Abwesend ❌", "Anwesend ⚽"], range=[-15, 115]), xaxis_title=None, height=220, plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=0,r=0,t=10,b=0))
                fig_curve.update_yaxes(showgrid=True, gridcolor="rgba(200,200,200,0.15)")
                st.plotly_chart(fig_curve, use_container_width=True, config={'displayModeBar': False})
                
                recent_count = sum([1 for t in last_5 if t["present"]])
                if recent_count >= 4:
                    st.success("🔥 **Status: ON FIRE!** Unglaublicher Einsatz in den letzten Wochen. Mach genau so weiter!")
                elif recent_count <= 1:
                    st.error("💤 **Status: Aufwachen!** Zuletzt wurden einige Einheiten verpasst. Schnür die Schuhe, ab zum nächsten Training!")
                else:
                    st.warning("🏃‍♂️ **Status: Solide.** Regelmäßige Beteiligung auf solidem Niveau.")

# --- TAB 3: SPIELÜBERSICHT ---
if selected_tab == "📖 Spielübersicht":
    st.subheader("📖 Historische Spielübersicht")
    spiele_set = set()
    for p in nur_spieler:
        for m in p.get("matches", []):
            if m.get("opponent", "Unbekannt") != "Unbekannt": spiele_set.add((m.get("date", "Unbekannt"), m.get("opponent", "Unbekannt"), m.get("type", "Spiel")))
    spiele_liste = sorted(list(spiele_set), key=lambda x: x[0], reverse=True)
    
    if not spiele_liste: st.info("Es wurden noch keine detaillierten Spiele geloggt.")
    else:
        gewaehltes_spiel_idx = st.selectbox("Wähle ein Match aus:", range(len(spiele_liste)), format_func=lambda i: f"📅 {spiele_liste[i][0]} | [{spiele_liste[i][2]}] gegen {spiele_liste[i][1]}")
        sel_datum, sel_gegner, sel_art = spiele_liste[gewaehltes_spiel_idx]
        sel_res_blau, sel_res_gelb = ["-"]*4, ["-"]*4
        for p in nur_spieler:
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

# --- TAB 4: KADER (TRAINER ONLY) ---
if selected_tab == "🏃‍♂️ Kader" and is_trainer:
    st.subheader("🏃‍♂️ Kader direkt in der Tabelle bearbeiten")
    kader_liste = []
    for p in st.session_state.data["players"]:
        pos = p.get("positions", [])
        kader_liste.append({"ID": str(p["id"]), "Nr.": int(p.get("number", "")) if str(p.get("number", "")).isdigit() else None, "Name": p["name"], "Rolle": p.get("role", "Spieler"), "Prio 1": pos[0] if len(pos) > 0 else "-", "Prio 2": pos[1] if len(pos) > 1 else "-", "Prio 3": pos[2] if len(pos) > 2 else "-", "Prio 4": pos[3] if len(pos) > 3 else "-", "Prio 5": pos[4] if len(pos) > 4 else "-"})
    kader_df = pd.DataFrame(kader_liste)
    if not kader_df.empty: kader_df = kader_df.sort_values(by="Nr.", na_position="last").reset_index(drop=True)
    editiertes_kader = st.data_editor(kader_df, hide_index=True, column_config={"ID": None, "Rolle": st.column_config.SelectboxColumn(options=["Spieler", "Trainer"], required=True), "Nr.": st.column_config.NumberColumn("Nr.", format="%d"), "Prio 1": st.column_config.SelectboxColumn(options=["-"] + POSITIONS), "Prio 2": st.column_config.SelectboxColumn(options=["-"] + POSITIONS), "Prio 3": st.column_config.SelectboxColumn(options=["-"] + POSITIONS), "Prio 4": st.column_config.SelectboxColumn(options=["-"] + POSITIONS), "Prio 5": st.column_config.SelectboxColumn(options=["-"] + POSITIONS)}, num_rows="dynamic", use_container_width=True)
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
                neuer_kader.append(orig)
            elif str(row["Name"]).strip():
                neuer_kader.append({"id": max([p["id"] for p in neuer_kader] + [p["id"] for p in st.session_state.data["players"]] + [0]) + 1, "name": str(row["Name"]), "role": str(row["Rolle"]), "number": nr_str, "positions": pos_liste, "training": [], "matches": []})
        st.session_state.data["players"] = neuer_kader
        if speichere_daten(st.session_state.data): st.success("Kader erfolgreich in der Cloud aktualisiert!")

# --- TAB 5: SPIEL LOGGEN (TRAINER ONLY) ---
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

# --- TAB 6: KI TWIN-TEAMS (TRAINER ONLY) ---
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
                genutzte_namen.add(bester["name"]); nr_b = f'<span class="nr">#{bester["nr"]}</span>' if bester["nr"] else ''
                return f'<div class="player" id="{team_id}_{rollen_name}" draggable="true" ondragstart="drag(event)">{nr_b}<span class="name-text">{bester["name"]}</span></div>'
            return ""

        rollen = [("TW", ["TW"]), ("ST", ["ST", "LF", "RF", "ZOM"]), ("LM", ["LM", "LF", "ZM"]), ("ZM", ["ZM", "ZDM", "ZOM"]), ("RM", ["RM", "RF", "ZM"]), ("IV (L)", ["IV", "LV", "ZDM"]), ("IV (R)", ["IV", "RV", "ZDM"])]
        t_blau, t_gelb, genutzte_namen = {}, {}, set(); is_alt = bool(alternative_klick)
        for i, (r_name, pr) in enumerate(rollen):
            if i % 2 == 0: t_blau[r_name] = waehle_spieler_taktik_mix(pr, "Blau", r_name, is_alt); t_gelb[r_name] = waehle_spieler_taktik_mix(pr, "Gelb", r_name, is_alt)
            else: t_gelb[r_name] = waehle_spieler_taktik_mix(pr, "Gelb", r_name, is_alt); t_blau[r_name] = waehle_spieler_taktik_mix(pr, "Blau", r_name, is_alt)

        ersatz = [c for c in blau_fest + gelb_fest + ki_pool + bench_fest if c["name"] not in genutzte_namen]
        b_blau_list = []
        for i, x in enumerate(ersatz):
            nr_tag = f'<span class="nr">#{x["nr"]}</span>' if x["nr"] else ""
            b_blau_list.append(f'<div class="player" id="bBlau_{i}" draggable="true" ondragstart="drag(event)">{nr_tag}<span class="name-text">{x["name"]}</span></div>')
        b_blau = "".join(b_blau_list)
        b_gelb_list = []
        for i, x in enumerate(ersatz):
            nr_tag = f'<span class="nr">#{x["nr"]}</span>' if x["nr"] else ""
            b_gelb_list.append(f'<div class="player" id="bGelb_{i}" draggable="true" ondragstart="drag(event)">{nr_tag}<span class="name-text">{x["name"]}</span></div>')
        b_gelb = "".join(b_gelb_list)
        
        st.session_state.pitch_blau_html = generiere_pitch_html(t_blau, b_blau, "Team Blau")
        st.session_state.pitch_gelb_html = generiere_pitch_html(t_gelb, b_gelb, "Team Gelb")

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
            def f_sp(w): return next((i for i, s in enumerate(spalten) if any(x in s.lower() for x in w)), 0)
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
                    
                    # 🎯 DER GEWÜNSCHTE EXAKTE FIX: Vergleich mit == statt "in" verhindert Überschneidungen (Emil / Emilio)
                    sp = next((x for x in st.session_state.data["players"] if p_n.lower() == x["name"].lower()), None)
                    if not sp: 
                        sp = {"id": max([x["id"] for x in st.session_state.data["players"]]+[0])+1, "name": p_n, "role": "Spieler", "number": "", "positions": ["ZM"], "training": [], "matches": []}
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

# --- TAB 8: TRAININGSPLANER (TRAINER ONLY) ---
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
                                if "docs.google.com/presentation" in gfx_url: st.components.v1.html(f'<iframe src="{gfx_url}" frameborder="0" width="100%" height="220" allowfullscreen="true"></iframe>', height=230)
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
                        if speichere_daten(st.session_state.data): st.success(f"Übung hinzugefügt!"); st.rerun()
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
    st.link_button("🌐 Offizielle fussball.de Tabelle öffnen", "https://www.fussball.de/spieltagsuebersicht/u12-bzl-36-fruehjahr-bezirksebene-hamburg-d-junioren-bezirksliga-d-junioren-saison2526-hamburg/-/staffel/0306E7FA78000005VS5489BUVV5FEO72-G#!/", type="primary")
