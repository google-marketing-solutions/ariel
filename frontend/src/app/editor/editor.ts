import { Component, OnInit, signal, computed, HostListener, ViewChild, ElementRef } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SpeakerModal } from '../_components/speaker-modal/speaker-modal';
import { Speaker } from '../home/home';

interface VideoSpeaker {
  speaker_id: string;
  name: string;
  speaker_name?: string;
  voice: string;
  gender: string;
}

interface VideoUtterance {
  id: string;
  original_text: string;
  translated_text: string;
  instructions: string;
  voice_instructions?: string;
  original_start_time: number;
  original_end_time: number;
  translated_start_time: number;
  translated_end_time: number;
  speaker: VideoSpeaker;
  audio_url?: string;
  duration?: number;
  // UI Only Derived bounds for cloned utterance tracks
  ui_original_start_time?: number;
  ui_original_end_time?: number;
}

interface VideoJob {
  video_id: string;
  original_language: string;
  translate_language: string;
  prompt_enhancements: string;
  speakers: VideoSpeaker[];
  utterances: VideoUtterance[];
  duration: number;
}

interface Language {
  name: string;
  code: string;
  readiness?: string;
}

export type PanelMode = 'timestamps' | 'speaker' | 'translation' | 'voice' | null;

@Component({
  selector: 'app-editor',
  standalone: true,
  imports: [CommonModule, FormsModule, SpeakerModal],
  templateUrl: './editor.html',
  styleUrl: './editor.scss'
})
export class Editor implements OnInit {
  videoId = signal<string | null>(null);
  videoUrl = signal<string | null>(null);
  videoData = signal<VideoJob | null>(null);
  isLoading = signal(true);
  error = signal<string | null>(null);

  // Audio elements for timeline
  originalAudio = new Audio();
  translatedAudio = new Audio();
  isPlayingOriginal = signal(false);
  isPlayingTranslated = signal(false);
  isPlayingSnippet = signal(false);
  isGeneratingAudio = signal(false);
  currentTime = signal(0);
  snippetStartTime = 0;

  // Audio elements for individual utterance snippet playback
  snippetAudio = new Audio();
  utteranceTimeoutId: any = null;
  activeAudioPlayback: { id: string; type: 'original' | 'translated' } | null = null;

  // Timeline dragging
  isDragging = signal(false);
  dragStartX = 0;
  dragInitialStartTime = 0;
  draggedUtteranceId = signal<string | null>(null);


  @ViewChild('timelineContainer') timelineContainer!: ElementRef<HTMLDivElement>;

  languages = signal<Language[]>([]);

  // UI State
  activeUtteranceId = signal<string | null>(null);
  activePanelMode = signal<PanelMode | null>(null);

  // Video Settings Editing State
  isEditingSettings = signal(false);
  private initialUtteranceState: VideoUtterance | null = null;
  editOriginalLanguage = signal<string>('');
  editTranslateLanguage = signal<string>('');
  editSpeakers = signal<VideoSpeaker[]>([]);
  gaLanguages = signal<Language[]>([]);
  previewLanguages = signal<Language[]>([]);

  // Speaker Modal State
  isSpeakerModalOpen = signal(false);
  speakerToEditId = signal<string | null>(null);

  constructor(
    private route: ActivatedRoute,
    private router: Router
  ) { }

  animationFrameId: number | null = null;

  ngOnInit() {
    const updateTimeLoop = () => {
      if (this.isPlayingOriginal()) {
        let currentVisualTime = this.originalAudio.currentTime;
        if (this.activeAudioPlayback?.type === 'original') {
          const activeU = this.videoData()?.utterances.find(u => u.id === this.activeAudioPlayback!.id);
          if (activeU && activeU.ui_original_start_time !== undefined) {
            const offset = activeU.ui_original_start_time - activeU.original_start_time;
            currentVisualTime += offset;
          }
        }
        this.currentTime.set(currentVisualTime);
      } else if (this.isPlayingTranslated()) {
        this.currentTime.set(this.translatedAudio.currentTime);
      } else if (this.isPlayingSnippet()) {
        this.currentTime.set(this.snippetStartTime + this.snippetAudio.currentTime);
      }
      this.animationFrameId = requestAnimationFrame(updateTimeLoop);
    };
    this.animationFrameId = requestAnimationFrame(updateTimeLoop);

    this.fetchLanguages();
    this.route.queryParams.subscribe(params => {
      const id = params['video_id'];
      if (id) {
        this.videoId.set(id);
        this.loadProject(id);
      } else {
        this.error.set('No video ID provided in URL');
        this.isLoading.set(false);
      }
    });
  }

