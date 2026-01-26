/**
 * @jest-environment jsdom
 */

import { appState } from './state';

describe('State', () => {
  it('should have default state', () => {
    expect(appState).toEqual({
      editingSpeakerId: null,
      isEditingVideoSettings: false,
    });
  });

  it('should be mutable', () => {
    appState.editingSpeakerId = '123';
    expect(appState.editingSpeakerId).toBe('123');

    // Reset for other tests (though not strictly necessary if tests are isolated effectively, but this is a singleton)
    appState.editingSpeakerId = null;
  });
});
