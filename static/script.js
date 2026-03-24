const socket = io();
let messageChart;
let network;
let nodes;
let edges;
let topicFilter = 'all';
let messageCount = 0;
let pinnedNodes = new Set();

// ============================================================
// Alpine.js global store for shared state
// ============================================================
document.addEventListener('alpine:init', () => {
    Alpine.store('mqtt', {
        connected: false,
        selectedTopic: 'all',
        messageCount: 0,
    });
});

// ============================================================
// Alpine.js root app component (bound to <body>)
// ============================================================
function mqttuiApp() {
    return {
        sidebarOpen: true,
        activeTab: 'dashboard',
        alertsLoaded: false,
        rulesLoaded: false,
        analyticsLoaded: false,
        pluginsLoaded: false,
        init() {
            // Initialize Chart.js and Vis.js network
            initChart();
            initNetwork();
            setInterval(updateChart, 1000);
            setInterval(updateStats, 5000);
            initDebugBar();
            trackClientPerformance();

            // Load existing topics from API
            loadTopicsFromAPI();
            setInterval(loadTopicsFromAPI, 30000);

            // Setup advanced search UI
            setupAdvancedSearchHandlers();

            // Handle batch messages from server (100ms batched)
            socket.on('mqtt_messages_batch', (batch) => {
                batch.forEach(msg => {
                    window.dispatchEvent(new CustomEvent('mqtt-message', { detail: msg }));
                    Alpine.store('mqtt').messageCount++;
                    messageCount++;
                    updateNetwork(msg);
                    updateTopicFilter(msg.topic);
                });
            });

            // Fallback for single messages (backward compat)
            socket.on('mqtt_message', (data) => {
                window.dispatchEvent(new CustomEvent('mqtt-message', { detail: data }));
                Alpine.store('mqtt').messageCount++;
                messageCount++;
                updateMessageList(data);
                updateNetwork(data);
                updateTopicFilter(data.topic);
            });
        },
        toggleSidebar() {
            this.sidebarOpen = !this.sidebarOpen;
            // Toggle body class for CSS max-width adjustment
            if (this.sidebarOpen) {
                document.body.classList.remove('sidebar-hidden');
            } else {
                document.body.classList.add('sidebar-hidden');
            }
        },
    };
}

// ============================================================
// Alpine.js message list component
// ============================================================
function messageListComponent() {
    return {
        messages: [],
        favorites: [],
        init() {
            this.loadMessages();
            this.loadFavorites();
            window.addEventListener('mqtt-message', (e) => {
                const msg = e.detail;
                const filter = Alpine.store('mqtt').selectedTopic;
                if (filter === 'all' || msg.topic === filter) {
                    this.messages.unshift(msg);
                    if (this.messages.length > 100) this.messages.pop();
                }
            });
        },
        async loadMessages(extraFilters = {}) {
            const params = new URLSearchParams({ limit: '50' });
            const topic = Alpine.store('mqtt').selectedTopic;
            if (topic && topic !== 'all') params.append('topic', topic);
            // Apply extra filters (from Advanced Search)
            Object.entries(extraFilters).forEach(([key, value]) => {
                if (value) params.append(key, value);
            });
            try {
                const resp = await fetch(`/api/v1/messages?${params}`);
                const data = await resp.json();
                const payload = data.data || data;
                this.messages = payload.messages || [];
            } catch (e) {
                console.error('Error loading messages:', e);
            }
        },
        showFavoritesOnly: false,
        get filteredMessages() {
            if (!this.showFavoritesOnly) return this.messages;
            return this.messages.filter(m => this.favorites.includes(m.topic));
        },
        async loadFavorites() {
            try {
                const resp = await fetch('/api/v1/topics/favorites');
                const data = await resp.json();
                if (data.status === 'success') {
                    this.favorites = data.data.favorites.map(f => f.topic);
                }
            } catch (e) {
                console.error('Error loading favorites:', e);
            }
        },
        isFavorite(topic) {
            return this.favorites.includes(topic);
        },
        async toggleFavorite(topic) {
            try {
                const resp = await fetch(`/api/v1/topics/${encodeURIComponent(topic)}/bookmark`, {
                    method: 'POST',
                });
                const data = await resp.json();
                if (data.status === 'success') {
                    if (data.data.bookmarked) {
                        this.favorites.push(topic);
                    } else {
                        this.favorites = this.favorites.filter(t => t !== topic);
                    }
                }
            } catch (e) {
                console.error('Error toggling favorite:', e);
            }
        },
        formatPayload(payload) {
            try { return JSON.stringify(JSON.parse(payload), null, 2); }
            catch { return payload; }
        },
        formatTime(ts) {
            return new Date(ts).toLocaleTimeString();
        },
    };
}

