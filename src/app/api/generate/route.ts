import { GoogleGenAI, HarmCategory, HarmBlockThreshold } from "@google/genai";
import { NextResponse } from "next/server";

const ai = new GoogleGenAI({});

export const maxDuration = 300; // Vercel Pro 서버리스 함수 타임아웃 300초로 연장

export async function POST(req: Request) {
  try {
    const { keyword, deviceType = 'desktop', category = 'general', goodUrl = "", badUrl = "" } = await req.json();

    if (!keyword) {
      return NextResponse.json({ error: "Keyword is required" }, { status: 400 });
    }

    // 1. [SEO 전략] 네이버 검색광고 API를 사용해 메인 키워드에 대한 연관 서브 키워드 4개 추출
    let subKeywordsText = "";
    try {
      const customerId = process.env.NAVER_AD_CUSTOMER_ID;
      const accessLicense = process.env.NAVER_AD_ACCESS_LICENSE;
      const secretKey = process.env.NAVER_AD_SECRET_KEY;
      
      if (customerId && accessLicense && secretKey && keyword.trim().length > 0) {
        const crypto = require('crypto');
        const timestamp = Date.now().toString();
        const method = "GET";
        const path = "/keywordstool";
        const signature = crypto.createHmac("sha256", secretKey).update(`${timestamp}.${method}.${path}`).digest("base64");
        
        // 메인 키워드 중 첫 단어로 연관검색어 조회
        const seedKw = keyword.trim().split(' ')[0];
        const apiUrl = `https://api.naver.com${path}?hintKeywords=${encodeURIComponent(seedKw)}&showDetail=1`;
        
        const res = await fetch(apiUrl, {
          method: "GET",
          headers: { 'X-Timestamp': timestamp, 'X-API-KEY': accessLicense, 'X-Customer': customerId, 'X-Signature': signature }
        });
        
        if (res.ok) {
          const data = await res.json();
          const list = data.keywordList || [];
          const filtered = list.filter((k: any) => k.relKeyword !== seedKw);
          filtered.sort((a: any, b: any) => parseInt(b.monthlyMobileQcCnt || "0") - parseInt(a.monthlyMobileQcCnt || "0"));
          
          const topSubKw = filtered.slice(0, 4).map((k: any) => k.relKeyword);
          if (topSubKw.length > 0) {
            subKeywordsText = `
[네이버 스마트블록 & 상위노출 필수 조건]
블로그 텍스트 정보량을 풍부하게 만들기 위해, 다음 4개의 <연관(서브) 키워드>를 포스팅 본문에 아주 자연스럽게 1~2회씩 무조건 섞어서 작성하세요. 
서브 키워드: ${topSubKw.join(', ')}
독자가 어색함을 느끼지 못하도록 진짜 정보인 것처럼 녹여내야 최적화 블로그 점수를 받습니다.`;
          }
        }
      }
    } catch (e) {
      console.warn("Sub-keywords fetch failed, proceeding without them", e);
    }

    const keywordGuidance = "추상적인 개념일 경우 서양인 사무실 사진이 나오지 않도록 시각적으로 직관적이고 상징적인 사물/풍경 '한글 단어'를 명사형태로 선택하세요.";

    const translatePrompt = `당신은 검색어에서 가장 핵심적이고 시각적인 이미지를 추출하는 프롬프트 엔지니어입니다. 
    사용자가 입력한 검색어에 가장 찰떡같이 어울리는 고품질 사진을 찾기 위해, 명확한 단어를 추출하세요.
    ${keywordGuidance}

    1. primary: 검색어를 가장 잘 표현하는 구체적이고 감각적인 한글 단어 1~2개
    2. fallback: primary 검색 실패 시 사용할, 검색어의 상위 카테고리에 해당하는 매우 포괄적이고 중립적인 한글 단어 1~2개
    3. englishSubject: 이 주제를 그림으로 그릴 때 메인 피사체가 될 만한 구체적인 영단어 2~3개
    
    [🔥 초강력 어그로/후킹 썸네일 카피라이팅 지침 🔥]
    4, 5, 6번 썸네일 문구는 네이버 메인 홈판에서 무조건 클릭하고 싶게 만드는 도발적인 극한의 카피라이팅이어야 합니다.
    4. thumbnailTop: 상단 해시태그용 어그로 문구 (예: #안보면손해 #수백만원절약 #1퍼센트만아는비밀) - 띄어쓰기 없이 해시태그로 3개 작성 (15자 이내)
    5. thumbnailMid: 썸네일 중앙 핵심 주제 (예: 청년미래적금, 숨은 정부지원금, 블로그 수익화) - 8자 이내 명사형태
    6. thumbnailBottom: 손실 회피 및 호기심을 극도로 자극하는 하단 문구 (예: 지금 당장 신청하세요!, 99%가 놓치는 꿀팁, 모르면 평생 후회) - 13자 이내
    
    예시:
    "블로그 썸네일 만들기" -> {"primary": "디자인", "fallback": "컴퓨터", "englishSubject": "designing on computer", "thumbnailTop": "#조회수폭발 #인플루언서비밀", "thumbnailMid": "썸네일 꿀팁", "thumbnailBottom": "안 보면 무조건 손해!"}
    "삼성전자 주가방향" -> {"primary": "주식 차트", "fallback": "금융", "englishSubject": "stock market chart rising", "thumbnailTop": "#개미투자자 #무조건필독", "thumbnailMid": "삼성전자 주가", "thumbnailBottom": "지금이 마지막 기회일까?"}

    반드시 아래 JSON 형식으로만 응답하세요. 다른 문장 부호나 설명은 절대 붙이지 마세요.
    {"primary": "...", "fallback": "...", "englishSubject": "...", "thumbnailTop": "...", "thumbnailMid": "...", "thumbnailBottom": "..."}
    
    사용자 검색어: ${keyword}`;

    let transRes;
    const transModels = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-1.5-flash"];
    let transAttempt = 0;

    while (transAttempt < transModels.length) {
      try {
        transRes = await ai.models.generateContent({
          model: transModels[transAttempt],
          contents: translatePrompt,
          config: { temperature: 0.1, responseMimeType: "application/json" },
        });
        break;
      } catch (err: any) {
        transAttempt++;
        const is503 = err?.status === 503 || err?.message?.includes('503') || err?.message?.includes('high demand') || err?.message?.includes('UNAVAILABLE');
        const is429 = err?.status === 429 || err?.message?.includes('429') || err?.message?.includes('quota') || err?.message?.includes('RESOURCE_EXHAUSTED');
        
        if ((is503 || is429) && transAttempt < transModels.length) {
          const waitMs = is429 ? 15000 : 3000;
          console.warn(`[Generate-Init] 503/429 error on ${transModels[transAttempt-1]}, falling back to ${transModels[transAttempt]} after ${waitMs}ms`);
          await new Promise(resolve => setTimeout(resolve, waitMs));
          continue;
        } else {
          throw err;
        }
      }
    }
    
    let searchParams = { primary: "사무실", fallback: "비즈니스", englishSubject: "office desktop", thumbnailTop: "오늘의 핵심 정보", thumbnailMid: keyword || "핵심 요약", thumbnailBottom: "지금 바로 확인!" };
    try {
      const jsonStr = transRes?.text?.trim() || "{}";
      const cleanedJsonStr = jsonStr.replace(/```json/g, '').replace(/```/g, '').trim();
      searchParams = JSON.parse(cleanedJsonStr);
    } catch (e) {
      console.warn("Failed to parse translate response, using fallback", e);
    }

    const PIXABAY_API_KEY = process.env.PIXABAY_API_KEY;
    let imageUrls: string[] = [];
    
    if (PIXABAY_API_KEY) {
      try {
        const fetchImages = async (query: string, limit: number) => {
          const url = `https://pixabay.com/api/?key=${PIXABAY_API_KEY}&q=${encodeURIComponent(query)}&image_type=photo&orientation=horizontal&safesearch=true&per_page=15`;
          const res = await fetch(url);
          const data = await res.json();
          if (data.hits && data.hits.length > 0) {
            return data.hits.sort(() => 0.5 - Math.random()).slice(0, limit).map((hit: any) => hit.webformatURL);
          }
          return [];
        };

        let foundImages = await fetchImages(searchParams.primary, 4);
        if (foundImages.length < 4) {
          const fallbackImages = await fetchImages(searchParams.fallback, 4 - foundImages.length);
          foundImages = [...foundImages, ...fallbackImages];
        }
        if (foundImages.length < 4) {
          const safeFallback = 'nature';
          const safeImages = await fetchImages(safeFallback, 4 - foundImages.length);
          foundImages = [...foundImages, ...safeImages];
        }
        imageUrls = foundImages;
      } catch (e) {
        console.error("Pixabay fetch error:", e);
      }
    }

    let personaGuidance = "";
    if (category === 'brandconnect') {
      personaGuidance = `
당신은 대한민국 5060 시니어들에게 극도로 자연스럽고 신뢰감을 높이는 명품 가성비 리뷰어이자 이웃 '김쌤'입니다.
이번 글은 기계적인 제품 소개가 아니라, **"실제 제가 직접 내돈내산으로 샀거나, 혹은 부모님께 직접 사드린 후 느낀 지극히 인간적이고 솔직한 1인칭 리뷰"** 형태로 작성되어야만 합니다.

[🚨 네이버 리빙/생활 홈판 1인칭 글쓰기 극대화 지침]
- 반드시 도입부에서 실제 상황("아침에 일어났는데 눈이 뻑뻑해서...", "저희 어머니가 요즘 자꾸 무릎이 쑤신다고 하셔서...")을 생생한 1인칭 시점으로 풀어가며 공감을 유도하세요.
- 격식 있고 딱딱한 백과사전식 말투는 절대 금지합니다. 진짜 블로그 이웃처럼 친근하게 대화하듯 작성하세요 ("~해보니 참 좋더라고요", "~했습니다", "~이웃님들도 아실 거예요").

[🔥 구매 전환율 300% 달성 필수 프롬프트 🔥]
1. 초강력 결핍 자극 (도입부 훅):
   - 대놓고 상품부터 들이밀면 절대 안 됩니다. 5060 독자들이 일상에서 느끼는 답답함과 고통(결핍)을 먼저 콕 짚어 내며 깊은 공감대를 형성하세요.
   - 예시: "나이 들수록 무릎 시리신 분들, 아직도 파스만 붙이고 계신가요?", "다가오는 명절, 매번 똑같은 현금이나 식용유 선물... 이제 지겨우시죠?"
   
2. 정보 70%, 추천 30% 황금비율 (스토리텔링):
   - 해당 상품이 필요한 이유에 대한 유용한 '건강상식'이나 '생활꿀팁' (정보)을 전반부에 배치하세요. 
   - 중반부부터 "그래서 제가 각종 커뮤니티 평점과 원료를 모두 깐깐하게 비교해보고 딱 고른 게 바로 이 제품입니다."라며 자연스럽게 상품명(또는 브랜드명)을 등장시킵니다.
   - 검색을 통해 파악한 상품의 장점이나 상세 정보를 나열식이 아닌 "이래서 우리한테 꼭 필요하고 돈값을 합니다"라는 확신에 찬 어조로 풀이하세요.
   - 각 문단마다 📌, 💡, ✔️ 등 다양한 이모지를 무작위하게 조합하여 넘버링 소제목을 창의적이고 다채롭게 달아주세요. (단조로운 숫자 나열 금지)

3. 직관적인 Call to Action (구매 행동 유도):
   - 본문 중간과 결론부에 시각적으로 뚜렷한 구매 행동 유도 문구(예: "이벤트 혜택이 언제 종료될지 모르니 일단 확인부터 해보세요!")를 쓴 뒤,
   - 그 다음 줄은 **아무런 기호나 괄호 없이 오직 "제휴링크" URL 전체만 단독으로 한 줄에** 작성하세요. (네이버 블로그에서 자동으로 링크 카드가 생성되도록 하기 위함입니다.)
   - 절대 링크 양옆에 괄호나 특수문자를 붙이지 마세요.

4. [🚨 법적 필수 규칙 (공정위 문구의 100% 무작위화) 🚨]
   - 글의 맨 마지막(모든 내용 끝)에 반드시 브랜드 커넥트 제휴 표시(공정위 문구)를 작성하되, **동일한 형태가 모든 글에 반복되면 유사문서 필터에 저해됩니다**. 다음 중 하나를 완전히 랜덤하게(어투와 마침표, 강조 스타일을 매번 무작위화하여) 선택하고 본인만의 신선한 말투로 <p style='font-size: 13px; color: #777; text-align: center;'><b>...</b></p> 태그 안에 작성해 주세요:
     - '해당 포스팅은 네이버 브랜드 커넥트를 통한 원고료 또는 소정의 수수료 지원으로 작성되었습니다.'
     - '브랜드 커넥트 활동의 일환으로 일정 수수료를 지급받을 수 있음을 알립니다.'
     - '본 포스팅은 브랜드 커넥트 캠페인에 참여하여 소정의 수수료를 제공받을 수 있습니다.'
     - '원활한 정보 제공을 위해 브랜드 커넥트 지원을 받아 일정액의 수수료를 받을 수 있습니다.'
     - '네이버 브랜드 커넥트를 통해 경제적 대가(수수료 등)를 제공받을 수 있는 홍보글입니다.'
`;
    } else {
      personaGuidance = `
당신은 한국 네이버 블로그 생태계를 지배하는 최정상급 '전문가 블로거'이자 친근한 동네 이웃 '김쌤'입니다.
최근 네이버 홈판(홈피드) 노출의 핵심 필터는 **"기계가 쓴 것 같은 템플릿 구성을 100% 잡아내어 누락시키는 AI 감지 및 유사구조 AI 필터"**입니다.
이 필터를 완벽히 부수기 위해 아래의 **초사실주의 1인칭 날것 스토리텔링** 및 **동적 구조 파괴(Dynamic Break) 규칙**, 그리고 **홈판 벤치마킹 스타일 가이드**를 반드시 적용하세요.

[🚨 네이버 상위 0.1% 홈판 최적화 - 초사실주의 1인칭 날것 스토리텔링]
- "안녕하세요 오늘의 유용한 정보를 전해드리는 김쌤입니다" 식의 기계적, 상투적 첫인사는 절대 금지합니다.
- 매번 도입부는 **실제 사람이 바로 겪은 날것의 극사실주의 가상 상황극(감정선, 요일, 날씨, 방문 대기 시간, 직원의 태도 등)**으로 어그로를 세게 끌며 흥미롭게 시작하세요.
  * 예시: "지난주 수요일 아침, 비가 추적추적 오는데 아침 8시 반부터 은행 문 열자마자 달려갔습니다. 제 앞에 벌써 15명이나 대기 중이더라고요...", "요즘 장보러 이마트 갈 때마다 정말 한숨만 푹푹 나오시죠? 저도 엊그제 상추 한 봉지 집었다가 가격표 보고 기겁해서 내려놨습니다..."
- 진짜 동네 이웃처럼 친근하고 부드러운 어조, 독백, 대화체, 감성적인 이웃 공감("아시다시피 이게 은근히 골치 아프잖아요?", "저만 그런 거 아니죠?")을 본문 전체에 유기적으로 녹이세요. 백과사전식 딱딱한 어조는 1%도 허용되지 않습니다.

[🚨 초치명적 주의사항: 100% 팩트 체크 및 실명 언급 (Hallucination 절대 차단) 🚨]
- 이 글은 독자들의 실제 자산 및 생활 요건과 연관되어 있으므로, 반드시 구글 검색 도구(googleSearch)의 검색 결과를 바탕으로 [실제 금리 수치, 지원 요건 대상, 신청 일정, 주관 기관 실명, 공식 신청 사이트]를 무조건 교차 팩트체크하세요. 
- 팩트가 확인되지 않은 가상의 액수나 일정은 절대 지어내지 마세요. 건강 정보인 경우 반드시 유효 약리 성분(알리신, 라이코펜, 설포라판 등)의 명칭과 과학적 원리를 쉽고 분명히 명시하십시오.
- **"OO은행, OO구청, XXX 브랜드"** 같은 억지 검열식 글자 가림막('O', 'X' 모자이크)은 네이버 DIA+ AI가 스팸/어뷰징 문서로 차단하는 가장 첫 번째 징후입니다. 눈치 보지 말고 실존하는 브랜드, 상품명, 구청명, 은행 실명을 그대로 당당하게 적어 신뢰도를 500% 확보하세요.

[🔥 네이버 AI 필터를 교란하는 '동적 구조 파괴 (Dynamic Structure Break)' 규칙 🔥]
모든 포스팅이 똑같이 획일화된 템플릿([요약] -> [본문] -> [꿀팁] -> [결론])으로 찍히면 네이버 로봇에 의해 즉시 홈판 추천에서 차단됩니다.
글을 작성할 때, **아래 3가지 스타일 중 1가지를 무작위로 스스로 엄선하여** 뼈대 구조를 완벽하게 뒤흔들어서 작성하세요. (본문 내에 스타일 이름은 적지 마세요)

* **스타일 A [스토리텔링 및 리스크 밀착형]**:
  - 전개 순서: [도입부 극사실주의 가상 스토리] -> [경험을 통해 알아낸 진짜 꿀팁과 주의사항(주의할 리스크) 먼저 방출] -> [본문 상세 정보 분석 및 핵심 조건] -> [📌 한눈에 보는 핵심 팩트체크 요약 리스트] -> [친근한 유대감 1줄 요약 결론] -> [같이 읽어보기 내부 링크 섹션]
* **스타일 B [속전속결 팩트 폭격형]**:
  - 전개 순서: [도입부 가벼운 일상 공감] -> [💡 바쁘신 분들을 위한 오늘의 정책 팩트체크 리스트 전면 배치] -> [본문 조건 및 혜택 상세 세부 분석] -> [🔑 놓치면 안 되는 상위 1% 딥 인사이트 주의사항] -> [최종 결론 요약 및 다정한 아웃트로] -> [같이 읽어보기 내부 링크 섹션]
* **스타일 C [장단점 입체 비교형]**:
  - 전개 순서: [도입부 현업의 상황/문제 직시] -> [본문 조건/상세 분석] -> [유사 상품/타 정책과의 구체적인 수치적 비교 및 장단점 분석] -> [김쌤이 알려주는 가장 실속 있는 활용 전략] -> [☘️ 최종 결론 핵심 요점 요약] -> [같이 읽어보기 내부 링크 섹션]

[🔥 네이버 상위 0.1% 홈판 벤치마킹 스타일 핵심 가이드 🔥]
1. **모바일 가독성 특화 단문(Short-line) 줄바꿈 강제:**
   - 모바일 화면 가로너비에서 줄바꿈이 지저분하게 깨지는 현상을 방지하고 리듬감을 높이기 위해, 한 줄당 평균 15~20자 내외로 호흡을 쪼개어 문장 중간에 의도적으로 자주 줄바꿈(HTML `<br>`) 처리를 하십시오.
   - 예시:
     몸이 가볍게 움직일 때는<br>
     관절의 역할을 크게 느끼지 못합니다.<br>
     하지만 무릎이 시큰하거나...
2. **인용구(Blockquote) 소제목 마크업 활성화:**
   - 네이버 블로그 스마트에디터의 세련된 인용 상자 스타일을 시뮬레이션할 수 있도록, 글의 주요 섹션 소제목 중 1~2개는 아래의 \`<blockquote>\` 태그로 래핑하여 작성하십시오:
     \`<blockquote style='border-left: 4px solid #00c73c; padding-left: 14px; margin-top: 40px; margin-bottom: 20px; font-weight: bold;'>[소제목 이름]</blockquote>\` (또는 테두리 색상을 \`#ff9900\`, \`#0066ff\` 등으로 다양화)
3. **1인칭 주관적 의견 및 통찰 15% 비중 의무화:**
   - 사실 나열만 하면 정보 공장 글로 감점됩니다. 글 중간중간에 "제 생각은 조금 다릅니다", "제가 직접 겪어보니 이건 별로더군요", "왜 무주택자만 힘들어지는 구조인지 그 이면의 진짜 이유는..." 처럼 **자신의 뚜렷한 철학, 비평 및 주관적 생각**을 반드시 15% 이상 분량으로 서술해 주십시오.
4. **기호 없는 순수 줄바꿈 리스트 체계:**
   - AI 특유의 글머리 기호(\`*\`, \`-\`, \`•\`, \`1.\`, \`2.\`)를 본문 내 리스트 작성 시 **절대 사용하지 마십시오.** 
   - 대신 깔끔하게 한 줄씩 줄바꿈하고 볼드 처리를 하는 순수 텍스트 리스트 형태를 사용하십시오.
     * 예시:
       <b>우리카드 앱 또는 홈페이지 접속</b><br>
       <b>메인 화면에서 민생회복 신청 클릭</b><br>
       <b>본인 인증 완료</b>
5. **[필수] "같이 읽어보기" (내부 추천 글) 링크 블록 삽입:**
   - 글의 맨 마지막 결론부 바로 위(또는 아웃트로 바로 직전)에, 연관 포스팅 추천을 통해 방문자를 붙잡아두는(체류시간 극대화) \`같이 읽어보기\` 섹션을 템플릿화하여 아래 HTML 마크업으로 무조건 삽입하십시오:
     \`<br><blockquote style='border-left: 4px solid #ff9900; padding-left: 12px; font-size: 14px; color: #555;'><b>같이 읽어보기 좋은 추천 글</b><br><a href='#' style='color: #0066ff; text-decoration: none;'>[본문 키워드와 연관된 가상의 추천 포스팅 제목 1]</a><br><a href='#' style='color: #0066ff; text-decoration: none;'>[본문 키워드와 연관된 가상의 추천 포스팅 제목 2]</a></blockquote>\`

`;
    }

    const currentYear = new Date().getFullYear();

    let visualGuidance = "";
    if (deviceType === 'mobile') {
        visualGuidance = `
3. 시각적 요소 및 썸네일 구조 (모바일 앱 전용 - 매우 중요!!):
   - 블로그 원본의 필수 레이아웃은 무조건 '대제목 -> 가벼운 인사말 -> [THUMBNAIL] -> 본격적인 본문 내용' 순서여야 합니다. 
   - 따라서 인사말이 끝나는 서론 직후에 반드시 [THUMBNAIL] 이라는 예약어를 단 1번 작성하세요.
   - 네이버 블로그 앱은 외부 사진 복사를 차단하므로 보조 사진 배치 명령어([IMAGE_1] 등)는 생략합니다.

4. 모바일 화면 최적화: 극강의 가독성 및 띄어쓰기 원칙 (가장 기본 HTML 태그와 인라인 컬러만 허용):
   - 네이버 블로그 앱은 복잡한 구조(표, 박스 등)를 부숴버리지만 **단순 글자색과 줄바꿈은 유지**합니다.
   - 따라서 전체 본문을 **오직 <p>, <br>, <b>, <span style="color:색상">** 태그만으로 작성하세요. 
   - <h2>, <h3>, <blockquote>, <table>, <ul>, <li> 등은 복사 시 박살나므로 일절 금지! **마크다운 기호(*, #, - 등)**도 앱에서 깨지므로 **절대 금지**합니다.
   
   - **소제목 구분 및 간격:** 
     소제목은 위/아래로 딱 한 칸 줄바꿈(<br>)만 허용합니다. 빈 줄이 뻥 뚫려 보이는 두 줄 띄어쓰기(<br><br> 또는 <p><br></p>)는 절대 금지합니다.
     올바른 형태 예시:
     <br>
     <p><b>📌 [1. 소제목 이름]</b></p>
     <br>
     <p>내용을 이어서 작성합니다...</p>
   
   - **자연스러운 여백 및 1줄 띄어쓰기 (두 줄 띄어쓰기 절대 금지):** 
     문단과 문단 사이, 또는 문장 사이에 빈 줄이 아예 없도록 **딱 한 번만 줄바꿈(<br>)** 하세요. 
     스마트폰 화면에서 텅 비어 보이지 않게, <br><br>나 <p><br></p> 같은 '두 줄 띄어쓰기'는 절대 피하고 촘촘하게 작성하세요.
   
   - **핵심 포인트 색상 강조:** 가독성을 끌어올리기 위해, 제품명이나 장점 등 중요 포인트에는 <span style="color: #00c73c;">...</span> 나 다른 눈에 띄는 색상을 무조건 적극적으로 사용해서 화사하게 꾸며주세요.`;
    } else {
        visualGuidance = `
3. 시각적 요소 및 썸네일 구조 (매우 중요!!):
   - 블로그 원본의 필수 레이아웃은 무조건 '대제목 -> 가벼운 인사말 -> [THUMBNAIL] -> 본격적인 본문 내용' 순서여야 합니다. 
   - 따라서 인사말이 끝나는 서론 직후에 반드시 [THUMBNAIL] 이라는 예약어를 단 1번 작성하세요.
   - 본문 중간중간 글의 문맥과 흐름이 자연스럽게 전환되는 곳에 사진을 최대 3장까지 적절히 거리를 두고 배치하기 위해 [IMAGE_1], [IMAGE_2], [IMAGE_3] 예약어를 삽입하세요.
   - 절대 <img> 태그 등을 임의로 사용하지 말고 오직 위 텍스트 예약어만 넣어야 합니다.

4. 가독성을 극대화하는 세련된 구조 (마크다운 절대 금지, 100% HTML 태그 작성):
   - **문단 길이 및 줄바꿈:** 2~3문장마다 반드시 문단을 나누고, 본문의 모든 일반 텍스트는 <p style='font-size: 16px; line-height: 1.8; margin-bottom: 26px; color: #333; letter-spacing: -0.5px;'>...</p> 태그로 감싸서 아주 읽기 편하게 만드세요.
   - **표(Table) 작성 규칙:** 마크다운 문법( |---| )은 화면이 깨지므로 절대 쓰지 마세요!! 표가 필요할 때는 반드시 HTML <table> <tr> <th> <td> 태그를 사용하고, style 속성으로 테두리(border: 1px solid #ddd; border-collapse: collapse; padding: 12px; text-align: left;)를 명시하세요. <th>에는 배경색(background-color: #f8f9fa;)도 넣으세요.
   - **소제목 계층화 (필수):** 대주제와 소주제는 글의 흐름이 자연스럽게 이어지도록 직관적으로 작성하고(번호 포함 가능), 아래의 세련된 인라인 스타일을 사용하되, **테두리(border)나 포인트 강조 색상은 주제 분위기에 맞춰 다양하게 변경하여 단조로운 패턴을 회피하세요.** (예: IT/금융은 \`#0066ff\` 또는 \`#00c73c\`, 일상/리뷰는 \`#ff9900\` 등 자유롭게 선택)
     대주제 예시: <h2 style='font-size: 24px; font-weight: 800; color: #111; margin-top: 70px; margin-bottom: 25px; padding-bottom: 10px; border-bottom: 2px solid #111;'>1. 대주제 타이틀</h2>
     소주제 예시: <h3 style='font-size: 20px; font-weight: 700; color: #333; margin-top: 60px; margin-bottom: 20px; padding-left: 14px; border-left: 4px solid #00c73c;'>1.1. 소주제 타이틀</h3> (보더 칼라 \`#00c73c\` 부분을 \`#0055ff\` 등 다양한 색상으로 자유롭게 변경 가능)
   - **리스트(List) 작성 규칙:** <ul> 태그에는 위아래 숨통을 트기 위해 반드시 <ul style='margin-top: 15px; margin-bottom: 35px; padding-left: 22px;'> 를 적용하세요. 그 안의 <li> 태그는 본문과 글씨 크기가 다르게 튀지 않도록 <li style='font-size: 16px; letter-spacing: -0.5px; margin-bottom: 15px; line-height: 1.8; color: #333;'> 처럼 폰트 사이즈와 여백을 명시하고, 핵심 단어는 <strong style='color: #00c73c;'> 태그로 강조하세요.
   - **중요**: HTML 태그에 속성을 넣을 때는 큰따옴표(") 대신 **반드시 홑따옴표(')**를 사용하세요.`;
    }

    const realTimeSeoGuidance = `
[네이버 상위노출 경쟁 분석 및 벤치마킹 (성공 패턴 지속 학습)]
- 구글 검색 도구(Tools)를 활용하여 목표 키워드('${keyword}')로 최근 트래픽이 폭발한 "잘 된 상위노출 블로그 글"을 실시간으로 검색하여 그들의 글쓰기 패턴을 계속 학습하세요.
- 상단 랭커들이 독자 체류 시간을 늘리기 위해 사용한 소제목 배치 구조, 도입부 후킹(Hooking) 방식, 필수 꿀팁(장단점, 혜택, 대기시간 등)을 정밀 벤치마킹하고 그 성공 공식을 체화하여 원고에 녹여내세요.
- 독자가 이 글 하나만 읽어도 블로그 5개를 찾아본 것과 같은 압도적인 가치를 얻도록 작성하되, 복사/붙여넣기는 철저히 배제합니다.
${subKeywordsText}

[🚨 필수 적용: 메가 키워드 타겟팅 금지 및 카피라이팅 지침 🚨]
1. 제목([TITLE]) 생성 시 절대로 포괄적이고 뻔한 "~~~ 총정리!", "~~~ 초보자 필독!" 혹은 아무 의미 없는 이모티콘 떡칠("🚨충격!🚨") 같은 인공지능이 쓴 티가 나는 제목은 피하세요. 또한, 제목([TITLE])에는 절대로 HTML 태그(예: <span>, <b> 등)를 포함하지 말고 순수 텍스트로만 작성해 주세요. (경험상 조회수 망의 원흉입니다)
2. 만약 주어진 키워드가 광범위하다면(예: '전국 새마을금고 특판', '대한민국 반값여행'), **절대 지역/대상을 광범위하게 쓰지 마시고 핀셋으로 집어내듯 극도로 구체적인 좁은 단위(예: 특정 지점명, 정확한 퍼센트, 구체적인 날짜)로 세분화**해야 조회수가 폭발합니다.

[🔥 어그로 폭발: 실제 조회수 대박 패턴을 적용한 제목 카피라이팅 지침 🔥]
3. 제목([TITLE]) 생성 시 사람들의 '손실 회피 심리'와 '호기심'을 자극하되, **반드시 구체적인 수치(%, 만원, 시간)와 특정 대상**을 조합하세요!
   - 👎 [학습된 실패 사례 (조회수 10 이하, 쓰지마세요!)]: 
     "4월 금리 3.7% 실화? 나만 모르는 전국 새마을금고 신협 비대면 특판..." (너무 광범위함)
     "모르면 20만원 손해! 4월 시작 대한민국 반값여행..." (구체적인 매력 포인트 부족)
     "🚨충격!🚨 2026년 청년주택드림청약통장..." (진부한 클릭베이트 이모티콘)
   
   - 👍 [지향해야 하는 압도적 성공 사례 (방문자 폭발 패턴!)]: 
     "아직도 3%대 예금 찾으세요? 99%가 모르는 새마을금고 3.9% 특판, 5분만 투자하면 이자가 달라집니다" (상대적 결핍 자극 + 구체적 수치 + 짧은 노력 강조)
     "일자리 채움 청년지원금 200만원? 2026년엔 최대 720만원으로 껑충! (신청 안하면 나만 손해)" (비교 수치 명확 제시)
     "성남사랑상품권 4월 10% 할인, 6일 오픈런 안 하면 5만원 그냥 버리는 겁니다" (특정 지역/날짜 + 구체적인 금전 손실 액수 명시)

4. 본문 도입부에서도 제목의 기대감을 받아주어, "이 글을 끝까지 안 읽으면 나만 바보가 될 것 같은 불안감"을 조성하며 몰입도를 300% 높이세요. 독자의 결핍(Pain Point)과 생생한 경험담(내돈내산 같은 톤)이 글에 강력하게 묻어나야 합니다.

[🚨 엄격한 자기검열 및 팩트체크 (거짓정보/가상명칭/블라인드 원천 차단) 🚨]
5. (가장 중요) 글을 쓰기 전에 **무조건 구글 검색 도구(Google Search Tool)**를 실행하여 해당 키워드나 제품/상품/정책이 **"현재 실존하는 고유명사인지"**, **"이미 마감되지 않았는지"**부터 정확히 팩트체크 하세요.
   - 팩트가 확인되지 않은 가상의 상품, 가상의 혜택 수치(%, 금액 수준)는 절대 지어내지 마세요(Hallucination 금지). 거짓 정보를 작성하면 블로그가 신고 당합니다.
   - 특히 정보가 조금이라도 부족하다고 해서 임의로 "OOO 브랜드", "XXX 제품", "***" 식의 알파벳/특수문자 모자이크(블라인드) 처리를 절대 하지 마세요. 독자를 기만하는 최악의 행동입니다. 찾을 수 없다면 검색된 내용 중에서 실존하는 다른 대안 상품명을 당당히 적으세요.
6. **"OO신협", "○○은행", "OOO 대용량 세제", "XXX 브랜드"**와 같이 'O', 'X' 등을 활용한 블라인드(가림막) 처리는 분야(금융, IT, 건강, 일상 제품 등)를 막론하고 **어떤 경우에도 100% 절대 금지**합니다.
   - 기사나 공식 쇼핑몰에서 교차 검증된 정확한 팩트(실존하는 지점명, 실제 브랜드명, 구체적인 제품명, 정확한 가격/이율)만 기재하세요.
   - 특정 브랜드나 상표를 검열 없이 그대로 노출하는 것이 이 블로그의 매력이자 신뢰의 핵심입니다. 눈치 보지 말고 실명을 언급하세요.

7. [🚨 치명적 발자국 회피: 면책 조항(Disclaimer)의 100% 무작위 동적 생성 🚨]
   - 글의 맨 마지막(결론 및 해시태그 바로 위)에는 법적/운영적 책임 방지를 위해 반드시 정보 공유 목적의 **면책 조항**을 작성해야 합니다.
   - **주의: 모든 글에 똑같은 단어나 템플릿의 면책 조항이 반복 삽입되면 네이버 유사문서 알고리즘에 의해 블로그 전체가 즉시 검색 차단(통누락)됩니다!**
   - 따라서 아래의 핵심 의도(정보 전달 목적, 정책 및 기준 변동 가능성, 최종 확인 권장)를 포함하되, **매번 완전히 다른 문장 구조, 어휘, 배치 순서로 새로운 2~3문장의 면책 조항을 자연스럽게 직접 지어내어** \`<p style='font-size: 13px; color: #888; text-align: center; line-height: 1.6;'><b>🚨 [팩트체크 및 면책고지]</b><br>...</p>\` 태그 형식으로 생성하십시오.
   - 창작 예시:
     - "본 포스팅은 언론 보도와 공식 보도자료를 기반으로 독자들의 이해를 돕기 위해 작성되었습니다. 시점과 주관 기관의 세부 정책 변화에 따라 실제 혜택 요건이 상이할 수 있으므로, 최종 신청 전에 필히 관할 처의 공식 공고를 교차 검증하시기 바랍니다."
     - "신뢰할 수 있는 공시 자료를 취합하여 정리했으나, 정책 변경이나 예산 한도 소진 등으로 세부 정보가 예고 없이 변경될 수 있습니다. 정확한 가입 조건은 반드시 주관사 공식 채널을 통해 마지막으로 확인해 주세요."
     - "이 글은 유용한 정보 전달을 목적으로 쓰인 개인 의견입니다. 구체적인 지급일이나 심사 기준 등은 변동 사항이 잦으므로, 모든 신청 및 계약 진행 전에 공식 사이트의 최신 안내를 반드시 검토하시는 것을 권장합니다."

8. **(매우 중요)** 구글 검색을 통해 얻은 원본 검색 데이터(JSON, 파이썬 딕셔너리 텍스트, 예: {'title': ...})를 블로그 본문에 절대 그대로 노출하거나 출력하지 마세요. 검색 결과는 오직 속으로 참고하여 사실 관계를 파악하는 데에만 사용하고, 최종 [CONTENT] 안에는 반드시 자연스러운 인간의 언어로 다듬어진 결과물만 작성해야 합니다.
`;

    let feedbackLearningGuidance = "";
    if (goodUrl || badUrl) {
      feedbackLearningGuidance += `
[개인화된 AI 강화 학습 지침 (매우 중요)]
사용자가 자신의 과거 블로그 포스팅 결과를 바탕으로 다음의 피드백 링크를 제공했습니다. 구글 검색 툴을 이용해 반드시 다음 URL들의 본문 내용을 파악하고 아래 지시를 100% 따르세요.
`;
      if (goodUrl) {
        feedbackLearningGuidance += `- 👍 [성공 사례 벤치마킹 필수 대상]: ${goodUrl}\n  이 글은 트래픽이 터진 '대박' 포스팅입니다. 이 글의 장점(가독성 퀄리티, 정보 배치 순서, 도입부의 공감 요소, 말투 등)을 철저히 분석하고, 이번 포스팅을 작성할 때 이 성공 패턴의 분위기와 전개 방식을 완벽하게 흡수하여 작성하세요.\n`;
      }
      if (badUrl) {
        feedbackLearningGuidance += `- 👎 [실패 사례 회피 필수 대상]: ${badUrl}\n  이 글은 노출되지 않은 '폭망' 포스팅입니다. 이 글의 단점(지루한 서론, 뻔한 정보 나열, 부족한 가독성 등)을 철저히 분석하고, 이번 포스팅에서는 절대로 이 글과 같은 스타일이나 정보 전개 방식을 답습하지 마세요.\n`;
      }
    }

    const prompt = `
${personaGuidance}
${realTimeSeoGuidance}
${feedbackLearningGuidance}

사용자가 검색한 아래 키워드를 바탕으로 최상급 품질의 네이버 블로그 포스팅을 작성하세요.

현재 연도(참고용): ${currentYear}년
목표 검색어/키워드: ${keyword}

${visualGuidance}

[출력 형식 제한]
반드시 아래의 특수 구분자를 사용하여 제목과 본문을 나누어 작성하세요. JSON 형식은 절대 사용하지 마세요.
[TITLE]
(생성된 블로그 제목을 순수 텍스트로 1줄로 작성)
[/TITLE]
[CONTENT]
${deviceType === 'mobile' ? "(생성된 블로그 본문을 <p>, <br>, <b> 태그만을 엄격하게 사용한 형태로 작성)" : "(생성된 블로그 본문을 화려한 HTML 태그 및 CSS가 포함된 텍스트로 작성)"}
[/CONTENT]
`;

    const commonConfig = {
      systemInstruction: "당신은 블로그 포스팅 작가를 돕는 보조 AI입니다. 구글 검색 결과를 통해 팩트를 체크하되, 절대로 검색 결과의 원본 데이터(JSON이나 파이썬 딕셔너리 구조, {'title': ...})를 사용자에게 그대로 노출하거나 본문에 출력하지 마세요. 오직 깔끔하게 다듬어진 블로그 [CONTENT] 텍스트만 출력해야 합니다.",
      temperature: 0.7,
      maxOutputTokens: 8192,
      tools: [{ googleSearch: {} }],
      // @ts-ignore
      safetySettings: [
        { category: HarmCategory.HARM_CATEGORY_HARASSMENT, threshold: HarmBlockThreshold.BLOCK_NONE },
        { category: HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold: HarmBlockThreshold.BLOCK_NONE },
        { category: HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold: HarmBlockThreshold.BLOCK_NONE },
        { category: HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold: HarmBlockThreshold.BLOCK_NONE }
      ]
    };

    let streamRes: any;
    const generateModels = [
      "gemini-2.5-flash", 
      "gemini-2.5-flash-lite",
      "gemini-1.5-flash"
    ];
    let genAttempt = 0;

    while (genAttempt < generateModels.length) {
      try {
        const currentModel = generateModels[genAttempt];
        const currentConfig = genAttempt === generateModels.length - 1 
          ? { ...commonConfig, tools: undefined } 
          : commonConfig;

        streamRes = await ai.models.generateContentStream({
          model: currentModel,
          contents: prompt,
          config: currentConfig,
        });
        break;
      } catch (generateErr: any) {
        genAttempt++;
        const is503 = generateErr?.status === 503 || generateErr.message?.includes('503') || generateErr.message?.includes('high demand') || generateErr.message?.includes('UNAVAILABLE');
        const is429 = generateErr?.status === 429 || generateErr.message?.includes('429') || generateErr.message?.includes('quota') || generateErr.message?.includes('RESOURCE_EXHAUSTED');
        
        if ((is503 || is429) && genAttempt < generateModels.length) {
          const waitMs = is429 ? 15000 : 3000;
          console.warn(`[Generate] 503/429 on ${generateModels[genAttempt-1]}. Waiting ${waitMs}ms before falling back to ${generateModels[genAttempt]}...`);
          await new Promise(resolve => setTimeout(resolve, waitMs));
          continue; 
        } else {
          throw generateErr;
        }
      }
    }

    const host = req.headers.get('host') || 'localhost:3000';
    const protocol = req.headers.get('x-forwarded-proto') || 'http';
    const baseUrl = `${protocol}://${host}`;

    // 2. [비주얼 강화] Pixabay 실물 사진을 배경으로 연동하여 썸네일 생성
    let thumbnailHtml = "";
    try {
      const topParams = encodeURIComponent(searchParams.thumbnailTop || '주목할 만한 정보');
      const midParams = encodeURIComponent(searchParams.thumbnailMid || keyword || '핵심 요약');
      const bottomParams = encodeURIComponent(searchParams.thumbnailBottom || '5분만에 알아보기');
      
      const styleParam = category ? `&style=${category}` : "";
      // Pixabay 첫 번째 이미지를 bg 파라미터로 추가 전달
      const bgParam = imageUrls.length > 0 ? `&bg=${encodeURIComponent(imageUrls[0])}` : "";
      const ogUrl = `${baseUrl}/api/og?top=${topParams}&mid=${midParams}&bottom=${bottomParams}${styleParam}${bgParam}&ext=.png`;

      thumbnailHtml = `<div style="text-align: center; margin-bottom: 24px;">
        <img src="${ogUrl}" alt="대표 썸네일" style="max-width: 100%; height: auto; border-radius: 12px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -2px rgba(0,0,0,0.05);" />
      </div>`;
    } catch (imgError) {
      console.error("OG Thumbnail Generation Failed:", imgError);
    }

    let processedImages: string[] = [];
    if (deviceType === 'desktop') {
      processedImages = imageUrls.slice(1).map(url => `${baseUrl}/api/proxy?url=${encodeURIComponent(url)}`);
    }

    const readable = new ReadableStream({
      async start(controller) {
        const encoder = new TextEncoder();
        try {
          const metaMsg = JSON.stringify({ type: 'meta', thumbnailHtml, images: processedImages });
          controller.enqueue(encoder.encode(`data: ${metaMsg}\n\n`));

          // 3. 실시간으로 청크 스트림을 수집하여 포스트 프로세싱
          let fullText = "";
          for await (const chunk of streamRes) {
            if (chunk.text) {
              fullText += chunk.text;
            }
          }

          // 무작위 인라인 스타일 셔플러를 제거하여 네이버 스마트에디터 ONE의 신뢰성 검증 통과 (Clean HTML 유지)
          let processedText = fullText;

          // 자연스러운 스트리밍 타이핑 효과 시뮬레이션
          const chunkSize = 25;
          for (let i = 0; i < processedText.length; i += chunkSize) {
            const chunk = processedText.substring(i, i + chunkSize);
            const textMsg = JSON.stringify({ type: 'text', text: chunk });
            controller.enqueue(encoder.encode(`data: ${textMsg}\n\n`));
            await new Promise(resolve => setTimeout(resolve, 3)); // 3ms 미세 딜레이
          }

          controller.close();
        } catch (e) {
          console.error("Stream Error:", e);
          controller.error(e);
        }
      }
    });

    return new Response(readable, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      }
    });
  } catch (error: unknown) {
    console.error("Gemini API Error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to generate blog post" },
      { status: 500 }
    );
  }
}
