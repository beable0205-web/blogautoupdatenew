import { NextResponse } from "next/server";
import crypto from "crypto";

export async function POST(req: Request) {
  try {
    const { keyword } = await req.json();

    if (!keyword || keyword.trim() === '') {
      return NextResponse.json({ error: "Keyword is required" }, { status: 400 });
    }

    const customerId = process.env.NAVER_AD_CUSTOMER_ID;
    const accessLicense = process.env.NAVER_AD_ACCESS_LICENSE;
    const secretKey = process.env.NAVER_AD_SECRET_KEY;

    if (!customerId || !accessLicense || !secretKey) {
      return NextResponse.json(
        { error: "네이버 검색광고 API 키가 설정되지 않았습니다. .env.local 파일에 NAVER_AD_CUSTOMER_ID, NAVER_AD_ACCESS_LICENSE, NAVER_AD_SECRET_KEY를 추가해주세요." },
        { status: 500 }
      );
    }

    const timestamp = Date.now().toString();
    const method = "GET";
    const path = "/keywordstool";

    const message = `${timestamp}.${method}.${path}`;
    const signature = crypto
      .createHmac("sha256", secretKey)
      .update(message)
      .digest("base64");

    // hintKeywords accepts up to 5 comma-separated keywords, but we just pass the first word of user input to get broader results
    const seedKeyword = keyword.trim().split(' ')[0];
    const apiUrl = `https://api.naver.com${path}?hintKeywords=${encodeURIComponent(seedKeyword)}&showDetail=1`;

    const response = await fetch(apiUrl, {
      method: "GET",
      headers: {
        "X-Timestamp": timestamp,
        "X-API-KEY": accessLicense,
        "X-Customer": customerId,
        "X-Signature": signature,
      },
      cache: "no-store",
    });

    if (!response.ok) {
      const errText = await response.text();
      console.error("Naver Ad API Error:", response.status, errText);
      return NextResponse.json(
        { error: `네이버 검색광고 API 호출 실패: ${response.status}`, details: errText },
        { status: response.status }
      );
    }

    const data = await response.json();
    
    const keywordList = data.keywordList || [];
    
    // Parse numeric counts (Naver sometimes returns "< 10" for low volume)
    const parseCnt = (val: any) => {
        if (typeof val === 'string' && val.includes('<')) return 5;
        return parseInt(val) || 0;
    };

    // 1. [초고단가 CPC 금융/비즈니스 단어 사전] - 애드포스트 클릭 단가가 수천~수만 원을 호가하는 마법의 키워드들
    const HIGH_CPC_WORDS = [
      '대출', '환급', '지원금', '청약', '금리', '세금', '연금', '부업', '창업', 
      '비트코인', '가상자산', '절세', '건보료', '카드', '보험', '특판', '예금', 
      '적금', '소상공인', '정부지원', '보조금', '수수료', '주식', '증권', '펀드', '수익'
    ];

    const mappedKeywords = keywordList.map((k: any) => {
        const pc = parseCnt(k.monthlyPcQcCnt);
        const mobile = parseCnt(k.monthlyMobileQcCnt);
        const total = pc + mobile;
        const kw = k.relKeyword || "";
        
        // 고단가 애드포스트 키워드 점수화 (포함될수록 수익 가중치 폭등)
        let cpcScore = 0;
        HIGH_CPC_WORDS.forEach(word => {
          if (kw.includes(word)) cpcScore += 10000;
        });

        return {
            keyword: kw,
            monthlyTotalCnt: total,
            pcCnt: pc,
            mobileCnt: mobile,
            cpcScore: cpcScore
        };
    });

    // 2. [황금 틈새(롱테일) 필터링] 
    // - 조건 1: 검색량 200 ~ 20,000 (최상위 인플루언서와 무모한 경쟁을 피하는 빈집)
    // - 조건 2: 4글자 이상 (구체적 검색 의도가 반영된 롱테일)
    const strictNicheKeywords = mappedKeywords.filter((k: any) => {
      const isNicheTraffic = k.monthlyTotalCnt >= 200 && k.monthlyTotalCnt <= 20000;
      const isLongTail = k.keyword.length >= 4;
      return isNicheTraffic && isLongTail;
    });

    let targetArray = strictNicheKeywords;

    if (targetArray.length < 12) {
       targetArray = mappedKeywords.filter((k: any) => 
         k.monthlyTotalCnt >= 150 && k.monthlyTotalCnt <= 35000 && k.keyword.length >= 3
       );
    }

    if (targetArray.length < 12) {
       targetArray = mappedKeywords;
    }

    // 3. [초고수익 정렬 알고리즘]
    // - 애드포스트 단가가 높은 키워드(cpcScore가 높은 것)를 무조건 상단 1순위로 배치
    // - 동점(cpcScore가 같음)일 경우 랜덤성을 주어 매번 다양한 노다지 키워드가 보이도록 셔플
    const sortedByCpcAndShuffled = targetArray.sort((a: any, b: any) => {
      if (b.cpcScore !== a.cpcScore) {
        return b.cpcScore - a.cpcScore; // 고단가 우선 정렬
      }
      return 0.5 - Math.random(); // 동점자는 무작위 셔플
    });

    // Return top 12 high-CPC golden niche keywords
    return NextResponse.json({ recommendations: sortedByCpcAndShuffled.slice(0, 12) });
  } catch (error: any) {
    console.error("Recommend Keywords API Error:", error);
    return NextResponse.json(
      { error: error?.message || "연관 키워드를 가져오는데 실패했습니다." },
      { status: 500 }
    );
  }
}
