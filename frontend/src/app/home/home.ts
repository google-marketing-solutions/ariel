import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { SpeakerModal } from '../_components/speaker-modal/speaker-modal';

export interface Language {
  name: string;
  code: string;
  readiness: string;
}

export interface Speaker {
  id: string;
  name: string;
  voice: string;
  voiceName: string;
  gender: string;
}

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, SpeakerModal],
  templateUrl: './home.html',
  styleUrl: './home.scss',
})
export class Home implements OnInit {
  gaLanguages = signal<Language[]>([]);
  previewLanguages = signal<Language[]>([]);

  speakers = signal<Speaker[]>([]);
  isSpeakerModalOpen = signal(false);

  ngOnInit() {
    this.fetchLanguages();
  }

  async fetchLanguages() {
    try {
      const response = await fetch('languages.json');
      const languages: Language[] = await response.json();

      this.gaLanguages.set(languages.filter(lang => lang.readiness === 'GA'));
      this.previewLanguages.set(languages.filter(lang => lang.readiness === 'Preview'));
    } catch (error) {
      console.error('Failed to fetch languages:', error);
    }
  }

  openSpeakerModal() {
    console.log('Opening speaker modal...');
    this.isSpeakerModalOpen.set(true);
  }

  closeSpeakerModal() {
    console.log('Closing speaker modal...');
    this.isSpeakerModalOpen.set(false);
  }

  onSpeakerAdded(speaker: Speaker) {
    this.speakers.update(speakers => [...speakers, speaker]);
  }

  removeSpeaker(speakerId: string) {
    this.speakers.update(speakers => speakers.filter(s => s.id !== speakerId));
  }
}
