/**
 * Centralized Font Configuration for Fed-Med-FL UI
 * 
 * Change the font family here to update it across the entire application.
 * All available options are listed below with their characteristics.
 */

// ============================================================================
// AVAILABLE FONT OPTIONS
// ============================================================================

export const AVAILABLE_FONTS = {
  /**
   * INTER - Modern, highly legible sans-serif (RECOMMENDED for medical apps)
   * - Optimized for screens and data-heavy interfaces
   * - Excellent for numbers and technical content
   * - Used by: GitHub, Mozilla, Stripe
   */
  inter: {
    name: 'Inter',
    family: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    googleFontsUrl: 'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap',
    weights: [300, 400, 500, 600, 700],
  },

  /**
   * ROBOTO - Material Design standard, geometric sans-serif
   * - Very popular and well-tested
   * - Friendly and professional
   * - Used by: Google, Android
   */
  roboto: {
    name: 'Roboto',
    family: "'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    googleFontsUrl: 'https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap',
    weights: [300, 400, 500, 700],
  },

  /**
   * OPEN SANS - Humanist sans-serif, warm and professional
   * - Highly legible
   * - Great for enterprise applications
   * - Used by: Many enterprise apps
   */
  openSans: {
    name: 'Open Sans',
    family: "'Open Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    googleFontsUrl: 'https://fonts.googleapis.com/css2?family=Open+Sans:wght@300;400;500;600;700&display=swap',
    weights: [300, 400, 500, 600, 700],
  },

  /**
   * POPPINS - Modern geometric sans-serif
   * - Very trendy and clean
   * - Great for modern applications
   * - Used by: Modern startups, SaaS apps
   */
  poppins: {
    name: 'Poppins',
    family: "'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    googleFontsUrl: 'https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap',
    weights: [300, 400, 500, 600, 700],
  },

  /**
   * IBM PLEX SANS - Corporate sans-serif
   * - Professional and clean
   * - Excellent for dashboards
   * - Used by: IBM, enterprise applications
   */
  ibmPlexSans: {
    name: 'IBM Plex Sans',
    family: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    googleFontsUrl: 'https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&display=swap',
    weights: [300, 400, 500, 600, 700],
  },

  /**
   * NUNITO - Rounded sans-serif, friendly
   * - Very pleasant visually
   * - Modern and approachable
   * - Used by: Modern SaaS applications
   */
  nunito: {
    name: 'Nunito',
    family: "'Nunito', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    googleFontsUrl: 'https://fonts.googleapis.com/css2?family=Nunito:wght@300;400;500;600;700&display=swap',
    weights: [300, 400, 500, 600, 700],
  },

  /**
   * SYSTEM DEFAULT - Use system fonts (fastest, no download)
   * - No external font loading
   * - Best performance
   * - Native look and feel
   */
  system: {
    name: 'System Default',
    family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif",
    googleFontsUrl: null,
    weights: [300, 400, 500, 600, 700],
  },
} as const;

// ============================================================================
// ACTIVE FONT CONFIGURATION
// ============================================================================

/**
 * 🎨 CHANGE THIS TO UPDATE THE FONT ACROSS THE ENTIRE APPLICATION
 * 
 * Options: 'inter' | 'roboto' | 'openSans' | 'poppins' | 'ibmPlexSans' | 'nunito' | 'system'
 * 
 * Recommended: 'inter' for medical/professional applications
 */
export const ACTIVE_FONT_KEY = 'inter' as keyof typeof AVAILABLE_FONTS;

// ============================================================================
// EXPORTED CONFIGURATION (DO NOT MODIFY)
// ============================================================================

export const activeFont = AVAILABLE_FONTS[ACTIVE_FONT_KEY];

export const fontConfig = {
  family: activeFont.family,
  googleFontsUrl: activeFont.googleFontsUrl,
  name: activeFont.name,
  weights: activeFont.weights,
};

// Export for easy access
export default fontConfig;
