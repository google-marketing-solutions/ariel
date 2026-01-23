/**
 * @jest-environment jsdom
 */

import {editUtterance} from './utterance';
import {runRegenerateDubbing, runRegenerateTranslation} from './api';
import {showToast} from './utils';
import {renderTimeline} from './timeline';

jest.mock('./api', () => ({
  runRegenerateDubbing: jest.fn(),
  runRegenerateTranslation: jest.fn(),
}));

jest.mock('./utils', () => ({
  showToast: jest.fn(),
}));

jest.mock('./timeline', () => ({
  renderTimeline: jest.fn(),
}));

describe('Utterance Editor', () => {
  let utterance;
  let currentVideoData;
  let speakers;
  let videoDuration;

  beforeEach(() => {
    document.body.innerHTML = `
      <div id="utterance-editor" style="display: none;">
        <div id="utterance-editor-content"></div>
        <button class="btn-close"></button>
      </div>
      <div id="utterances-list"></div>
      <div id="toast-container"></div>
      <div id="confirmation-modal">
        <div class="modal-title"></div>
        <div class="modal-body"></div>
        <button id="confirm-close-btn"></button>
      </div>
    `;

    utterance = {
      id: 'utterance_1',
      original_text: 'Hello world',
      translated_text: 'Bonjour le monde',
      original_start_time: 0,
      original_end_time: 1,
      translated_start_time: 0,
      translated_end_time: 1,
      speaker: {voice: 'voice_1', gender: 'female'},
    };

    currentVideoData = {
      utterances: [utterance],
    };
    speakers = [{voice: 'voice_1', name: 'Speaker 1'}];
    videoDuration = 10;
    utteranceEditor = document.getElementById('utterance-editor');

    // Mock the bootstrap Modal
    window.bootstrap = {
      Modal: jest.fn().mockImplementation(() => ({
        show: jest.fn(),
        hide: jest.fn(),
      })),
    };

    // Mock remove function for toast
    const mockToast = {remove: jest.fn()};
    showToast.mockReturnValue(mockToast);
    runRegenerateTranslation.mockResolvedValue(utterance);
    runRegenerateDubbing.mockResolvedValue(utterance);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('Regenerate Translation Button', () => {
    it('should show success toast on successful translation regeneration', async () => {
      editUtterance(utterance, 0, currentVideoData, speakers, videoDuration);

      const regenerateBtn = document.getElementById(
        'regenerate-translation-btn',
      );
      regenerateBtn.click();

      expect(showToast).toHaveBeenCalledWith(
        'Regenerating translation...',
        'info',
        0,
      );

      // Wait for the promise to resolve
      await Promise.resolve();

      expect(runRegenerateTranslation).toHaveBeenCalled();
      const inProgressToast = showToast.mock.results[0].value;
      expect(inProgressToast.remove).toHaveBeenCalled();
      expect(showToast).toHaveBeenCalledWith(
        'Translation regenerated successfully!',
        'success',
        6000,
      );
    });

    it('should show error toast on failed translation regeneration', async () => {
      const error = new Error('Failed to regenerate');
      runRegenerateTranslation.mockRejectedValue(error);

      editUtterance(utterance, 0, currentVideoData, speakers, videoDuration);

      const regenerateBtn = document.getElementById(
        'regenerate-translation-btn',
      );
      regenerateBtn.click();

      expect(showToast).toHaveBeenCalledWith(
        'Regenerating translation...',
        'info',
        0,
      );

      // Wait for the promise to resolve
      await Promise.resolve();
      await Promise.resolve();

      expect(runRegenerateTranslation).toHaveBeenCalled();
      const inProgressToast = showToast.mock.results[0].value;
      expect(inProgressToast.remove).toHaveBeenCalled();
      expect(showToast).toHaveBeenCalledWith(
        'Failed to regenerate translation.',
        'error',
        6000,
      );
    });
  });

  describe('Regenerate Dubbing Button', () => {
    it('should show success toast on successful dubbing regeneration', async () => {
      editUtterance(utterance, 0, currentVideoData, speakers, videoDuration);

      const regenerateBtn = document.getElementById('regenerate-dubbing-btn');
      regenerateBtn.click();

      expect(showToast).toHaveBeenCalledWith('Regenerating dubbing...', 'info', 0);

      // Wait for the promise to resolve
      await Promise.resolve();

      expect(runRegenerateDubbing).toHaveBeenCalled();
      const inProgressToast = showToast.mock.results[0].value;
      expect(inProgressToast.remove).toHaveBeenCalled();
      expect(showToast).toHaveBeenCalledWith(
        'Dubbing regenerated successfully!',
        'success',
        6000,
      );
      expect(renderTimeline).toHaveBeenCalled();
    });

    it('should show error toast on failed dubbing regeneration', async () => {
      const error = new Error('Failed to regenerate');
      runRegenerateDubbing.mockRejectedValue(error);

      editUtterance(utterance, 0, currentVideoData, speakers, videoDuration);

      const regenerateBtn = document.getElementById('regenerate-dubbing-btn');
      regenerateBtn.click();

      expect(showToast).toHaveBeenCalledWith('Regenerating dubbing...', 'info', 0);

      // Wait for the promise to resolve
      await Promise.resolve();
      await Promise.resolve();

      expect(runRegenerateDubbing).toHaveBeenCalled();
      const inProgressToast = showToast.mock.results[0].value;
      expect(inProgressToast.remove).toHaveBeenCalled();
      expect(showToast).toHaveBeenCalledWith(
        'Failed to regenerate dubbing.',
        'error',
      );
    });

    it('should show error toast when dubbing regeneration results in zero duration', async () => {
      const zeroDurationUtterance = {...utterance, translated_end_time: utterance.translated_start_time};
      runRegenerateDubbing.mockResolvedValue(zeroDurationUtterance);
      editUtterance(utterance, 0, currentVideoData, speakers, videoDuration);

      const regenerateBtn = document.getElementById('regenerate-dubbing-btn');
      regenerateBtn.click();

      expect(showToast).toHaveBeenCalledWith('Regenerating dubbing...', 'info', 0);

      // Wait for the promise to resolve
      await Promise.resolve();

      expect(runRegenerateDubbing).toHaveBeenCalled();
      const inProgressToast = showToast.mock.results[0].value;
      expect(inProgressToast.remove).toHaveBeenCalled();
      expect(showToast).toHaveBeenCalledWith(
        'Dubbing regeneration failed.',
        'error',
        6000,
      );
      expect(renderTimeline).toHaveBeenCalled();
    });
  });
});
