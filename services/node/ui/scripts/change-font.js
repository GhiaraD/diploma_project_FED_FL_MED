#!/usr/bin/env node

/**
 * Quick Font Changer Script
 * 
 * Usage: node scripts/change-font.js <font-name>
 * Example: node scripts/change-font.js poppins
 */

const fs = require('fs');
const path = require('path');

const FONTS_CONFIG_PATH = path.join(__dirname, '../src/config/fonts.ts');

const AVAILABLE_FONTS = [
  'inter',
  'roboto',
  'openSans',
  'poppins',
  'ibmPlexSans',
  'nunito',
  'system'
];

const FONT_DESCRIPTIONS = {
  inter: 'Modern, highly legible (RECOMMENDED for medical apps)',
  roboto: 'Material Design standard',
  openSans: 'Humanist, warm and professional',
  poppins: 'Modern geometric, trendy',
  ibmPlexSans: 'Corporate, excellent for dashboards',
  nunito: 'Rounded, friendly',
  system: 'Use system fonts (fastest, no download)'
};

function showUsage() {
  console.log('\n🎨 Fed-Med-FL Font Changer\n');
  console.log('Usage: node scripts/change-font.js <font-name>\n');
  console.log('Available fonts:');
  AVAILABLE_FONTS.forEach(font => {
    console.log(`  • ${font.padEnd(15)} - ${FONT_DESCRIPTIONS[font]}`);
  });
  console.log('\nExample: node scripts/change-font.js poppins\n');
}

function changeFont(fontName) {
  if (!AVAILABLE_FONTS.includes(fontName)) {
    console.error(`\n❌ Error: Unknown font "${fontName}"\n`);
    showUsage();
    process.exit(1);
  }

  try {
    // Read the fonts config file
    let content = fs.readFileSync(FONTS_CONFIG_PATH, 'utf8');

    // Find and replace the ACTIVE_FONT_KEY line
    const regex = /export const ACTIVE_FONT_KEY = '[^']+' as keyof typeof AVAILABLE_FONTS;/;
    const newLine = `export const ACTIVE_FONT_KEY = '${fontName}' as keyof typeof AVAILABLE_FONTS;`;

    if (!regex.test(content)) {
      console.error('\n❌ Error: Could not find ACTIVE_FONT_KEY in fonts.ts\n');
      process.exit(1);
    }

    content = content.replace(regex, newLine);

    // Write back to file
    fs.writeFileSync(FONTS_CONFIG_PATH, content, 'utf8');

    console.log('\n✅ Font changed successfully!\n');
    console.log(`   New font: ${fontName}`);
    console.log(`   Description: ${FONT_DESCRIPTIONS[fontName]}\n`);
    console.log('🔄 Next steps:');
    console.log('   1. Rebuild the UI: npm run build');
    console.log('   2. Restart the dev server: npm run dev');
    console.log('   3. Or restart Docker: docker compose restart node1-ui\n');

  } catch (error) {
    console.error('\n❌ Error changing font:', error.message, '\n');
    process.exit(1);
  }
}

// Main
const args = process.argv.slice(2);

if (args.length === 0 || args[0] === '--help' || args[0] === '-h') {
  showUsage();
  process.exit(0);
}

const fontName = args[0];
changeFont(fontName);
