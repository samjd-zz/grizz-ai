function showProgress(message) {
    document.getElementById('progress-container').style.display = 'block';
    document.getElementById('progress-text').textContent = message;
}

function updateProgress(percentage, message) {
    document.getElementById('progress').style.width = percentage + '%';
    document.getElementById('progress-text').textContent = message;
}

function hideProgress() {
    document.getElementById('progress-container').style.display = 'none';
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
