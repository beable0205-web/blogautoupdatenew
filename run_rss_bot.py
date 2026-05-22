import os
import sys
import time
import feedparser
import requests
import csv
import re
import random
import json
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google import genai
from google.genai import types
import datetime

load_dotenv(dotenv_path=".env.local")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("❌ 에러: .env.local 파일에 GEMINI_API_KEY가 없습니다.")
    sys.exit(1)

client = genai.Client(api_key=GEMINI_API_KEY)

# RSS Feeds to monitor
FEEDS = {
    'health': {
        'name': '복지/보건 보도자료 (대한민국 정책브리핑)',
        'url': 'https://www.korea.kr/rss/welfare.xml',
        'persona': 'health'
    },
    'economy': {
         'name': '경제 보도자료 (대한민국 정책브리핑)',
         'url': 'https://www.korea.kr/rss/economy.xml',
         'persona': 'economy'
    }
}

# HTML 마크업 코드 유사도 필터 회피용 Shuffler 구현
def randomize_html_styles(html):
    def get_random_p_style():
        font_sizes = ['15px', '16px', '17px']
        line_heights = ['1.65', '1.7', '1.75', '1.8', '1.85', '1.9']
        margins = ['20px', '22px', '24px', '26px', '28px', '30px']
        colors = ['#333333', '#222222', '#444444', '#1e293b', '#0f172a']
        letter_spacings = ['-0.3px', '-0.5px', '-0.4px', 'normal']

        size = random.choice(font_sizes)
        height = random.choice(line_heights)
        margin = random.choice(margins)
        color = random.choice(colors)
        ls = random.choice(letter_spacings)

        props = [
            f"font-size: {size}",
            f"line-height: {height}",
            f"margin-bottom: {margin}",
            f"color: {color}",
            f"letter-spacing: {ls}"
        ]
        
        random.shuffle(props)
        return f"style='{'; '.join(props)};'"

    def get_random_h2_style():
        font_sizes = ['22px', '23px', '24px', '25px']
        weights = ['700', '800', '900']
        colors = ['#111111', '#0f172a', '#1e293b', '#2d3748']
        border_colors = ['#111111', '#00c73c', '#0066ff', '#ff9900', '#DB2777', '#8B5CF6', '#10B981']
        
        size = random.choice(font_sizes)
        weight = random.choice(weights)
        color = random.choice(colors)
        border_c = random.choice(border_colors)

        props = [
            f"font-size: {size}",
            f"font-weight: {weight}",
            f"color: {color}",
            f"margin-top: {50 + random.randint(0, 24)}px",
            f"margin-bottom: {20 + random.randint(0, 9)}px",
            "padding-bottom: 10px",
            f"border-bottom: 2px solid {border_c}"
        ]
        
        random.shuffle(props)
        return f"style='{'; '.join(props)};'"

    def get_random_h3_style():
        font_sizes = ['18px', '19px', '20px', '21px']
        weights = ['700', '800']
        colors = ['#333333', '#1e293b', '#2d3748', '#4a5568']
        border_colors = ['#00c73c', '#0066ff', '#ff9900', '#DB2777', '#8B5CF6', '#10B981']
        
        size = random.choice(font_sizes)
        weight = random.choice(weights)
        color = random.choice(colors)
        border_c = random.choice(border_colors)

        props = [
            f"font-size: {size}",
            f"font-weight: {weight}",
            f"color: {color}",
            f"margin-top: {40 + random.randint(0, 24)}px",
            f"margin-bottom: {15 + random.randint(0, 9)}px",
            "padding-left: 14px",
            f"border-left: 4px solid {border_c}"
        ]
        
        random.shuffle(props)
        return f"style='{'; '.join(props)};'"

    processed = html

    # 인라인 스타일 패턴 매칭 및 교체
    processed = re.sub(r"<p\s+style=['\"][^'\"]*['\"]>", lambda m: f"<p {get_random_p_style()}>", processed, flags=re.IGNORECASE)
    processed = re.sub(r"<h2\s+style=['\"][^'\"]*['\"]>", lambda m: f"<h2 {get_random_h2_style()}>", processed, flags=re.IGNORECASE)
    processed = re.sub(r"<h3\s+style=['\"][^'\"]*['\"]>", lambda m: f"<h3 {get_random_h3_style()}>", processed, flags=re.IGNORECASE)

    # </p> 태그 뒤에 무작위 해시 주석 추가
    def add_hash(match):
        random_hash = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=6))
        return f"<!-- hash_{random_hash} --></p>"

    processed = re.sub(r"</p>", add_hash, processed, flags=re.IGNORECASE)

    return processed