// ============================================================
// Alpine.js stats component
// ============================================================
function statsComponent() {
    return {
        connections: 0,
        topics: 0,
        messageTotal: 0,
        init() {
            this.fetchStats();
            setInterval(() => this.fetchStats(), 5000);
        },
        async fetchStats() {
            try {
                const resp = await fetch('/stats');
                const data = await resp.json();
                this.connections = data.connection_count;
                this.topics = data.topic_count;
                this.messageTotal = data.message_count;
            } catch (e) {
                console.error('Error fetching stats:', e);
            }
        },
    };
}

// ============================================================
// Alpine.js publish component
// ============================================================
function publishComponent() {
    return {
        topic: '',
        message: '',
        async submit() {
            await fetch('/publish', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `topic=${encodeURIComponent(this.topic)}&message=${encodeURIComponent(this.message)}`
            });
            this.topic = '';
            this.message = '';
        },
    };
}

// ============================================================
// Chart.js (kept as-is per plan)
// ============================================================
function initChart() {
    if (messageChart) return;
    const canvas = document.getElementById('messageChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    // Create gradient fill
    const gradient = ctx.createLinearGradient(0, 0, 0, canvas.parentElement.clientHeight || 160);
    gradient.addColorStop(0, 'rgba(59, 130, 246, 0.3)');
    gradient.addColorStop(1, 'rgba(59, 130, 246, 0.0)');

    // Pre-fill with zeros for smooth start
    const emptyLabels = Array(30).fill('');
    const emptyData = Array(30).fill(0);

    messageChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: emptyLabels,
            datasets: [{
                label: 'msg/s',
                data: emptyData,
                borderColor: 'rgb(59, 130, 246)',
                backgroundColor: gradient,
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4,
                pointHoverBackgroundColor: 'rgb(59, 130, 246)',
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 300 },
            interaction: { intersect: false, mode: 'index' },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(75, 85, 99, 0.3)', drawBorder: false },
                    ticks: {
                        color: 'rgb(156, 163, 175)',
                        font: { size: 10 },
                        maxTicksLimit: 4,
                        callback: v => Number.isInteger(v) ? v : '',
                    },
                    border: { display: false },
                },
                x: {
                    display: false,
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(17, 24, 39, 0.9)',
                    titleColor: 'rgb(156, 163, 175)',
                    bodyColor: 'rgb(59, 130, 246)',
                    bodyFont: { weight: 'bold', size: 14 },
                    padding: 8,
                    displayColors: false,
                    callbacks: {
                        title: (items) => items[0]?.label || '',
                        label: (item) => `${item.raw} msg/s`,
                    }
                }
            }
        }
    });
}

function updateChart() {
    if (!messageChart) return;
    const now = new Date();
    const timeLabel = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

    messageChart.data.labels.push(timeLabel);
    messageChart.data.datasets[0].data.push(messageCount);

    if (messageChart.data.labels.length > 30) {
        messageChart.data.labels.shift();
        messageChart.data.datasets[0].data.shift();
    }

    // Update the big rate number
    const rateDisplay = document.getElementById('rate-display');
    if (rateDisplay) rateDisplay.textContent = messageCount;

    messageChart.update('none'); // skip animation for smoother feel at 1s interval
    messageCount = 0;
}

