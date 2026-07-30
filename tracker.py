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
