"use client";

import { useState } from "react";
import { Sparkles, Copy, CheckCircle2, PenTool, Loader2, AlertCircle, Lightbulb, TrendingUp, DollarSign, FileUp, Trash2 } from "lucide-react";

// 클라이언트 사이드 PDF.js 라이브러리 동적 로드
const loadPdfJs = (): Promise<any> => {
  return new Promise((resolve, reject) => {
    if (typeof window === "undefined") {
      reject(new Error("브라우저 환경이 필요합니다."));
      return;
    }
    if ((window as any).pdfjsLib) {
      resolve((window as any).pdfjsLib);
      return;
    }
    const script = document.createElement("script");
    script.src = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.min.js";
    script.onload = () => {
      const pdfjsLib = (window as any).pdfjsLib;
      pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js";
      resolve(pdfjsLib);
    };
    script.onerror = () => reject(new Error("PDF.js 라이브러리를 로드하는 데 실패했습니다."));
    document.head.appendChild(script);
  });
};

// 클라이언트 사이드 PDF 텍스트 추출 (최대 20페이지)
const extractTextFromPdfClient = async (file: File, maxPages: number = 20): Promise<string> => {
  const pdfjsLib = await loadPdfJs();
  const arrayBuffer = await file.arrayBuffer();
  const loadingTask = pdfjsLib.getDocument({ data: arrayBuffer });
  const pdf = await loadingTask.promise;
  
  let fullText = "";
  const pagesToParse = Math.min(pdf.numPages, maxPages);
  
  for (let i = 1; i <= pagesToParse; i++) {
    try {
      const page = await pdf.getPage(i);
      const textContent = await page.getTextContent();
      const pageText = textContent.items
        .map((item: any) => item.str)
        .join(" ");
      fullText += pageText + "\n";
    } catch (pageErr) {
      console.error(`페이지 ${i} 파싱 에러:`, pageErr);
    }
  }
  
  return fullText;
};

