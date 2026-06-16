import { NextResponse } from "next/server";
import { GoogleGenAI } from "@google/genai";
import * as _pdf from "pdf-parse";
const pdf = (_pdf as any).default || _pdf;

export const maxDuration = 300; // Vercel 서버리스 타임아웃 300초 연장

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const pdfText = body.pdfText as string;
    const deviceType = (body.deviceType as string) || "desktop";
    const category = (body.category as string) || "economy";

    if (!pdfText || !pdfText.trim()) {
      return NextResponse.json({ error: "해석할 PDF 텍스트 내용이 유효하지 않습니다." }, { status: 400 });
    }

    // 1단계: 썸네일 카피 및 키워드 추출 (JSON 추출)
    const metadataPrompt = `당신은 금융/투자 보고서를 분석하여 검색용 키워드 및 어그로 썸네일 카피를 추출하는 수석 애널리스트입니다.
다음은 분석할 PDF 보고서의 본문 내용입니다:
---
${pdfText.substring(0, 15000)}
---

위 보고서를 깊이 이해하고, 이에 어울리는 네이버 블로그 포스팅용 검색어 정보와 메인 썸네일 카피를 작성하십시오.
1. primary: 이 보고서의 가장 핵심 피사체/주제를 표현하는 시각적이고 직관적인 한글 단어 1~2개 (예: 주식 차트, 공장, 건물)
2. fallback: primary 검색 실패 시 사용할 상위 카테고리 단어 (예: 금융, 경제, IT)
3. englishSubject: 이 주제를 표현하는 구체적인 영어 단어 2~3개 (예: stock market graph, real estate model)
4. thumbnailTop: 상단 해시태그용 어그로 문구 (예: #수익률극대화 #필수투자전략 #긴급시장분석) - 띄어쓰기 없이 해시태그로 3개 작성 (15자 이내)
5. thumbnailMid: 썸네일 중앙 핵심 주제 (예: 반도체 전망, 금리 인하 수혜, 부동산 정책) - 8자 이내 명사형태
6. thumbnailBottom: 신뢰성과 호기심을 극대화하는 하단 문구 (예: 애널리스트 심층 분석, 꼭 알아야 할 리스크) - 13자 이내

반드시 아래 JSON 형식으로만 응답하세요. 다른 설명은 절대 붙이지 마세요.
{"primary": "...", "fallback": "...", "englishSubject": "...", "thumbnailTop": "...", "thumbnailMid": "...", "thumbnailBottom": "..."}`;

    const geminiApiKey = process.env.GEMINI_API_KEY;
    const deepseekApiKey = process.env.DEEPSEEK_API_KEY;

    if (!geminiApiKey && !deepseekApiKey) {
      return NextResponse.json({ error: "GEMINI_API_KEY 또는 DEEPSEEK_API_KEY가 설정되지 않았습니다." }, { status: 400 });
    }

    let searchParams = { primary: "주식 차트", fallback: "금융", englishSubject: "stock market chart", thumbnailTop: "#전문투자분석 #리포트분석", thumbnailMid: "리포트 분석", thumbnailBottom: "애널리스트 심층분석" };

    // 1단계 분석 진행
    try {
      if (geminiApiKey) {
        const ai = new GoogleGenAI({ apiKey: geminiApiKey });
        const res = await ai.models.generateContent({
          model: "gemini-2.5-flash",
          contents: metadataPrompt,
          config: {
            responseMimeType: "application/json",
            temperature: 0.1
          }
        });
        const jsonStr = res.text?.trim() || "{}";
        const cleanedJsonStr = jsonStr.replace(/```json/g, "").replace(/```/g, "").trim();
        searchParams = JSON.parse(cleanedJsonStr);
      } else if (deepseekApiKey) {
        const transResponse = await fetch("https://api.deepseek.com/v1/chat/completions", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${deepseekApiKey}`
          },
          body: JSON.stringify({
            model: "deepseek-chat",
            messages: [{ role: "user", content: metadataPrompt }],
            response_format: { type: "json_object" },
            temperature: 0.1
          })
        });
        if (transResponse.ok) {
          const transData = await transResponse.json();
          const jsonStr = transData.choices[0].message.content.trim();
          const cleanedJsonStr = jsonStr.replace(/```json/g, "").replace(/```/g, "").trim();
          searchParams = JSON.parse(cleanedJsonStr);
        }
      }
    } catch (e) {
      console.warn("PDF Metadata parsing failed, using fallback metadata", e);
    }

    // 2단계: Pixabay 대표 이미지 1장 가져오기
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

        let foundImages = await fetchImages(searchParams.primary, 1);
        if (foundImages.length < 1) {
          const fallbackImages = await fetchImages(searchParams.fallback, 1);
          foundImages = [...foundImages, ...fallbackImages];
        }
        if (foundImages.length < 1) {
          foundImages = await fetchImages("business", 1);
        }
        imageUrls = foundImages;
      } catch (e) {
        console.error("Pixabay fetch error:", e);
      }
    }

    const prompt = `당신은 금융/투자 리서치 센터 및 자산운용사에서 다년간 투자 전략과 기업 분석을 담당한 수석 애널리스트입니다.
우리는 사용자가 제공한 PDF 보고서를 바탕으로, 독자들에게 전문적이면서도 가독성이 뛰어난 네이버 블로그용 투자 분석 글을 작성해야 합니다.

[분석할 PDF 보고서 본문 내용]
---
${pdfText.substring(0, 20000)}
---

[🚨 작성 지침 (전문 투자 분석 블로그)]
1. **전문성 및 신뢰성:**
   - 어조는 철저히 **전문적이고, 객관적이며, 신뢰감 있는 경어체**로 일관되게 작성하십시오. 친근하거나 가벼운 사담 말투, 반말, 슬랭(예: ~음, ~임, ~였음, 호구 등)은 **절대 금지**합니다. (~습니다, ~입니다, ~라고 판단됩니다 등 공적이고 정돈된 표준어 사용)
   - PDF 내의 모든 수치(금리, 주가, 목표가, 비율 등)는 **100% 정확하게 인용**되어야 합니다. 임의로 숫자를 지어내거나 추정치를 팩트인 것처럼 작성하는 행동은 엄격히 금지합니다. (PDF 본문에 나타나지 않은 구체적인 수치는 절대 임의 기재하지 말 것)
2. **구조적 가독성 (HTML 태그 사용):**
   - 글은 마크다운 기호(예: #, *, - 등) 없이 오직 깔끔한 HTML 태그(\`<p>\`, \`<b>\`, \`<h2>\`, \`<h3>\`, \`<table>\`, \`<tr>\`, \`<td>\`, \`<th>\` 등)로만 구성하십시오.
   - 스마트폰 화면 가로너비에서 리듬감 있게 줄바꿈이 깨지지 않도록, 한 줄당 평균 15~20자 내외로 호흡을 쪼개어 문장 중간에 의도적으로 자주 줄바꿈(HTML \`<br>\`) 처리를 하십시오.
   - 복잡한 수치나 비교 데이터가 있다면 반드시 인라인 CSS 스타일이 들어간 세련된 HTML \`<table>\`을 사용해 일목요연하게 정리하십시오. 
     예: \`<table style="width:100%; border-collapse:collapse; margin:20px 0; font-size:14px;"><tr style="background-color:#f8f9fa;"><th style="border:1px solid #ddd; padding:10px; text-align:left;">항목</th><th style="border:1px solid #ddd; padding:10px; text-align:left;">상세 데이터</th></tr><tr><td style="border:1px solid #ddd; padding:10px;">...</td><td style="border:1px solid #ddd; padding:10px;">...</td></tr></table>\`
   - 본문 중간에 보조 이미지 예약어(\`[IMAGE_1]\` 등)는 **일절 기재하지 마십시오.** 보조 이미지는 필요 없습니다.
3. **분석적 서술:**
   - 보고서의 핵심 요약 및 개요를 글의 서두(\`<div style="border-left: 4px solid #0066ff; background-color: #f8fafc; padding: 15px; margin-bottom: 35px; border-radius: 4px;">...</div>\` 스타일의 박스)에 2~4문장으로 정돈해 넣으십시오.
   - 보고서의 결론뿐만 아니라, 그러한 전망이 나온 근거와 리스크 요인을 애널리스트의 관점에서 체계적으로 서술하십시오.
4. **구글 실시간 검색 팩트체크 연동:**
   - (Gemini 모델 전용) 보고서 내의 정보가 실시간 시장 동향과 맞닿아 있으므로, 구글 검색 결과를 통해 관련 최신 기사나 동향을 함께 교차 검증하여 글의 완성도를 극대화하십시오.

[출력 형식 제한]
반드시 아래의 특수 구분자를 사용하여 제목과 본문을 나누어 작성하세요. JSON 형식은 절대 사용하지 마세요.
[TITLE]
(생성된 블로그 제목을 순수 텍스트로 1줄로 작성)
[/TITLE]
[CONTENT]
(생성된 블로그 본문을 HTML 태그만을 엄격하게 사용한 형태로 작성. 대표 이미지 자리 표시를 위해 본문 도입부 직후 적절한 곳에 [THUMBNAIL] 예약어를 단 1번 무조건 삽입하십시오.)
[/CONTENT]`;

    const systemInstruction = "당신은 블로그 포스팅 작가를 돕는 보조 AI입니다. 절대로 검색 결과의 원본 데이터(JSON이나 파이썬 딕셔너리 구조, {'title': ...})를 사용자에게 그대로 노출하거나 본문에 출력하지 마세요. 오직 깔끔하게 다듬어진 블로그 [CONTENT] 텍스트만 출력해야 합니다.";

    let fullText = "";
    let deepseekStreamResponse: Response | null = null;

    // PDF 기반 분석은 팩트체크가 매우 중요하므로 Gemini 2.5-flash를 우선 적용 (구글 검색 Grounding 연동)
    const useGemini = !!geminiApiKey;

    if (useGemini) {
      console.log(`[Generate-PDF] Using Gemini API (gemini-2.5-flash) with Google Search grounding.`);
      try {
        const ai = new GoogleGenAI({ apiKey: geminiApiKey });
        const response = await ai.models.generateContent({
          model: "gemini-2.5-flash",
          contents: prompt,
          config: {
            systemInstruction: systemInstruction + " 반드시 구글 검색 결과를 적극 참고해 거짓 없는 최신 정보를 담으십시오.",
            tools: [{ googleSearch: {} }],
            temperature: 0.3
          }
        });
        fullText = response.text || "";
      } catch (err) {
        console.error("Gemini PDF grounding call failed, falling back to DeepSeek:", err);
      }
    }

    if (!fullText && deepseekApiKey) {
      console.log(`[Generate-PDF] Falling back or using DeepSeek-V3 API.`);
      try {
        deepseekStreamResponse = await fetch("https://api.deepseek.com/v1/chat/completions", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${deepseekApiKey}`
          },
          body: JSON.stringify({
            model: "deepseek-chat",
            messages: [
              { role: "system", content: systemInstruction },
              { role: "user", content: prompt }
            ],
            temperature: 0.3,
            max_tokens: 8192,
            stream: true
          })
        });

        if (!deepseekStreamResponse.ok) {
          const errText = await deepseekStreamResponse.text();
          throw new Error(`DeepSeek stream API failed: ${deepseekStreamResponse.status} ${errText}`);
        }
      } catch (err) {
        console.error("DeepSeek generate stream error:", err);
        throw err;
      }
    }

    if (!fullText && !deepseekStreamResponse) {
      throw new Error("콘텐츠 생성을 진행할 수 없습니다. API 연동 오류를 확인해 주세요.");
    }

    const host = req.headers.get("host") || "localhost:3000";
    const protocol = req.headers.get("x-forwarded-proto") || "http";
    const baseUrl = `${protocol}://${host}`;

    // 썸네일 생성
    let thumbnailHtml = "";
    try {
      const topParams = encodeURIComponent(searchParams.thumbnailTop || "#전문리포트분석 #시장전망");
      const midParams = encodeURIComponent(searchParams.thumbnailMid || "리포트 심층 분석");
      const bottomParams = encodeURIComponent(searchParams.thumbnailBottom || "수석 애널리스트 팩트체크");
      
      const styleParam = `&style=economy`;
      const bgParam = imageUrls.length > 0 ? `&bg=${encodeURIComponent(imageUrls[0])}` : "";
      const ogUrl = `${baseUrl}/api/og?top=${topParams}&mid=${midParams}&bottom=${bottomParams}${styleParam}${bgParam}&ext=.png`;

      thumbnailHtml = `<div style="text-align: center; margin-bottom: 24px;">
        <img src="${ogUrl}" alt="대표 썸네일" style="max-width: 100%; height: auto; border-radius: 12px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -2px rgba(0,0,0,0.05);" />
      </div>`;
    } catch (imgError) {
      console.error("OG Thumbnail Generation Failed:", imgError);
    }

    // 보조 이미지는 필요 없다고 하였으므로 빈 배열
    const processedImages: string[] = [];

    const readable = new ReadableStream({
      async start(controller) {
        const encoder = new TextEncoder();
        try {
          const metaMsg = JSON.stringify({ type: "meta", thumbnailHtml, images: processedImages });
          controller.enqueue(encoder.encode(`data: ${metaMsg}\n\n`));

          let finalFullText = fullText;
          if (!finalFullText && deepseekStreamResponse) {
            const reader = deepseekStreamResponse.body?.getReader();
            const decoder = new TextDecoder("utf-8");
            let buffer = "";

            if (reader) {
              while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop() || "";

                for (const line of lines) {
                  const cleanedLine = line.trim();
                  if (cleanedLine.startsWith("data:")) {
                    const dataContent = cleanedLine.substring(5).trim();
                    if (dataContent === "[DONE]") break;
                    try {
                      const parsed = JSON.parse(dataContent);
                      const delta = parsed.choices[0]?.delta?.content || "";
                      finalFullText += delta;
                    } catch (e) {
                      // JSON 파싱 실패 무시
                    }
                  }
                }
              }
            }
          }

          // 자연스러운 스트리밍 타이핑 효과 시뮬레이션
          const chunkSize = 25;
          for (let i = 0; i < finalFullText.length; i += chunkSize) {
            const chunk = finalFullText.substring(i, i + chunkSize);
            const textMsg = JSON.stringify({ type: "text", text: chunk });
            controller.enqueue(encoder.encode(`data: ${textMsg}\n\n`));
            await new Promise((resolve) => setTimeout(resolve, 3));
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
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive"
      }
    });

  } catch (error: unknown) {
    console.error("PDF Generate API Error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "PDF 분석 원고 생성을 진행하지 못했습니다." },
      { status: 500 }
    );
  }
}
