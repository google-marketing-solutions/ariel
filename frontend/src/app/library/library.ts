import { Component, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

interface VideoSpeaker {
  id: string;
  name: string;
  voice: string;
  gender: string;
}

interface VideoJob {
  video_id: string;
  name: string;
  url: string;
  download_url: string;
  created_at: number;
  original_language: string;
  translate_language: string;
  duration: number;
  speakers: VideoSpeaker[];
}

@Component({
  selector: 'app-library',
  imports: [RouterLink],
  templateUrl: './library.html',
  styleUrl: './library.scss'
})
export class Library implements OnInit {
  videos = signal<VideoJob[]>([]);
  isLoading = signal(true);
  error = signal<string | null>(null);

  ngOnInit() {
    this.fetchVideos();
  }

  async fetchVideos() {
    this.isLoading.set(true);
    try {
      const response = await fetch('/api/videos');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      this.videos.set(data);
    } catch (err: any) {
      console.error('Failed to load videos:', err);
      this.error.set(err.message || 'Failed to load videos');
    } finally {
      this.isLoading.set(false);
    }
  }

  formatDate(timestamp: number): string {
    if (!timestamp) return 'Date unknown';
    // The Python backend might send seconds or ms, usually seconds from GCS
    const date = new Date(timestamp > 1e11 ? timestamp : timestamp * 1000);
    return date.toLocaleString();
  }

  formatDuration(duration: number): string {
    const safeDuration = duration || 0;
    const minutes = Math.floor(safeDuration / 60);
    const seconds = Math.floor(safeDuration % 60);
    return `${minutes}m ${seconds}s`;
  }

  getSpeakersString(speakers: VideoSpeaker[]): string {
    if (!speakers || speakers.length === 0) return 'Unknown';
    const uniqueVoices = [...new Set(speakers.map(s => s.voice).filter(v => v))];
    return uniqueVoices.length > 0 ? uniqueVoices.join(', ') : 'Unknown';
  }

  isDeleteModalOpen = signal(false);
  pendingDeleteVideoId = signal<string | null>(null);
  isDeleting = signal(false);

  promptDelete(videoId: string) {
    this.pendingDeleteVideoId.set(videoId);
    this.isDeleteModalOpen.set(true);
  }

  cancelDelete() {
    this.isDeleteModalOpen.set(false);
    this.pendingDeleteVideoId.set(null);
  }

  async deleteVideo() {
    const videoId = this.pendingDeleteVideoId();
    if (!videoId) return;

    this.isDeleting.set(true);
    try {
      const response = await fetch(`/api/videos/${videoId}`, { method: 'DELETE' });
      if (response.ok) {
        // Refresh the list
        await this.fetchVideos();
        this.isDeleteModalOpen.set(false);
        this.pendingDeleteVideoId.set(null);
      } else {
        console.error('Failed to delete video');
        // A toast or inline error could be added here later if needed
      }
    } catch (err) {
      console.error('Error deleting video:', err);
    } finally {
      this.isDeleting.set(false);
    }
  }
}
