import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Editor } from './editor';
import { provideRouter, Router, ActivatedRoute } from '@angular/router';
import { VideoGenerationService } from '../services/video-generation.service';
import { MatTooltipModule } from '@angular/material/tooltip';
import { of, Subject } from 'rxjs';
import { signal, WritableSignal } from '@angular/core';
import { Speaker } from '../_components/speaker-modal/speaker-modal';

describe('Editor', () => {
  let component: Editor;
  let fixture: ComponentFixture<Editor>;
  let mockRouter: any;
  let mockActivatedRoute: any;
  let mockVideoGenerationService: any;
  let navigationEndSubject: Subject<any>;

  beforeEach(async () => {
    navigationEndSubject = new Subject<any>();

    mockActivatedRoute = {
      queryParams: of({ video_id: 'test-video-id' }),
    };

    mockVideoGenerationService = {
      generateVideo$: of(null),
      updateUnregeneratedCount: vi.fn(),
      setProcessingAudio: vi.fn(),
    };

    // Mock global Audio
    vi.spyOn(window, 'Audio').mockImplementation(function() {
      return {
        play: vi.fn().mockResolvedValue(undefined),
        pause: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        load: vi.fn(),
        src: '',
        currentTime: 0,
        readyState: 4, // HAVE_ENOUGH_DATA
        onended: null
      };
    } as any);

    // Mock fetch
    vi.spyOn(window, 'fetch').mockImplementation(async (input: RequestInfo | URL) => {
      if (typeof input === 'string') {
        if (input.includes('/api/projects/test-video-id')) {
          return new Response(JSON.stringify({
            video_id: 'test-video-id',
            original_language: 'en',
            translate_language: 'es',
            speakers: [
              { speaker_id: 'spk_1', name: 'Alice', voice: 'voice_1', gender: 'female' },
              { speaker_id: 'spk_2', name: 'Bob', voice: 'voice_2', gender: 'male' }
            ],
            utterances: [
              {
                id: 'utt_1',
                original_text: 'Hello',
                translated_text: 'Hola',
                original_start_time: 0,
                original_end_time: 2,
                translated_start_time: 0,
                translated_end_time: 2,
                speaker: { speaker_id: 'spk_1', name: 'Alice', voice: 'voice_1', gender: 'female' }
              },
              {
                id: 'utt_2',
                original_text: 'World',
                translated_text: 'Mundo',
                original_start_time: 2,
                original_end_time: 4,
                translated_start_time: 2,
                translated_end_time: 4,
                speaker: { speaker_id: 'spk_1', name: 'Alice', voice: 'voice_1', gender: 'female' }
              }
            ],
            duration: 10,
          }), { status: 200 });
        }
        if (input.includes('languages.json')) {
          return new Response(JSON.stringify([
            { name: 'English', code: 'en' },
            { name: 'Spanish', code: 'es' },
          ]), { status: 200 });
        }
        if (input.includes('/regenerate_dubbing')) {
            return new Response(JSON.stringify({ audio_url: 'new_audio.wav', duration: 1.0 }));
        }
        if (input.includes('/regenerate_translation')) {
            return new Response(JSON.stringify({ translated_text: 'Hola corregido' }));
        }
      }
      return Promise.reject(new Error(`Unexpected fetch request: ${input}`));
    });

    await TestBed.configureTestingModule({
      imports: [Editor, MatTooltipModule],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: mockActivatedRoute },
        { provide: VideoGenerationService, useValue: mockVideoGenerationService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(Editor);
    component = fixture.componentInstance;

    mockRouter = TestBed.inject(Router);
    vi.spyOn(mockRouter, 'navigate');

    Object.defineProperty(mockRouter, 'events', {
      value: navigationEndSubject.asObservable(),
      writable: true,
    });
    
    // Mock requestAnimationFrame and cancelAnimationFrame
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb: FrameRequestCallback) => {
      return 1;
    });
    vi.spyOn(window, 'cancelAnimationFrame');

    // Mock crypto.randomUUID for createNewUtterance
    if (!window.crypto) {
        (window as any).crypto = {};
    }
    window.crypto.randomUUID = vi.fn().mockReturnValue('new-uuid');

    fixture.detectChanges();
  });

  it('should create the component', () => {
    expect(component).toBeTruthy();
  });

  it('should load project on init and set edit state', async () => {
    await fixture.whenStable();
    expect(component.videoId()).toBe('test-video-id');
    expect(component.videoData()).not.toBeNull();
    expect(window.fetch).toHaveBeenCalledWith('/api/projects/test-video-id');
    
    // Check if edit state is initialized
    expect(component.editOriginalLanguage()).toBe('en');
    expect(component.editTranslateLanguage()).toBe('es');
    expect(component.editSpeakers().length).toBe(2);
    expect(component.editSpeakers()[0].speaker_id).toBe('spk_1');
    expect(component.editSpeakers()[1].speaker_id).toBe('spk_2');
  });

  it('should display correct languages in script-header', async () => {
    await fixture.whenStable();
    fixture.detectChanges();
    
    const scriptHeader = fixture.nativeElement.querySelector('.script-header');
    expect(scriptHeader).toBeTruthy();
    
    const spans = scriptHeader.querySelectorAll('span');
    expect(spans.length).toBe(2);
    expect(spans[0].textContent).toContain('English');
    expect(spans[1].textContent).toContain('Spanish');
  });

  describe('Utterance Items', () => {
    beforeEach(async () => {
      await fixture.whenStable();
      fixture.detectChanges();
    });

    it('should render all utterances', () => {
      const utterances = fixture.nativeElement.querySelectorAll('.utterance-item');
      expect(utterances.length).toBe(2);
    });

    it('should focus an utterance on click', () => {
      const firstUtterance = fixture.nativeElement.querySelector('.utterance-item');
      firstUtterance.click();
      fixture.detectChanges();
      expect(component.activeUtteranceId()).toBe('utt_1');
      expect(firstUtterance.classList).toContain('active');
    });

    it('should update original text', () => {
      const firstUtterance = component.videoData()?.utterances[0];
      component.updateOriginalText('utt_1', 'New Hello');
      expect(component.videoData()?.utterances[0].original_text).toBe('New Hello');
      expect(component.videoData()?.utterances[0].needs_translation_regen).toBe(true);
    });

    it('should update translated text', () => {
      component.updateTranslatedText('utt_1', 'Nueva Hola');
      expect(component.videoData()?.utterances[0].translated_text).toBe('Nueva Hola');
      expect(component.videoData()?.utterances[0].needs_dubbing_regen).toBe(true);
    });

    it('should toggle mute', () => {
      component.toggleMuteUtterance('utt_1');
      expect(component.videoData()?.utterances[0].muted).toBe(true);
      component.toggleMuteUtterance('utt_1');
      expect(component.videoData()?.utterances[0].muted).toBe(false);
    });

    it('should toggle remove', () => {
      component.toggleRemoveUtterance('utt_1');
      expect(component.videoData()?.utterances[0].removed).toBe(true);
      component.toggleRemoveUtterance('utt_1');
      expect(component.videoData()?.utterances[0].removed).toBe(false);
    });

    it('should call regenerate translation', async () => {
      await component.regenerateTranslation('utt_1');
      expect(window.fetch).toHaveBeenCalledWith('/regenerate_translation', expect.any(Object));
      expect(component.videoData()?.utterances[0].translated_text).toBe('Hola corregido');
    });

    it('should call regenerate dubbing', async () => {
      await component.regenerateDubbing('utt_1');
      expect(window.fetch).toHaveBeenCalledWith('/regenerate_dubbing', expect.any(Object));
      expect(component.videoData()?.utterances[0].audio_url).toBe('new_audio.wav');
    });

    it('should create a new utterance', () => {
      const event = new Event('click');
      component.createNewUtterance(0, event);
      expect(component.videoData()?.utterances.length).toBe(3);
      expect(component.videoData()?.utterances[1].id).toBe('new-uuid');
    });

    it('should merge utterances', () => {
      const event = new Event('click');
      component.mergeUtterances(0, event);
      expect(component.videoData()?.utterances.length).toBe(1);
      expect(component.videoData()?.utterances[0].original_text).toBe('Hello World');
    });
  });

  describe('Adjust timestamps panel', () => {
    beforeEach(async () => {
      await fixture.whenStable();
      fixture.detectChanges();
      // Focus first utterance and open timestamps panel
      component.setActivePanel('utt_1', 'timestamps');
      fixture.detectChanges();
    });

    it('should open the timestamps panel', () => {
      expect(component.activePanelMode()).toBe('timestamps');
      const panelHeader = fixture.nativeElement.querySelector('.panel-header');
      expect(panelHeader.textContent).toContain('Adjust timestamps');
    });

    it('should update start timestamp and linked end timestamp', () => {
      const startInput = fixture.nativeElement.querySelector('.translated-timestamps input:nth-child(1)');
      const endInput = fixture.nativeElement.querySelector('.translated-timestamps div:nth-child(2) input');
      
      component.onStartTimestampInput('00:01.00', endInput);
      fixture.detectChanges();
      
      expect(component.draftTimestamps()?.start).toBe('00:01.00');
      expect(component.draftTimestamps()?.end).toBe('00:03.00'); // Linked: 1.00 + 2.00 duration
    });

    it('should update end timestamp and linked start timestamp', () => {
      const startInput = fixture.nativeElement.querySelector('.translated-timestamps div:nth-child(1) input');
      
      component.onEndTimestampInput(startInput, '00:05.00');
      fixture.detectChanges();
      
      expect(component.draftTimestamps()?.end).toBe('00:05.00');
      expect(component.draftTimestamps()?.start).toBe('00:03.00'); // Linked: 5.00 - 2.00 duration
    });

    it('should save timestamp changes', () => {
      component.draftTimestamps.set({ start: '00:01.00', end: '00:03.00' });
      component.saveTimestamps();
      fixture.detectChanges();
      
      expect(component.videoData()?.utterances[0].translated_start_time).toBe(1);
      expect(component.videoData()?.utterances[0].translated_end_time).toBe(3);
      expect(component.draftTimestamps()).toBeNull();
    });

    it('should cancel timestamp changes', () => {
      component.draftTimestamps.set({ start: '00:01.00', end: '00:03.00' });
      component.cancelTimestamps();
      fixture.detectChanges();
      
      expect(component.draftTimestamps()).toBeNull();
      expect(component.videoData()?.utterances[0].translated_start_time).toBe(0);
    });

    it('should show error for negative start time', () => {
      component.draftTimestamps.set({ start: '-00:01.00', end: '00:01.00' });
      component.saveTimestamps();
      fixture.detectChanges();
      
      expect(component.timestampError()).not.toBeNull();
      expect(component.videoData()?.utterances[0].translated_start_time).toBe(0); // Not saved
    });
  });

  describe('Change speaker panel', () => {
    beforeEach(async () => {
      await fixture.whenStable();
      fixture.detectChanges();
      // Focus first utterance and open speaker panel
      component.setActivePanel('utt_1', 'speaker');
      fixture.detectChanges();
    });

    it('should open the speaker panel', () => {
      expect(component.activePanelMode()).toBe('speaker');
      const panelHeader = fixture.nativeElement.querySelector('.panel-header');
      expect(panelHeader.textContent).toContain('Change speaker');
    });

    it('should select a speaker', () => {
      const bobSpeaker = component.videoData()?.speakers[1];
      if (bobSpeaker) {
        component.onSpeakerSelect(bobSpeaker);
        fixture.detectChanges();
        expect(component.draftSpeaker()).toEqual(bobSpeaker);
      }
    });

    it('should save speaker change', () => {
      const bobSpeaker = component.videoData()?.speakers[1];
      if (bobSpeaker) {
        component.onSpeakerSelect(bobSpeaker);
        component.saveSpeaker();
        fixture.detectChanges();
        
        expect(component.videoData()?.utterances[0].speaker.speaker_id).toBe('spk_2');
        expect(component.videoData()?.utterances[0].needs_dubbing_regen).toBe(true);
        expect(component.draftSpeaker()).toBeNull();
      }
    });
  });

  describe('Video Settings', () => {
    beforeEach(async () => {
      await fixture.whenStable(); // Ensure project is loaded
    });

    it('should toggle edit settings mode', () => {
      expect(component.isEditingSettings()).toBe(false);
      component.toggleEditSettings();
      expect(component.isEditingSettings()).toBe(true);
      component.toggleEditSettings();
      expect(component.isEditingSettings()).toBe(false);
    });

    it('should add a new speaker', () => {
      component.isEditingSettings.set(true);
      const newSpeaker: Speaker = { id: 'spk_3', name: 'Charlie', voice: 'voice_3', voiceName: 'Charlie Voice', gender: 'male' };
      component.onSpeakerAddedOrEdited(newSpeaker);
      expect(component.editSpeakers().length).toBe(3);
      expect(component.editSpeakers()[2]).toEqual(expect.objectContaining({ speaker_id: 'spk_3', name: 'Charlie' }));
    });

    it('should edit an existing speaker', () => {
      component.isEditingSettings.set(true);
      component.speakerToEditId.set('spk_1');
      const editedSpeaker: Speaker = { id: 'spk_1', name: 'Alice V2', voice: 'voice_1_new', voiceName: 'Alice V2 Voice', gender: 'female' };
      component.onSpeakerAddedOrEdited(editedSpeaker);
      expect(component.editSpeakers().length).toBe(2);
      expect(component.editSpeakers()[0]).toEqual(expect.objectContaining({ name: 'Alice V2', voice: 'voice_1_new' }));
    });

    it('should remove a speaker', () => {
      component.isEditingSettings.set(true);
      component.removeEditSpeaker('spk_1');
      expect(component.editSpeakers().length).toBe(1);
    });

    it('should not save settings if nothing changed', async () => {
      component.isEditingSettings.set(true);
      await component.saveVideoSettings();
      expect(window.fetch).not.toHaveBeenCalledWith('/process', expect.any(Object));
      expect(component.isEditingSettings()).toBe(false);
    });

    it('should trigger regenerate_dubbing when a speaker is replaced by a different one', async () => {
      vi.mocked(window.fetch).mockClear();
      component.isEditingSettings.set(true);

      // Add a second speaker
      const speaker2: Speaker = { id: 'spk_2', name: 'Bob', voice: 'voice_2', voiceName: 'Bob Voice', gender: 'male' };
      component.onSpeakerAddedOrEdited(speaker2);
      
      // Remove the original speaker (spk_1)
      // This orphans the utterance that was assigned to spk_1
      component.removeEditSpeaker('spk_1');

      await component.saveVideoSettings();

      // Expect regeneration because the utterance's speaker was deleted
      expect(window.fetch).toHaveBeenCalledWith('/regenerate_dubbing', expect.any(Object));
      expect(component.isEditingSettings()).toBe(false);
    });

    it('should NOT trigger regenerate_dubbing when the same speaker is added back', async () => {
      vi.mocked(window.fetch).mockClear();
      component.isEditingSettings.set(true);

      // Remove the speaker
      component.removeEditSpeaker('spk_1');
      
      // Add it back exactly as it was
      const speaker1: Speaker = { id: 'spk_1', name: 'Alice', voice: 'voice_1', voiceName: 'Alice Voice', gender: 'female' };
      component.onSpeakerAddedOrEdited(speaker1);

      await component.saveVideoSettings();

      // No regeneration expected because the final state matches the initial state
      expect(window.fetch).not.toHaveBeenCalledWith('/regenerate_dubbing', expect.any(Object));
      expect(component.isEditingSettings()).toBe(false);
    });
  });
});
