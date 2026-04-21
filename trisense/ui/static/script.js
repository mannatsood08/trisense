// Clock update
function updateClock() {
    const now = new Date();
    document.getElementById('clock').textContent = now.toLocaleTimeString('en-US', { hour12: false });
}
setInterval(updateClock, 1000);
updateClock();

// Connect to Server-Sent Events
const eventSource = new EventSource('/events');

function updateModuleUI(moduleId, status) {
    const card = document.getElementById(`${moduleId}-card`);
    const valText = document.getElementById(`${moduleId}-val`);
    
    valText.textContent = status;
    
    // Reset classes
    card.className = 'status-card';
    valText.className = 'card-value';
    
    let stateClass = 'normal';
    
    // Determine severity based on status strings
    if (status === 'FALL_DETECTED' || status === 'EMERGENCY') {
        stateClass = 'emergency';
    } else if (status === 'POTENTIAL_FALL' || status === 'UNKNOWN_PERSON' || status === 'WARNING') {
        stateClass = 'warning';
    }
    
    card.classList.add(`border-${stateClass}`);
    valText.classList.add(`state-${stateClass}`);
}

function updateGlobalState(state) {
    const appContainer = document.getElementById('app');
    const globalText = document.getElementById('global-state-text');
    const videoOverlay = document.getElementById('video-overlay');
    
    globalText.textContent = state;
    
    appContainer.className = '';
    globalText.className = '';
    videoOverlay.style.boxShadow = 'none';
    
    if (state === 'EMERGENCY') {
        appContainer.classList.add('emergency-state');
        globalText.classList.add('bg-emergency');
        videoOverlay.style.backgroundColor = 'var(--color-emergency)';
        videoOverlay.style.boxShadow = '0 0 15px var(--color-emergency)';
    } else if (state === 'WARNING') {
        appContainer.classList.add('warning-state');
        globalText.classList.add('bg-warning');
        videoOverlay.style.backgroundColor = 'var(--color-warning)';
        videoOverlay.style.boxShadow = '0 0 15px var(--color-warning)';
    } else {
        globalText.classList.add('bg-normal');
        videoOverlay.style.backgroundColor = 'var(--color-normal)';
        videoOverlay.style.boxShadow = '0 0 10px var(--color-normal)';
    }
}

function addLogEntry(data) {
    const logList = document.getElementById('log-list');
    
    const entry = document.createElement('div');
    entry.className = `log-item border-${data.severity.toLowerCase()}`;
    
    const time = new Date(data.timestamp * 1000).toLocaleTimeString();
    
    // Use dynamic severity colors for border-left
    if (data.severity === 'HIGH') entry.style.borderLeftColor = 'var(--color-emergency)';
    else if (data.severity === 'MEDIUM') entry.style.borderLeftColor = 'var(--color-warning)';
    else entry.style.borderLeftColor = 'var(--color-normal)';

    entry.innerHTML = `
        <div class="log-time">${time}</div>
        <div class="log-title">[${data.source.toUpperCase()}] ${data.event}</div>
        <div class="log-details">${data.details || ''}</div>
    `;
    
    logList.prepend(entry);
    
    // Keep max 50 entries in UI
    if (logList.children.length > 50) {
        logList.removeChild(logList.lastChild);
    }
}

eventSource.onmessage = function(e) {
    const data = JSON.parse(e.data);
    
    // Update individual module
    updateModuleUI(data.source, data.event);
    
    // Update global system status
    updateGlobalState(data.system_state);
    
    // Only add to log if it's a noteworthy event
    if (data.event !== 'NORMAL') {
        addLogEntry(data);
    }
};
