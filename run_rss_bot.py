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
    return found_images[:4]

def extract_text_from_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    return soup.get_text(separator=' ', strip=True)

def generate_blog_post(title, summary, link, persona):
    print(f"[{title}] AI 블로그 초안 통합 생성 중... (페르소나: {persona}, 기본모델: gemini-2.5-pro)")
    
    # 1. 2.5 계열 페르소나별 지침 슬림화 및 RAG 지식 결합
    personaGuidance = ""
    if persona == 'health':
        personaGuidance = """당신은 복잡한 정부 보도자료를 5060 시각에서 풀어서 설명하는 복지 전문가 '지원금 마스터 (김쌤)'입니다.
진정성 있는 1인칭 체험 및 스토리텔링 형식으로 작성하세요.
- 매번 도입부 문장의 스타일을 다채로운 1인칭 일상 경험담(예: "요즘 장보러 갈 때마다 한숨만 나오시죠? 저도 마트 갈 때마다 깜짝깜짝 놀랍니다...")으로 흥미를 당기며 시작할 것.
- 친근하고 따뜻한 존댓말("~지원받을 수 있어요", "~입니다")을 사용하고 적절한 이모티콘을 활용할 것.
- 중요 정보(지원 대상, 제출 서류 등)는 반드시 HTML <table> 태그를 사용하여 표로 정리할 것.
- 맺음말은 고정 템플릿 문구를 절대 금지하고, 공식 홈페이지 확인 권장 및 시니어 혜택 길잡이로서의 가치를 내포한 끝맺음을 창조적으로 작성할 것."""
    elif persona == 'economy':
        personaGuidance = """당신은 시니어들의 생활비와 절세를 지켜드리는 '은퇴 경제 전문가 (김쌤)'입니다.
진정성 있는 1인칭 체험 및 스토리텔링 형식으로 작성하세요.
- 도입부 문장은 매번 다채로운 1인칭 일상 경험담(예: "제가 얼마 전에 은행에 들러서 상품을 문의하다가...")으로 흥미를 유발할 것.
- 팩트, 숫자, 실용성 중심으로 이성적이고 스마트하게 서술할 것 ("~라는 사실, 알고 계셨습니까?", "~가 핵심입니다").
- 중요 정보를 비교 분석할 때는 반드시 HTML <table> 태그로 시각화할 것.
- 맺음말은 노후의 경제 동반자로서의 따뜻한 조언과 핵심 가치를 매번 새로운 문장으로 직접 작성할 것."""
    elif persona == 'brandconnect':
        personaGuidance = """당신은 5060 시니어들에게 프리미엄 가성비템을 솔직하게 리뷰해주는 '가성비 꿀템 리뷰어 (김쌤)'입니다.
실제 내돈내산이나 부모님께 직접 사드린 솔직한 1인칭 체험형 리뷰 형식으로 작성하세요.
- 반드시 도입부에서 실제 상황(예: "저희 어머니가 어머니가 자꾸 무릎이 쑤신다고 하셔서...")을 풀어가며 깊은 공감대를 형성할 것.
- 대놓고 상품부터 소개하지 말고 일상에서 느끼는 고통/결핍을 먼저 짚어낼 것.
- 정보 70%, 추천 30%의 황금비율을 유지하며, 📌, 💡, ✔️ 등의 이모지를 섞어 소제목을 달아줄 것.
- 본문 중간과 결론부에 call to action 문구(예: "이벤트 혜택이 언제 종료될지 모르니 일단 확인부터 해보세요!")를 적어줄 것."""

    # 최신 네이버 상위 노출 자가 학습 지침 로드
    naver_learning_guide = ""
    knowledge_path = 'naver_style_knowledge.json'
    if os.path.exists(knowledge_path):
        try:
            with open(knowledge_path, 'r', encoding='utf-8') as f:
                k_data = json.load(f)
                guide = k_data.get('style_guide', '')
                keyword_learned = k_data.get('target_keyword', '')
                if guide:
                    naver_learning_guide = f"\n[최신 상위 노출 학습 지침 (반영필수)]\n최근 네이버 블로그 영역에서 실제로 상위 노출되고 있는 '{keyword_learned}' 관련 우수 사례 분석 결과입니다:\n{guide}\n"
        except Exception as ke:
            print(f"⚠️ 네이버 자가 학습 지식 로드 실패: {ke}")

    # 네이버 멀티 블로그 성과 반성 및 피드백 지침 로드
    blog_insight_guide = ""
    insight_path = 'blog_insight_report.json'
    if os.path.exists(insight_path):
        try:
            with open(insight_path, 'r', encoding='utf-8') as f:
                i_data = json.load(f)
                report = i_data.get('insight_report', '')
                if report:
                    blog_insight_guide = f"\n[실시간 블로그 성과 피드백 지침 (반영필수)]\n성과 분석에 따른 썸네일 및 본문 개선 행동 강령입니다:\n{report}\n"
        except Exception as ie:
            print(f"⚠️ 네이버 성찰 피드백 로드 실패: {ie}")

    current_year = datetime.datetime.now().year

    # 1-Pass 통합 프롬프트 작성
    prompt = f"""
    당신은 대한민국 상위 1% 노출을 주도하는 최고의 블로그 1인칭 스토리텔러이자 SEO 엔지니어입니다.
    
    [역할 및 페르소나 지침]
    {personaGuidance}
    
    {naver_learning_guide}
    
    {blog_insight_guide}
    
    [글 작성 입력 정보]
    - 뉴스 제목: {title}
    - 핵심 요약: {summary}
    - 원본 링크: {link}
    - 작성 기준 연도: 무조건 {current_year}년
    
    [공통 필수 준수 가이드]
    1. 분량: 공백 제외 800자 ~ 1,000자. 모바일 가독성 최적화.
    2. 본문 오프닝 서론 직후 적절한 위치에 대표 이미지 표식용 `[THUMBNAIL]` 예약어 단 1번 작성. 본론 중간에는 이미지 표식용 `[IMAGE_1]`, `[IMAGE_2]`, `[IMAGE_3]` 예약어를 적절하게 배치하십시오.
    3. 클릭을 유도하는 유튜브/네이버 메인 스타일 제목 (Title) 작성:
       - 길이 25자 이내, 핵심 목표 키워드는 제목의 가장 앞부분(좌측) 배치.
       - 구체적인 숫자(예: 10분 만에, 5천만 원 등)를 포함하여 호기심과 실리적 이득 유도.
    4. 100% HTML 태그로 구조화 작성 (마크다운 기호 `*`, `-`, `##` 등 절대 금지):
       - 본문의 모든 문단은 `<p style='font-size: 16px; line-height: 1.8; margin-bottom: 26px; color: #333; letter-spacing: -0.5px;'>...</p>` 로 감싸 문단을 쪼개어 가독성을 높일 것.
       - 표(Table)가 필요할 때는 반드시 HTML `<table>`, `<tr>`, `<th>`, `<td>` 태그와 인라인 스타일을 사용할 것 (테두리, 배경색 등).
       - 소제목 계층화 필수: 대주제 `<h2>`, 소주제 `<h3>` 사용 및 세련된 인라인 스타일(테두리, 언더라인 등) 적용.
       - HTML 태그 내 속성은 반드시 홑따옴표(')를 사용할 것.
    5. 할루시네이션(거짓정보) 방지: 제공된 요약 및 정보의 팩트에 기반해서만 작성하고 없는 수치는 지어내지 말 것.
    6. 면책 조항(Disclaimer)의 100% 무작위 동적 생성: 
       - 글의 맨 마지막(결론 및 해시태그 바로 위)에 🚨 [팩트체크 및 면책고지] 문구를 매번 완전히 다른 어투와 어휘로 지어내어 `<p style='font-size: 13px; color: #888; text-align: center; line-height: 1.6;'><b>🚨 [팩트체크 및 면책고지]</b><br>...</p>` 형식으로 생성.
    7. 썸네일 카피라이팅 후킹 지침:
       - thumbnailTop: 해시태그3개, thumbnailMid: 핵심주제, thumbnailBottom: 하단어그로문구
       - primary: 검색어 단어, fallback: 포괄적 단어, englishSubject: 영어 단어

    [출력 요구사항 및 JSON 스키마]
    반드시 아래 JSON 스키마 규격으로만 완벽한 JSON 문자열로 출력해 주십시오. 다른 부연 설명이나 JSON 밖의 잡담은 절대 적지 마십시오.
    {{
      "thumbnail": {{
        "primary": "검색어 단어",
        "fallback": "포괄적 단어",
        "englishSubject": "영어 단어",
        "thumbnailTop": "해시태그3개",
        "thumbnailMid": "핵심주제",
        "thumbnailBottom": "하단어그로문구"
      }},
      "title": "클릭하고 싶은 블로그 제목 한 줄",
      "content": "HTML로 완벽하게 다듬어진 블로그 본문 (THUMBNAIL 및 IMAGE 예약어 포함)"
    }}
    """

    # 2. 초저비용 모드 (gemini-2.5-flash 고정) 스위칭 지원
    use_low_cost = os.environ.get("USE_LOW_COST_MODEL", "False").strip().lower() == "true"
    
    if use_low_cost:
        print("💡 [초저비용 모드 활성화] 본문 생성에 gemini-2.5-flash 단일 모델을 사용하여 비용을 50배 절감합니다.")
        models = ['gemini-2.5-flash']
    else:
        models = ['gemini-2.5-pro', 'gemini-2.5-flash']

    try:
        res = None
        last_err = None
        
        # 구글 검색을 활용한 팩트체크 장착 config
        for model_name in models:
            for attempt in range(1, 3):
                try:
                    config = types.GenerateContentConfig(
                        system_instruction="당신은 최고 품질의 블로그 원고를 생산하고 팩트를 체크하는 보조 AI입니다. 반드시 구글 검색 결과를 적극 참고해 거짓 없는 최신 정보를 담으십시오. 반드시 JSON 형식으로만 최종 응답해야 합니다.",
                        response_mime_type="application/json",
                        tools=[types.Tool(google_search=types.GoogleSearch())],
                        temperature=0.3
                    )
                    res = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config
                    )
                    break
                except Exception as search_err:
                    print(f"⚠️ {model_name} (시도 {attempt}/2) 툴 호출 실패로 툴 없이 재시도합니다: {search_err}")
                    # 만약 Billing Block이나 429가 의심되면 강제로 60초 쿨다운
                    if any(x in str(search_err).lower() for x in ["exceeded", "quota", "billing", "429", "blocked"]):
                        print("🚨 [쿨다운 필터 가동] Rate limit / Billing 한도 도달 감지. 60초 강제 대기합니다...")
                        time.sleep(60)
                    try:
                        config = types.GenerateContentConfig(
                            system_instruction="당신은 최고 품질의 블로그 원고를 생산하는 보조 AI입니다. 반드시 JSON 형식으로만 최종 응답해야 합니다.",
                            response_mime_type="application/json",
                            temperature=0.3
                        )
                        res = client.models.generate_content(
                            model=model_name,
                            contents=prompt,
                            config=config
                        )
                        break
                    except Exception as inner_err:
                        print(f"⚠️ {model_name} (시도 {attempt}/2) 일반 시도 실패: {inner_err}")
                        last_err = inner_err
                        if any(x in str(inner_err).lower() for x in ["exceeded", "quota", "billing", "429", "blocked"]):
                            print("🚨 [쿨다운 필터 가동] Rate limit / Billing 한도 도달 감지. 60초 강제 대기합니다...")
                            time.sleep(60)
            if res:
                break

        if not res:
            raise last_err if last_err else Exception("통합 원고 생성 최종 실패")

        # JSON 파싱
        json_str = res.text.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]
        parsed_res = json.loads(json_str.strip())
        
        # 파싱 데이터 추출
        thumbnail_params = parsed_res.get('thumbnail', {})
        blog_title = parsed_res.get('title', title)
        blog_content = parsed_res.get('content', '')

        # 3. 썸네일 이미지 검색 및 HTML 조립
        PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY")
        image_urls = []
        if PIXABAY_API_KEY:
            image_urls = fetch_pixabay_images(
                thumbnail_params.get('primary', '사무실'), 
                thumbnail_params.get('fallback', '비즈니스'), 
                PIXABAY_API_KEY
            )
            
        base_url = os.environ.get("BASE_URL", "http://localhost:3000")
        thumbnail_html = ""
        try:
            top_params = requests.utils.quote(thumbnail_params.get('thumbnailTop', '#정보공유 #필수지식'))
            mid_params = requests.utils.quote(thumbnail_params.get('thumbnailMid', blog_title[:8] if len(blog_title) > 8 else blog_title))
            bottom_params = requests.utils.quote(thumbnail_params.get('thumbnailBottom', '지금 확인하세요!'))
            style_param = f"&style={persona}" if persona else ""
            bg_param = f"&bg={requests.utils.quote(image_urls[0])}" if image_urls else ""
            
            og_url = f"{base_url}/api/og?top={top_params}&mid={mid_params}&bottom={bottom_params}{style_param}{bg_param}&ext=.png"
            
            thumbnail_html = f"""<div style="text-align: center; margin-bottom: 24px;">
      <img src="{og_url}" alt="대표 썸네일" style="max-width: 100%; height: auto; border-radius: 12px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -2px rgba(0,0,0,0.05);" />
    </div>"""
        except Exception as e:
            print(f"⚠️ 썸네일 이미지 URL 생성 실패: {e}")

        # 4. 포스트 프로세싱 & HTML 스타일 셔플링
        randomized_body = randomize_html_styles(blog_content)
        
        # [제휴마케팅 저품질 회피용 댓글 우회 및 인젝션 꿀팁 적용]
        if persona == 'brandconnect' and link:
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
            else:
                # 댓글 유도가 아닌 직접 링크 형태일 때 법적 필수 공정위 문구의 100% 무작위 동적 생성
                disclosure_texts = [
                    '해당 포스팅은 네이버 브랜드 커넥트를 통한 원고료 또는 소정의 수수료 지원으로 작성되었습니다.',
                    '브랜드 커넥트 활동의 일환으로 일정 수수료를 지급받을 수 있음을 알립니다.',
                    '본 포스팅은 브랜드 커넥트 캠페인에 참여하여 소정의 수수료를 제공받을 수 있습니다.',
                    '원활한 정보 제공을 위해 브랜드 커넥트 지원을 받아 일정액의 수수료를 받을 수 있습니다.',
                    '네이버 브랜드 커넥트를 통해 경제적 대가(수수료 등)를 제공받을 수 있는 홍보글입니다.'
                ]
                chosen_disclosure = random.choice(disclosure_texts)
                randomized_body += f"\n\n<p style='font-size: 13px; color: #777; text-align: center;'><b>{chosen_disclosure}</b></p>"

        # [THUMBNAIL] 예약어 치환
        if "[THUMBNAIL]" in randomized_body:
            randomized_body = randomized_body.replace("[THUMBNAIL]", thumbnail_html)
        else:
            # 썸네일 예약어가 없으면 서론 첫 단락 뒤에 강제 주입
            first_p_idx = randomized_body.find("</p>")
            if first_p_idx != -1:
                randomized_body = randomized_body[:first_p_idx+4] + "\n" + thumbnail_html + randomized_body[first_p_idx+4:]
            else:
                randomized_body = thumbnail_html + "\n" + randomized_body

        # [IMAGE_1], [IMAGE_2], [IMAGE_3] 예약어 치환
        for idx, img_url in enumerate(image_urls[1:4], start=1):
            img_tag = f"""<div style="text-align: center; margin-top: 24px; margin-bottom: 24px;">
  <img src="{img_url}" alt="본문 이미지 {idx}" style="max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);" />
</div>"""
            randomized_body = randomized_body.replace(f"[IMAGE_{idx}]", img_tag)

        # 기존 RSS 포스팅 저장 루틴과의 호환을 위한 출력 규격 복원
        full_result = f"[TITLE]\n{blog_title}\n[/TITLE]\n[CONTENT]\n{randomized_body}\n[/CONTENT]"
        return full_result

    except Exception as e:
        print(f"❌ 통합 블로그 원고 생성 최종 에러: {e}")
        return ""

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
