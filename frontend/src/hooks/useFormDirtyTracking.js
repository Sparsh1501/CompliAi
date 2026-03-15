import { useState, useEffect, useCallback } from 'react';

/**
 * Custom hook to track if a form has unsaved changes
 * @param {Object} initialValues - The initial form values
 * @param {Object} currentValues - The current form values
 * @returns {Object} { isDirty, markClean, confirmNavigation }
 */
export const useFormDirtyTracking = (initialValues, currentValues) => {
  const [isDirty, setIsDirty] = useState(false);

  // Check if form values have changed from initial state
  useEffect(() => {
    const hasChanges = JSON.stringify(initialValues) !== JSON.stringify(currentValues);
    setIsDirty(hasChanges);
  }, [initialValues, currentValues]);

  // Mark form as clean (e.g., after successful submission)
  const markClean = useCallback(() => {
    setIsDirty(false);
  }, []);

  // Add beforeunload listener to warn on browser refresh/close
  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = ''; // Chrome requires returnValue to be set
        return '';
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isDirty]);

  return {
    isDirty,
    markClean
  };
};
