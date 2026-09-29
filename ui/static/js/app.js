// ElderAlpha AI Dashboard Client - Real-Time Live Market & TradingView Experience

let currentSymbol = "EURUSD=X";
let currentTimeframe = "15m";
let currentCapital = 10000.0;
let currentRiskPct = 0.0025;
let currentAnalysis = null;
let soundEnabled = true;
let socket = null;
let reconnectTimer = null;
let audioCtx = null;
let currentDragMode = 'pan';
let isFullscreen = false;
let paper_broker_is_halted = false;
let currentChartSymbol = null;
let currentChartTimeframe = null;
let isUserZoomed = false;
let currentXRange = null;
let currentYRange = null;

document.addEventListener("DOMContentLoaded", () => {
    initAudioContext();
    initEventListeners();
    initWebSocket();
    fetchAnalysis();
    fetchBrokerStatus();
    fetchScreener();
    fetchJournal();
    fetchAutoTrainerStatus();
    setInterval(fetchAutoTrainerStatus, 8000);
    fetchNewsStatus();
    setInterval(fetchNewsStatus, 10000);
});

function initAudioContext() {
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        audioCtx = new AudioContext();
    } catch (e) {
        console.warn("Web Audio API not supported", e);
    }
}

function playSignalChime(isBullish = true) {
    if (!soundEnabled || !audioCtx) return;
    try {
        if (audioCtx.state === 'suspended') {
            audioCtx.resume();
        }
        const now = audioCtx.currentTime;
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);

        const freq1 = isBullish ? 587.33 : 440.0; // D5 vs A4
        const freq2 = isBullish ? 880.00 : 329.63; // A5 vs E4

        osc.frequency.setValueAtTime(freq1, now);
        osc.frequency.exponentialRampToValueAtTime(freq2, now + 0.15);

        gain.gain.setValueAtTime(0.2, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.45);

        osc.start(now);
        osc.stop(now + 0.45);
    } catch (e) {
        console.error("Audio error", e);
    }
}

function initWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/live`;

    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        const badge = document.getElementById("live-indicator");
        if (badge) {
            badge.className = "flex items-center gap-1.5 px-2.5 py-1 rounded bg-emerald-950/80 border border-emerald-500/50 text-emerald-400 font-bold text-[11px]";
            badge.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span><span>LIVE STREAMING</span>`;
        }
        if (currentSymbol) {
            socket.send(`SUBSCRIBE:${currentSymbol}`);
        }
    };

    socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === "LIVE_TICK") {
                handleLiveTick(data);
            } else if (data.type === "SNAPSHOT") {
                updateMarquee(data.quotes);
            }
        } catch (e) {
            console.error("[WebSocket] Parse error:", e);
        }
    };

    socket.onclose = () => {
        const badge = document.getElementById("live-indicator");
        if (badge) {
            badge.className = "flex items-center gap-1.5 px-2.5 py-1 rounded bg-amber-950/80 border border-amber-500/50 text-amber-400 font-bold text-[11px]";
            badge.innerHTML = `<span class="w-2 h-2 rounded-full bg-amber-400 animate-pulse"></span><span>CONNECTING...</span>`;
        }
        clearTimeout(reconnectTimer);
        reconnectTimer = setTimeout(initWebSocket, 3000);
    };

    socket.onerror = (err) => {
        console.error("[WebSocket] Error:", err);
    };
}

function handleLiveTick(data) {
    if (data.all_quotes) {
        updateMarquee(data.all_quotes);
    }

    if (data.quote && data.quote.symbol === currentSymbol) {
        const q = data.quote;
        const bidAskSpan = document.getElementById("live-bid-ask");
        if (bidAskSpan) {
            bidAskSpan.innerText = `Bid: ${q.bid} | Ask: ${q.ask} (Spread: ${q.spread})`;
        }
    }

    if (data.analysis && data.analysis.symbol === currentSymbol && data.analysis.timeframe === currentTimeframe) {
        const prevSignal = currentAnalysis ? currentAnalysis.trade_signal : null;
        currentAnalysis = data.analysis;
        renderAnalysis(data.analysis, false); // Don't auto-override user manual zoom on tick

        if (!prevSignal && data.analysis.trade_signal) {
            playSignalChime(data.analysis.trade_signal.action === "BUY");
        }
    }

    updateLiveCopilotVerdict(data.analysis, data.quote);

    if (data.broker) {
        renderBrokerHUD(data.broker);
    }
}

function updateMarquee(quotes) {
    const container = document.getElementById("marquee-items");
    if (!container || !quotes) return;

    container.innerHTML = Object.values(quotes).map(q => {
        const isForex = q.type === "forex";
        const label = q.name.split("/")[0].trim();
        return `
            <div onclick="switchSymbol('${q.symbol}')" class="flex items-center space-x-2 cursor-pointer hover:text-white transition px-2 py-0.5 rounded bg-slate-900 border border-slate-800">
                <span class="text-slate-400 font-semibold">${label}:</span>
                <span class="font-bold text-white font-mono">$${q.price.toFixed(isForex ? 5 : 2)}</span>
                <span class="text-[10px] text-slate-500 font-mono">spd:${q.spread}</span>
            </div>
        `;
    }).join('');
}

function updateLiveCopilotVerdict(analysis, quote) {
    if (!analysis) return;

    const banner = document.getElementById("verdict-banner");
    const statusText = document.getElementById("verdict-status");
    const subText = document.getElementById("verdict-subtext");

    const chkSpread = document.getElementById("chk-spread");
    const chkNews = document.getElementById("chk-news");
    const chkPattern = document.getElementById("chk-pattern");
    const chkMovement = document.getElementById("chk-movement");
    const chkCircuit = document.getElementById("chk-circuit");

    const spreadOk = quote ? (quote.spread <= (quote.type === "forex" ? 0.0003 : 10.0)) : true;
    chkSpread.innerHTML = spreadOk
        ? `<i class="fa-solid fa-circle-check text-emerald-400 mr-1"></i> Tight & Safe`
        : `<i class="fa-solid fa-triangle-exclamation text-amber-400 mr-1"></i> Wide Spread`;

    const inBlackout = analysis.event_lockout && analysis.event_lockout.in_blackout;
    chkNews.innerHTML = inBlackout
        ? `<i class="fa-solid fa-circle-xmark text-rose-400 mr-1"></i> ${analysis.event_lockout.upcoming_event} Blackout`
        : `<i class="fa-solid fa-circle-check text-emerald-400 mr-1"></i> Clean Window`;

    const hasPattern = analysis.detected_pattern !== null;
    chkPattern.innerHTML = hasPattern
        ? `<i class="fa-solid fa-circle-check text-emerald-400 mr-1"></i> ${analysis.detected_pattern.pattern_type}`
        : `<i class="fa-solid fa-circle-xmark text-slate-500 mr-1"></i> No Pattern`;

    const prob = analysis.movement_ai ? analysis.movement_ai.continuation_probability : 0.5;
    const aiPass = prob >= 0.58;
    chkMovement.innerHTML = aiPass
        ? `<i class="fa-solid fa-circle-check text-emerald-400 mr-1"></i> Edge ${(prob * 100).toFixed(0)}%`
        : `<i class="fa-solid fa-circle-xmark text-slate-500 mr-1"></i> ${(prob * 100).toFixed(0)}% (Neutral)`;

    const isSafe = !paper_broker_is_halted;
    chkCircuit.innerHTML = isSafe
        ? `<i class="fa-solid fa-circle-check text-emerald-400 mr-1"></i> Safe (0.25% Rule)`
        : `<i class="fa-solid fa-circle-xmark text-rose-400 mr-1"></i> Halted`;

    if (inBlackout) {
        banner.className = "p-3 rounded-lg border border-rose-600 bg-rose-950/70 mb-3 flex items-center justify-between";
        statusText.innerHTML = `<i class="fa-solid fa-ban text-rose-400"></i> NO-GO (EVENT RISK)`;
        statusText.className = "text-sm font-bold text-rose-300 flex items-center gap-1.5";
        subText.innerText = "Macro News Blackout Active";
    } else if (hasPattern && spreadOk && isSafe) {
        const side = analysis.detected_pattern.direction;
        banner.className = "p-3 rounded-lg border border-emerald-500 bg-emerald-950/80 mb-3 flex items-center justify-between ring-2 ring-emerald-500/50 animate-pulse";
        statusText.innerHTML = `<i class="fa-solid fa-circle-play text-emerald-400"></i> GO: EXECUTE ${side}`;
        statusText.className = "text-sm font-bold text-emerald-300 flex items-center gap-1.5";
        subText.innerText = `${analysis.detected_pattern.pattern_type} Verified`;
    } else {
        banner.className = "p-3 rounded-lg border border-slate-700 bg-slate-950/80 mb-3 flex items-center justify-between";
        statusText.innerHTML = `<i class="fa-solid fa-hand text-amber-400"></i> NO-GO (PATIENCE)`;
        statusText.className = "text-sm font-bold text-amber-400 flex items-center gap-1.5";
        subText.innerText = "Wait for high-probability setup";
    }
}

