document.addEventListener('DOMContentLoaded', async () => {
  const libraryGrid = document.getElementById('video-library-grid');

  function formatDate(dateInput) {
    if (!dateInput) return 'Date unknown';

    let date;
    if (typeof dateInput === 'number') {
      date = new Date(dateInput * 1000);
    } else {
      date = new Date(dateInput);
    }
    return date.toLocaleString();
  }

  try {
    const response = await fetch('/api/videos');
    if (!response.ok) throw new Error("Failed to fetch videos");
    const videos = await response.json();

    libraryGrid.innerHTML = '';

    if (videos.length === 0) {
      libraryGrid.innerHTML = `
                <div class="col-12 text-center mt-5">
                    <p class="text-muted">No videos found. Go back home to create one!</p>
                </div>
            `;
      return;
    }

    videos.forEach(video => {
      const dateStr = formatDate(video.created_at);
      const safeDuration = video.duration || 0;
      const minutes = Math.floor(safeDuration / 60);
      const seconds = Math.floor(safeDuration % 60);
      const durationStr = `${minutes}m ${seconds}s`;

      let speakerDisplay = "Unknown";

      if (video.speakers && video.speakers.length > 0) {
        const allVoices = video.speakers.map(s => s.voice).filter(v => v);
        const uniqueVoices = [...new Set(allVoices)];
        if (uniqueVoices.length > 0) {
          speakerDisplay = uniqueVoices.join(", ");
        }
      }
      const cardHtml = `
                <div class="col-md-10 offset-md-1 mb-3">
                    <div class="card shadow-sm h-100 border-0" style="background-color: #444;">
                        <div class="row g-0 align-items-center">
                            
                            <div class="col-md-4 col-sm-5 bg-black d-flex justify-content-center rounded-start" style="min-height: 140px;">
                                <video controls class="w-100" style="max-height: 180px; object-fit: contain;" preload="metadata">
                                    <source src="${video.url}" type="video/mp4">
                                </video>
                            </div>
                            
                            <div class="col-md-8 col-sm-7">
                                <div class="card-body">
                                    <div class="d-flex justify-content-between align-items-start mb-2">
                                        <div class="me-3" style="min-width: 0;">
                                            <h6 class="card-title text-truncate mb-1 fw-bold text-white" title="${video.name}">
                                                ${video.name}
                                            </h6>
                                            <p class="card-text text-white small mb-0">
                                                <i class="bi bi-clock"></i> ${dateStr}
                                            </p>
                                        </div>
                                        
                                        <a href="${video.download_url}" download="${video.name}" class="btn btn-sm btn-primary text-white text-nowrap">
                                            <i class="bi bi-download"></i> Download
                                        </a>
                                    </div>
                                    
                                    <div class="d-flex flex-wrap gap-2">
                                        <span class="badge bg-secondary border border-secondary text-white" title="Original -> Translated">
                                            <i class="bi bi-translate"></i> ${video.original_language || '?'} &rarr; ${video.translate_language || '?'}
                                        </span>
                                        <span class="badge bg-secondary border border-secondary text-white">
                                            <i class="bi bi-person"></i> ${speakerDisplay}
                                        </span>
                                        <span class="badge bg-secondary border border-secondary text-white">
                                            <i class="bi bi-stopwatch"></i> ${durationStr}
                                        </span>
                                    </div>

                                </div>
                            </div>

                        </div>
                    </div>
                </div>
            `;
      libraryGrid.insertAdjacentHTML('beforeend', cardHtml);
    });
  } catch (error) {
    console.error("Error loading library:", error);
    libraryGrid.innerHTML = `<div class="alert alert-danger">Error loading videos. Check console.</div>`;
  }
});