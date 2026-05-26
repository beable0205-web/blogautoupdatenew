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
            flexDirection: 'column',
            alignItems: 'flex-start',
            justifyContent: 'flex-end',
            backgroundImage: bgUrl ? 'none' : bgGradient,
            backgroundColor: bgUrl ? '#111' : 'transparent',
            fontFamily: 'sans-serif',
            position: 'relative',
            overflow: 'hidden',
            padding: '80px',
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
                opacity: 0.95,
                filter: 'brightness(0.70) contrast(1.1)'
              }} 
            />
          )}

          {/* 감성 뷰파인더 오버레이 (고화질 카메라 브래킷 & 십자선) */}
          <div style={{ position: 'absolute', top: '40px', left: '40px', width: '30px', height: '30px', borderTop: '4px solid rgba(255,255,255,0.7)', borderLeft: '4px solid rgba(255,255,255,0.7)' }} />
          <div style={{ position: 'absolute', top: '40px', right: '40px', width: '30px', height: '30px', borderTop: '4px solid rgba(255,255,255,0.7)', borderRight: '4px solid rgba(255,255,255,0.7)' }} />
          <div style={{ position: 'absolute', bottom: '40px', left: '40px', width: '30px', height: '30px', borderBottom: '4px solid rgba(255,255,255,0.7)', borderLeft: '4px solid rgba(255,255,255,0.7)' }} />
          <div style={{ position: 'absolute', bottom: '40px', right: '40px', width: '30px', height: '30px', borderBottom: '4px solid rgba(255,255,255,0.7)', borderRight: '4px solid rgba(255,255,255,0.7)' }} />
          
          {/* 중앙 촬영 크로스헤어 데코 */}
          <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ width: '20px', height: '2px', backgroundColor: 'rgba(255,255,255,0.2)' }} />
            <div style={{ width: '2px', height: '20px', backgroundColor: 'rgba(255,255,255,0.2)', position: 'absolute' }} />
          </div>

          {/* 세련된 다중 색상 백그라운드 그라데이션 글로우 마스크 (배경이 없을 때만 데코) */}
          {!bgUrl && (
            <>
              <div style={{ position: 'absolute', top: `${glow1Y}px`, left: `${glow1X}px`, width: '500px', height: '500px', borderRadius: '250px', backgroundColor: palette.glow1, opacity: 0.8, filter: 'blur(100px)' }} />
              <div style={{ position: 'absolute', bottom: `${glow2Y}px`, right: `${glow2X}px`, width: '550px', height: '550px', borderRadius: '275px', backgroundColor: palette.glow2, opacity: 0.7, filter: 'blur(110px)' }} />
            </>
          )}

          {/* 가독성을 높이기 위한 극적인 하단 그라데이션 암전 패널 */}
          <div 
            style={{
              position: 'absolute',
              bottom: 0,
              left: 0,
              width: '100%',
              height: '65%',
              backgroundImage: 'linear-gradient(to top, rgba(0,0,0,0.92) 0%, rgba(0,0,0,0.65) 45%, rgba(0,0,0,0.2) 80%, transparent 100%)',
              pointerEvents: 'none',
            }}
          />

          {/* 좌측 상단 - 힙한 라이브 메거진 에디토리얼 시그니처 표식 */}
          <div
            style={{
              position: 'absolute',
              top: '65px',
              left: '80px',
              display: 'flex',
              alignItems: 'center',
              gap: '12px'
            }}
          >
            <div style={{ width: '10px', height: '28px', backgroundColor: '#CCFF00', borderRadius: '2px' }} />
            <span style={{ fontSize: 24, fontWeight: 900, color: '#CCFF00', letterSpacing: '0.15em' }}>
              {activeSignature}
            </span>
          </div>

          {/* 메인 텍스트 컨테이너 - 100% 좌측 하단 정렬 매거진 스타일 */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'flex-start',
              justifyContent: 'flex-end',
              width: '100%',
              zIndex: 10,
              position: 'relative'
            }}
          >
            {/* Top Hashtags - 쨍한 라임 형광 필약 배지 */}
            <div
              style={{
                display: 'flex',
                fontSize: 32,
                color: '#111111',
                backgroundColor: '#CCFF00',
                padding: '8px 24px',
                borderRadius: '6px',
                fontWeight: 900,
                marginBottom: '40px',
                letterSpacing: '-0.01em',
                boxShadow: '0 8px 20px rgba(204,255,0,0.25)'
              }}
            >
              {topTags}
            </div>

            {/* Mid Huge Title - 잡지 메인 커버 텍스트 */}
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                justifyContent: 'flex-start',
                textAlign: 'left',
                wordBreak: 'keep-all',
                fontSize: midSize + 15,
                fontWeight: 900,
                color: '#FFFFFF',
                lineHeight: 1.12,
                letterSpacing: '-0.04em',
                marginBottom: '20px',
                maxWidth: '920px',
                textShadow: '0 4px 15px rgba(0,0,0,0.8)'
              }}
            >
              {mid}
            </div>

            {/* Bottom Accent Subtitle - 시선을 머물게 하는 형광 옐로우 강조 구절 */}
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                justifyContent: 'flex-start',
                textAlign: 'left',
                wordBreak: 'keep-all',
                fontSize: bottomSize + 10,
                fontWeight: 900,
                color: '#FACC15',
                lineHeight: 1.12,
                letterSpacing: '-0.04em',
                marginBottom: '15px',
                maxWidth: '920px',
                textShadow: '0 4px 15px rgba(0,0,0,0.8)'
              }}
            >
              {bottom}
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
