document.addEventListener('DOMContentLoaded', function() {
    // Function to add output to the terminal
    function addOutput(output, color='#0f0') { // Set default color to bright green
        const outputDiv = document.createElement('div');
        outputDiv.className = 'output';
        
        // Split the output by "pwned!" and process each part
        const parts = output.split(/(pwned!)/i); // Use a regex to keep "pwned!" in the results
        parts.forEach(part => {
            const span = document.createElement('span');
            if (part.toLowerCase() === "pwned!") {
                span.style.color = 'red'; // Set "pwned!" to red
                span.style.fontSize = '24px'; // Make "pwned!" appear in a bigger font size
                span.textContent = part;
            } else {
                span.style.color = color; // Set the color from the API or use default bright green
                span.textContent = part; // Normal text
            }
            outputDiv.appendChild(span);
        });

        const terminal = document.getElementById('terminal'); // Ensure you have an element with id="terminal" in your HTML
        terminal.appendChild(outputDiv);
        terminal.scrollTop = terminal.scrollHeight; // Scroll to the bottom of the terminal
    }
    
    var socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port + '/get');

    socket.on('message', function(data) {
        const color = data.color || '#0f0'; // Use color from data or default to bright green if undefined
        addOutput(data.data, color);
    });
});
