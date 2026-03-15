import React, { useState } from 'react';
import { themes, getDarkThemes, getLightThemes } from '../config/themes';
import { useTheme } from '../context/ThemeContext';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Check, Palette } from 'lucide-react';
import { Badge } from './ui/badge';

export default function ThemeSelector() {
    const { currentTheme, previewTheme, activeTheme, changeTheme, previewThemeChange, cancelPreview, applyPreview, isPreviewMode } = useTheme();
    const [selectedCategory, setSelectedCategory] = useState('all');

    const darkThemes = getDarkThemes();
    const lightThemes = getLightThemes();

    const getDisplayThemes = () => {
        if (selectedCategory === 'dark') return darkThemes;
        if (selectedCategory === 'light') return lightThemes;
        return Object.values(themes);
    };

    const handleThemeClick = (themeId) => {
        previewThemeChange(themeId);
    };

    const handleApply = () => {
        applyPreview();
    };

    const handleCancel = () => {
        cancelPreview();
    };

    return (
        <div className="space-y-6">
            {/* Category Filter */}
            <div className="flex gap-2">
                <Button
                    variant={selectedCategory === 'all' ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setSelectedCategory('all')}
                >
                    All Themes
                </Button>
                <Button
                    variant={selectedCategory === 'dark' ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setSelectedCategory('dark')}
                >
                    Dark ({darkThemes.length})
                </Button>
                <Button
                    variant={selectedCategory === 'light' ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setSelectedCategory('light')}
                >
                    Light ({lightThemes.length})
                </Button>
            </div>

            {/* Preview Mode Banner */}
            {isPreviewMode && (
                <div className="flex items-center justify-between p-4 bg-blue-50 border border-blue-200 rounded-lg">
                    <div className="flex items-center gap-2">
                        <Palette className="h-5 w-5 text-blue-600" />
                        <div>
                            <p className="text-sm font-medium text-blue-900">Preview Mode Active</p>
                            <p className="text-xs text-blue-700">You're previewing: {themes[previewTheme]?.name}</p>
                        </div>
                    </div>
                    <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={handleCancel}>
                            Cancel
                        </Button>
                        <Button size="sm" onClick={handleApply} className="bg-blue-600 hover:bg-blue-700 text-white">
                            Apply Changes
                        </Button>
                    </div>
                </div>
            )}

            {/* Theme Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {getDisplayThemes().map((theme) => {
                    const isActive = theme.id === activeTheme;
                    const isCurrent = theme.id === currentTheme;

                    return (
                        <Card
                            key={theme.id}
                            className={`cursor-pointer transition-all hover:shadow-lg ${isActive ? 'ring-2 ring-primary ring-offset-2' : ''
                                }`}
                            onClick={() => handleThemeClick(theme.id)}
                        >
                            <CardContent className="p-4">
                                {/* Theme Name & Badge */}
                                <div className="flex items-center justify-between mb-3">
                                    <div className="flex items-center gap-2">
                                        <h3 className="font-semibold text-sm">{theme.name}</h3>
                                        {isCurrent && !isPreviewMode && (
                                            <Check className="h-4 w-4 text-green-600" />
                                        )}
                                    </div>
                                    <Badge variant={theme.type === 'dark' ? 'secondary' : 'default'} className="text-xs">
                                        {theme.type === 'dark' ? 'Dark' : 'Light'}
                                    </Badge>
                                </div>

                                {/* Color Preview */}
                                <div className="space-y-2">
                                    {/* Primary & Secondary */}
                                    <div className="flex gap-2 h-12 rounded-md overflow-hidden">
                                        <div
                                            className="flex-1"
                                            style={{ backgroundColor: theme.preview.primary }}
                                            title="Primary"
                                        />
                                        <div
                                            className="flex-1"
                                            style={{ backgroundColor: theme.preview.secondary }}
                                            title="Secondary"
                                        />
                                    </div>

                                    {/* Background Preview */}
                                    <div
                                        className="h-16 rounded-md border flex items-center justify-center"
                                        style={{ backgroundColor: theme.preview.background }}
                                    >
                                        <div
                                            className="w-3/4 h-8 rounded"
                                            style={{ backgroundColor: theme.colors.surface }}
                                        />
                                    </div>
                                </div>

                                {/* Status Indicator */}
                                {isActive && (
                                    <div className="mt-3 text-xs text-center font-medium text-primary">
                                        {isPreviewMode ? 'Previewing' : 'Active'}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    );
                })}
            </div>
        </div>
    );
}
