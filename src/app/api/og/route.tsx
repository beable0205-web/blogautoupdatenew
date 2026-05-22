import { ImageResponse } from 'next/og';

export const runtime = 'edge';

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const top = searchParams.get('top') || '블로그 왕초보 필수';
    const mid = searchParams.get('mid') || '블로그';
    const bottom = searchParams.get('bottom') || '챌린지';
    const bgUrl = searchParams.get('bg');
    const style = searchParams.get('style') || 'blog1';

    // Simple deterministic hash based on text to generate dynamic styles
    const getHash = (str: string) => {
      let hash = 0;
      for (let i = 0; i < str.length; i++) {
        hash = (hash << 5) - hash + str.charCodeAt(i);
        hash |= 0;
      }
      return Math.abs(hash);
    };

    const seed = getHash(mid + bottom + top);
    const isDarkTheme = seed % 3 === 0; // 1 in 3 chance of dark theme for high variation
    
    // Randomize Glassmorphic Card Dimensions (width/height 780px to 900px)
    const cardWidth = 780 + (seed % 120);
    const cardHeight = 780 + ((seed >> 2) % 120);
    const cardRadius = 40 + (seed % 50); // 40px to 90px
    const cardBorderWidth = 2 + (seed % 4); // 2px to 5px
    
    // Card opacity and color based on theme
    const cardBg = isDarkTheme 
      ? `rgba(15, 23, 42, ${0.60 + ((seed % 15) / 100)})` 
      : `rgba(255, 255, 255, ${0.68 + ((seed % 15) / 100)})`;
      
    const cardBorderColor = isDarkTheme
      ? `rgba(255, 255, 255, ${0.15 + ((seed % 10) / 100)})`
      : `rgba(255, 255, 255, ${0.40 + ((seed % 15) / 100)})`;

    // Dynamic fonts colors
    const fontColor = isDarkTheme ? '#F8FAFC' : '#1E293B';
    const secondaryFontColor = isDarkTheme ? '#E2E8F0' : '#334155';

    // Base color palettes based on hash
    const colorPalettes = [
      { glow1: '#818CF8', glow2: '#C084FC', badgeColor: '#4F46E5', badgeBg: 'rgba(79, 70, 229, 0.15)', bottomColor: '#6366F1' }, // Indigo/Purple
      { glow1: '#22D3EE', glow2: '#818CF8', badgeColor: '#0891B2', badgeBg: 'rgba(8, 145, 178, 0.15)', bottomColor: '#06B6D4' }, // Cyan/Blue
      { glow1: '#F472B6', glow2: '#FB7185', badgeColor: '#DB2777', badgeBg: 'rgba(219, 39, 119, 0.15)', bottomColor: '#E11D48' }, // Pink/Rose
      { glow1: '#34D399', glow2: '#6EE7B7', badgeColor: '#059669', badgeBg: 'rgba(5, 150, 105, 0.15)', bottomColor: '#10B981' }, // Emerald/Teal
      { glow1: '#FBBF24', glow2: '#F59E0B', badgeColor: '#D97706', badgeBg: 'rgba(217, 119, 6, 0.15)', bottomColor: '#F59E0B' }, // Amber/Orange
      { glow1: '#A78BFA', glow2: '#F472B6', badgeColor: '#7C3AED', badgeBg: 'rgba(124, 58, 237, 0.15)', bottomColor: '#8B5CF6' }  // Purple/Pink
    ];
    const palette = colorPalettes[seed % colorPalettes.length];

    // Dynamic backgrounds
    let bgGradient = 'linear-gradient(to bottom right, #1E1B4B, #4F46E5)';
    if (seed % 4 === 1) {
      bgGradient = 'linear-gradient(to bottom right, #0F172A, #1E293B)'; // Dark Slate
    } else if (seed % 4 === 2) {
      bgGradient = 'linear-gradient(to bottom right, #064E3B, #022C22)'; // Deep Forest
    } else if (seed % 4 === 3) {
      bgGradient = 'linear-gradient(to bottom right, #4A044E, #1F0022)'; // Deep Violet
    }

    // Hashtags converter
    const topTags = top.includes('#') ? top : `#${top.split(' ').filter(t => t.trim() !== '').join(' #')}`;
    
    // Dynamic sizes for fonts
    const getFontSize = (text: string) => {
      if (text.length > 12) return 80;
      if (text.length > 8) return 105;
      if (text.length > 5) return 130;
      return 170;
    };
    
    const midSize = getFontSize(mid);
    const bottomSize = getFontSize(bottom);

    // Dynamic editorial signature list (bypasses automatic signature filtering)
    const signatures = [
      'DAILY LIFE & INFO',
      'TREND FOCUS INSIGHT',
      'DAILY ECONOMIC NOTES',
      'WEEKLY TREND REPORT',
      'LIVING & LIFE INFO',
      'TODAY HOT TOPIC',
      'REAL LIFE ISSUES',
      'FINANCIAL GUIDE & TIPS',
      'REAL ESTATE & FINANCE',
      'HEALTH & LIFE DIRECTORY',
      'PREMIUM INSIGHT REPORT',
      'LIFE DESIGN DIGEST'
    ];
    const activeSignature = signatures[seed % signatures.length];

    // Dynamic position shift for glows (100px to 300px variations)
    const glow1X = 100 + (seed % 200);
    const glow1Y = 80 + ((seed >> 1) % 180);
    const glow2X = 100 + ((seed >> 2) % 200);
    const glow2Y = 100 + ((seed >> 3) % 200);

    return new ImageResponse(
      (
        <div
          style={{
            height: '100%',
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundImage: bgUrl ? 'none' : bgGradient,
            backgroundColor: bgUrl ? '#111' : 'transparent',
            fontFamily: 'sans-serif',
            position: 'relative',
            overflow: 'hidden',
          }}
        >
          {bgUrl && (
            // eslint-disable-next-line @next/next/no-img-element
            <img 
              src={bgUrl} 
              alt="bg" 
              style={{ 
                position: 'absolute', 
                top: 0, 
                left: 0, 
                width: '100%', 
                height: '100%', 
                objectFit: 'cover', 
                opacity: 0.90,
                filter: 'brightness(0.85) contrast(1.05)'
              }} 
            />
          )}

          {/* Dynamic background visual elements */}
          {!bgUrl && (
            <div style={{ position: 'absolute', top: '-15px', left: '50px', display: 'flex', fontSize: 140, fontWeight: 900, color: 'rgba(255, 255, 255, 0.04)', letterSpacing: '0.08em' }}>
              EDITORIAL
            </div>
          )}
          {!bgUrl && (
            <div style={{ position: 'absolute', bottom: '-15px', right: '50px', display: 'flex', fontSize: 140, fontWeight: 900, color: 'rgba(255, 255, 255, 0.04)', letterSpacing: '0.08em' }}>
              MAGAZINE
            </div>
          )}

          {/* Randomly placed decorative accent patterns to make every thumbnail uniquely identifiable */}
          <div style={{ position: 'absolute', top: `${glow1Y}px`, left: `${glow1X}px`, width: '350px', height: '350px', borderRadius: '175px', backgroundColor: palette.glow1, opacity: bgUrl ? 0.45 : 0.75, filter: 'blur(70px)' }} />
          <div style={{ position: 'absolute', bottom: `${glow2Y}px`, right: `${glow2X}px`, width: '400px', height: '400px', borderRadius: '200px', backgroundColor: palette.glow2, opacity: bgUrl ? 0.35 : 0.65, filter: 'blur(80px)' }} />

          {/* Transparent Glassmorphism Center Box */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: cardBg,
              width: `${cardWidth}px`,
              height: `${cardHeight}px`,
              borderRadius: `${cardRadius}px`,
              boxShadow: isDarkTheme ? '0 40px 100px rgba(0,0,0,0.6)' : '0 45px 120px rgba(0,0,0,0.22)',
              border: `${cardBorderWidth}px solid ${cardBorderColor}`,
              position: 'relative',
              padding: '50px',
            }}
          >
            {/* Top Hashtags (Sleek pill style) */}
            <div
              style={{
                display: 'flex',
                fontSize: 34,
                color: isDarkTheme ? '#F8FAFC' : palette.badgeColor,
                backgroundColor: isDarkTheme ? 'rgba(255,255,255,0.1)' : palette.badgeBg,
                padding: '12px 32px',
                borderRadius: '32px',
                fontWeight: 800,
                marginBottom: '65px',
                letterSpacing: '-0.02em',
                boxShadow: '0 4px 12px rgba(0,0,0,0.05)'
              }}
            >
              {topTags}
            </div>

            {/* Mid Huge Title */}
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                justifyContent: 'center',
                textAlign: 'center',
                wordBreak: 'keep-all',
                fontSize: midSize,
                fontWeight: 900,
                color: fontColor,
                lineHeight: 1.15,
                letterSpacing: '-0.05em',
                marginBottom: '18px',
                padding: '0 30px',
                textShadow: isDarkTheme ? '0 2px 10px rgba(0,0,0,0.4)' : 'none'
              }}
            >
              {mid}
            </div>

            {/* Bottom Accent Subtitle */}
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                justifyContent: 'center',
                textAlign: 'center',
                wordBreak: 'keep-all',
                fontSize: bottomSize,
                fontWeight: 900,
                color: isDarkTheme ? palette.glow1 : palette.bottomColor,
                lineHeight: 1.15,
                letterSpacing: '-0.05em',
                marginBottom: '80px',
                padding: '0 30px',
                textShadow: isDarkTheme ? '0 2px 10px rgba(0,0,0,0.4)' : 'none'
              }}
            >
              {bottom}
            </div>

            {/* Decorative metadata/signature at the bottom */}
            <div
              style={{
                position: 'absolute',
                bottom: '55px',
                display: 'flex',
                fontSize: 24,
                color: isDarkTheme ? 'rgba(255,255,255,0.35)' : '#94A3B8',
                fontWeight: 700,
                letterSpacing: '0.12em',
              }}
            >
              {activeSignature}
            </div>
          </div>
        </div>
      ),
      {
        width: 1080,
        height: 1080,
      }
    );
  } catch (e: unknown) {
    console.log(`${e instanceof Error ? e.message : 'Unknown Error'}`);
    return new Response(`Failed to generate the image`, {
      status: 500,
    });
  }
}
