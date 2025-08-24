const socket = io();
let messageChart;
let network;
let nodes;
let edges;
let topicFilter = 'all';

function initChart() {
    const ctx = document.getElementById('messageChart').getContext('2d');
    messageChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Messages per second',
                data: [],
                borderColor: 'rgb(59, 130, 246)',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        color: 'rgb(209, 213, 219)'
                    }
                },
                x: {
                    ticks: {
                        color: 'rgb(209, 213, 219)'
                    }
                }
            },
            plugins: {
                legend: {
                    labels: {
                        color: 'rgb(209, 213, 219)'
                    }
                }
            }
        }
    });
}

function updateMessageList(message) {
    if (topicFilter === 'all' || message.topic === topicFilter) {
        const messageList = document.getElementById('message-list');
        const messageElement = document.createElement('div');
        messageElement.className = 'mb-2 p-2 bg-gray-700 rounded';
        messageElement.innerHTML = `<strong class="text-blue-400">${message.topic}:</strong> ${message.payload}`;
        messageList.insertBefore(messageElement, messageList.firstChild);

        if (messageList.childElementCount > 100) {
            messageList.removeChild(messageList.lastChild);
        }
    }
}

function updateChart() {
    const now = new Date();
    messageChart.data.labels.push(now.toLocaleTimeString());
    messageChart.data.datasets[0].data.push(messageCount);

    if (messageChart.data.labels.length > 10) {
        messageChart.data.labels.shift();
        messageChart.data.datasets[0].data.shift();
    }

    messageChart.update();
    messageCount = 0;
}

let messageCount = 0;

function initNetwork() {
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
                iterations: 100,
                updateInterval: 25
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
            font: {
                color: '#FFFFFF',
                size: 14
            },
            borderWidth: 2,
            shadow: true,
            margin: 10
        },
        edges: {
            width: 2,
            color: { inherit: 'from' },
            smooth: {
                type: 'continuous'
            },
            arrows: {
                to: { enabled: true, scaleFactor: 0.5 }
            }
        },
        interaction: {
            dragNodes: true,
            dragView: true,
            zoomView: true
        }
    };

    network = new vis.Network(container, data, options);
    
    // Add node pinning functionality
    let pinnedNodes = new Set();
    
    // Double-click to pin/unpin nodes
    network.on('doubleClick', function(params) {
        if (params.nodes.length > 0) {
            const nodeId = params.nodes[0];
            if (pinnedNodes.has(nodeId)) {
                // Unpin node
                pinnedNodes.delete(nodeId);
                nodes.update({
                    id: nodeId,
                    fixed: false,
                    color: nodes.get(nodeId).color || '#97C2FC'
                });
            } else {
                // Pin node
                pinnedNodes.add(nodeId);
                nodes.update({
                    id: nodeId,
                    fixed: true,
                    color: '#FF6B6B'  // Red color to indicate pinned
                });
            }
        }
    });
    
    // Right-click context menu for pinning (optional)
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

    // Update the size of the final topic node to indicate message received
    const finalNodeId = topicParts.join('/');
    const finalNode = nodes.get(finalNodeId);
    nodes.update({ id: finalNodeId, size: finalNode.size + 5 });
    setTimeout(() => {
        nodes.update({ id: finalNodeId, size: finalNode.size });
    }, 1000);
}

socket.on('mqtt_message', function(data) {
    updateMessageList(data);
    messageCount++;
    updateNetwork(data);
    updateTopicFilter(data.topic);
});

function getRandomColor() {
    const letters = '0123456789ABCDEF';
    let color = '#';
    for (let i = 0; i < 6; i++) {
        color += letters[Math.floor(Math.random() * 16)];
    }
    return color;
}

document.getElementById('publish-form').addEventListener('submit', function(e) {
    e.preventDefault();
    const topic = document.getElementById('topic').value;
    const message = document.getElementById('message').value;
    
    fetch('/publish', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `topic=${encodeURIComponent(topic)}&message=${encodeURIComponent(message)}`
    });

    document.getElementById('topic').value = '';
    document.getElementById('message').value = '';
});

function updateStats() {
    fetch('/stats')
        .then(response => response.json())
        .then(data => {
            document.getElementById('connection-count').textContent = data.connection_count;
            document.getElementById('topic-count').textContent = data.topic_count;
            document.getElementById('message-count').textContent = data.message_count;
        });
}

function updateTopicFilter(newTopic) {
    const topicFilter = document.getElementById('topic-filter');
    if (!Array.from(topicFilter.options).some(option => option.value === newTopic)) {
        const option = document.createElement('option');
        option.value = newTopic;
        option.textContent = newTopic;
        topicFilter.appendChild(option);
    }
}

