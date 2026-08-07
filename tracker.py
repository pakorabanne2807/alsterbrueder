import base64
import io
import json
import os
import random
import re
import threading
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
# --- ENV-DATEI LADE-BEFEHL (ABGESICHERT) ---
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- GEMINI KI PAKET IMPORTER (NEUES SDK) ---
try:
  from google import genai
  from google.genai import types

  HAS_GEMINI_LIB = True
except ImportError:
  HAS_GEMINI_LIB = False

# --- KONFIGURATION & SETUP ---
st.set_page_config(
    page_title="Alsterbrüder", 
    page_icon="⚽", 
    layout="wide"
)

# --- RESPONSIVE SVG-VORSCHAU FÜR SKIZZEN ---
def render_svg_responsive(svg_code, height=340):
    if not svg_code or "<svg" not in svg_code:
        st.caption("Keine Skizze vorhanden.")
        return
        
    # CSS-Wrapper: Erzwingt flexible Skalierung auf 100% Breite ohne Scrollbalken
    html_wrapper = f"""
    <div style="display: flex; justify-content: center; align-items: center; width: 100%; overflow: hidden; padding: 5px;">
        <style>
            svg {{
                width: 100% !important;
                height: auto !important;
                max-height: {height - 20}px;
                display: block;
                margin: 0 auto;
            }}
        </style>
        {svg_code}
    </div>
    """
    st.components.v1.html(html_wrapper, height=height, scrolling=False)


# --- GENERATOR FÜR DRUCKFERTIGES DIN-A4 TRAININGSPLAN-PDF ---
def generiere_druck_html(einheits_titel, datum_str, phasen_liste):
    html_content = f"""
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="utf-8">
        <title>{einheits_titel}</title>
        <style>
            @page {{ size: A4 portrait; margin: 12mm; }}
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #0f172a; margin: 0; padding: 0; background-color: #fff; line-height: 1.3; font-size: 11pt; }}
            .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 3px solid #0284c7; padding-bottom: 8px; margin-bottom: 12px; }}
            .header h1 {{ margin: 0; font-size: 18pt; color: #0369a1; }}
            .header .meta {{ font-size: 9pt; color: #64748b; text-align: right; }}
            .phase-box {{ border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px; margin-bottom: 10px; page-break-inside: avoid; background-color: #f8fafc; }}
            .phase-title {{ font-size: 12pt; font-weight: bold; color: #0284c7; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; margin-bottom: 6px; }}
            .content-grid {{ display: flex; gap: 12px; }}
            .text-col {{ flex: 1.8; }}
            .gfx-col {{ flex: 1; max-width: 220px; text-align: center; display: flex; align-items: center; justify-content: center; }}
            .gfx-col svg {{ width: 100% !important; height: auto !important; max-height: 180px; border-radius: 4px; border: 1px solid #94a3b8; }}
            .section-label {{ font-weight: bold; color: #334155; font-size: 9.5pt; margin-top: 4px; display: block; }}
            .section-text {{ margin: 0 0 4px 0; font-size: 9pt; white-space: pre-line; color: #334155; }}
            .no-print {{ background: #e0f2fe; padding: 12px; text-align: center; font-weight: bold; margin-bottom: 15px; border-radius: 6px; border: 1px solid #bae6fd; }}
            .btn-print {{ background: #0284c7; color: white; border: none; padding: 8px 16px; font-size: 11pt; border-radius: 4px; cursor: pointer; margin-top: 6px; font-weight: bold; }}
            @media print {{ .no-print {{ display: none; }} body {{ background: white; }} .phase-box {{ border: 1px solid #94a3b8; }} }}
        </style>
    </head>
    <body>
        <div class="no-print">
            📄 Druckansicht bereit! Klicke auf den Button, um das PDF zu speichern:
            <br>
            <button class="btn-print" onclick="window.print()">🖨️ Als PDF speichern / Drucken</button>
        </div>
        
        <div class="header">
            <div>
                <h1>⚽ {einheits_titel}</h1>
                <span style="font-size: 10pt; color: #475569;">SC Alsterbrüder U13 – Trainingsplan</span>
            </div>
            <div class="meta">
                <b>Datum:</b> {datum_str}<br>
                <b>Feld:</b> Viertelfeld
            </div>
        </div>
    """

    for p in phasen_liste:
        svg_code = p.get('grafik', '').strip()
        if not svg_code or '<svg' not in svg_code:
            svg_code = p.get('svg_code', '').strip()

        html_content += f"""
        <div class="phase-box">
            <div class="phase-title">{p.get('phase', p.get('phase_title', 'Phase'))}: {p.get('name', p.get('exercise_name', 'Übung'))}</div>
            <div class="content-grid">
                <div class="text-col">
                    <span class="section-label">🛠️ Aufbau & Material:</span>
                    <p class="section-text">{p.get('aufbau', p.get('setup_text', '-'))}</p>
                    <span class="section-label">🏃‍♂️ Ablauf & Regeln:</span>
                    <p class="section-text">{p.get('flow_text', '-') if 'flow_text' in p else ''}</p>
                    <span class="section-label">🗣️ Coaching-Punkte:</span>
                    <p class="section-text">{p.get('coaching_points', '-') if 'coaching_points' in p else ''}</p>
                </div>
                <div class="gfx-col">
                    {svg_code if ("<svg" in svg_code) else "<span style='font-size: 8pt; color: #94a3b8;'>Keine Skizze</span>"}
                </div>
            </div>
        </div>
        """

    html_content += """
    </body>
    </html>
    """
    return html_content

import sqlite3
DB_FILE = "alsterbrueder_daten.db"

# --- SQLITE SETUP (KUGELSICHERER SPEICHER) ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Wir erstellen eine Tabelle mit einem einzigen Key-Value Paar ("main", "JSON-DATEN")
    c.execute('CREATE TABLE IF NOT EXISTS store (id TEXT PRIMARY KEY, data TEXT)')
    conn.commit()
    conn.close()

init_db()

POSITIONS = [
    "TW", "IV", "LV", "RV", "ZDM", "ZM", "ZOM", "LM", "RM", "LF", "RF", "ST"
]

# --- STANDARDISIERTE 5 TRAININGS-PHASEN ---
PHASEN_NAMEN = [
    "Phase 1: Aufwärmen",
    "Phase 2: Passspiel",
    "Phase 3: Rondo",
    "Phase 4: Duelle / Druck",
    "Phase 5: Abschlussspiel"
]

# --- SICHERE HOLUNG DER SENSIBLEN DATEN (SECRETS / ENV) ---
def get_secret_value(key_name, default_val=""):
    try:
        if key_name in st.secrets:
            return str(st.secrets[key_name]).strip()
    except Exception:
        pass
    return os.environ.get(key_name, default_val).strip()

API_URL = get_secret_value("API_URL", "")
GEMINI_API_KEY = get_secret_value("GEMINI_API_KEY", "")

def get_background_gemini_key():
    return get_secret_value("GEMINI_API_KEY", GEMINI_API_KEY)

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

