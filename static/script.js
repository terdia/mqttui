const socket = io();
let messageChart;
let network;
let nodes;
let edges;

function initChart() {
    const ctx = document.getElementById('messageChart').getContext('2d');
    messageChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Messages per second',
                data: [],
                borderColor: 'rgb(75, 192, 192)',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

function updateMessageList(message) {
    const messageList = document.getElementById('message-list');
    const messageElement = document.createElement('div');
    messageElement.className = 'mb-2 p-2 bg-gray-100 dark:bg-gray-700 rounded';
    messageElement.textContent = `${message.topic}: ${message.payload}`;
    messageList.insertBefore(messageElement, messageList.firstChild);

    if (messageList.childElementCount > 100) {
        messageList.removeChild(messageList.lastChild);
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
    if (typeof vis === 'undefined') {
        console.error('Vis.js library not loaded');
        return;
    }

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
                size: 12,
                face: 'Tahoma'
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
                size: 20 - index * 2  // Gradually decrease size for subtopics
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

    // Focus on the relevant part of the network
    network.focus(finalNodeId, {
        scale: 1,
        animation: {
            duration: 1000,
            easingFunction: 'easeInOutQuad'
        }
    });
}

socket.on('mqtt_message', function(data) {
    updateMessageList(data);
    messageCount++;
    updateNetwork(data);
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

document.addEventListener('DOMContentLoaded', function() {
    initChart();
    initNetwork();
    setInterval(updateChart, 1000);
    setInterval(updateStats, 5000);
});