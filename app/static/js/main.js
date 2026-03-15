// --- Session Management ---
// Generate a unique Session ID and store it in the browser's Session Storage.
// It resets when the user completely closes the browser tab.
let sessionId = sessionStorage.getItem('alphapulse_session');
if (!sessionId) {
    sessionId = 'sess_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
    sessionStorage.setItem('alphapulse_session', sessionId);
}
console.log("Current AlphaPulse Session ID:", sessionId);

// --- Live Market Status ---
async function fetchMarketStatus() {
    try {
        const res = await fetch('/api/v1/market-status');
        const data = await res.json();
        
        // Update Navbar Status
        const statusEl = document.getElementById('market-status');
        if (data.is_open) {
            statusEl.innerHTML = '<span class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span> Market Open';
        } else {
            statusEl.innerHTML = '<span class="w-2 h-2 rounded-full bg-red-500"></span> Market Closed';
        }
        
        // Update 3D Wireframe Trend
        renderWireframe(data.is_bull);
    } catch (e) {
        console.error("Failed to fetch market status");
    }
}
fetchMarketStatus(); // Run on load

// --- 1. 3D Wireframe Bull/Bear Engine ---
function renderWireframe(isBull) {
    const container = document.getElementById('trend-indicator');
    const color = isBull ? 'text-green-400' : 'text-red-500';
    const shadowColor = isBull ? 'rgba(74, 222, 128, 0.6)' : 'rgba(239, 68, 68, 0.6)';
    const text = isBull ? 'S&P 500: Bullish Trend' : 'S&P 500: Bearish Trend';

    const bullMesh = `
        <polygon points="100,160 40,80 60,40 100,60 140,40 160,80" fill="none" stroke="currentColor" stroke-width="2"/>
        <polygon points="100,160 70,100 100,120 130,100" fill="none" stroke="currentColor" stroke-width="1.5"/>
        <polygon points="60,40 20,10 40,60" fill="none" stroke="currentColor" stroke-width="2"/>
        <polygon points="140,40 180,10 160,60" fill="none" stroke="currentColor" stroke-width="2"/>
        <line x1="100" y1="60" x2="100" y2="120" stroke="currentColor" stroke-width="1.5" stroke-dasharray="2 2"/>
        <line x1="40" y1="80" x2="70" y2="100" stroke="currentColor" stroke-width="1.5"/>
        <line x1="160" y1="80" x2="130" y2="100" stroke="currentColor" stroke-width="1.5"/>
    `;
    const bearMesh = `
        <polygon points="100,150 30,100 50,30 150,30 170,100" fill="none" stroke="currentColor" stroke-width="2"/>
        <polygon points="100,150 60,110 100,130 140,110" fill="none" stroke="currentColor" stroke-width="1.5"/>
        <path d="M50,30 Q20,-10 70,20" fill="none" stroke="currentColor" stroke-width="2"/>
        <path d="M150,30 Q180,-10 130,20" fill="none" stroke="currentColor" stroke-width="2"/>
        <line x1="100" y1="50" x2="100" y2="130" stroke="currentColor" stroke-width="1.5" stroke-dasharray="2 2"/>
        <line x1="30" y1="100" x2="60" y2="110" stroke="currentColor" stroke-width="1.5"/>
        <line x1="170" y1="100" x2="140" y2="110" stroke="currentColor" stroke-width="1.5"/>
    `;

    container.innerHTML = `
        <div class="relative w-48 h-48 flex justify-center items-center wireframe-globe drop-shadow-[0_0_20px_${shadowColor}]">
            <div class="absolute inset-0 w-full h-full border border-${color.split('-')[1]}-500/30 rounded-full animate-[spin_10s_linear_infinite]" style="transform: rotateX(60deg);"></div>
            <div class="absolute inset-0 w-full h-full border border-${color.split('-')[1]}-500/20 rounded-full animate-[spin_15s_linear_infinite]" style="transform: rotateY(60deg);"></div>
            <svg viewBox="0 0 200 200" class="w-32 h-32 absolute z-10 ${color} animate-pulse">
                ${isBull ? bullMesh : bearMesh}
            </svg>
        </div>
        <div class="${color} font-mono text-sm tracking-widest uppercase mt-4" style="text-shadow: 0 0 10px ${shadowColor}">${text}</div>
    `;
}
renderWireframe(true); // Default to Bull

