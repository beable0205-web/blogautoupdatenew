import os
import re
import sys
import json
import urllib.parse
import requests
import pandas as pd
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
ACCOUNTS_ENV = os.getenv('NAVER_BLOG_ACCOUNTS')

if not GEMINI_API_KEY:
    print("오류: GEMINI_API_KEY가 없습니다.")
    sys.exit(1)

client = genai.Client(api_key=GEMINI_API_KEY)

# 데이터 보관 CSV 파일 경로
VISITOR_CSV = 'visitor_stats.csv'
PERFORMANCE_CSV = 'post_performance.csv'
REPORT_JSON = 'blog_insight_report.json'
TREND_CSV = 'collected_trends.csv'

def parse_blog_accounts():
    """env 환경변수로부터 6개 계정 ID 리스트 파싱"""
    if not ACCOUNTS_ENV:
        # 기본값 폴백 (유저가 제공한 6개 계정 명시)
        return [
            "jjangdol0205",
            "cofinance1",
            "cofinance12",
            "kjh2579489",
            "better_life333",
            "business9489"
        ]
    accounts = []
    for item in ACCOUNTS_ENV.split(','):
        if ':' in item:
            accounts.append(item.split(':')[0].strip())
        else:
            accounts.append(item.strip())
    return accounts

def fetch_blog_visitors(blog_id):
    """각 블로그의 Today/Total 방문자 수 크롤링 (window.__INITIAL_STATE__ JSON 파싱 기반 우회 기법)"""
    url = f"https://m.blog.naver.com/{blog_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://m.naver.com/'
    }
    today, total = 0, 0
    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code == 200:
            html = response.text
            # window.__INITIAL_STATE__ JSON 또는 직접 정규식으로 dayVisitorCount와 totalVisitorCount 파싱
            day_match = re.search(r'"dayVisitorCount"\s*:\s*(\d+)', html)
            total_match = re.search(r'"totalVisitorCount"\s*:\s*(\d+)', html)
            
            if day_match:
                today = int(day_match.group(1))
            if total_match:
                total = int(total_match.group(1))
                
        # 비상 Fallback: JSON 객체 내 alert/totalVisitor 등 교차 필드 파싱 시도
        if today == 0 and total == 0:
            today_alt = re.search(r'"todayVisitor"\s*:\s*(\d+)', html)
            total_alt = re.search(r'"totalVisitor"\s*:\s*(\d+)', html)
            if today_alt:
                today = int(today_alt.group(1))
            if total_alt:
                total = int(total_alt.group(1))
                
        return today, total
    except Exception as e:
        print(f"⚠️ 블로그 {blog_id} 방문자 수 파싱 실패: {e}")
        return 0, 0

import time
import random

def check_search_rank_optimized(keyword, blog_ids):
    """네이버 모바일 통합 검색(블로그 탭) 영역에서 6개 블로그의 노출 순위 한 번에 트레킹 (403 Forbidden 우회 혁신)"""
    clean_k = re.sub(r'\[.*?\]', '', keyword).strip()
    encoded = urllib.parse.quote(clean_k)
    # 403 Forbidden 차단 우회를 위해 모바일 검색 탭 사용
    url = f"https://m.search.naver.com/search.naver?ssc=tab.m_blog.all&query={encoded}"
    
    # 봇 감지 회피용 모바일 브라우저 헤더셋
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://m.naver.com/',
        'Sec-Ch-Ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        'Sec-Ch-Ua-Mobile': '?1',
        'Sec-Ch-Ua-Platform': '"Android"',
        'Upgrade-Insecure-Requests': '1'
    }
    
    found_ranks = {}
    try:
        # 네이버 차단 방지용 임의 딜레이
        time.sleep(random.uniform(1.5, 3.0))
        
        response = requests.get(url, headers=headers, timeout=12)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        rank = 1
        processed_links = set()
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            # 모바일 및 PC 블로그 링크 교차 파싱 허용
            if 'blog.naver.com' in href and not any(x in href for x in ['MyBlog', 'CategoryList', 'admin', 'WriteForm']):
                match = re.search(r'blog\.naver\.com/([a-zA-Z0-9_-]+)/([0-9]+)', href)
                if match:
                    post_id = f"{match.group(1)}/{match.group(2)}"
                    if post_id not in processed_links:
                        processed_links.add(post_id)
                        blog_id = match.group(1)
                        if blog_id in blog_ids and blog_id not in found_ranks:
                            found_ranks[blog_id] = rank
                        rank += 1
            if rank > 15:  # 상위 1.5페이지 수준까지만 수집
                break
        return found_ranks
    except Exception as e:
        print(f"⚠️ 랭킹 검색 추적 실패 ({keyword}): {e}")
        return found_ranks

