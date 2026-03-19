import { Component, OnInit, OnDestroy, signal, computed, ViewChild, ElementRef, inject, effect, ChangeDetectionStrategy, HostListener } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { Subscription } from 'rxjs';
import { VideoGenerationService } from '../services/video-generation.service';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatTooltipModule, MAT_TOOLTIP_DEFAULT_OPTIONS } from '@angular/material/tooltip';
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
  speaking_rate: number;
  original_start_time: number;
  original_end_time: number;
  translated_start_time: number;
  translated_end_time: number;
  speaker: VideoSpeaker;
  audio_url?: string;
  duration?: number;


  // Mute State flag and cached timestamps
  muted?: boolean;
  initial_translated_start_time?: number;
  initial_translated_end_time?: number;

  // Deleted State flag
  removed?: boolean;

  // Regeneration flags
  needs_translation_regen?: boolean;
  needs_dubbing_regen?: boolean;
  isNew?: boolean;
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
  imports: [CommonModule, FormsModule, SpeakerModal, MatTooltipModule],
  providers: [
    { provide: MAT_TOOLTIP_DEFAULT_OPTIONS, useValue: { showDelay: 300, hideDelay: 0, touchendHideDelay: 1500 } }
  ],
  templateUrl: './editor.html',
  styleUrl: './editor.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '(document:mousemove)': 'onDragMove($event)',
    '(document:mouseup)': 'onDragEnd($event)',
    '(document:click)': 'onDocumentClick($event)'
  }
})
export class Editor implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private router = inject(Router);

  videoId = signal<string | null>(null);
  videoUrl = signal<string | null>(null);
  videoData = signal<VideoJob | null>(null);
  isLoading = signal(true);
  error = signal<string | null>(null);
  isGeneratingVideo = signal(false);

  // Track specific utterance being processed
  processingUtteranceId = signal<string | null>(null);
  processingAction = signal<'translation' | 'dubbing' | null>(null);
  successUtteranceId = signal<string | null>(null);
  successAction = signal<'translation' | 'dubbing' | null>(null);

  private videoGenerationService = inject(VideoGenerationService);
  private videoGenSub?: Subscription;

  // Audio elements for timeline
  originalAudio = new Audio();
  translatedAudio = new Audio();
  isPlayingOriginal = signal(false);
  isPlayingTranslated = signal(false);
  isPlayingSnippet = signal(false);
  isGeneratingAudio = signal(false);
  isProcessingGlobalChanges = signal(false);
  currentTime = signal(0);
  snippetStartTime = 0;

  // Audio elements for individual utterance snippet playback
  snippetAudio = new Audio();
  utteranceTimeoutId: ReturnType<typeof setTimeout> | undefined;
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
  showValidationModal = signal(false);
  validationModalTitle = signal('');
  validationModalMessage = signal('');
  showProceedButton = signal(true);


  // Draft State for active panel
  draftVoiceInstructions = signal<string | null>(null);
  draftSpeakingRate = signal<number | null>(null);
  draftTranslationInstructions = signal<string | null>(null);
  draftTimestamps = signal<{ start: string, end: string } | null>(null);
  timestampError = signal<string | null>(null);
  draftSpeaker = signal<VideoSpeaker | null>(null);

  isVoiceDirty = computed(() => {
    const active = this.activeUtterance;
    if (!active) return false;
    const draftVoice = this.draftVoiceInstructions();
    const draftRate = this.draftSpeakingRate();

    const voiceInstructionsChanged = draftVoice !== null && draftVoice !== (active.voice_instructions || '');
    const speakingRateChanged = draftRate !== null && draftRate !== active.speaking_rate;

    return voiceInstructionsChanged || speakingRateChanged;
  });

  isTranslationDirty = computed(() => {
    const active = this.activeUtterance;
    if (!active) return false;
    const draft = this.draftTranslationInstructions();
    if (draft === null) return false;
    return draft !== (active.instructions || '');
  });

  isTimestampsDirty = computed(() => {
    const active = this.activeUtterance;
    if (!active) return false;
    const draft = this.draftTimestamps();
    if (draft === null) return false;
    return draft.start !== this.formatTime(active.translated_start_time) ||
      draft.end !== this.formatTime(active.translated_end_time);
  });

  isSpeakerDirty = computed(() => {
    const active = this.activeUtterance;
    if (!active) return false;
    const draft = this.draftSpeaker();
    if (draft === null) return false;
    return draft.speaker_id !== active.speaker?.speaker_id;
  });

  durationWarningCount = computed(() => {
    const data = this.videoData();
    if (!data || !data.duration) return 0;
    return data.utterances.filter(u => u.translated_end_time > data.duration && !u.removed).length;
  });

  // Video Settings Editing State
  isEditingSettings = signal(false);

  // Overlap Popup State
  showOverlapPopup = signal(false);
  overlappingUtterances = signal<VideoUtterance[]>([]);
  popupPosition = signal<{ x: number, y: number }>({ x: 0, y: 0 });
  popupCloseTimeout: ReturnType<typeof setTimeout> | undefined;
  initialUtteranceState = signal<VideoUtterance | null>(null);

  // Custom Modal State
  showDiscardModal = signal(false);
  pendingDiscardAction: (() => void) | null = null;

  canUndoActiveUtterance = computed(() => {
    const activeId = this.activeUtteranceId();
    const data = this.videoData();
    const initialState = this.initialUtteranceState();

    if (!activeId || !data || !initialState) return false;

    const currentU = data.utterances.find(u => u.id === activeId);
    if (!currentU) return false;

    return currentU.original_text !== initialState.original_text ||
      currentU.translated_text !== initialState.translated_text ||
      (currentU.instructions || '') !== (initialState.instructions || '') ||
      (currentU.voice_instructions || '') !== (initialState.voice_instructions || '') ||
      currentU.translated_start_time !== initialState.translated_start_time ||
      currentU.translated_end_time !== initialState.translated_end_time ||
      currentU.speaker.speaker_id !== initialState.speaker.speaker_id;
  });
  editOriginalLanguage = signal('');
  editTranslateLanguage = signal('');
  editSpeakers = signal<VideoSpeaker[]>([]);
  gaLanguages = signal<Language[]>([]);
  previewLanguages = signal<Language[]>([]);

  // Dropdown States
  isOriginalOpen = signal(false);
  isTranslationOpen = signal(false);

  originalLanguageLabel = computed(() => {
    const code = this.editOriginalLanguage();
    const lang = this.languages().find(l => l.code === code);
    return lang ? lang.name : 'Select Language';
  });

  translateLanguageLabel = computed(() => {
    const code = this.editTranslateLanguage();
    const lang = this.languages().find(l => l.code === code);
    return lang ? lang.name : 'Select Language';
  });

  // Speaker Modal State
  isSpeakerModalOpen = signal(false);
  speakerToEditId = signal<string | null>(null);

  constructor() {
    effect(() => {
      const data = this.videoData();
      if (data) {
        const count = data.utterances.filter(u => u.needs_translation_regen || u.needs_dubbing_regen).length;
        this.videoGenerationService.updateUnregeneratedCount(count);
      } else {
        this.videoGenerationService.updateUnregeneratedCount(0);
      }
    });

    effect(() => {
      this.videoGenerationService.setProcessingAudio(this.isGeneratingAudio());
    }, { allowSignalWrites: true });
  }

  animationFrameId: number | null = null;

  ngOnInit() {
    const updateTimeLoop = () => {
      if (this.isPlayingOriginal()) {
        let currentVisualTime = this.originalAudio.currentTime;
        if (this.activeAudioPlayback?.type === 'original') {
          // Time matches originalAudio directly
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

    this.videoGenSub = this.videoGenerationService.generateVideo$.subscribe(async () => {
      console.log("generateVideo$ triggered");
      if (this.validateForGeneration()) {
        this.generateVideo();
      }
    });

    this.fetchLanguages();
    this.route.queryParams.subscribe(params => {
      const id = params['video_id'];
      if (id) {
        this.videoId.set(id);
        this.loadProject(id);
      } else {
        this.router.navigate(['/']);
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

      // The backend puts Gemini generated voice hints into the 'instructions' property by default
      // Map these to the more specific 'voice_instructions' frontend property instead so they appear in the correct tab
      if (data.utterances) {
        data.utterances.forEach(u => {
          if (u.instructions && !u.voice_instructions) {
            u.voice_instructions = u.instructions;
            u.instructions = ''; // Clear translation instructions to be clean by default
          }
        });
      }

      this.videoData.set(data);
      this.initEditState();

      let rawUrl = (data as VideoJob & { original_video_url?: string }).original_video_url;

      if (!rawUrl && data.video_id) {
        // Fallback: try to deduce from utterances if available
        const u = data.utterances.find(utt => utt.audio_url);
        if (u && u.audio_url) {
          let url = u.audio_url;
          if (!url.startsWith('http') && !url.startsWith('/')) {
            url = '/' + url;
          }
          const lastSlash = url.lastIndexOf('/');
          if (lastSlash !== -1) {
            rawUrl = url.substring(0, lastSlash + 1) + data.video_id;
          }
        } else {
          // Absolute fallback
          rawUrl = `temp/${data.video_id}/${data.video_id}`;
        }
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
    } catch (err: unknown) {
      console.error('Failed to load project:', err);
      const errorMessage = err instanceof Error ? err.message : 'Failed to load project details';
      this.error.set(errorMessage);
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

  ngOnDestroy() {
    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
    }
    this.videoGenSub?.unsubscribe();
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

    this.isProcessingGlobalChanges.set(true);
    this.isGeneratingAudio.set(true);

    try {
      if (originalLangChanged) {
        // Full reprocessing including transcription
        const formData = new FormData();
        formData.append('original_language', newOriginalLang);
        formData.append('translate_language', newTranslateLang);
        formData.append('source_video_id', data.video_id);
        formData.append('update_existing', 'true');
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
      this.isProcessingGlobalChanges.set(false);
      this.isGeneratingAudio.set(false);
    }
  }

  // --- Right Panel Interactions ---

  executeWithDirtyCheck(action: () => void) {
    if (this.isVoiceDirty() || this.isTranslationDirty() || this.isTimestampsDirty() || this.isSpeakerDirty()) {
      this.pendingDiscardAction = action;
      this.showDiscardModal.set(true);
    } else {
      action();
    }
  }

  onSaveAndProceed() {
    if (this.isTimestampsDirty()) {
      this.saveTimestamps();
      if (this.timestampError()) {
        this.showDiscardModal.set(false);
        return; // Halt if save validation failed
      }
    }

    if (this.isVoiceDirty()) this.saveVoiceInstructions();
    if (this.isTranslationDirty()) this.saveTranslationInstructions();
    if (this.isSpeakerDirty()) this.saveSpeaker();

    this.showDiscardModal.set(false);
    if (this.pendingDiscardAction) {
      this.pendingDiscardAction();
      this.pendingDiscardAction = null;
    }
  }

  onConfirmDiscard() {
    this.showDiscardModal.set(false);
    if (this.pendingDiscardAction) {
      this.pendingDiscardAction();
      this.pendingDiscardAction = null;
    }
  }

  onCancelDiscard() {
    this.showDiscardModal.set(false);
    this.pendingDiscardAction = null;
  }

  private _focusUtteranceLogic(utteranceId: string) {
    const prevId = this.activeUtteranceId();
    const data = this.videoData();


    this.activeUtteranceId.set(utteranceId);
    this.activePanelMode.set(null);
    this.clearDrafts();
    const dataCurrent = this.videoData(); // Use a different name to avoid shadowing?
    if (dataCurrent) {
      const u = dataCurrent.utterances.find(utt => utt.id === utteranceId);
      if (u) {
        this.initialUtteranceState.set(JSON.parse(JSON.stringify(u)));
      }
    }
  }

  focusUtterance(utteranceId: string) {
    if (this.activeUtteranceId() !== utteranceId) {
      this.executeWithDirtyCheck(() => {
        this._focusUtteranceLogic(utteranceId);
      });
    }
  }

  setActivePanel(utteranceId: string, mode: PanelMode) {
    if (this.activeUtteranceId() === utteranceId && this.activePanelMode() === mode) {
      // Toggle off the panel if clicking the same button again
      if (this.activePanelMode() !== null) {
        this.executeWithDirtyCheck(() => {
          this.activePanelMode.set(null);
          this.clearDrafts();
        });
      }
    } else {
      this.executeWithDirtyCheck(() => {
        if (this.activeUtteranceId() !== utteranceId) {
          this._focusUtteranceLogic(utteranceId);
        }
        this.clearDrafts();
        this.activePanelMode.set(mode);
      });
    }
  }

  clearDrafts() {
    this.draftVoiceInstructions.set(null);
    this.draftTranslationInstructions.set(null);
    this.draftTimestamps.set(null);
    this.timestampError.set(null);
    this.draftSpeaker.set(null);
  }

  onVoiceInput(val: string) {
    this.draftVoiceInstructions.set(val);
  }

  onSpeakingRateInput(val: number) {
    this.draftSpeakingRate.set(val);
  }

  onTranslationInput(val: string) {
    this.draftTranslationInstructions.set(val);
  }

  onStartTimestampInput(startStr: string, endInput: HTMLInputElement) {
    const active = this.activeUtterance;
    if (!active) return;
    const currentDuration = active.translated_end_time - active.translated_start_time;

    let newStart = this.parseTime(startStr);
    if (!isNaN(newStart) && startStr.includes(':')) {
      const newEnd = newStart + currentDuration;
      const newEndStr = this.formatTime(newEnd);
      endInput.value = newEndStr;
      this.draftTimestamps.set({ start: startStr, end: newEndStr });
      this.timestampError.set(null);
    } else {
      this.draftTimestamps.set({ start: startStr, end: endInput.value });
      this.timestampError.set(null);
    }
  }

  onEndTimestampInput(startInput: HTMLInputElement, endStr: string) {
    const active = this.activeUtterance;
    if (!active) return;
    const currentDuration = active.translated_end_time - active.translated_start_time;

    let newEnd = this.parseTime(endStr);
    if (!isNaN(newEnd) && endStr.includes(':')) {
      let newStart = newEnd - currentDuration;

      const newStartStr = this.formatTime(newStart);
      startInput.value = newStartStr;
      this.draftTimestamps.set({ start: newStartStr, end: endStr });
      this.timestampError.set(null);
    } else {
      this.draftTimestamps.set({ start: startInput.value, end: endStr });
      this.timestampError.set(null);
    }
  }

  onSpeakerSelect(spk: VideoSpeaker) {
    this.draftSpeaker.set(spk);
  }

  checkTranslationRegen(u: VideoUtterance, initialState: VideoUtterance | null): boolean {
    if (!initialState || initialState.id !== u.id) return true;
    const isDirty = (
      u.original_text !== initialState.original_text ||
      (u.instructions || '') !== (initialState.instructions || '')
    );
    return !!initialState.needs_translation_regen || isDirty;
  }

  checkDubbingRegen(u: VideoUtterance, initialState: VideoUtterance | null): boolean {
    if (!initialState || initialState.id !== u.id) return true;
    const isDirty = (
      u.speaker.speaker_id !== initialState.speaker.speaker_id ||
      (u.voice_instructions || '') !== (initialState.voice_instructions || '') ||
      u.translated_text !== initialState.translated_text ||
      u.original_text !== initialState.original_text ||
      (u.instructions || '') !== (initialState.instructions || '')
    );
    return !!initialState.needs_dubbing_regen || isDirty;
  }

  changeSpeaker(newSpeaker: VideoSpeaker) {
    const data = this.videoData();
    const activeId = this.activeUtteranceId();
    const initialState = this.initialUtteranceState();
    if (!data || !activeId) return;

    this.videoData.update(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        utterances: prev.utterances.map(u => {
          if (u.id === activeId) {
            const updated = { ...u, speaker: newSpeaker };
            updated.needs_dubbing_regen = this.checkDubbingRegen(updated, initialState);
            return updated;
          }
          return u;
        })
      };
    });
  }

  saveTranslationInstructions() {
    const draft = this.draftTranslationInstructions();
    if (draft === null) return;
    const data = this.videoData();
    const activeId = this.activeUtteranceId();
    const initialState = this.initialUtteranceState();
    if (!data || !activeId) return;

    this.videoData.update(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        utterances: prev.utterances.map(u => {
          if (u.id === activeId) {
            const updated = { ...u, instructions: draft };
            updated.needs_translation_regen = this.checkTranslationRegen(updated, initialState);
            updated.needs_dubbing_regen = this.checkDubbingRegen(updated, initialState);
            return updated;
          }
          return u;
        })
      };
    });
    this.draftTranslationInstructions.set(null);
  }

  saveVoiceInstructions() {
    const draft = this.draftVoiceInstructions() || undefined;
    const draftRate = this.draftSpeakingRate() || 1.0;
    const data = this.videoData();
    const activeId = this.activeUtteranceId();
    const initialState = this.initialUtteranceState();
    if (!data || !activeId) return;

    this.videoData.update(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        utterances: prev.utterances.map(u => {
          if (u.id === activeId) {
            const updated = { ...u, voice_instructions: draft, speaking_rate: draftRate };
            updated.needs_dubbing_regen = this.checkDubbingRegen(updated, initialState);
            return updated;
          }
          return u;
        })
      };
    });
    this.draftVoiceInstructions.set(null);
    this.draftSpeakingRate.set(null);
  }

  saveSpeaker() {
    const draft = this.draftSpeaker();
    if (draft === null) return;
    this.changeSpeaker(draft);
    this.draftSpeaker.set(null);
  }

  cancelTimestamps() {
    this.draftTimestamps.set(null);
    this.timestampError.set(null);
  }

  saveTimestamps() {
    const draft = this.draftTimestamps();
    if (draft === null) return;

    // Validate negative timestamps on save
    if (this.parseTime(draft.start) < 0) {
      this.timestampError.set("Start time cannot be negative. To change duration of utterance, try changing the speed or shortening the text.");
      return;
    }

    this.timestampError.set(null);
    this.applyTimestamps(this.activeUtteranceId()!, draft.start, draft.end);
    this.draftTimestamps.set(null);
  }

  updateOriginalText(utteranceId: string, newText: string) {
    const initialState = this.initialUtteranceState();
    this.videoData.update(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        utterances: prev.utterances.map(u => {
          if (u.id === utteranceId) {
            const updated = { ...u, original_text: newText };
            updated.needs_translation_regen = this.checkTranslationRegen(updated, initialState);
            updated.needs_dubbing_regen = this.checkDubbingRegen(updated, initialState);
            return updated;
          }
          return u;
        })
      };
    });
  }

  updateTranslatedText(utteranceId: string, newText: string) {
    const initialState = this.initialUtteranceState();
    this.videoData.update(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        utterances: prev.utterances.map(u => {
          if (u.id === utteranceId) {
            const updated = { ...u, translated_text: newText };
            updated.needs_translation_regen = this.checkTranslationRegen(updated, initialState);
            updated.needs_dubbing_regen = this.checkDubbingRegen(updated, initialState);
            return updated;
          }
          return u;
        })
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
      this.processingUtteranceId.set(utteranceId);
      this.processingAction.set('translation');
      this.successUtteranceId.set(null);
      this.successAction.set(null);

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

      this.successUtteranceId.set(utteranceId);
      this.successAction.set('translation');

      // Clear success state after 3 seconds
      setTimeout(() => {
        if (this.successUtteranceId() === utteranceId && this.successAction() === 'translation') {
          this.successUtteranceId.set(null);
          this.successAction.set(null);
        }
      }, 3000);

      const result = await response.json();

      this.videoData.update(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          utterances: prev.utterances.map((u, i) =>
            i === utteranceIndex ? {
              ...u,
              translated_text: result.translated_text,
              needs_translation_regen: false,
              needs_dubbing_regen: true
            } : u
          )
        };
      });

    } catch (e) {
      console.error(e);
      alert('Failed to regenerate translation');
    } finally {
      this.isGeneratingAudio.set(false);
      this.processingUtteranceId.set(null);
      this.processingAction.set(null);
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
      this.processingUtteranceId.set(utteranceId);
      this.processingAction.set('dubbing');
      this.successUtteranceId.set(null);
      this.successAction.set(null);

      const response = await fetch('/regenerate_dubbing', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          video: data,
          utterance: utteranceIndex,
          instructions: utterance.voice_instructions || utterance.instructions || '',

        })
      });

      if (!response.ok) {
        throw new Error('Failed to regenerate dubbing.');
      }

      this.successUtteranceId.set(utteranceId);
      this.successAction.set('dubbing');

      // Clear success state after 3 seconds
      setTimeout(() => {
        if (this.successUtteranceId() === utteranceId && this.successAction() === 'dubbing') {
          this.successUtteranceId.set(null);
          this.successAction.set(null);
        }
      }, 3000);

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
              translated_end_time: u.translated_start_time + result.duration,
              needs_dubbing_regen: false
            } : u
          )
        };
      });

    } catch (e) {
      console.error(e);
      alert('Failed to regenerate dubbing');
    } finally {
      this.isGeneratingAudio.set(false);
      this.processingUtteranceId.set(null);
      this.processingAction.set(null);
    }
  }

  revertUtterance(utteranceId: string) {
    const initialState = this.initialUtteranceState();
    if (!initialState || initialState.id !== utteranceId) return;

    this.videoData.update(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        utterances: prev.utterances.map(u =>
          u.id === utteranceId
            ? JSON.parse(JSON.stringify(initialState))
            : u
        )
      };
    });
  }

  toggleMuteUtterance(utteranceId: string) {
    this.videoData.update(prev => {
      if (!prev) return prev;

      const utteranceIndex = prev.utterances.findIndex(u => u.id === utteranceId);
      if (utteranceIndex === -1) return prev;

      const utterance = prev.utterances[utteranceIndex];
      const newMutedState = !utterance.muted;

      // Update the utterance
      const updatedUtterance = { ...utterance, muted: newMutedState };

      if (newMutedState) {
        // Cache initial times before muting if not cached
        if (updatedUtterance.initial_translated_start_time === undefined) {
          updatedUtterance.initial_translated_start_time = updatedUtterance.translated_start_time;
          updatedUtterance.initial_translated_end_time = updatedUtterance.translated_end_time;
        }

        // Reset translated times to match original
        updatedUtterance.translated_start_time = updatedUtterance.original_start_time;
        updatedUtterance.translated_end_time = updatedUtterance.original_end_time;

      } else {
        // Restore initial times on unmute
        if (updatedUtterance.initial_translated_start_time !== undefined) {
          updatedUtterance.translated_start_time = updatedUtterance.initial_translated_start_time;
        }
        if (updatedUtterance.initial_translated_end_time !== undefined) {
          updatedUtterance.translated_end_time = updatedUtterance.initial_translated_end_time;
        }
      }

      const newUtterances = [...prev.utterances];
      newUtterances[utteranceIndex] = updatedUtterance;

      return {
        ...prev,
        utterances: newUtterances
      };
    });

    // Close any open side panels if the utterance was just muted and was active
    const updated = this.videoData()?.utterances.find(u => u.id === utteranceId);
    if (updated?.muted && this.activeUtteranceId() === utteranceId) {
      this.activePanelMode.set(null);
    }
  }

  toggleRemoveUtterance(utteranceId: string) {
    this.videoData.update(prev => {
      if (!prev) return prev;

      const utteranceIndex = prev.utterances.findIndex(u => u.id === utteranceId);
      if (utteranceIndex === -1) return prev;

      const utterance = prev.utterances[utteranceIndex];

      const isNew = utterance.id.startsWith('utterance_') || utterance.isNew;
      const isEmpty = !utterance.translated_text && !utterance.original_text;

      if (isNew && isEmpty) {
        const newUtterances = prev.utterances.filter(u => u.id !== utteranceId);
        return { ...prev, utterances: newUtterances };
      }

      const newRemovedState = !utterance.removed;
      const updatedUtterance = { ...utterance, removed: newRemovedState };

      // Ensure mute is cancelled if remove is activated, matching legacy UI logic
      if (updatedUtterance.removed && updatedUtterance.muted) {
        updatedUtterance.muted = false;
      }

      const newUtterances = [...prev.utterances];
      newUtterances[utteranceIndex] = updatedUtterance;

      return {
        ...prev,
        utterances: newUtterances
      };
    });

    // Close side panels and optionally clear active selection if utterance was removed
    const updated = this.videoData()?.utterances.find(u => u.id === utteranceId);
    if ((!updated || updated.removed) && this.activeUtteranceId() === utteranceId) {
      this.activePanelMode.set(null);
      if (!updated) {
        this.activeUtteranceId.set(null);
      }
    }
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

    // Add visual padding to the right of the timeline (at least 1 second or 5%)
    const padding = Math.max(0.1, maxDuration * 0.01);
    return Math.max(maxDuration + padding, 1);
  }

  // Utility to format seconds to MM:SS.ms format for presentation
  formatTime(seconds: number): string {
    const isNegative = seconds < 0;
    const absSeconds = Math.abs(seconds);
    const min = Math.floor(absSeconds / 60);
    const sec = Math.floor(absSeconds % 60);
    const ms = Math.floor((absSeconds % 1) * 100);
    const timeStr = `${min.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
    return isNegative ? `-${timeStr}` : timeStr;
  }

  // Parse time back from MM:SS.ms (e.g., 01:15.50 -> 75.5)
  parseTime(timeStr: string): number {
    try {
      const isNegative = timeStr.trim().startsWith('-');
      if (isNegative) timeStr = timeStr.trim().substring(1);

      const parts = timeStr.split(':');
      if (parts.length !== 2) return 0;
      const min = parseInt(parts[0], 10) || 0;
      const secParts = parts[1].split('.');
      const sec = parseInt(secParts[0], 10) || 0;
      let ms = 0;
      if (secParts.length > 1) {
        let msStr = secParts[1];
        if (msStr.length === 1) msStr += '0';
        ms = parseInt(msStr.substring(0, 2), 10) || 0;
      }
      const val = (min * 60) + sec + (ms / 100);
      return isNegative ? -val : val;
    } catch {
      return 0;
    }
  }

  applyTimestamps(id: string | undefined, startStr: string, endStr: string) {
    if (!id) return;

    let newStart = this.parseTime(startStr);
    let newEnd = this.parseTime(endStr);

    if (newEnd < newStart) {
      alert("End time cannot be earlier than start time.");
      return;
    }

    this.videoData.update((data) => {
      if (!data) return data;
      const newData = JSON.parse(JSON.stringify(data));
      const utterance = newData.utterances.find((u: VideoUtterance) => u.id === id);
      if (utterance) {
        utterance.translated_start_time = newStart;
        utterance.translated_end_time = newEnd;
      }
      return newData;
    });
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
        this.originalAudio.src = this.getOriginalAudioSrc(data);
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
      this.utteranceTimeoutId = undefined;
    }
    this.currentTime.set(0);
    this.activeAudioPlayback = null;
  }

  playOriginalUtterance(utterance: VideoUtterance, event: Event) {
    console.log('playOriginalUtterance with ID:', utterance.id);
    event.stopPropagation();

    if (this.activeAudioPlayback?.id === utterance.id && this.activeAudioPlayback?.type === 'original') {
      this.stopCurrentAudio();
      return;
    }

    this.stopCurrentAudio();
    this.activeAudioPlayback = { id: utterance.id, type: 'original' };

    const data = this.videoData();
    if (data && data.video_id) {
      const expectedSrc = this.getOriginalAudioSrc(data);

      const playSnippet = () => {
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
      };

      if (!this.originalAudio.src.includes(expectedSrc)) {
        this.originalAudio.src = expectedSrc;
        this.originalAudio.addEventListener('canplay', playSnippet, { once: true });
      } else {
        if (this.originalAudio.readyState >= 3) {
          playSnippet();
        } else {
          this.originalAudio.addEventListener('canplay', playSnippet, { once: true });
        }
      }
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
      let url = utterance.audio_url;
      if (!url.startsWith('http') && !url.startsWith('/')) {
        url = '/' + url;
      }
      this.snippetAudio.src = url;
      this.snippetStartTime = utterance.translated_start_time;
      this.snippetAudio.play().then(() => {
        this.isPlayingSnippet.set(true);
      }).catch(err => {
        console.error("Error playing translated utterance snippet", err);
      });

      this.snippetAudio.onended = () => {
        this.isPlayingSnippet.set(false);
        this.currentTime.set(0);
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

  async generateVideo() {
    if (!this.videoData() || !this.videoUrl()) return;
    this.isGeneratingVideo.set(true);
    try {
      const payload = {
        video: this.videoData(),
        original_video_url: this.videoUrl()
      };
      const response = await fetch('/generate_video', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload)
      });
      if (!response.ok) throw new Error('Failed to generate video');
      const result = await response.json();

      // Navigate to results page and pass the generated data via Router state
      this.router.navigate(['/result'], { state: { finalVideoData: result, originalVideoData: this.videoData() } });
    } catch (err) {
      console.error("Error generating video:", err);
      alert("Failed to generate video");
    } finally {
      this.isGeneratingVideo.set(false);
    }
  }

  validateForGeneration(): boolean {
    const hasUnregenerated = this.hasUnregeneratedChanges();
    const exceedsLength = this.checkExceedsLength();

    if (hasUnregenerated || exceedsLength) {
      this.showValidationModal.set(true);

      let title = '';
      let message = '';
      let showProceed = true;

      if (hasUnregenerated && exceedsLength) {
        title = 'Multiple Issues Found';
        message = 'You have unregenerated changes that will NOT be included in the final video. Also, one or more utterances exceed the original video length. If you proceed, the final video will be extended to match the audio, and the last frame will likely be frozen during the extended part.';
      } else if (hasUnregenerated) {
        title = 'Unregenerated Changes';
        message = 'You have unchanged text or voices that have not been regenerated yet. These changes will NOT be included in the final video. Do you want to proceed anyway?';
      } else if (exceedsLength) {
        title = 'Utterances Exceed Length';
        message = 'One or more utterances exceed the original video length. If you proceed, the final video will be extended to match the audio, and the last frame will likely be frozen during the extended part. Do you want to proceed?';
      }

      this.validationModalTitle.set(title);
      this.validationModalMessage.set(message);
      this.showProceedButton.set(showProceed);

      return false;
    }
    return true;
  }

  hasUnregeneratedChanges(): boolean {
    const data = this.videoData();
    if (!data) return false;
    return data.utterances.some(u => u.needs_translation_regen || u.needs_dubbing_regen);
  }

  checkExceedsLength(): boolean {
    const data = this.videoData();
    if (!data || !data.duration || data.utterances.length === 0) {
      return false;
    }
    const maxEndTime = Math.max(...data.utterances.map(u => u.translated_end_time));
    const exceeds = maxEndTime > data.duration;
    return exceeds;
  }

  onConfirmValidation() {
    this.showValidationModal.set(false);
    this.generateVideo();
  }

  onCancelValidation() {
    this.showValidationModal.set(false);
  }

  getMaxEndTime(): number {
    const data = this.videoData();
    if (!data || data.utterances.length === 0) return 0;
    return Math.max(...data.utterances.map(u => u.translated_end_time));
  }

  getOverlappingUtterances(utterance: VideoUtterance): VideoUtterance[] {
    const data = this.videoData();
    if (!data) return [];
    return data.utterances.filter(u =>
      !u.removed &&
      (u.id === utterance.id ||
        (utterance.translated_start_time <= u.translated_end_time && utterance.translated_end_time >= u.translated_start_time))
    );
  }

  showPopup(event: MouseEvent, utterance: VideoUtterance) {
    const overlaps = this.getOverlappingUtterances(utterance);
    if (overlaps.length > 1) {
      this.overlappingUtterances.set(overlaps);
      this.popupPosition.set({ x: event.clientX, y: event.clientY });
      this.showOverlapPopup.set(true);
      clearTimeout(this.popupCloseTimeout);
    }
  }

  hidePopup(event: MouseEvent) {
    // Delay closing to allow moving to popup
    this.popupCloseTimeout = setTimeout(() => {
      this.showOverlapPopup.set(false);
      this.overlappingUtterances.set([]);
    }, 100);
  }

  keepPopupOpen() {
    clearTimeout(this.popupCloseTimeout);
  }

  closePopup() {
    this.showOverlapPopup.set(false);
    this.overlappingUtterances.set([]);
  }

  selectFromPopup(u: VideoUtterance) {
    this.focusUtterance(u.id);
    this.closePopup();
  }

  getUtteranceIndex(u: VideoUtterance): number {
    const data = this.videoData();
    if (!data) return -1;
    return data.utterances.findIndex(item => item.id === u.id);
  }

  getUtteranceOverlap(utterance: VideoUtterance): VideoUtterance | null {
    if (utterance.muted || utterance.removed) return null;
    const data = this.videoData();
    if (!data || data.utterances.length <= 1) return null;
    return data.utterances.find(u =>
      u.id !== utterance.id && !u.muted && !u.removed &&
      ((utterance.translated_start_time >= u.translated_start_time && utterance.translated_start_time < u.translated_end_time) ||
        (utterance.translated_end_time > u.translated_start_time && utterance.translated_end_time <= u.translated_end_time) ||
        (utterance.translated_start_time <= u.translated_start_time && utterance.translated_end_time >= u.translated_end_time))
    ) || null;
  }

  onDragStart(event: MouseEvent, utterance: VideoUtterance) {
    if (event.button !== 0) return;
    event.preventDefault();
    this.focusUtterance(utterance.id);
    this.isDragging.set(true);
    this.draggedUtteranceId.set(utterance.id);
    this.dragStartX = event.clientX;
    this.dragInitialStartTime = utterance.translated_start_time;
  }

  onDragMove(event: MouseEvent) {
    if (!this.isDragging() || !this.draggedUtteranceId() || !this.timelineContainer) return;

    const containerWidth = this.timelineContainer.nativeElement.clientWidth;
    const duration = this.timelineDuration;
    const timePerPixel = duration / containerWidth;

    const deltaX = event.clientX - this.dragStartX;
    let newStartTime = this.dragInitialStartTime + (deltaX * timePerPixel);

    // Bounds check
    if (newStartTime < 0) newStartTime = 0;

    this.videoData.update(prev => {
      if (!prev) return prev;
      const index = prev.utterances.findIndex(u => u.id === this.draggedUtteranceId());
      if (index === -1) return prev;

      const newUtterances = [...prev.utterances];
      const u = { ...newUtterances[index] };
      const uDuration = u.translated_end_time - u.translated_start_time;

      u.translated_start_time = Number(newStartTime.toFixed(2));
      u.translated_end_time = Number((newStartTime + uDuration).toFixed(2));

      newUtterances[index] = u;

      return { ...prev, utterances: newUtterances };
    });
  }

  onDragEnd(event: MouseEvent) {
    if (this.isDragging()) {
      this.isDragging.set(false);
      this.draggedUtteranceId.set(null);
    }
  }

  createNewUtterance(index: number, event: Event) {
    event.stopPropagation();

    this.executeWithDirtyCheck(() => {
      this.videoData.update(prev => {
        if (!prev) return prev;

        const isAbove = index === -1;
        const currentUtterance = prev.utterances[isAbove ? 0 : index];
        if (!currentUtterance) return prev;

        let newStartTime = currentUtterance.translated_end_time;
        if (isAbove) {
          newStartTime = Math.max(0, currentUtterance.translated_start_time - 1.0);
        }
        let newEndTime = isAbove ? currentUtterance.translated_start_time : newStartTime + 1.0;

        if (isAbove && newEndTime <= newStartTime) {
          newStartTime = 0;
          newEndTime = 1.0;
        }

        const newUtterance: VideoUtterance = {
          id: crypto.randomUUID(),
          original_text: '',
          translated_text: '',
          original_start_time: 0,
          original_end_time: 0,
          translated_start_time: newStartTime,
          translated_end_time: newEndTime,
          speaker: currentUtterance.speaker,
          instructions: currentUtterance.instructions,
          voice_instructions: currentUtterance.voice_instructions,
          speaking_rate: 1.0,
          audio_url: '',
          needs_dubbing_regen: true,
          needs_translation_regen: true,
          muted: false,
          removed: false,
          isNew: true
        };

        const newUtterances = [...prev.utterances];
        if (isAbove) {
          newUtterances.unshift(newUtterance);
        } else {
          newUtterances.splice(index + 1, 0, newUtterance);
        }

        return { ...prev, utterances: newUtterances };
      });

      const data = this.videoData();
      if (data) {
        const focusIndex = index === -1 ? 0 : index + 1;
        this.focusUtterance(data.utterances[focusIndex].id);
      }
    });
  }
  mergeUtterances(index: number, event: Event) {
    event.stopPropagation();

    this.executeWithDirtyCheck(() => {
      this.videoData.update(prev => {
        if (!prev || index >= prev.utterances.length - 1) return prev;

        const topUtterance = prev.utterances[index];
        const bottomUtterance = prev.utterances[index + 1];

        const mergedUtterance: VideoUtterance = {
          ...topUtterance,
          id: crypto.randomUUID(),
          original_text: `${topUtterance.original_text} ${bottomUtterance.original_text}`.trim(),
          translated_text: `${topUtterance.translated_text} ${bottomUtterance.translated_text}`.trim(),
          original_end_time: bottomUtterance.original_end_time,
          translated_end_time: bottomUtterance.translated_end_time,
          needs_translation_regen: true,
          needs_dubbing_regen: true,
          audio_url: ''
        };

        const newUtterances = [...prev.utterances];
        // Remove both top and bottom, and insert the newly merged one
        newUtterances.splice(index, 2, mergedUtterance);

        return { ...prev, utterances: newUtterances };
      });

      // Focus the new merged utterance
      const data = this.videoData();
      if (data) {
        this.focusUtterance(data.utterances[index].id);
      }
    });
  }

  onDocumentClick(event: MouseEvent) {
    if (!this.activeUtteranceId() && !this.activePanelMode()) return;

    const targetElement = event.target as HTMLElement;

    if (targetElement.closest('form')) return;

    if (targetElement.closest('.border-b.border-black\\/5')) return;

    // Clicks on the transparent gap between utterances (divider) should be treated as background clicks (fall through to clear).
    // But clicks on actual action buttons inside the divider or inside the utterance itself should keep it open.
    if (targetElement.closest('.utterance-insert-divider') && !targetElement.closest('button')) {
    } else if (targetElement.closest('[id^="utterance-"]')) {
      return;
    }

    // Ignore clicks inside the right Advanced Settings panel
    if (targetElement.closest('aside')) return;

    // Ignore clicks inside the timeline footer (avoids closing when clicking play/pause or timeblocks)
    if (targetElement.closest('footer')) return;

    // Ignore clicks inside the header container
    if (targetElement.closest('header')) return;

    // Ignore clicks on custom overlays, speaker modal, or the discard modal itself
    if (targetElement.closest('app-speaker-modal') || targetElement.closest('.cdk-overlay-container') || targetElement.closest('#discard-modal')) return;

    // Ignore clicks if the discard modal is already open
    if (this.showDiscardModal()) return;

    // Check for unsaved changes before deselecting
    this.executeWithDirtyCheck(() => {
      this.clearDrafts();
      this.activeUtteranceId.set(null);
      this.activePanelMode.set(null);
    });
  }









private getOriginalAudioSrc(data: VideoJob): string {
    const u = data.utterances.find(utt => utt.audio_url);
  let expectedSrc = `/temp/${data.video_id}/original_audio.wav`;
    if (u && u.audio_url) {
      let url = u.audio_url;
      if (!url.startsWith('http') && !url.startsWith('/')) {
        url = '/' + url;
      }
      const lastSlash = url.lastIndexOf('/');
      if (lastSlash !== -1) {
        expectedSrc = url.substring(0, lastSlash + 1) + 'original_audio.wav';
      }
    }
    return expectedSrc;
  }
}