// --- 2. Zero-Token Local Search ---
const localDatabase = [
    { symbol: "AAPL", name: "Apple Inc.", price: 173.50, zScore: 1.2, pe: 28.5, roe: "145%", de: 1.2, website: "https://apple.com" },
    { symbol: "TSLA", name: "Tesla Inc.", price: 180.50, zScore: -3.1, pe: 45.2, roe: "22%", de: 0.7, website: "https://tesla.com" }
];

function executeSearch(event) {
    if (event.key !== 'Enter') return;
    const query = document.getElementById('main-search').value.toLowerCase().trim();
    if (!query) return;

    const results = localDatabase.map(stock => {
        let score = 0;
        const sym = stock.symbol.toLowerCase();
        const name = stock.name.toLowerCase();
        
        if (sym === query) score = 100; 
        else if (name === query) score = 95; 
        else if (sym.includes(query)) score = 80; 
        else if (name.includes(query)) score = 60; 
        
        return { ...stock, matchScore: score };
    }).filter(s => s.matchScore > 0).sort((a, b) => b.matchScore - a.matchScore);

    renderSearchResults(results, query);
}

function renderSearchResults(results, query) {
    const section = document.getElementById('search-results-section');
    const grid = document.getElementById('search-grid');
    const meta = document.getElementById('search-meta');
    
    section.classList.remove('hidden');
    grid.innerHTML = '';
    meta.innerText = results.length === 0 ? `No matches found for "${query}".` : `Found ${results.length} match(es) for "${query}".`;

    results.forEach((data) => {
        const colorClass = data.zScore < 0 ? 'text-pink-500' : 'text-green-400';
        const card = document.createElement('div');
        card.className = `glass-card p-6 cursor-pointer transform hover:scale-105 transition duration-300`;
        card.onclick = () => openModal(data);
        card.innerHTML = `
            <div class="flex justify-between items-start mb-2">
                <div><h3 class="font-bold text-2xl text-white tracking-wide">${data.symbol}</h3></div>
                <div class="${colorClass} font-mono font-bold bg-black/40 px-3 py-1 rounded-full border border-white/5 text-sm">Z: ${data.zScore > 0 ? '+' : ''}${data.zScore}</div>
            </div>
            <div class="text-xl text-gray-300 mt-2">$${data.price.toFixed(2)}</div>
            <div class="mt-4 pt-4 border-t border-white/10 flex justify-between items-center text-sm group">
                <span class="text-gray-400 truncate w-32">${data.name}</span>
                <span class="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-500 font-bold group-hover:translate-x-1 transition-transform">Analyze with AI &rarr;</span>
            </div>
        `;
        grid.appendChild(card);
    });
    section.scrollIntoView({ behavior: 'smooth' });
}

