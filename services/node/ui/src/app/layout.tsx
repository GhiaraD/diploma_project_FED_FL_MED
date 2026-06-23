import type { Metadata } from "next";
import { AppRouterCacheProvider } from '@mui/material-nextjs/v15-appRouter';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import theme from './theme';
import { AuthProvider } from '@/contexts/AuthContext';
import { fontConfig } from '@/config/fonts';
import "./globals.css";

export const metadata: Metadata = {
  title: "Fed-Med-FL - Node Portal",
  description: "Federated Learning Medical Imaging Platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        {/* Load Google Fonts if configured */}
        {fontConfig.googleFontsUrl && (
          <link
            rel="stylesheet"
            href={fontConfig.googleFontsUrl}
            crossOrigin="anonymous"
          />
        )}
      </head>
      <body>
        <AppRouterCacheProvider>
          <ThemeProvider theme={theme}>
            <CssBaseline />
            <AuthProvider>
              {children}
            </AuthProvider>
          </ThemeProvider>
        </AppRouterCacheProvider>
      </body>
    </html>
  );
}
