import type { Metadata } from 'next';
import { Manrope, IBM_Plex_Mono } from 'next/font/google';
import './globals.css';

// Primary interface font — loaded and self-hosted at build time via next/font.
const manrope = Manrope({
  subsets: ['latin'],
  variable: '--font-manrope',
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

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <meta name="color-scheme" content="dark" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>
      <body className={`${manrope.variable} ${plexMono.variable}`}>{children}</body>
    </html>
  );
}