// --- 3. LIVE Python API Integration: Scan Market ---
async function fetchLiveAnomalies() {
    const grid = document.getElementById('anomaly-grid');
    grid.innerHTML = '<div class="text-center w-full col-span-3 text-purple-400 animate-pulse">Running live Python math models via yfinance...</div>';
    
    try {
        const res = await fetch('/api/v1/scan');
        const json = await res.json();
        const anomalies = json.data;

        grid.innerHTML = '';
        if(anomalies.length === 0) {
            grid.innerHTML = '<div class="text-gray-500 col-span-3 text-center">No high-sigma anomalies detected in the current scan.</div>';
            return;
        }

        anomalies.forEach((data, index) => {
            // 1. Determine the Badge Color based on the backend 'color' field
            const badgeClass = data.color === 'pink' 
                ? 'bg-pink-500/20 text-pink-400 border-pink-500/30' 
                : 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
            
            const zColor = data.zScore < 0 ? 'text-pink-500' : 'text-green-400';
            
            const card = document.createElement('div');
            card.className = `glass-card p-6 cursor-pointer reveal-on-scroll delay-${index * 100} visible`;
            card.onclick = () => openModal(data);
            
            card.innerHTML = `
                <div class="flex justify-between items-start mb-4">
                    <div>
                        <h3 class="font-bold text-2xl text-white tracking-wide">${data.symbol}</h3>
                        <div class="text-xl text-gray-300 mt-1">$${data.price.toFixed(2)}</div>
                    </div>
                    <div class="flex flex-col items-end gap-2">
                        <span class="px-2 py-1 rounded text-[10px] font-bold border uppercase ${badgeClass}">
                            ${data.severity}
                        </span>
                        <div class="${zColor} font-mono font-bold bg-black/40 px-3 py-1 rounded-full border border-white/5 text-sm">
                            Z: ${data.zScore > 0 ? '+' : ''}${data.zScore}
                        </div>
                    </div>
                </div>
                <div class="mt-6 pt-4 border-t border-white/10 flex justify-between items-center text-sm group">
                    <span class="text-gray-400">Status: <span class="text-yellow-400">Pending AI Review</span></span>
                    <span class="text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-pink-500 font-bold group-hover:translate-x-1 transition-transform">Run Agent &rarr;</span>
                </div>
            `;
            grid.appendChild(card);
        });
    } catch (e) {
        grid.innerHTML = '<div class="text-red-500 col-span-3 text-center">Error connecting to Python backend.</div>';
    }
}

// --- 4. LIVE Python API Integration: Deep-Dive Modal ---
async function openModal(data) {
    document.getElementById('deep-dive-modal').classList.remove('hidden');
    
    // Set static UI data
    document.getElementById('modal-symbol').innerText = data.symbol;
    document.getElementById('modal-name').innerText = data.name || data.symbol;
    document.getElementById('modal-price').innerText = `$${data.price.toFixed(2)}`;
    document.getElementById('modal-zscore').innerText = `${data.zScore > 0 ? '+' : ''}${data.zScore} Sigma`;
    document.getElementById('modal-pe').innerText = data.pe || 'N/A';
    document.getElementById('modal-roe').innerText = data.roe || 'N/A';
    document.getElementById('modal-de').innerText = data.de || 'N/A';
    document.getElementById('modal-website').href = data.website || '#';
    
    const reasoningBox = document.getElementById('modal-ai-reasoning');

    // 1. INJECT FLASHING STATE WHILE WAITING
    reasoningBox.innerHTML = '<span class="animate-pulse text-purple-400 font-semibold">Authorizing Gemini Agent... querying guardrails...</span>';

    setTimeout(() => {
        const content = document.getElementById('modal-content-wrapper');
        content.classList.remove('scale-95', 'opacity-0');
        content.classList.add('scale-100', 'opacity-100');
    }, 10);

    // Call the Python AI endpoint
    try {
        const res = await fetch(`/api/v1/analyze/${data.symbol}?price=${data.price}&z_score=${data.zScore}&session_id=${sessionId}`, { method: 'POST' });
        const json = await res.json();
        
        // If it was pulled from the database, show a blue badge to flex your token savings!
        if (json.cached) {
            reasoningBox.innerHTML = `
                <div class="mb-3 inline-block bg-blue-500/20 text-blue-400 border border-blue-500/30 px-2 py-1 rounded text-xs font-bold flex items-center gap-1 w-max">
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                    Retrieved from BigQuery Cache (0 Tokens)
                </div>
                ${json.reasoning}
            `;
        } else {
            reasoningBox.innerText = json.reasoning;
        }
    } catch (e) {
        reasoningBox.innerText = "Error: Failed to reach backend.";
    }
}

