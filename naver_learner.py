import os
import re
import sys
import json
import urllib.parse
import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from dotenv import load_dotenv
from datetime import datetime

# 윈도우 환경 이모지 cp949 인코딩 에러 방지
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# 환경변수 로드
if not os.getenv('GITHUB_ACTIONS_ENV'):
    load_dotenv('.env.local')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if not GEMINI_API_KEY:
    print("오류: GEMINI_API_KEY가 없습니다.")
    sys.exit(1)

client = genai.Client(api_key=GEMINI_API_KEY)
KNOWLEDGE_FILE = 'naver_style_knowledge.json'

def search_naver_blogs(query):
    """네이버 통합 블로그 영역에서 검색어 기반 상위 3개 블로그 URL 수집"""
    encoded_query = urllib.parse.quote(query)
    # 최신 네이버 블로그 검색 탭 URL
    url = f"https://search.naver.com/search.naver?ssc=tab.blog.all&query={encoded_query}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    
    blog_urls = []
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # href 속성에서 blog.naver.com 링크 수집
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'blog.naver.com' in href and not any(x in href for x in ['MyBlog', 'CategoryList', 'admin', 'WriteForm']):
                # 일반 PC/모바일 포맷 파싱 및 PostView 규격으로 일원화
                match = re.search(r'https?://blog\.naver\.com/([a-zA-Z0-9_-]+)/([0-9]+)', href)
                if match:
                    normalized = f"https://blog.naver.com/PostView.naver?blogId={match.group(1)}&logNo={match.group(2)}"
                    if normalized not in blog_urls:
                        blog_urls.append(normalized)
                        
                match_m = re.search(r'https?://m\.blog\.naver\.com/([a-zA-Z0-9_-]+)/([0-9]+)', href)
                if match_m:
                    normalized = f"https://blog.naver.com/PostView.naver?blogId={match_m.group(1)}&logNo={match_m.group(2)}"
                    if normalized not in blog_urls:
                        blog_urls.append(normalized)
                        
            if len(blog_urls) >= 3:
                break
                
        return blog_urls
    except Exception as e:
        print(f"⚠️ 네이버 블로그 검색 오류 ({query}): {e}")
        return []