// ============================================================
// Vis.js network (kept as-is per plan)
// ============================================================
function initNetwork() {
    if (network) return; // Already initialized
    nodes = new vis.DataSet([
        { id: 'broker', label: 'MQTT Broker', shape: 'hexagon', color: '#FFA500', size: 30 }
    ]);
    edges = new vis.DataSet();

    const container = document.getElementById('network-visualization');
    const data = { nodes, edges };
    const options = {
        physics: {
            enabled: true,
            stabilization: {
                enabled: true,
                iterations: 150,
                updateInterval: 25,
                fit: true
            },
            barnesHut: {
                gravitationalConstant: -8000,
                centralGravity: 0.3,
                springLength: 200,
                springConstant: 0.04,
                damping: 0.09,
                avoidOverlap: 0.1
            }
        },
        nodes: {
            font: { color: '#FFFFFF', size: 14 },
            borderWidth: 2,
            shadow: true,
            margin: 10
        },
        edges: {
            width: 2,
            color: { inherit: 'from' },
            smooth: { type: 'continuous' },
            arrows: { to: { enabled: true, scaleFactor: 0.5 } }
        },
        interaction: {
            dragNodes: true,
            dragView: true,
            zoomView: true
        },
        layout: {
            improvedLayout: true,
            clusterThreshold: 150
        }
    };

    network = new vis.Network(container, data, options);

    // Auto-fit network after stabilization
    network.on('stabilizationIterationsDone', function() {
        network.fit({
            animation: { duration: 1000, easingFunction: 'easeInOutQuad' }
        });
    });

    // Double-click to pin/unpin nodes
    network.on('doubleClick', function(params) {
        if (params.nodes.length > 0) {
            const nodeId = params.nodes[0];
            if (pinnedNodes.has(nodeId)) {
                pinnedNodes.delete(nodeId);
                nodes.update({
                    id: nodeId,
                    fixed: false,
                    color: nodes.get(nodeId).color || '#97C2FC'
                });
            } else {
                pinnedNodes.add(nodeId);
                nodes.update({
                    id: nodeId,
                    fixed: true,
                    color: '#FF6B6B'
                });
            }
        }
    });

    // Right-click context menu for pinning
    network.on('oncontext', function(params) {
        params.event.preventDefault();
        if (params.nodes.length > 0) {
            const nodeId = params.nodes[0];
            const isPinned = pinnedNodes.has(nodeId);
            const action = isPinned ? 'Unpin' : 'Pin';

            if (confirm(`${action} node "${nodes.get(nodeId).label}"?`)) {
                if (isPinned) {
                    pinnedNodes.delete(nodeId);
                    nodes.update({
                        id: nodeId,
                        fixed: false,
                        color: nodes.get(nodeId).color || '#97C2FC'
                    });
                } else {
                    pinnedNodes.add(nodeId);
                    nodes.update({
                        id: nodeId,
                        fixed: true,
                        color: '#FF6B6B'
                    });
                }
            }
        }
    });
}

function updateNetwork(message) {
    if (!nodes || !edges || !network) {
        console.error('Network not initialized');
        return;
    }

    const topicParts = message.topic.split('/');
    let parentId = 'broker';

    topicParts.forEach((part, index) => {
        const nodeId = topicParts.slice(0, index + 1).join('/');
        if (!nodes.get(nodeId)) {
            nodes.add({
                id: nodeId,
                label: part,
                color: getRandomColor(),
                shape: 'dot',
                size: 20 - index * 2
            });

            clearTimeout(window.autoFitTimeout);
            window.autoFitTimeout = setTimeout(() => {
                if (network) {
                    network.fit({
                        animation: { duration: 800, easingFunction: 'easeInOutQuad' }
                    });
                }
            }, 2000);
        }
        if (parentId !== nodeId) {
            const edgeId = `${parentId}-${nodeId}`;
            if (!edges.get(edgeId)) {
                edges.add({ id: edgeId, from: parentId, to: nodeId });
            }
        }
        parentId = nodeId;
    });

    // Animate message flow
    const edgeIds = edges.getIds();
    edgeIds.forEach(edgeId => {
        edges.update({ id: edgeId, color: { color: '#00ff00' }, width: 4 });
        setTimeout(() => {
            edges.update({ id: edgeId, color: { inherit: 'from' }, width: 2 });
        }, 1000);
    });

    // Pulse the final topic node
    const finalNodeId = topicParts.join('/');
    const finalNode = nodes.get(finalNodeId);
    nodes.update({ id: finalNodeId, size: finalNode.size + 5 });
    setTimeout(() => {
        nodes.update({ id: finalNodeId, size: finalNode.size });
    }, 1000);
}

