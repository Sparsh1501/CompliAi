import React, { createContext, useContext, useState, useEffect } from 'react';
import { getTheme, DEFAULT_THEME } from '../config/themes';

const ThemeContext = createContext();

export const useTheme = () => {
    const context = useContext(ThemeContext);
    if (!context) {
        throw new Error('useTheme must be used within a ThemeProvider');
    }
    return context;
};

export const ThemeProvider = ({ children }) => {
    const [currentTheme, setCurrentTheme] = useState(DEFAULT_THEME);
    const [isLoading, setIsLoading] = useState(true);
    const [previewTheme, setPreviewTheme] = useState(null);

    // Apply theme to document root
    const applyTheme = (themeId) => {
        const theme = getTheme(themeId);
        const root = document.documentElement;

        // Apply all color variables
        Object.entries(theme.colors).forEach(([key, value]) => {
            root.style.setProperty(`--color-${key}`, value);
        });

        // Set data attribute for theme type
        root.setAttribute('data-theme', theme.type);
        root.setAttribute('data-theme-id', theme.id);
    };

    // Load theme from backend on mount
    useEffect(() => {
        const loadTheme = async () => {
            try {
                const token = localStorage.getItem('token');
                if (token) {
                    const response = await fetch('/api/user/theme', {
                        headers: { 'Authorization': `Bearer ${token}` }
                    });
                    if (response.ok) {
                        const data = await response.json();
                        setCurrentTheme(data.preferred_theme || DEFAULT_THEME);
                    }
                }
            } catch (error) {
                console.error('Failed to load theme from backend:', error);
                // Fall back to localStorage
                const localTheme = localStorage.getItem('theme');
                if (localTheme) setCurrentTheme(localTheme);
            } finally {
                setIsLoading(false);
            }
        };
        loadTheme();
    }, []);

    // Apply theme on mount and when currentTheme changes
    useEffect(() => {
        if (!isLoading) {
            applyTheme(previewTheme || currentTheme);
        }
    }, [currentTheme, previewTheme, isLoading]);

    // Change theme permanently
    const changeTheme = async (themeId) => {
        setCurrentTheme(themeId);
        setPreviewTheme(null);
        localStorage.setItem('theme', themeId);

        // Save to backend
        try {
            const token = localStorage.getItem('token');
            if (token) {
                await fetch('/api/user/theme', {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({ theme_id: themeId })
                });
            }
        } catch (error) {
            console.error('Failed to save theme to backend:', error);
        }
    };

    // Preview theme temporarily (for live preview)
    const previewThemeChange = (themeId) => {
        setPreviewTheme(themeId);
    };

    // Cancel preview and revert to current theme
    const cancelPreview = () => {
        setPreviewTheme(null);
    };

    // Apply previewed theme permanently
    const applyPreview = () => {
        if (previewTheme) {
            changeTheme(previewTheme);
        }
    };

    const value = {
        currentTheme,
        previewTheme,
        activeTheme: previewTheme || currentTheme,
        changeTheme,
        previewThemeChange,
        cancelPreview,
        applyPreview,
        isPreviewMode: !!previewTheme,
    };

    return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
};
