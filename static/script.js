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
            stabilization: false,
            barnesHut: {
                gravitationalConstant: -2000,
                springLength: 150,
                springConstant: 0.04,
            }
        },
        nodes: {
            font: {
                color: '#FFFFFF'
            }
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
        }
    };

    network = new vis.Network(container, data, options);
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

document.getElementById('topic-filter').addEventListener('change', function(e) {
    topicFilter = e.target.value;
    document.getElementById('message-list').innerHTML = '';
});



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
document.addEventListener('DOMContentLoaded', function() {
    initChart();
    initNetwork();
    setInterval(updateChart, 1000);
    setInterval(updateStats, 5000);
    initDebugBar();
    trackClientPerformance();
});