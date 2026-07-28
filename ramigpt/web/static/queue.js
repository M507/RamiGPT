// Function to add text to the corresponding textarea
function addToQueue(queueId) {
    const input = document.getElementById(`${queueId}-input`);
    const value = input.value.trim();

    if (value) {
        const queueTable = document.querySelector(`#${queueId} .queue-table tbody`);

        // Create a new row and add the text
        const row = document.createElement("tr");
        row.innerHTML = `<td>${value}</td>`;
        row.addEventListener("click", function () {
            deleteFromQueue(queueId, row, value);
        });

        queueTable.appendChild(row);

        // Determine endpoint dynamically
        const endpoints = {
            "queue1": "/fact",
            "queue2": "/hint",
            "queue3": "/avoid",
            "queue4": "/demo"
        };
        const endpoint = endpoints[queueId];

        if (endpoint) {
            sendRequest(endpoint, value, "POST"); // Send POST request
        }

        input.value = ''; // Clear input field
    }
}

// Function to remove a row from the table and send a DELETE request
function deleteFromQueue(queueId, row, value) {
    const queueTable = document.querySelector(`#${queueId} .queue-table tbody`);

    // Remove the row from the UI
    queueTable.removeChild(row);

    // Determine endpoint dynamically
    const endpoints = {
        "queue1": "/fact",
        "queue2": "/hint",
        "queue3": "/avoid",
        "queue4": "/demo"
    };
    const endpoint = endpoints[queueId];

    if (endpoint) {
        sendRequest(endpoint, value, "DELETE"); // Send DELETE request
    }
}

// General function to send a request to the backend
function sendRequest(endpoint, text, method) {
    fetch(endpoint, {
        method: method,
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ text: text })
    })
    .then(response => response.json())
    .then(data => {
        console.log(`${method} Success:`, data.message);
    })
    .catch(error => {
        console.error(`${method} Error:`, error);
    });
}

// Attach event listeners to each input field for adding entries on 'Enter'
document.querySelectorAll('.queue input').forEach(input => {
    input.addEventListener('keydown', function(event) {
        if (event.key === 'Enter') {
            event.preventDefault();
            const queueId = this.parentElement.id;
            addToQueue(queueId);
        }
    });
});

// Matrix background effect
function setupMatrixBackground() {
    const canvas = document.createElement('canvas');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    document.getElementById('matrix-canvas').appendChild(canvas);
    
    const ctx = canvas.getContext('2d');
    const characters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789$+-*/=%"\'#&_(),.;:?!\\|{}<>[]^~';
    const columns = Math.floor(canvas.width / 15);
    const drops = [];
    
    for (let i = 0; i < columns; i++) {
        drops[i] = Math.floor(Math.random() * canvas.height);
    }
    
    function draw() {
        ctx.fillStyle = 'rgba(0, 0, 0, 0.05)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        ctx.fillStyle = '#0f0';
        ctx.font = '15px Courier New';
        
        for (let i = 0; i < drops.length; i++) {
            const text = characters.charAt(Math.floor(Math.random() * characters.length));
            ctx.fillText(text, i * 15, drops[i] * 15);
            
            if (drops[i] * 15 > canvas.height && Math.random() > 0.975) {
                drops[i] = 0;
            }
            
            drops[i]++;
        }
    }
    
    setInterval(draw, 35);
}