def fetch_blog_content(url):
    """네이버 스마트에디터 ONE (se-main-container) 본문 영역 크롤링 및 토큰 최적화용 스마트 정제"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        raw_text = ""
        container = soup.select_one('.se-main-container')
        if container:
            raw_text = container.get_text('\n', strip=True)
        else:
            post_content = soup.select_one('#postViewArea')
            if post_content:
                raw_text = post_content.get_text('\n', strip=True)
                
        if not raw_text:
            return ""
            
        # 1. 광고성 상투 문구 및 메타 영역 간이 필터링
        cleaned = re.sub(r'(서로이웃|서이추|공감|댓글|이웃환영|소정의 수수료|지원받아|포스팅입니다).*', '', raw_text, flags=re.IGNORECASE)
        # 2. 연속된 다중 개행 및 공백 정제
        cleaned = re.sub(r'\n+', '\n', cleaned)
        cleaned = re.sub(r' +', ' ', cleaned)
        cleaned = cleaned.strip()
        
        # 3. 토큰 최적화용 스마트 슬라이싱 (도입부 600자 + 결론부 600자 결합)
        if len(cleaned) > 1200:
            half = 600
            cleaned = cleaned[:half] + "\n[... 중간 내용 중략 ...]\n" + cleaned[-half:]
            
        return cleaned
    except Exception as e:
        print(f"⚠️ 본문 크롤링 오류 ({url}): {e}")
        return ""

def analyze_blog_styles(keyword, blog_contents):
    """Gemini 2.5 Flash를 활용한 상위 노출 블로그 작문 스타일 추출 및 SEO 분석 학습"""
    if not blog_contents:
        return "실제 이웃에게 대화하듯 질문을 던져 공감대를 형성하는 도입부 전략을 사용할 것. 정보 전달 단락에서는 핵심 혜택을 명확히 전달하고, 가독성을 극대화하기 위해 적절한 텍스트 강조 및 구조화된 단락 전개를 활용할 것."

    combined_text = ""
    for i, content in enumerate(blog_contents):
        combined_text += f"\n--- [상위 블로그 #{i+1} 본문 샘플] ---\n{content}\n"

    prompt = f"""
    당신은 네이버 뷰(VIEW) 영역 및 모바일 홈피드 추천 노출 알고리즘을 꿰뚫고 있는 국내 최고 권위의 블로그 SEO 엔지니어이자 마케팅 전문가입니다.
    아래는 현재 네이버 랭킹 상위에 노출되고 있는 고품질 활성 블로그들의 실제 본문 텍스트입니다.
    
    [벤치마킹 타겟 키워드]
    {keyword}
    
    [상위 노출 블로그 본문 수집 데이터]
    {combined_text}
    
    이 실제 글들을 정밀하게 관찰/분석하여, 당사 자동 포스팅 AI 봇의 글쓰기 프롬프트 지침(System Prompt)에 즉각 주입할 '네이버 상위 노출 실시간 스타일 가이드북'을 추출해 주세요.
    
    [🚨 치명적 작성 제약 조건 🚨]
    - 상세한 장문의 분석 레포트가 아닌, **AI 블로그 원고 작성 시 즉각 반영할 구체적 가이드라인(500자 내외)**으로 요약해 주세요.
    - 어조는 무조건 '~할 것', '~해야 함' 같은 직관적이고 행동을 지시하는 **'명령조/지침형 어조'**로 일원화해 주세요.
    - 예시: "도입부에서는 개인적인 생활 속 불편함을 질문 형식으로 던져 깊은 공감을 형성할 것. 본문에서는 소제목별로 핵심 정보를 비교 분석하는 HTML 표를 사용해 가독성을 대폭 끌어올릴 것. 말투는 이웃집 경제 삼촌처럼 따뜻하고 편안한 1인칭 시점을 철저히 고수할 것."
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3
            )
        )
        return response.text.strip()
    except Exception as e:
        print(f"⚠️ Gemini 벤치마크 학습 실패: {e}")
        return "실제 이웃에게 대화하듯 질문을 던져 공감대를 형성하는 도입부 전략을 사용할 것. 정보 전달 단락에서는 핵심 혜택을 명확히 전달하고, 가독성을 극대화하기 위해 적절한 텍스트 강조 및 구조화된 단락 전개를 활용할 것."

def run_learning(target_keyword="부동산 대책 DSR 대출 제한"):
    """자가 학습 프로세스 총괄 컨트롤러"""
    print(f"\n[학습 시작] 타겟 키워드: '{target_keyword}' 분석 진행 중...")
    
    # 1. 상위 블로그 URL 수집
    urls = search_naver_blogs(target_keyword)
    print(f"-> 발견된 상위 노출 블로그 링크 수: {len(urls)}개")
    for url in urls:
        print(f"   * {url}")
        
    # 2. 각 블로그 본문 크롤링
    contents = []
    for url in urls:
        content = fetch_blog_content(url)
        if content:
            contents.append(content)
            
    print(f"-> 본문 크롤링 완료 블로그 수: {len(contents)}개")
    
    # 3. Gemini 스타일 자가 학습 가이드 분석
    style_guide = analyze_blog_styles(target_keyword, contents)
    print("\n================== [네이버 상위 노출 자가 학습 결과] ==================")
    print(style_guide)
    print("=======================================================================\n")
    
    # 4. JSON 파일 저장
    knowledge_data = {
        "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "target_keyword": target_keyword,
        "style_guide": style_guide
    }
    
    with open(KNOWLEDGE_FILE, 'w', encoding='utf-8') as f:
        json.dump(knowledge_data, f, ensure_ascii=False, indent=2)
        
    print(f"-> 학습 지식 파일이 정상적으로 갱신되었습니다: {KNOWLEDGE_FILE}")
    return style_guide

if __name__ == "__main__":
    # 단독 실행 시 테스트용 키워드
    run_learning("부동산 DSR 대출 제한 긴급 정책")
