 // Current time display
 function updateTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('en-US', { hour12: false });
    document.getElementById('time').textContent = timeString;
}

function logout() {
    // Simple redirect for demonstration purposes
    window.location.href = '/logout';
}