// ============================================================
// Standalone utility functions (kept as-is per plan)
// ============================================================

function getRandomColor() {
    const letters = '0123456789ABCDEF';
    let color = '#';
    for (let i = 0; i < 6; i++) {
        color += letters[Math.floor(Math.random() * 16)];
    }
    return color;
}

// Legacy updateMessageList for backward-compat single-message handler
function updateMessageList(message) {
    // Now handled by Alpine.js messageListComponent via CustomEvent
    // This function is kept for any non-Alpine fallback paths
}

function updateStats() {
    // Stats are now handled by Alpine.js statsComponent — this is a no-op
}

function updateTopicFilter(newTopic) {
    const topicFilterEl = document.getElementById('topic-filter');
    if (topicFilterEl && !Array.from(topicFilterEl.options).some(option => option.value === newTopic)) {
        const option = document.createElement('option');
        option.value = newTopic;
        option.textContent = newTopic;
        topicFilterEl.appendChild(option);
    }
}

function loadTopicsFromAPI() {
    fetch('/api/v1/topics')
        .then(response => response.json())
        .then(envelope => {
            const data = envelope.data || envelope;
            const topicFilterEl = document.getElementById('topic-filter');
            if (!topicFilterEl) return;

            const allTopicsOption = topicFilterEl.querySelector('option[value="all"]');
            topicFilterEl.innerHTML = '';
            if (allTopicsOption) {
                topicFilterEl.appendChild(allTopicsOption);
            } else {
                const option = document.createElement('option');
                option.value = 'all';
                option.textContent = 'All Topics';
                topicFilterEl.appendChild(option);
            }

            // Sort favorites to top
            const topics = data.topics || [];
            topics.sort((a, b) => {
                if (a.is_favorite && !b.is_favorite) return -1;
                if (!a.is_favorite && b.is_favorite) return 1;
                return 0;
            });

            topics.forEach(topic => {
                const option = document.createElement('option');
                option.value = topic.topic;
                const star = topic.is_favorite ? '\u2605 ' : '';
                const count = topic.message_count != null ? ` (${topic.message_count})` : '';
                option.textContent = `${star}${topic.topic}${count}`;
                topicFilterEl.appendChild(option);
            });
        })
        .catch(error => console.error('Error loading topics:', error));
}

function loadFilteredMessages(customFilters = {}) {
    // Find the Alpine message list component and call loadMessages with filters
    const messageList = document.getElementById('message-list');
    if (!messageList) return;

    // Read topic from dropdown (not stale global)
    const topicEl = document.getElementById('topic-filter');
    const selectedTopic = topicEl ? topicEl.value : 'all';
    if (selectedTopic !== 'all') {
        Alpine.store('mqtt').selectedTopic = selectedTopic;
    }

    // Get the Alpine component on the parent element
    const alpineEl = messageList.closest('[x-data]');
    if (alpineEl && alpineEl._x_dataStack) {
        const component = alpineEl._x_dataStack[0];
        if (component && component.loadMessages) {
            component.loadMessages(customFilters);
            return;
        }
    }

    // Fallback: dispatch event with filters
    window.dispatchEvent(new CustomEvent('apply-filters', { detail: customFilters }));
}

