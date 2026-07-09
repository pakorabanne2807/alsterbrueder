import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
import random
import requests

# --- KONFIGURATION & SETUP ---
st.set_page_config(
    page_title="FC Alsterbrüder U14 Tracker", 
    page_icon="⚽", 
    layout="wide"
)

DATA_FILE = "alsterbrueder_daten.json"
POSITIONS = [
    "TW", "IV", "LV", "RV", "ZDM", "ZM", "ZOM", "LM", "RM", "LF", "RF", "ST"
]

# 🌍 HIER DEINE KOPIERTE GOOGLE GOOGLE APPS SCRIPT URL EINTRAGEN:
# (Denk dran, deinen /exec Link hier wieder einzufügen!)
API_URL = "https://script.google.com/macros/s/AKfycbwC5946xV9qMBEiTkPYTt1sqP0n0ohPN_n2QqA1nPWurK63_QYs9WiTwUNIN2J0Qs9MPA/exec"

# --- SIDEBAR: PASSWORT-SCHUTZ (TRAINER VS. ELTERN) ---
with st.sidebar:
    st.markdown("### 🔐 Bereichs-Zugang")
    passwort_eingabe = st.text_input(
        "Trainer-Passwort für Schreibrechte:", 
        type="password", 
        help="Ohne Passwort bleibt die App im schreibgeschützten Eltern-Modus."
    )
    
    is_trainer = (passwort_eingabe == "alster2014")
    
    if is_trainer:
        st.success("👨‍🍳 Trainer-Modus aktiv (Schreibrechte freigeschaltet)")
    else:
        st.info("👪 Eltern-Modus aktiv (Schreibgeschützte Ansicht)")

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
            "id": i + 1, 
            "name": name, 
            "role": "Spieler", 
            "number": str(random.randint(2, 99)), 
            "positions": pos, 
            "training": [], 
            "matches": []
        })
    spieler_liste.append({
        "id": 999, 
        "name": "Pascal (Trainer)", 
        "role": "Trainer", 
        "number": "", 
        "positions": [], 
        "training": [], 
        "matches": []
    })
    return {"players": spieler_liste}

def lade_daten():
    data = None
    if API_URL:
        try:
            res = requests.get(API_URL, timeout=10)
            if res.text.strip().startswith("<!DOCTYPE") or "html" in res.text.lower():
                st.error("⚠️ Google verweigert den Zugriff! HTML erhalten.")
                data = None
            else:
                data = res.json()
        except Exception as e:
            st.error(f"Cloud-Fehler ({e}). Lade lokalen Speicher...")
            data = None
            
    if data is None:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = generiere_testdaten()

    for p in data.get("players", []):
        if "role" not in p: p["role"] = "Spieler"
        if "number" not in p: p["number"] = ""
        if "positions" not in p: p["positions"] = ["ZM"]
    return data

def speichere_daten(data):
    if API_URL:
        try:
            requests.post(
                API_URL, 
                data=json.dumps(data), 
                headers={"Content-Type": "application/json"}, 
                timeout=10
            )
            return
        except Exception as e:
            st.error(f"Fehler beim Sichern in der Google-Cloud: {e}")
            
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# --- INITIALISIERUNG DER SPEICHERRÄUME ---
if "data" not in st.session_state:
    st.session_state.data = lade_daten()

# 🧠 HIER IST DIE REPARATUR: Zuweisungs-Speicher für die KI von Sekunde 1 an bereitstellen
if "zuweisungen" not in st.session_state:
    st.session_state.zuweisungen = {}