def fetch_pixabay_images(primary, fallback, api_key):
    if not api_key:
        return []
    
    def fetch_images_by_query(query, limit):
        url = f"https://pixabay.com/api/?key={api_key}&q={requests.utils.quote(query)}&image_type=photo&orientation=horizontal&safesearch=true&per_page=15"
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                hits = data.get('hits', [])
                if hits:
                    random.shuffle(hits)
                    return [hit.get('webformatURL') for hit in hits[:limit]]
        except Exception as e:
            print(f"⚠️ Pixabay 이미지 검색 에러 ({query}): {e}")
        return []

    found_images = fetch_images_by_query(primary, 4)
    if len(found_images) < 4:
        fallback_images = fetch_images_by_query(fallback, 4 - len(found_images))
        found_images.extend(fallback_images)
    if len(found_images) < 4:
        safe_images = fetch_images_by_query('nature', 4 - len(found_images))
        found_images.extend(safe_images)
    return found_images

def extract_text_from_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    return soup.get_text(separator=' ', strip=True)

def generate_blog_post(title, summary, link, persona):
    print(f"[{title}] AI 블로그 초안 생성 중... (페르소나: {persona})")
    
    # 1. 썸네일 추출 및 카피라이팅을 위한 Gemini 1차 호출
    keyword_guidance = "추상적인 개념일 경우 서양인 사무실 사진이 나오지 않도록 시각적으로 직관적이고 상징적인 사물/풍경 '한글 단어'를 명사형태로 선택하세요."
    
    translate_prompt = f"""당신은 검색어에서 가장 핵심적이고 시각적인 이미지를 추출하는 프롬프트 엔지니어입니다. 
    사용자가 입력한 검색어에 가장 찰떡같이 어울리는 고품질 사진을 찾기 위해, 명확한 단어를 추출하세요.
    {keyword_guidance}

    1. primary: 검색어를 가장 잘 표현하는 구체적이고 감각적인 한글 단어 1~2개
    2. fallback: primary 검색 실패 시 사용할, 검색어의 상위 카테고리에 해당하는 매우 포괄적이고 중립적인 한글 단어 1~2개
    3. englishSubject: 이 주제를 그림으로 그릴 때 메인 피사체가 될 만한 구체적인 영단어 2~3개
    
    [🔥 초강력 어그로/후킹 썸네일 카피라이팅 지침 🔥]
    4, 5, 6번 썸네일 문구는 네이버 메인 홈판에서 무조건 클릭하고 싶게 만드는 도발적인 극한의 카피라이팅이어야 합니다.
    4. thumbnailTop: 상단 해시태그용 어그로 문구 (예: #안보면손해 #수백만원절약 #1퍼센트만아는비밀) - 띄어쓰기 없이 해시태그로 3개 작성 (15자 이내)
    5. thumbnailMid: 썸네일 중앙 핵심 주제 (예: 청년미래적금, 숨은 정부지원금, 블로그 수익화) - 8자 이내 명사형태
    6. thumbnailBottom: 손실 회피 및 호기심을 극도로 자극하는 하단 문구 (예: 지금 당장 신청하세요!, 99%가 놓치는 꿀팁, 모르면 평생 후회) - 13자 이내
    
    예시:
    "블로그 썸네일 만들기" -> {{"primary": "디자인", "fallback": "컴퓨터", "englishSubject": "designing on computer", "thumbnailTop": "#조회수폭발 #인플루언서비밀", "thumbnailMid": "썸네일 꿀팁", "thumbnailBottom": "안 보면 무조건 손해!"}}
    "삼성전자 주가방향" -> {{"primary": "주식 차트", "fallback": "금융", "englishSubject": "stock market chart rising", "thumbnailTop": "#개미투자자 #무조건필독", "thumbnailMid": "삼성전자 주가", "thumbnailBottom": "지금이 마지막 기회일까?"}}

    반드시 아래 JSON 형식으로만 응답하세요. 다른 문장 부호나 설명은 절대 붙이지 마세요.
    {{"primary": "...", "fallback": "...", "englishSubject": "...", "thumbnailTop": "...", "thumbnailMid": "...", "thumbnailBottom": "..."}}
    
    사용자 검색어: {title}"""

    search_params = {
        "primary": "복지 혜택",
        "fallback": "한국 복지",
        "englishSubject": "welfare benefits",
        "thumbnailTop": "오늘의 핵심 정보",
        "thumbnailMid": title[:8] if len(title) > 8 else title,
        "thumbnailBottom": "지금 바로 확인!"
    }
    
    try:
        models_thumbnail = ['gemini-3.5-flash', 'gemini-2.5-pro', 'gemini-2.5-flash']
        init_res = None
        for model_name in models_thumbnail:
            try:
                init_res = client.models.generate_content(
                    model=model_name,
                    contents=translate_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        response_mime_type="application/json"
                    )
                )
                break
            except Exception as e:
                print(f"⚠️ 썸네일 추출 중 {model_name} 실패, 다음 우회: {e}")
                
        if init_res:
            json_str = init_res.text.strip()
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
            search_params = json.loads(json_str.strip())
    except Exception as e:
        print(f"⚠️ 썸네일 파라미터 1차 추출 최종 실패, 기본값 사용: {e}")

    PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY")
    image_urls = []
    if PIXABAY_API_KEY:
        image_urls = fetch_pixabay_images(search_params.get('primary', '사무실'), search_params.get('fallback', '비즈니스'), PIXABAY_API_KEY)
        
    base_url = os.environ.get("BASE_URL", "http://localhost:3000")
    thumbnail_html = ""
    try:
        top_params = requests.utils.quote(search_params.get('thumbnailTop', '#정보공유 #필수지식'))
        mid_params = requests.utils.quote(search_params.get('thumbnailMid', title[:8] if len(title) > 8 else title))
        bottom_params = requests.utils.quote(search_params.get('thumbnailBottom', '지금 확인하세요!'))
        style_param = f"&style={persona}" if persona else ""
        bg_param = f"&bg={requests.utils.quote(image_urls[0])}" if image_urls else ""
        
        og_url = f"{base_url}/api/og?top={top_params}&mid={mid_params}&bottom={bottom_params}{style_param}{bg_param}&ext=.png"
        
        thumbnail_html = f"""<div style="text-align: center; margin-bottom: 24px;">
  <img src="{og_url}" alt="대표 썸네일" style="max-width: 100%; height: auto; border-radius: 12px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -2px rgba(0,0,0,0.05);" />
</div>"""
    except Exception as e:
        print(f"⚠️ 썸네일 이미지 URL 생성 실패: {e}")

    # 2. 페르소나별 가이드
    personaGuidance = ""
    if persona == 'health':
        personaGuidance = """
당신은 대한민국 네이버 블로그 생태계를 완벽하게 이해하고 있으며, 정부 보도자료를 5060 시각에서 '나도 받을 수 있나?'라는 관점으로 풀어서 설명하는 복지 전문가 일명 **'지원금 마스터 (김쌤)'**입니다.
이 블로그의 핵심 콘셉트는 "복잡한 정부 혜택, 내 지갑 속으로 쏙 들어오게!" 입니다. 제공된 뉴스/보도자료를 바탕으로 정보성 블로그 글을 작성해주세요.
홈판(홈피드)에 오르는 글들의 공통점은 철저하게 **"진정성 있는 1인칭 체험 및 스토리텔링"**이라는 점입니다. 당신이 직접 겪은 이야기나, 이웃을 위해 발벗고 나서서 직접 알아본 생생한 스토리처럼 작성하세요.

[🚨 네이버 상위 1% 홈판 최적화 1인칭 작성 가이드]
- "안녕하세요! 오늘의 꿀정보 전달자 김쌤입니다." 로봇 같은 인사말은 피하세요.
- 매번 도입부 문장의 스타일을 완전히 바꾸어, 독특한 1인칭 일상 경험담("제가 얼마 전에 세무서에 볼일이 있어 갔다가...", "요즘 장보러 갈 때마다 한숨만 나오시죠? 저도 마트 갈 때마다 깜짝깜짝 놀랍니다...")으로 흥미를 당기며 시작하세요.
- 친근하고 따뜻한 반말과 존댓말의 적절한 조합, 대화하듯 다정한 감성 터치를 본문 내내 유지하세요.
- 친절한 존댓말("~지원받을 수 있어요", "~입니다", "~준비하셨나요?")을 주로 사용하며, 약간의 이모티콘(💰, 📝, 🎁, 😊)을 가미하세요.

2. 내용 전개 방식 및 데이터:
   - [필수 정보 출처]: 제공된 기사 내용을 100% 신뢰할 수 있는 공식 데이터라고 가정하고 작성하세요. 대상자(연령, 소득 수준)와 신청 기한(날짜)을 최우선으로 정확하게 짚어서 알려줍니다.
   - [오프닝]: <blockquote> 태그를 사용해 최신 소식을 언급하며 따뜻한 조언으로 출발합니다.
   - [시각화]: 반드시 중요 정보(지원 대상, 제출 서류 등)를 HTML <table> 태그를 사용하여 표 1개 이상으로 정리하세요. (마크다운 표 금지. 오직 HTML <table>, <tr>, <th>, <td>와 인라인 CSS 사용. 테두리나 배경색 등 무작위화 적용)
   - [마무리 및 브랜딩 다각화]: "공식 홈페이지(복지로, 보조금24 등)에서 최종 공고를 꼭 재확인해 보시길 권해드립니다. 지금까지 5060 시니어분들의 든든한 혜택 길잡이, 김쌤이었습니다!" 등과 같은 핵심 가치를 내포한 맺음말을 매번 다른 어조와 단어로 다채롭게 지어내어 작성하십시오. (고정된 템플릿 문구 절대 금지)

해시태그: 맨 마지막에 글 주제와 어울리는 4~6개의 태그(예: #정부지원금, #복지혜택, #시니어혜택, #복지제도 등)를 완전 무작위하고 고유하게 띄어쓰기로 나열해 생성하세요. (정형화된 하나의 해시태그 목록을 매 글마다 반복 출력하면 유사문서 필터에 걸려 누락되므로 절대 금지합니다.)
"""
    elif persona == 'economy':
        personaGuidance = """
당신은 은퇴 설계 분야의 일타 강사이자, 시니어들의 생활비와 절세를 지켜드리는 일명 **'은퇴 경제 전문가 (김쌤)'**입니다.
이 블로그의 모토는 "은퇴는 끝이 아닌 새로운 시작입니다." 입니다. 제공된 뉴스를 보고 복잡한 연금, 건보료 등 노후 돈 문제를 속 시원하게 파헤치는 정보성 블로그 글을 작성해주세요.
홈판(홈피드)에 오르는 글들의 공통점은 철저하게 **"진정성 있는 1인칭 체험 및 스토리텔링"**이라는 점입니다. 당신이 직접 겪은 이야기나, 이웃을 위해 발벗고 나서서 직접 알아본 생생한 스토리처럼 작성하세요.

[🚨 네이버 상위 1% 홈판 최적화 1인칭 작성 가이드]
- "안녕하세요! 오늘의 꿀정보 전달자 김쌤입니다." 로봇 같은 인사말은 피하세요.
- 매번 도입부 문장의 스타일을 완전히 바꾸어, 독특한 1인칭 일상 경험담("제가 얼마 전에 은행에 들러서 상품을 문의하다가...", "요즘 세금 통지서 볼 때마다 가슴이 덜컥 내려앉으시죠? 저도 마찬가지입니다...")으로 흥미를 당기며 시작하세요.
- 친근하고 따뜻한 반말과 존댓말의 적절한 조합, 대화하듯 다정한 감성 터치를 본문 내내 유지하세요.
- 감성팔이보다는 완전한 **[팩트, 숫자, 실용성]** 중심으로 이성적이고 스마트하게 서술합니다. ("~라는 사실, 알고 계셨습니까?", "~가 핵심입니다", "~꼭 기억하십시오.")
- 전문적인 세무/건보료 지식을 예리하게 분석하되, 실생활에 적용할 수 있게 사례(예: 건보료 피부양자 자격 박탈 기준 등)를 들어 쉽게 설명합니다. 강조 표시기호(✅, 📌, 💡, 💰)를 적절히 사용합니다.

2. 내용 전개 방식 및 데이터:
   - [필수 정보 출처]: 제공된 기사 내용을 100% 신뢰할 수 있는 국민연금, 건보공단, 금감원, 국세청 등의 공식 데이터라고 가정하고 작성하세요.
   - [오프닝]: <blockquote> 태그를 사용해 불안 요소나 화두를 팩트로 콕 짚어 던집니다.
   - [본론 솔루션]: 추상적 위로가 아니라 팩트를 검증해야 합니다. 제도를 비교하거나 계산해야 할 내용을 HTML <table> 태그로 시각화하세요. (마크다운 표 금지)
   - [마무리 및 브랜딩 다각화]: "아는 만큼 지키고 불릴 수 있습니다. 오늘도 치밀하게 준비하시어 은퇴 후 품격 있는 삶을 만드시길 바랍니다. 은퇴 경제 동반자 김쌤이었습니다!" 등과 같은 핵심 가치를 내포한 끝맺음을 매번 고유하고 새로운 형식의 문장으로 직접 작성하십시오. (동일 문구 반복 절대 금지)

해시태그: 맨 마지막에 글 내용에 가장 잘 어울리는 경제 및 은퇴 태그 4~6개(예: #시니어경제, #은퇴준비, #노후대비, #국민연금 등)를 매번 완전히 다르고 불규칙하게 선정하여 띄어쓰기로 작성하세요. (유사문서 회피용 패턴 타파 필수)
"""
    elif persona == 'brandconnect':
        personaGuidance = """
당신은 대한민국 5060 시니어들에게 "내 돈 주고 사긴 아깝고 남이 사주면 좋은 물건", "살면서 꼭 필요한 프리미엄 가성비템"을 족집게처럼 골라주는 '가성비 꿀템 리뷰어 (김쌤)'입니다.
이 블로그의 모토는 "광고인듯 광고아닌, 진짜 우리 삶의 질을 높여주는 정보" 입니다. 주어진 상품명과 소구포인트를 바탕으로 구매율(전환율)이 폭발하는 브랜드 커넥트 제휴 마케팅 글을 작성해주세요.
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

해시태그: 맨 마지막에 상품 종류와 문맥에 완전히 부합하는 태그 4~6개(예: #부모님선물 #가성비꿀템 #생활꿀팁 등)를 다양하게 조합해 띄어쓰기로 생성하십시오.
"""
    
    current_year = datetime.datetime.now().year

    prompt = f"""
{personaGuidance}

[입력 정보]
- 뉴스 제목: {title}
- 핵심 내용 요약: {summary}
- 원본 링크: {link}
- 작성 기준 연도: 무조건 {current_year}년 (절대로 과거 연도를 출력하지 마세요. 모든 정책과 혜택은 {current_year}년 기준입니다.)

[공통 필수 준수 가이드]
1. 분량과 깊이: 공백 제외 800자 ~ 1,000자. 모바일 최적화. 서론 직후에 [THUMBNAIL] 단 1번 작성.
2. 클릭을 유도하는 강력한 유튜브/네이버 메인 스타일 제목 (Title) 작성 (매우 중요!!!):
   - 길이 및 레이아웃: 모바일에서 잘리지 않도록 반드시 25자 이내로 작성하세요.
   - 배치: 핵심 목표 키워드는 무조건 제목의 가장 앞부분(좌측) 배치하여 검색 노출을 극대화하세요.
   - 문장 구조: 구체적인 숫자(예: 10분 만에, 5천만 원, 90% 지원)를 포함하여 호기심과 이득을 직관적으로 제시하세요.
   - 예시: "[지원금] 5060 건보료 10만 원 아끼는 3가지 비밀" 처럼 쓰세요.
3. 가독성을 극대화하는 세련된 구조 (마크다운 절대 금지, 100% HTML 태그 작성):
   - 문단 길이 및 줄바꿈: 2~3문장마다 반드시 문단을 나누고, 본문의 모든 일반 텍스트는 <p style='font-size: 16px; line-height: 1.8; margin-bottom: 26px; color: #333; letter-spacing: -0.5px;'>...</p> 태그로 감싸서 아주 읽기 편하게 만드세요.
   - 표(Table) 작성 규칙: 마크다운 문법( |---| )은 화면이 깨지므로 절대 쓰지 마세요!! 표가 필요할 때는 반드시 HTML <table> <tr> <th> <td> 태그를 사용하고, style 속성으로 테두리(border: 1px solid #ddd; border-collapse: collapse; padding: 12px; text-align: left;)를 명시하세요. <th>에는 배경색(background-color: #f8f9fa;)도 넣으세요.
   - 소제목 계층화 (필수): 대주제와 소주제는 글의 흐름이 자연스럽게 이어지도록 직관적으로 작성하고, 아래의 세련된 인라인 스타일을 사용하되, 테두리(border)나 포인트 강조 색상은 주제 분위기에 맞춰 다양하게 변경하여 단조로운 패턴을 회피하세요. (예: IT/금융은 `#0066ff` 또는 `#00c73c`, 일상/리뷰는 `#ff9900` 등 자유롭게 선택)
     대주제 예시: <h2 style='font-size: 24px; font-weight: 800; color: #111; margin-top: 70px; margin-bottom: 25px; padding-bottom: 10px; border-bottom: 2px solid #111;'>1. 대주제 타이틀</h2>
     소주제 예시: <h3 style='font-size: 20px; font-weight: 700; color: #333; margin-top: 60px; margin-bottom: 20px; padding-left: 14px; border-left: 4px solid #00c73c;'>1.1. 소주제 타이틀</h3>
   - HTML 태그에 속성을 넣을 때는 큰따옴표(") 대신 반드시 홑따옴표(')를 사용하세요.
4. [🚨 할루시네이션(거짓정보) 방지 규칙 🚨]
   - 제공된 '입력 정보(요약 및 링크)'에 기반해서만 작성하세요. 입력 정보에 없는 구체적인 예산, 지급일, 정확한 금리 등을 AI 마음대로 지어내서 적으면 블로그가 영구 정지됩니다. 모르는 수치는 "공식 홈페이지 참조" 등으로 안내하세요.
5. [🚨 치명적 발자국 회피: 면책 조항(Disclaimer)의 100% 무작위 동적 생성 🚨]
   - 글의 맨 마지막(결론 및 해시태그 바로 위)에는 법적/운영적 책임 방지를 위해 반드시 정보 공유 목적의 면책 조항을 작성해야 합니다.
   - 주의: 모든 글에 똑같은 단어나 템플릿의 면책 조항이 반복 삽입되면 네이버 유사문서 알고리즘에 의해 블로그 전체가 즉시 검색 차단(통누락)됩니다!
   - 따라서 아래의 핵심 의도(정보 전달 목적, 정책 및 기준 변동 가능성, 최종 확인 권장)를 포함하되, 매번 완전히 다른 문장 구조, 어휘, 배치 순서로 새로운 2~3문장의 면책 조항을 자연스럽게 직접 지어내어 <p style='font-size: 13px; color: #888; text-align: center; line-height: 1.6;'><b>🚨 [팩트체크 및 면책고지]</b><br>...</p> 태그 형식으로 생성하십시오.
   - 창작 예시:
     - "본 포스팅은 언론 보도와 공식 보도자료를 기반으로 독자들의 이해를 돕기 위해 작성되었습니다. 시점과 주관 기관의 세부 정책 변화에 따라 실제 혜택 요건이 상이할 수 있으므로, 최종 신청 전에 필히 관할 처의 공식 공고를 교차 검증하시기 바랍니다."
     - "신뢰할 수 있는 공시 자료를 취합하여 정리했으나, 정책 변경이나 예산 한도 소진 등으로 세부 정보가 예고 없이 변경될 수 있습니다. 정확한 가입 조건은 반드시 주관사 공식 채널을 통해 마지막으로 확인해 주세요."
     - "이 글은 유용한 정보 전달을 목적으로 쓰인 개인 의견입니다. 구체적인 지급일이나 심사 기준 등은 변동 사항이 잦으므로, 모든 신청 및 계약 진행 전에 공식 사이트의 최신 안내를 반드시 검토하시는 것을 권장합니다."

[출력 형식 제한]
반드시 아래 특수 구분자를 사용하세요.
[TITLE]
(생성된 블로그 제목 한 줄)
[/TITLE]
[CONTENT]
(생성된 블로그 본문 HTML)
[/CONTENT]
"""

    try:
        models_content = ['gemini-3.5-flash', 'gemini-2.5-pro', 'gemini-2.5-flash']
        response = None
        last_content_err = None
        
        for model_name in models_content:
            try:
                try:
                    config = types.GenerateContentConfig(
                        system_instruction="당신은 블로그 포스팅 작가를 돕는 보조 AI입니다. 구글 검색 결과를 통해 팩트를 체크하되, 절대로 검색 결과의 원본 데이터(JSON이나 파이썬 딕셔너리 구조, {'title': ...})를 사용자에게 그대로 노출하거나 본문에 출력하지 마세요. 오직 깔끔하게 다듬어진 블로그 [CONTENT] 텍스트만 출력해야 합니다.",
                        tools=[types.Tool(google_search=types.GoogleSearch())]
                    )
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config
                    )
                    break
                except Exception as search_err:
                    print(f"⚠️ {model_name} google_search 장착 실패로 툴 없이 재시도합니다: {search_err}")
                    config = types.GenerateContentConfig(
                        system_instruction="당신은 블로그 포스팅 작가를 돕는 보조 AI입니다. 절대로 검색 결과의 원본 데이터(JSON이나 파이썬 딕셔너리 구조)를 사용자에게 그대로 노출하거나 본문에 출력하지 마세요. 오직 깔끔하게 다듬어진 블로그 [CONTENT] 텍스트만 출력해야 합니다."
                    )
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config
                    )
                    break
            except Exception as e:
                print(f"⚠️ {model_name} 본문 생성 실패, 다음 우회: {e}")
                last_content_err = e

        if not response:
            raise last_content_err if last_content_err else Exception("본문 생성 최종 실패")
            
        full_text = response.text
        
        # 포스트 프로세싱 & HTML 스타일 셔플링
        processed_text = full_text
        content_match = re.search(r"([\s\S]*?)\[CONTENT\]([\s\S]*?)\[/CONTENT\]", full_text, re.IGNORECASE)
        
        if content_match:
            before_content = content_match.group(1)
            content_body = content_match.group(2)
            
            # HTML 스타일 셔플링 적용!
            randomized_body = randomize_html_styles(content_body)
            
            # [제휴마케팅 저품질 회피용 댓글 우회 및 인젝션 꿀팁 적용]
            if persona == 'brandconnect' and link:
                # 50% 확률로 본문 내 직접 링크를 댓글 유도 CTA로 변환
                if random.random() < 0.5:
                    comment_ctas = [
                        "이벤트 혜택이 언제 종료될지 모르니 일단 확인부터 해보세요!\n\n💡 <b>[최저가 및 추가 혜택 링크는 첫 번째 댓글에 고정해 두었습니다! 확인해 보세요 😊]</b>",
                        "한정 수량이니 늦지 않게 확인해 보시길 권해드려요.\n\n📌 <b>[공식 최저가 혜택 바로가기 링크는 첫 번째 댓글에 남겨 놓았습니다!]</b>",
                        "워낙 인기가 많아 금방 품절될 수 있으니 서두르세요!\n\n✔ <b>[상세 정보와 10% 추가할인 링크는 댓글창의 첫 번째 댓글을 참고해 주세요!]</b>"
                    ]
                    chosen_cta = random.choice(comment_ctas)
                    if link in randomized_body:
                        randomized_body = randomized_body.replace(link, chosen_cta)
                    else:
                        randomized_body += f"\n\n<p style='font-size: 16px; text-align: center; color: #1e293b;'>{chosen_cta}</p>"
                    
                    randomized_body += f"\n\n<!-- [🚨네이버 저품질 방지 우회] 첫댓글 삽입용 제휴 링크 주소: {link} -->"
            
            # [THUMBNAIL] 예약어 치환
            if "[THUMBNAIL]" in randomized_body:
                randomized_body = randomized_body.replace("[THUMBNAIL]", thumbnail_html)
            else:
                randomized_body = thumbnail_html + "\n" + randomized_body
                
            # [IMAGE_1], [IMAGE_2], [IMAGE_3] 예약어 치환
            for idx, img_url in enumerate(image_urls[1:4], start=1):
                img_tag = f"""<div style="text-align: center; margin-top: 24px; margin-bottom: 24px;">
  <img src="{img_url}" alt="본문 이미지 {idx}" style="max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);" />
</div>"""
                randomized_body = randomized_body.replace(f"[IMAGE_{idx}]", img_tag)
                
            processed_text = f"{before_content}[CONTENT]\n{randomized_body}\n[/CONTENT]"
            
        return processed_text
    except Exception as e:
        print(f"Gemini API 오류: {e}")
        return None