  async fetchLanguages() {
    try {
      const response = await fetch('languages.json');
      const langs: Language[] = await response.json();
      this.languages.set(langs);
      this.gaLanguages.set(langs.filter(lang => lang.readiness === 'GA'));
      this.previewLanguages.set(langs.filter(lang => lang.readiness === 'Preview'));
    } catch (error) {
      console.error('Failed to fetch languages:', error);
    }
  }

  getLanguageName(code: string | undefined): string {
    if (!code) return 'Unknown';
    const lang = this.languages().find(l => l.code === code);
    return lang ? lang.name : code;
  }

  async loadProject(id: string) {
    this.isLoading.set(true);
    this.error.set(null);
    try {
      const response = await fetch(`/api/projects/${id}`);
      if (!response.ok) {
        throw new Error(`Project not found! status: ${response.status}`);
      }
      const data: VideoJob = await response.json();
      this.videoData.set(data);
      this.initEditState();

      let rawUrl = (data as any).original_video_url;

      if (!rawUrl && data.video_id) {
        // Fallback if missing, though it should be there.
        rawUrl = `temp/${data.video_id}/${data.video_id}`;
      }

      if (rawUrl) {
        // Ensure web_path starts with '/' for the proxy
        if (!rawUrl.startsWith('/')) {
          rawUrl = '/' + rawUrl;
        }

        this.videoUrl.set(rawUrl);
      } else {
        this.error.set('No video URL found in project data');
      }
    } catch (err: any) {
      console.error('Failed to load project:', err);
      this.error.set(err.message || 'Failed to load project details');
    } finally {
      this.isLoading.set(false);
    }
  }

  initEditState() {
    const data = this.videoData();
    if (data) {
      this.editOriginalLanguage.set(data.original_language);
      this.editTranslateLanguage.set(data.translate_language);
      this.editSpeakers.set([...data.speakers]);
    }
  }

  toggleEditSettings() {
    if (this.isEditingSettings()) {
      // Cancel edit
      this.isEditingSettings.set(false);
      this.initEditState();
    } else {
      // Start edit
      this.initEditState();
      this.isEditingSettings.set(true);
    }
  }

  // --- Speaker Modal Logic ---
  openAddSpeakerModal() {
    this.speakerToEditId.set(null);
    this.isSpeakerModalOpen.set(true);
  }

  openEditSpeakerVoiceModal(speakerId: string) {
    this.speakerToEditId.set(speakerId);
    this.isSpeakerModalOpen.set(true);
  }

  closeSpeakerModal() {
    this.isSpeakerModalOpen.set(false);
    this.speakerToEditId.set(null);
  }

  onSpeakerAddedOrEdited(modalSpeaker: Speaker) {
    const editId = this.speakerToEditId();
    if (editId) {
      // Edit existing speaker voice
      this.editSpeakers.update(speakers =>
        speakers.map(s => s.speaker_id === editId ? {
          ...s,
          voice: modalSpeaker.voice,
          // Make sure we keep the name the user previously assigned to it, or take from modal if they changed it
          name: modalSpeaker.name || s.name
        } : s)
      );
    } else {
      // Add new speaker
      const newSpeaker: VideoSpeaker = {
        speaker_id: modalSpeaker.id,
        name: modalSpeaker.name,
        voice: modalSpeaker.voice,
        gender: modalSpeaker.gender
      };
      this.editSpeakers.update(s => [...s, newSpeaker]);
    }
    this.closeSpeakerModal();
  }