function renderBrokerHUD(data) {
    document.getElementById("hud-equity").innerText = `$${data.total_equity.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
    const pnlSpan = document.getElementById("hud-session-pnl");
    pnlSpan.innerText = `$${data.session_realized_pnl.toFixed(2)}`;
    pnlSpan.className = data.session_realized_pnl >= 0 ? "text-emerald-400 font-bold" : "text-rose-400 font-bold";

    const cb = data.circuit_breaker;
    paper_broker_is_halted = cb.is_halted;
    const cbBadge = document.getElementById("hud-circuit-badge");
    const cbText = document.getElementById("hud-circuit-text");
    if (cb.is_halted) {
        cbBadge.className = "px-3 py-1.5 rounded-lg border border-rose-600 bg-rose-950/70 text-rose-300 flex items-center gap-1.5";
        cbText.innerText = "Risk: HALTED";
    } else {
        cbBadge.className = "px-3 py-1.5 rounded-lg border border-emerald-600/40 bg-emerald-950/40 text-emerald-400 flex items-center gap-1.5";
        cbText.innerText = `Risk: Safe (${cb.consecutive_losses}/${cb.max_allowed_consecutive_losses} L)`;
    }

    const gp = data.gain_protector;
    const gpBadge = document.getElementById("hud-gain-badge");
    const gpText = document.getElementById("hud-gain-text");
    if (gp.locked_for_session) {
        gpBadge.className = "px-3 py-1.5 rounded-lg border border-emerald-500 bg-emerald-900 text-emerald-200 flex items-center gap-1.5 font-bold";
        gpText.innerText = "Gain Lock: SECURED";
    } else if (gp.protection_activated) {
        gpBadge.className = "px-3 py-1.5 rounded-lg border border-amber-500 bg-amber-950 text-amber-300 flex items-center gap-1.5";
        gpText.innerText = "Gain Lock: ACTIVE";
    } else {
        gpBadge.className = "px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-900 text-slate-400 flex items-center gap-1.5";
        gpText.innerText = "Gain Lock: Inactive";
    }

    const posTable = document.getElementById("positions-table-body");
    const posCount = document.getElementById("open-positions-count");
    posCount.innerText = data.open_positions.length;

    if (data.open_positions.length === 0) {
        posTable.innerHTML = `<tr><td colspan="11" class="p-4 text-center text-slate-500">No active positions. Execute a trade from the AI Advisor above.</td></tr>`;
    } else {
        posTable.innerHTML = data.open_positions.map(p => `
            <tr class="hover:bg-slate-800/40">
                <td class="p-2.5 text-slate-400">${p.id}</td>
                <td class="p-2.5 font-bold text-white">${p.symbol}</td>
                <td class="p-2.5 ${p.direction === 'BULLISH' ? 'text-emerald-400' : 'text-rose-400'} font-bold">${p.direction === 'BULLISH' ? 'BUY' : 'SELL'}</td>
                <td class="p-2.5 text-slate-300">${p.pattern_name}</td>
                <td class="p-2.5">$${p.entry_price.toFixed(p.entry_price < 10 ? 5 : 2)}</td>
                <td class="p-2.5 font-bold">$${p.current_price.toFixed(p.current_price < 10 ? 5 : 2)}</td>
                <td class="p-2.5 text-rose-400">$${p.stop_loss.toFixed(p.stop_loss < 10 ? 5 : 2)}</td>
                <td class="p-2.5 text-emerald-400">$${p.target_1.toFixed(p.target_1 < 10 ? 5 : 2)}</td>
                <td class="p-2.5">${p.remaining_size}</td>
                <td class="p-2.5 font-bold ${p.unrealized_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}">$${p.unrealized_pnl.toFixed(2)}</td>
                <td class="p-2.5">${p.partial_taken ? '<span class="text-cyan-400">Target 1 Taken (BE Set)</span>' : '<span class="text-slate-400">Running</span>'}</td>
            </tr>
        `).join('');
    }
}

function initEventListeners() {
    // Audio Toggle
    const audioBtn = document.getElementById("btn-audio-toggle");
    if (audioBtn) {
        audioBtn.addEventListener("click", () => {
            soundEnabled = !soundEnabled;
            audioBtn.innerHTML = soundEnabled ? `<i class="fa-solid fa-volume-high"></i>` : `<i class="fa-solid fa-volume-xmark text-slate-500"></i>`;
            if (soundEnabled && audioCtx && audioCtx.state === 'suspended') {
                audioCtx.resume();
            }
        });
    }

    // Chart Toolbar: Auto-Align
    document.getElementById("btn-chart-align").addEventListener("click", () => {
        autoAlignChart(true);
    });

    // Chart Toolbar: Zoom In
    document.getElementById("btn-chart-zoom-in").addEventListener("click", () => {
        zoomInChart();
    });

    // Chart Toolbar: Zoom Out
    document.getElementById("btn-chart-zoom-out").addEventListener("click", () => {
        zoomOutChart();
    });

    // Chart Toolbar: Pan / Drag Toggle
    document.getElementById("btn-chart-pan").addEventListener("click", () => {
        togglePanMode();
    });

    // Chart Toolbar: Fullscreen Toggle
    document.getElementById("btn-chart-fullscreen").addEventListener("click", () => {
        toggleFullscreen();
    });

    // Global Keyboard Shortcuts
    window.addEventListener("keydown", (e) => {
        // Ignore if user is typing in an input
        if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT" || e.target.tagName === "TEXTAREA") {
            return;
        }
        if (e.key === "f" || e.key === "F") {
            e.preventDefault();
            toggleFullscreen();
        } else if (e.key === "a" || e.key === "A" || e.key === "r" || e.key === "R") {
            e.preventDefault();
            autoAlignChart(true);
        } else if (e.key === "+" || e.key === "=") {
            e.preventDefault();
            zoomInChart();
        } else if (e.key === "-" || e.key === "_") {
            e.preventDefault();
            zoomOutChart();
        } else if (e.key === "p" || e.key === "P") {
            e.preventDefault();
            togglePanMode();
        } else if (e.key === "Escape" && isFullscreen) {
            e.preventDefault();
            toggleFullscreen();
        }
    });

    // Window Resize -> auto resize Plotly canvas
    window.addEventListener("resize", () => {
        Plotly.Plots.resize('plotly-chart');
    });

    // Asset Selectors
    document.querySelectorAll(".asset-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".asset-btn").forEach(b => b.classList.remove("active-asset"));
            btn.classList.add("active-asset");
            switchSymbol(btn.dataset.symbol);
        });
    });

    // Timeframe Selectors
    document.querySelectorAll(".tf-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".tf-btn").forEach(b => b.classList.remove("active-tf"));
            btn.classList.add("active-tf");
            currentTimeframe = btn.dataset.tf;
            isUserZoomed = false;
            currentChartTimeframe = null;
            currentXRange = null;
            currentYRange = null;
            fetchAnalysis(true);
            notifyActiveSymbol();
        });
    });

    // Risk Pct Selector
    const riskSelect = document.getElementById("select-risk-pct");
    if (riskSelect) {
        riskSelect.addEventListener("change", (e) => {
            currentRiskPct = parseFloat(e.target.value);
            fetchAnalysis();
        });
    }

    // Manual Refresh
    document.getElementById("btn-refresh").addEventListener("click", () => {
        fetchAnalysis();
        fetchBrokerStatus();
        fetchScreener();
        fetchJournal();
    });

    // Calibrate & Train
    document.getElementById("btn-calibrate-now").addEventListener("click", runCalibration);

    // Auto-Trainer Controls
    const toggleAutotrainBtn = document.getElementById("btn-toggle-autotrain");
    if (toggleAutotrainBtn) {
        toggleAutotrainBtn.addEventListener("click", toggleAutoTrainer);
    }
    const trainAllBtn = document.getElementById("btn-train-all-assets");
    if (trainAllBtn) {
        trainAllBtn.addEventListener("click", triggerTrainAllAssets);
    }

    // News Alert Controls (Andrew Elder Ch 4)
    const toggleNewsLockBtn = document.getElementById("btn-toggle-newslock");
    if (toggleNewsLockBtn) {
        toggleNewsLockBtn.addEventListener("click", toggleNewsLockout);
    }
    const simulateNewsBtn = document.getElementById("btn-simulate-news");
    if (simulateNewsBtn) {
        simulateNewsBtn.addEventListener("click", toggleNewsSimulation);
    }
    const toggleNewsDrawerBtn = document.getElementById("btn-toggle-news-drawer");
    if (toggleNewsDrawerBtn) {
        toggleNewsDrawerBtn.addEventListener("click", toggleNewsDrawer);
    }

    // Execute Paper Trade
    document.getElementById("btn-execute-trade").addEventListener("click", executeCurrentSignal);

    // Rescan Screener
    document.getElementById("btn-scan-market").addEventListener("click", fetchScreener);

    // Bottom Tabs Switcher
    document.querySelectorAll(".bottom-tab").forEach(tab => {
        tab.addEventListener("click", () => {
            document.querySelectorAll(".bottom-tab").forEach(t => {
                t.classList.remove("active-tab");
                t.classList.add("text-slate-400", "border-transparent");
            });
            tab.classList.add("active-tab");
            tab.classList.remove("text-slate-400", "border-transparent");

            document.querySelectorAll(".tab-content").forEach(tc => tc.classList.add("hidden"));
            const targetId = tab.dataset.target;
            document.getElementById(targetId).classList.remove("hidden");

            if (targetId === "tab-journal") fetchJournal();
            if (targetId === "tab-positions") fetchBrokerStatus();
        });
    });
}

function switchSymbol(symbol) {
    currentSymbol = symbol;
    document.querySelectorAll(".asset-btn").forEach(b => {
        if (b.dataset.symbol === symbol) {
            b.classList.add("active-asset");
        } else {
            b.classList.remove("active-asset");
        }
    });
    isUserZoomed = false;
    currentChartSymbol = null;
    currentXRange = null;
    currentYRange = null;
    const chartDiv = document.getElementById('plotly-chart');
    if (chartDiv && chartDiv.layout) {
        delete chartDiv.layout.xaxis;
        delete chartDiv.layout.yaxis;
    }
    fetchAnalysis(true);
    notifyActiveSymbol();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function notifyActiveSymbol() {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(`SUBSCRIBE:${currentSymbol}:${currentTimeframe}`);
    }
    fetch("/api/set-active-symbol", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: currentSymbol, timeframe: currentTimeframe })
    }).catch(() => {});
}

async function fetchAnalysis(shouldAutoAlign = false) {
    try {
        const url = `/api/analysis?symbol=${encodeURIComponent(currentSymbol)}&timeframe=${currentTimeframe}&capital=${currentCapital}&risk_pct=${currentRiskPct}`;
        const res = await fetch(url);
        const data = await res.json();
        if (!data.error) {
            currentAnalysis = data;
            renderAnalysis(data, shouldAutoAlign);
        }
    } catch (err) {
        console.error("Failed to fetch analysis:", err);
    }
}

function renderAnalysis(data, shouldAutoAlign = false) {
    document.getElementById("active-symbol-title").innerText = `${data.asset_name} (${data.timeframe})`;
    const priceBadge = document.getElementById("active-price-badge");
    priceBadge.innerText = data.current_price.toFixed(data.current_price < 10 ? 5 : 2);

    const patBadge = document.getElementById("active-pattern-badge");
    const patText = document.getElementById("active-pattern-text");
    if (data.detected_pattern) {
        patBadge.classList.remove("hidden");
        patText.innerText = data.detected_pattern.pattern_type;
    } else {
        patBadge.classList.add("hidden");
    }

    if (data.candles && data.candles.length > 0) {
        const last = data.candles[data.candles.length - 1];
        document.getElementById("stat-atr").innerText = last.atr14 ? last.atr14.toFixed(last.close < 10 ? 5 : 2) : "--";
        document.getElementById("stat-rvol").innerText = last.rvol ? `${last.rvol.toFixed(2)}x` : "1.00x";
        document.getElementById("stat-mfi").innerText = last.mfi14 ? last.mfi14.toFixed(1) : "50.0";
    }

    const actionBadge = document.getElementById("ai-action-badge");
    const execBtn = document.getElementById("btn-execute-trade");

    if (data.trade_signal) {
        const sig = data.trade_signal;
        const isNewsBlackout = data.news_alert && data.news_alert.in_blackout;

        if (isNewsBlackout) {
            actionBadge.innerText = "🚨 SKIPPED (NEWS BLACKOUT)";
            actionBadge.className = "px-3 py-1 rounded text-xs font-bold uppercase tracking-wider bg-rose-950 border border-rose-600 text-rose-300 animate-pulse";
        } else {
            actionBadge.innerText = `${sig.action} • ${sig.pattern}`;
            actionBadge.className = sig.action === "BUY"
                ? "px-3 py-1 rounded text-xs font-bold uppercase tracking-wider bg-emerald-950 border border-emerald-600 text-emerald-400"
                : "px-3 py-1 rounded text-xs font-bold uppercase tracking-wider bg-rose-950 border border-rose-600 text-rose-400";
        }

        document.getElementById("ai-pattern-name").innerText = sig.pattern;
        document.getElementById("ai-confidence").innerText = `${Math.round(sig.confidence * 100)}%`;
        document.getElementById("ai-payout-ratio").innerText = `${sig.payout_ratio.toFixed(2)}R`;
        document.getElementById("ai-entry-price").innerText = sig.entry_price.toFixed(sig.entry_price < 10 ? 5 : 2);
        document.getElementById("ai-stop-loss").innerText = sig.stop_loss.toFixed(sig.stop_loss < 10 ? 5 : 2);
        document.getElementById("ai-target-1").innerText = sig.target_1.toFixed(sig.target_1 < 10 ? 5 : 2);
        document.getElementById("ai-target-2").innerText = sig.target_2.toFixed(sig.target_2 < 10 ? 5 : 2);

        document.getElementById("ai-position-size").innerText = sig.units_label;
        document.getElementById("ai-max-risk").innerText = `$${sig.risk_per_trade_usd.toFixed(2)} (${(currentRiskPct * 100).toFixed(2)}%)`;
        document.getElementById("ai-rationale").innerText = sig.rationale;

        if (isNewsBlackout) {
            execBtn.disabled = true;
            execBtn.innerHTML = `<i class="fa-solid fa-ban"></i> Trade Blocked (News Blackout)`;
            execBtn.className = "w-full bg-slate-800 text-rose-400 font-bold py-2 px-4 rounded-lg text-xs uppercase tracking-wider border border-rose-900/50 cursor-not-allowed flex items-center justify-center gap-2";
        } else {
            execBtn.disabled = false;
            execBtn.innerHTML = `<i class="fa-solid fa-bolt"></i> Execute Paper Trade`;
            execBtn.className = "w-full bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:hover:bg-emerald-600 text-white font-bold py-2 px-4 rounded-lg text-xs uppercase tracking-wider transition shadow-lg flex items-center justify-center gap-2 cursor-pointer";
        }
    } else {
        actionBadge.innerText = "MONITORING";
        actionBadge.className = "px-3 py-1 rounded text-xs font-bold uppercase tracking-wider bg-slate-800 text-slate-400";
        document.getElementById("ai-pattern-name").innerText = "No active trigger (Protecting Capital)";
        document.getElementById("ai-confidence").innerText = "--%";
        document.getElementById("ai-payout-ratio").innerText = "-- (Target >= 2.0R)";
        document.getElementById("ai-entry-price").innerText = "--";
        document.getElementById("ai-stop-loss").innerText = "--";
        document.getElementById("ai-target-1").innerText = "--";
        document.getElementById("ai-target-2").innerText = "--";
        document.getElementById("ai-position-size").innerText = "Awaiting Setup";
        document.getElementById("ai-rationale").innerText = "Elder Rule: Never force trades. Wait for clean structure and minimum 2:1 payout.";
        execBtn.disabled = true;
        execBtn.innerHTML = `<i class="fa-solid fa-bolt"></i> Execute Paper Trade`;
        execBtn.className = "w-full bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:hover:bg-emerald-600 text-white font-bold py-2 px-4 rounded-lg text-xs uppercase tracking-wider transition shadow-lg flex items-center justify-center gap-2 cursor-pointer";
    }

    if (data.news_alert) {
        renderNewsHUD(data.news_alert);
    }

    if (data.movement_ai) {
        const prob = data.movement_ai.continuation_probability || 0.5;
        document.getElementById("ai-continuation-prob").innerText = `${Math.round(prob * 100)}%`;
        document.getElementById("prob-progress-bar").style.width = `${Math.min(100, Math.max(0, prob * 100))}%`;
        document.getElementById("ai-signal-quality").innerText = data.movement_ai.signal_quality || "NEUTRAL";

        const statusSpan = document.getElementById("ai-model-status");
        if (statusSpan) {
            if (data.movement_ai.is_trained) {
                const samples = data.movement_ai.training_samples || 0;
                const winRate = data.movement_ai.historical_win_rate ? ` (${data.movement_ai.historical_win_rate}% Win)` : "";
                statusSpan.innerText = `${samples.toLocaleString()} Quality Trades${winRate}`;
            } else {
                statusSpan.innerText = "Untrained";
            }
        }
    }

    if (data.calibration) {
        const cal = data.calibration;
        document.getElementById("param-atr-stop").innerText = `${cal.atr_stop_multiplier.toFixed(2)}x`;
        document.getElementById("param-atr-trail").innerText = `${cal.atr_trail_multiplier.toFixed(2)}x`;
        document.getElementById("param-fib-c").innerText = `${cal.abcd_min_pullback_fib} - ${cal.abcd_max_pullback_fib}`;
        document.getElementById("param-rvol-trigger").innerText = `${cal.rvol_threshold.toFixed(2)}x`;
    }

    if (data.options_advisory) {
        const opt = data.options_advisory;
        document.getElementById("opt-structure").innerText = opt.structure || "--";
        document.getElementById("opt-bias").innerText = opt.bias || "--";
        document.getElementById("opt-rationale").innerText = opt.rationale || "--";
    }

    renderPlotlyChart(data, shouldAutoAlign);
}

// Safe ISO Date Parser (Guaranteed never to return NaN or fallback to year 2000)
function safeParseTimestamp(str) {
    if (!str) return null;
    if (typeof str === 'number') return isNaN(str) ? null : str;
    const cleanStr = String(str).trim().replace(' ', 'T');
    const ms = Date.parse(cleanStr);
    return isNaN(ms) ? null : ms;
}

function safeFormatDate(ms) {
    if (!ms || isNaN(ms)) return null;
    const d = new Date(ms);
    if (isNaN(d.getTime())) return null;
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

// Compute TradingView-Style Auto-Aligned Bounds (Vertical breathing room + Right-hand forward margin)
function getAutoAlignedRanges(data) {
    if (!data || !data.candles || data.candles.length === 0) return null;
    const candles = data.candles;
    const lows = candles.map(c => Number(c.low)).filter(v => isFinite(v) && v > 0);
    const highs = candles.map(c => Number(c.high)).filter(v => isFinite(v) && v > 0);
    const times = candles.map(c => String(c.timestamp).trim());

    if (lows.length === 0 || highs.length === 0 || times.length === 0) return null;

    let minY = Math.min(...lows);
    let maxY = Math.max(...highs);

    if (data.detected_pattern) {
        const sl = parseFloat(data.detected_pattern.stop_loss);
        const t2 = parseFloat(data.detected_pattern.target_2);
        const t1 = parseFloat(data.detected_pattern.target_1);
        const cur = Number(data.current_price || minY);
        if (isFinite(sl) && sl > 0 && Math.abs(sl - cur) / cur < 0.4) minY = Math.min(minY, sl);
        if (isFinite(t2) && t2 > 0 && Math.abs(t2 - cur) / cur < 0.4) maxY = Math.max(maxY, t2);
        if (isFinite(t1) && t1 > 0 && Math.abs(t1 - cur) / cur < 0.4) maxY = Math.max(maxY, t1);
    }

    const ySpan = Math.max(1e-5, maxY - minY);
    const yPad = ySpan * 0.10;

    const n = times.length;
    const startIdx = Math.max(0, n - 48);
    const startTime = times[startIdx];
    const lastTime = times[n - 1];

    let tLast = safeParseTimestamp(lastTime);
    let tPrev = (n >= 2) ? safeParseTimestamp(times[n - 2]) : null;

    let endTime = lastTime;
    if (tLast && tPrev && tLast > tPrev) {
        const dt = tLast - tPrev;
        const futureMs = tLast + (8 * dt);
        const formattedFuture = safeFormatDate(futureMs);
        if (formattedFuture) {
            endTime = formattedFuture;
        }
    }

    return {
        xRange: [startTime, endTime],
        yRange: [minY - yPad, maxY + yPad]
    };
}

function renderPlotlyChart(data, shouldAutoAlign = false) {
    const candles = data.candles;
    if (!candles || candles.length === 0) return;

    const symbolChanged = (data.symbol !== currentChartSymbol);
    const timeframeChanged = (data.timeframe !== currentChartTimeframe);
    if (symbolChanged || timeframeChanged) {
        currentChartSymbol = data.symbol;
        currentChartTimeframe = data.timeframe;
        isUserZoomed = false;
        currentXRange = null;
        currentYRange = null;
    }

    const autoBounds = getAutoAlignedRanges(data);
    if (!autoBounds) return;

    if (shouldAutoAlign || !isUserZoomed || !currentXRange || !currentYRange) {
        currentXRange = autoBounds.xRange;
        currentYRange = autoBounds.yRange;
        isUserZoomed = false;
    } else {
        const chartDiv = document.getElementById('plotly-chart');
        const full = chartDiv && chartDiv._fullLayout;
        if (full && full.xaxis && full.yaxis) {
            const curY = full.yaxis.range;
            const midY = (curY[0] + curY[1]) / 2.0;
            const curPx = data.current_price;
            if (!isFinite(midY) || Math.abs(midY - curPx) / curPx > 0.6) {
                currentXRange = autoBounds.xRange;
                currentYRange = autoBounds.yRange;
                isUserZoomed = false;
            } else {
                currentXRange = [String(full.xaxis.range[0]), String(full.xaxis.range[1])];
                currentYRange = [Number(curY[0]), Number(curY[1])];
            }
        } else {
            currentXRange = autoBounds.xRange;
            currentYRange = autoBounds.yRange;
        }
    }

    const times = candles.map(c => c.timestamp);
    const opens = candles.map(c => c.open);
    const highs = candles.map(c => c.high);
    const lows = candles.map(c => c.low);
    const closes = candles.map(c => c.close);
    const ema9 = candles.map(c => c.ema9);
    const ema20 = candles.map(c => c.ema20);

    const traces = [
        {
            x: times,
            open: opens,
            high: highs,
            low: lows,
            close: closes,
            type: 'candlestick',
            name: data.symbol,
            increasing: { line: { color: '#10b981', width: 1.5 }, fillcolor: '#10b981' },
            decreasing: { line: { color: '#ef4444', width: 1.5 }, fillcolor: '#ef4444' },
            yaxis: 'y'
        },
        {
            x: times,
            y: ema9,
            type: 'scatter',
            mode: 'lines',
            name: 'EMA 9',
            line: { color: '#c084fc', width: 1.5 },
            yaxis: 'y'
        },
        {
            x: times,
            y: ema20,
            type: 'scatter',
            mode: 'lines',
            name: 'EMA 20',
            line: { color: '#f43f5e', width: 1.5 },
            yaxis: 'y'
        }
    ];

    const shapes = [];
    const annotations = [];

    // Current Price Line & Badge (TradingView Yellow Line & Label)
    const curPx = data.current_price;
    const pxDecimals = curPx < 10 ? 5 : 2;
    shapes.push({
        type: 'line',
        xref: 'paper',
        x0: 0,
        x1: 1,
        y0: curPx,
        y1: curPx,
        line: { color: '#f59e0b', width: 1.3, dash: 'dot' }
    });
    annotations.push({
        xref: 'paper',
        x: 1.0,
        y: curPx,
        text: `<b>${curPx.toFixed(pxDecimals)}</b>`,
        showarrow: false,
        font: { color: '#000000', size: 11, family: 'monospace' },
        bgcolor: '#f59e0b',
        bordercolor: '#d97706',
        borderwidth: 1,
        borderpad: 3,
        xanchor: 'left'
    });

    // Detected Pattern Overlay
    if (data.detected_pattern) {
        const pat = data.detected_pattern;
        const pts = pat.points || {};

        if (pat.pattern_type === "ABCD Pattern" && pts.A && pts.B && pts.C) {
            traces.push({
                x: [pts.A.time, pts.B.time, pts.C.time, times[times.length - 1]],
                y: [pts.A.price, pts.B.price, pts.C.price, pat.target_2],
                type: 'scatter',
                mode: 'lines+markers+text',
                name: 'ABCD Legs',
                text: ['A (Low)', 'B (High)', 'C (Pullback)', 'D (Target)'],
                textposition: 'top center',
                line: { color: '#06b6d4', width: 2, dash: 'dot' },
                marker: { size: 8, color: '#22d3ee' }
            });
        }

        if (pat.pattern_type === "Bull Flag Momentum" && pts.pole_base && pts.pole_peak) {
            traces.push({
                x: [pts.pole_base.time, pts.pole_peak.time],
                y: [pts.pole_base.price, pts.pole_peak.price],
                type: 'scatter',
                mode: 'lines+text',
                name: 'Flag Pole',
                text: ['Base', 'Pole Peak'],
                line: { color: '#10b981', width: 3 }
            });
        }

        if (pat.pattern_type === "Consolidation Triangle") {
            const sup = pts.support || pts.rising_low;
            if (sup && isFinite(sup)) {
                shapes.push({
                    type: 'line',
                    xref: 'paper',
                    x0: 0.15,
                    x1: 1,
                    y0: sup,
                    y1: sup,
                    line: { color: '#06b6d4', width: 1.8, dash: 'dot' }
                });
                annotations.push({
                    xref: 'paper',
                    x: 0.15,
                    y: sup,
                    text: `Support ($${sup.toFixed(pxDecimals)})`,
                    showarrow: false,
                    font: { color: '#06b6d4', size: 10 },
                    bgcolor: '#083344'
                });
            }
            if (pts.resistance && isFinite(pts.resistance)) {
                shapes.push({
                    type: 'line',
                    xref: 'paper',
                    x0: 0.15,
                    x1: 1,
                    y0: pts.resistance,
                    y1: pts.resistance,
                    line: { color: '#f59e0b', width: 1.8, dash: 'dot' }
                });
                annotations.push({
                    xref: 'paper',
                    x: 0.15,
                    y: pts.resistance,
                    text: `Resistance ($${pts.resistance.toFixed(pxDecimals)})`,
                    showarrow: false,
                    font: { color: '#f59e0b', size: 10 },
                    bgcolor: '#451a03'
                });
            }
        }

        // Stop Loss Line
        shapes.push({
            type: 'line',
            xref: 'paper',
            x0: 0,
            x1: 1,
            y0: pat.stop_loss,
            y1: pat.stop_loss,
            line: { color: '#ef4444', width: 1.5, dash: 'dash' }
        });
        annotations.push({
            xref: 'paper',
            x: 0.98,
            y: pat.stop_loss,
            text: `Stop ($${pat.stop_loss.toFixed(pxDecimals)})`,
            showarrow: false,
            font: { color: '#ef4444', size: 10 },
            bgcolor: '#450a0a'
        });

        // Target 1 Line
        shapes.push({
            type: 'line',
            xref: 'paper',
            x0: 0,
            x1: 1,
            y0: pat.target_1,
            y1: pat.target_1,
            line: { color: '#10b981', width: 1.5, dash: 'dash' }
        });
        annotations.push({
            xref: 'paper',
            x: 0.98,
            y: pat.target_1,
            text: `T1 (50% Out) ($${pat.target_1.toFixed(pxDecimals)})`,
            showarrow: false,
            font: { color: '#10b981', size: 10 },
            bgcolor: '#064e3b'
        });

        // Target 2 Line
        shapes.push({
            type: 'line',
            xref: 'paper',
            x0: 0,
            x1: 1,
            y0: pat.target_2,
            y1: pat.target_2,
            line: { color: '#06b6d4', width: 1.5, dash: 'dot' }
        });
        annotations.push({
            xref: 'paper',
            x: 0.98,
            y: pat.target_2,
            text: `T2 ($${pat.target_2.toFixed(pxDecimals)})`,
            showarrow: false,
            font: { color: '#06b6d4', size: 10 },
            bgcolor: '#083344'
        });
    }

    const layout = {
        dragmode: currentDragMode,
        showlegend: false,
        paper_bgcolor: '#0b0f19',
        plot_bgcolor: '#0b0f19',
        margin: { l: 25, r: 70, t: 15, b: 30 },
        xaxis: {
            type: 'date',
            rangeslider: { visible: false },
            color: '#94a3b8',
            gridcolor: '#1e293b',
            linecolor: '#1e293b',
            range: currentXRange,
            autorange: false
        },
        yaxis: {
            color: '#94a3b8',
            gridcolor: '#1e293b',
            linecolor: '#1e293b',
            side: 'right',
            range: currentYRange,
            autorange: false
        },
        shapes: shapes,
        annotations: annotations
    };

    const configPlot = {
        responsive: true,
        scrollZoom: true,
        displayModeBar: false
    };

    Plotly.react('plotly-chart', traces, layout, configPlot);
    attachPlotlyEventListeners();
}

function attachPlotlyEventListeners() {
    const chartDiv = document.getElementById('plotly-chart');
    if (!chartDiv || chartDiv._chartEventsAttached) return;
    chartDiv._chartEventsAttached = true;

    chartDiv.on('plotly_relayout', (eventData) => {
        if (!eventData) return;
        if (eventData['xaxis.autorange'] || eventData['yaxis.autorange']) {
            autoAlignChart(true);
            return;
        }
        if (eventData['xaxis.range[0]'] !== undefined && eventData['xaxis.range[1]'] !== undefined) {
            isUserZoomed = true;
            currentXRange = [String(eventData['xaxis.range[0]']), String(eventData['xaxis.range[1]'])];
        } else if (eventData['xaxis.range'] !== undefined) {
            isUserZoomed = true;
            currentXRange = [String(eventData['xaxis.range'][0]), String(eventData['xaxis.range'][1])];
        }
        if (eventData['yaxis.range[0]'] !== undefined && eventData['yaxis.range[1]'] !== undefined) {
            isUserZoomed = true;
            currentYRange = [Number(eventData['yaxis.range[0]']), Number(eventData['yaxis.range[1]'])];
        } else if (eventData['yaxis.range'] !== undefined) {
            isUserZoomed = true;
            currentYRange = [Number(eventData['yaxis.range'][0]), Number(eventData['yaxis.range'][1])];
        }
    });

    chartDiv.on('plotly_doubleclick', () => {
        autoAlignChart(true);
    });
}

// 1. Auto-Align Chart (Guaranteed clean framing without falling back to 2000)
function autoAlignChart(force = true) {
    isUserZoomed = false;
    if (!currentAnalysis) return;
    const ranges = getAutoAlignedRanges(currentAnalysis);
    if (!ranges) return;
    currentXRange = ranges.xRange;
    currentYRange = ranges.yRange;

    Plotly.relayout('plotly-chart', {
        'xaxis.range': currentXRange,
        'yaxis.range': currentYRange,
        'xaxis.autorange': false,
        'yaxis.autorange': false
    });
}

// 2. Zoom In (Scale Chart In)
function zoomInChart() {
    if (!currentAnalysis || !currentXRange || !currentYRange) {
        autoAlignChart(true);
        return;
    }
    isUserZoomed = true;

    let t0 = safeParseTimestamp(currentXRange[0]);
    let t1 = safeParseTimestamp(currentXRange[1]);
    let y0 = Number(currentYRange[0]);
    let y1 = Number(currentYRange[1]);

    if (!t0 || !t1 || t1 <= t0 || !isFinite(y0) || !isFinite(y1)) {
        autoAlignChart(true);
        return;
    }

    const xSpan = t1 - t0;
    const newT0 = t0 + (xSpan * 0.15);
    const newT1 = t1 - (xSpan * 0.05);

    const ySpan = y1 - y0;
    const newY0 = y0 + (ySpan * 0.10);
    const newY1 = y1 - (ySpan * 0.10);

    const s0 = safeFormatDate(newT0);
    const s1 = safeFormatDate(newT1);

    if (s0 && s1) {
        currentXRange = [s0, s1];
        currentYRange = [newY0, newY1];
        Plotly.relayout('plotly-chart', {
            'xaxis.range': currentXRange,
            'yaxis.range': currentYRange,
            'xaxis.autorange': false,
            'yaxis.autorange': false
        });
    } else {
        autoAlignChart(true);
    }
}

// 3. Zoom Out (Scale Chart Out)
function zoomOutChart() {
    if (!currentAnalysis || !currentXRange || !currentYRange) {
        autoAlignChart(true);
        return;
    }
    isUserZoomed = true;

    let t0 = safeParseTimestamp(currentXRange[0]);
    let t1 = safeParseTimestamp(currentXRange[1]);
    let y0 = Number(currentYRange[0]);
    let y1 = Number(currentYRange[1]);

    if (!t0 || !t1 || t1 <= t0 || !isFinite(y0) || !isFinite(y1)) {
        autoAlignChart(true);
        return;
    }

    const xSpan = t1 - t0;
    const newT0 = t0 - (xSpan * 0.20);
    const newT1 = t1 + (xSpan * 0.10);

    const ySpan = y1 - y0;
    const newY0 = y0 - (ySpan * 0.12);
    const newY1 = y1 + (ySpan * 0.12);

    const s0 = safeFormatDate(newT0);
    const s1 = safeFormatDate(newT1);

    if (s0 && s1) {
        currentXRange = [s0, s1];
        currentYRange = [newY0, newY1];
        Plotly.relayout('plotly-chart', {
            'xaxis.range': currentXRange,
            'yaxis.range': currentYRange,
            'xaxis.autorange': false,
            'yaxis.autorange': false
        });
    } else {
        autoAlignChart(true);
    }
}

// 4. Toggle Pan / Drag Mode
function togglePanMode() {
    currentDragMode = (currentDragMode === 'pan') ? 'zoom' : 'pan';
    const panBtn = document.getElementById('btn-chart-pan');
    if (panBtn) {
        if (currentDragMode === 'pan') {
            panBtn.className = "w-7 h-7 rounded-lg bg-cyan-950/70 text-cyan-300 border border-cyan-600 flex items-center justify-center transition";
            panBtn.title = "Current: Pan/Drag Mode (Click for Box-Zoom)";
            panBtn.innerHTML = `<i class="fa-solid fa-hand"></i>`;
        } else {
            panBtn.className = "w-7 h-7 rounded-lg bg-slate-800 text-slate-300 border border-slate-700 flex items-center justify-center transition";
            panBtn.title = "Current: Box-Zoom Mode (Click for Pan/Drag)";
            panBtn.innerHTML = `<i class="fa-solid fa-magnifying-glass"></i>`;
        }
    }
    Plotly.relayout('plotly-chart', { dragmode: currentDragMode });
}

// 5. Toggle Fullscreen Mode
function toggleFullscreen() {
    const container = document.getElementById('chart-card-container');
    const fsIcon = document.getElementById('fs-icon');
    const fsText = document.getElementById('fs-text');
    const fsBtn = document.getElementById('btn-chart-fullscreen');

    isFullscreen = !isFullscreen;

    if (isFullscreen) {
        container.classList.add('chart-fullscreen-overlay');
        if (fsIcon) fsIcon.className = "fa-solid fa-compress";
        if (fsText) fsText.innerText = "Exit";
        if (fsBtn) fsBtn.className = "px-2.5 py-1.5 rounded-lg bg-rose-950/80 hover:bg-rose-900 text-rose-300 border border-rose-600 flex items-center gap-1.5 font-bold transition cursor-pointer";
        
        // Also try native Fullscreen API if available
        if (container.requestFullscreen && !document.fullscreenElement) {
            container.requestFullscreen().catch(() => {});
        }
    } else {
        container.classList.remove('chart-fullscreen-overlay');
        if (fsIcon) fsIcon.className = "fa-solid fa-expand";
        if (fsText) fsText.innerText = "Fullscreen";
        if (fsBtn) fsBtn.className = "px-2.5 py-1.5 rounded-lg bg-purple-950/70 hover:bg-purple-900/90 text-purple-300 border border-purple-700/60 flex items-center gap-1.5 font-bold transition cursor-pointer";
        
        if (document.fullscreenElement && document.exitFullscreen) {
            document.exitFullscreen().catch(() => {});
        }
    }

    setTimeout(() => {
        Plotly.Plots.resize('plotly-chart');
        autoAlignChart(true);
    }, 150);
}

// Document native fullscreen change listener
document.addEventListener("fullscreenchange", () => {
    if (!document.fullscreenElement && isFullscreen) {
        toggleFullscreen();
    }
});

async function runCalibration() {
    const btn = document.getElementById("btn-calibrate-now");
    const originalText = btn.innerHTML;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Calibrating & Training Model...`;
    btn.disabled = true;

    try {
        const res = await fetch("/api/calibrate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ symbol: currentSymbol, timeframe: currentTimeframe })
        });
        const result = await res.json();
        if (result.status === "success") {
            btn.innerHTML = `<i class="fa-solid fa-check text-emerald-400"></i> Calibrated & Trained!`;
            setTimeout(() => {
                btn.innerHTML = originalText;
                btn.disabled = false;
            }, 2500);
            fetchAnalysis();
            fetchAutoTrainerStatus();
        }
    } catch (e) {
        console.error("Calibration failed:", e);
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

// Autonomous Training Engine Client Controls
async function fetchAutoTrainerStatus() {
    try {
        const res = await fetch("/api/auto-trainer/status");
        if (!res.ok) return;
        const status = await res.json();
        renderAutoTrainerHUD(status);
    } catch (e) {
        console.warn("Auto-trainer status check:", e);
    }
}

function renderAutoTrainerHUD(status) {
    if (!status) return;

    // 1. Toggle Button & Dot
    const toggleBtn = document.getElementById("btn-toggle-autotrain");
    const statusText = document.getElementById("autotrain-status-text");
    const dot = document.getElementById("autotrain-dot");
    const statusPill = document.getElementById("autotrain-status-pill");
    const lastInfo = document.getElementById("autotrain-last-info");

    if (toggleBtn && statusText && dot) {
        if (status.enabled) {
            toggleBtn.className = "px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-emerald-950/80 text-emerald-400 border border-emerald-600/70 hover:bg-emerald-900 transition flex items-center gap-1 cursor-pointer";
            statusText.innerText = "Auto-Train: ON";
            dot.className = "w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse";
        } else {
            toggleBtn.className = "px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-slate-800 text-slate-400 border border-slate-700 hover:bg-slate-700 transition flex items-center gap-1 cursor-pointer";
            statusText.innerText = "Auto-Train: PAUSED";
            dot.className = "w-1.5 h-1.5 rounded-full bg-slate-500";
        }
    }

    // 2. Training Activity Pill
    if (statusPill) {
        if (status.is_training_now) {
            const sym = (status.current_symbol || "Asset").replace('=X', '');
            statusPill.innerHTML = `<span class="text-amber-400 font-bold"><i class="fa-solid fa-spinner fa-spin mr-1"></i> Training ${sym}...</span>`;
        } else if (!status.enabled) {
            statusPill.innerHTML = `<span class="text-slate-400 font-mono">Paused (Manual Only)</span>`;
        } else {
            const hours = status.retrain_interval_hours || 6;
            statusPill.innerHTML = `<span class="text-emerald-400 font-mono font-semibold">Active (Every ${hours}h)</span>`;
        }
    }

    // 3. Last Trained Profile Info
    if (lastInfo) {
        if (status.recent_runs && status.recent_runs.length > 0) {
            const last = status.recent_runs[0];
            const cleanSym = (last.symbol || "").replace('=X', '');
            const winRate = last.high_confidence_win_rate ? `${last.high_confidence_win_rate}% Win` : `${last.base_win_rate}% Win`;
            lastInfo.innerText = `${cleanSym}: ${last.samples} trades (${winRate})`;
            lastInfo.title = `Trained at: ${last.trained_at || 'Recently'} (Duration: ${last.duration_seconds}s)`;
        } else if (status.models && status.models[currentSymbol] && status.models[currentSymbol].is_trained) {
            const m = status.models[currentSymbol];
            const cleanSym = currentSymbol.replace('=X', '');
            lastInfo.innerText = `${cleanSym}: ${m.samples} trades (${m.win_rate}% Win)`;
        }
    }
}

async function toggleAutoTrainer() {
    try {
        const toggleBtn = document.getElementById("btn-toggle-autotrain");
        const isCurrentlyOn = toggleBtn ? toggleBtn.innerText.includes("ON") : true;
        const newTarget = !isCurrentlyOn;

        const res = await fetch("/api/auto-trainer/toggle", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ enabled: newTarget })
        });
        const data = await res.json();
        fetchAutoTrainerStatus();
    } catch (e) {
        console.error("Toggle auto-trainer failed:", e);
    }
}

