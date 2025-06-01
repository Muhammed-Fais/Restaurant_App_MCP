const chatBox = document.getElementById('chat-box');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');

let conversation = []; // To hold conversation context locally

sendButton.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

function sendMessage() {
    const messageText = userInput.value.trim();
    if (messageText === '') return;

    appendMessage(messageText, 'user-message');
    conversation.push({ role: 'user', content: messageText });
    userInput.value = '';

    fetch('/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ messages: conversation }),
    })
    .then(response => response.json())
    .then(data => {
        if (data && data.length > 0) {
            const agentResponse = data[data.length -1]; // Get the last message from the agent
            appendMessage(agentResponse.content, 'agent-message');
            conversation.push(agentResponse); // Add agent's response to local context
        } else {
            appendMessage("Error: No response from agent", 'agent-message');
        }
    })
    .catch((error) => {
        console.error('Error:', error);
        appendMessage("Error communicating with the agent.", 'agent-message');
    });
}

function appendMessage(text, className) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', className);
    messageDiv.textContent = text;
    chatBox.appendChild(messageDiv);
    chatBox.scrollTop = chatBox.scrollHeight; // Scroll to the bottom
} 