document.getElementById('submitButton').addEventListener('click', async () => {
    const prompt = document.getElementById('promptInput').value.trim();
    const total = document.getElementById('totalInput').value;
    
    if (!prompt) {
        alert('Please enter a prompt.');
        return;
    }

    // Add user message to chat
    const chatBox = document.getElementById('chatBox');
    const userMessage = document.createElement('div');
    userMessage.className = 'message user';
    userMessage.textContent = prompt;
    chatBox.appendChild(userMessage);

    // Clear inputs
    document.getElementById('promptInput').value = '';
    document.getElementById('totalInput').value = '10';

    // Send request to backend
    try {
        const response = await fetch('/scrape', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt, total })
        });

        const data = await response.json();

        if (data.error) {
            const errorMessage = document.createElement('div');
            errorMessage.className = 'message bot';
            errorMessage.textContent = `Error: ${data.error}`;
            chatBox.appendChild(errorMessage);
        } else {
            // Display analysis
            const analysisMessage = document.createElement('div');
            analysisMessage.className = 'message bot';
            analysisMessage.textContent = `Based on your prompt, I recommend looking for jobs at ${data.business_type} in ${data.location}.`;
            chatBox.appendChild(analysisMessage);

            // Display results
            data.results.forEach(result => {
                const resultMessage = document.createElement('div');
                resultMessage.className = 'message result';
                resultMessage.innerHTML = `
                    <strong>${result['Business Name']}</strong><br>
                    <strong>Coordinates:</strong> ${result['Coordinates'] || 'Not found'}<br>
                    <strong>Phone:</strong> ${result['Phone Number'] || 'Not found'}<br>
                    <strong>Description:</strong> ${result['Description'] || 'Not available'}<br>
                    <strong>Job Suggestions:</strong><br><pre>${result['Job Suggestions']}</pre>
                `;
                chatBox.appendChild(resultMessage);
            });
        }

        // Scroll to bottom
        chatBox.scrollTop = chatBox.scrollHeight;
    } catch (error) {
        const errorMessage = document.createElement('div');
        errorMessage.className = 'message bot';
        errorMessage.textContent = 'An error occurred. Please try again.';
        chatBox.appendChild(errorMessage);
        chatBox.scrollTop = chatBox.scrollHeight;
    }
});