def process_feeds():
    os.makedirs('outputs', exist_ok=True)
    
    # 윈도우 한글 깨짐 방지
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
        
    print("="*50)
    print("🤖 김쌤의 RSS 자동 포스팅 봇 가동 (최신 보도자료 읽기)")
    print("="*50)
    
    for feed_id, config in FEEDS.items():
        print(f"\n📡 피드 스크래핑 중: {config['name']} ({config['url']})")
        
        try:
            feed = feedparser.parse(config['url'])
            
            if not feed.entries:
                print("새로운 공고/보도자료가 없습니다.")
                continue
                
            # 가장 최신 보도자료 1개만 처리 (과도한 API 호출 방지 및 테스트용)
            latest_entry = feed.entries[0]
            
            title = latest_entry.title
            link = latest_entry.link
            
            # 요약문 또는 본문 추출 (보통 RSS는 summary에 들어있음)
            summary_html = latest_entry.get('summary') or latest_entry.get('description') or ""
            clean_summary = extract_text_from_html(summary_html)
            
            print(f"✅ 최신 뉴스 감지: {title}")
            
            # AI 블로그 글 생성
            result_text = generate_blog_post(title, clean_summary, link, config['persona'])
            
            if result_text:
                # 결과물 파일 저장 (특수문자 제거)
                timestamp = int(time.time())
                safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
                filename = f"outputs/RSS_{config['persona']}_{safe_title[:20]}_{timestamp}.md"
                
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"원본 소스(공식 발표자료): {link}\n\n")
                    f.write(result_text)
                    
                print(f"💖 포스팅 생성 완료! 저장 위치: {filename}")
            else:
                print("❌ 콘텐츠 생성 실패")
                
        except Exception as e:
            print(f"피드 처리 에러 ({config['name']}): {e}")

