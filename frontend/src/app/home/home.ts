import { Component, OnInit, signal, computed, inject, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
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
  imports: [CommonModule, FormsModule, SpeakerModal],
  templateUrl: './home.html',
  styleUrl: './home.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '(document:click)': 'onDocumentClick($event)'
  }
})
export class Home implements OnInit {
  private router = inject(Router);

  gaLanguages = signal<Language[]>([]);
  previewLanguages = signal<Language[]>([]);

  speakers = signal<Speaker[]>([]);
  isSpeakerModalOpen = signal(false);
  speakerToEdit = signal<Speaker | null>(null);

  useProModel = signal(false);
  adjustSpeed = signal(false);

  selectedVideoFile = signal<File | null>(null);
  videoPreviewUrl = signal<string | null>(null);

  originalLanguage = signal<string>('');
  translationLanguage = signal<string>('');
  geminiInstructions = signal<string>('');

  isOriginalOpen = signal(false);
  isTranslationOpen = signal(false);

  toggleOriginal(event: MouseEvent) {
    if (this.isProcessing() || this.isPreprocessing()) return;
    this.isOriginalOpen.set(!this.isOriginalOpen());
    if (this.isOriginalOpen()) {
      this.isTranslationOpen.set(false);
    }
  }

  dropdownPosition = signal<'bottom' | 'top'>('bottom');

  toggleTranslation(event: MouseEvent) {
    if (this.isProcessing() || this.isPreprocessing()) return;
    this.isTranslationOpen.set(!this.isTranslationOpen());
    if (this.isTranslationOpen()) {
      this.isOriginalOpen.set(false);
      
      const target = event.currentTarget as HTMLElement;
      if (target) {
        const rect = target.getBoundingClientRect();
        const spaceBelow = window.innerHeight - rect.bottom;
        // 250px is the max-height of the dropdown + some padding
        if (spaceBelow < 280 && rect.top > 280) {
          this.dropdownPosition.set('top');
        } else {
          this.dropdownPosition.set('bottom');
        }
      }
    } else {
      this.searchLanguage.set('');
    }
  }

  searchLanguage = signal<string>('');

  filteredGaLanguages = computed(() => {
    const query = this.searchLanguage().toLowerCase().trim();
    if (!query) return this.gaLanguages();
    return this.gaLanguages().filter(lang => lang.name.toLowerCase().includes(query));
  });

  filteredPreviewLanguages = computed(() => {
    const query = this.searchLanguage().toLowerCase().trim();
    if (!query) return this.previewLanguages();
    return this.previewLanguages().filter(lang => lang.name.toLowerCase().includes(query));
  });

  originalLanguageLabel = computed(() => {
    const code = this.originalLanguage();
    if (!code) return 'Please select...';
    const match = [...this.gaLanguages(), ...this.previewLanguages()].find(l => l.code === code);
    return match ? match.name : 'Please select...';
  });

  translationLanguageLabel = computed(() => {
    const code = this.translationLanguage();
    if (!code) return 'Please select...';
    const match = [...this.gaLanguages(), ...this.previewLanguages()].find(l => l.code === code);
    return match ? match.name : 'Please select...';
  });

  isProcessing = signal(false);

  step = signal(1); // 1 = Upload, 2 = Configure
  isPreprocessing = signal(false);
  processingMessage = signal('Processing...');
  private processingInterval: any;

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
    this.speakerToEdit.set(null);
    this.isSpeakerModalOpen.set(true);
  }

  editSpeaker(speaker: Speaker) {
    this.speakerToEdit.set(speaker);
    this.isSpeakerModalOpen.set(true);
  }

  closeSpeakerModal() {
    this.isSpeakerModalOpen.set(false);
    this.speakerToEdit.set(null);
  }

  onSpeakerAdded(speaker: Speaker) {
    const target = this.speakerToEdit();
    if (target) {
      this.speakers.update(speakers => speakers.map(s => s.id === target.id ? speaker : s));
    } else {
      this.speakers.update(speakers => [...speakers, speaker]);
    }
    this.speakerToEdit.set(null);
  }

  removeSpeaker(speakerId: string) {
    this.speakers.update(speakers => speakers.filter(s => s.id !== speakerId));
  }

  triggerFileInput() {
    const fileInput = document.getElementById('video-input') as HTMLInputElement;
    if (fileInput) {
      fileInput.click();
    }
  }

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.handleFile(input.files[0]);
    }
  }

  onDragOver(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
    // Optional: Add some visual styling here for drag over
  }

  onDrop(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();

    if (event.dataTransfer?.files && event.dataTransfer.files.length > 0) {
      const file = event.dataTransfer.files[0];
      if (file.type.startsWith('video/')) {
        this.handleFile(file);
      }
    }
  }

  private handleFile(file: File) {
    this.selectedVideoFile.set(file);

    const reader = new FileReader();
    reader.onload = (e) => {
      this.videoPreviewUrl.set(e.target?.result as string);
    };
    reader.readAsDataURL(file);
  }

  removeVideo() {
    this.videoPreviewUrl.set(null);
    this.selectedVideoFile.set(null);
    this.step.set(1);
    this.originalLanguage.set('');
    this.translationLanguage.set('');
    this.speakers.set([]);
    // Reset file input so selecting the same file triggers 'change' event again
    const fileInput = document.getElementById('video-input') as HTMLInputElement;
    if (fileInput) {
      fileInput.value = '';
    }
  }

  isFormValid(): boolean {
    return this.step() === 2 &&
      !!this.selectedVideoFile() &&
      this.originalLanguage() !== '' &&
      this.translationLanguage() !== '' &&
      this.speakers().length > 0;
  }

  async processVideo() {
    const videoFile = this.selectedVideoFile();
    if (!videoFile || !this.translationLanguage()) return;

    this.isPreprocessing.set(true);
    this.processingMessage.set('Uploading video...');

    const messages = [
      { time: 4000, text: 'Analyzing audio...' },
      { time: 10000, text: 'Extracting speech...' },
      { time: 20000, text: 'Translating...' },
      { time: 35000, text: 'Synthesizing voice...' },
      { time: 60000, text: 'Generating utterances...' },
      { time: 120000, text: 'Almost done...' }
    ];

    const startTime = Date.now();
    this.processingInterval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const nextMessage = [...messages].reverse().find(m => elapsed >= m.time);
      if (nextMessage) {
        this.processingMessage.set(nextMessage.text);
      }
    }, 1000);

    const formData = new FormData();
    formData.append('video', videoFile);
    formData.append('translate_language', this.translationLanguage());
    formData.append('use_pro_model', this.useProModel().toString());

    try {
      console.log('Sending request to /process...');
      const response = await fetch('/process', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      console.log('Received result from backend:', result);

      if (result.video_id) {
        this.router.navigate(['/editor'], { state: { from: 'home' }, queryParams: { video_id: result.video_id } });
      }
    } catch (error) {
      console.error('Failed to process video:', error);
    } finally {
      clearInterval(this.processingInterval);
      this.isPreprocessing.set(false);
      this.processingMessage.set('Processing...');
    }
  }

  onDocumentClick(event: MouseEvent) {
    const target = event.target as HTMLElement;
    if (!target.closest('.custom-select')) {
      if (this.isOriginalOpen()) this.isOriginalOpen.set(false);
      if (this.isTranslationOpen()) {
        this.isTranslationOpen.set(false);
        this.searchLanguage.set('');
      }
    }
  }
}
