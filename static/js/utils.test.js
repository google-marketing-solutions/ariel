
import { checkOverlap } from './utils';

describe('checkOverlap', () => {
  test('NO overlap, should return empty array', () => {
    // Arrange
    const utterance = { id: 1, translated_start_time: 0, translated_end_time: 5 };
    const otherUtterance = { id: 2, translated_start_time: 10, translated_end_time: 15 };
    const allUtterances = [otherUtterance];
    // Act
    const result = checkOverlap(utterance, allUtterances);
    // Assert
    expect(result).toEqual([]);
  });

  test('PARTIAL OVERLAP, should return error message', () => {
    // Arrange
    const utterance = { id: 1, translated_start_time: 0, translated_end_time: 5 };
    const otherUtterance = { id: 2, translated_start_time: 3, translated_end_time: 8 };
    const allUtterances = [otherUtterance];
    // Act
    const result = checkOverlap(utterance, allUtterances);
    // Assert
    expect(result).toEqual(['Translated time overlaps with another utterance.']);
  });

  test('ENCLOSED OVERLAP, should return error message', () => {
    // Arrange
    const utterance = { id: 1, translated_start_time: 2, translated_end_time: 4 };
    const otherUtterance = { id: 2, translated_start_time: 0, translated_end_time: 8 };
    const allUtterances = [otherUtterance];
    // Act
    const result = checkOverlap(utterance, allUtterances);
    // Assert
    expect(result).toEqual(['Translated time overlaps with another utterance.']);
  });

  test('SAME ID, should return empty array', () => {
    // Arrange
    const utterance = { id: 1, translated_start_time: 2, translated_end_time: 4 };
    const otherUtterance = { id: 1, translated_start_time: 2, translated_end_time: 4 };
    const allUtterances = [otherUtterance];
    // Act
    const result = checkOverlap(utterance, allUtterances);
    // Assert
    expect(result).toEqual([]);
  });

  test('REMOVED UTTERANCE, should return empty array', () => {
    // Arrange
    const utterance = { id: 1, translated_start_time: 2, translated_end_time: 4, removed: true };
    const otherUtterance = { id: 2, translated_start_time: 2, translated_end_time: 4 };
    const allUtterances = [otherUtterance];
    // Act
    const result = checkOverlap(utterance, allUtterances);
    // Assert
    expect(result).toEqual([]);
  });
});
