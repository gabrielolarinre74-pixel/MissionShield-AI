import type { Metadata } from 'next';
import { Source_Sans_3, IBM_Plex_Mono } from 'next/font/google';
import './globals.css';

// Primary interface font — loaded and self-hosted at build time via next/font.
// The variable classes are applied on <html> so the CSS custom properties
// referenced by globals.css :root rules resolve (the previous bug applied
// them to <body>, which made --font-sans invalid and fell back to serif).
const sourceSans = Source_Sans_3({
  subsets: ['latin'],
  variable: '--font-source-sans',
});

// Restrained monospace for technical values only (telemetry, timestamps,
// measurements, machine identifiers).
const plexMono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-plex-mono',
});

export const metadata: Metadata = {
  title: 'MissionShield AI — Space Mission Decision Support',
  description:
    'AI-powered space mission decision-support platform. Real NASA/NOAA space-weather data, deterministic mission risk analysis, and IBM Granite mission intelligence.',
};

// Runs before first paint to set the persisted (or OS-preferred) theme and
// prevent a flash of the wrong color scheme. Dark is the CSS default.
const THEME_INIT_SCRIPT = `(function(){
  try {
    var key = 'missionshield_theme';
    var stored = null;
    try { stored = localStorage.getItem(key); } catch (e) {}
    var theme = 'dark';
    if (stored === 'light' || stored === 'dark') {
      theme = stored;
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
      theme = 'light';
    }
    document.documentElement.setAttribute('data-theme', theme);
    var meta = document.querySelector('meta[name="color-scheme"]');
    if (meta) meta.setAttribute('content', theme);
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
})();`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${sourceSans.variable} ${plexMono.variable}`}>
      <head>
        <meta name="color-scheme" content="dark" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
