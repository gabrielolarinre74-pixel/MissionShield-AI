import type { Metadata } from 'next';
import './globals.css';

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
      <body>{children}</body>
    </html>
  );
}