// ============================================================
// Advanced search handlers (kept as-is per plan)
// ============================================================
function setupAdvancedSearchHandlers() {
    const applyBtn = document.getElementById('apply-filters-btn');
    if (applyBtn) {
        applyBtn.addEventListener('click', function() {
            const filters = {
                content: document.getElementById('content-search').value,
                regex_topic: document.getElementById('regex-topic').value,
                json_path: document.getElementById('json-path').value,
                json_value: document.getElementById('json-value').value,
                hours: document.getElementById('time-filter').value
            };

            Object.keys(filters).forEach(key => {
                if (!filters[key]) delete filters[key];
            });

            loadFilteredMessages(filters);
        });
    }

    const clearBtn = document.getElementById('clear-filters-btn');
    if (clearBtn) {
        clearBtn.addEventListener('click', function() {
            const topicFilterEl = document.getElementById('topic-filter');
            if (topicFilterEl) topicFilterEl.value = 'all';
            const contentSearch = document.getElementById('content-search');
            if (contentSearch) contentSearch.value = '';
            const regexTopic = document.getElementById('regex-topic');
            if (regexTopic) regexTopic.value = '';
            const jsonPath = document.getElementById('json-path');
            if (jsonPath) jsonPath.value = '';
            const jsonValue = document.getElementById('json-value');
            if (jsonValue) jsonValue.value = '';
            const timeFilter = document.getElementById('time-filter');
            if (timeFilter) timeFilter.value = '';
            topicFilter = 'all';
            if (window.Alpine && Alpine.store('mqtt')) {
                Alpine.store('mqtt').selectedTopic = 'all';
            }
            loadFilteredMessages();
        });
    }

    loadFilterPresets();

    const loadPresetBtn = document.getElementById('load-preset-btn');
    if (loadPresetBtn) {
        loadPresetBtn.addEventListener('click', function() {
            const presetName = document.getElementById('preset-select').value;
            if (!presetName) {
                alert('Please select a preset to load');
                return;
            }

            fetch(`/api/v1/filter-presets/${encodeURIComponent(presetName)}/use`, {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                const inner = data.data || data;
                if (data.status === 'success' || inner.filters) {
                    const filters = inner.filters;
                    const contentSearch = document.getElementById('content-search');
                    if (contentSearch) contentSearch.value = filters.content || '';
                    const regexTopic = document.getElementById('regex-topic');
                    if (regexTopic) regexTopic.value = filters.regex_topic || '';
                    const jsonPath = document.getElementById('json-path');
                    if (jsonPath) jsonPath.value = filters.json_path || '';
                    const jsonValue = document.getElementById('json-value');
                    if (jsonValue) jsonValue.value = filters.json_value || '';
                    const timeFilter = document.getElementById('time-filter');
                    if (timeFilter) timeFilter.value = filters.hours || '';

                    if (filters.topic) {
                        const topicFilterEl = document.getElementById('topic-filter');
                        if (topicFilterEl) topicFilterEl.value = filters.topic;
                        topicFilter = filters.topic;
                    }

                    loadFilteredMessages(filters);
                } else {
                    alert('Error loading preset: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error loading preset:', error);
                alert('Error loading preset');
            });
        });
    }

    const savePresetBtn = document.getElementById('save-preset-btn');
    if (savePresetBtn) {
        savePresetBtn.addEventListener('click', function() {
            const name = prompt('Enter a name for this filter preset:');
            if (!name) return;

            const description = prompt('Enter a description (optional):') || '';

            const filters = {
                content: document.getElementById('content-search').value,
                regex_topic: document.getElementById('regex-topic').value,
                json_path: document.getElementById('json-path').value,
                json_value: document.getElementById('json-value').value,
                hours: document.getElementById('time-filter').value
            };

            if (topicFilter && topicFilter !== 'all') {
                filters.topic = topicFilter;
            }

            Object.keys(filters).forEach(key => {
                if (!filters[key]) delete filters[key];
            });

            if (Object.keys(filters).length === 0) {
                alert('No filters to save');
                return;
            }

            fetch('/api/v1/filter-presets', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: name,
                    description: description,
                    filters: filters
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    alert('Filter preset saved successfully!');
                    loadFilterPresets();
                } else {
                    alert('Error saving preset: ' + (data.error?.message || data.error));
                }
            })
            .catch(error => {
                console.error('Error saving preset:', error);
                alert('Error saving preset');
            });
        });
    }

    // Fullscreen and reset buttons for network
    const fullscreenBtn = document.getElementById('fullscreen-btn');
    if (fullscreenBtn) {
        fullscreenBtn.addEventListener('click', function() {
            const networkDiv = document.getElementById('network-visualization');
            if (networkDiv.requestFullscreen) {
                networkDiv.requestFullscreen();
            } else if (networkDiv.webkitRequestFullscreen) {
                networkDiv.webkitRequestFullscreen();
            } else if (networkDiv.msRequestFullscreen) {
                networkDiv.msRequestFullscreen();
            }
        });
    }

    const resetBtn = document.getElementById('reset-nodes-btn');
    if (resetBtn) {
        resetBtn.addEventListener('click', function() {
            if (network) {
                pinnedNodes.forEach(nodeId => {
                    const node = nodes.get(nodeId);
                    if (node) {
                        nodes.update({
                            id: nodeId,
                            fixed: false,
                            color: node.originalColor || '#97C2FC'
                        });
                    }
                });
                pinnedNodes.clear();

                network.setOptions({
                    physics: {
                        enabled: true,
                        stabilization: {
                            enabled: true,
                            iterations: 150,
                            updateInterval: 25,
                            fit: true
                        }
                    }
                });

                setTimeout(() => {
                    network.fit({
                        animation: { duration: 1000, easingFunction: 'easeInOutQuad' }
                    });
                }, 500);
            }
        });
    }
}