function loadTopicsFromAPI() {
    fetch('/api/topics')
        .then(response => response.json())
        .then(data => {
            const topicFilter = document.getElementById('topic-filter');
            
            // Clear existing options except "All Topics"
            const allTopicsOption = topicFilter.querySelector('option[value="all"]');
            topicFilter.innerHTML = '';
            if (allTopicsOption) {
                topicFilter.appendChild(allTopicsOption);
            } else {
                // Create "All Topics" option if it doesn't exist
                const option = document.createElement('option');
                option.value = 'all';
                option.textContent = 'All Topics';
                topicFilter.appendChild(option);
            }
            
            // Add topics from API (sorted by most recent)
            data.topics.forEach(topic => {
                const option = document.createElement('option');
                option.value = topic.topic;
                option.textContent = `${topic.topic} (${topic.message_count})`;
                topicFilter.appendChild(option);
            });
            
            console.log(`Loaded ${data.topics.length} topics from API`);
        })
        .catch(error => {
            console.error('Error loading topics:', error);
        });
}

document.getElementById('topic-filter').addEventListener('change', function(e) {
    topicFilter = e.target.value;
    loadFilteredMessages();
});

function loadFilteredMessages(customFilters = {}) {
    const messageList = document.getElementById('message-list');
    messageList.innerHTML = '<div class="loading text-center p-4">Loading messages...</div>';
    
    // Build API query parameters
    let queryParams = new URLSearchParams();
    queryParams.append('limit', '50'); // Show last 50 messages
    
    // Add topic filter
    if (topicFilter && topicFilter !== 'all') {
        queryParams.append('topic', topicFilter);
    }
    
    // Add custom filters
    Object.entries(customFilters).forEach(([key, value]) => {
        if (value) queryParams.append(key, value);
    });
    
    fetch(`/api/messages?${queryParams.toString()}`)
        .then(response => response.json())
        .then(data => {
            messageList.innerHTML = '';
            
            if (data.messages.length === 0) {
                messageList.innerHTML = '<div class="no-messages text-center p-4 text-gray-400">No messages found for current filter</div>';
                return;
            }
            
            // Display filtered messages
            data.messages.forEach(message => {
                const messageElement = document.createElement('div');
                messageElement.className = 'message-item bg-gray-700 p-3 rounded mb-2 hover:bg-gray-600 transition-colors';
                
                const timestamp = new Date(message.timestamp).toLocaleTimeString();
                const payload = message.payload.length > 200 ? 
                    message.payload.substring(0, 200) + '...' : message.payload;
                
                // Pretty print JSON if possible
                let formattedPayload = payload;
                try {
                    const parsed = JSON.parse(payload);
                    formattedPayload = JSON.stringify(parsed, null, 2);
                } catch (e) {
                    // Keep original payload if not JSON
                }
                
                messageElement.innerHTML = `
                    <div class="flex justify-between items-start mb-2">
                        <span class="topic text-blue-400 font-medium">${message.topic}</span>
                        <span class="timestamp text-gray-400 text-sm">${timestamp}</span>
                    </div>
                    <div class="message-payload text-gray-200 text-sm whitespace-pre-wrap">${formattedPayload}</div>
                `;
                
                messageList.appendChild(messageElement);
            });
            
            // Update filter status
            const statusElement = messageList.parentElement.querySelector('.filter-status');
            if (statusElement) statusElement.remove();
            
            const status = document.createElement('div');
            status.className = 'filter-status text-sm text-gray-400 mb-3 flex justify-between items-center';
            status.innerHTML = `
                <span>Showing ${data.messages.length} of ${data.total} messages</span>
                ${Object.keys(customFilters).length > 0 || (topicFilter && topicFilter !== 'all') ? 
                    '<span class="text-yellow-400">🔍 Filtered</span>' : ''}
            `;
            messageList.parentElement.insertBefore(status, messageList);
            
        })
        .catch(error => {
            console.error('Error loading messages:', error);
            messageList.innerHTML = '<div class="error text-center p-4 text-red-400">Error loading messages</div>';
        });
}

