document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Handle file input display
    const fileInputs = document.querySelectorAll('.custom-file-input');
    fileInputs.forEach(input => {
        input.addEventListener('change', function(e) {
            const fileName = this.files[0]?.name || 'No file chosen';
            const fileLabel = this.nextElementSibling;
            if (fileLabel) {
                fileLabel.textContent = fileName;
            }
            
            // Show selected file name in UI
            const fileNameElement = document.getElementById(`${this.id}-name`);
            if (fileNameElement) {
                fileNameElement.textContent = fileName;
            }
        });
    });

    // Handle form submissions with AJAX
    const startMessagingForm = document.getElementById('messaging-form');
    if (startMessagingForm) {
        startMessagingForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Disable the submit button and show loading state
            const submitBtn = document.getElementById('start-session-btn');
            const originalBtnText = submitBtn.textContent;
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
            
            // First upload credentials file if it exists
            const credentialsFile = document.getElementById('credentials-file').files[0];
            const messageFile = document.getElementById('message-file').files[0];
            
            const formData = new FormData();
            
            // Process the credentials file first
            if (credentialsFile) {
                formData.append('credentials_file', credentialsFile);
                
                fetch('/upload_credentials', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Now process the message file
                        processMessageFile();
                    } else {
                        showAlert('danger', `Error uploading credentials: ${data.error}`);
                        resetButton();
                    }
                })
                .catch(error => {
                    showAlert('danger', `Error: ${error.message}`);
                    resetButton();
                });
            } else {
                // No credentials file, proceed with message file
                processMessageFile();
            }
            
            function processMessageFile() {
                if (messageFile) {
                    const msgFormData = new FormData();
                    msgFormData.append('message_file', messageFile);
                    
                    fetch('/upload_message', {
                        method: 'POST',
                        body: msgFormData
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            // Now start the messaging process
                            startMessaging();
                        } else {
                            showAlert('danger', `Error uploading message file: ${data.error}`);
                            resetButton();
                        }
                    })
                    .catch(error => {
                        showAlert('danger', `Error: ${error.message}`);
                        resetButton();
                    });
                } else {
                    // No message file, proceed with starting the session
                    startMessaging();
                }
            }
            
            function startMessaging() {
                const campaignData = new FormData(startMessagingForm);
                
                fetch('/start_messaging', {
                    method: 'POST',
                    body: campaignData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        showAlert('success', 'Messaging campaign started successfully!');
                        
                        // Update UI to show active campaign
                        document.getElementById('start-messaging-btn').style.display = 'none';
                        document.getElementById('stop-messaging-btn').style.display = 'block';
                        
                        // Start polling for status updates
                        if (data.campaign_id) {
                            pollCampaignStatus(data.campaign_id);
                        }
                    } else {
                        showAlert('danger', `Error starting messaging: ${data.error}`);
                    }
                    resetButton();
                })
                .catch(error => {
                    showAlert('danger', `Error: ${error.message}`);
                    resetButton();
                });
            }
            
            function resetButton() {
                submitBtn.disabled = false;
                submitBtn.textContent = originalBtnText;
            }
        });
    }
    
    // Handle stop messaging button
    const stopMessagingBtn = document.getElementById('stop-messaging-btn');
    if (stopMessagingBtn) {
        stopMessagingBtn.addEventListener('click', function() {
            // Disable the button and show loading state
            stopMessagingBtn.disabled = true;
            stopMessagingBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Stopping...';
            
            fetch('/stop_messaging', {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showAlert('info', 'Messaging stopped successfully');
                    
                    // Update UI
                    document.getElementById('start-messaging-btn').style.display = 'block';
                    document.getElementById('stop-messaging-btn').style.display = 'none';
                } else {
                    showAlert('danger', `Error stopping messaging: ${data.error}`);
                }
                // Re-enable the button
                stopMessagingBtn.disabled = false;
                stopMessagingBtn.textContent = 'STOP MESSAGING';
            })
            .catch(error => {
                showAlert('danger', `Error: ${error.message}`);
                stopMessagingBtn.disabled = false;
                stopMessagingBtn.textContent = 'STOP MESSAGING';
            });
        });
    }

    // Function to poll campaign status
    function pollCampaignStatus(campaignId) {
        const statusInterval = setInterval(() => {
            fetch(`/campaign_status/${campaignId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Update message count if available
                        if (data.messages_sent !== undefined) {
                            const messageCountElement = document.getElementById('message-count');
                            if (messageCountElement) {
                                messageCountElement.textContent = data.messages_sent;
                            }
                        }
                        
                        // If campaign is no longer active, update UI
                        if (!data.is_active) {
                            document.getElementById('start-messaging-btn').style.display = 'block';
                            document.getElementById('stop-messaging-btn').style.display = 'none';
                            clearInterval(statusInterval);
                        }
                    } else {
                        console.error("Error fetching campaign status:", data.error);
                    }
                })
                .catch(error => {
                    console.error("Error polling campaign status:", error);
                });
        }, 5000); // Poll every 5 seconds
    }

    // Helper function to show alerts
    function showAlert(type, message) {
        const alertsContainer = document.getElementById('alerts-container');
        if (!alertsContainer) return;
        
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.role = 'alert';
        
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        alertsContainer.appendChild(alertDiv);
        
        // Auto-close after 5 seconds
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alertDiv);
            bsAlert.close();
        }, 5000);
    }
});
