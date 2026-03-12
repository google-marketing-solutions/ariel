import { Component, EventEmitter, OnInit, Output, Input, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Speaker } from '../../home/home';

export interface Voice {
  name: string;
  gender: string;
  url?: string;
}

@Component({
  selector: 'app-speaker-modal',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './speaker-modal.html',
  styleUrl: './speaker-modal.scss',
})
export class SpeakerModal implements OnInit {
  @Output() close = new EventEmitter<void>();
  @Output() speakerAdded = new EventEmitter<Speaker>();
  @Input() speakerCount = 0;

  speakerName = signal('');
  searchQuery = signal('');
  genderFilter = signal<'all' | 'Male' | 'Female'>('all');

  voices = signal<Voice[]>([]);

  filteredVoices = computed(() => {
    const query = this.searchQuery().toLowerCase();
    const filter = this.genderFilter();

    return this.voices().filter(voice => {
      const matchesName = voice.name.toLowerCase().includes(query);
      const matchesGender = filter === 'all' || voice.gender === filter;
      return matchesName && matchesGender;
    });
  });

  currentlyPlayingAudio: HTMLAudioElement | null = null;
  currentlyPlayingVoiceName = signal<string | null>(null);

  ngOnInit() {
    this.fetchVoices();
  }

  async fetchVoices() {
    try {
      const response = await fetch('voices.json');
      const data = await response.json();
      this.voices.set(data.voices);
    } catch (error) {
      console.error('Failed to fetch voices:', error);
    }
  }

  togglePlay(voice: Voice, event: Event) {
    event.stopPropagation();

    // If clicking the currently playing voice, pause it
    if (this.currentlyPlayingVoiceName() === voice.name) {
      this.stopPlaying();
      return;
    }

    // Stop requested if another is playing
    if (this.currentlyPlayingAudio) {
      this.stopPlaying();
    }

    if (voice.url) {
      this.currentlyPlayingAudio = new Audio(voice.url);
      this.currentlyPlayingVoiceName.set(voice.name);

      this.currentlyPlayingAudio.addEventListener('ended', () => {
        this.stopPlaying();
      });

      this.currentlyPlayingAudio.play();
    }
  }

  stopPlaying() {
    if (this.currentlyPlayingAudio) {
      this.currentlyPlayingAudio.pause();
      this.currentlyPlayingAudio = null;
    }
    this.currentlyPlayingVoiceName.set(null);
  }

  selectVoice(voice: Voice) {
    this.stopPlaying();

    const customName = this.speakerName().trim() || `Speaker ${this.speakerCount + 1}`;

    const newSpeaker: Speaker = {
      id: `speaker_${Date.now()}`,
      name: customName,
      voice: voice.name,
      voiceName: voice.name,
      gender: voice.gender
    };

    this.speakerAdded.emit(newSpeaker);
    this.closeModal();
  }

  closeModal() {
    this.stopPlaying();
    this.close.emit();
  }
}
