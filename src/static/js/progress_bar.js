function showProgress(message) {
    document.getElementById('progress-container').style.display = 'block';
    document.getElementById('progress-text').textContent = message;
    
    // Add dimming overlay
    let overlay = document.getElementById('dimming-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'dimming-overlay';
        overlay.style.position = 'fixed';
        overlay.style.top = document.getElementById('progress-container').offsetHeight + 'px';
        overlay.style.left = '0';
        overlay.style.width = '100%';
        overlay.style.height = '100%';
        overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
        overlay.style.zIndex = '999';
        document.body.appendChild(overlay);
    }
    
    // Disable all inputs
    disableAllInputs(true);
}

function updateProgress(percentage, message) {
    document.getElementById('progress').style.width = percentage + '%';
    document.getElementById('progress-text').textContent = message;
}

function hideProgress() {
    document.getElementById('progress-container').style.display = 'none';
    
    // Remove dimming overlay
    const overlay = document.getElementById('dimming-overlay');
    if (overlay) {
        overlay.remove();
    }
    
    // Re-enable all inputs
    disableAllInputs(false);
}

function disableAllInputs(disable) {
    // Disable form inputs
    const inputs = document.querySelectorAll('input, select, textarea, button');
    inputs.forEach(input => {
        input.disabled = disable;
    });

    // Disable map controls if they exist
    if (window.map) {
        const controls = window.map.controls;
        if (controls) {
            for (let i = 0; i < controls.length; i++) {
                const control = controls[i];
                if (disable) {
                    control.disable();
                } else {
                    control.enable();
                }
            }
        }
        // Disable/enable map zoom
        if (disable) {
            window.map.scrollWheelZoom.disable();
            window.map.dragging.disable();
            window.map.touchZoom.disable();
            window.map.doubleClickZoom.disable();
            window.map.boxZoom.disable();
            window.map.keyboard.disable();
        } else {
            window.map.scrollWheelZoom.enable();
            window.map.dragging.enable();
            window.map.touchZoom.enable();
            window.map.doubleClickZoom.enable();
            window.map.boxZoom.enable();
            window.map.keyboard.enable();
        }
    }
}

function initializeProgressBar(formId, progressUrl) {
    document.getElementById(formId).onsubmit = function(e) {
        e.preventDefault();
        var formData = new FormData(this);

        showProgress('Starting comic generation...');

        fetch(this.action, {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            if (data.task_id) {
                var eventSource = new EventSource(progressUrl + '?task_id=' + data.task_id);
                var retryCount = 0;
                var maxRetries = 3;

                eventSource.onmessage = function(event) {
                    var data = JSON.parse(event.data);
                    console.log('Received SSE data:', data);  // Debug log
                    if (data.progress !== undefined) {
                        updateProgress(data.progress, data.message);
                    }
                    if (data.success !== undefined) {
                        eventSource.close();
                        hideProgress();
                        if (data.success) {
                            document.getElementById('comic-generation-form').style.display = 'none';
                            document.getElementById('result').innerHTML = data.html;
                        } else {
                            document.getElementById('result').innerHTML = '<p class="error">' + (data.message || 'An error occurred. Please try again.') + '</p>';
                        }
                    }
                };

                eventSource.onerror = function(error) {
                    console.error('EventSource error:', error);  // Debug log
                    eventSource.close();
                    
                    if (retryCount < maxRetries) {
                        retryCount++;
                        console.log('Retrying connection... Attempt ' + retryCount);
                        setTimeout(function() {
                            eventSource = new EventSource(progressUrl + '?task_id=' + data.task_id);
                        }, 1000 * retryCount);  // Exponential backoff
                    } else {
                        hideProgress();
                        document.getElementById('result').innerHTML = '<p class="error">An error occurred while receiving updates. Please try again.</p>';
                    }
                };
            } else {
                throw new Error('No task ID received from server.');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            hideProgress();
            document.getElementById('result').innerHTML = '<p class="error">An error occurred: ' + error.message + '. Please try again.</p>';
        });
    };
}