async function triggerTrainAllAssets() {
    const btn = document.getElementById("btn-train-all-assets");
    if (!btn) return;
    const originalText = btn.innerHTML;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Queuing...`;
    btn.disabled = true;

    try {
        const res = await fetch("/api/auto-trainer/train-now", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ symbol: "ALL", force: true })
        });
        const data = await res.json();
        btn.innerHTML = `<i class="fa-solid fa-check text-emerald-400"></i> Queued (BG)`;
        setTimeout(fetchAutoTrainerStatus, 1000);
        setTimeout(() => {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }, 2500);
    } catch (e) {
        console.error("Trigger retrain all failed:", e);
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

// News Alert & Economic Calendar Engine (Andrew Elder Ch 4)
async function fetchNewsStatus() {
    try {
        const res = await fetch(`/api/news/status?symbol=${encodeURIComponent(currentSymbol)}`);
        if (!res.ok) return;
        const data = await res.json();
        renderNewsHUD(data);
    } catch (e) {
        console.warn("News status check:", e);
    }
}

function renderNewsHUD(newsData) {
    if (!newsData) return;

    const banner = document.getElementById("news-alert-banner");
    const badge = document.getElementById("news-alert-badge");
    const dot = document.getElementById("news-alert-dot");
    const badgeText = document.getElementById("news-alert-badge-text");
    const headline = document.getElementById("news-alert-headline");
    const lockBtn = document.getElementById("btn-toggle-newslock");
    const lockText = document.getElementById("newslock-text");
    const simBtnText = document.getElementById("btn-simulate-news-text");
    const simBtn = document.getElementById("btn-simulate-news");

    // Lockout Switch State
    if (lockBtn && lockText) {
        if (newsData.lockout_enabled) {
            lockBtn.className = "px-2.5 py-1 rounded text-[11px] font-medium bg-emerald-950/80 text-emerald-400 border border-emerald-700/60 hover:bg-emerald-900 transition flex items-center gap-1 cursor-pointer";
            lockText.innerText = "News Skip: ON";
        } else {
            lockBtn.className = "px-2.5 py-1 rounded text-[11px] font-medium bg-slate-800 text-slate-400 border border-slate-700 hover:bg-slate-700 transition flex items-center gap-1 cursor-pointer";
            lockText.innerText = "News Skip: OFF";
        }
    }

    // Simulation Button State
    if (simBtnText && simBtn) {
        if (newsData.is_simulated) {
            simBtn.className = "px-2.5 py-1 rounded text-[11px] font-bold bg-rose-900/90 hover:bg-rose-800 text-rose-200 border border-rose-600 transition flex items-center gap-1 cursor-pointer";
            simBtnText.innerText = "Clear Simulated Shock";
        } else {
            simBtn.className = "px-2.5 py-1 rounded text-[11px] font-medium bg-slate-800 hover:bg-slate-700 text-amber-300 border border-slate-700 transition flex items-center gap-1 cursor-pointer";
            simBtnText.innerText = "Simulate News Event";
        }
    }

    // Blackout Alert Banner
    if (banner && badge && dot && badgeText && headline) {
        if (newsData.is_blackout) {
            banner.className = "bg-rose-950/90 border-b border-rose-700 px-6 py-2 transition-all duration-300 shadow-lg";
            badge.className = "px-2.5 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider bg-rose-900/90 text-rose-200 flex items-center gap-1.5 border border-rose-500 animate-pulse";
            dot.className = "w-2 h-2 rounded-full bg-rose-400 animate-ping";
            badgeText.innerText = "🚨 HIGH-IMPACT NEWS BLACKOUT";

            const ev = newsData.active_event;
            const evTitle = ev ? ev.title : "High-Impact Economic Release";
            const evStatus = ev ? ev.status : "Active";
            headline.innerHTML = `<span class="text-rose-200 font-bold">${evTitle}</span> • <span class="text-rose-300 font-mono">${evStatus}</span> • <span class="text-white underline">Automated signals SKIPPED to protect capital</span>`;
        } else {
            banner.className = "bg-slate-950 border-b border-slate-800 px-6 py-2 transition-all duration-300";
            badge.className = "px-2.5 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider bg-slate-800 text-slate-300 flex items-center gap-1.5 border border-slate-700";
            dot.className = "w-2 h-2 rounded-full bg-emerald-400";
            badgeText.innerText = "News: Calm";

            if (newsData.upcoming_events && newsData.upcoming_events.length > 0) {
                const nextEv = newsData.upcoming_events[0];
                headline.innerHTML = `Economic conditions clear for <strong class="text-white">${currentSymbol.replace('=X', '')}</strong>. Next event: <span class="text-cyan-300 font-medium">${nextEv.title} (${nextEv.countdown})</span>`;
            } else {
                headline.innerText = `Economic conditions clear for ${currentSymbol.replace('=X', '')}. No high-impact releases imminent.`;
            }
        }
    }

    // Populate Calendar Drawer
    const calList = document.getElementById("news-calendar-list");
    if (calList && newsData.upcoming_events) {
        calList.innerHTML = newsData.upcoming_events.map(ev => {
            const isHigh = ev.impact === "HIGH";
            const impactColor = isHigh ? "bg-rose-950/80 text-rose-300 border-rose-700" : "bg-amber-950/80 text-amber-300 border-amber-700";
            const blackoutBorder = ev.in_blackout ? "border-rose-500 bg-rose-950/30" : "border-slate-800 bg-slate-900/60";
            return `
                <div class="p-2.5 rounded-lg border ${blackoutBorder} flex flex-col justify-between text-[11px]">
                    <div class="flex justify-between items-start gap-1 mb-1">
                        <span class="font-bold text-white leading-tight">${ev.title}</span>
                        <span class="px-1.5 py-0.5 rounded text-[10px] font-bold border ${impactColor}">${ev.currency} • ${ev.impact}</span>
                    </div>
                    <div class="flex justify-between items-center text-slate-400 text-[10px] pt-1 border-t border-slate-800/60">
                        <span class="font-mono text-cyan-300">${ev.countdown}</span>
                        <span class="text-slate-500">${ev.scheduled_time.split(' ')[1].substring(0, 5)} Local</span>
                    </div>
                </div>
            `;
        }).join('');
    }
}

async function toggleNewsLockout() {
    try {
        const lockText = document.getElementById("newslock-text");
        const isCurrentlyOn = lockText ? lockText.innerText.includes("ON") : true;
        const newTarget = !isCurrentlyOn;

        const res = await fetch("/api/news/toggle", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ enabled: newTarget })
        });
        const data = await res.json();
        fetchNewsStatus();
        fetchAnalysis();
    } catch (e) {
        console.error("Toggle news lockout failed:", e);
    }
}

async function toggleNewsSimulation() {
    const simBtnText = document.getElementById("btn-simulate-news-text");
    const isSimulated = simBtnText && simBtnText.innerText.includes("Clear");

    try {
        if (isSimulated) {
            await fetch("/api/news/simulate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ action: "clear" })
            });
        } else {
            await fetch("/api/news/simulate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    action: "start",
                    title: "US Non-Farm Payrolls (NFP) Shock Alert",
                    duration_minutes: 15,
                    currency: "USD"
                })
            });
        }
        fetchNewsStatus();
        fetchAnalysis();
    } catch (e) {
        console.error("Toggle news simulation failed:", e);
    }
}

function toggleNewsDrawer() {
    const drawer = document.getElementById("news-calendar-drawer");
    const arrow = document.getElementById("news-drawer-arrow");
    if (!drawer) return;

    const isHidden = drawer.classList.contains("hidden");
    if (isHidden) {
        drawer.classList.remove("hidden");
        if (arrow) arrow.className = "fa-solid fa-chevron-up text-[10px]";
    } else {
        drawer.classList.add("hidden");
        if (arrow) arrow.className = "fa-solid fa-chevron-down text-[10px]";
    }
}

async function executeCurrentSignal() {
    if (!currentAnalysis || !currentAnalysis.trade_signal) return;
    const sig = currentAnalysis.trade_signal;

    try {
        const res = await fetch("/api/execute-trade", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                symbol: sig.symbol,
                action: sig.action,
                entry_price: sig.entry_price,
                stop_loss: sig.stop_loss,
                target_1: sig.target_1,
                target_2: sig.target_2,
                position_size: sig.position_size,
                pattern: sig.pattern
            })
        });
        const data = await res.json();
        if (data.status === "opened") {
            playSignalChime(sig.action === "BUY");
            alert(`Live Trade Position Opened!\nSymbol: ${sig.symbol}\nSide: ${sig.action}\nEntry: $${sig.entry_price}\nSize: ${sig.units_label}\nStop: $${sig.stop_loss}`);
            fetchBrokerStatus();
        } else {
            alert(`Trade Blocked: ${data.reason}`);
        }
    } catch (err) {
        console.error("Trade execution failed:", err);
    }
}

async function fetchBrokerStatus() {
    try {
        const res = await fetch("/api/broker");
        const data = await res.json();
        renderBrokerHUD(data);
    } catch (e) {
        console.error("Broker status error:", e);
    }
}

async function fetchScreener() {
    try {
        const res = await fetch("/api/screener");
        const data = await res.json();
        const tbody = document.getElementById("screener-table-body");

        if (!data.items || data.items.length === 0) {
            tbody.innerHTML = `<tr><td colspan="9" class="p-4 text-center text-slate-500">No Apex candidates detected at present.</td></tr>`;
            return;
        }

        tbody.innerHTML = data.items.map(item => `
            <tr class="hover:bg-slate-800/40">
                <td class="p-2.5 font-bold text-white">${item.symbol}</td>
                <td class="p-2.5 text-slate-300">${item.name}</td>
                <td class="p-2.5 font-mono">$${item.price}</td>
                <td class="p-2.5 font-bold ${item.rvol >= 2.0 ? 'text-emerald-400' : 'text-slate-300'}">${item.rvol}x</td>
                <td class="p-2.5 text-cyan-300">${item.atr_pct}%</td>
                <td class="p-2.5 ${item.trend_bias === 'BULLISH' ? 'text-emerald-400' : 'text-rose-400'} font-bold">${item.trend_bias}</td>
                <td class="p-2.5 font-bold text-purple-400">${item.predator_score}</td>
                <td class="p-2.5"><span class="px-2 py-0.5 rounded text-[10px] ${item.status.includes('HIGH') ? 'bg-emerald-950 text-emerald-400 border border-emerald-700' : 'bg-slate-800 text-slate-300'}">${item.status}</span></td>
                <td class="p-2.5 text-right">
                    <button onclick="switchSymbol('${item.symbol}')" class="text-xs bg-slate-800 hover:bg-slate-700 text-cyan-300 px-2 py-1 rounded border border-slate-700">
                        Analyze
                    </button>
                </td>
            </tr>
        `).join('');
    } catch (e) {
        console.error("Screener fetch error:", e);
    }
}

async function fetchJournal() {
    try {
        const res = await fetch("/api/journal");
        const data = await res.json();
        const a = data.analysis;

        document.getElementById("journal-hit-rate").innerText = `${a.hit_rate_pct}% (${a.win_count}W / ${a.loss_count}L)`;
        document.getElementById("journal-payout-ratio").innerText = `${a.payout_ratio.toFixed(2)} (Target >= 2.0)`;
        document.getElementById("journal-profit-factor").innerText = `${a.profit_factor.toFixed(2)}`;
        const netSpan = document.getElementById("journal-net-pnl");
        netSpan.innerText = `$${a.net_pnl.toFixed(2)}`;
        netSpan.className = a.net_pnl >= 0 ? "text-base font-bold text-emerald-400 font-mono" : "text-base font-bold text-rose-400 font-mono";

        const warnBox = document.getElementById("journal-warnings-box");
        if (a.elder_warnings && a.elder_warnings.length > 0) {
            warnBox.classList.remove("hidden");
            warnBox.innerHTML = `<strong><i class="fa-solid fa-triangle-exclamation mr-1"></i> Elder Discipline Check:</strong><ul class="list-disc list-inside mt-1">${a.elder_warnings.map(w => `<li>${w}</li>`).join('')}</ul>`;
        } else {
            warnBox.classList.add("hidden");
        }

        const tbody = document.getElementById("journal-table-body");
        if (!data.trades || data.trades.length === 0) {
            tbody.innerHTML = `<tr><td colspan="10" class="p-4 text-center text-slate-500">No journal logs recorded yet. Complete paper trades to populate stats.</td></tr>`;
            return;
        }

        tbody.innerHTML = data.trades.map(t => `
            <tr class="hover:bg-slate-800/40">
                <td class="p-2.5 text-slate-400">${t.entry_time}</td>
                <td class="p-2.5 font-bold text-white">${t.symbol}</td>
                <td class="p-2.5 ${t.direction === 'BULLISH' ? 'text-emerald-400' : 'text-rose-400'} font-bold">${t.direction === 'BULLISH' ? 'BUY' : 'SELL'}</td>
                <td class="p-2.5 text-slate-300">${t.pattern}</td>
                <td class="p-2.5">$${t.entry_price.toFixed(t.entry_price < 10 ? 5 : 2)}</td>
                <td class="p-2.5">$${t.exit_price ? t.exit_price.toFixed(t.exit_price < 10 ? 5 : 2) : '--'}</td>
                <td class="p-2.5 font-bold ${t.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}">$${t.pnl.toFixed(2)}</td>
                <td class="p-2.5 ${t.pnl_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}">${t.pnl_pct.toFixed(2)}%</td>
                <td class="p-2.5 text-slate-400">${t.reasons_for_exit || '--'}</td>
                <td class="p-2.5 text-cyan-300">${t.mental_state_entry || '--'}</td>
            </tr>
        `).join('');
    } catch (e) {
        console.error("Journal fetch error:", e);
    }
}