def generate_with_fallback(prompt, config=None):
    """Gemini 429 RESOURCE_EXHAUSTED 방지용 예비 모델 교차 우회 호출 헬퍼"""
    models_to_try = ['gemini-3.5-flash', 'gemini-2.5-pro', 'gemini-2.5-flash']
    last_err = None
    for model_name in models_to_try:
        try:
            res = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )
            return res
        except Exception as e:
            print(f"⚠️ [blog_monitor] {model_name} 호출 실패, 다음 모델로 우회합니다: {e}")
            last_err = e
    raise last_err

def run_performance_monitoring():
    """모든 멀티 블로그 계정에 대해 크롤링 및 모니터링 수행"""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 6대 멀티 블로그 성과 추적 시작...")
    blog_ids = parse_blog_accounts()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    # 1. 일간 방문자수 통계 누적
    visitor_records = []
    for blog_id in blog_ids:
        today_v, total_v = fetch_blog_visitors(blog_id)
        print(f"-> 블로그 [{blog_id}]: 오늘 방문자: {today_v:,}명 | 총 방문자: {total_v:,}명")
        visitor_records.append({
            'timestamp': timestamp,
            'blog_id': blog_id,
            'today_visitors': today_v,
            'total_visitors': total_v
        })
        
    # CSV 저장
    df_new_v = pd.DataFrame(visitor_records)
    if os.path.exists(VISITOR_CSV):
        df_old_v = pd.read_csv(VISITOR_CSV)
        df_combined_v = pd.concat([df_old_v, df_new_v], ignore_index=True)
    else:
        df_combined_v = df_new_v
    df_combined_v.to_csv(VISITOR_CSV, index=False, encoding='utf-8-sig')
    
    # 2. 최근 발행 포스트 검색 상위 노출 랭킹 트레킹
    performance_records = []
    if os.path.exists(TREND_CSV):
        try:
            df_trend = pd.read_csv(TREND_CSV)
            # 완료 상태인 글 중 최근 8개만 기획
            completed_posts = df_trend[df_trend['상태'] == '완료'].tail(8)
            
            for index, row in completed_posts.iterrows():
                title = row['title']
                # 제목에 검색량 표기가 붙어있을 수 있으므로 정제
                clean_title = re.sub(r'\s*\[검색량:.*\]\s*', '', title)
                # DSR, 대출 등 핵심 키워드성 단어 추출
                search_query = clean_title[:25]
                
                # 모든 블로그 계정 ID에 대해 단 한 번의 네이버 검색으로 랭킹 매칭 처리! (403 Forbidden 우회 혁신)
                ranks = check_search_rank_optimized(search_query, blog_ids)
                
                for blog_id, rank in ranks.items():
                    print(f"   * [노출 확인] 블로그 [{blog_id}] -> '{search_query}' 네이버 검색 랭킹 {rank}위 진입!")
                    performance_records.append({
                        'timestamp': timestamp,
                        'blog_id': blog_id,
                        'post_title': clean_title,
                        'search_query': search_query,
                        'rank': rank
                    })
        except Exception as te:
            print(f"⚠️ 최근 완료 키워드 로드 중 에러: {te}")
            
    # CSV 저장
    if performance_records:
        df_new_p = pd.DataFrame(performance_records)
        if os.path.exists(PERFORMANCE_CSV):
            df_old_p = pd.read_csv(PERFORMANCE_CSV)
            df_combined_p = pd.concat([df_old_p, df_new_p], ignore_index=True)
        else:
            df_combined_p = df_new_p
        df_combined_p.to_csv(PERFORMANCE_CSV, index=False, encoding='utf-8-sig')
    
    # 3. Gemini 기반 6개 블로그 일간 피드백 분석 학습 (Fallback 우회 가동)
    print("\n[AI 성과 반사 및 극비 진단 처방전 수립 중 (Agonizing)...]")
    
    visitor_summary = ""
    for r in visitor_records:
        visitor_summary += f"- {r['blog_id']}: 오늘 {r['today_visitors']}명 (총 {r['total_visitors']}명)\n"
        
    rank_summary = ""
    if performance_records:
        for r in performance_records:
            rank_summary += f"- {r['blog_id']} 블로그: 글 '{r['post_title']}' -> 네이버 랭킹 {r['rank']}위 등극\n"
    else:
        rank_summary = "- 상위 노출 1~15위 진입 글이 아직 탐지되지 않았습니다. 썸네일 및 HTML Shuffler 전조를 더욱 강화해야 합니다.\n"
        
    prompt = f"""
    당신은 6개의 독립적인 상업용 네이버 블로그 채널을 동시 운영하며 하루 1,000만 원 수익을 이끌어내는 극비 마케팅 연합의 전략 총괄 책임자입니다.
    아래는 오늘 자정 기준 6개 멀티 블로그 채널의 실제 실시간 방문자수 통계와 네이버 검색 상위 노출 랭킹 결과입니다.
    
    [6대 멀티 블로그 오늘자 방문자 수 현황]
    {visitor_summary}
    
    [오늘자 네이버 통합 검색 랭킹 노출 성과]
    {rank_summary}
    
    위의 냉혹한 실제 통계 데이터를 기반으로 다음 세 가지 요소를 포함하는 '일간 블로그 성과 반성 및 피드백 전술 요약본'을 작성해 주세요:
    1. 방문자 수가 급상승하거나 상위 노출에 진입한 블로그의 성공 패턴 요인 분석
    2. 조회수가 미비하거나 노출에 진입하지 못해 보완이 시급한 채널에 대한 뼈아픈 반성(Agonize)
    3. 내일 원고 생성 봇이 바로 반영할 **"썸네일 카피라이팅 후킹 강도 조절, 표/단락 구조 배치 세부 튜닝"** 극비 실천 지침
    
    [🚨 치명적 작성 제약 조건 🚨]
    - 지침은 반드시 **AI 글쓰기 봇이 직접 프롬프트 상의 로직으로 즉시 흡수할 수 있는 250자 ~ 400자 사이의 지시조 가이드라인**으로 압축 요약해야 합니다.
    - 말투는 무조건 '~할 것', '~해야 함', '~를 철저히 고수할 것' 등 직관적이고 강력한 **명령조/지침형 어조**로 고정해 주세요.
    - 뻔한 위로나 원론적인 이야기는 적지 말고, 수집된 데이터를 토대로 실질적인 작문 튜닝 방안만 명확히 적어주세요.
    """
    
    try:
        response = generate_with_fallback(
            prompt=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3
            )
        )
        insight_report = response.text.strip()
    except Exception as ge:
        print(f"⚠️ Gemini 성과 분석 피드백 생성 최종 실패: {ge}")
        insight_report = "네이버 블로그 1페이지 진입을 위해 소제목에 타겟 키워드를 가장 좌측에 배치하고, 본문 중간에 가독성이 우수한 HTML 표 구조를 1개 이상 100% 필수 삽입하여 독자 체류 시간을 2분 이상으로 이끌어낼 것. 친근한 1인칭 대화 톤앤매너를 철저히 고수할 것."
        
    print("\n================== [AI 일간 극비 성찰 및 전술 지침] ==================")
    print(insight_report)
    print("=======================================================================\n")
    
    # 4. JSON 갱신
    report_data = {
        "analyzed_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "visitor_records": visitor_records,
        "performance_records": performance_records,
        "insight_report": insight_report
    }
    
    with open(REPORT_JSON, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
        
    print(f"-> 성과 기반 피드백 리포트가 최종 저장되었습니다: {REPORT_JSON}")
    return report_data

if __name__ == "__main__":
    # 단독 실행 시 테스트 구동
    run_performance_monitoring()
