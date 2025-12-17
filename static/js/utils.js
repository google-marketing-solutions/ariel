export function showToast(message, type = 'error') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;

    container.appendChild(toast);

    // Trigger the animation
    setTimeout(() => {
        toast.classList.add('show');
    }, 100);

    // Hide the toast after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        // Remove the element after the transition is complete
        setTimeout(() => {
            container.removeChild(toast);
        }, 500);
    }, 6000);
}

export function checkOverlap(utterance, allUtterances) {
    const messages = [];
    for (const other of allUtterances) {
        if (utterance.id === other.id || other.removed) continue;

        // Check for overlap
        if (utterance.translated_start_time < other.translated_end_time && other.translated_start_time < utterance.translated_end_time) {
            messages.push(`Translated time overlaps with another utterance.`);
            break; // No need to check further
        }
    }
    return messages;
}