# --- NATIVE HTML5 TAKTIKBOARD KOMPONENTE (PERFEKTE GEOMETRIE & MAGNETE) ---
def render_html5_taktikboard():
    html_code = r"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 0; background: #f8fafc; }
        .toolbar { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; align-items: center; background: #ffffff; padding: 8px 12px; border-radius: 8px; border: 1px solid #cbd5e1; }
        .toolbar-label { font-size: 13px; font-weight: bold; color: #334155; margin-right: 4px; }
        .drag-item { display: inline-flex; align-items: center; justify-content: center; width: 34px; height: 34px; background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px; cursor: grab; font-size: 18px; user-select: none; transition: all 0.15s ease; touch-action: manipulation; }
        .drag-item:active, .drag-item.selected-item { cursor: grabbing; transform: scale(1.15); background: #3b82f6; border-color: #1d4ed8; box-shadow: 0 0 8px rgba(59, 130, 246, 0.6); }
        .tool-btn { padding: 6px 12px; border-radius: 6px; border: 1px solid #94a3b8; font-size: 13px; cursor: pointer; background: #fff; color: #334155; }
        .tool-btn.active { background: #e2e8f0; border-color: #475569; font-weight: bold; box-shadow: inset 0 2px 4px rgba(0,0,0,0.1); }
        .btn-action { border: none; font-weight: bold; color: white; padding: 6px 10px; border-radius: 6px; cursor: pointer; font-size: 13px; }
        .btn-success { background: #16a34a; }
        .btn-danger { background: #ef4444; }
        .divider { border-left: 2px solid #e2e8f0; height: 24px; margin: 0 4px; }
        .status-bar { font-size: 12.5px; font-weight: bold; color: #1e3a8a; background: #f0fdf4; padding: 7px 12px; border-radius: 6px; margin-bottom: 8px; border: 1px solid #bbf7d0; }
        #board-container { position: relative; width: 550px; height: 380px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); border-radius: 8px; overflow: hidden; touch-action: none; }
        canvas { position: absolute; top: 0; left: 0; cursor: crosshair; touch-action: none; -webkit-user-select: none; user-select: none; }
        
        #textModal { display:none; position:absolute; z-index:100; left:50%; top:50%; transform:translate(-50%, -50%); background:white; padding:15px; border-radius:8px; box-shadow:0 4px 15px rgba(0,0,0,0.3); border:1px solid #cbd5e1; width:240px; }
        #textModalInput { width:100%; box-sizing:border-box; padding:6px; border-radius:4px; border:1px solid #94a3b8; font-family:sans-serif; resize:none; }
    </style>
    </head>
    <body>

    <div class="toolbar">
        <div class="toolbar-label">Symbole:</div>
        <div class="drag-item" draggable="true" ondragstart="onDragStart(event, 'dot', '#facc15')" onclick="selectItemMobile(this, 'dot', '#facc15')" title="Spieler Gelb">🟡</div>
        <div class="drag-item" draggable="true" ondragstart="onDragStart(event, 'dot', '#ef4444')" onclick="selectItemMobile(this, 'dot', '#ef4444')" title="Spieler Rot">🔴</div>
        <div class="drag-item" draggable="true" ondragstart="onDragStart(event, 'dot', '#000000')" onclick="selectItemMobile(this, 'dot', '#000000')" title="Torwart">⚫</div>
        <div class="drag-item" draggable="true" ondragstart="onDragStart(event, 'utensil', 'cone', '#ea580c')" onclick="selectItemMobile(this, 'utensil', 'cone', '#ea580c')" title="Hütchen">🔺</div>
        <div class="drag-item" draggable="true" ondragstart="onDragStart(event, 'utensil', 'pole', '#facc15')" onclick="selectItemMobile(this, 'utensil', 'pole', '#facc15')" title="Stange">📍</div>
        <div class="drag-item" draggable="true" ondragstart="onDragStart(event, 'utensil', 'minigoal', '#ffffff')" onclick="selectItemMobile(this, 'utensil', 'minigoal', '#ffffff')" title="Minitor (H)">🥅</div>
        <div class="drag-item" draggable="true" ondragstart="onDragStart(event, 'utensil', 'minigoal_v', '#ffffff')" onclick="selectItemMobile(this, 'utensil', 'minigoal_v', '#ffffff')" title="Minitor (V)">🥅<sup style="font-size:10px">V</sup></div>
        <div class="drag-item" draggable="true" ondragstart="onDragStart(event, 'utensil', 'largegoal', '#ffffff')" onclick="selectItemMobile(this, 'utensil', 'largegoal', '#ffffff')" title="Großes Tor (H)">🥅<sub style="font-size:10px">LH</sub></div>
        <div class="drag-item" draggable="true" ondragstart="onDragStart(event, 'utensil', 'largegoal_v', '#ffffff')" onclick="selectItemMobile(this, 'utensil', 'largegoal_v', '#ffffff')" title="Großes Tor (V)">🥅<sub style="font-size:10px">LV</sub></div>
        <button class="tool-btn" style="margin-left:auto;" onclick="addTextShape()">🔤 Text</button>
    </div>

    <div class="toolbar">
        <div class="toolbar-label">Tools:</div>
        <button id="btn_move" class="tool-btn active" onclick="setTool('move')" title="Objekte verschieben">✋ Bewegen</button>
        <button id="btn_multiselect" class="tool-btn" onclick="setTool('multiselect')" title="Auf dem Handy: Tippe mehrere Symbole nacheinander an">☑️ Mehrfach</button>
        <button id="btn_line" class="tool-btn" onclick="setTool('line')">📏 Pass</button>
        <button id="btn_dashed" class="tool-btn" onclick="setTool('dashed')">🏁 Lauf</button>
        <button id="btn_curve" class="tool-btn" onclick="setTool('curve')">➰ Kurve</button>
        
        <div class="divider"></div>
        <button class="tool-btn" onclick="copySelection()" title="Auswahl kopieren (Strg+C)">📋 Kopieren</button>
        <button class="tool-btn" onclick="pasteSelection()" title="Auswahl einfügen (Strg+V)">📥 Einfügen</button>
        <button class="tool-btn" style="color: #ef4444;" onclick="deleteSelection()" title="Auswahl löschen (Entf)">🗑️ Löschen</button>
        
        <div class="divider"></div>
        <button class="tool-btn" onclick="exportShapes()" title="Bauplan für später speichern">💾 Export</button>
        <button class="tool-btn" onclick="importShapes()" title="Bauplan wieder laden">📂 Import</button>
        <button class="tool-btn" style="background:#0284c7; color:white; font-weight:bold;" onclick="sendToExercise()" title="Skizze direkt an eine Übung anhängen">⚽ An Übung senden</button>
        
        <div class="divider"></div>
        <select id="templateSelect" style="margin-left:auto; padding:5px; border-radius:6px; border:1px solid #94a3b8;" onchange="resetPitch()">
            <option value="Plain">🟩 Leeres Feld</option>
            <option value="EinTor">🥅 1 Tor & 16er</option>
            <option value="ZweiTore">🥅🥅 2 Tore</option>
        </select>
        <button class="btn-action btn-danger" onclick="clearDrawings()" title="Alles löschen">💥</button>
        <button class="btn-action btn-success" onclick="downloadSketch()" title="Bild als PNG speichern">📸</button>
    </div>

    <div id="statusBar" class="status-bar">💡 Aktiviere "Markieren" und ziehe einen Rahmen über den Rasen, um mehrere Objekte zu wählen!</div>

    <div id="board-container">
        <canvas id="pitchCanvas" width="550" height="380"></canvas>
        <canvas id="drawCanvas" width="550" height="380"></canvas>
        
        <!-- Text-Eingabefenster -->
        <div id="textModal">
            <div style="margin-bottom:8px; font-weight:bold; font-size:13px; color:#334155;">📝 Text eingeben:</div>
            <textarea id="textModalInput" rows="3" placeholder="Dein Text hier..."></textarea>
            <div style="font-size:10px; color:#64748b; margin-top:4px;">[Enter] Speichern | [Strg+Enter] Absatz</div>
            <div style="margin-top:10px; display:flex; justify-content:flex-end; gap:8px;">
                <button onclick="closeTextModal(false)" style="padding:6px 12px; cursor:pointer; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:4px; font-size:12px;">Abbrechen</button>
                <button onclick="closeTextModal(true)" style="padding:6px 12px; cursor:pointer; background:#1e3a8a; color:white; border:none; border-radius:4px; font-weight:bold; font-size:12px;">Speichern</button>
            </div>
        </div>
    </div>

    <script>
        const pitchCanvas = document.getElementById('pitchCanvas');
        const pitchCtx = pitchCanvas.getContext('2d');
        const drawCanvas = document.getElementById('drawCanvas');
        const drawCtx = drawCanvas.getContext('2d');
        const statusBar = document.getElementById('statusBar');

        let shapes = []; 
        let history = []; 
        let curveStep = 0;
        let curveP0 = {x: 0, y: 0};
        let curveP2 = {x: 0, y: 0};
        
        let selectedShapes = [];
        let clipboard = [];
        let isSelecting = false;
        let selStart = {x: 0, y: 0};
        let selEnd = {x: 0, y: 0};
        
        let isDragging = false;
        let dragTarget = null; 
        let isLineDrawing = false;
        let lineStart = {x: 0, y: 0};
        let activeTool = 'move';
        
        // Touch/Mobile Platzierungs-Variable
        let selectedMobileItem = null;

        function selectItemMobile(element, type, subtypeOrColor, overrideColor = null) {
            document.querySelectorAll('.drag-item').forEach(el => el.classList.remove('selected-item'));
            
            if (selectedMobileItem && selectedMobileItem.element === element) {
                selectedMobileItem = null;
                updateStatus();
                return;
            }
            
            element.classList.add('selected-item');
            selectedMobileItem = { element: element, type: type, subtypeOrColor: subtypeOrColor, overrideColor: overrideColor };
            statusBar.innerText = "👉 Tippe jetzt auf das Spielfeld, um das Symbol zu platzieren!";
        }

        function setTool(t) {
            activeTool = t;
            document.querySelectorAll('.tool-btn').forEach(b => b.classList.remove('active'));
            document.getElementById('btn_' + t).classList.add('active');
            curveStep = 0;
            updateStatus();
            redrawAll();
        }

        function updateStatus() {
            if (activeTool === 'curve') {
                if (curveStep === 0) statusBar.innerText = "🎯 Flugkurve: 1. Klick = STARTPUNKT setzen.";
                else if (curveStep === 1) statusBar.innerText = "🎯 Flugkurve: 2. Klick = ZIELPUNKT setzen.";
                else if (curveStep === 2) statusBar.innerText = "🎯 Flugkurve: Bewege Maus für Bogen & klicke zum FIXIEREN!";
            } else if (activeTool === 'line' || activeTool === 'dashed') {
                statusBar.innerText = "📏 Pass/Laufweg: Klicke auf den freien Rasen & ziehe die Maus.";
            } else {
                statusBar.innerText = "💡 Ziehe einen Rahmen über den Rasen, um mehrere Symbole zu markieren!";
            }
        }

        function exportShapes() {
            if (shapes.length === 0) {
                alert("Es gibt nichts zu exportieren! Das Feld ist leer.");
                return;
            }
            const dataStr = JSON.stringify(shapes);
            prompt("Kopiere diesen Taktik-Code (Strg+C) und füge ihn in das Textfeld deiner Übung ein:", dataStr);
            statusBar.innerText = "✅ Taktik-Code bereitgestellt!";
        }

        function importShapes() {
            const dataStr = prompt("Füge hier deinen Taktik-Code ein:");
            if (dataStr) {
                try {
                    const parsed = JSON.parse(dataStr);
                    if (Array.isArray(parsed)) {
                        saveSnapshot();
                        shapes = parsed;
                        selectedShapes = [];
                        redrawAll();
                        statusBar.innerText = "📂 Skizze erfolgreich geladen und kann jetzt bearbeitet werden!";
                    } else {
                        alert("Das sieht nicht nach einem gültigen Taktik-Code aus.");
                    }
                } catch(e) {
                    alert("Ungültiger Code! Fehler beim Einlesen.");
                }
            }
        }

        function sendToExercise() {
            if (shapes.length === 0) {
                alert("Das Feld ist leer! Zeichne zuerst eine Skizze.");
                return;
            }
            const dataStr = JSON.stringify(shapes);
            prompt("📋 Kopiere diesen Taktik-Code (Strg+C) und füge ihn unten im Zuordnungs-Formular ein:", dataStr);
            statusBar.innerText = "⚽ Taktik-Code in die Zwischenablage kopiert!";
        }

        function onDragStart(e, type, subtypeOrColor, overrideColor = null) {
            const data = { type: type };
            if (type === 'dot') data.color = subtypeOrColor;
            else if (type === 'utensil') {
                data.uType = subtypeOrColor;
                data.color = overrideColor;
            }
            e.dataTransfer.setData('text/plain', JSON.stringify(data));
            e.dataTransfer.effectAllowed = 'copy';
        }

        drawCanvas.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'copy';
        });

        drawCanvas.addEventListener('drop', (e) => {
            e.preventDefault();
            const pos = getPos(e);
            try {
                const data = JSON.parse(e.dataTransfer.getData('text/plain'));
                saveSnapshot();
                let newShape;
                if (data.type === 'dot') {
                    newShape = { type: 'dot', x: pos.x, y: pos.y, color: data.color };
                    shapes.push(newShape);
                } else if (data.type === 'utensil') {
                    newShape = { type: 'utensil', uType: data.uType, x: pos.x, y: pos.y, color: data.color || '#ffffff' };
                    shapes.push(newShape);
                }
                if (newShape) selectedShapes = [newShape];
                setTool('move');
                redrawAll();
            } catch (err) {}
        });

        const textModal = document.getElementById('textModal');
        const textModalInput = document.getElementById('textModalInput');
        let pendingTextPos = null;

        function addTextShape() {
            pendingTextPos = { x: 275, y: 190 };
            textModal.style.display = 'block';
            textModalInput.value = '';
            textModalInput.focus();
            statusBar.innerText = "🔤 Gib deinen Text ein.";
        }

        function closeTextModal(save) {
            textModal.style.display = 'none';
            if (save) {
                const txt = textModalInput.value.trim();
                if (txt && pendingTextPos) {
                    saveSnapshot();
                    let newShape = { type: 'text', text: txt, x: pendingTextPos.x, y: pendingTextPos.y, color: '#000000' };
                    shapes.push(newShape);
                    selectedShapes = [newShape]; 
                    setTool('move');
                    redrawAll();
                    statusBar.innerText = "🔤 Text platziert. Du kannst ihn jetzt verschieben.";
                }
            } else {
                updateStatus();
            }
            pendingTextPos = null;
        }

        textModalInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && e.ctrlKey) {
                e.preventDefault();
                const cursorPos = this.selectionStart;
                const textBefore = this.value.substring(0, cursorPos);
                const textAfter = this.value.substring(this.selectionEnd, this.value.length);
                this.value = textBefore + '\\n' + textAfter;
                this.selectionStart = this.selectionEnd = cursorPos + 1;
            } else if (e.key === 'Enter' && !e.ctrlKey) {
                e.preventDefault();
                closeTextModal(true);
            }
        });

        function deleteSelection() {
            if (selectedShapes.length > 0) {
                saveSnapshot();
                shapes = shapes.filter(s => !selectedShapes.includes(s));
                selectedShapes = [];
                redrawAll();
                statusBar.innerText = "🗑️ Auswahl gelöscht.";
            }
        }

        function copySelection() {
            if (selectedShapes.length > 0) {
                clipboard = JSON.parse(JSON.stringify(selectedShapes));
                statusBar.innerText = `📋 ${clipboard.length} Objekt(e) kopiert!`;
            }
        }

        function pasteSelection() {
            if (clipboard.length > 0) {
                saveSnapshot();
                selectedShapes = [];
                const newShapes = JSON.parse(JSON.stringify(clipboard));
                newShapes.forEach(s => {
                    const offset = 20;
                    if (s.x !== undefined) { s.x += offset; s.y += offset; }
                    if (s.x1 !== undefined) { s.x1 += offset; s.y1 += offset; s.x2 += offset; s.y2 += offset; }
                    if (s.x0 !== undefined) { s.x0 += offset; s.y0 += offset; s.cx += offset; s.cy += offset; s.x2 += offset; s.y2 += offset; }
                    shapes.push(s);
                    selectedShapes.push(s);
                });
                clipboard = JSON.parse(JSON.stringify(newShapes)); 
                setTool('move');
                redrawAll();
                statusBar.innerText = "📥 Objekte eingefügt!";
            }
        }

        window.addEventListener('keydown', function(e) {
            if (document.activeElement.tagName === 'TEXTAREA' || document.activeElement.tagName === 'INPUT') return;
            
            if (e.key === 'Delete' || e.key === 'Backspace') {
                deleteSelection();
            } else if (e.key === 'c' && (e.ctrlKey || e.metaKey)) {
                copySelection();
            } else if (e.key === 'v' && (e.ctrlKey || e.metaKey)) {
                pasteSelection();
            }
        });

        function drawPitch() {
            const type = document.getElementById('templateSelect').value;
            const w = 550, h = 380;
            
            pitchCtx.fillStyle = "#2e7d32";
            pitchCtx.fillRect(0, 0, w, h);
            
            pitchCtx.fillStyle = "#388e3c";
            for(let i=0; i<w; i+=50) {
                if((i/50)%2 === 0) pitchCtx.fillRect(i, 0, 50, h);
            }

            pitchCtx.strokeStyle = "#ffffff";
            pitchCtx.lineWidth = 3;

            if(type === "EinTor") {
                const goalLineY = 350;
                const penaltyBoxTopY = 200;
                const penaltySpotY = 270;
                const centerX = 275;

                pitchCtx.strokeRect(30, 30, w-60, h-60);
                pitchCtx.strokeRect(100, penaltyBoxTopY, 350, 150);
                pitchCtx.strokeRect(180, 290, 190, 60);
                
                pitchCtx.fillStyle = "#e2e8f0";
                pitchCtx.fillRect(215, goalLineY, 120, 16);
                pitchCtx.strokeRect(215, goalLineY, 120, 16);
                
                pitchCtx.fillStyle = "#ffffff";
                pitchCtx.beginPath(); pitchCtx.arc(centerX, penaltySpotY, 4, 0, Math.PI*2); pitchCtx.fill();
                
                const arcRadius = 85;
                const yDist = penaltySpotY - penaltyBoxTopY; 
                const intersectAngle = Math.asin(yDist / arcRadius);
                
                pitchCtx.beginPath();
                pitchCtx.arc(centerX, penaltySpotY, arcRadius, Math.PI + intersectAngle, Math.PI * 2 - intersectAngle);
                pitchCtx.stroke();
                
            } else if (type === "ZweiTore") {
                const centerX = 275;
                pitchCtx.strokeRect(30, 30, w-60, h-60);
                pitchCtx.beginPath(); pitchCtx.moveTo(30, h/2); pitchCtx.lineTo(w-30, h/2); pitchCtx.stroke();
                pitchCtx.beginPath(); pitchCtx.arc(centerX, h/2, 50, 0, Math.PI*2); pitchCtx.stroke();
                pitchCtx.fillStyle = "#ffffff";
                pitchCtx.beginPath(); pitchCtx.arc(centerX, h/2, 4, 0, Math.PI*2); pitchCtx.fill();
                
                pitchCtx.strokeRect(100, 270, 350, 80);
                pitchCtx.strokeRect(180, 320, 190, 30);
                pitchCtx.fillStyle = "#e2e8f0"; pitchCtx.fillRect(215, 350, 120, 16); pitchCtx.strokeRect(215, 350, 120, 16);
                pitchCtx.fillStyle = "#ffffff"; pitchCtx.beginPath(); pitchCtx.arc(centerX, 290, 4, 0, Math.PI*2); pitchCtx.fill();
                
                pitchCtx.strokeRect(100, 30, 350, 80);
                pitchCtx.strokeRect(180, 30, 190, 30);
                pitchCtx.fillStyle = "#e2e8f0"; pitchCtx.fillRect(215, 14, 120, 16); pitchCtx.strokeRect(215, 14, 120, 16);
                pitchCtx.fillStyle = "#ffffff"; pitchCtx.beginPath(); pitchCtx.arc(centerX, 90, 4, 0, Math.PI*2); pitchCtx.fill();
            } else {
                pitchCtx.strokeRect(30, 30, w-60, h-60);
            }
        }

        function resetPitch() { drawPitch(); curveStep = 0; updateStatus(); }

        function drawArrowHead(ctx, fromX, fromY, toX, toY, color) {
            const headlen = 13; const dx = toX - fromX; const dy = toY - fromY; const angle = Math.atan2(dy, dx);
            ctx.fillStyle = color; ctx.beginPath();
            ctx.moveTo(toX, toY);
            ctx.lineTo(toX - headlen * Math.cos(angle - Math.PI / 6), toY - headlen * Math.sin(angle - Math.PI / 6));
            ctx.lineTo(toX - headlen * Math.cos(angle + Math.PI / 6), toY - headlen * Math.sin(angle + Math.PI / 6));
            ctx.closePath(); ctx.fill();
        }

        function redrawAll() {
            drawCtx.clearRect(0, 0, 550, 380);

            shapes.forEach(s => {
                drawCtx.strokeStyle = s.color;
                drawCtx.fillStyle = s.color;

                if (s.type === 'dot') {
                    drawCtx.beginPath(); drawCtx.arc(s.x, s.y, 11, 0, Math.PI * 2); drawCtx.fill();
                    drawCtx.strokeStyle = "#ffffff"; drawCtx.lineWidth = 2; drawCtx.stroke();
                } else if (s.type === 'line' || s.type === 'dashed') {
                    drawCtx.lineWidth = 4; drawCtx.setLineDash(s.type === 'dashed' ? [8, 6] : []);
                    drawCtx.beginPath(); drawCtx.moveTo(s.x1, s.y1); drawCtx.lineTo(s.x2, s.y2); drawCtx.stroke();
                    drawCtx.setLineDash([]); drawArrowHead(drawCtx, s.x1, s.y1, s.x2, s.y2, s.color);
                } else if (s.type === 'curve') {
                    drawCtx.lineWidth = 4; drawCtx.beginPath(); drawCtx.moveTo(s.x0, s.y0);
                    drawCtx.quadraticCurveTo(s.cx, s.cy, s.x2, s.y2); drawCtx.stroke();
                    drawArrowHead(drawCtx, s.cx, s.cy, s.x2, s.y2, s.color);
                } else if (s.type === 'text') {
                    drawCtx.font = "bold 15px Arial";
                    drawCtx.shadowColor = "rgba(255,255,255,0.7)"; drawCtx.shadowBlur = 4;
                    const lines = s.text.split('\\n');
                    for (let i = 0; i < lines.length; i++) {
                        drawCtx.fillText(lines[i], s.x - 10, s.y + 5 + (i * 18));
                    }
                    drawCtx.shadowBlur = 0;
                } else if (s.type === 'utensil') {
                    if (s.uType === 'cone') {
                        drawCtx.fillStyle = "#ea580c"; drawCtx.beginPath();
                        drawCtx.moveTo(s.x, s.y - 10); drawCtx.lineTo(s.x + 10, s.y + 10); drawCtx.lineTo(s.x - 10, s.y + 10); drawCtx.fill();
                    } else if (s.uType === 'pole') {
                        drawCtx.strokeStyle = "#facc15"; drawCtx.lineWidth = 4;
                        drawCtx.beginPath(); drawCtx.moveTo(s.x, s.y + 12); drawCtx.lineTo(s.x, s.y - 12); drawCtx.stroke();
                        drawCtx.fillStyle = "#000"; drawCtx.beginPath(); drawCtx.arc(s.x, s.y + 12, 4, 0, Math.PI*2); drawCtx.fill();
                    } else if (s.uType === 'minigoal') {
                        drawCtx.strokeStyle = "#ffffff"; drawCtx.lineWidth = 4; 
                        drawCtx.strokeRect(s.x - 20, s.y - 5, 40, 10);
                        drawCtx.strokeStyle = "rgba(255,255,255,0.4)"; drawCtx.lineWidth = 1; drawCtx.beginPath();
                        for(let i=-15; i<=15; i+=5) { drawCtx.moveTo(s.x + i, s.y - 5); drawCtx.lineTo(s.x + i, s.y + 5); }
                        drawCtx.stroke();
                    } else if (s.uType === 'minigoal_v') {
                        drawCtx.strokeStyle = "#ffffff"; drawCtx.lineWidth = 4; 
                        drawCtx.strokeRect(s.x - 5, s.y - 20, 10, 40);
                        drawCtx.strokeStyle = "rgba(255,255,255,0.4)"; drawCtx.lineWidth = 1; drawCtx.beginPath();
                        for(let i=-15; i<=15; i+=5) { drawCtx.moveTo(s.x - 5, s.y + i); drawCtx.lineTo(s.x + 5, s.y + i); }
                        drawCtx.stroke();
                    } else if (s.uType === 'largegoal') {
                        drawCtx.strokeStyle = "#ffffff"; drawCtx.lineWidth = 5; 
                        drawCtx.strokeRect(s.x - 45, s.y - 10, 90, 20);
                        drawCtx.strokeStyle = "rgba(255,255,255,0.4)"; drawCtx.lineWidth = 1.5; drawCtx.beginPath();
                        for(let i=-40; i<=40; i+=8) { drawCtx.moveTo(s.x + i, s.y - 10); drawCtx.lineTo(s.x + i, s.y + 10); }
                        for(let j=-5; j<=5; j+=5) { drawCtx.moveTo(s.x - 45, s.y + j); drawCtx.lineTo(s.x + 45, s.y + j); }
                        drawCtx.stroke();
                    } else if (s.uType === 'largegoal_v') {
                        drawCtx.strokeStyle = "#ffffff"; drawCtx.lineWidth = 5; 
                        drawCtx.strokeRect(s.x - 10, s.y - 45, 20, 90);
                        drawCtx.strokeStyle = "rgba(255,255,255,0.4)"; drawCtx.lineWidth = 1.5; drawCtx.beginPath();
                        for(let i=-40; i<=40; i+=8) { drawCtx.moveTo(s.x - 10, s.y + i); drawCtx.lineTo(s.x + 10, s.y + i); }
                        for(let j=-5; j<=5; j+=5) { drawCtx.moveTo(s.x + j, s.y - 45); drawCtx.lineTo(s.x + j, s.y + 45); }
                        drawCtx.stroke();
                    }
                }
            });

            // Highlights
            selectedShapes.forEach(s => {
                drawCtx.strokeStyle = "#3b82f6"; 
                drawCtx.lineWidth = 2;
                drawCtx.setLineDash([4, 4]);
                
                if (s.type === 'dot' || s.type === 'text' || s.type === 'utensil') {
                    drawCtx.beginPath(); drawCtx.arc(s.x, s.y, 22, 0, Math.PI * 2); drawCtx.stroke();
                } else if (s.type === 'line' || s.type === 'dashed') {
                    drawCtx.beginPath(); drawCtx.arc(s.x1, s.y1, 10, 0, Math.PI * 2); drawCtx.stroke();
                    drawCtx.beginPath(); drawCtx.arc(s.x2, s.y2, 10, 0, Math.PI * 2); drawCtx.stroke();
                    let midX = (s.x1 + s.x2) / 2; let midY = (s.y1 + s.y2) / 2;
                    drawCtx.beginPath(); drawCtx.arc(midX, midY, 14, 0, Math.PI * 2); drawCtx.stroke();
                } else if (s.type === 'curve') {
                    drawCtx.beginPath(); drawCtx.arc(s.x0, s.y0, 10, 0, Math.PI * 2); drawCtx.stroke();
                    drawCtx.beginPath(); drawCtx.arc(s.x2, s.y2, 10, 0, Math.PI * 2); drawCtx.stroke();
                    let midX = (s.x0 + s.x2) / 2; let midY = (s.y0 + s.y2) / 2;
                    drawCtx.beginPath(); drawCtx.arc(midX, midY, 14, 0, Math.PI * 2); drawCtx.stroke();
                }
                drawCtx.setLineDash([]);
            });

            // Selektions-Rechteck
            if (isSelecting) {
                drawCtx.fillStyle = "rgba(59, 130, 246, 0.2)";
                drawCtx.strokeStyle = "rgba(59, 130, 246, 0.8)";
                drawCtx.lineWidth = 1;
                drawCtx.fillRect(selStart.x, selStart.y, selEnd.x - selStart.x, selEnd.y - selStart.y);
                drawCtx.strokeRect(selStart.x, selStart.y, selEnd.x - selStart.x, selEnd.y - selStart.y);
            }
        }

        function saveSnapshot() { history.push(JSON.parse(JSON.stringify(shapes))); }
        function undoLast() { curveStep = 0; if (history.length > 0) { shapes = history.pop(); selectedShapes = []; redrawAll(); } updateStatus(); }
        function clearDrawings() { curveStep = 0; shapes = []; history = []; selectedShapes = []; drawCtx.clearRect(0, 0, 550, 380); updateStatus(); }
        function getPos(e) { const rect = drawCanvas.getBoundingClientRect(); return { x: e.clientX - rect.left, y: e.clientY - rect.top }; }

        // Hilfsfunktion für Touch-Koordinaten auf dem Smartphone
        function getTouchPos(e) {
            const rect = drawCanvas.getBoundingClientRect();
            const touch = e.touches[0] || e.changedTouches[0];
            return {
                x: touch.clientX - rect.left,
                y: touch.clientY - rect.top
            };
        }

        function getHitHandle(pos) {
            // Auf Touch-Geräten nutzen wir deutlich größere Radien (30px / 35px) zum "Anfassen"
            const rDot = 30;
            const rHandle = 35; 
            
            for (let i = shapes.length - 1; i >= 0; i--) {
                let s = shapes[i];
                if (s.type === 'dot' || s.type === 'text' || s.type === 'utensil') {
                    if (Math.hypot(s.x - pos.x, s.y - pos.y) <= rDot) return { shape: s, handle: 'center' };
                } else if (s.type === 'line' || s.type === 'dashed') {
                    if (Math.hypot(s.x1 - pos.x, s.y1 - pos.y) <= rHandle) return { shape: s, handle: 'start' };
                    if (Math.hypot(s.x2 - pos.x, s.y2 - pos.y) <= rHandle) return { shape: s, handle: 'end' };
                    let midX = (s.x1 + s.x2) / 2; let midY = (s.y1 + s.y2) / 2;
                    if (Math.hypot(midX - pos.x, midY - pos.y) <= rHandle) return { shape: s, handle: 'center' };
                } else if (s.type === 'curve') {
                    if (Math.hypot(s.x0 - pos.x, s.y0 - pos.y) <= rHandle) return { shape: s, handle: 'start' };
                    if (Math.hypot(s.cx - pos.x, s.cy - pos.y) <= rHandle) return { shape: s, handle: 'control' };
                    if (Math.hypot(s.x2 - pos.x, s.y2 - pos.y) <= rHandle) return { shape: s, handle: 'end' };
                    let midX = (s.x0 + s.x2) / 2; let midY = (s.y0 + s.y2) / 2;
                    if (Math.hypot(midX - pos.x, midY - pos.y) <= rHandle) return { shape: s, handle: 'center' };
                }
            } return null;
        }

        function downloadSketch() {
            selectedShapes = []; redrawAll();
            const combinedCanvas = document.createElement('canvas'); combinedCanvas.width = 550; combinedCanvas.height = 380;
            const combCtx = combinedCanvas.getContext('2d');
            combCtx.drawImage(pitchCanvas, 0, 0); combCtx.drawImage(drawCanvas, 0, 0);
            const link = document.createElement('a'); link.download = 'taktik_skizze.png'; link.href = combinedCanvas.toDataURL('image/png'); link.click();
        }

        // --- MAUS EVENTS ---
        
        drawCanvas.addEventListener('dblclick', (e) => {
            const pos = getPos(e);
            const hit = getHitHandle(pos);
            if (hit) {
                saveSnapshot();
                shapes = shapes.filter(s => s !== hit.shape);
                selectedShapes = selectedShapes.filter(s => s !== hit.shape);
                isDragging = false;
                dragTarget = null;
                redrawAll();
                statusBar.innerText = "🗑️ Symbol gelöscht!";
            }
        });

        drawCanvas.addEventListener('mousedown', (e) => {
            const pos = getPos(e); 
            
            // Mobile-Platzierung ausführen, falls ein Symbol ausgewählt ist
            if (selectedMobileItem) {
                saveSnapshot();
                let newShape;
                if (selectedMobileItem.type === 'dot') {
                    newShape = { type: 'dot', x: pos.x, y: pos.y, color: selectedMobileItem.subtypeOrColor };
                } else if (selectedMobileItem.type === 'utensil') {
                    newShape = { type: 'utensil', uType: selectedMobileItem.subtypeOrColor, x: pos.x, y: pos.y, color: selectedMobileItem.overrideColor || '#ffffff' };
                }
                if (newShape) {
                    shapes.push(newShape);
                    selectedShapes = [newShape];
                }
                selectedMobileItem.element.classList.remove('selected-item');
                selectedMobileItem = null;
                setTool('move');
                redrawAll();
                return;
            }

            const hit = getHitHandle(pos);
            if (activeTool === 'move') {
                if (hit) {
                    saveSnapshot(); 
                    isDragging = true; 
                    dragTarget = hit; 
                    dragTarget.lastX = pos.x; 
                    dragTarget.lastY = pos.y; 
                    
                    if (!selectedShapes.includes(hit.shape)) {
                        selectedShapes = [hit.shape];
                    }
                    redrawAll();
                    return;
                } else {
                    selectedShapes = [];
                    isSelecting = true;
                    selStart = pos;
                    selEnd = pos;
                    redrawAll();
                    return;
                }
            }

            const drawColor = "#ffffff"; 
            if (activeTool === 'curve') {
                if (curveStep === 0) { curveP0 = pos; curveStep = 1; updateStatus(); } 
                else if (curveStep === 1) { curveP2 = pos; curveStep = 2; updateStatus(); } 
                else if (curveStep === 2) {
                    saveSnapshot();
                    let newShape = { type: 'curve', x0: curveP0.x, y0: curveP0.y, cx: pos.x, cy: pos.y, x2: curveP2.x, y2: curveP2.y, color: drawColor };
                    shapes.push(newShape);
                    selectedShapes = [];
                    curveStep = 0; 
                    redrawAll();
                }
            } else if (activeTool === 'line' || activeTool === 'dashed') { 
                isLineDrawing = true; 
                lineStart = pos; 
            }
        });

        drawCanvas.addEventListener('mousemove', (e) => {
            const pos = getPos(e); 
            const drawColor = "#ffffff";

            if (isDragging && dragTarget) {
                const dx = pos.x - dragTarget.lastX;
                const dy = pos.y - dragTarget.lastY;

                if (selectedShapes.length > 1 && selectedShapes.includes(dragTarget.shape)) {
                    selectedShapes.forEach(s => {
                        if (s.type === 'dot' || s.type === 'text' || s.type === 'utensil') { 
                            s.x += dx; s.y += dy; 
                        } else if (s.type === 'line' || s.type === 'dashed') { 
                            s.x1 += dx; s.y1 += dy; s.x2 += dx; s.y2 += dy; 
                        } else if (s.type === 'curve') { 
                            s.x0 += dx; s.y0 += dy; s.cx += dx; s.cy += dy; s.x2 += dx; s.y2 += dy; 
                        }
                    });
                } else {
                    const s = dragTarget.shape; 
                    const h = dragTarget.handle;
                    
                    if (s.type === 'dot' || s.type === 'text' || s.type === 'utensil') { 
                        s.x = pos.x; s.y = pos.y; 
                    }
                    else if (s.type === 'line' || s.type === 'dashed') { 
                        if (h === 'start') { s.x1 = pos.x; s.y1 = pos.y; } 
                        else if (h === 'end') { s.x2 = pos.x; s.y2 = pos.y; } 
                        else if (h === 'center') { s.x1 += dx; s.y1 += dy; s.x2 += dx; s.y2 += dy; }
                    }
                    else if (s.type === 'curve') { 
                        if (h === 'start') { s.x0 = pos.x; s.y0 = pos.y; } 
                        else if (h === 'control') { s.cx = pos.x; s.cy = pos.y; } 
                        else if (h === 'end') { s.x2 = pos.x; s.y2 = pos.y; } 
                        else if (h === 'center') { s.x0 += dx; s.y0 += dy; s.cx += dx; s.cy += dy; s.x2 += dx; s.y2 += dy; }
                    }
                }
                
                dragTarget.lastX = pos.x;
                dragTarget.lastY = pos.y;
                redrawAll();
            } else if (isSelecting) {
                selEnd = pos;
                redrawAll();
            } else if (activeTool === 'curve') {
                if (curveStep === 1) {
                    redrawAll(); drawCtx.strokeStyle = drawColor; drawCtx.lineWidth = 2; drawCtx.setLineDash([4, 4]); drawCtx.beginPath(); drawCtx.moveTo(curveP0.x, curveP0.y); drawCtx.lineTo(pos.x, pos.y); drawCtx.stroke(); drawCtx.setLineDash([]);
                } else if (curveStep === 2) {
                    redrawAll(); drawCtx.strokeStyle = drawColor; drawCtx.lineWidth = 4; drawCtx.beginPath(); drawCtx.moveTo(curveP0.x, curveP0.y); drawCtx.quadraticCurveTo(pos.x, pos.y, curveP2.x, curveP2.y); drawCtx.stroke(); drawArrowHead(drawCtx, pos.x, pos.y, curveP2.x, curveP2.y, drawColor);
                }
            } else if (isLineDrawing) {
                redrawAll(); drawCtx.strokeStyle = drawColor; drawCtx.lineWidth = 4; drawCtx.setLineDash(activeTool === 'dashed' ? [8, 6] : []); drawCtx.beginPath(); drawCtx.moveTo(lineStart.x, lineStart.y); drawCtx.lineTo(pos.x, pos.y); drawCtx.stroke(); drawCtx.setLineDash([]); drawArrowHead(drawCtx, lineStart.x, lineStart.y, pos.x, pos.y, drawColor);
            }
        });

        drawCanvas.addEventListener('mouseup', (e) => {
            const pos = getPos(e); 
            const drawColor = "#ffffff";
            if (isDragging) { 
                isDragging = false; 
                dragTarget = null; 
            } else if (isSelecting) {
                isSelecting = false;
                
                const minX = Math.min(selStart.x, selEnd.x);
                const maxX = Math.max(selStart.x, selEnd.x);
                const minY = Math.min(selStart.y, selEnd.y);
                const maxY = Math.max(selStart.y, selEnd.y);

                selectedShapes = shapes.filter(s => {
                    if (s.type === 'dot' || s.type === 'text' || s.type === 'utensil') {
                        return s.x >= minX && s.x <= maxX && s.y >= minY && s.y <= maxY;
                    } else if (s.type === 'line' || s.type === 'dashed') {
                        return s.x1 >= minX && s.x1 <= maxX && s.y1 >= minY && s.y1 <= maxY &&
                               s.x2 >= minX && s.x2 <= maxX && s.y2 >= minY && s.y2 <= maxY;
                    } else if (s.type === 'curve') {
                        return s.x0 >= minX && s.x0 <= maxX && s.y0 >= minY && s.y0 <= maxY &&
                               s.x2 >= minX && s.x2 <= maxX && s.y2 >= minY && s.y2 <= maxY;
                    }
                    return false;
                });
                
                redrawAll();
                if (selectedShapes.length > 0) {
                    statusBar.innerText = `✅ ${selectedShapes.length} Objekte markiert.`;
                } else {
                    updateStatus();
                }
            } else if (isLineDrawing) { 
                isLineDrawing = false; 
                saveSnapshot(); 
                let newShape = { type: activeTool, x1: lineStart.x, y1: lineStart.y, x2: pos.x, y2: pos.y, color: drawColor };
                shapes.push(newShape); 
                selectedShapes = []; 
                redrawAll(); 
            }
        });

        // --- HILFSFUNKTION & TOUCH-STEUERUNG FÜR SMARTPHONES ---
        drawCanvas.addEventListener('touchstart', (e) => {
            if (e.touches.length === 0) return;
            const pos = getTouchPos(e);
            
            if (activeTool === 'multiselect') {
                const hit = getHitHandle(pos);
                if (hit) {
                    if (selectedShapes.includes(hit.shape)) {
                        selectedShapes = selectedShapes.filter(s => s !== hit.shape);
                    } else {
                        selectedShapes.push(hit.shape);
                    }
                    redrawAll();
                    statusBar.innerText = `☑️ ${selectedShapes.length} Objekt(e) markiert.`;
                }
                return;
            }

            if (activeTool === 'move') {
                const hit = getHitHandle(pos);
                if (hit) {
                    saveSnapshot();
                    isDragging = true;
                    dragTarget = hit;
                    dragTarget.lastX = pos.x;
                    dragTarget.lastY = pos.y;
                    if (!selectedShapes.includes(hit.shape)) {
                        selectedShapes = [hit.shape];
                    }
                    redrawAll();
                }
                return;
            }

            if (activeTool === 'line' || activeTool === 'dashed') {
                isLineDrawing = true;
                lineStart = pos;
            }
        }, { passive: true });

        drawCanvas.addEventListener('touchmove', (e) => {
            if (e.touches.length === 0) return;
            const pos = getTouchPos(e);

            if (isDragging && dragTarget) {
                const dx = pos.x - dragTarget.lastX;
                const dy = pos.y - dragTarget.lastY;

                if (selectedShapes.length > 1 && selectedShapes.includes(dragTarget.shape)) {
                    selectedShapes.forEach(s => {
                        if (s.type === 'dot' || s.type === 'text' || s.type === 'utensil') { 
                            s.x += dx; s.y += dy; 
                        } else if (s.type === 'line' || s.type === 'dashed') { 
                            s.x1 += dx; s.y1 += dy; s.x2 += dx; s.y2 += dy; 
                        } else if (s.type === 'curve') { 
                            s.x0 += dx; s.y0 += dy; s.cx += dx; s.cy += dy; s.x2 += dx; s.y2 += dy; 
                        }
                    });
                } else {
                    const s = dragTarget.shape; 
                    const h = dragTarget.handle;
                    
                    if (s.type === 'dot' || s.type === 'text' || s.type === 'utensil') { 
                        s.x = pos.x; s.y = pos.y; 
                    } else if (s.type === 'line' || s.type === 'dashed') { 
                        if (h === 'start') { s.x1 = pos.x; s.y1 = pos.y; } 
                        else if (h === 'end') { s.x2 = pos.x; s.y2 = pos.y; } 
                        else if (h === 'center') { s.x1 += dx; s.y1 += dy; s.x2 += dx; s.y2 += dy; }
                    } else if (s.type === 'curve') { 
                        if (h === 'start') { s.x0 = pos.x; s.y0 = pos.y; } 
                        else if (h === 'control') { s.cx = pos.x; s.cy = pos.y; } 
                        else if (h === 'end') { s.x2 = pos.x; s.y2 = pos.y; } 
                        else if (h === 'center') { s.x0 += dx; s.y0 += dy; s.cx += dx; s.cy += dy; s.x2 += dx; s.y2 += dy; }
                    }
                }
                dragTarget.lastX = pos.x;
                dragTarget.lastY = pos.y;
                redrawAll();
            } else if (isLineDrawing) {
                redrawAll();
                drawCtx.strokeStyle = "#ffffff";
                drawCtx.lineWidth = 4;
                drawCtx.setLineDash(activeTool === 'dashed' ? [8, 6] : []);
                drawCtx.beginPath();
                drawCtx.moveTo(lineStart.x, lineStart.y);
                drawCtx.lineTo(pos.x, pos.y);
                drawCtx.stroke();
                drawCtx.setLineDash([]);
                drawArrowHead(drawCtx, lineStart.x, lineStart.y, pos.x, pos.y, "#ffffff");
            }
        }, { passive: true });

        drawCanvas.addEventListener('touchend', (e) => {
            if (isDragging) {
                isDragging = false;
                dragTarget = null;
            } else if (isLineDrawing) {
                isLineDrawing = false;
                saveSnapshot();
                if (e.changedTouches.length > 0) {
                    const pos = getTouchPos(e);
                    let newShape = { type: activeTool, x1: lineStart.x, y1: lineStart.y, x2: pos.x, y2: pos.y, color: "#ffffff" };
                    shapes.push(newShape);
                    selectedShapes = [];
                }
                redrawAll();
            }
        }, { passive: true });

        drawPitch(); updateStatus();
    </script>
    </body>
    </html>
    """
    st.components.v1.html(html_code, height=580)

# --- INTELLIGENTER JSON-SLICER ---
def extract_json_array(text):
    import json
    text = text.strip()
    if "```" in text:
        text = re.sub(r"```[a-zA-Z]*\n?", "", text).replace("```", "").strip()
        
    # Plan A: Wenn die KI sauberes JSON liefert, direkt durchwinken
    try:
        json.loads(text)
        return text
    except Exception:
        pass
        
    # Plan B (Der Ausputzer): Ignoriert alle Fehler und fischt nur die echten JSON-Objekte raus
    objekte = []
    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(text):
        start = text.find('{', idx)
        if start == -1:
            break
        try:
            # raw_decode liest genau EIN valides Objekt und sagt uns, wo es endet
            obj, parsed_len = decoder.raw_decode(text[start:])
            objekte.append(json.dumps(obj))
            idx = start + parsed_len
        except Exception:
            idx = start + 1
            
    if objekte:
        return "[" + ", ".join(objekte) + "]"
        
    return text
# ==============================================================================
# 2. STABILE KI-ABFRAGE (MIT SICHERHEITS-CHECK & FEHLER-DETEKTOR)
# ==============================================================================
# ==============================================================================
# DYNAMISCHE KI-ABFRAGE (OFFLINE-SICHER)
# ==============================================================================
def get_gemini_json_text(prompt, api_key):
  key = api_key.strip()

  # 1. Schneller Offline-Check vor dem Netzwerkaufruf
  try:
    requests.get('https://1.1.1.1', timeout=1.5)
  except Exception:
    raise Exception("📡 Du bist aktuell offline. Der KI-Planer benötigt eine Internetverbindung. Du kannst aber alle gespeicherten Übungen und Pläne offline nutzen!")

  # 2. Direkt bei Google abfragen, welche Modelle für deinen Key JETZT exakt existieren
  list_url = f'https://generativelanguage.googleapis.com/v1beta/models?key={key}'
  try:
    res = requests.get(list_url, timeout=10)
    if res.status_code != 200:
      list_url = f'https://generativelanguage.googleapis.com/v1/models?key={key}'
      res = requests.get(list_url, timeout=10)

    if res.status_code != 200:
      raise Exception(f'API-Key abgelehnt (Status {res.status_code})')

    data = res.json()
    # Nur Modelle filtern, die für Textgenerierung freigeschaltet sind
    available_models = [
        m['name']
        for m in data.get('models', [])
        if 'generateContent' in m.get('supportedGenerationMethods', [])
    ]

    if not available_models:
      raise Exception(
          'Kein freigeschaltetes Gemini-Modell für diesen API-Key gefunden.'
      )
  except Exception as e:
    raise Exception(f'Modell-Liste konnte nicht geladen werden: {e}')

  # 2. Bevorzugte Reihenfolge festlegen (Schnelle Flash-Modelle zuerst)
  preferred_order = [
      'models/gemini-2.0-flash',
      'models/gemini-2.5-flash',
      'models/gemini-1.5-flash',
      'models/gemini-1.5-pro',
  ]
  sorted_models = sorted(
      available_models,
      key=lambda m: (
          preferred_order.index(m) if m in preferred_order else 99
      ),
  )

  api_version = 'v1beta' if 'v1beta' in list_url else 'v1'
  last_err = ''

  # 3. Schleife NUR durch die Modelle, die Google wirklich für dich gelistet hat
  for model_name in sorted_models:
    url = f'https://generativelanguage.googleapis.com/{api_version}/{model_name}:generateContent?key={key}'
    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'responseMimeType': 'application/json'},
    }

    try:
      response = requests.post(url, json=payload, timeout=25)

      if response.status_code == 200:
        res_data = response.json()
        if 'candidates' in res_data and res_data['candidates']:
          cand = res_data['candidates'][0]
          if cand.get('finishReason') == 'SAFETY':
            last_err = f'{model_name}: Wegen Sicherheitsfilter blockiert'
            continue
          parts = cand.get('content', {}).get('parts', [])
          if parts:
            return parts[0]['text']
      elif response.status_code == 429:
        last_err = f'{model_name}: Gratis-Limit erreicht (429)'
        continue
      else:
        last_err = f'{model_name}: HTTP {response.status_code}'
    except Exception as e:
      last_err = str(e)
      continue

  raise Exception(
      f'Kein verfügbares Modell konnte die Anfrage verarbeiten. Letzter Status:'
      f' {last_err}'
  )

# --- ECHTE GEMINI KI-GENERATOREN ---
def generiere_echte_ki_fragen(thema, api_key):
    if not HAS_GEMINI_LIB or not api_key: return None
    try:
        prompt = (f"Erstelle exakt 2 Multiple-Choice-Taktikfragen für U13-Fußballer zum Thema '{thema}'.\n"
                  "GIB AUSSCHLIESSLICH EIN SAUBERES JSON-ARRAY ZURÜCK!\n"
                  "Nutze KEINE Platzhalter. Generiere 2 echte, sofort spielbare Fragen.\n"
                  "Beispiel-Format:\n"
                  "[\n"
                  "  {\"question\": \"Was ist die wichtigste Regel beim Gegenpressing?\", \"options\": [\"A) Sofort nachsetzen\", \"B) Zurückziehen\", \"C) Abwarten\"], \"correct\": \"A) Sofort nachsetzen\", \"points\": 10}\n"
                  "]")
        raw_text = get_gemini_json_text(prompt, api_key)
        
        # Abfangen: Wenn die KI absolut nichts antwortet
        if not raw_text or not raw_text.strip():
            raise ValueError("Die KI hat eine leere Antwort zurückgegeben.")
            
        extracted_text = extract_json_array(raw_text)
        if not extracted_text or not extracted_text.strip():
            raise ValueError("Es konnte kein JSON-Format in der Antwort gefunden werden.")
            
        parsed = json.loads(extracted_text)
        
        # Defensive Rückgabe, falls Gemini ein umschließendes Objekt gebaut hat
        if isinstance(parsed, dict):
            for k in ["items", "fragen", "questions"]:
                if k in parsed: 
                    parsed = parsed[k]
                    break
            else:
                parsed = [parsed]
        
        if not isinstance(parsed, list):
            parsed = [parsed]
            
        # Platzhalter rausfiltern und knallhart auf exakt 2 Fragen limitieren
        echte_fragen = [q for q in parsed if isinstance(q, dict) and q.get("question") and "..." not in q.get("question", "")]
        return echte_fragen[:2]
    except Exception as e: 
        st.error(f"KI-Fehler (Quiz): Bitte drücke den Button noch einmal. (Details: {e})")
        return None

def generiere_echte_ki_challenges(thema, api_key):
    if not HAS_GEMINI_LIB or not api_key: return None
    try:
        prompt = (f"Erstelle exakt 2 Wochen-Challenges für U13-Fußballer zum Thema '{thema}'.\n"
                  "GIB AUSSCHLIESSLICH EIN SAUBERES JSON-ARRAY ZURÜCK!\n"
                  "Nutze KEINE Platzhalter. Generiere 2 echte, sofort spielbare Challenges.\n"
                  "Beispiel-Format:\n"
                  "[\n"
                  "  {\"title\": \"100x Jonglieren ohne Bodenkontakt\", \"points\": 25}\n"
                  "]")
        raw_text = get_gemini_json_text(prompt, api_key)
        
        if not raw_text or not raw_text.strip():
            raise ValueError("Die KI hat eine leere Antwort zurückgegeben.")
            
        extracted_text = extract_json_array(raw_text)
        if not extracted_text or not extracted_text.strip():
            raise ValueError("Es konnte kein JSON-Format in der Antwort gefunden werden.")
            
        parsed = json.loads(extracted_text)
        
        if isinstance(parsed, dict):
            for k in ["items", "challenges"]:
                if k in parsed: 
                    parsed = parsed[k]
                    break
            else:
                parsed = [parsed]
                
        if not isinstance(parsed, list):
            parsed = [parsed]
            
        # Platzhalter rausfiltern und knallhart auf exakt 2 Challenges limitieren
        echte_challenges = [c for c in parsed if isinstance(c, dict) and c.get("title") and "..." not in c.get("title", "")]
        return echte_challenges[:2]
    except Exception as e: 
        st.error(f"KI-Fehler (Challenge): Bitte drücke den Button noch einmal. (Details: {e})")
        return None

# ==============================================================================
# 3. GENERATOR FÜR TRAININGSPLAN (MIT DIAGNOSE & ANTI-KOPIER-SPERRE)
# ==============================================================================
def erstelle_ki_planer_prompt(anzahl_spieler, gewaehlte_phasen_bool, db_exercises, anzahl_tw="Egal"):
    """Baut den KI-Prompt inklusive Spieler- und Torhüter-Vorgaben auf."""
    if db_exercises:
        # Wir nehmen bis zu 15 Übungen als Inspiration, da die bloße Existenz in der DB das "Gütesiegel" ist
        ex_summary = [f"- [{e.get('name', 'Übung')}] (Phase: {e.get('phase', '-')}, Schwerpunkt: {e.get('schwerpunkt', '-')})" for e in db_exercises[-15:]]
        db_kontext = "\n".join(ex_summary)
    else:
        db_kontext = "Noch keine Übungen in der Datenbank vorhanden."

    if isinstance(gewaehlte_phasen_bool, bool):
        gewaehlte_phasen_bool = [True, True, True, True, gewaehlte_phasen_bool]

    anzufordernde_phasen = []
    for idx, (titel, aktiv) in enumerate(zip(PHASEN_NAMEN, gewaehlte_phasen_bool), 1):
        if aktiv:
            anzufordernde_phasen.append(f'- Phase {idx}: "{titel}"')
    
    phasen_text = "\n".join(anzufordernde_phasen)

    return f"""
Erstelle hochqualitative, altersgerechte Fußball-Übungen für eine U13-Mannschaft (Goldenes Lernalter).
RAHMENBEDINGUNGEN FÜR JEDE ÜBUNG:
- Feldgröße: EXAKT EIN VIERTELFELD (ca. 35x50 Meter). Gebe bei den Übungen konkrete Meter-Maße an, die optimal in dieses Feld passen!
- Spieleranzahl: {anzahl_spieler} Feldspieler. Alle Spieler müssen durchgängig aktiv sein (Vermeidung von langen Warteschlangen).
- Verfügbare Torhüter (TW): {anzahl_tw}. (Passe die Tore/Zielformen strikt an die Anzahl der Torhüter an! Bei 0 TW nutze Minitore/Dribbellinien, bei 1 TW z. B. 1 Jugendtor + Minitore als Konterziele, bei 2 TW 2 Jugendtore).
- Verfügbares Material: Maximal 2 Jugendtore, 4 Minitore, Hütchen und Stangen. Plane absolut nichts, was dieses Material übersteigt.

### DEINE INSPIRATIONSQUELLE (DIE TRAINER-DATENBANK):
{db_kontext}

### REGELN FÜR DIE ÜBUNGS-GENERIERUNG:
- Lass dich stark von den oben gelisteten Übungen aus der Datenbank inspirieren (Stil, Organisationsformen, Schwerpunkte).
- Bringe aber gleichzeitig frische, neue Ideen und clevere Abwandlungen ein, damit das Training für die U13 spannend bleibt!
- Kombiniere die bewährte Trainer-DNA mit neuen Impulsen. Erschaffe kreative Übungen, die so in der Datenbank noch nicht existieren.

ERSTELLE NEUE ÜBUNGEN AUSSCHLIESSLICH FÜR FOLGENDE PHASEN:
{phasen_text}

AUSGABE FORMAT (GIB AUSSCHLIESSLICH EIN VALIDES JSON ARRAY FÜR DIE ANGEFORDERTEN PHASEN ZURÜCK!):
[
  {{
    "phase_num": 1,
    "phase_title": "Phase 1: Aufwärmen",
    "exercise_name": "Name der Übung",
    "spieler_bereich": "{anzahl_spieler - 2}-{anzahl_spieler + 2} Spieler",
    "tw_info": "{anzahl_tw}",
    "setup_text": "Aufbau...",
    "flow_text": "Ablauf...",
    "coaching_points": "Tipps..."
  }}
]
"""

def generiere_ki_einheit_5_phasen(anzahl_spieler, gewaehlte_phasen_bool, api_key, db_exercises=None, alter_plan=None, anzahl_tw="Egal"):
    if isinstance(gewaehlte_phasen_bool, bool):
        gewaehlte_phasen_bool = [True, True, True, True, gewaehlte_phasen_bool]

    if not any(gewaehlte_phasen_bool):
        st.warning("Bitte wähle mindestens eine Phase zum Generieren aus!")
        return alter_plan or []

    prompt = erstelle_ki_planer_prompt(anzahl_spieler, gewaehlte_phasen_bool, db_exercises or [], anzahl_tw)
    raw_text = ""
    try:
        raw_text = get_gemini_json_text(prompt, api_key)
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z]*\n", "", cleaned)
            cleaned = re.sub(r"\n```$", "", cleaned)
            
        neue_uebungen = json.loads(cleaned)
        neue_map = {u.get("phase_num"): u for u in neue_uebungen if "phase_num" in u}
        
        finaler_plan = []
        for idx in range(1, 6):
            ist_aktiv = gewaehlte_phasen_bool[idx - 1]
            
            if ist_aktiv:
                match = neue_map.get(idx)
                if not match and neue_uebungen:
                    match = neue_uebungen.pop(0)
                    match["phase_num"] = idx
                    match["phase_title"] = PHASEN_NAMEN[idx - 1]
                
                if match:
                    finaler_plan.append(match)
                else:
                    finaler_plan.append({
                        "phase_num": idx, "phase_title": PHASEN_NAMEN[idx - 1],
                        "exercise_name": "Fehler bei Generierung", "setup_text": "-", "flow_text": "-", "coaching_points": "-"
                    })
            else:
                if alter_plan and len(alter_plan) >= idx and alter_plan[idx - 1]:
                    finaler_plan.append(alter_plan[idx - 1])
                else:
                    finaler_plan.append({
                        "phase_num": idx, "phase_title": PHASEN_NAMEN[idx - 1],
                        "exercise_name": "Nicht generiert (Abgewählt)", "setup_text": "-", "flow_text": "-", "coaching_points": "-"
                    })
                    
        return finaler_plan

    except json.decoder.JSONDecodeError:
        st.error("JSON-Lesefehler! Die KI hat keinen sauberen Code geliefert.")
        st.info(f"Die Roh-Antwort der KI war:\n{raw_text}")
        return alter_plan
    except Exception as e:
        st.error(f"Fehler bei KI-Generierung: {e}")
        return alter_plan

# ==============================================================================
# 2. SKIZZEN-GENERATOR FÜR EINE EINZELNE ÜBUNG (AUF KNOPFDRUCK)
# ==============================================================================
def generiere_ki_skizze(uebungs_text, api_key):
    prompt = f"""
    Erstelle EINE hochdetaillierte Taktik-Skizze für folgende Fußball-Übung auf einem Viertelfeld.
    ÜBUNG: {uebungs_text}

    REGELN FÜR DEN SVG-CODE (STRIKT EINHALTEN!):
    - Valider HTML SVG-Code, viewBox='0 0 500 350'.
    - Rasen (fill='#2e7d32'), Meter-Angaben, Spieler (gelb/rot), Hütchen (orange), Pfeile.
    - GIB AUSSCHLIESSLICH EIN GÜLTIGES JSON-OBJEKT ZURÜCK!
    - Nutze im SVG-Code AUSSCHLIESSLICH einfache Anführungszeichen (').

    Format-Vorlage:
    {{
      "svg_code": "<svg viewBox='0 0 500 350'>...dein code...</svg>"
    }}
    """
    raw_text = ""
    try:
        raw_text = get_gemini_json_text(prompt, api_key)
        
        if raw_text: 
            raw_text = raw_text.replace("\\", "")
            
        # Plan A: Versuchen, das JSON sauber zu laden
        try:
            data = json.loads(extract_json_array(raw_text))
            svg = ""
            if isinstance(data, list) and len(data) > 0:
                svg = data[0].get("svg_code", "")
            elif isinstance(data, dict):
                svg = data.get("svg_code", "")
        except Exception:
            svg = ""
            
        # Plan B (Der Libero): Wenn JSON kaputt ist, holen wir uns das SVG direkt aus dem Text
        if not svg or "<svg" not in svg:
            match = re.search(r"(<svg.*?</svg>)", raw_text, re.IGNORECASE | re.DOTALL)
            if match:
                svg = match.group(1)
                
        if not svg:
            raise ValueError("Kein <svg> Tag im generierten Code gefunden.")
            
        return svg
    except Exception as e:
        st.error(f"Fehler bei Skizzen-Generierung: {e}")
        with st.expander("🔍 Fehleranalyse: Was hat die KI geantwortet?"):
            st.code(raw_text)
        return None

# --- FUNKTION: BESTEHENDE ÜBUNG MIT KI ANPASSEN ---
def render_ki_anpassen_bereich(gemini_key):
    st.divider()
    st.markdown("### 🪄 Bestehende Übung mit KI anpassen")
    st.caption("Wähle eine Übung aus deiner Sammlung und sage der KI, was geändert werden soll.")

    db_exercises = st.session_state.data.get("exercises", [])
    if not db_exercises:
        return

    options_map = {f"[{e.get('phase', 'Phase')}] {e.get('name', 'Übung')}": e for e in db_exercises}
    selected_label = st.selectbox("Übung zum Bearbeiten auswählen:", list(options_map.keys()))
    selected_ex = options_map[selected_label]

    aenderungswunsch = st.text_input("Was möchtest du an dieser Übung ändern?", placeholder="z. B. 'Passe die Übung für 11 Spieler an'")

    if st.button("🪄 Übung jetzt von KI umbauen lassen", type="primary"):
        if not aenderungswunsch:
            st.warning("Bitte gib zuerst einen Änderungswunsch ein!")
        elif not gemini_key:
            st.error("Kein Gemini API Key vorhanden!")
        else:
            with st.spinner("KI baut deine Übung um..."):
                modify_prompt = f"""
Du bist ein Fußballexperte. Passe die folgende Übung nach dem Wunsch des Trainers an.
URSPRÜNGLICHE ÜBUNG:
- Name: {selected_ex.get('name')}
- Phase: {selected_ex.get('phase')}
- Aufbau/Ablauf: {selected_ex.get('aufbau')}

WUNSCH DES TRAINERS:
"{aenderungswunsch}"

Gib ausschließlich das Ergebnis im folgenden JSON-Format zurück:
{{
  "name": "Neuer/Angepasster Name",
  "phase": "{selected_ex.get('phase')}",
  "schwerpunkt": "{selected_ex.get('schwerpunkt')}",
  "spieler": "Spieleranzahl",
  "aufbau": "Neuer Aufbau, Ablauf und Coaching-Punkte..."
}}
"""
                try:
                    res_raw = get_gemini_json_text(modify_prompt, gemini_key)
                    cleaned = res_raw.strip().replace("```json", "").replace("```", "")
                    res_json = json.loads(cleaned)
                    
                    neue_id = max([x.get("id", 0) for x in st.session_state.data["exercises"]] + [0]) + 1
                    res_json["id"] = neue_id
                    res_json["grafik"] = selected_ex.get("grafik", "")
                    
                    st.session_state.data["exercises"].append(res_json)
                    speichere_daten(st.session_state.data)
                    st.success("🎉 Angepasste Übung als neue Variante in der Sammlung gespeichert!")
                    st.rerun()
                except Exception as err:
                    st.error(f"Fehler bei der KI-Anpassung: {err}")

# --- DATEN-MANAGEMENT ---
def generiere_leere_daten():
    return {
        "players": [], 
        "exercises": [], 
        "challenge_pool": [],
        "active_challenge_id": None,
        "quiz_pool": [],
        "active_quiz_ids": [],
        "principles": [],
        "standards": []
    }
@st.cache_data(show_spinner=False)
def lade_daten():
    data = None
    local_data = None
    
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT data FROM store WHERE id="main"')
        row = c.fetchone()
        conn.close()
        if row:
            local_data = json.loads(row[0])
    except Exception:
        local_data = None

    if data is None or not isinstance(data, dict):
        if local_data:
            data = local_data
        else:
            data = generiere_leere_daten()

    if local_data and isinstance(local_data, dict):
        local_p = local_data.get("principles", [])
        cloud_p = data.get("principles", [])
        if len(local_p) > len(cloud_p):
            data["principles"] = local_p

    if "players" not in data: data["players"] = []
    if "exercises" not in data: data["exercises"] = []
    if "principles" not in data: data["principles"] = []
    if "standards" not in data: data["standards"] = []

    for pr in data.get("principles", []):
        if "positions" not in pr or not isinstance(pr["positions"], list):
            pr["positions"] = ["Alle"]

    if "challenge_pool" not in data or not data["challenge_pool"]: data["challenge_pool"] = []
    if "active_challenge_ids" not in data: 
        alt_id = data.get("active_challenge_id")
        data["active_challenge_ids"] = [alt_id] if alt_id is not None else []
        
    if "quiz_pool" not in data or not data["quiz_pool"]: data["quiz_pool"] = []
    if "active_quiz_ids" not in data: 
        data["active_quiz_ids"] = [q["id"] for q in data["quiz_pool"][:2]] if data["quiz_pool"] else []

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

# --- CLOUD BACKGROUND WORKER ---
def _cloud_sync_worker(payload_str, url):
    try:
        requests.post(url, data=payload_str, headers={"Content-Type": "text/plain"}, timeout=15)
    except Exception as e:
        print(f"Hintergrund-Speicherfehler Cloud: {e}")

# --- PFEILSCHNELLE SPEICHERFUNKTION ---
def speichere_daten(data):
    lade_daten.clear() # Leert den Cache, damit beim nächsten Reload die frischen Daten geladen werden!
    st.session_state.data = data
    payload_str = json.dumps(data, ensure_ascii=False)
    
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('REPLACE INTO store (id, data) VALUES ("main", ?)', (payload_str,))
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"❌ lokaler Speicherfehler (SQLite): {e}")

    if API_URL:
        threading.Thread(target=_cloud_sync_worker, args=(payload_str, API_URL), daemon=True).start()
        
    return True

# --- INITIALISIERUNG DER SPEICHERRÄUME ---
if "data" not in st.session_state: st.session_state.data = lade_daten()
if "zuweisungen" not in st.session_state: st.session_state.zuweisungen = {}

nur_spieler = [p for p in st.session_state.data["players"] if p.get("role", "Spieler") == "Spieler"]

qp_trainer = st.query_params.get("trainer") == "1"
qp_player = st.query_params.get("player")
qp_pin = st.query_params.get("pin")

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
        with st.expander("⚙️ Erweitere API-Einstellungen", expanded=False):
            gemini_key_input = st.text_input(
                "🔑 Gemini API Key (Manuelle Eingabe):", 
                value=gemini_key if gemini_key else "", 
                type="password", 
                key="gemini_key_input"
            )
            if gemini_key_input:
                gemini_key = gemini_key_input.strip()
                
            # --- Live Status-Ampel für den API-Key ---
            if gemini_key:
                try:
                    # Blitzschneller Check bei Google
                    test_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={gemini_key}"
                    test_res = requests.get(test_url, timeout=2)
                    
                    if test_res.status_code == 200:
                        st.success("🟢 API-Key gültig & verbunden!")
                    elif test_res.status_code == 400:
                        st.error("🔴 Ungültiges Format (Leerzeichen?)")
                    elif test_res.status_code == 401:
                        st.error("🔴 Key abgelehnt (Nicht autorisiert)")
                    else:
                        st.warning(f"🟡 Fehler (Code: {test_res.status_code})")
                except requests.exceptions.RequestException:
                    st.warning("⚪ Keine Internetverbindung")
            else:
                st.info("⚪ Kein Key hinterlegt")
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
available_tabs = ["📊 Übersicht", "📜 Team-DNA", "📐 Standards", "🔍 Spieler-Profile", "📖 Spielübersicht", "🎮 Challenge & Quiz"]

if logged_in_player or is_trainer: available_tabs += ["🎥 Videoanalyse"]
if is_trainer: available_tabs += ["🏃‍♂️ Kader", "⚽ Spiel loggen", "🤖 KI Twin-Teams", "📥 Import (SpielerPlus)", "📋 Trainingsplaner"]
available_tabs += ["🏆 Liga-Tabelle"]

tab_slugs = {
    "📊 Übersicht": "uebersicht", "📜 Team-DNA": "dna", "📐 Standards": "standards", "🔍 Spieler-Profile": "profile", 
    "📖 Spielübersicht": "spieluebersicht", "🎮 Challenge & Quiz": "challenge", "🎥 Videoanalyse": "video", 
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
            st.plotly_chart(fig_bet, use_container_width=True, config={'displayModeBar': False, 'include_mathjax': False})
            
        with c_col2:
            fig_tore = px.bar(df_tore_top5, x="Name", y="⚽ Tore", text="⚽ Tore", color_discrete_sequence=[fca_yellow])
            fig_tore.update_traces(textposition="outside")
            fig_tore.update_layout(xaxis_title=None, yaxis_title=None, margin=dict(l=10, r=10, t=10, b=10), height=280, plot_bgcolor="rgba(0,0,0,0)")
            fig_tore.update_yaxes(showgrid=True, gridcolor="rgba(200,200,200,0.15)", range=[0, max(df_tore_top5["⚽ Tore"].max() + 1 if not df_tore_top5.empty else 5, 5)])
            st.markdown("<p style='text-align:center;'><b>⚽ Top Torschützen (Top 5)</b></p>", unsafe_allow_html=True)
            st.plotly_chart(fig_tore, use_container_width=True, config={'displayModeBar': False, 'include_mathjax': False})
            
        with c_col3:
            if not df_scorer_top5.empty:
                fig_pie = px.pie(df_scorer_top5, values="🌟 Scorer", names="Name", hole=0.4, color_discrete_sequence=fca_colors)
                fig_pie.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=280, legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
                st.markdown("<p style='text-align:center;'><b>🌟 Scorer-Verteilung (Top 5)</b></p>", unsafe_allow_html=True)
                st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False, 'include_mathjax': False})
            else: 
                st.markdown("<p style='text-align:center;'><b>🌟 Scorer-Verteilung</b></p>", unsafe_allow_html=True)
                st.info("Noch keine Scorer registriert.")
    else: st.info("Keine Spieler im Kader.")

# --- 📜 TAB 1.5: TEAM-DNA ---
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
                    st.caption(f"📍 Positionen: **{pos_str}**")
            st.write(p["desc"])

    dna_tab1, dna_tab2, dna_tab3 = st.tabs([
        "⚽ Auf dem Platz (Taktik)", 
        "🧠 Neben dem Platz (Einstellung)", 
        "📍 Positionsspezifische Aufgaben"
    ])
    
    with dna_tab1:
        kat_platz = [p for p in prinzipien if p.get("category") == "⚽ Auf dem Platz (Taktik)" or ("Auf dem Platz" in p.get("category", "") and "Neben" not in p.get("category", ""))]
        if not kat_platz: st.info("Noch keine taktischen Prinzipien hinterlegt.")
        for p in kat_platz: render_prinzip_card(p)

    with dna_tab2:
        kat_geist = [p for p in prinzipien if p.get("category") == "🧠 Neben dem Platz (Einstellung)" or "Neben dem Platz" in p.get("category", "") or "Einstellung" in p.get("category", "")]
        if not kat_geist: st.info("Noch keine Einstellungs-Prinzipien hinterlegt.")
        for p in kat_geist: render_prinzip_card(p)

    with dna_tab3:
        kat_pos = [p for p in prinzipien if p.get("category") == "📍 Positionsspezifisch" or "Position" in p.get("category", "")]
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

    if is_trainer:
        st.divider()
        st.markdown("### 🛠️ Trainer-Verwaltung: Team-DNA bearbeiten")
        
        tr_p1, tr_p2, tr_p3, tr_p4, tr_p5 = st.tabs([
            "➕ Neues Prinzip hinzufügen", 
            "✏️ Prinzip bearbeiten", 
            "🔃 Reihenfolge ändern",
            "🗑️ Prinzip löschen",
            "💾 Backup & Wiederherstellung"
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
                        neues_objekt = {
                            "id": neue_id,
                            "title": p_title.strip(),
                            "category": p_cat,
                            "positions": p_pos if p_pos else ["Alle"],
                            "desc": p_desc.strip()
                        }
                        
                        prinzipien_pool = st.session_state.data.get("principles", [])
                        prinzipien_pool.append(neues_objekt)
                        st.session_state.data["principles"] = prinzipien_pool
                        
                        speichere_daten(st.session_state.data)
                        st.toast("🎉 Prinzip erfolgreich gespeichert!", icon="💾")
                        st.rerun()

        with tr_p2:
            prinzipien_pool = st.session_state.data.get("principles", [])
            if not prinzipien_pool:
                st.info("Keine Prinzipien zum Bearbeiten vorhanden.")
            else:
                p_options = {f"[{p['id']}] {p['title']} ({p.get('category', '-')})": p["id"] for p in prinzipien_pool}
                sel_p_label = st.selectbox("Wähle ein Prinzip zum Bearbeiten aus:", list(p_options.keys()))
                sel_p_id = p_options[sel_p_label]
                edit_p = next((x for x in prinzipien_pool if x["id"] == sel_p_id), None)
                
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
                            speichere_daten(st.session_state.data)
                            st.toast("🎉 Prinzip aktualisiert!", icon="✏️")
                            st.rerun()

        with tr_p3:
            st.markdown("##### 🔃 Reihenfolge der Prinzipien verschieben")
            prinzipien_pool = st.session_state.data.get("principles", [])
            if not prinzipien_pool:
                st.info("Keine Prinzipien vorhanden.")
            else:
                for idx, p in enumerate(prinzipien_pool):
                    with st.container(border=True):
                        c_num, c_title, c_up, c_down = st.columns([1, 6, 1, 1])
                        c_num.markdown(f"**#{idx + 1}**")
                        pos_info = ", ".join(p.get("positions", ["Alle"]))
                        c_title.markdown(f"**{p['title']}** (`{p.get('category', '-')}` | `{pos_info}`)")
                        
                        if idx > 0:
                            if c_up.button("⬆️", key=f"p_up_{p['id']}_{idx}"):
                                prinzipien_pool[idx], prinzipien_pool[idx - 1] = prinzipien_pool[idx - 1], prinzipien_pool[idx]
                                st.session_state.data["principles"] = prinzipien_pool
                                speichere_daten(st.session_state.data)
                                st.rerun()
                        
                        if idx < len(prinzipien_pool) - 1:
                            if c_down.button("⬇️", key=f"p_down_{p['id']}_{idx}"):
                                prinzipien_pool[idx], prinzipien_pool[idx + 1] = prinzipien_pool[idx + 1], prinzipien_pool[idx]
                                st.session_state.data["principles"] = prinzipien_pool
                                speichere_daten(st.session_state.data)
                                st.rerun()

        with tr_p4:
            prinzipien_pool = st.session_state.data.get("principles", [])
            st.markdown("##### 🗑️ Einzelne oder ALLE Prinzipien löschen:")
            if st.button("💥 Alle aktuellen Prinzipien auf einmal löschen (Leerer Neustart)", type="secondary"):
                st.session_state.data["principles"] = []
                speichere_daten(st.session_state.data)
                st.toast("🔥 Alle Prinzipien gelöscht!")
                st.rerun()

            st.write("---")
            for p in prinzipien_pool:
                col_d1, col_d2 = st.columns([4, 1])
                pos_info = ", ".join(p.get("positions", ["Alle"]))
                col_d1.write(f"**[{p['id']}] {p['title']}** (`{p.get('category','-')}` | `{pos_info}`)")
                if col_d2.button("🗑️ Löschen", key=f"del_p_{p['id']}"):
                    st.session_state.data["principles"] = [x for x in prinzipien_pool if x["id"] != p["id"]]
                    speichere_daten(st.session_state.data)
                    st.toast("🗑️ Prinzip gelöscht!")
                    st.rerun()

        with tr_p5:
            st.markdown("##### 💾 Datenbank-Sicherung (JSON Export & Import)")
            json_str = json.dumps(st.session_state.data, indent=4, ensure_ascii=False)
            st.download_button(
                label="📥 Aktuellen Datenstand herunterladen (.json)",
                data=json_str,
                file_name=f"alsterbrueder_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                mime="application/json",
                type="primary"
            )
            st.write("")
            uploaded_backup = st.file_uploader("📤 Backup-Datei hochladen (.json Wiederherstellung)", type=["json"])
            if uploaded_backup is not None:
                if st.button("🔥 Backup jetzt einspielen & überschreiben"):
                    try:
                        restored_data = json.load(uploaded_backup)
                        st.session_state.data = restored_data
                        speichere_daten(restored_data)
                        st.success("🎉 Backup erfolgreich eingespielt!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler beim Laden des Backups: {e}")

# --- 📐 TAB 1.8: STANDARDS & TAKTIKBOARD ---
if selected_tab == "📐 Standards":
    st.subheader("📐 Standard-Varianten & Taktikboard")
    st.caption("Unsere einstudierten Ecken, Freistöße und Einwürfe auf einen Blick!")
    
    standards_list = st.session_state.data.get("standards", [])
    filter_type = st.selectbox("Nach Typ filtern:", ["Alle Typen", "Ecke Links", "Ecke Rechts", "Freistoß", "Einwurf"])
    gefilderte_st = standards_list if filter_type == "Alle Typen" else [s for s in standards_list if s.get("type") == filter_type]
    
    if not gefilderte_st:
        st.info("Noch keine Standard-Varianten hinterlegt.")
    else:
        for s in gefilderte_st:
            with st.container(border=True):
                col_info, col_img = st.columns([1, 1])
                with col_info:
                    st.markdown(f"### {s['title']}")
                    st.caption(f"📌 Typ: **{s.get('type', '-')}** | 🗣️ Rufsignal: **{s.get('signal', 'Keins')}**")
                    st.markdown(f"**🛠️ Ablauf & Aufgaben:**\n{s.get('desc', '-')}")
                with col_img:
                    if s.get("image"):
                        st.image(f"data:image/png;base64,{s['image']}", caption="Taktik-Skizze", use_container_width=True)
                    else:
                        st.info("Keine Taktik-Skizze hinterlegt.")

    if is_trainer:
        st.divider()
        st.markdown("### 🛠️ Trainer-Verwaltung: Standards zeichnen & verwalten")
        st_tr1, st_tr2 = st.tabs(["✏️ Neue Variante zeichnen", "🗑️ Variante löschen"])
        
        with st_tr1:
            st.markdown("##### 📐 Neue Standard-Variante anlegen")
            s_title = st.text_input("Name der Variante (z.B. 'Ecke Kurz - Alpha'):", key="std_title")
            c_s1, c_s2 = st.columns(2)
            s_type = c_s1.selectbox("Typ:", ["Ecke Links", "Ecke Rechts", "Freistoß", "Einwurf"], key="std_type")
            s_signal = c_s2.text_input("Signal / Rufwort (z.B. 'Rechte Hand hoch'):", key="std_signal")
            s_desc = st.text_area("Laufwege & Aufgaben (Wer läuft wohin?):", key="std_desc")
            
            st.markdown("---")
            st.markdown("##### 🎨 Taktik-Spielfeld & Zeichenbrett")
            
            render_html5_taktikboard()

            st.write("")
            st.info("💡 **Tipp:** Wenn du fertig gezeichnet hast, klicke oben im Board auf '📸 Skizze als Bild speichern' und lade das Bild hier hoch:")
            uploaded_sketch = st.file_uploader("📸 Heruntergeladene Taktikskizze hier hochladen:", type=["png", "jpg", "jpeg"], key="std_sketch_upload")

            if st.button("💾 Standard-Variante dauerhaft speichern", type="primary"):
                if not s_title.strip():
                    st.error("Bitte gib der Variante einen Namen!")
                else:
                    img_b64_to_save = ""
                    if uploaded_sketch is not None:
                        img_bytes = uploaded_sketch.read()
                        img_b64_to_save = base64.b64encode(img_bytes).decode("utf-8")
                        
                    neue_id = max([s["id"] for s in standards_list] + [0]) + 1
                    neues_std = {
                        "id": neue_id,
                        "title": s_title.strip(),
                        "type": s_type,
                        "signal": s_signal.strip(),
                        "desc": s_desc.strip(),
                        "image": img_b64_to_save
                    }
                    
                    standards_pool = st.session_state.data.get("standards", [])
                    standards_pool.append(neues_std)
                    st.session_state.data["standards"] = standards_pool
                    
                    speichere_daten(st.session_state.data)
                    st.toast("🎉 Standard-Variante gesichert!", icon="📐")
                    st.rerun()

        with st_tr2:
            st.markdown("##### 🗑️ Bestehende Standard-Varianten löschen:")
            if not standards_list:
                st.info("Keine Varianten vorhanden.")
            else:
                for s in standards_list:
                    col_sa, col_sb = st.columns([4, 1])
                    col_sa.write(f"**[{s['id']}] {s['title']}** (`{s.get('type', '-')}` | Signal: `{s.get('signal', '-')}`)")
                    if col_sb.button("🗑️ Löschen", key=f"del_std_{s['id']}"):
                        st.session_state.data["standards"] = [x for x in standards_list if x["id"] != s["id"]]
                        speichere_daten(st.session_state.data)
                        st.toast("🗑️ Variante gelöscht!")
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
        
        # --- DYNAMISCHE FUT-STATS BERECHNUNG (GAMIFICATION) ---
        # 1. Basiswerte holen
        base_pac = int(p.get("base_pac", 75))
        base_sho = int(p.get("base_sho", 60))
        base_pas = int(p.get("base_pas", 65))
        base_dri = int(p.get("base_dri", 70))
        base_def = int(p.get("base_def", 55))
        base_phy = int(p.get("base_phy", 65))

        # 2. Reale Leistungs-Boni berechnen
        bonus_sho = stats["⚽ Tore"] * 2  # +2 pro Tor
        bonus_pas = stats["🅰️ Vorlagen"] * 2  # +2 pro Vorlage
        
        # Trainingsbeteiligung: Über 60% gibt Pluspunkte, darunter Abzug
        bonus_phy = int((stats["Beteiligung"] - 60) / 3) 
        
        # Fleiß bei Challenges macht schneller/fitter
        bonus_pac = len(p.get("completed_challenges", [])) * 2 
        
        # Taktik-Quizze fördern Spielintelligenz & Technik
        bonus_dri = len(p.get("solved_quizzes", [])) * 2 
        
        # Spielpraxis härtet defensiv ab
        bonus_def = stats["🏃‍♂️ Spiele"] * 1 
        
        # 3. Finale Werte berechnen (Gedeckelt zwischen 1 und 99)
        pac = min(max(base_pac + bonus_pac, 1), 99)
        sho = min(max(base_sho + bonus_sho, 1), 99)
        pas = min(max(base_pas + bonus_pas, 1), 99)
        dri = min(max(base_dri + bonus_dri, 1), 99)
        df_val = min(max(base_def + bonus_def, 1), 99)
        phy = min(max(base_phy + bonus_phy, 1), 99)
        
        # 4. Gesamt-Rating (OVR) berechnen
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
    
    with c_sub1:
        challenge_katalog = st.session_state.data.get("challenge_pool", [])
        
        # Daten-Migration zur Laufzeit abfangen
        if "active_challenge_ids" not in st.session_state.data:
            alt_id = st.session_state.data.get("active_challenge_id")
            active_ch_ids = [alt_id] if alt_id is not None else []
        else:
            active_ch_ids = st.session_state.data.get("active_challenge_ids", [])
            
        aktive_challenges = [c for c in challenge_katalog if c["id"] in active_ch_ids]
        
        if aktive_challenges:
            st.markdown("### 🎯 Aktuelle Wochen-Aufgaben")
            for c in aktive_challenges:
                st.info(f"**{c['title']}**\n\nBelohnung: `+{c.get('points', 25)} EP`")
        else:
            st.info("Aktuell ist keine Challenge aktiv. Pause für diese Woche!")

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
                st.markdown("##### 🗓️ Aktive Wochen-Challenges festlegen")
                if not challenge_katalog: st.warning("Katalog ist leer.")
                else:
                    options_dict = {}
                    for c in challenge_katalog:
                        status = f"⚠️ Bereits {c.get('used_count', 0)}x genutzt" if c.get("used_count", 0) > 0 else "🟢 Neu"
                        label = f"[{c['id']}] {c['title']} ({c.get('points', 25)} EP) | {status}"
                        options_dict[label] = c["id"]
                    
                    default_selected = [k for k, v in options_dict.items() if v in active_ch_ids]
                    gewaehlte_ch_labels = st.multiselect(
                        "Wähle aktive Challenges aus deinem Katalog (leer lassen für keine):", 
                        options=list(options_dict.keys()),
                        default=default_selected
                    )
                    
                    if st.button("💾 Ausgewählte Challenges für die Woche freischalten", type="primary"):
                        neue_aktive_ids = [options_dict[lbl] for lbl in gewaehlte_ch_labels]
                        st.session_state.data["active_challenge_ids"] = neue_aktive_ids
                        
                        for n_id in neue_aktive_ids:
                            c_obj = next((x for x in challenge_katalog if x["id"] == n_id), None)
                            if c_obj and n_id not in active_ch_ids: # Zähler nur erhöhen wenn frisch aktiviert
                                c_obj["used_count"] = c_obj.get("used_count", 0) + 1
                                
                        speichere_daten(st.session_state.data)
                        st.success(f"Erfolgreich {len(neue_aktive_ids)} Challenges für die Woche aktiviert!")
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
                        # Defensive Aufstellung: Falls die KI einen anderen Key-Namen erfindet
                        c_title = ki_c.get('title', ki_c.get('aufgabe', ki_c.get('name', 'Taktik-Challenge')))
                        c_points = int(ki_c.get('points', ki_c.get('punkte', 25)))
                        
                        st.info(f"**Aufgabe:** {c_title}\n\n• **Belohnung:** `{c_points} EP`")
                        if st.button(f"➕ Challenge #{idx+1} dauerhaft in den Katalog übernehmen", key=f"add_gem_c_{idx}"):
                            neue_id = max([c["id"] for c in challenge_katalog] + [0]) + 1
                            challenge_katalog.append({"id": neue_id, "title": c_title, "points": c_points, "used_count": 0})
                            st.session_state.data["challenge_pool"] = challenge_katalog
                            speichere_daten(st.session_state.data)
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
                            speichere_daten(st.session_state.data)
                            st.success("Neue Challenge im Katalog gespeichert!")
                            st.rerun()

            with ch_tr_4:
                st.markdown("##### 🗂️ Gesamter Challenge-Katalog:")
                if not challenge_katalog:
                    st.write("Dein Katalog ist leer.")
                else:
                    for c in challenge_katalog:
                        status = f"⚠️ {c.get('used_count',0)}x genutzt" if c.get('used_count',0) > 0 else "🟢 Neu"
                        is_active = " (🟢 AKTUELL AKTIV)" if c["id"] in active_ch_ids else ""
                        
                        with st.expander(f"✏️ [{c['id']}] {c['title']} {is_active} ({c.get('points',25)} EP)"):
                            with st.form(f"edit_c_form_{c['id']}"):
                                e_title = st.text_input("Aufgabe anpassen:", value=c['title'])
                                e_pts = st.number_input("Punkte (EP):", min_value=5, max_value=100, value=int(c.get('points', 25)))
                                
                                if st.form_submit_button("💾 Änderungen speichern", type="primary"):
                                    c['title'] = e_title.strip()
                                    c['points'] = int(e_pts)
                                    speichere_daten(st.session_state.data)
                                    st.toast("🎉 Challenge erfolgreich aktualisiert!", icon="✏️")
                                    st.rerun()
                                    
                            if st.button("🗑️ Challenge aus Katalog löschen", key=f"del_c_{c['id']}"):
                                st.session_state.data["challenge_pool"] = [x for x in challenge_katalog if x["id"] != c["id"]]
                                st.session_state.data["active_challenge_ids"] = [x for x in active_ch_ids if x != c["id"]]
                                speichere_daten(st.session_state.data)
                                st.success("Challenge gelöscht!")
                                st.rerun()

        if logged_in_player and aktive_challenges:
            st.divider()
            st.markdown(f"**Hi {logged_in_player['name']}, hake hier deine geschafften Challenges ab:**")
            
            alle_geschafft = True
            for c in aktive_challenges:
                c_id_key = f"ch_id_{c['id']}"
                already_done = c_id_key in logged_in_player.get("completed_challenges", [])
                
                if already_done:
                    st.success(f"✅ **{c['title']}** – Erfolgreich abgehakt!")
                else:
                    alle_geschafft = False
                    if st.button(f"🔥 Ich habe '{c['title']}' geschafft!", key=f"btn_done_{c['id']}", type="primary"):
                        logged_in_player["points"] = logged_in_player.get("points", 0) + int(c.get("points", 25))
                        if "completed_challenges" not in logged_in_player: logged_in_player["completed_challenges"] = []
                        logged_in_player["completed_challenges"].append(c_id_key)
                        speichere_daten(st.session_state.data)
                        st.balloons()
                        st.success(f"Punkte für '{c['title']}' gutgeschrieben!")
                        st.rerun()
            
            if alle_geschafft:
                st.info("🏆 Wahnsinn! Du hast bereits alle Aufgaben für diese Woche erledigt!")
                
        elif not logged_in_player and aktive_challenges:
            st.info("🔒 Logge dich in der Sidebar als Spieler ein, um die Challenges abzuhaken.")

    with c_sub2:
        st.markdown("### 🧩 Taktik-Quiz & Punkte-Konto")
        master_katalog = st.session_state.data.get("quiz_pool", [])
        aktive_ids = st.session_state.data.get("active_quiz_ids", [])
        
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
                            
                        speichere_daten(st.session_state.data)
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
                            speichere_daten(st.session_state.data)
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
                            speichere_daten(st.session_state.data)
                            st.success("Neue Frage im Katalog gespeichert!")
                            st.rerun()

            with tr_q_tab4:
                st.markdown("##### 🗂️ Alle Fragen im Gesamtkatalog:")
                if not master_katalog: 
                    st.write("Katalog ist leer.")
                else:
                    for q in master_katalog:
                        status = f"⚠️ {q.get('used_count',0)}x genutzt" if q.get('used_count',0) > 0 else "🟢 Neu"
                        is_active_str = " (🟢 DIESE WOCHE AKTIV)" if q["id"] in aktive_ids else ""
                        
                        with st.expander(f"✏️ [{q['id']}] {q['question']} {is_active_str}"):
                            with st.form(f"edit_q_form_{q['id']}"):
                                eq_q = st.text_input("Taktikfrage:", value=q.get("question", ""))
                                
                                opts = q.get("options", ["A) ", "B) ", "C) "])
                                while len(opts) < 3: opts.append("")
                                
                                val_a = opts[0][3:].strip() if opts[0].startswith("A)") else opts[0]
                                val_b = opts[1][3:].strip() if opts[1].startswith("B)") else opts[1]
                                val_c = opts[2][3:].strip() if opts[2].startswith("C)") else opts[2]
                                
                                eq_a = st.text_input("Antwort A:", value=val_a)
                                eq_b = st.text_input("Antwort B:", value=val_b)
                                eq_c = st.text_input("Antwort C:", value=val_c)
                                
                                cur_corr = q.get("correct", "")
                                corr_idx = 0
                                if cur_corr.startswith("B)"): corr_idx = 1
                                elif cur_corr.startswith("C)"): corr_idx = 2
                                
                                eq_correct = st.selectbox("Richtige Option:", ["Option A", "Option B", "Option C"], index=corr_idx)
                                eq_pts = st.number_input("Punkte:", min_value=5, max_value=50, value=int(q.get("points", 10)))
                                
                                if st.form_submit_button("💾 Änderungen speichern", type="primary"):
                                    q["question"] = eq_q.strip()
                                    q["options"] = [f"A) {eq_a.strip()}", f"B) {eq_b.strip()}", f"C) {eq_c.strip()}"]
                                    
                                    if eq_correct == "Option A": q["correct"] = f"A) {eq_a.strip()}"
                                    elif eq_correct == "Option B": q["correct"] = f"B) {eq_b.strip()}"
                                    else: q["correct"] = f"C) {eq_c.strip()}"
                                    
                                    q["points"] = int(eq_pts)
                                    speichere_daten(st.session_state.data)
                                    st.toast("🎉 Frage erfolgreich aktualisiert!", icon="✏️")
                                    st.rerun()
                                    
                            if st.button("🗑️ Frage aus Katalog löschen", key=f"del_q_{q['id']}"):
                                st.session_state.data["quiz_pool"] = [x for x in master_katalog if x["id"] != q["id"]]
                                st.session_state.data["active_quiz_ids"] = [x for x in aktive_ids if x != q["id"]]
                                speichere_daten(st.session_state.data)
                                st.success("Frage gelöscht!")
                                st.rerun()
            st.divider()

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
                            speichere_daten(st.session_state.data)
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
            speichere_daten(st.session_state.data)
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
        speichere_daten(st.session_state.data)
        st.success("Kader erfolgreich aktualisiert!")

# --- TAB 5: SPIEL LOGGEN ---
if selected_tab == "⚽ Spiel loggen" and is_trainer:
    st.subheader("⚽ Spieltag Statistiken loggen")
    c_meta1, c_meta2, c_meta3 = st.columns(3); m_datum = c_meta1.date_input("Datum Spiel", datetime.today()); m_type = c_meta2.selectbox("Spielart", ["Ligaspiel", "Testspiel"]); m_opponent = c_meta3.text_input("Gegner", placeholder="z.B. VfL Hamburg")
    col_blau, col_gelb = st.columns(2)
    with col_blau: st.markdown("<b>🔵 Team Blau Ergebnisse</b>", unsafe_allow_html=True); sub_b = st.columns(4); m_b1 = sub_b[0].text_input("Sp. 1", "0:0", key="b1"); m_b2 = sub_b[1].text_input("Sp. 2", "0:0", key="b2"); m_b3 = sub_b[2].text_input("Sp. 3", "0:0", key="b3"); m_b4 = sub_b[3].text_input("Sp. 4", "0:0", key="b4")
    with col_gelb: st.markdown("<b>🟡 Team Gelb Ergebnisse</b>", unsafe_allow_html=True); sub_g = st.columns(4); m_g1 = sub_g[0].text_input("Sp. 1", "0:0", key="g1"); m_g2 = sub_g[1].text_input("Sp. 2", "0:0", key="g2"); m_g3 = sub_g[3].text_input("Sp. 3", "0:0", key="g3"); m_g4 = sub_g[4].text_input("Sp. 4", "0:0", key="g4")
    st.divider(); spiel_liste = []
    for p in nur_spieler:
        planung = st.session_state.zuweisungen.get(str(p["id"]), "🤖 KI entscheidet")
        default_status = "❌ Nicht in Kader" if planung == "❌ Abwesend" else ("🔵 Team Blau" if planung == "🤖 KI entscheidet" else planung)
        spiel_liste.append({"ID": str(p["id"]), "Nr.": int(p["number"]) if str(p["number"]).isdigit() else None, "Name": p["name"], "Team / Status": default_status, "⚽ Tore": 0, "Vorlagen": 0})
    spiel_df = pd.DataFrame(spiel_liste)
    if not spiel_df.empty: spiel_df = spiel_df.sort_values(by="Nr.", na_position="last").reset_index(drop=True)
    editiertes_spiel = st.data_editor(spiel_df, disabled=["ID", "Nr.", "Name"], hide_index=True, column_config={"ID": None, "Nr.": st.column_config.NumberColumn("Nr.", format="%d"), "Team / Status": st.column_config.SelectboxColumn(options=["🔵 Team Blau", "🟡 Team Gelb", "🔄 Ersatzbank", "❌ Nicht im Kader"], required=True), "⚽ Tore": st.column_config.NumberColumn(min_value=0, format="%d"), "Vorlagen": st.column_config.NumberColumn(min_value=0, format="%d")}, use_container_width=True)
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
            speichere_daten(st.session_state.data)
            st.success("Spieltag erfolgreich archiviert!")

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
            st.dataframe(df_import.head(2))
            spalten = df_import.columns.tolist()
            
            def f_sp(w):
                for i, s in enumerate(spalten):
                    if s.lower() in w: return i
                for i, s in enumerate(spalten):
                    if any(x in s.lower() for x in w) and "team" not in s.lower(): return i
                return 0
                
            c1, c2, c3, c4 = st.columns(4)
            name_sp = c1.selectbox("Name Spalte", spalten, index=f_sp(["user_name", "spielername", "spieler", "name"]))
            tail_sp = c2.selectbox("Beteiligung Spalte", spalten, index=f_sp(["user_participation", "zusage", "status"]))
            dat_sp = c3.selectbox("Datum Spalte", spalten, index=f_sp(["event_date_start", "datum", "date"]))
            typ_sp = c4.selectbox("Event-Typ Spalte", spalten, index=f_sp(["event_type", "typ", "art"]))
            
            st.divider()
            st.markdown("#### 🔄 Namens-Zuordnung überprüfen")
            st.caption("Prüfe, ob die Namen aus der CSV-Datei korrekt mit deinen Spielern verknüpft sind.")
            
            # Alle einzigartigen Namen aus der CSV holen
            csv_namen = df_import[name_sp].astype(str).str.strip().unique().tolist()
            db_spieler_namen = sorted([p["name"] for p in st.session_state.data["players"]])
            
            mapping_daten = []
            for csv_name in csv_namen:
                # Versuch einer automatischen Zuordnung (Case-Insensitive)
                match = next((db_n for db_n in db_spieler_namen if db_n.lower() == csv_name.lower()), "➕ Als neuen Spieler anlegen")
                mapping_daten.append({"Name in CSV": csv_name, "Zuordnung in App": match})
            
            mapping_df = pd.DataFrame(mapping_daten)
            
            # Editor für die Zuordnung
            editiertes_mapping = st.data_editor(
                mapping_df,
                hide_index=True,
                disabled=["Name in CSV"],
                column_config={
                    "Zuordnung in App": st.column_config.SelectboxColumn(
                        "Verknüpfen mit...",
                        options=["➕ Als neuen Spieler anlegen", "❌ Ignorieren (Nicht importieren)"] + db_spieler_namen,
                        required=True
                    )
                },
                use_container_width=True
            )
            
            # Erzeuge ein Dictionary für schnellen Lookup beim Import
            mapping_dict = {row["Name in CSV"]: row["Zuordnung in App"] for _, row in editiertes_mapping.iterrows()}

            if st.button("💾 Daten jetzt verarbeiten", type="primary"):
                imp = 0
                for index, row in df_import.iterrows():
                    p_n_csv = str(row[name_sp]).strip()
                    ziel_name = mapping_dict.get(p_n_csv, "❌ Ignorieren (Nicht importieren)")
                    
                    if ziel_name == "❌ Ignorieren (Nicht importieren)":
                        continue
                        
                    p_t = str(row[tail_sp]).strip().lower()
                    p_d = str(row[dat_sp]).strip().split(" ")[0]
                    p_y = str(row[typ_sp]).strip()
                    
                    erfolgs_woerter = ["status_confirmed", "ja", "zugesagt", "anwesend", "erschienen", "teilgenommen", "1", "true", "yes"]
                    anw = any(wort in p_t for wort in erfolgs_woerter)
                    
                    # Spieler finden oder neu anlegen
                    if ziel_name == "➕ Als neuen Spieler anlegen":
                        sp = next((x for x in st.session_state.data["players"] if p_n_csv.lower() == x["name"].lower()), None)
                        if not sp: 
                            sp = {"id": max([x["id"] for x in st.session_state.data["players"]]+[0])+1, "name": p_n_csv, "role": "Spieler", "number": "", "positions": ["ZM"], "training": [], "matches": [], "pin": "", "video_url": "", "video_notes": "", "points": 0, "completed_challenges": [], "solved_quizzes": []}
                            st.session_state.data["players"].append(sp)
                    else:
                        sp = next(x for x in st.session_state.data["players"] if x["name"] == ziel_name)
                        
                    # Training eintragen
                    if "training" not in sp: sp["training"] = []
                    bestehender_eintrag = next((t for t in sp["training"] if t.get('date') == p_d and t.get('type') == p_y), None)
                    if bestehender_eintrag: 
                        bestehender_eintrag["present"] = anw
                    else: 
                        sp["training"].append({"date": p_d, "type": p_y, "present": anw})
                    imp += 1
                    
                speichere_daten(st.session_state.data)
                st.toast("🎉 Daten erfolgreich aktualisiert!", icon="🚀")
                st.success(f"🎉 Erfolg! {imp} Einträge wurden verarbeitet.")
        except Exception as e: st.error(f"Fehler: {e}")

    st.write(""); st.divider(); st.markdown("### ⚠️ Gefahrenzone")
    if st.button("💥 Alle Trainingsdaten unwiderruflich löschen", type="secondary"):
        for p in st.session_state.data["players"]: p["training"] = []
        speichere_daten(st.session_state.data)
        st.toast("🔥 Gelöscht!", icon="🗑️")
        st.success("Trainingszähler steht wieder auf 0%!")

# # --- TAB 8: MAẞGESCHNEIDERTER KI 5-PHASEN TRAININGSPLANER ---
if selected_tab == "📋 Trainingsplaner" and is_trainer:
    st.subheader("📋 Interaktiver Alsterbrüder 5-Phasen-Trainingsplaner")
    st.caption("Massgeschneidert auf dein Viertelfeld (2 Jugendtore, 4 Minitore, Hütchen & Stangen)")


    p_tab_gen, p_tab_db, p_tab_draw, p_tab_pdf = st.tabs([
        "✨ KI-Einheit generieren",
        "🗂️ Übungssammlung",
        "🎨 Skizzen zeichnen",
        "🧱 Einheiten-Baukasten & PDF-Export",
        ])
    
    with p_tab_draw:
        st.markdown("### 🎨 Taktik-Skizzen für deine Übungen zeichnen")
        st.caption("Nutze das Board, um eigene Skizzen zu erstellen. Klicke im Board auf '⚽ An Übung senden', kopiere den Code und verknüpfe ihn direkt mit einer Übung.")
        
        render_html5_taktikboard()
        
        st.divider()
        st.markdown("#### 🔗 Skizze aus Board einer Übung zuweisen")
        
        db_exercises = st.session_state.data.get("exercises", [])
        
        with st.form("assign_sketch_form"):
            code_input = st.text_area("📋 Taktik-Code hier einfügen (aus '⚽ An Übung senden'):", height=70)
            
            ex_options = {"➕ Als NEUE Übung anlegen": -1}
            for ex in db_exercises:
                ex_options[f"[{ex.get('phase', 'Phase')}] {ex.get('name', 'Übung')}"] = ex["id"]
                
            selected_ex_label = st.selectbox("Ziel-Übung auswählen:", list(ex_options.keys()))
            selected_ex_id = ex_options[selected_ex_label]
            
            # Zusatzfelder, falls die Skizze als neue Übung angelegt werden soll
            new_ex_name = st.text_input("Name der neuen Übung (nur wichtig bei 'Als NEUE Übung anlegen'):")
            new_ex_phase = st.selectbox("Phase (nur bei neuer Übung):", PHASEN_NAMEN)
            
            if st.form_submit_button("💾 Skizze jetzt verknüpfen & speichern", type="primary"):
                if not code_input.strip():
                    st.error("Bitte füge zuerst den Taktik-Code aus dem Board ein!")
                elif selected_ex_id == -1 and not new_ex_name.strip():
                    st.error("Bitte gib einen Namen für die neue Übung ein!")
                else:
                    if selected_ex_id == -1:
                        # Neue Übung in der DB anlegen
                        neue_id = max([x.get("id", 0) for x in db_exercises] + [0]) + 1
                        neue_uebung = {
                            "id": neue_id,
                            "name": new_ex_name.strip(),
                            "phase": new_ex_phase,
                            "schwerpunkt": "Eigene Skizze",
                            "spieler": "Kader",
                            "tw": "Egal",
                            "aufbau": "Manuell erstellt mit Skizze aus Taktikboard.",
                            "grafik": code_input.strip()
                        }
                        st.session_state.data["exercises"].append(neue_uebung)
                        st.toast(f"🎉 Neue Übung '{new_ex_name}' mit Skizze gespeichert!", icon="⚽")
                    else:
                        # Bestehende Übung in der DB aktualisieren
                        target_ex = next((x for x in db_exercises if x["id"] == selected_ex_id), None)
                        if target_ex:
                            target_ex["grafik"] = code_input.strip()
                            st.toast(f"🎉 Skizze erfolgreich an '{target_ex['name']}' angehängt!", icon="🔗")
                            
                    speichere_daten(st.session_state.data)
                    st.rerun()

    with p_tab_pdf:
        st.markdown("### 🧱 Stelle deine heutige Einheit zusammen")
        st.caption("Wähle aus deiner Datenbank für jede der 5 Phasen die passende Übung aus.")

        db_exercises = st.session_state.data.get("exercises", [])

        if not db_exercises:
            st.warning("Deine Datenbank ist noch leer. Speichere zuerst Übungen aus dem KI-Planer oder lege welche an!")
        else:
            col_meta1, col_meta2 = st.columns([2, 1])
            with col_meta1:
                plan_titel = st.text_input("Titel der Einheit:", value="U13 Viertelfeld-Einheit")
            with col_meta2:
                plan_datum = st.date_input("Datum des Trainings:")

            st.divider()
            st.markdown("##### 🔍 Übungssammlung für heutigen Kader filtern:")
            b_f1, b_f2 = st.columns([1.5, 1])
            with b_f1:
                b_sp_bereich = st.slider("Spieleranzahl-Bereich:", min_value=4, max_value=24, value=(6, 20), key="baukasten_sp_slider")
                b_min_sp, b_max_sp = b_sp_bereich
            with b_f2:
                b_filter_tw = st.selectbox("Verfügbare Torhüter (TW):", ["Egal", "Ohne TW (0)", "1 TW", "2 TW"], key="baukasten_tw_select")

            st.divider()
            gewaehlte_einheit = []

            # Für jede der 5 Phasen ein gefiltertes Auswahlfeld erzeugen
            for i, phase_name in enumerate(PHASEN_NAMEN, 1):
                st.markdown(f"#### {phase_name}")
                
                target_phase = phase_name.lower()
                passende = []
                
                for ex in db_exercises:
                    ex_phase = str(ex.get("phase", ex.get("phase_title", ""))).strip().lower()
                    
                    if not ex_phase or ex_phase == "phase":
                        continue
                    
                    if ex_phase in target_phase or target_phase in ex_phase:
                        # 1. Spieleranzahl-Bereich prüfen
                        sp_str = str(ex.get("spieler", ""))
                        nums = [int(n) for n in re.findall(r'\d+', sp_str)]
                        if nums:
                            ex_min, ex_max = min(nums), max(nums)
                            if ex_max < b_min_sp or ex_min > b_max_sp:
                                continue

                        # 2. Torhüter (TW) Filter prüfen
                        tw_val = str(ex.get("tw", "")).strip()
                        full_text = f"{ex.get('name', '')} {ex.get('aufbau', '')} {ex.get('schwerpunkt', '')} {sp_str}".lower()
                        
                        if b_filter_tw == "Ohne TW (0)":
                            if "0 tw" in tw_val or "ohne" in tw_val.lower():
                                pass
                            elif "2 tw" in full_text or "1 tw" in full_text or "torwart" in full_text or "torhüter" in full_text:
                                if "ohne tw" not in full_text and "kein tw" not in full_text:
                                    continue
                        elif b_filter_tw == "1 TW":
                            if "1 tw" in tw_val:
                                pass
                            elif "2 tw" in full_text or "2 torhüter" in full_text or "ohne tw" in full_text:
                                if "1 tw" not in full_text and "1 torwart" not in full_text and "1 torhüter" not in full_text:
                                    continue
                        elif b_filter_tw == "2 TW":
                            if "2 tw" in tw_val:
                                pass
                            elif "2 tw" not in full_text and "2 torhüter" in full_text and "2 torwarte" not in full_text and "zwei tw" not in full_text:
                                continue

                        passende.append(ex)

                if passende:
                    options_map = {
                        f"{ex.get('name', 'Ohne Name')} ({ex.get('spieler', 'Kader')})": ex 
                        for ex in passende
                    }
                    
                    selected_key = st.selectbox(
                        f"Übung für {phase_name} wählen:", 
                        options=list(options_map.keys()), 
                        key=f"baukasten_p_{i}"
                    )
                    
                    if selected_key:
                        gewaehlte_einheit.append(options_map[selected_key])
                else:
                    st.warning(f"⚠️ Keine passende Übung für '{phase_name}' mit diesen Kriterien ({b_min_sp}–{b_max_sp} Spieler, {b_filter_tw}) in der Datenbank.")

            st.divider()

            # Download-Button erscheint, sobald alle 5 Phasen besetzt sind
            if len(gewaehlte_einheit) == 5:
                pdf_html = generiere_druck_html(plan_titel, plan_datum.strftime("%d.%m.%Y"), gewaehlte_einheit)
                
                st.download_button(
                    label="📄 Druckfertigen Trainingsplan herunterladen (HTML/PDF)",
                    data=pdf_html,
                    file_name=f"Trainingsplan_{plan_datum.strftime('%Y-%m-%d')}.html",
                    mime="text/html",
                    type="primary"
                )
                
                st.info("💡 **Tipp:** Wenn du die heruntergeladene Datei öffnest, klickst du einfach auf 'Als PDF speichern'. So erhältst du ein perfektes DIN A4 Dokument inkl. aller Taktikskizzen!")
            elif db_exercises:
                st.caption("ℹ️ Sobald für alle 5 Phasen jeweils eine Übung gewählt ist, wird der PDF-Download freigeschaltet.")
    with p_tab_gen:
        c_conf1, c_col2 = st.columns([1, 1])
        with c_conf1:
            anzahl_sp = st.number_input("Anzahl anwesender Spieler:", min_value=6, max_value=24, value=len(nur_spieler) if nur_spieler else 14)
        with c_col2:
            anzahl_tw = st.selectbox("Verfügbare Torhüter (TW):", ["Egal", "Ohne TW (0)", "1 TW", "2 TW"], index=0, key="gen_tw_select")

        st.markdown("##### ⚙️ Welche Phasen sollen neu generiert werden?")
        ch_col1, ch_col2, ch_col3, ch_col4, ch_col5 = st.columns(5)
        p1_active = ch_col1.checkbox("Phase 1\n(Aufwärmen)", value=True)
        p2_active = ch_col2.checkbox("Phase 2\n(Passspiel)", value=True)
        p3_active = ch_col3.checkbox("Phase 3\n(Rondo)", value=True)
        p4_active = ch_col4.checkbox("Phase 4\n(Duelle)", value=True)
        p5_active = ch_col5.checkbox("Phase 5\n(Abschluss)", value=True)

        gewaehlte_phasen = [p1_active, p2_active, p3_active, p4_active, p5_active]

        if st.button("✨ Neue KI-Einheit auf dem Viertelfeld generieren", type="primary"):
            if not gemini_key:
                st.error("⚠️ Kein Gemini API Key hinterlegt.")
            else:
                with st.spinner("🤖 Gemini berechnet deine gewählten Phasen..."):
                    db_ex = st.session_state.data.get("exercises", [])
                    alter_plan = st.session_state.get("aktueller_ki_plan", None)
                    
                    neue_einheit = generiere_ki_einheit_5_phasen(
                        anzahl_sp, gewaehlte_phasen, gemini_key, db_ex, alter_plan, anzahl_tw
                    )
                    
                    if neue_einheit:
                        st.session_state.aktueller_ki_plan = neue_einheit
                        st.toast("🎉 Übungen wurden aktualisiert!", icon="⚽")

        # ANZEIGE DES KI-GENERIEREN PLANS
        if "aktueller_ki_plan" in st.session_state and st.session_state.aktueller_ki_plan:
            st.divider()
            st.markdown(f"### 📋 Dein aktueller Trainingsplan ({anzahl_sp} Spieler)")
            
            for idx, ph in enumerate(st.session_state.aktueller_ki_plan):
                with st.container(border=True):
                    col_t, col_svg = st.columns([2, 1])
                    with col_t:
                        st.markdown(f"#### Phase {ph.get('phase_num', idx+1)}: {ph.get('exercise_name', 'Übung')}")
                        st.caption(f"📌 **Kategorie:** {ph.get('phase_title', PHASEN_NAMEN[idx])}")
                        st.caption(f"👥 **Geeignet für:** {ph.get('spieler_bereich', f'{anzahl_sp} Spieler')}")
                        st.markdown(f"**🛠️ Aufbau & Material:**\n{ph.get('setup_text', '-')}")
                        st.markdown(f"**🏃‍♂️ Ablauf & Regeln:**\n{ph.get('flow_text', '-')}")
                        st.markdown(f"**🗣️ Coaching-Tipps:** {ph.get('coaching_points', '-')}")
                        
                        st.write("")
                        # SPEICHERKNOPF MIT DYNAMISCHEM SPIELER-BEREICH
                        if st.button(f"💾 In Übungs-Datenbank speichern", key=f"save_ex_{idx}_{ph.get('exercise_name')}"):
                            neue_id = max([x.get("id", 0) for x in st.session_state.data["exercises"]] + [0]) + 1
                            full_aufbau = f"🛠️ AUFBAU:\n{ph.get('setup_text', '')}\n\n🏃‍♂️ ABLAUF:\n{ph.get('flow_text', '')}\n\n🗣️ COACHING:\n{ph.get('coaching_points', '')}"
                            
                            p_num = ph.get('phase_num', idx+1)
                            p_title_str = PHASEN_NAMEN[p_num - 1] if 1 <= p_num <= 5 else PHASEN_NAMEN[idx]

                            st.session_state.data["exercises"].append({
                                "id": neue_id,
                                "name": ph.get('exercise_name', 'KI Übung'),
                                "phase": p_title_str,
                                "schwerpunkt": "Viertelfeld / KI-Generiert",
                                "spieler": ph.get('spieler_bereich', f"{anzahl_sp} Spieler"),
                                "aufbau": full_aufbau,
                                "grafik": ph.get("svg_code", "")
                            })
                            speichere_daten(st.session_state.data)
                            st.toast(f"🎉 '{ph.get('exercise_name')}' ({ph.get('spieler_bereich', '')}) gespeichert!", icon="💾")

                    with col_svg:
                        svg = ph.get('svg_code', '').strip()
                        if svg and '<svg' in svg:
                            # Skizze ist da -> Anzeigen
                            render_svg_responsive(svg, height=320)
                        else:
                            # Noch keine Skizze da -> Button anzeigen
                            st.info("Keine Skizze vorhanden.")
                            if st.button(f"🎨 Skizze mit KI generieren", key=f"draw_svg_{idx}"):
                                with st.spinner("🤖 Zeichne Taktik-Skizze..."):
                                    uebungs_infos = f"{ph.get('exercise_name')} | Aufbau: {ph.get('setup_text')} | Ablauf: {ph.get('flow_text')}"
                                    neue_skizze = generiere_ki_skizze(uebungs_infos, gemini_key)
                                    if neue_skizze:
                                        st.session_state.aktueller_ki_plan[idx]["svg_code"] = neue_skizze
                                        st.rerun()

            # CHAT-EINGABE FÜR ANPASSUNGEN
            st.divider()
            st.markdown("### 💬 Passt was nicht? Diskutiere mit Gemini:")
            user_chat_msg = st.chat_input("Änderungswunsch eingeben (z. B. 'Mach Phase 3 zu einem 4v2 Rondo')...")
            if user_chat_msg:
                with st.spinner("🤖 Gemini passt deinen Trainingsplan an..."):
                    angepasst = anpassung_ki_einheit_chat(st.session_state.aktueller_ki_plan, user_chat_msg, gemini_key)
                    if angepasst:
                        st.session_state.aktueller_ki_plan = angepasst
                        st.success("Plan erfolgreich überarbeitet!")
                        st.rerun()

    # 2. ÜBUNGSSAMMLUNG (ANZEIGE & DETAIL-BEARBEITUNG)
    with p_tab_db:
        st.markdown("#### 🗂️ Gespeicherte Übungssammlung")
        
        with st.expander("➕ Eigene Übung manuell anlegen (Offline-Modus)", expanded=False):
            with st.form("neue_uebung_form"):
                u_name = st.text_input("Name der Übung:")
                c_u1, c_u2 = st.columns([1, 1])
                with c_u1:
                    u_phase = st.selectbox("Trainings-Phase:", PHASEN_NAMEN)
                    u_players = st.text_input("Spieleranzahl (z. B. '10-14 Spieler'):")
                with c_u2:
                    u_focus = st.text_input("Schwerpunkt / Tag (z. B. 'Gegenpressing'):")
                    u_tw = st.selectbox("Verfügbare Torhüter (TW):", ["Egal", "Ohne TW (0)", "1 TW", "2 TW"])
                    
                u_setup = st.text_area("Aufbau, Ablauf und Coaching-Punkte:", height=120)
                u_gfx = st.text_area("Taktik-Code / SVG Skizze (Optional, aus Taktikboard kopierbar):", height=80)
                
                if st.form_submit_button("💾 Übung lokal speichern", type="primary"):
                    if not u_name.strip():
                        st.error("Bitte gib der Übung einen Namen!")
                    else:
                        neue_id = max([x.get("id", 0) for x in st.session_state.data["exercises"]] + [0]) + 1
                        neue_uebung = {
                            "id": neue_id, 
                            "name": u_name.strip(), 
                            "phase": u_phase, 
                            "schwerpunkt": u_focus.strip(), 
                            "spieler": u_players.strip(), 
                            "tw": u_tw,
                            "aufbau": u_setup.strip(), 
                            "grafik": u_gfx.strip()
                        }
                        st.session_state.data["exercises"].append(neue_uebung)
                        speichere_daten(st.session_state.data)
                        st.toast("🎉 Übung erfolgreich offline gespeichert!", icon="💾")
                        st.rerun()

        st.divider()
        if not st.session_state.data["exercises"]:
            st.info("Deine Übungssammlung ist aktuell noch leer. Speichere Übungen aus dem KI-Planer oder lege manuell welche an.")
        else:
           # --- DYNAMISCHER 3-FACH FILTER (PHASE, SPIELER-BEREICH & TORHÜTER) ---
            f_col1, f_col2, f_col3 = st.columns([1.2, 1.8, 1])
            
            with f_col1:
                filter_phase = st.selectbox("Nach Phase filtern:", ["Alle 5 Phasen"] + PHASEN_NAMEN)
                
            with f_col2:
                filter_sp_bereich = st.slider("Spieleranzahl-Bereich:", min_value=4, max_value=24, value=(6, 20))
                min_sp, max_sp = filter_sp_bereich

            with f_col3:
                filter_tw = st.selectbox("Verfügbare Torhüter (TW):", ["Egal", "Ohne TW (0)", "1 TW", "2 TW"], key="db_tw_select")

            for ex in st.session_state.data["exercises"]:
                # 1. Phasen-Filter
                if filter_phase != "Alle 5 Phasen" and ex.get("phase") != filter_phase:
                    continue

                # 2. Dynamischer Spieleranzahl-Bereich Filter (prüft Überschneidungen)
                sp_str = str(ex.get("spieler", ""))
                nums = [int(n) for n in re.findall(r'\d+', sp_str)]
                if nums:
                    ex_min, ex_max = min(nums), max(nums)
                    if ex_max < min_sp or ex_min > max_sp:
                        continue

                # 3. Torhüter (TW) Filter (mit smarter Text-Erkennung)
                tw_val = str(ex.get("tw", "")).strip()
                full_text = f"{ex.get('name', '')} {ex.get('aufbau', '')} {ex.get('schwerpunkt', '')} {sp_str}".lower()
                
                if filter_tw == "Ohne TW (0)":
                    if "0 tw" in tw_val or "ohne" in tw_val.lower():
                        pass
                    elif "2 tw" in full_text or "1 tw" in full_text or "torwart" in full_text or "torhüter" in full_text:
                        if "ohne tw" not in full_text and "kein tw" not in full_text:
                            continue
                elif filter_tw == "1 TW":
                    if "1 tw" in tw_val:
                        pass
                    elif "2 tw" in full_text or "2 torhüter" in full_text or "ohne tw" in full_text:
                        if "1 tw" not in full_text and "1 torwart" not in full_text and "1 torhüter" not in full_text:
                            continue
                elif filter_tw == "2 TW":
                    if "2 tw" in tw_val:
                        pass
                    elif "2 tw" not in full_text and "2 torhüter" in full_text and "2 torwarte" not in full_text and "zwei tw" not in full_text:
                        continue
                    
                # 3. NACHTRÄGLICHES BEARBEITEN & GRAFIK-VORSCHAU
                with st.expander(f"✏️ [{ex.get('phase', 'Phase')}] {ex.get('name', 'Übung')}", expanded=False):
                    
                    # --- RESPONSIVE SKIZZEN-VORSCHAU IN DER DATENBANK ---
                    svg_code = ex.get('grafik', '').strip()
                    if svg_code and '<svg' in svg_code:
                      st.markdown('**🎨 Taktik-Skizze mit Maßangaben:**')
                      render_svg_responsive(svg_code, height=340)
                    elif svg_code and svg_code.startswith('['):
                      st.info("💡 Diese Übung enthält einen Taktik-Code aus deinem Board! Kopiere ihn einfach hier raus und lade ihn im Taktikboard (Tab: Skizzen zeichnen) über den '📂 Import'-Button, um die Übung zu bearbeiten.")
                    # -------------------------------------------

                    with st.form(key=f"edit_ex_form_{ex['id']}"):
                        e_name = st.text_input("Übungsname:", value=ex.get("name", ""))
                        
                        cur_p = ex.get("phase", PHASEN_NAMEN[0])
                        p_idx = PHASEN_NAMEN.index(cur_p) if cur_p in PHASEN_NAMEN else 0
                        e_phase = st.selectbox("Phase zuordnen:", PHASEN_NAMEN, index=p_idx)
                        
                        e_focus = st.text_input("Schwerpunkt:", value=ex.get("schwerpunkt", ""))
                        e_players = st.text_input("Spieleranzahl:", value=ex.get("spieler", ""))
                        
                        cur_tw = ex.get("tw", "Egal")
                        tw_options = ["Egal", "Ohne TW (0)", "1 TW", "2 TW"]
                        tw_idx = tw_options.index(cur_tw) if cur_tw in tw_options else 0
                        e_tw = st.selectbox("Torhüter-Anforderung:", tw_options, index=tw_idx)
                        
                        e_aufbau = st.text_area("Aufbau, Ablauf & Regeln:", value=ex.get("aufbau", ""), height=150)
                        e_grafik = st.text_area("Taktik-Code (Füge hier SVG oder Board-Export ein):", value=ex.get("grafik", ""), height=80)
                        
                        btn_c1, btn_c2 = st.columns([1, 1])
                        save_btn = btn_c1.form_submit_button("💾 Änderungen für diese Übung speichern", type="primary")
                        
                        if save_btn:
                            ex["name"] = e_name.strip()
                            ex["phase"] = e_phase
                            if "rating" in ex: del ex["rating"]
                            ex["schwerpunkt"] = e_focus.strip()
                            ex["spieler"] = e_players.strip()
                            ex["tw"] = e_tw
                            ex["aufbau"] = e_aufbau.strip()
                            ex["grafik"] = e_grafik.strip()
                            speichere_daten(st.session_state.data)
                            st.toast("🎉 Übung erfolgreich aktualisiert!", icon="✏️")
                            st.rerun()

                    # Löschen Button (außerhalb der Form)
                    if st.button("🗑️ Übung aus Datenbank löschen", key=f"del_ex_{ex['id']}"):
                        st.session_state.data["exercises"] = [x for x in st.session_state.data["exercises"] if x["id"] != ex["id"]]
                        speichere_daten(st.session_state.data)
                        st.toast("🗑️ Übung gelöscht!")
                        st.rerun()
                        # GANZ UNTEN IN DER ÜBUNGSSAMMLUNG RENDERER AUFRUFEN:
        render_ki_anpassen_bereich(gemini_key)
# --- TAB 9: LIGA-ZENTRALE ---
if selected_tab == "🏆 Liga-Tabelle":
    st.subheader("🏆 Liga-Zentrale (U12 Bezirksliga 36)")
    st.link_button("🌐 Offizielle fussball.de Tabelle öffnen", "[https://www.fussball.de/spieltagsuebersicht/u12-bzl-36-fruehjahr-bezirksebene-hamburg-d-junioren-bezirksliga-d-junioren-saison2526-hamburg/-/staffel/0306E7FA78000005VS5489BUVV5FEO72-G#!/](https://www.fussball.de/spieltagsuebersicht/u12-bzl-36-fruehjahr-bezirksebene-hamburg-d-junioren-bezirksliga-d-junioren-saison2526-hamburg/-/staffel/0306E7FA78000005VS5489BUVV5FEO72-G#!/)", type="primary")
