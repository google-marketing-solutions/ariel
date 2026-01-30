/**
 * @jest-environment jsdom
 */

import {
    fetchLanguages,
    fetchVoices,
    processVideo,
    regenerateTranslation,
    runRegenerateTranslation
} from './api';

describe('API Functions', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
    // Reset console.log to avoid cluttering test output
    jest.spyOn(console, 'log').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('fetchLanguages', () => {
    it('should fetch languages and populate select elements', async () => {
      const mockLanguages = [
        {name: 'English', code: 'en-US', readiness: 'GA'},
        {name: 'French', code: 'fr-FR', readiness: 'Preview'},
      ];
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockLanguages),
      });

      const originalSelect = document.createElement('select');
      const translationSelect = document.createElement('select');

      await fetchLanguages(originalSelect, translationSelect);

      expect(fetch).toHaveBeenCalledWith('static/languages.json');
      expect(originalSelect.options.length).toBeGreaterThan(0);
      expect(translationSelect.options.length).toBeGreaterThan(0);
    });

    it('should throw error if fetch fails', async () => {
      global.fetch.mockResolvedValue({
        ok: false,
        status: 404,
      });

      const originalSelect = document.createElement('select');
      const translationSelect = document.createElement('select');

      await expect(
        fetchLanguages(originalSelect, translationSelect),
      ).rejects.toThrow('HTTP error! status: 404');
    });
  });

  describe('fetchVoices', () => {
    it('should fetch voices successfully', async () => {
      const mockVoices = [{name: 'Voice 1', id: 'v1'}];
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockVoices),
      });

      const result = await fetchVoices();
      expect(result).toEqual(mockVoices);
    });
  });

  describe('processVideo', () => {
    it('should process video successfully', async () => {
      const mockFormData = new FormData();
      const mockResponse = {success: true};
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await processVideo(mockFormData);
      expect(fetch).toHaveBeenCalledWith('/process', {
        method: 'POST',
        body: mockFormData,
      });
      expect(result).toEqual(mockResponse);
    });

    it('should handle 413 error', async () => {
      global.fetch.mockResolvedValue({
        ok: false,
        status: 413,
      });

      await expect(processVideo(new FormData())).rejects.toThrow(
        'Video file is too large',
      );
    });
  });

  // Add more tests for other functions similar to processVideo...
  describe('regenerateTranslation', () => {
    it('should regenerate translation successfully', async () => {
        const mockResponse = {translated_text: 'Bonjour'};
        global.fetch.mockResolvedValue({
            ok: true,
            json: () => Promise.resolve(mockResponse)
        });

        const result = await regenerateTranslation({}, 0, 'Translate to French');
        expect(result).toEqual(mockResponse);
    });
  });

  describe('runRegenerateTranslation', () => {
      it('should update utterance with new translation', async () => {
          const mockResult = {
              translated_text: 'New Text',
              duration: 5,
              audio_url: 'audio.mp3'
          };
          global.fetch.mockResolvedValue({
              ok: true,
              json: () => Promise.resolve(mockResult)
          });

          const utterance = {translated_start_time: 0};
          const updated = await runRegenerateTranslation({}, utterance, 0, '');

          expect(updated.translated_text).toBe(mockResult.translated_text);
          expect(updated.translated_end_time).toBe(5);
          expect(updated.audio_url).toBe(mockResult.audio_url);
      });
  });
});