// Topic filter change handler
document.addEventListener('DOMContentLoaded', function() {
    const topicFilterEl = document.getElementById('topic-filter');
    if (topicFilterEl) {
        topicFilterEl.addEventListener('change', function(e) {
            topicFilter = e.target.value;
            if (window.Alpine && Alpine.store('mqtt')) {
                Alpine.store('mqtt').selectedTopic = topicFilter;
            }
            loadFilteredMessages();
        });
    }
});

function loadFilterPresets() {
    fetch('/api/v1/filter-presets')
        .then(response => response.json())
        .then(data => {
            const presetSelect = document.getElementById('preset-select');
            if (!presetSelect) return;

            presetSelect.innerHTML = '<option value="">Select a preset...</option>';

            const presets = (data.data || data).presets || [];
            presets.forEach(preset => {
                const option = document.createElement('option');
                option.value = preset.name;
                option.textContent = `${preset.name}${preset.description ? ' - ' + preset.description : ''}`;
                presetSelect.appendChild(option);
            });
        })
        .catch(error => console.error('Error loading presets:', error));
}

// ============================================================
// Debug bar (kept as-is per plan)
// ============================================================
let debugBar;
let debugBarToggle;

function initDebugBar() {
    if (debugBar) return; // Already initialized
    debugBar = document.createElement('div');
    debugBar.id = 'debug-bar';
    debugBar.style.display = 'none';
    document.body.appendChild(debugBar);

    debugBarToggle = document.createElement('button');
    debugBarToggle.id = 'debug-bar-toggle';
    debugBarToggle.innerHTML = 'Debug';
    debugBarToggle.onclick = toggleDebugBar;
    document.body.appendChild(debugBarToggle);

    const closeButton = document.createElement('button');
    closeButton.id = 'debug-bar-close';
    closeButton.innerHTML = '&times;';
    closeButton.onclick = closeDebugBar;
    debugBar.appendChild(closeButton);

    updateDebugBar();
    setInterval(updateDebugBar, 1000);
}

function toggleDebugBar() {
    fetch('/toggle-debug-bar', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            debugBar.style.display = data.enabled ? 'block' : 'none';
            debugBarToggle.classList.toggle('active', data.enabled);
        });
}

function closeDebugBar() {
    debugBar.style.display = 'none';
    fetch('/toggle-debug-bar', { method: 'POST' });
    debugBarToggle.classList.remove('active');
}

function trackClientPerformance() {
    const perfData = window.performance.timing;
    const pageLoadTime = perfData.loadEventEnd - perfData.navigationStart;
    const domReadyTime = perfData.domContentLoadedEventEnd - perfData.navigationStart;

    fetch('/record-client-performance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pageLoadTime, domReadyTime }),
    });
}

function updateDebugBar() {
    fetch('/debug-bar')
        .then(response => response.json())
        .then(data => {
            let content = '<button id="debug-bar-close" onclick="closeDebugBar()">&times;</button>';
            content += '<div class="debug-content">';
            for (const [panelName, panelData] of Object.entries(data)) {
                content += `<div class="debug-panel"><h3>${panelName}</h3><ul>`;
                for (const [key, value] of Object.entries(panelData)) {
                    let displayValue = value;
                    if (typeof value === 'object' && value !== null) {
                        displayValue = '<pre>' + JSON.stringify(value, null, 2) + '</pre>';
                    }
                    content += `<li><strong>${key}:</strong> ${displayValue}</li>`;
                }
                content += '</ul></div>';
            }
            content += '</div>';
            debugBar.innerHTML = content;
        });
}