export default function Home() {
  const [keyword, setKeyword] = useState("");
  const [bcTitle, setBcTitle] = useState("");
  const [bcLink, setBcLink] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  
  const [result, setResult] = useState<{
    title: string;
    content: string;
  } | null>(null);
  
  const [copiedField, setCopiedField] = useState<string | null>(null);
  
  const [mode, setMode] = useState<'keyword' | 'pdf'>('keyword');
  const [pdfFile, setPdfFile] = useState<File | null>(null);

  // 통합 트렌드 (일반 + 경제)
  const [aiTrends, setAiTrends] = useState<any[]>([]);
  const [isTrendLoading, setIsTrendLoading] = useState(false);
  const [selectedBots, setSelectedBots] = useState<string[]>([]);
  const [trendCoreKeyword, setTrendCoreKeyword] = useState("");

  const LOCAL_STORAGE_KEY = 'autoblog_keyword_history';

  const getBannedKeywords = () => {
    if (typeof window === 'undefined') return [];
    try {
      const stored = localStorage.getItem(LOCAL_STORAGE_KEY);
      if (!stored) return [];
      const history = JSON.parse(stored);
      return Object.entries(history).filter(([_, count]: any) => count >= 3).map(([kw]) => kw);
    } catch (e) {
      return [];
    }
  };

  const saveKeywordHistory = (keywords: string[]) => {
    if (typeof window === 'undefined') return;
    try {
      const stored = localStorage.getItem(LOCAL_STORAGE_KEY);
      const history = stored ? JSON.parse(stored) : {};
      keywords.forEach(kw => {
        history[kw] = (history[kw] || 0) + 1;
      });
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(history));
    } catch (e) {}
  };

  const toggleBotSelection = (botId: string) => {
    setSelectedBots(prev => {
      if (prev.includes(botId)) {
        return [];
      }
      return [botId];
    });
  };

  const handleExtractMultiTrends = async () => {
    if (selectedBots.length !== 1) {
      alert("정확히 1개의 호기를 선택해야 합니다.");
      return;
    }
    setIsTrendLoading(true);
    setResult(null);
    setAiTrends([]);
    try {
      const bannedKeywords = getBannedKeywords();
      
      const res = await fetch('/api/agent-trend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bannedKeywords, style: selectedBots[0], coreKeyword: trendCoreKeyword }),
      });
      const data = await res.json();
      
      if (data.trends && Array.isArray(data.trends)) {
        const slicedTrends = data.trends.slice(0, 5);
        setAiTrends(slicedTrends);
        saveKeywordHistory(slicedTrends.map((t: any) => t.keyword));
      } else {
        alert(data.error || 'AI 트렌드 발굴에 실패했습니다.');
      }
    } catch (e) {
      alert('네트워크 오류가 발생했습니다.');
    } finally {
      setIsTrendLoading(false);
    }
  };

  const handleGenerate = async (e?: React.FormEvent | null, overrideKeyword?: string, category: string = 'general') => {
    if (e) e.preventDefault();
    
    if (mode === 'keyword') {
      let currentKeyword = overrideKeyword || keyword;
      if (!currentKeyword.trim()) return;
      if (overrideKeyword) {
        setKeyword(overrideKeyword);
      }
    } else {
      if (!pdfFile) {
        setErrorMsg("분석할 PDF 파일을 업로드해 주세요.");
        return;
      }
    }

    setIsGenerating(true);
    setResult(null);
    setErrorMsg(null);
    
    window.scrollTo({ top: 0, behavior: 'smooth' });

    try {
      let response: Response;

      if (mode === 'keyword') {
        let currentKeyword = overrideKeyword || keyword;
        response = await fetch('/api/generate', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ keyword: currentKeyword, deviceType: 'mobile', category }),
        });
      } else {
        // 클라이언트 사이드에서 PDF 텍스트 추출 (대용량 파일 413 Payload Too Large 방지)
        let extractedText = "";
        try {
          extractedText = await extractTextFromPdfClient(pdfFile!);
        } catch (pdfErr: any) {
          throw new Error(`PDF 파일 분석 중 오류가 발생했습니다: ${pdfErr.message || pdfErr}`);
        }

        if (!extractedText || extractedText.trim().length < 50) {
          throw new Error("PDF 파일에서 읽을 수 있는 텍스트가 너무 적거나 없습니다. 스캔된 이미지 형식이거나 보안이 적용된 파일인지 확인해 주세요.");
        }

        response = await fetch('/api/generate-pdf', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            pdfText: extractedText,
            deviceType: "mobile",
            category,
          }),
        });
      }

      if (!response.ok) {
        let errMsg = `생성 중 오류가 발생했습니다. (상태 코드: ${response.status})`;
        try {
          const errData = await response.json();
          if (errData.error) errMsg = errData.error;
        } catch (_) {
          try {
            const rawText = await response.clone().text();
            if (rawText) {
              errMsg += ` - ${rawText.substring(0, 100)}`;
            }
          } catch (__) {}
        }
        throw new Error(errMsg);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("스트림을 읽을 수 없습니다.");

      const decoder = new TextDecoder();
      let aiText = "";
      let metaData: any = null;
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        
        let boundary = buffer.indexOf('\n\n');
        while (boundary !== -1) {
           const message = buffer.substring(0, boundary);
           buffer = buffer.substring(boundary + 2);
           
           if (message.startsWith('data: ')) {
               try {
                   const data = JSON.parse(message.substring(6));
                   if (data.type === 'meta') {
                       metaData = data;
                   } else if (data.type === 'text') {
                       aiText += data.text;
                       
                       let currentTitle = "블로그 타이틀 작성 중...";
                       const titleMatch = aiText.match(/\[TITLE\]([\s\S]*?)\[\/TITLE\]/i);
                       if (titleMatch) {
                           currentTitle = titleMatch[1].trim();
                       } else if (aiText.includes('[TITLE]')) {
                           currentTitle = aiText.split(/\[TITLE\]/i)[1].trim(); 
                       }
                       currentTitle = currentTitle.replace(/<[^>]*>/g, '');

                       let currentContent = aiText;
                       if (aiText.includes('[CONTENT]')) {
                           currentContent = aiText.split(/\[CONTENT\]/i)[1] || "";
                       }
                       currentContent = currentContent.replace(/\[\/CONTENT\]/i, '').trim();

                       if (metaData) {
                           if (currentContent.includes('[THUMBNAIL]')) {
                               currentContent = currentContent.replace('[THUMBNAIL]', metaData.thumbnailHtml);
                           } else if (metaData.thumbnailHtml) {
                               currentContent = metaData.thumbnailHtml + '<br/>' + currentContent;
                           }
                           
                           if (metaData.images && metaData.images.length > 0) {
                               metaData.images.forEach((imgUrl: string, idx: number) => {
                                   const ph = `[IMAGE_${idx+1}]`;
                                   const imgTag = `<div style="text-align: center; margin: 32px 0;"><img src="${imgUrl}" style="max-width: 100%; height: auto; border-radius: 8px;"></div>`;
                                   if (currentContent.includes(ph)) {
                                       currentContent = currentContent.replace(ph, imgTag);
                                   }
                               });
                           }
                       }
                       
                       setResult({ title: currentTitle, content: currentContent + '<span className="inline-block w-2 h-4 ml-1 bg-[#00c73c] animate-pulse"></span>' });
                   }
               } catch(e) { console.error("SSE parse error", e, message); }
           }
           boundary = buffer.indexOf('\n\n');
        }
      }

      let finalContent = aiText;
      if (finalContent.includes('[CONTENT]')) finalContent = finalContent.split(/\[CONTENT\]/i)[1] || "";
      finalContent = finalContent.replace(/\[\/CONTENT\]/i, '').trim();
      
      if (metaData) {
          if (finalContent.includes('[THUMBNAIL]')) {
              finalContent = finalContent.replace('[THUMBNAIL]', metaData.thumbnailHtml);
          } else {
              finalContent = metaData.thumbnailHtml + '<br/>' + finalContent;
          }
          
          if (metaData.images) {
              metaData.images.forEach((imgUrl: string, idx: number) => {
                  const ph = `[IMAGE_${idx+1}]`;
                  const imgTag = `<div style="text-align: center; margin: 32px 0;"><img src="${imgUrl}" style="max-width: 100%; height: auto; border-radius: 8px;"></div>`;
                  if (finalContent.includes(ph)) {
                     finalContent = finalContent.replace(ph, imgTag);
                  } else {
                     finalContent += imgTag; 
                  }
              });
          }
      }
      
      const rawTitle = aiText.match(/\[TITLE\]([\s\S]*?)\[\/TITLE\]/i)?.[1]?.trim() || "제목 완성";
      const finalTitle = rawTitle.replace(/<[^>]*>/g, '');
      setResult({ title: finalTitle, content: finalContent });

    } catch (error: unknown) {
      console.error(error);
      if (error instanceof Error) {
        if (error.name === 'AbortError') return;
        setErrorMsg(error.message);
      } else {
        setErrorMsg('알 수 없는 오류가 발생했습니다.');
      }
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSelectAllAndCopy = async (elementId: string, field: string) => {
    const el = document.getElementById(elementId);
    if (!el) return;

    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(el);
    
    if (selection) {
      selection.removeAllRanges();
      selection.addRange(range);
    }
    
    let copySuccess = false;
    try {
      const result = document.execCommand('copy');
      if (result) copySuccess = true;
    } catch (err) {}

    if (!copySuccess && navigator.clipboard && window.ClipboardItem) {
      try {
        const html = el.innerHTML;
        const text = el.innerText || el.textContent || '';
        const wrappedHtml = `<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>${html}</body></html>`;
        
        const htmlBlob = new Blob([wrappedHtml], { type: 'text/html' });
        const textBlob = new Blob([text], { type: 'text/plain' });
        const clipboardItem = new window.ClipboardItem({
          'text/html': htmlBlob,
          'text/plain': textBlob
        });
        
        await navigator.clipboard.write([clipboardItem]);
        copySuccess = true;
      } catch (err) {}
    }

    if (copySuccess) {
      setCopiedField(field);
      setTimeout(() => setCopiedField(null), 2000);
    } else {
      alert('자동 복사가 차단되었습니다. 파랗게 선택된 본문을 터치하여 나타나는 기본 [복사] 버튼을 직접 눌러주세요!');
    }
  };

  const renderTrendBlock = (trends: any[], title: string, icon: React.ReactNode, type: 'purple' | 'blue' | 'emerald' | 'red', category: string) => {
    if (trends.length === 0) return null;
    
    const colorMap = {
      purple: {
        bg: 'bg-purple-50', border: 'border-purple-100', titleText: 'text-purple-900', badgeInfo: 'bg-purple-600', 
        cardBorder: 'border-purple-100', cardTitle: 'text-purple-900 hover:text-purple-600', 
        btn: 'bg-purple-50 hover:bg-purple-600 text-purple-700 hover:text-white border-purple-200 hover:border-purple-600'
      },
      blue: {
        bg: 'bg-blue-50', border: 'border-blue-100', titleText: 'text-blue-900', badgeInfo: 'bg-blue-600', 
        cardBorder: 'border-blue-100', cardTitle: 'text-blue-900 hover:text-blue-600', 
        btn: 'bg-blue-50 hover:bg-blue-600 text-blue-700 hover:text-white border-blue-200 hover:border-blue-600'
      },
      emerald: {
        bg: 'bg-emerald-50', border: 'border-emerald-100', titleText: 'text-emerald-900', badgeInfo: 'bg-emerald-600', 
        cardBorder: 'border-emerald-100', cardTitle: 'text-emerald-900 hover:text-emerald-600', 
        btn: 'bg-emerald-50 hover:bg-emerald-600 text-emerald-700 hover:text-white border-emerald-200 hover:border-emerald-600'
      },
      red: {
        bg: 'bg-red-50', border: 'border-red-100', titleText: 'text-red-900', badgeInfo: 'bg-red-600', 
        cardBorder: 'border-red-100', cardTitle: 'text-red-900 hover:text-red-600', 
        btn: 'bg-red-50 hover:bg-red-600 text-red-700 hover:text-white border-red-200 hover:border-red-600'
      }
    };
    const colors = colorMap[type];

    return (
      <div className={`mt-6 ${colors.bg} p-6 rounded-2xl border ${colors.border} shadow-sm animate-fade-in`}>
        <h3 className={`text-lg font-bold ${colors.titleText} mb-4 flex items-center gap-2`}>
          <span className={`${colors.badgeInfo} text-white text-xs px-2 py-1 rounded-md flex items-center gap-1`}>
            {icon} AI 픽
          </span>
          {title}
        </h3>
        <div className="flex flex-col gap-3">
          {trends.map((trend, i) => (
            <div key={i} className={`p-4 bg-white border ${colors.cardBorder} rounded-xl shadow-sm group`}>
              <div className="flex justify-between items-start mb-2">
                <span className={`font-extrabold text-lg transition-colors ${colors.cardTitle}`}>{trend.keyword}</span>
                <span className="text-xs font-semibold px-2 py-1 bg-gray-50 border border-gray-200 rounded text-gray-600">
                  월 조회: {trend.monthlyTotalCnt > 0 ? `${trend.monthlyTotalCnt.toLocaleString()}회` : '신규/미집계'}
                </span>
              </div>
              <p className="text-sm text-gray-600 bg-gray-50 border border-gray-100 p-2.5 rounded-lg leading-snug mb-3">{trend.reason}</p>
              <button
                type="button"
                onClick={() => handleGenerate(null, trend.keyword, category)}
                className={`w-full py-2.5 font-bold rounded-lg transition-colors flex items-center justify-center gap-2 border text-sm ${colors.btn}`}
              >
                <PenTool className="w-4 h-4" /> 이 키워드로 즉시 자동 생성
              </button>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const isAnyLoading = isTrendLoading || isGenerating;

  return (
    <div className="min-h-screen pb-20 text-slate-900 bg-slate-50">
      <div className="fixed top-0 left-0 w-full h-[50vh] bg-gradient-to-b from-cyan-50 to-transparent -z-10 pointer-events-none" />
      
      <main className="container pt-16 md:pt-24 animate-fade-in">
        <section className="text-center mb-16 max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white border border-slate-200 text-sm font-bold text-slate-800 mb-6 shadow-sm">
            <Sparkles className="w-4 h-4" />
            <span>AI 기반 네이버 블로그 자동 완성</span>
          </div>
          <h1 className="heading-1 mb-6 transition-colors duration-300 text-[#005a2b]">
            키워드 하나로 끝내는<br />수익형 블로그 포스팅 자동화
          </h1>
          <p className="text-xl text-muted">
            복사/붙여넣기에 최적화된 고품질 초안을 5초 만에 만들어냅니다.<br className="hidden md:block" />
            저품질 걱정 없는 완벽한 네이버 맞춤형 글쓰기를 경험해보세요.
          </p>
        </section>

        <div className="grid md:grid-cols-[1fr_1.2fr] gap-8 max-w-6xl mx-auto">
          <section className="glass-panel p-8 delay-100 h-fit">
            
            <h2 className="heading-2 mb-6 flex items-center gap-2 text-slate-900">
              <PenTool className="w-6 h-6 text-slate-800" />
              AI가 알아서 🚀 빈집 털어옵니다
            </h2>

            {/* 생성 모드 선택 탭 */}
            <div className="flex bg-slate-100 p-1 rounded-xl mb-6 border border-slate-200">
              <button
                type="button"
                onClick={() => setMode('keyword')}
                className={`flex-1 py-2.5 text-sm font-bold rounded-lg transition-all ${
                  mode === 'keyword'
                    ? 'bg-white text-slate-900 shadow-sm'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                키워드 자동 생성
              </button>
              <button
                type="button"
                onClick={() => setMode('pdf')}
                className={`flex-1 py-2.5 text-sm font-bold rounded-lg transition-all ${
                  mode === 'pdf'
                    ? 'bg-white text-slate-900 shadow-sm'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                PDF 리포트 분석
              </button>
            </div>
            
            <form onSubmit={handleGenerate} className="space-y-6">
              {mode === 'keyword' ? (
                <div className="space-y-4">
                  {/* 핵심 키워드 입력 */}
                  <div className="space-y-2 mb-2">
                    <label htmlFor="trendCoreKeyword" className="block text-sm font-semibold">
                      트렌드 추출용 핵심 키워드 <span className="text-slate-400 font-normal">(선택)</span>
                    </label>
                    <input
                      id="trendCoreKeyword"
                      type="text"
                      value={trendCoreKeyword}
                      onChange={(e) => setTrendCoreKeyword(e.target.value)}
                      placeholder="예) 60대 비즈니스 경제"
                      className="w-full px-4 py-3 rounded-md border border-slate-300 bg-white text-slate-900 placeholder-slate-400 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 outline-none transition-all shadow-sm"
                    />
                    <p className="text-xs text-slate-500">두 번째 블로그 추출 시 키워드를 기반으로 연관 롱테일을 찾아옵니다.</p>
                  </div>

                  {/* 10 Core Bot Modes (2 Columns x 5 Rows) - 비즈니스/경제 10대 황금 카테고리 재편 */}
                  <div className="grid grid-cols-2 gap-0 border border-slate-300 rounded-md overflow-hidden bg-slate-200 gap-[1px]">
                    {/* Row 1 */}
                    <button type="button" onClick={() => toggleBotSelection('bot1')} disabled={isAnyLoading} className={`w-full px-4 py-4 bg-white hover:bg-slate-50 flex flex-col items-start gap-1 transition-colors ${selectedBots.includes('bot1') ? 'bg-green-100 ring-2 ring-inset ring-green-500' : ''}`}>
                      <div className="flex items-center gap-1">
                        {isTrendLoading && selectedBots.includes('bot1') ? <Loader2 className="w-4 h-4 animate-spin text-green-600" /> : <Sparkles className="w-4 h-4 text-black" />}
                        <span className="text-[14px] font-bold text-slate-900 text-left">1호기 (재테크/부업)</span>
                      </div>
                      <span className="text-[12px] font-normal text-slate-600 leading-tight text-left">앱테크/N잡러 부의 추월차선</span>
                    </button>
                    <button type="button" onClick={() => toggleBotSelection('bot2')} disabled={isAnyLoading} className={`w-full px-4 py-4 bg-white hover:bg-slate-50 flex flex-col items-start gap-1 transition-colors ${selectedBots.includes('bot2') ? 'bg-green-100 ring-2 ring-inset ring-green-500' : ''}`}>
                      <div className="flex items-center gap-1">
                        {isTrendLoading && selectedBots.includes('bot2') ? <Loader2 className="w-4 h-4 animate-spin text-green-600" /> : <Sparkles className="w-4 h-4 text-black" />}
                        <span className="text-[14px] font-bold text-slate-900 text-left">2호기 (지원금/복지)</span>
                      </div>
                      <span className="text-[12px] font-normal text-slate-600 leading-tight text-left">숨은 환급금/지자체 복지 혜택</span>
                    </button>
                    
                    {/* Row 2 */}
                    <button type="button" onClick={() => toggleBotSelection('bot3')} disabled={isAnyLoading} className={`w-full px-4 py-4 bg-white hover:bg-slate-50 flex flex-col items-start gap-1 transition-colors ${selectedBots.includes('bot3') ? 'bg-green-100 ring-2 ring-inset ring-green-500' : ''}`}>
                      <div className="flex items-center gap-1">
                        {isTrendLoading && selectedBots.includes('bot3') ? <Loader2 className="w-4 h-4 animate-spin text-green-600" /> : <Sparkles className="w-4 h-4 text-black" />}
                        <span className="text-[14px] font-bold text-slate-900 text-left">3호기 (부동산/대출)</span>
                      </div>
                      <span className="text-[12px] font-normal text-slate-600 leading-tight text-left">주거 디딤돌/버팀목 특례 정책</span>
                    </button>
                    <button type="button" onClick={() => toggleBotSelection('bot4')} disabled={isAnyLoading} className={`w-full px-4 py-4 bg-white hover:bg-slate-50 flex flex-col items-start gap-1 transition-colors ${selectedBots.includes('bot4') ? 'bg-green-100 ring-2 ring-inset ring-green-500' : ''}`}>
                      <div className="flex items-center gap-1">
                        {isTrendLoading && selectedBots.includes('bot4') ? <Loader2 className="w-4 h-4 animate-spin text-green-600" /> : <Sparkles className="w-4 h-4 text-black" />}
                        <span className="text-[14px] font-bold text-slate-900 text-left">4호기 (예적금/특판)</span>
                      </div>
                      <span className="text-[12px] font-normal text-slate-600 leading-tight text-left">초고금리 파킹통장/적금 비교</span>
                    </button>
                    
                    {/* Row 3 */}
                    <button type="button" onClick={() => toggleBotSelection('bot5')} disabled={isAnyLoading} className={`w-full px-4 py-4 bg-white hover:bg-slate-50 flex flex-col items-start gap-1 transition-colors ${selectedBots.includes('bot5') ? 'bg-green-100 ring-2 ring-inset ring-green-500' : ''}`}>
                      <div className="flex items-center gap-1">
                        {isTrendLoading && selectedBots.includes('bot5') ? <Loader2 className="w-4 h-4 animate-spin text-green-600" /> : <Sparkles className="w-4 h-4 text-black" />}
                        <span className="text-[14px] font-bold text-slate-900 text-left">5호기 (세금/연금)</span>
                      </div>
                      <span className="text-[12px] font-normal text-slate-600 leading-tight text-left">연말정산/상속세/건보료 줄이기</span>
                    </button>
                    <button type="button" onClick={() => toggleBotSelection('bot6')} disabled={isAnyLoading} className={`w-full px-4 py-4 bg-white hover:bg-slate-50 flex flex-col items-start gap-1 transition-colors ${selectedBots.includes('bot6') ? 'bg-green-100 ring-2 ring-inset ring-green-500' : ''}`}>
                      <div className="flex items-center gap-1">
                        {isTrendLoading && selectedBots.includes('bot6') ? <Loader2 className="w-4 h-4 animate-spin text-green-600" /> : <Sparkles className="w-4 h-4 text-black" />}
                        <span className="text-[14px] font-bold text-slate-900 text-left">6호기 (주식/세계경제)</span>
                      </div>
                      <span className="text-[12px] font-normal text-slate-600 leading-tight text-left">미국 빅테크/국내 테마주 동향</span>
                    </button>
                    
                    {/* Row 4 */}
                    <button type="button" onClick={() => toggleBotSelection('bot7')} disabled={isAnyLoading} className={`w-full px-4 py-4 bg-white hover:bg-slate-50 flex flex-col items-start gap-1 transition-colors ${selectedBots.includes('bot7') ? 'bg-green-100 ring-2 ring-inset ring-green-500' : ''}`}>
                      <div className="flex items-center gap-1">
                        {isTrendLoading && selectedBots.includes('bot7') ? <Loader2 className="w-4 h-4 animate-spin text-green-600" /> : <Sparkles className="w-4 h-4 text-black" />}
                        <span className="text-[14px] font-bold text-slate-900 text-left">7호기 (가상자산)</span>
                      </div>
                      <span className="text-[12px] font-normal text-slate-600 leading-tight text-left">비트코인 반감기/과세 대응 팁</span>
                    </button>
                    <button type="button" onClick={() => toggleBotSelection('bot8')} disabled={isAnyLoading} className={`w-full px-4 py-4 bg-white hover:bg-slate-50 flex flex-col items-start gap-1 transition-colors ${selectedBots.includes('bot8') ? 'bg-green-100 ring-2 ring-inset ring-green-500' : ''}`}>
                      <div className="flex items-center gap-1">
                        {isTrendLoading && selectedBots.includes('bot8') ? <Loader2 className="w-4 h-4 animate-spin text-green-600" /> : <Sparkles className="w-4 h-4 text-black" />}
                        <span className="text-[14px] font-bold text-slate-900 text-left">8호기 (창업/소상공인)</span>
                      </div>
                      <span className="text-[12px] font-normal text-slate-600 leading-tight text-left">청년창업/소상공인 무이자 대출</span>
                    </button>
                    
                    {/* Row 5 */}
                    <button type="button" onClick={() => toggleBotSelection('bot9')} disabled={isAnyLoading} className={`w-full px-4 py-4 bg-white hover:bg-slate-50 flex flex-col items-start gap-1 transition-colors ${selectedBots.includes('bot9') ? 'bg-green-100 ring-2 ring-inset ring-green-500' : ''}`}>
                      <div className="flex items-center gap-1">
                        {isTrendLoading && selectedBots.includes('bot9') ? <Loader2 className="w-4 h-4 animate-spin text-green-600" /> : <Sparkles className="w-4 h-4 text-black" />}
                        <span className="text-[14px] font-bold text-slate-900 text-left">9호기 (소비/쇼핑테크)</span>
                      </div>
                      <span className="text-[12px] font-normal text-slate-600 leading-tight text-left">마트 세일/알리테무 직구 대응</span>
                    </button>
                    <button type="button" onClick={() => toggleBotSelection('bot10')} disabled={isAnyLoading} className={`w-full px-4 py-4 bg-white hover:bg-slate-50 flex flex-col items-start gap-1 transition-colors ${selectedBots.includes('bot10') ? 'bg-green-100 ring-2 ring-inset ring-green-500' : ''}`}>
                      <div className="flex items-center gap-1">
                        {isTrendLoading && selectedBots.includes('bot10') ? <Loader2 className="w-4 h-4 animate-spin text-green-600" /> : <Sparkles className="w-4 h-4 text-black" />}
                        <span className="text-[14px] font-bold text-slate-900 text-left">10호기 (비즈니스/트렌드)</span>
                      </div>
                      <span className="text-[12px] font-normal text-slate-600 leading-tight text-left">챗GPT 업무 활용/몸값 올리기</span>
                    </button>
                  </div>

                  {selectedBots.length > 0 && (
                    <div className="mt-4">
                      <button
                        type="button"
                        onClick={handleExtractMultiTrends}
                        disabled={selectedBots.length !== 1 || isTrendLoading}
                        className={`w-full py-4 rounded-lg font-bold text-lg transition-all flex items-center justify-center gap-2 ${
                          selectedBots.length === 1
                            ? 'bg-[#00c73c] hover:bg-[#00a833] text-white shadow-lg transform hover:scale-[1.02]'
                            : 'bg-slate-200 text-slate-400 cursor-not-allowed'
                        }`}
                      >
                        {isTrendLoading ? <Loader2 className="w-6 h-6 animate-spin" /> : <Sparkles className="w-6 h-6" />}
                        {selectedBots.length === 1 ? "선택한 1개 호기로 5개 키워드 추출 🚀" : "1개의 호기를 선택해주세요"}
                      </button>
                    </div>
                  )}

                  {renderTrendBlock(aiTrends, "AI 연계 황금 키워드 TOP 5", <Lightbulb className="w-3 h-3"/>, 'emerald', selectedBots.join(','))}

                  <div className="flex items-center gap-3 my-6">
                    <div className="h-px bg-slate-200 flex-1"></div>
                    <span className="text-sm font-semibold text-slate-400">또는</span>
                    <div className="h-px bg-slate-200 flex-1"></div>
                  </div>

                  <div className="space-y-2">
                    <label htmlFor="keyword" className="block text-sm font-semibold">
                      직접 작성할 키워드 입력 <span className="text-red-500">*</span>
                    </label>
                    <input
                      id="keyword"
                      type="text"
                      value={keyword}
                      onChange={(e) => setKeyword(e.target.value)}
                      placeholder="직접 작성하고 싶은 특정 키워드가 있다면 입력하세요."
                      className="w-full px-4 py-3 rounded-md border border-slate-300 bg-white text-slate-900 placeholder-slate-400 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 outline-none transition-all shadow-sm"
                    />
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <label className="block text-sm font-semibold">
                      분석할 PDF 리포트 파일 업로드 <span className="text-red-500">*</span>
                    </label>
                    <div
                      className={`border-2 border-dashed rounded-xl p-8 text-center transition-all ${
                        pdfFile
                          ? 'border-emerald-500 bg-emerald-50/50'
                          : 'border-slate-300 hover:border-cyan-500 bg-white hover:bg-slate-50/50'
                      }`}
                    >
                      <input
                        type="file"
                        id="pdf-file-upload"
                        accept=".pdf"
                        className="hidden"
                        onChange={(e) => {
                          const file = e.target.files?.[0] || null;
                          setPdfFile(file);
                        }}
                      />
                      <label htmlFor="pdf-file-upload" className="cursor-pointer block space-y-3">
                        <div className="flex justify-center">
                          <FileUp className={`w-10 h-10 ${pdfFile ? 'text-emerald-600' : 'text-slate-400'}`} />
                        </div>
                        <div>
                          {pdfFile ? (
                            <div className="space-y-1">
                              <p className="font-semibold text-emerald-900">{pdfFile.name}</p>
                              <p className="text-xs text-emerald-700">{(pdfFile.size / (1024 * 1024)).toFixed(2)} MB</p>
                            </div>
                          ) : (
                            <div className="space-y-1">
                              <p className="font-semibold text-slate-700">여기를 클릭하거나 PDF 파일을 끌어다 놓으세요.</p>
                              <p className="text-xs text-slate-500">지원 형식: PDF (최대 10MB)</p>
                            </div>
                          )}
                        </div>
                      </label>
                    </div>
                    {pdfFile && (
                      <button
                        type="button"
                        onClick={() => setPdfFile(null)}
                        className="text-xs font-semibold text-red-500 hover:underline mt-2 flex items-center gap-1"
                      >
                        <Trash2 className="w-3 h-3" /> 파일 삭제
                      </button>
                    )}
                  </div>
                </div>
              )}

              {errorMsg && (
                <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-md text-sm flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                  <span>{errorMsg}</span>
                </div>
              )}

              <button
                type="submit"
                disabled={isAnyLoading}
                onClick={(e) => handleGenerate(e, undefined, mode === 'keyword' ? (selectedBots[0] || 'general') : 'economy')}
                className="w-full py-4 text-lg mt-8 disabled:opacity-70 disabled:cursor-not-allowed bg-[#00c73c] hover:bg-[#00a832] text-white font-bold rounded-xl shadow-md transition-all flex items-center justify-center gap-2"
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    포스팅 생성 중...
                  </>
                ) : (
                  <>
                    <PenTool className="w-5 h-5" />
                    {mode === 'keyword' ? `입력된 키워드로 포스팅 생성 (${selectedBots[0] || 'general'} 썸네일)` : "PDF 리포트 분석하여 포스팅 생성 (전문 투자 썸네일)"}
                  </>
                )}
              </button>
            </form>
          </section>

          {/* 생성 결과 패널 */}
          <section className="glass-panel p-8 delay-200">
            {result ? (
              <div className="space-y-8 animate-fade-in">
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <h3 className="text-sm font-semibold text-muted">추천 제목</h3>
                    <div className="flex gap-2">
                      <button 
                        onClick={() => handleSelectAllAndCopy('generated-title', 'title')}
                        className="text-xs flex items-center gap-1 text-[#00c73c] hover:bg-green-50 px-2 py-1 rounded transition-colors border border-green-200"
                      >
                        {copiedField === 'title' ? <CheckCircle2 className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                        {copiedField === 'title' ? '복사됨' : '복사'}
                      </button>
                    </div>
                  </div>
                  <div id="generated-title" className="p-4 bg-white text-black border border-gray-200 rounded-md shadow-sm font-semibold selection:bg-green-200 selection:text-green-900" style={{ color: '#000000', backgroundColor: '#ffffff' }}>
                    {result.title}
                  </div>
                </div>

                <div>
                  <div className="flex justify-between items-center mb-2">
                    <h3 className="text-sm font-semibold text-muted">본문 (모바일 블로그 호환)</h3>
                    <div className="flex flex-wrap justify-end gap-2">
                       <button 
                        onClick={() => handleSelectAllAndCopy('generated-content', 'content')}
                        className="text-xs flex items-center gap-1 bg-[#00c73c] text-white hover:bg-green-600 px-3 py-1.5 rounded transition-colors shadow-sm font-medium"
                      >
                        {copiedField === 'content' ? <CheckCircle2 className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                        {copiedField === 'content' ? '완료 (붙여넣기 하세요)' : '본문 전체 복사'}
                      </button>
                    </div>
                  </div>
                  
                  <div className="bg-green-50 border border-green-200 text-green-800 text-xs p-3 rounded-md mb-3 flex items-start gap-2">
                    <Lightbulb className="w-4 h-4 shrink-0 mt-0.5 text-green-600" />
                    <div>
                      <span className="font-bold">네이버 폰 앱(스마트폰) 완벽 호환!</span> 기본적으로 모바일 포맷으로 완성되었습니다.<br/>
                      아래 <strong>[본문 전체 복사]</strong> 버튼을 누르시고 네이버 블로그 앱에서 바로 붙여넣어주세요.
                    </div>
                  </div>

                  <div 
                    id="generated-content"
                    className="p-5 bg-white text-black border border-gray-200 rounded-md shadow-sm min-h-[300px] leading-relaxed text-[15px] prose max-w-none selection:bg-green-200 selection:text-green-900"
                    style={{ color: '#000000', backgroundColor: '#ffffff' }}
                    dangerouslySetInnerHTML={{ __html: result.content }}
                  />
                </div>
              </div>
            ) : (
              <div className="h-full min-h-[400px] flex flex-col items-center justify-center text-center opacity-50">
                <Sparkles className="w-12 h-12 mb-4 text-gray-400" />
                <p className="text-gray-500">
                  원하는 AI 모드를 선택하시거나 <br/>직접 키워드를 입력하시면<br/>이곳에 고품질 블로그 원고가 완성됩니다.
                </p>
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
