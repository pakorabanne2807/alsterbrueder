// --- NAHTLOSE TOUCH-STEUERUNG FÜR SMARTPHONES ---

        drawCanvas.addEventListener('touchstart', (e) => {
            e.preventDefault(); // Stoppt Seiten-Scrollen auf dem Spielfeld sofort
            if (e.touches.length === 0) return;
            
            const pos = getTouchPos(e);
            
            // 1. Mehrfach-Auswahl Modus (Handy)
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

            // 2. Symbole verschieben oder Linien verändern
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

            // 3. Linien (Pass / Laufweg) direkt mit dem Finger ziehen
            if (activeTool === 'line' || activeTool === 'dashed') {
                isLineDrawing = true;
                lineStart = pos;
            }
        }, { passive: false });

        drawCanvas.addEventListener('touchmove', (e) => {
            e.preventDefault(); // Stoppt Seiten-Scrollen während der Finger gleitet
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
        }, { passive: false });

        drawCanvas.addEventListener('touchend', (e) => {
            e.preventDefault();
            if (isDragging) {
                isDragging = false;
                dragTarget = null;
            } else if (isLineDrawing) {
                isLineDrawing = false;
                saveSnapshot();
                redrawAll();
            }
        }, { passive: false });
