const socket = io();

let appState = {
    mode: 'DEMO',
    demoBalance: 1000.00,
    liveBalance: 0.00,
    status: 'WAITING',
    currentMultiplier: 1.00
};

let betPanel1 = { amount: 10.00, status: 'NONE', cashoutMultiplier: 0 };
let betPanel2 = { amount: 20.00, status: 'NONE', cashoutMultiplier: 0 };

let canvas, ctx, particles = [];

function initCanvas() {
    canvas = document.getElementById('flightCanvas');
    if (!canvas) return;
    ctx = canvas.getContext('2d');
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
}

function resizeCanvas() {
    if (!canvas) return;
    canvas.width = canvas.getBoundingClientRect().width;
    canvas.height = canvas.getBoundingClientRect().height;
}

class Particle {
    constructor(x, y, color) {
        this.x = x; 
        this.y = y;
        this.vx = (Math.random() - 0.5) * 4 - 3;
        this.vy = (Math.random() - 0.5) * 3 + 1;
        this.size = Math.random() * 4 + 2;
        this.color = color; 
        this.alpha = 1; 
        this.life = Math.random() * 20 + 20;
    }
    update() { 
        this.x += this.vx; 
        this.y += this.vy; 
        this.alpha -= 1 / this.life; 
    }
    draw(ctx) {
        ctx.save(); 
        ctx.globalAlpha = Math.max(0, this.alpha);
        ctx.fillStyle = this.color; 
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2); 
        ctx.fill(); 
        ctx.restore();
    }
}