def process_brandconnect_csv():
    os.makedirs('outputs', exist_ok=True)
    csv_file = 'brandconnect_products.csv'
    if not os.path.exists(csv_file):
        print("❌ 브랜드 커넥트 CSV 파일이 없습니다. 건너뜁니다.")
        return

    rows = []
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    
    # 찾기: 상태가 "대기"인 첫 번째 상품
    target_idx = -1
    for i, row in enumerate(rows):
        if row.get('상태', '').strip() == '대기':
            target_idx = i
            break
            
    if target_idx == -1:
        print("ℹ️ 대기 중인 브랜드 커넥트 상품이 없습니다.")
        return
        
    product = rows[target_idx]
    product_name = product.get('상품명', '이름없는상품')
    points = product.get('소구포인트', '')
    aff_link = product.get('제휴링크', '')
    
    print(f"\n🛍️ 브랜드 커넥트 상품 감지: {product_name}")
    
    # generate_blog_post 호출 전에 브랜드 커넥트용 persona 추가
    result_text = generate_blog_post(product_name, f"소구포인트: {points}", aff_link, 'brandconnect')
    
    if result_text:
        timestamp = int(time.time())
        safe_title = "".join([c for c in product_name if c.isalpha() or c.isdigit() or c==' ']).rstrip()
        filename = f"outputs/BrandConnect_{safe_title[:20]}_{timestamp}.md"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"원본 소스(공식 발표자료 및 제휴링크): {aff_link}\n\n")
            f.write(result_text)
            
        print(f"💖 브랜드 커넥트 포스팅 생성 완료! 저장 위치: {filename}")
        
        # 상태 업데이트
        rows[target_idx]['상태'] = '완료'
        
        # 파일 덮어쓰기
        with open(csv_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=reader.fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            
    else:
        print("❌ 브랜드 커넥트 콘텐츠 생성 실패")


def process_trends_csv():
    os.makedirs('outputs', exist_ok=True)
    csv_file = 'collected_trends.csv'
    if not os.path.exists(csv_file):
        print("❌ 실시간 트렌드 CSV 파일이 없습니다. 건너뜁니다.")
        return

    rows = []
    # UTF-8 with BOM 대응을 위해 utf-8-sig 사용
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)
            
    if not rows:
        print("ℹ️ 수집된 실시간 트렌드가 없습니다.")
        return

    # '상태' 컬럼이 없는 기존 행을 대비해 채워줌
    for row in rows:
        if '상태' not in row:
            row['상태'] = '완료'

    # 상태가 "대기"인 첫 번째 트렌드 키워드 찾기
    target_idx = -1
    for i, row in enumerate(rows):
        if row.get('상태', '').strip() == '대기':
            target_idx = i
            break

    if target_idx == -1:
        print("ℹ️ 대기 중인 실시간 트렌드 키워드가 없습니다.")
        return

    trend = rows[target_idx]
    raw_title = trend.get('title', '')
    category = trend.get('category', '도파민/이슈')
    
    # 타이틀에서 "[검색량: xxx회]" 부분 정규식으로 정제
    clean_keyword = re.sub(r'\[검색량:\s*[\d,]+회\]', '', raw_title).strip()
    
    print(f"\n⚡ 실시간 황금 트렌드 포스팅 시작: {clean_keyword} (카테고리: {category})")
    
    # 카테고리에 맞춰 페르소나 매핑
    persona = 'economy'
    if category in ['보조금/지원금/복지', '연금/시니어']:
        persona = 'health'
    elif category in ['예적금/특판', '부동산/청약', '세금/절세', '주식/비트코인 한탕주의']:
        persona = 'economy'
    else:
        persona = 'health'

    # 구글 실시간 검색 팩트체크를 유도하며 글 작성
    result_text = generate_blog_post(clean_keyword, f"주제: {clean_keyword}에 관하여 최신 실시간 이슈와 핵심 팩트 정보를 분석하여 작성하세요. 구글 검색을 적극 활용해야 합니다.", "https://search.naver.com", persona)
    
    if result_text:
        timestamp = int(time.time())
        safe_title = "".join([c for c in clean_keyword if c.isalpha() or c.isdigit() or c==' ']).rstrip()
        filename = f"outputs/Trend_{category.replace('/', '_')}_{safe_title[:20]}_{timestamp}.md"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"원본 키워드 소스: {raw_title}\n")
            f.write(f"분류 카테고리: {category}\n\n")
            f.write(result_text)
            
        print(f"💖 실시간 트렌드 자동 포스팅 완료! 저장 위치: {filename}")
        
        # 상태 업데이트
        rows[target_idx]['상태'] = '완료'
        
        # CSV 파일 업데이트
        if fieldnames and '상태' not in fieldnames:
            fieldnames = list(fieldnames) + ['상태']
            
        with open(csv_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    else:
        print("❌ 실시간 트렌드 콘텐츠 생성 실패")


if __name__ == "__main__":
    process_feeds()
    print("="*50)
    process_brandconnect_csv()
    print("="*50)
    process_trends_csv()
    print("="*50)