function closeModal() {
    const content = document.getElementById('modal-content-wrapper');
    content.classList.remove('scale-100', 'opacity-100');
    content.classList.add('scale-95', 'opacity-0');
    setTimeout(() => { document.getElementById('deep-dive-modal').classList.add('hidden'); }, 300);
}

// --- 5. LIVE Python API Integration: Support Chatbot ---
function toggleChat() {
    document.getElementById('support-chat').classList.toggle('hidden');
}

async function sendSupportMessage() {
    const input = document.getElementById('chat-input');
    const history = document.getElementById('chat-history');
    const msg = input.value.trim();
    if(!msg) return;
    
    // Add user message
    history.innerHTML += `<div class="flex justify-end"><div class="bg-purple-600/50 p-3 rounded-lg border border-purple-500/30 text-white max-w-[85%]">${msg}</div></div>`;
    input.value = '';
    history.scrollTop = history.scrollHeight;
    
    // Call Python backend
    try {
        const res = await fetch('/api/v1/support', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: msg })
        });
        const json = await res.json();
        
        history.innerHTML += `
            <div class="flex justify-start">
                <div class="bg-white/5 p-3 rounded-lg border border-white/10 text-gray-200 max-w-[85%]">
                    <span class="text-xs text-purple-400 font-bold block mb-1">Agent</span>
                    ${json.reply}
                </div>
            </div>`;
    } catch (e) {
        history.innerHTML += `<div class="text-red-400 text-xs">Error connecting to support agent.</div>`;
    }
    history.scrollTop = history.scrollHeight;
}

document.getElementById('chat-input').addEventListener('keypress', function (e) {
    if (e.key === 'Enter') sendSupportMessage();
});

// Init scroll observer
const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => { if (entry.isIntersecting) entry.target.classList.add('visible'); });
}, { threshold: 0.1 });
document.querySelectorAll('.reveal-on-scroll').forEach(el => observer.observe(el));

// --- Reporting Logic ---
function toggleReportForm() {
    const form = document.getElementById('report-form-container');
    form.classList.toggle('hidden');
    // Reset form when closed
    if (form.classList.contains('hidden')) {
        document.getElementById('report-checkbox').checked = false;
        document.getElementById('report-category').value = "";
        document.getElementById('report-description').value = "";
        document.getElementById('report-description').classList.add('hidden');
        validateReportForm();
    }
}

function validateReportForm() {
    const isChecked = document.getElementById('report-checkbox').checked;
    const category = document.getElementById('report-category').value;
    const descInput = document.getElementById('report-description');
    const submitBtn = document.getElementById('submit-report-btn');
    
    // Show/hide description box
    if (category === "Others") {
        descInput.classList.remove('hidden');
    } else {
        descInput.classList.add('hidden');
    }

    // Validation Rules
    let isValid = isChecked && category !== "";
    if (category === "Others" && descInput.value.trim() === "") isValid = false;

    if (isValid) {
        submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        submitBtn.classList.add('hover:bg-pink-500');
        submitBtn.disabled = false;
    } else {
        submitBtn.classList.add('opacity-50', 'cursor-not-allowed');
        submitBtn.classList.remove('hover:bg-pink-500');
        submitBtn.disabled = true;
    }
}

async function submitReport() {
    const btn = document.getElementById('submit-report-btn');
    const ticker = document.getElementById('modal-symbol').innerText;
    const category = document.getElementById('report-category').value;
    const description = document.getElementById('report-description').value;

    btn.innerText = "Submitting...";
    btn.disabled = true;

    try {
        await fetch(`/api/v1/report/${ticker}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, category: category, description: description })
        });
        btn.innerText = "Report Submitted!";
        btn.classList.replace('bg-pink-600/50', 'bg-green-600/50');
        setTimeout(() => toggleReportForm(), 2000);
    } catch (e) {
        btn.innerText = "Error Submitting";
        setTimeout(() => { btn.innerText = "Submit Report"; validateReportForm(); }, 2000);
    }
}