function drawJet(ctx, x, y) {
    ctx.save(); 
    ctx.translate(x, y); 
    ctx.rotate(-Math.PI / 10);

    // Engine Afterburner Glow
    ctx.fillStyle = '#f59e0b';
    ctx.beginPath();
    ctx.arc(-22, 1, 6 + Math.random() * 3, 0, Math.PI * 2);
    ctx.fill();

    // Fuselage Body
    ctx.fillStyle = '#e11d48';
    ctx.beginPath();
    ctx.moveTo(30, 0);
    ctx.quadraticCurveTo(12, -7, -20, -5);
    ctx.lineTo(-24, 5);
    ctx.quadraticCurveTo(12, 7, 30, 0);
    ctx.closePath();
    ctx.fill();

    // Top Wing
    ctx.fillStyle = '#be123c';
    ctx.beginPath();
    ctx.moveTo(5, -2);
    ctx.lineTo(-12, -22);
    ctx.lineTo(-18, -2);
    ctx.closePath();
    ctx.fill();

    // Bottom Wing
    ctx.beginPath();
    ctx.moveTo(5, 2);
    ctx.lineTo(-12, 18);
    ctx.lineTo(-18, 2);
    ctx.closePath();
    ctx.fill();

    // Cockpit Window
    ctx.fillStyle = '#38bdf8';
    ctx.beginPath();
    ctx.ellipse(10, -2, 7, 3, Math.PI / 8, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
}

function renderCanvas() {
    if (!ctx || !canvas) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const w = canvas.width, h = canvas.height;

    if (appState.status === 'IN_FLIGHT') {
        const progress = Math.min((appState.currentMultiplier - 1) / 10, 1);
        const currentX = 40 + (w * 0.8 - 40) * Math.min(progress, 1);
        const currentY = (h - 40) - ((h - 40) - h * 0.25) * Math.min(Math.pow(progress, 0.75), 1);

        // Flight trajectory curve
        ctx.save(); 
        ctx.beginPath(); 
        ctx.moveTo(40, h - 40);
        ctx.quadraticCurveTo(40 + (currentX - 40) * 0.5, h - 40, currentX, currentY);
        ctx.strokeStyle = '#e11d48'; 
        ctx.lineWidth = 5; 
        ctx.lineCap = 'round';
        ctx.stroke(); 
        ctx.restore();

        // Particles
        if (Math.random() < 0.7) {
            particles.push(new Particle(currentX - 18, currentY + 2, '#fb7185'));
            particles.push(new Particle(currentX - 22, currentY + 2, '#f59e0b'));
        }

        particles.forEach((p, idx) => { 
            p.update(); 
            p.draw(ctx); 
            if (p.alpha <= 0) particles.splice(idx, 1); 
        });

        drawJet(ctx, currentX, currentY);
    }
    requestAnimationFrame(renderCanvas);
}

function updateBalanceDisplay() {
    const balEl = document.getElementById('userBalance');
    const labelEl = document.getElementById('balanceLabel');
    const modeBadge = document.getElementById('modeBadge');
    const modeText = document.getElementById('modeText');

    if (!balEl || !labelEl || !modeBadge || !modeText) return;

    modeText.innerText = appState.mode;
    if (appState.mode === 'DEMO') {
        labelEl.innerText = 'Demo Balance';
        balEl.innerText = `$${appState.demoBalance.toFixed(2)}`;
        modeBadge.className = 'w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse';
        modeText.className = 'text-xs font-bold text-amber-400 uppercase';
    } else {
        labelEl.innerText = 'Live Balance';
        balEl.innerText = `$${appState.liveBalance.toFixed(2)}`;
        modeBadge.className = 'w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse';
        modeText.className = 'text-xs font-bold text-emerald-400 uppercase';
    }
}

function renderHistory(history) {
    if (!history) return;
    let html = '';
    history.forEach(val => {
        let badgeClass = val >= 2.0 ? 'bg-purple-950/80 text-purple-300 border-purple-500/40' : 'bg-slate-800 text-sky-400 border-sky-500/30';
        html += `<span class="px-2.5 py-1 rounded-lg text-xs font-bold border ${badgeClass}">${val.toFixed(2)}x</span>`;
    });
    const hBar = document.getElementById('historyBar');
    const hBarMob = document.getElementById('historyBarMobile');
    if (hBar) hBar.innerHTML = html;
    if (hBarMob) hBarMob.innerHTML = html;
}

function updateLiveBetsTable(players) {
    const tableBody = document.getElementById('liveBetsTable');
    const countEl = document.getElementById('liveBetCount');
    if (!tableBody || !countEl) return;

    countEl.innerText = `${players ? players.length : 0} Bets`;
    if (!players || players.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="5" class="p-4 text-center text-slate-500 italic">Waiting for bets...</td></tr>`;
        return;
    }
    let html = '';
    players.forEach(p => {
        const isCash = p.status === 'CASHED_OUT';
        html += `<tr class="border-b border-slate-800/40">
            <td class="p-2.5 font-bold">${p.phone}</td>
            <td class="p-2.5"><span class="text-[10px] px-1.5 py-0.5 rounded ${p.mode==='LIVE'?'bg-emerald-950 text-emerald-400 border border-emerald-800/50':'bg-amber-950 text-amber-400 border border-amber-800/50'}">${p.mode}</span></td>
            <td class="p-2.5 font-mono">$${p.amount.toFixed(2)}</td>
            <td class="p-2.5 font-bold ${isCash ? 'text-emerald-400' : 'text-slate-400'}">${isCash ? p.cashout_multiplier.toFixed(2) + 'x' : '-'}</td>
            <td class="p-2.5 text-right font-mono font-bold ${isCash ? 'text-emerald-400' : 'text-slate-500'}">${isCash ? '+$' + p.win_amount.toFixed(2) : '-'}</td>
        </tr>`;
    });
    tableBody.innerHTML = html;
}

function fetchUserInfo() {
    fetch('/api/user_info')
        .then(r => r.json())
        .then(d => {
            if (d && d.live_balance !== undefined) {
                appState.liveBalance = parseFloat(d.live_balance);
                updateBalanceDisplay();
            }
        })
        .catch(err => console.error("Error fetching user info:", err));
}

function updateActionButtonsUI() {
    [1, 2].forEach(pNum => {
        const panel = pNum === 1 ? betPanel1 : betPanel2;
        const btn = document.getElementById(`actionBtn${pNum}`);
        const textEl = document.getElementById(`actionText${pNum}`);
        const subtextEl = document.getElementById(`actionSubtext${pNum}`);

        if (!btn || !textEl || !subtextEl) return;

        if (panel.status === 'NONE') {
            btn.className = 'w-full h-16 rounded-xl font-black text-base uppercase bg-emerald-600 hover:bg-emerald-500 text-white transition cursor-pointer';
            textEl.innerText = 'PLACE BET';
            subtextEl.innerText = `${panel.amount.toFixed(2)} USD`;
        } else if (panel.status === 'IN_GAME') {
            if (appState.status === 'IN_FLIGHT') {
                btn.className = 'w-full h-16 rounded-xl font-black text-base uppercase bg-amber-400 hover:bg-amber-300 text-slate-950 animate-pulse transition cursor-pointer';
                textEl.innerText = 'CASH OUT';
                subtextEl.innerText = `$${(panel.amount * appState.currentMultiplier).toFixed(2)} USD`;
            } else {
                btn.className = 'w-full h-16 rounded-xl font-black text-base bg-emerald-700/60 text-white transition cursor-not-allowed';
                textEl.innerText = 'BET ACCEPTED';
                subtextEl.innerText = 'Waiting for flight...';
            }
        }
    });
}

function handlePanelAction(panelId) {
    const panel = panelId === 1 ? betPanel1 : betPanel2;
    const betInput = document.getElementById(`betAmount${panelId}`);
    const autoToggle = document.getElementById(`autoCashoutToggle${panelId}`);
    const autoRateInput = document.getElementById(`autoCashoutRate${panelId}`);

    if (!betInput) return;
    const amount = parseFloat(betInput.value) || 0;
    if (amount <= 0) return;

    if (panel.status === 'NONE') {
        socket.emit('place_bet', {
            panel_id: panelId,
            amount: amount,
            mode: appState.mode,
            auto_enabled: autoToggle ? autoToggle.checked : false,
            auto_rate: autoRateInput ? (parseFloat(autoRateInput.value) || 2.00) : 2.00
        });
    } else if (panel.status === 'IN_GAME' && appState.status === 'IN_FLIGHT') {
        socket.emit('manual_cashout', { panel_id: panelId });
    }
}

function setupEventListeners() {
    // Mode Switch Button
    const modeBtn = document.getElementById('modeToggleBtn');
    if (modeBtn) {
        modeBtn.addEventListener('click', () => {
            appState.mode = appState.mode === 'DEMO' ? 'LIVE' : 'DEMO';
            if (appState.mode === 'LIVE') {
                fetchUserInfo();
            } else {
                updateBalanceDisplay();
            }
        });
    }

    // Reset Balance
    const depositBtn = document.getElementById('depositBtn');
    if (depositBtn) {
        depositBtn.addEventListener('click', () => {
            if (appState.mode === 'DEMO') {
                appState.demoBalance = 1000.00;
                updateBalanceDisplay();
            } else {
                fetchUserInfo();
            }
        });
    }

    // Panel Inputs & Quick Presets
    [1, 2].forEach(pNum => {
        const toggle = document.getElementById(`autoCashoutToggle${pNum}`);
        const rateInput = document.getElementById(`autoCashoutRate${pNum}`);
        const betInput = document.getElementById(`betAmount${pNum}`);

        if (toggle && rateInput) {
            toggle.addEventListener('change', (e) => {
                rateInput.disabled = !e.target.checked;
                rateInput.classList.toggle('opacity-50', !e.target.checked);
            });
        }

        if (betInput) {
            betInput.addEventListener('input', (e) => {
                const val = parseFloat(e.target.value) || 0;
                if (pNum === 1) betPanel1.amount = val;
                else betPanel2.amount = val;
                updateActionButtonsUI();
            });
        }

        document.querySelectorAll(`.quick-preset-${pNum}`).forEach(btn => {
            btn.addEventListener('click', () => {
                const addVal = parseFloat(btn.getAttribute('data-val')) || 0;
                const currentVal = parseFloat(betInput ? betInput.value : 0) || 0;
                const newVal = currentVal + addVal;
                if (betInput) betInput.value = newVal.toFixed(2);
                if (pNum === 1) betPanel1.amount = newVal;
                else betPanel2.amount = newVal;
                updateActionButtonsUI();
            });
        });
    });

    // Place Bet / Cash Out Buttons
    const actionBtn1 = document.getElementById('actionBtn1');
    if (actionBtn1) {
        actionBtn1.addEventListener('click', () => handlePanelAction(1));
    }

    const actionBtn2 = document.getElementById('actionBtn2');
    if (actionBtn2) {
        actionBtn2.addEventListener('click', () => handlePanelAction(2));
    }
}

// Socket Listeners
socket.on('round_waiting', (data) => {
    appState.status = 'WAITING';
    
    const countBox = document.getElementById('countdownBox');
    const multBox = document.getElementById('multiplierBox');
    const crashBox = document.getElementById('crashedBox');
    const countText = document.getElementById('countdownText');

    if (countBox) countBox.classList.remove('hidden');
    if (multBox) multBox.classList.add('hidden');
    if (crashBox) crashBox.classList.add('hidden');
    if (countText) countText.innerText = data.countdown.toFixed(1);
    
    const circle = document.getElementById('countdownCircle');
    if (circle) {
        const offset = 251.2 - (data.countdown / 5.0) * 251.2;
        circle.style.strokeDashoffset = offset;
    }

    updateActionButtonsUI();
});

socket.on('multiplier_update', (data) => {
    appState.status = 'IN_FLIGHT';
    appState.currentMultiplier = data.multiplier;

    const countBox = document.getElementById('countdownBox');
    const multBox = document.getElementById('multiplierBox');
    const multText = document.getElementById('multiplierText');

    if (countBox) countBox.classList.add('hidden');
    if (multBox) multBox.classList.remove('hidden');
    if (multText) multText.innerText = `${data.multiplier.toFixed(2)}x`;

    if (data.players) updateLiveBetsTable(data.players);
    updateActionButtonsUI();
});

socket.on('round_crashed', (data) => {
    appState.status = 'CRASHED';

    const multBox = document.getElementById('multiplierBox');
    const crashBox = document.getElementById('crashedBox');
    const crashedAtText = document.getElementById('crashedAtText');

    if (multBox) multBox.classList.add('hidden');
    if (crashBox) crashBox.classList.remove('hidden');
    if (crashedAtText) crashedAtText.innerText = `${data.crash_point.toFixed(2)}x`;

    renderHistory(data.history);
    
    betPanel1.status = 'NONE';
    betPanel2.status = 'NONE';
    updateActionButtonsUI();
});

socket.on('bet_accepted', (data) => {
    const panel = data.panel_id === 1 ? betPanel1 : betPanel2;
    panel.status = 'IN_GAME';
    if (data.mode === 'LIVE' && data.new_balance !== null) {
        appState.liveBalance = data.new_balance;
    } else if (data.mode === 'DEMO') {
        appState.demoBalance -= data.amount;
    }
    updateBalanceDisplay();
    updateActionButtonsUI();
});

socket.on('cashout_success', (data) => {
    const panel = data.panel_id === 1 ? betPanel1 : betPanel2;
    panel.status = 'NONE';
    panel.cashoutMultiplier = data.multiplier;
    if (data.mode === 'LIVE' && data.new_balance !== null) {
        appState.liveBalance = data.new_balance;
    } else if (data.mode === 'DEMO') {
        appState.demoBalance += data.win_amount;
    }
    updateBalanceDisplay();
    updateActionButtonsUI();
});

socket.on('live_bets_update', (data) => { 
    updateLiveBetsTable(data.players); 
});

// Run once the entire DOM finishes loading
document.addEventListener('DOMContentLoaded', () => {
    initCanvas();
    renderCanvas();
    setupEventListeners();
    fetchUserInfo();
    updateBalanceDisplay();
    updateActionButtonsUI();
});