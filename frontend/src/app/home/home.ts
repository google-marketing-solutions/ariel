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

  isProcessing = signal(false);

  step = signal(1);
  isPreprocessing = signal(false);

  constructor(private router: Router) { }

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
      this.translationLanguage() !== '';
  }

  async preprocessVideo() {
    const videoFile = this.selectedVideoFile();
    if (!videoFile) return;

    this.isPreprocessing.set(true);

    const formData = new FormData();
    formData.append('video', videoFile);
    formData.append('use_pro_model', this.useProModel().toString());

    try {
      console.log('Sending request to /preprocess...');
      const response = await fetch('/preprocess', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      console.log('Received result from backend:', result);

      if (result.original_language) {
        this.originalLanguage.set(result.original_language);
      }
      if (result.speakers && Array.isArray(result.speakers)) {
        const mappedSpeakers = result.speakers.map((s: any) => ({
          id: s.speaker_id,
          name: s.speaker_name || `Speaker ${s.speaker_id}`,
          voice: s.voice,
          voiceName: s.voice,
          gender: s.gender ? s.gender : 'neutral'
        }));
        this.speakers.set(mappedSpeakers);
      }
      this.step.set(2);
    } catch (error) {
      console.error('Failed to preprocess video:', error);
    } finally {
      this.isPreprocessing.set(false);
    }
  }

  async startProcessing() {
    if (!this.isFormValid()) return;

    this.isProcessing.set(true);

    const formData = new FormData();
    const videoFile = this.selectedVideoFile();
    if (videoFile) {
      formData.append('video', videoFile);
    }
    formData.append('original_language', this.originalLanguage());
    formData.append('translate_language', this.translationLanguage());
    formData.append('prompt_enhancements', this.geminiInstructions());
    formData.append('adjust_speed', this.adjustSpeed().toString());
    formData.append('use_pro_model', this.useProModel().toString());

    // Map speakers to format expected by backend
    const speakersToPost = this.speakers().map((s, index) => ({
      id: `speaker_${(index + 1).toString()}`,
      name: s.name,
      voice: s.voice,
      gender: s.gender,
    }));
    formData.append('speakers', JSON.stringify(speakersToPost));

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

      // Redirect to the Editor page
      if (result.video_id) {
        this.router.navigate(['/editor'], { queryParams: { video_id: result.video_id } });
      }
    } catch (error) {
      console.error('Failed to process video:', error);
    } finally {
      this.isProcessing.set(false);
    }
  }
}
