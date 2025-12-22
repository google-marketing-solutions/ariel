/*
* Copyright 2025 Google LLC
*
* Licensed under the Apache License, Version 2.0 (the "License"); you may not
* use this file except in compliance with the License. You may obtain a copy
* of the License at
*
*   http://www.apache.org/licenses/LICENSE-2.0

* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
* WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
* License for the specific language governing permissions and limitations
* under the License.
*/

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
    if (
      utterance.translated_start_time < other.translated_end_time &&
      other.translated_start_time < utterance.translated_end_time
    ) {
      messages.push('Translated time overlaps with another utterance.');
      break; // No need to check further
    }
  }
  return messages;
}