function setupAdvancedSearchHandlers() {
    // Apply Filters Button
    document.getElementById('apply-filters-btn').addEventListener('click', function() {
        const filters = {
            content: document.getElementById('content-search').value,
            regex_topic: document.getElementById('regex-topic').value,
            json_path: document.getElementById('json-path').value,
            json_value: document.getElementById('json-value').value,
            hours: document.getElementById('time-filter').value
        };
        
        // Remove empty filters
        Object.keys(filters).forEach(key => {
            if (!filters[key]) delete filters[key];
        });
        
        loadFilteredMessages(filters);
    });
    
    // Clear Filters Button
    document.getElementById('clear-filters-btn').addEventListener('click', function() {
        document.getElementById('topic-filter').value = 'all';
        document.getElementById('content-search').value = '';
        document.getElementById('regex-topic').value = '';
        document.getElementById('json-path').value = '';
        document.getElementById('json-value').value = '';
        document.getElementById('time-filter').value = '';
        topicFilter = 'all';
        loadFilteredMessages();
    });
    
    // Load Filter Presets
    loadFilterPresets();
    
    // Load Preset Button
    document.getElementById('load-preset-btn').addEventListener('click', function() {
        const presetName = document.getElementById('preset-select').value;
        if (!presetName) {
            alert('Please select a preset to load');
            return;
        }
        
        fetch(`/api/filter-presets/${encodeURIComponent(presetName)}/use`, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Apply filters to UI
                const filters = data.filters;
                document.getElementById('content-search').value = filters.content || '';
                document.getElementById('regex-topic').value = filters.regex_topic || '';
                document.getElementById('json-path').value = filters.json_path || '';
                document.getElementById('json-value').value = filters.json_value || '';
                document.getElementById('time-filter').value = filters.hours || '';
                
                if (filters.topic) {
                    document.getElementById('topic-filter').value = filters.topic;
                    topicFilter = filters.topic;
                }
                
                // Apply the loaded filters
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
    
    // Save Preset Button
    document.getElementById('save-preset-btn').addEventListener('click', function() {
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
        
        // Remove empty filters
        Object.keys(filters).forEach(key => {
            if (!filters[key]) delete filters[key];
        });
        
        if (Object.keys(filters).length === 0) {
            alert('No filters to save');
            return;
        }
        
        fetch('/api/filter-presets', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: name,
                description: description,
                filters: filters
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Filter preset saved successfully!');
                loadFilterPresets(); // Refresh preset list
            } else {
                alert('Error saving preset: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error saving preset:', error);
            alert('Error saving preset');
        });
    });
    
    // Fullscreen and reset buttons for network
    document.getElementById('fullscreen-btn').addEventListener('click', function() {
        const networkDiv = document.getElementById('network-visualization');
        if (networkDiv.requestFullscreen) {
            networkDiv.requestFullscreen();
        } else if (networkDiv.webkitRequestFullscreen) {
            networkDiv.webkitRequestFullscreen();
        } else if (networkDiv.msRequestFullscreen) {
            networkDiv.msRequestFullscreen();
        }
    });
    
    document.getElementById('reset-nodes-btn').addEventListener('click', function() {
        if (network) {
            network.fit();
            // Reset node positions by recreating the network
            const data = {
                nodes: nodes,
                edges: edges
            };
            network.setData(data);
        }
    });
}

function loadFilterPresets() {
    fetch('/api/filter-presets')
        .then(response => response.json())
        .then(data => {
            const presetSelect = document.getElementById('preset-select');
            
            // Clear existing options except first
            presetSelect.innerHTML = '<option value="">Select a preset...</option>';
            
            // Add presets
            data.presets.forEach(preset => {
                const option = document.createElement('option');
                option.value = preset.name;
                option.textContent = `${preset.name}${preset.description ? ' - ' + preset.description : ''}`;
                presetSelect.appendChild(option);
            });
        })
        .catch(error => {
            console.error('Error loading presets:', error);
        });
}



let debugBar;
let debugBarToggle;

function initDebugBar() {
    debugBar = document.createElement('div');
    debugBar.id = 'debug-bar';
    debugBar.style.display = 'none';
    document.body.appendChild(debugBar);

    debugBarToggle = document.createElement('button');
    debugBarToggle.id = 'debug-bar-toggle';
    debugBarToggle.innerHTML = '🐞 Debug';
    debugBarToggle.onclick = toggleDebugBar;
    document.body.appendChild(debugBarToggle);

    const closeButton = document.createElement('button');
    closeButton.id = 'debug-bar-close';
    closeButton.innerHTML = '&times;';
    closeButton.onclick = closeDebugBar;
    debugBar.appendChild(closeButton);

    updateDebugBar();
    setInterval(updateDebugBar, 1000);  // Update every second
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
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            pageLoadTime,
            domReadyTime,
        }),
    });
}

function updateDebugBar() {
    fetch('/debug-bar')
        .then(response => response.json())
        .then(data => {
            let content = '<div class="debug-content">';
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
            debugBar.appendChild(document.getElementById('debug-bar-close'));
        });
}
function toggleAdvancedSearch() {
    const content = document.getElementById('advanced-search-content');
    const icon = document.getElementById('search-toggle-icon');
    
    if (content.classList.contains('hidden')) {
        content.classList.remove('hidden');
        icon.textContent = '▼';
    } else {
        content.classList.add('hidden');
        icon.textContent = '▶';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    initChart();
    initNetwork();
    setInterval(updateChart, 1000);
    setInterval(updateStats, 5000);
    initDebugBar();
    trackClientPerformance();
    
    // Load existing topics from API
    loadTopicsFromAPI();
    // Refresh topics every 30 seconds
    setInterval(loadTopicsFromAPI, 30000);
    
    // Load initial messages
    loadFilteredMessages();
    
    // Setup advanced search UI
    setupAdvancedSearchHandlers();
});