# --- LOGIK: STATISTIKEN BERECHNEN ---
def berechne_statistiken(spieler, erlaubte_typen=None):
    alle_events = spieler.get("training", [])
    if erlaubte_typen is not None:
        alle_events = [t for t in alle_events if t.get("type", "Training") in erlaubte_typen]
        
    gesamt_tr = len(alle_events)
    anwesend_tr = [t for t in alle_events if t["present"]]
    beteiligungs_quote = (len(anwesend_tr) / gesamt_tr * 100) if gesamt_tr > 0 else 0

    spiele = spieler.get("matches", [])
    
    tore_gesamt = 0
    vorlagen_gesamt = 0
    for m in spiele:
        if m.get("played", True) and m.get("team", "Blau") in ["Blau", "Gelb", "Ersatz"]:
            if "goals" in m:
                tore_gesamt += int(m["goals"])
            elif "goalsStr" in m:
                g_str = str(m["goalsStr"]).strip()
                if g_str: tore_gesamt += len(g_str.split(","))
            vorlagen_gesamt += int(m.get("assists", 0))

    nr_val = spieler.get("number", "")
    nr = int(nr_val) if str(nr_val).isdigit() else None

    club = "-"
    if gesamt_tr > 0:
        if beteiligungs_quote == 100: club = "👑 Königs-Club"
        elif beteiligungs_quote >= 90: club = "🥇 Gold-Club"
        elif beteiligungs_quote >= 75: club = "🥈 Silber-Club"
        elif beteiligungs_quote >= 50: club = "🥉 Bronze-Club"

    return {
        "Nr.": nr,
        "Name": spieler["name"],
        "Positionen": ", ".join(spieler["positions"]),
        "Beteiligung": round(beteiligungs_quote),
        "Meilenstein": club,
        "⚽ Tore": tore_gesamt,
        "🅰️ Vorlagen": vorlagen_gesamt,
        "🔥 Scorer": tore_gesamt + vorlagen_gesamt
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

# --- UI: DYNAMISCHE REITER-STEUERUNG ---
tabs_definition = ["📊 Übersicht", "📖 Spielübersicht"]
if is_trainer: 
    tabs_definition += ["🏃‍♂️ Kader", "⚽ Spiel loggen"]
tabs_definition += ["🤖 KI Twin-Teams"]
if is_trainer: 
    tabs_definition += ["📥 Import (SpielerPlus)"]
tabs_definition += ["🏆 Liga-Tabelle"]

rendered_tabs = st.tabs(tabs_definition)
tab_map = {name: rendered_tabs[i] for i, name in enumerate(tabs_definition)}

# --- TAB 1: ÜBERSICHT ---
with tab_map["📊 Übersicht"]:
    st.subheader("🏆 Team Übersicht")
    if st.session_state.data["players"]:
        nur_spieler = [p for p in st.session_state.data["players"] if p.get("role", "Spieler") == "Spieler"]
        nur_trainer = [p for p in st.session_state.data["players"] if p.get("role", "Spieler") == "Trainer"]
        
        typen_set = set()
        for p in st.session_state.data["players"]:
            for t in p.get("training", []):
                typen_set.add(t.get("type", "Training"))
        alle_event_typen = sorted(list(typen_set))
        if not alle_event_typen: 
            alle_event_typen = ["Training"]
            
        gewaehlte_typen = st.multiselect("Beteiligung filtern nach Event-Typ:", alle_event_typen, default=alle_event_typen)
        
        if nur_spieler:
            statistiken = [berechne_statistiken(p, gewaehlte_typen) for p in nur_spieler]
            df = pd.DataFrame(statistiken).sort_values(by="Beteiligung", ascending=False).reset_index(drop=True)
            
            st.dataframe(
                df, 
                column_config={
                    "Nr.": st.column_config.NumberColumn("Nr.", format="%d"), 
                    "Name": st.column_config.TextColumn("Spielername"), 
                    "Positionen": st.column_config.TextColumn("Positionen"), 
                    "Beteiligung": st.column_config.ProgressColumn("Trainingsbeteiligung", min_value=0, max_value=100, format="%d%%"), 
                    "Meilenstein": st.column_config.TextColumn("Meilenstein-Status"), 
                    "⚽ Tore": st.column_config.NumberColumn("⚽ Tore", format="%d"), 
                    "🅰️ Vorlagen": st.column_config.NumberColumn("🅰️ Vorlagen", format="%d"), 
                    "🔥 Scorer": st.column_config.NumberColumn("🔥 Scorer", format="%d")
                }, 
                hide_index=True, 
                use_container_width=True
            )
            
            st.divider()
            st.markdown("### 👑 Der Trainings-Meilenstein-Club")
            st.write("Hier werden die Jungs für ihren Fleiß im Training gefeiert!")
            
            mc1, mc2, mc3, mc4 = st.columns(4)
            with mc1: 
                st.info("**👑 Königs-Club (100%)**")
                for s in statistiken:
                    if s["Meilenstein"] == "👑 Königs-Club":
                        st.write(f"• {s['Name']}")
            with mc2: 
                st.success("**🥇 Gold-Club (90%+)**")
                for s in statistiken:
                    if s["Meilenstein"] == "🥇 Gold-Club":
                        st.write(f"• {s['Name']}")
            with mc3: 
                st.warning("**🥈 Silber-Club (75%+)**")
                for s in statistiken:
                    if s["Meilenstein"] == "🥈 Silber-Club":
                        st.write(f"• {s['Name']}")
            with mc4: 
                st.error("**🥉 Bronze-Club (50%+)**")
                for s in statistiken:
                    if s["Meilenstein"] == "🥉 Bronze-Club":
                        st.write(f"• {s['Name']}")
        else: 
            st.info("Keine Spieler im Kader.")
            
        if nur_trainer: 
            st.write("---")
            trainer_namen = [t['name'] for t in nur_trainer]
            st.success(f"**Verantwortliche:** {', '.join(trainer_namen)}")
    else: 
        st.info("Keine Mitglieder im Kader.")

# --- TAB: SPIELÜBERSICHT ---
with tab_map["📖 Spielübersicht"]:
    st.subheader("📖 Historische Spielübersicht")
    
    spiele_set = set()
    for p in st.session_state.data["players"]:
        for m in p.get("matches", []):
            if m.get("opponent", "Unbekannt") != "Unbekannt":
                spiele_set.add((m.get("date", "Unbekannt"), m.get("opponent", "Unbekannt"), m.get("type", "Spiel")))
                
    spiele_liste = sorted(list(spiele_set), key=lambda x: x[0], reverse=True)
    
    if not spiele_liste: 
        st.info("Es wurden noch keine detaillierten Spiele geloggt.")
    else:
        gewaehltes_spiel_idx = st.selectbox(
            "Wähle ein Match aus:", 
            range(len(spiele_liste)), 
            format_func=lambda i: f"📅 {spiele_liste[i][0]} | [{spiele_liste[i][2]}] gegen {spiele_liste[i][1]}"
        )
        sel_datum, sel_gegner, sel_art = spiele_liste[gewaehltes_spiel_idx]
        
        sel_res_blau, sel_res_gelb = ["-"]*4, ["-"]*4
        for p in st.session_state.data["players"]:
            p_match = next((m for m in p.get("matches", []) if m.get("date") == sel_datum and m.get("opponent") == sel_gegner), None)
            if p_match:
                sel_res_blau = p_match.get("team_blau_results", p_match.get("team_a_results", ["-"]*4))
                sel_res_gelb = p_match.get("team_gelb_results", p_match.get("team_b_results", ["-"]*4))
                break
                
        st.divider()
        st.markdown(f"### ⚽ {sel_art} gegen **{sel_gegner}**\nSpieltag vom: **{sel_datum}**")
        
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
        for p in st.session_state.data["players"]:
            if p.get("role", "Spieler") == "Spieler":
                p_match = next((m for m in p.get("matches", []) if m.get("date") == sel_datum and m.get("opponent") == sel_gegner), None)
                if p_match:
                    t_val = p_match.get("team", "Blau" if p_match.get("played", True) else "Abwesend")
                    lbl = "🔵 Team Blau" if t_val == "Blau" else ("🟡 Team Gelb" if t_val == "Gelb" else ("🔄 Ersatzbank" if t_val == "Ersatz" else "❌ Nicht im Kader"))
                    match_details.append({
                        "Nr.": int(p["number"]) if str(p["number"]).isdigit() else None, 
                        "Name": p["name"], 
                        "Team / Status": lbl, 
                        "⚽ Tore": p_match.get("goals", 0), 
                        "Vorlagen": p_match.get("assists", 0)
                    })
                    
        if match_details:
            df_details = pd.DataFrame(match_details).sort_values(by=["Team / Status", "Nr."], ascending=[True, True], na_position="last").reset_index(drop=True)
            st.write("")
            c1, c2, c3 = st.columns(3)
            c1.metric("Erzielte Tore (Gesamt)", df_details["⚽ Tore"].sum())
            c2.metric("Gesamtvorlagen", df_details["Vorlagen"].sum())
            c3.metric("Spieler aktiv", (df_details["Team / Status"] != "❌ Nicht im Kader").sum())
            
            st.dataframe(df_details, column_config={"Nr.": st.column_config.NumberColumn("Nr.", format="%d"), "Name": st.column_config.TextColumn("Spielername"), "Team / Status": st.column_config.TextColumn("Einteilung"), "⚽ Tore": st.column_config.NumberColumn("Tore", format="%d"), "Vorlagen": st.column_config.NumberColumn("Vorlagen", format="%d")}, hide_index=True, use_container_width=True)

# --- TAB 2: KADER (NUR TRAINER) ---
if "🏃‍♂️ Kader" in tab_map:
    with tab_map["🏃‍♂️ Kader"]:
        st.subheader("🏃‍♂️ Kader direkt in der Tabelle bearbeiten")
        kader_liste = []
        for p in st.session_state.data["players"]:
            pos = p.get("positions", [])
            kader_liste.append({
                "ID": str(p["id"]),
                "Nr.": int(p.get("number", "")) if str(p.get("number", "")).isdigit() else None,
                "Name": p["name"],
                "Rolle": p.get("role", "Spieler"),
                "Prio 1": pos[0] if len(pos) > 0 else "-",
                "Prio 2": pos[1] if len(pos) > 1 else "-",
                "Prio 3": pos[2] if len(pos) > 2 else "-",
                "Prio 4": pos[3] if len(pos) > 3 else "-",
                "Prio 5": pos[4] if len(pos) > 4 else "-"
            })
        kader_df = pd.DataFrame(kader_liste)
        
        if not kader_df.empty:
            kader_df = kader_df.sort_values(by="Nr.", na_position="last").reset_index(drop=True)
            
        editiertes_kader = st.data_editor(
            kader_df, 
            hide_index=True, 
            column_config={
                "ID": None, 
                "Rolle": st.column_config.SelectboxColumn(options=["Spieler", "Trainer"], required=True), 
                "Nr.": st.column_config.NumberColumn("Nr.", format="%d"), 
                "Prio 1": st.column_config.SelectboxColumn(options=["-"] + POSITIONS), 
                "Prio 2": st.column_config.SelectboxColumn(options=["-"] + POSITIONS), 
                "Prio 3": st.column_config.SelectboxColumn(options=["-"] + POSITIONS), 
                "Prio 4": st.column_config.SelectboxColumn(options=["-"] + POSITIONS), 
                "Prio 5": st.column_config.SelectboxColumn(options=["-"] + POSITIONS)
            }, 
            num_rows="dynamic", 
            use_container_width=True
        )
        
        if st.button("💾 Alle Änderungen im Kader speichern", type="primary"):
            neuer_kader = []
            for index, row in editiertes_kader.iterrows():
                row_id, pos_liste = row.get("ID"), []
                for col in ["Prio 1", "Prio 2", "Prio 3", "Prio 4", "Prio 5"]:
                    if row.get(col, "-") != "-": 
                        pos_liste.append(row.get(col))
                nr_str = str(int(float(row.get("Nr.")))) if pd.notna(row.get("Nr.")) else ""
                orig = next((p for p in st.session_state.data["players"] if str(p["id"]) == str(row_id)), None) if pd.notna(row_id) else None
                if orig:
                    orig["name"], orig["role"], orig["number"], orig["positions"] = str(row["Name"]), str(row["Rolle"]), nr_str, (pos_liste if row["Rolle"] == "Spieler" else [])
                    neuer_kader.append(orig)
                elif str(row["Name"]).strip():
                    neuer_kader.append({"id": max([p["id"] for p in neuer_kader] + [p["id"] for p in st.session_state.data["players"]] + [0]) + 1, "name": str(row["Name"]), "role": str(row["Rolle"]), "number": nr_str, "positions": pos_liste, "training": [], "matches": []})
            st.session_state.data["players"] = neuer_kader; speichere_daten(st.session_state.data); st.success("Kader aktualisiert!"); st.rerun()

# --- TAB 3: SPIEL LOGGEN (NUR TRAINER) ---
if "⚽ Spiel loggen" in tab_map:
    with tab_map["⚽ Spiel loggen"]:
        st.subheader("⚽ Spieltag Statistiken loggen")
        c_meta1, c_meta2, c_meta3 = st.columns(3); m_datum = c_meta1.date_input("Datum Spiel", datetime.today()); m_type = c_meta2.selectbox("Spielart", ["Ligaspiel", "Testspiel"]); m_opponent = c_meta3.text_input("Gegner", placeholder="z.B. VfL Hamburg")
        col_blau, col_gelb = st.columns(2)
        with col_blau: st.markdown("<b>🔵 Team Blau Ergebnisse</b>", unsafe_allow_html=True); sub_b = st.columns(4); m_b1 = sub_b[0].text_input("Sp. 1", "0:0", key="b1"); m_b2 = sub_b[1].text_input("Sp. 2", "0:0", key="b2"); m_b3 = sub_b[2].text_input("Sp. 3", "0:0", key="b3"); m_b4 = sub_b[3].text_input("Sp. 4", "0:0", key="b4")
        with col_gelb: st.markdown("<b>🟡 Team Gelb Ergebnisse</b>", unsafe_allow_html=True); sub_g = st.columns(4); m_g1 = sub_g[0].text_input("Sp. 1", "0:0", key="g1"); m_g2 = sub_g[1].text_input("Sp. 2", "0:0", key="g2"); m_g3 = sub_g[2].text_input("Sp. 3", "0:0", key="g3"); m_g4 = sub_g[3].text_input("Sp. 4", "0:0", key="g4")
        
        st.divider(); nur_spieler = [p for p in st.session_state.data["players"] if p.get("role", "Spieler") == "Spieler"]
        spiel_liste = []
        for p in nur_spieler:
            planung = st.session_state.zuweisungen.get(str(p["id"]), "🤖 KI entscheidet")
            default_status = "❌ Nicht in Kader" if planung == "❌ Abwesend" else ("🔵 Team Blau" if planung == "🤖 KI entscheidet" else planung)
            spiel_liste.append({
                "ID": str(p["id"]), 
                "Nr.": int(p["number"]) if str(p["number"]).isdigit() else None, 
                "Name": p["name"], 
                "Team / Status": default_status, 
                "⚽ Tore": 0, 
                "Vorlagen": 0
            })
        
        spiel_df = pd.DataFrame(spiel_liste)
        if not spiel_df.empty:
            spiel_df = spiel_df.sort_values(by="Nr.", na_position="last").reset_index(drop=True)
            
        editiertes_spiel = st.data_editor(
            spiel_df, 
            disabled=["ID", "Nr.", "Name"], 
            hide_index=True, 
            column_config={
                "ID": None, 
                "Nr.": st.column_config.NumberColumn("Nr.", format="%d"), 
                "Team / Status": st.column_config.SelectboxColumn(
                    options=[
                        "🔵 Team Blau", 
                        "🟡 Team Gelb", 
                        "🔄 Ersatzbank", 
                        "❌ Nicht in Kader"
                    ], 
                    required=True
                ), 
                "⚽ Tore": st.column_config.NumberColumn(min_value=0, format="%d"), 
                "Vorlagen": st.column_config.NumberColumn(min_value=0, format="%d")
            }, 
            use_container_width=True
        )

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
                speichere_daten(st.session_state.data); st.success("Gespeichert!"); st.rerun()

# --- TAB 4: KI TWIN-TEAMS ---
with tab_map["🤖 KI Twin-Teams"]:
    st.subheader("🤖 KI Twin-Aufstellung")
    nur_spieler = [p for p in st.session_state.data["players"] if p.get("role", "Spieler") == "Spieler"]
    
    if is_trainer:
        st.markdown("#### 📋 Kader-Zuweisung")
        zuweisungs_liste = []
        for p in nur_spieler:
            zuweisungs_liste.append({
                "ID": str(p["id"]), 
                "Nr.": int(p["number"]) if str(p["number"]).isdigit() else None, 
                "Name": p["name"], 
                "Hauptposition": p["positions"][0] if p["positions"] else "-", 
                "Zuweisung / Status": st.session_state.zuweisungen.get(str(p["id"]), "🤖 KI entscheidet")
            })
        df_zuweisung = pd.DataFrame(zuweisungs_liste)
        if not df_zuweisung.empty:
            df_zuweisung = df_zuweisung.sort_values(by="Nr.", na_position="last").reset_index(drop=True)
            
        editiertes_kader_zuweisung = st.data_editor(
            df_zuweisung, 
            hide_index=True, 
            disabled=["ID", "Nr.", "Name", "Hauptposition"], 
            column_config={
                "ID": None, 
                "Nr.": st.column_config.NumberColumn("Nr.", format="%d"), 
                "Zuweisung / Status": st.column_config.SelectboxColumn(
                    options=[
                        "🤖 KI entscheidet", 
                        "🔵 Team Blau", 
                        "🟡 Team Gelb", 
                        "🔄 Ersatzbank", 
                        "❌ Abwesend"
                    ], 
                    required=True
                )
            }, 
            use_container_width=True
        )

    btn_col1, btn_col2 = st.columns(2)
    berechnen_klick = btn_col1.button("🤖 KI Aufstellung berechnen" if is_trainer else "⚽ Aktuelle Aufstellung laden", type="primary", use_container_width=True)
    alternative_klick = btn_col2.button("🔄 Alternative Variante berechnen", type="secondary", use_container_width=True) if is_trainer else False

    if berechnen_klick or alternative_klick:
        blau_fest, gelb_fest, ki_pool, bench_fest = [], [], [], []
        if is_trainer:
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
        else:
            for p_data in nur_spieler:
                status = st.session_state.zuweisungen.get(str(p_data["id"]), "🤖 KI entscheidet")
                if status == "❌ Abwesend": continue
                stats = berechne_statistiken(p_data); c_info = {"id": p_data["id"], "name": p_data["name"], "nr": p_data.get("number", ""), "positions": p_data.get("positions", ["ZM"]), "beteiligung": stats["Beteiligung"]}
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
        if is_trainer: st.info("💡 Taktikboard active: Karten können per Drag & Drop verschoben werden.")
        c_p1, c_p2 = st.columns(2)
        with c_p1: st.markdown("### 🔵 Team Blau"); st.components.v1.html(st.session_state.pitch_blau_html, height=460)
        with c_p2: st.markdown("### 🟡 Team Gelb"); st.components.v1.html(st.session_state.pitch_gelb_html, height=460)
    else: st.warning("Aufstellung muss berechnet oder geladen werden.")

# --- TAB 5: SPIELERPLUS IMPORT (NUR TRAINER) ---
if "📥 Import (SpielerPlus)" in tab_map:
    with tab_map["📥 Import (SpielerPlus)"]:
        st.subheader("📥 Massen-Import (SpielerPlus CSV)")
        hochgeladene_datei = st.file_uploader("Datei auswählen", type=["csv", "xlsx"])
        if hochgeladene_datei is not None:
            try:
                df_import = pd.read_csv(hochgeladene_datei, sep=";") if hochgeladene_datei.name.endswith('.csv') else pd.read_excel(hochgeladene_datei)
                st.dataframe(df_import.head(2)); spalten = df_import.columns.tolist()
                def f_sp(w): return next((i for i, s in enumerate(spalten) if any(x in s.lower() for x in w)), 0)
                
                c1, c2, c3, c4 = st.columns(4)
                name_sp = c1.selectbox("Name", spalten, index=f_sp(["user_name", "spielername", "spieler", "name"]))
                teil_sp = c2.selectbox("Beteiligung", spalten, index=f_sp(["user_participation", "zusage", "status"]))
                dat_sp = c3.selectbox("Datum", spalten, index=f_sp(["event_date_start", "datum", "date"]))
                typ_sp = c4.selectbox("Event-Typ", spalten, index=f_sp(["event_type", "typ", "art"]))
                
                if st.button("Verarbeiten", type="primary"):
                    imp = 0
                    for index, row in df_import.iterrows():
                        p_n, p_t, p_d, p_y = str(row[name_sp]).strip(), str(row[teil_sp]).strip().lower(), str(row[dat_sp]).strip().split(" ")[0], str(row[typ_sp]).strip()
                        anw = p_t in ["ja", "zugesagt", "anwesend", "1", "true", "yes"]
                        sp = next((x for x in st.session_state.data["players"] if p_n.lower() in x["name"].lower() or x["name"].lower() in p_n.lower()), None)
                        if not sp: sp = {"id": max([x["id"] for x in st.session_state.data["players"]]+[0])+1, "name": p_n, "role": "Spieler", "number": "", "positions": ["ZM"], "training": [], "matches": []}; st.session_state.data["players"].append(sp)
                        if not any(t.get('date') == p_d and t.get('type') == p_y for t in sp.get("training", [])):
                            if "training" not in sp: sp["training"] = []
                            sp["training"].append({"date": p_d, "type": p_y, "present": anw}); imp += 1
                    speichere_daten(st.session_state.data); st.success(f"{imp} Einträge importiert!"); st.rerun()
            except Exception as e: st.error(f"Fehler: {e}")

# --- TAB 6: LIGA-ZENTRALE ---
with tab_map["🏆 Liga-Tabelle"]:
    st.subheader("🏆 Liga-Zentrale (U12 Bezirksliga 36)")
    st.link_button("🌐 Offizielle fussball.de Tabelle öffnen", "https://www.fussball.de/spieltagsuebersicht/u12-bzl-36-fruehjahr-bezirksebene-hamburg-d-junioren-bezirksliga-d-junioren-saison2526-hamburg/-/staffel/0306E7FA78000005VS5489BUVV5FEO72-G#!/", type="primary")