// ============================================================
// Alpine.js rule form component (create/edit)
// ============================================================
function ruleFormComponent(existing = {}) {
    const condition = existing.condition || {};
    const action = existing.action || {};
    return {
        form: {
            id: existing.id || null,
            name: existing.name || '',
            description: existing.description || '',
            trigger_topic: existing.trigger_topic || '',
            condition_path: condition.path || '',
            condition_op: condition.op || '',
            condition_value: condition.value !== undefined ? String(condition.value) : '',
            action_type: action.type || 'publish',
            action_topic: action.topic || '',
            action_payload: action.payload || '',
            action_url: action.url || '',
            action_template: action.payload_template || '',
            action_severity: action.severity || 'info',
            action_message: action.message || '',
            action_bot_token: action.bot_token || '',
            action_chat_id: action.chat_id || '',
            action_message_template: action.message_template || '',
            action_slack_url: action.webhook_url || '',
            rate_limit_per_min: existing.rate_limit_per_min || 10,
        },
        error: '',
        success: '',
        buildPayload() {
            const payload = {
                name: this.form.name,
                description: this.form.description,
                trigger_topic: this.form.trigger_topic,
                rate_limit_per_min: this.form.rate_limit_per_min,
            };
            // Build condition
            if (this.form.condition_op && this.form.condition_path) {
                const cond = { path: this.form.condition_path, op: this.form.condition_op };
                if (!['exists', 'not_exists'].includes(this.form.condition_op)) {
                    let val = this.form.condition_value;
                    const num = Number(val);
                    if (!isNaN(num) && val.trim() !== '') val = num;
                    cond.value = val;
                }
                payload.condition = cond;
            } else {
                payload.condition = {};
            }
            // Build action
            const act = { type: this.form.action_type };
            if (this.form.action_type === 'publish') {
                act.topic = this.form.action_topic;
                act.payload = this.form.action_payload;
            } else if (this.form.action_type === 'telegram') {
                act.bot_token = this.form.action_bot_token;
                act.chat_id = this.form.action_chat_id;
                if (this.form.action_message_template) act.message_template = this.form.action_message_template;
            } else if (this.form.action_type === 'slack') {
                act.webhook_url = this.form.action_slack_url;
                if (this.form.action_message_template) act.message_template = this.form.action_message_template;
            } else if (this.form.action_type === 'webhook') {
                act.url = this.form.action_url;
                if (this.form.action_template) act.payload_template = this.form.action_template;
            } else if (this.form.action_type === 'log') {
                act.severity = this.form.action_severity;
                act.message = this.form.action_message;
            }
            payload.action = act;
            return payload;
        },
        async submitRule() {
            this.error = '';
            this.success = '';
            const payload = this.buildPayload();
            const url = this.form.id ? `/api/v1/rules/${this.form.id}` : '/api/v1/rules/';
            const method = this.form.id ? 'PUT' : 'POST';
            try {
                const resp = await fetch(url, {
                    method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });
                const data = await resp.json();
                if (data.status === 'success') {
                    this.success = this.form.id ? 'Rule updated' : 'Rule created';
                    // Reload rules list via htmx
                    htmx.ajax('GET', '/partials/rules', { target: '#rules-panel', swap: 'innerHTML' });
                } else {
                    this.error = data.error?.message || 'Unknown error';
                }
            } catch (e) {
                this.error = 'Network error: ' + e.message;
            }
        },
    };
}

// ============================================================
// Alpine.js dry-run test component
// ============================================================
function dryRunComponent(ruleId) {
    return {
        ruleId: ruleId,
        topic: '',
        payload: '',
        result: null,
        error: '',
        async runTest() {
            this.error = '';
            this.result = null;
            let payloadVal = this.payload;
            try { payloadVal = JSON.parse(this.payload); } catch (e) { /* use raw string */ }
            try {
                const resp = await fetch(`/api/v1/rules/${this.ruleId}/test`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ topic: this.topic, payload: payloadVal }),
                });
                const data = await resp.json();
                if (data.status === 'success') {
                    this.result = data.data;
                } else {
                    this.error = data.error?.message || 'Test failed';
                }
            } catch (e) {
                this.error = 'Network error: ' + e.message;
            }
        },
    };
}
