import { GoogleGenAI } from "@google/genai";
import crypto from "crypto";
import dotenv from "dotenv";
dotenv.config({ path: ".env" });
dotenv.config({ path: ".env.local" });

async function run() {
  console.log("Testing generation...");
  try {
    const ai = new GoogleGenAI({});
    const prompt = `당신은 대한민국 상위 0.1% 네이버 블로그 트래픽 마스터(SEO 전문가)입니다.
현재 구글 검색(Google Search)을 실시간으로 적극 활용하여, 오늘 날짜 기준으로 네이버 블로그 생태계에서 매우 뜨거운 관심을 받고 있지만 아직 초대형 인플루언서들이 꽉 잡고 있지 않은 **'틈새(니치) 황금 롱테일 키워드' 딱 5개**를 발굴해내세요.

[키워드 발굴 절대 원칙]
1. (절대 금지): '비트코인', '장외주식', '맛집', '여자트로트가수' 같은 뻔하고 넓은 메가 키워드.
2. (강력 권장): 구체적인 리뷰, 혜택, 신청방법, 후기, 비교 등이 포함된 5글자 이상의 롱테일 키워드. (예: "애플페이 교통카드 등록 단점")
3. 실시간으로 사람들이 가장 불안해하거나 궁금해하는 최근 이슈 위주로 발굴하세요.

반드시 아래 JSON 형식으로만 응답하세요. 백틱(\`\`\`)이나 다른 설명은 절대 추가하지 마세요.
{
  "trends": [
    {
      "keyword": "발굴한 롱테일 키워드",
      "reason": "왜 이 키워드가 지금 트래픽을 당길 수 있는 황금 빈집인지에 대한 아주 짧은 분석 (1~2문장)"
    }
  ]
}
`;
    console.log("Calling GoogleGenAI...");
    const response = await ai.models.generateContent({
      model: "gemini-2.5-flash",
      contents: prompt,
      config: {
        temperature: 0.8,
        tools: [{ googleSearch: {} }]
      },
    });

    console.log("Raw Response:");
    console.log(response.text);

  } catch (e) {
    console.error("Error occurred:", e);
  }
}
run();