  removeEditSpeaker(speakerId: string) {
    this.editSpeakers.update(speakers => speakers.filter(s => s.speaker_id !== speakerId));
  }

  async saveVideoSettings() {
    const data = this.videoData();
    if (!data) return;

    const newOriginalLang = this.editOriginalLanguage();
    const newTranslateLang = this.editTranslateLanguage();
    const newSpeakers = this.editSpeakers();

    const originalLangChanged = newOriginalLang !== data.original_language;
    const translateLangChanged = newTranslateLang !== data.translate_language;

    // Check if speakers changed
    const speakersChanged = JSON.stringify(newSpeakers.map(s => ({ speaker_id: s.speaker_id, voice: s.voice }))) !==
      JSON.stringify(data.speakers.map(s => ({ speaker_id: s.speaker_id, voice: s.voice })));

    if (!originalLangChanged && !translateLangChanged && !speakersChanged) {
      this.isEditingSettings.set(false);
      return;
    }

    this.isGeneratingAudio.set(true);

    try {
      if (originalLangChanged) {
        // Full reprocessing including transcription
        const formData = new FormData();
        formData.append('original_language', newOriginalLang);
        formData.append('translate_language', newTranslateLang);
        formData.append('source_video_id', data.video_id);
        formData.append('update_existing', 'true');
        formData.append('adjust_speed', 'false'); // Defaulting to false as it's not exposed in Editor UI
        formData.append('prompt_enhancements', data.prompt_enhancements || '');

        const speakersToPost = newSpeakers.map((s, index) => ({
          id: s.speaker_id || `speaker_${(index + 1).toString()}`,
          name: s.speaker_name || s.name,
          voice: s.voice,
          gender: s.gender,
        }));
        formData.append('speakers', JSON.stringify(speakersToPost));

        const response = await fetch('/process', { method: 'POST', body: formData });
        if (!response.ok) throw new Error('Failed to reprocess video.');
        const result = await response.json();

        if (result.video_id && result.video_id !== data.video_id) {
          this.router.navigate(['/editor'], { queryParams: { video_id: result.video_id } });
        } else {
          this.loadProject(result.video_id);
        }

      } else if (translateLangChanged) {
        // Translation change (Fork)
        const formData = new FormData();
        formData.append('source_video_id', data.video_id);
        formData.append('original_language', data.original_language);
        formData.append('translate_language', newTranslateLang);
        formData.append('adjust_speed', 'false'); // Defaulting to false as it's not exposed in Editor UI
        formData.append('prompt_enhancements', data.prompt_enhancements || '');

        const speakersToPost = newSpeakers.map((s, index) => ({
          id: s.speaker_id || `speaker_${(index + 1).toString()}`,
          name: s.speaker_name || s.name,
          voice: s.voice,
          gender: s.gender,
        }));
        formData.append('speakers', JSON.stringify(speakersToPost));

        const response = await fetch('/process', { method: 'POST', body: formData });
        if (!response.ok) throw new Error('Failed to create translation.');
        const result = await response.json();

        if (result.video_id && result.video_id !== data.video_id) {
          this.router.navigate(['/editor'], { queryParams: { video_id: result.video_id } });
        } else {
          this.loadProject(result.video_id);
        }

      } else if (speakersChanged) {
        // Only voices changed, update data and regenerate dubbings that were changed
        const changedSpeakers = newSpeakers.filter(
          ns => !data.speakers.find(os => os.speaker_id === ns.speaker_id && os.voice === ns.voice)
        );
        const changedSpeakerIds = changedSpeakers.map(cs => cs.speaker_id);

        const utterancesToUpdate = data.utterances.filter(u => changedSpeakerIds.includes(u.speaker.speaker_id));

        const dubbingPromises = utterancesToUpdate.map(async (utterance) => {
          const originalIndex = data.utterances.findIndex(u => u.id === utterance.id);
          const response = await fetch('/regenerate_dubbing', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              video: data,
              utterance: originalIndex,
              instructions: utterance.voice_instructions || utterance.instructions || ''
            })
          });
          if (!response.ok) throw new Error('Failed to regenerate dubbing.');

          const result = await response.json();
          const targetUtterance = data.utterances[originalIndex];
          targetUtterance.audio_url = result.audio_url;
          targetUtterance.duration = result.duration;
          targetUtterance.translated_end_time = targetUtterance.translated_start_time + result.duration;
        });

