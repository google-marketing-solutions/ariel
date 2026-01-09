/**
 * @jest-environment jsdom
 */

import {generateAudio, playAudio} from './audio';
import {showToast} from './utils';

// Mock the showToast function
jest.mock('./utils', () => ({
  showToast: jest.fn(),
}));

// Mock the global Audio object
const mockAudio = {
  play: jest.fn(),
};
global.Audio = jest.fn(() => mockAudio);

describe('Audio Functions', () => {
  beforeEach(() => {
    // Clear all instances and calls to constructor and all methods:
    showToast.mockClear();
    global.Audio.mockClear();
    mockAudio.play.mockClear();
    global.fetch = jest.fn();
  });

  describe('generateAudio', () => {
    it('should call fetch with the correct parameters and return an Audio object', async () => {
      const mockVideoData = {video_id: '123'};
      const mockAudioUrl = 'test.mp3';
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({audio_url: mockAudioUrl}),
      });

      const audio = await generateAudio(mockVideoData);

      expect(fetch).toHaveBeenCalledWith('/generate_audio', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(mockVideoData),
      });

      expect(Audio).toHaveBeenCalledWith(mockAudioUrl);
      expect(showToast).toHaveBeenCalledWith(
        'Audio generated successfully',
        'success',
      );
      expect(audio).toBe(mockAudio);
    });

    it('should handle fetch errors gracefully and return null', async () => {
      const mockVideoData = {video_id: '123'};
      global.fetch.mockResolvedValue({
        ok: false,
        status: 500,
      });

      const audio = await generateAudio(mockVideoData);

      expect(showToast).toHaveBeenCalledWith(
        'HTTP error! status: 500',
        'error',
      );
      expect(audio).toBeNull();
    });
  });

  describe('playAudio', () => {
    it('should call play on the audio object if it exists', () => {
      playAudio(mockAudio);
      expect(mockAudio.play).toHaveBeenCalled();
    });

    it('should show a toast message if no audio is available to play', () => {
      playAudio(null);
      expect(mockAudio.play).not.toHaveBeenCalled();
      expect(showToast).toHaveBeenCalledWith('No audio to play', 'error');
    });
  });
});
