document.addEventListener('DOMContentLoaded', function() {
    // UI Elements
    const messagingForm = document.getElementById('messaging-form');
    const credentialsFileInput = document.getElementById('credentials-file');
    const credentialsFileName = document.getElementById('credentials-file-name');
    const messageText = document.getElementById('message_text');
    const startMessageBtn = document.getElementById('start-messaging-btn');
    const stopMessageBtn = document.getElementById('stop-messaging-btn');
    const startSessionBtn = document.getElementById('start-session-btn');
    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');
    const messageCount = document.getElementById('message-count');
    
    // State variables
    let activeCampaignId = null;
    let statusPollInterval = null;
    let credentialsFile = null;
    
    // Initialize UI
    stopMessageBtn.disabled = true;
    
    // File input handling
    credentialsFileInput.addEventListener('change', function(e) {
        credentialsFile = e.target.files[0];
        if (credentialsFile) {
            credentialsFileName.textContent = credentialsFile.name;
        } else {
            credentialsFileName.textContent = 'No file chosen';
        }
    });
    
    // Start messaging button
    startMessageBtn.addEventListener('click', function() {
        if (messagingForm.checkValidity()) {
            startMessaging();
        } else {
            showAlert('warning', 'Please fill in all required fields');
            messagingForm.reportValidity();
        }
    });
    
    // Stop messaging button
    stopMessageBtn.addEventListener('click', function() {
        stopMessaging();
    });
    
    // Form submission
    messagingForm.addEventListener('submit', function(e) {
        e.preventDefault();
        if (messagingForm.checkValidity()) {
            startMessaging();
        }
    });
    
    // Function to start messaging
    async function startMessaging() {
        try {
            // Check if credentials file is uploaded
            if (!credentialsFile) {
                showAlert('warning', 'Please upload your credentials.json file');
                return;
            }
            
            // Check if message text is provided
            if (!messageText.value.trim()) {
                showAlert('warning', 'Please enter a message text');
                return;
            }
            
            // Prepare form data
            const formData = new FormData();
            formData.append('credentials_file', credentialsFile);
            formData.append('target_number', document.getElementById('target_number').value);
            formData.append('target_type', document.getElementById('target_type').value);
            formData.append('delay_time', document.getElementById('delay_time').value);
            formData.append('message_text', messageText.value);
            
            // Disable buttons during request
            startMessageBtn.disabled = true;
            startSessionBtn.disabled = true;
            
            // Make API request
            const response = await fetch('/direct_messaging', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                showAlert('success', 'Messaging started successfully');
                activeCampaignId = result.campaign_id;
                
                // Update UI
                startMessageBtn.disabled = true;
                stopMessageBtn.disabled = false;
                startSessionBtn.disabled = true;
                
                // Update status indicators
                statusDot.classList.add('active');
                statusText.textContent = 'Campaign active';
                
                // Start polling for status updates
                if (statusPollInterval) {
                    clearInterval(statusPollInterval);
                }
                statusPollInterval = setInterval(
                    () => pollCampaignStatus(activeCampaignId), 
                    3000
                );
            } else {
                showAlert('danger', `Error: ${result.error}`);
                resetButtons();
            }
            
        } catch (error) {
            console.error('Error:', error);
            showAlert('danger', 'An error occurred. Please try again.');
            resetButtons();
        }
    }
    
    // Function to stop messaging
    async function stopMessaging() {
        try {
            // Disable stop button during request
            stopMessageBtn.disabled = true;
            
            // Make API request
            const response = await fetch('/stop_direct_messaging', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    campaign_id: activeCampaignId
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                showAlert('info', 'Messaging stopped successfully');
                resetButtons();
                
                // Update status indicators
                statusDot.classList.remove('active');
                statusText.textContent = 'Campaign stopped';
                
                // Stop polling
                if (statusPollInterval) {
                    clearInterval(statusPollInterval);
                    statusPollInterval = null;
                }
            } else {
                showAlert('danger', `Error: ${result.error}`);
                stopMessageBtn.disabled = false;
            }
            
        } catch (error) {
            console.error('Error:', error);
            showAlert('danger', 'An error occurred. Please try again.');
            stopMessageBtn.disabled = false;
        }
    }
    
    // Function to poll campaign status
    async function pollCampaignStatus(campaignId) {
        if (!campaignId) return;
        
        try {
            const response = await fetch(`/campaign_status/${campaignId}`);
            const result = await response.json();
            
            if (result.success) {
                // Update message count
                messageCount.textContent = result.messages_sent;
                
                // Check if campaign is still active
                if (!result.is_active) {
                    statusDot.classList.remove('active');
                    statusText.textContent = 'Campaign completed';
                    resetButtons();
                    
                    // Stop polling
                    if (statusPollInterval) {
                        clearInterval(statusPollInterval);
                        statusPollInterval = null;
                    }
                }
            }
        } catch (error) {
            console.error('Error polling status:', error);
        }
    }
    
    // Reset buttons to initial state
    function resetButtons() {
        startMessageBtn.disabled = false;
        stopMessageBtn.disabled = true;
        startSessionBtn.disabled = false;
    }
    
    // Function to show alert message
    function showAlert(type, message) {
        const alertsContainer = document.getElementById('alerts-container');
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.role = 'alert';
        
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        alertsContainer.appendChild(alertDiv);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            alertDiv.remove();
        }, 5000);
    }
});