        await Promise.all(dubbingPromises);

        // Update speaker voices locally
        for (let u of data.utterances) {
          const newSpk = changedSpeakers.find(s => s.speaker_id === u.speaker.speaker_id);
          if (newSpk) {
            u.speaker.voice = newSpk.voice;
          }
        }

        data.speakers = newSpeakers;

        this.videoData.set({ ...data });
        this.initEditState();
      }

      this.isEditingSettings.set(false);
    } catch (e) {
      console.error(e);
      alert('Failed to update video settings');
    } finally {
      this.isGeneratingAudio.set(false);
    }
  }

  // --- Right Panel Interactions ---

  focusUtterance(utteranceId: string) {
    if (this.activeUtteranceId() !== utteranceId) {
      this.activeUtteranceId.set(utteranceId);
      this.activePanelMode.set(null);
      // Create a snapshot for reverting later
      const data = this.videoData();
      if (data) {
        const u = data.utterances.find(utt => utt.id === utteranceId);
        if (u) {
          this.initialUtteranceState = JSON.parse(JSON.stringify(u));
        }
      }
    }
  }

  setActivePanel(utteranceId: string, mode: PanelMode) {
    if (this.activeUtteranceId() === utteranceId && this.activePanelMode() === mode) {
      // Toggle off the panel if clicking the same button again
      this.activePanelMode.set(null);
    } else {
      // Set to new active pane
      this.activeUtteranceId.set(utteranceId);
      this.activePanelMode.set(mode);
    }
  }

  changeSpeaker(newSpeaker: VideoSpeaker) {
    const data = this.videoData();
    const activeId = this.activeUtteranceId();
    if (!data || !activeId) return;

    this.videoData.update(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        utterances: prev.utterances.map(u =>
          u.id === activeId ? { ...u, speaker: newSpeaker } : u
        )
      };
    });
  }

  saveTranslationInstructions(instructions: string) {
    const data = this.videoData();
    const activeId = this.activeUtteranceId();
    if (!data || !activeId) return;

    this.videoData.update(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        utterances: prev.utterances.map(u =>
          u.id === activeId ? { ...u, instructions } : u
        )
      };
    });
  }

  saveVoiceInstructions(voice_instructions: string) {
    const data = this.videoData();
    const activeId = this.activeUtteranceId();
    if (!data || !activeId) return;

    this.videoData.update(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        utterances: prev.utterances.map(u =>
          u.id === activeId ? { ...u, voice_instructions } : u
        )
      };
    });
  }

  updateOriginalText(utteranceId: string, newText: string) {
    this.videoData.update(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        utterances: prev.utterances.map(u =>
          u.id === utteranceId ? { ...u, original_text: newText } : u
        )
      };
    });
  }

  updateTranslatedText(utteranceId: string, newText: string) {
    this.videoData.update(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        utterances: prev.utterances.map(u =>
          u.id === utteranceId ? { ...u, translated_text: newText } : u
        )
      };
    });
  }

  updateTranslationInstructions(utteranceId: string, text: string) {
    this.videoData.update(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        utterances: prev.utterances.map(u =>
          u.id === utteranceId ? { ...u, instructions: text } : u
        )
      };
    });
  }

  updateVoiceInstructions(utteranceId: string, text: string) {
    this.videoData.update(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        utterances: prev.utterances.map(u =>
          u.id === utteranceId ? { ...u, voice_instructions: text } : u
        )
      };
    });
  }

  async regenerateTranslation(utteranceId: string) {
    const data = this.videoData();
    if (!data) return;

    const utteranceIndex = data.utterances.findIndex(u => u.id === utteranceId);
    if (utteranceIndex === -1) return;

    const utterance = data.utterances[utteranceIndex];

    try {
      this.isGeneratingAudio.set(true);
      const response = await fetch('/regenerate_translation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          video: data,
          utterance: utteranceIndex,
          instructions: utterance.instructions || utterance.voice_instructions || ''
        })
      });

      if (!response.ok) {
        throw new Error('Failed to regenerate translation.');
      }

      const result = await response.json();

      this.videoData.update(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          utterances: prev.utterances.map((u, i) =>
            i === utteranceIndex ? {
              ...u,
              translated_text: result.translated_text,
              audio_url: result.audio_url,
              duration: result.duration,
              translated_end_time: u.translated_start_time + result.duration
            } : u
          )
        };
      });

    } catch (e) {
      console.error(e);
      alert('Failed to regenerate translation');
    } finally {
      this.isGeneratingAudio.set(false);
    }
  }

  async regenerateDubbing(utteranceId: string) {
    const data = this.videoData();
    if (!data) return;

    const utteranceIndex = data.utterances.findIndex(u => u.id === utteranceId);
    if (utteranceIndex === -1) return;

    const utterance = data.utterances[utteranceIndex];

    try {
      this.isGeneratingAudio.set(true);
      const response = await fetch('/regenerate_dubbing', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          video: data,
          utterance: utteranceIndex,
          instructions: utterance.voice_instructions || utterance.instructions || ''
        })
      });

      if (!response.ok) {
        throw new Error('Failed to regenerate dubbing.');
      }

      const result = await response.json();

      this.videoData.update(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          utterances: prev.utterances.map((u, i) =>
            i === utteranceIndex ? {
              ...u,
              audio_url: result.audio_url,
              duration: result.duration,
              translated_end_time: u.translated_start_time + result.duration
            } : u
          )
        };
      });

    } catch (e) {
      console.error(e);
      alert('Failed to regenerate dubbing');
    } finally {
      this.isGeneratingAudio.set(false);
    }
  }

  revertUtterance(utteranceId: string) {
    if (!this.initialUtteranceState || this.initialUtteranceState.id !== utteranceId) return;

    this.videoData.update(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        utterances: prev.utterances.map(u =>
          u.id === utteranceId
            ? JSON.parse(JSON.stringify(this.initialUtteranceState))
            : u
        )
      };
    });
  }

  cloneUtterance(utteranceId: string) {
    this.videoData.update(prev => {
      if (!prev) return prev;

      const currentIndex = prev.utterances.findIndex(u => u.id === utteranceId);
      if (currentIndex === -1) return prev;

      const utterance = prev.utterances[currentIndex];
      const newUtterance = JSON.parse(JSON.stringify(utterance)); // Deep copy

      newUtterance.id = `utterance_${Date.now()}`; // Simple unique ID
      const duration = utterance.translated_end_time - utterance.translated_start_time;
      newUtterance.translated_start_time = utterance.translated_end_time;
      newUtterance.translated_end_time = utterance.translated_end_time + duration;

      const originalDuration = utterance.original_end_time - utterance.original_start_time;
      const refOriginalEnd = utterance.ui_original_end_time !== undefined ? utterance.ui_original_end_time : utterance.original_end_time;
      newUtterance.ui_original_start_time = refOriginalEnd;
      newUtterance.ui_original_end_time = refOriginalEnd + originalDuration;

      const newUtterances = [...prev.utterances];
      newUtterances.splice(currentIndex + 1, 0, newUtterance);

      return {
        ...prev,
        utterances: newUtterances
      };
    });

    // Close active panel when cloning
    this.activePanelMode.set(null);
  }

  get activeUtterance(): VideoUtterance | null {
    const data = this.videoData();
    const id = this.activeUtteranceId();
    if (!data || !id) return null;
    return data.utterances.find(u => u.id === id) || null;
  }

  get timelineDuration(): number {
    const data = this.videoData();
    if (!data) return 1;

    let maxDuration = data.duration || 1;
    for (const u of data.utterances) {
      if (u.original_end_time > maxDuration) maxDuration = u.original_end_time;
      if (u.translated_end_time > maxDuration) maxDuration = u.translated_end_time;
    }

    // Add a small buffer visually at the end
    return maxDuration;
  }

  // Utility to format seconds to MM:SS.ms format for presentation
  formatTime(seconds: number): string {
    const min = Math.floor(seconds / 60);
    const sec = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 100);
    return `${min.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
  }

  // --- Audio Interactions ---
  toggleOriginalAudio() {
    if (this.isPlayingOriginal()) {
      this.originalAudio.pause();
      this.originalAudio.currentTime = 0;
      this.currentTime.set(0);
      this.isPlayingOriginal.set(false);
    } else {
      const data = this.videoData();
      if (data && data.video_id) {
        this.originalAudio.src = `/temp/${data.video_id}/original_audio.wav`;
        this.originalAudio.play().then(() => {
          this.isPlayingOriginal.set(true);
        }).catch(err => {
          console.error("Error playing original audio", err);
        });
        this.originalAudio.onended = () => {
          this.isPlayingOriginal.set(false);
          this.currentTime.set(0);
        };
      }
    }
  }

  async toggleTranslatedAudio() {
    if (this.isPlayingTranslated()) {
      this.translatedAudio.pause();
      this.translatedAudio.currentTime = 0;
      this.currentTime.set(0);
      this.isPlayingTranslated.set(false);
    } else {
      const data = this.videoData();
      if (!data) return;

      this.isGeneratingAudio.set(true);
      try {
        const res = await fetch('/generate_audio', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
        if (res.ok) {
          const result = await res.json();
          this.translatedAudio.src = result.audio_url;
          this.translatedAudio.play().then(() => {
            this.isPlayingTranslated.set(true);
          }).catch(err => {
            console.error("Error playing translated audio", err);
          });
          this.translatedAudio.onended = () => {
            this.isPlayingTranslated.set(false);
            this.currentTime.set(0);
          };
        } else {
          console.error("Failed to generate audio:", res.status);
        }
      } catch (err) {
        console.error("Failed to generate audio:", err);
      } finally {
        this.isGeneratingAudio.set(false);
      }
    }
  }

  stopCurrentAudio() {
    this.originalAudio.pause();
    this.isPlayingOriginal.set(false);
    this.translatedAudio.pause();
    this.isPlayingTranslated.set(false);
    this.snippetAudio.pause();
    this.isPlayingSnippet.set(false);
    if (this.utteranceTimeoutId) {
      clearTimeout(this.utteranceTimeoutId);
      this.utteranceTimeoutId = null;
    }
    this.currentTime.set(0);
    this.activeAudioPlayback = null;
  }

  playOriginalUtterance(utterance: VideoUtterance, event: Event) {
    event.stopPropagation();

    if (this.activeAudioPlayback?.id === utterance.id && this.activeAudioPlayback?.type === 'original') {
      this.stopCurrentAudio();
      return;
    }

    this.stopCurrentAudio();
    this.activeAudioPlayback = { id: utterance.id, type: 'original' };

    const data = this.videoData();
    if (data && data.video_id) {
      // Ensure the source is set
      if (!this.originalAudio.src.includes(`/temp/${data.video_id}/original_audio.wav`)) {
        this.originalAudio.src = `/temp/${data.video_id}/original_audio.wav`;
      }

      this.originalAudio.currentTime = utterance.original_start_time;
      this.originalAudio.play().then(() => {
        this.isPlayingOriginal.set(true);
      }).catch(err => {
        console.error("Error playing original utterance snippet", err);
      });

      const duration = (utterance.original_end_time - utterance.original_start_time) * 1000;
      this.utteranceTimeoutId = setTimeout(() => {
        this.originalAudio.pause();
        this.isPlayingOriginal.set(false);
        this.currentTime.set(0);
        if (this.activeAudioPlayback?.id === utterance.id && this.activeAudioPlayback?.type === 'original') {
          this.activeAudioPlayback = null;
        }
      }, duration);
    }
  }

  playTranslatedUtterance(utterance: VideoUtterance, event: Event) {
    event.stopPropagation();

    if (this.activeAudioPlayback?.id === utterance.id && this.activeAudioPlayback?.type === 'translated') {
      this.stopCurrentAudio();
      return;
    }

    this.stopCurrentAudio();
    this.activeAudioPlayback = { id: utterance.id, type: 'translated' };

    if (utterance.audio_url) {
      this.snippetAudio.src = utterance.audio_url;
      this.snippetStartTime = utterance.translated_start_time;
      this.snippetAudio.play().then(() => {
        this.isPlayingSnippet.set(true);
      }).catch(err => {
        console.error("Error playing translated utterance snippet", err);
      });

      this.snippetAudio.onended = () => {
        this.isPlayingSnippet.set(false);
        this.currentTime.set(0); // If tied to timeline visual, reset it.
        if (this.activeAudioPlayback?.id === utterance.id && this.activeAudioPlayback?.type === 'translated') {
          this.activeAudioPlayback = null;
        }
      };
    } else {
      console.warn("No audio_url available for this translated utterance.");
    }
  }

  // --- Timeline Interactions ---

  getTimeMarkers(): number[] {
    const duration = this.timelineDuration;
    const markers = [];
    for (let i = 0; i <= duration; i += 5) {
      markers.push(i);
    }
    return markers;
  }

  // Using percentage for the layout positions
  getLeftPercent(time: number): number {
    const duration = this.timelineDuration;
    return (time / duration) * 100;
  }

  getWidthPercent(startTime: number, endTime: number): number {
    const duration = this.timelineDuration;
    return ((endTime - startTime) / duration) * 100;
  }

  getUtteranceOverlap(utterance: VideoUtterance): VideoUtterance | null {
    const data = this.videoData();
    if (!data || data.utterances.length <= 1) return null;
    return data.utterances.find(u =>
      u.id !== utterance.id &&
      ((utterance.translated_start_time >= u.translated_start_time && utterance.translated_start_time < u.translated_end_time) ||
        (utterance.translated_end_time > u.translated_start_time && utterance.translated_end_time <= u.translated_end_time) ||
        (utterance.translated_start_time <= u.translated_start_time && utterance.translated_end_time >= u.translated_end_time))
    ) || null;
  }

  onDragStart(event: MouseEvent, utterance: VideoUtterance) {
    if (event.button !== 0) return; // Only left click
    event.preventDefault();
    this.focusUtterance(utterance.id);
    this.isDragging.set(true);
    this.draggedUtteranceId.set(utterance.id);
    this.dragStartX = event.clientX;
    this.dragInitialStartTime = utterance.translated_start_time;
  }

  @HostListener('document:mousemove', ['$event'])
  onDragMove(event: MouseEvent) {
    if (!this.isDragging() || !this.draggedUtteranceId() || !this.timelineContainer) return;

    const containerWidth = this.timelineContainer.nativeElement.clientWidth;
    const duration = this.timelineDuration;
    const timePerPixel = duration / containerWidth;

    const deltaX = event.clientX - this.dragStartX;
    let newStartTime = this.dragInitialStartTime + (deltaX * timePerPixel);

    // Bounds check
    if (newStartTime < 0) newStartTime = 0;

    const data = this.videoData();
    if (!data) return;
    const utterance = data.utterances.find(u => u.id === this.draggedUtteranceId());
    if (utterance) {
      const uDuration = utterance.translated_end_time - utterance.translated_start_time;
      utterance.translated_start_time = Number(newStartTime.toFixed(2));
      utterance.translated_end_time = Number((newStartTime + uDuration).toFixed(2));
    }
  }

  @HostListener('document:mouseup', ['$event'])
  onDragEnd(event: MouseEvent) {
    if (this.isDragging()) {
      this.isDragging.set(false);
      this.draggedUtteranceId.set(null);
    }
  }

}
