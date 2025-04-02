// script.js
// WebSocket connection
const ws = new WebSocket('ws://localhost:8000/ws/chat');

// DOM elements
const chatMessages = document.getElementById('chatMessages');
const userInput = document.getElementById('userInput');
const sendButton = document.getElementById('sendButton');

// Auto-resize textarea
userInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});

// Handle WebSocket connection
ws.onopen = () => {
    console.log('Connected to WebSocket');
    sendButton.disabled = false;
    addMessage('Connected to the server. You can start chatting!', 'system');
};

ws.onclose = () => {
    console.log('Disconnected from WebSocket');
    sendButton.disabled = true;
    addMessage('Disconnected from the server. Please refresh the page.', 'system');
};

ws.onerror = (error) => {
    console.error('WebSocket error:', error);
    sendButton.disabled = true;
    addMessage('Error connecting to the server. Please check if the server is running.', 'system');
};

// Handle WebSocket message
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === 'response') {
        // For both streaming and non-streaming responses
        if (data.streaming) {
            // If streaming, update the ongoing message
            updateStreamingMessage(data.content);
        } else {
            // For final message, add it to chat and finalize any streaming message
            finalizeStreamingMessage();
            addMessage(data.content, 'assistant');
        }
    }
};

// Add message to chat
function addMessage(content, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;
    
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    messageContent.innerHTML = marked.parse(content);  // Marked parsing to render Markdown content
    
    messageDiv.appendChild(messageContent);
    chatMessages.appendChild(messageDiv);
    
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Initialize streaming message with typing effect
function initStreamingMessage() {
    // Remove any existing typing indicator
    removeTypingIndicator();

    // Create a new message div for the assistant's streaming message
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';

    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';

    // Create a cursor element to simulate typing
    const cursor = document.createElement('span');
    cursor.className = 'cursor';
    cursor.innerHTML = '|';

    // Initially, the message is empty, and only a cursor is visible
    messageContent.appendChild(document.createTextNode(''));
    messageContent.appendChild(cursor);

    messageDiv.appendChild(messageContent);
    chatMessages.appendChild(messageDiv);

    chatMessages.scrollTop = chatMessages.scrollHeight;
    return messageContent;
}

// Update the streaming message with new content
function updateStreamingMessage(content) {
    let currentStreamingMessage = document.querySelector('.message.assistant .message-content');
    
    if (!currentStreamingMessage) {
        currentStreamingMessage = initStreamingMessage();
    }

    currentStreamingMessage.childNodes[0].nodeValue = content;
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Finalize the streaming message (remove the cursor)
function finalizeStreamingMessage() {
    const streamingMessage = document.querySelector('.message.assistant .cursor');
    if (streamingMessage) {
        streamingMessage.remove();
    }
}

// Remove typing indicator
function removeTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) {
        indicator.remove();
    }
}

// Typing indicator (optional, can be implemented if needed)
function addTypingIndicator() {
    removeTypingIndicator(); // Remove any existing indicator

    const indicator = document.createElement('div');
    indicator.className = 'message assistant';
    indicator.id = 'typingIndicator';

    const content = document.createElement('div');
    content.className = 'typing-indicator';
    content.innerHTML = 'Typing...'; // Simple text indicator instead of dots

    indicator.appendChild(content);
    chatMessages.appendChild(indicator);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Handle sending user messages
sendButton.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    // Add user message to chat
    addMessage(message, 'user');

    // Clear input field
    userInput.value = '';
    userInput.style.height = 'auto';

    // Add typing indicator while waiting for response
    addTypingIndicator();

    try {
        // Send the message to the WebSocket server
        ws.send(JSON.stringify({ message }));
    } catch (error) {
        console.error('Error sending message:', error);
        removeTypingIndicator();
        addMessage('Error sending message to server.', 'system');
    }
}