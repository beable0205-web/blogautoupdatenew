import os
import re
import time
import requests
from bs4 import BeautifulSoup
import schedule
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime
import subprocess
import hmac
import hashlib
import base64
import sys
from naver_learner import run_learning
from blog_monitor import run_performance_monitoring

# 윈도우 콘솔 환경에서 이모지 출력 시 발생하는 cp949 인코딩 에러 방지
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# .env.local 파일에서 환경변수 로드 (로컬 환경인 경우)
if not os.getenv('GITHUB_ACTIONS_ENV'):
    load_dotenv('.env.local')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')

if not DEEPSEEK_API_KEY or "your_deepseek_api_key" in DEEPSEEK_API_KEY:
    print("오류: DEEPSEEK_API_KEY가 없습니다. (.env.local 또는 깃허브 시크릿을 확인하세요)")
    exit(1)

# 최신 모델 Fallback 연동 헬퍼 함수 정의 (초저비용 모드 및 429 쿨다운 필터 장착)
def generate_with_fallback(prompt, temperature=0.7):
    """DeepSeek API 호출 및 429/503 에러 쿨다운 필터 장착 (시도 3회)"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "당신은 실시간 트렌드 분석 및 블로그 키워드 마스터입니다."},
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature
    }
    
    last_err = None
    for attempt in range(1, 4):
        try:
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=90
            )
            if response.status_code == 200:
                res_data = response.json()
                return res_data['choices'][0]['message']['content'].strip()
            elif response.status_code in [429, 503]:
                print(f"⚠️ [trend_crawler] DeepSeek API {response.status_code} 에러 감지 (시도 {attempt}/3). 15초 대기합니다...")
                time.sleep(15)
            else:
                raise Exception(f"API Error status code: {response.status_code}, Response: {response.text}")
        except Exception as e:
            print(f"⚠️ [trend_crawler] DeepSeek API 호출 시도 {attempt}/3 실패: {e}")
            last_err = e
            time.sleep(5)
    raise last_err

# 네이버 검색광고 API 키 로드
NAVER_AD_CUSTOMER_ID = os.getenv('NAVER_AD_CUSTOMER_ID')
NAVER_AD_ACCESS_LICENSE = os.getenv('NAVER_AD_ACCESS_LICENSE')
NAVER_AD_SECRET_KEY = os.getenv('NAVER_AD_SECRET_KEY')

# 저장할 CSV 파일 경로
CSV_FILE = 'collected_trends.csv'

# 다음 뉴스 (메인 및 인기 랭킹) 수집
def fetch_daum_news():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    urls = ['https://news.daum.net/', 'https://news.daum.net/ranking/popular']
    headlines = []
    
    try:
        for url in urls:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for a in soup.find_all('a'):
                href = a.get('href', '')
                title = a.text.strip()
                if 'v.daum.net/v/' in href and title and title not in headlines:
                    headlines.append(title)
        
        # 중복 제거 및 리스트 반환 (최대 50개)
        unique_headlines = list(dict.fromkeys(headlines))[:50]
        return unique_headlines
    except Exception as e:
        print(f"다음 뉴스 수집 오류: {e}")
        return []

# 네이트판 수집
def fetch_nate_pann():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    url = 'https://pann.nate.com/talk/ranking'
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        stories = []
        # 네이트판 랭킹 제목 추출
        for a in soup.select('dl dt a'):
            title = a.text.strip()
            if title:
                stories.append(title)
                
        # 중복 제거 및 상위 20개 추출
        unique_stories = list(dict.fromkeys(stories))[:20]
        return unique_stories
    except Exception as e:
        print(f"네이트판 수집 오류: {e}")
        return []

# 네이버 검색광고 API 호출 (검색량 분석)
def get_naver_search_volumes(keywords):
    if not NAVER_AD_CUSTOMER_ID or not NAVER_AD_ACCESS_LICENSE or not NAVER_AD_SECRET_KEY:
        print("네이버 검색광고 API 키가 없습니다. 검색량 검증을 건너뜁니다.")
        return {k: -1 for k in keywords}

    results = {}
    # 네이버 API는 한 번에 5개까지만 hintKeywords 조회가 가능하므로 5개씩 쪼개어 요청
    for i in range(0, len(keywords), 5):
        batch = keywords[i:i+5]
        # 공백 제거 후 요청
        hint_keywords = ",".join([k.replace(" ", "") for k in batch])
        
        timestamp = str(int(time.time() * 1000))
        method = "GET"
        path = "/keywordstool"
        message = f"{timestamp}.{method}.{path}"
        
        signature = base64.b64encode(hmac.new(NAVER_AD_SECRET_KEY.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).digest()).decode('utf-8')
        
        headers = {
            'X-Timestamp': timestamp,
            'X-API-KEY': NAVER_AD_ACCESS_LICENSE,
            'X-Customer': str(NAVER_AD_CUSTOMER_ID),
            'X-Signature': signature
        }
        
        url = f"https://api.naver.com{path}?hintKeywords={hint_keywords}&showDetail=1"
        try:
            res = requests.get(url, headers=headers)
            if res.status_code == 200:
                data = res.json()
                k_list = data.get('keywordList', [])
                for match in k_list:
                    rel_k = match.get('relKeyword', '')
                    pc = match.get('monthlyPcQcCnt', 0)
                    mob = match.get('monthlyMobileQcCnt', 0)
                    
                    if isinstance(pc, str) and '<' in pc: pc = 5
                    if isinstance(mob, str) and '<' in mob: mob = 5
                    
                    total = int(pc) + int(mob)
                    
                    # 매칭되는 원래 키워드 찾기 (공백 제거된 것과 매칭)
                    for original_k in batch:
                        if original_k.replace(" ", "") == rel_k:
                            results[original_k] = total
            time.sleep(0.5) # API Rate limit 보호
        except Exception as e:
            print(f"네이버 API 요청 실패: {e}")
            
    # 누락된 키워드는 -1로 처리
    for k in keywords:
        if k not in results:
            results[k] = -1
            
    return results

# 과거 키워드 로드 (최근 50개)
def get_past_keywords():
    try:
        if os.path.exists(CSV_FILE):
            df = pd.read_csv(CSV_FILE)
            if 'title' in df.columns:
                return df['title'].tail(50).tolist()
    except Exception as e:
        print(f"과거 키워드 로드 실패: {e}")
    return []

# AI 자가 학습 및 전략 수립 (Agonize)
def generate_daily_breakthrough_strategy(past_keywords):
    if not past_keywords:
        return "과거 데이터가 부족하여 기본 9대 카테고리(정치, 복지, 예적금, 연금, 부동산, 세금, 이슈 등)를 유지합니다."
        
    prompt = f"""
    당신은 블로그 트렌드 전략가입니다.
    현재 블로그 조회수가 정체되어 있습니다. 아래는 최근 생성했던 50개의 블로그 키워드 목록입니다.
    
    [최근 50개 키워드 목록]
    {chr(10).join(past_keywords)}
    
    위 키워드들이 왜 독자들의 클릭을 유도하지 못했는지(뻔한 주제, 후킹 부족 등) 뼈아프게 반성(Agonize)하고,
    오늘 조회수 1만뷰를 터트리기 위해 완전히 새롭고 시의성 있는 "블루오션 카테고리 전략 3가지"를 제안해 주세요.
    
    [🚨 강력한 추가 지시사항 (부동산 필수 포함) 🚨]
    현재 대중의 관심과 검색 수요가 '부동산(청약, 대출, 하락장 등)'에 폭발적으로 몰려 있습니다.
    따라서 제안하는 3개의 전략 중 **최소 1~2개는 반드시 부동산/주거/대출 관련 숨겨진 틈새 시장(예: 지역별 폭락, 특정 대출 정책 등)**이어야 합니다.
    """
    try:
        response_text = generate_with_fallback(prompt, temperature=0.7)
        return response_text
    except Exception as e:
        print(f"전략 수립 중 오류 발생: {e}")
        return "기본 9대 카테고리(정치, 복지, 예적금, 연금, 부동산, 세금, 이슈 등)를 유지합니다."

# DeepSeek로 황금 키워드 추출 (동적 전략 반영)
def extract_golden_keywords_with_deepseek(daum_headlines, nate_stories, strategy):
    all_issues = []
    if daum_headlines:
        all_issues.append("[다음 뉴스 랭킹]")
        all_issues.extend([f"- {h}" for h in daum_headlines])
    if nate_stories:
        all_issues.append("\n[네이트판 인기 스토리]")
        all_issues.extend([f"- {h}" for h in nate_stories])
        
    if not all_issues:
        return []
        
    prompt = f"""
    당신은 대한민국 상위 0.1% 조회수를 이끌어내는 블로그 트렌드 마스터입니다.
    아래는 현재 인터넷에서 가장 뜨거운 실시간 뉴스 및 커뮤니티 썰 목록입니다.
    이 목록을 분석하여, 블로그 포스팅 시 '조회수 1만 뷰 이상'을 달성할 수 있는 \"고부가가치 황금 키워드/후킹 제목\"을 추출해 주셔야 합니다.
    
    [오늘의 맞춤형 돌파 전략 (AI 자가 반성 기반)]
    {strategy}
    
    위 전략을 바탕으로 기존의 뻔한 주제를 버리고, 사람들의 공포(FOMO), 호기심, 돈, 도파민을 강력하게 자극하는 롱테일 키워드를 기획하세요.
    제목은 점잖은 뉴스 헤드라인이 아니라, 독자가 무조건 클릭할 수밖에 없도록 매우 자극적이고 '엣지(Edge) 있는' 도발적인 톤앤매너로 작성해야 합니다.
    
    [🚨 치명적 주의사항 (가짜 뉴스 생성 절대 금지) 🚨]
    - 원본 뉴스 제목에 없는 '없는 사실, 조작된 수치, 거짓된 혜택'을 절대 지어내지 마세요.
    - 자극적인 제목을 만들더라도 100% 팩트를 기반으로 해야 하며, 독자를 기만하는 허위 사실을 생성하면 안 됩니다.
    
    [출력 형식]
    돌파 전략에 맞춰 파급력이 클 것 같은 \"정제된 키워드(또는 제목)\" 후보군을 **넉넉하게 30개** 뽑아주세요.
    반드시 다음과 같이 \"정제된 키워드 | 카테고리명\" 형식으로 한 줄씩 출력해주세요. 다른 부연 설명은 절대 적지 마세요.
    (예시: 2026 숨은 정부지원금 확인하기 | 보조금/지원금/복지)
    
    [🚨 카테고리명 필수 조건 🚨]
    카테고리명은 반드시 아래의 10가지 중 하나여야만 합니다. 절대 새로운 카테고리를 임의로 만들지 마세요.
    1. 재테크/머니파이프라인
    2. 보조금/정부지원금
    3. 부동산/청약 대출
    4. 예적금/특판 재무설계
    5. 세금/연금/절세 꿀팁
    6. 주식/글로벌 경제이슈
    7. 비트코인/가상자산 동향
    8. 창업/정부 정책자금
    9. 소비/가성비 쇼핑 테크
    10. 트렌드 코리아/비즈니스 이슈
    
    [실시간 소스 데이터]
    """
    prompt += "\n".join(all_issues)
    
    try:
        response_text = generate_with_fallback(prompt, temperature=0.7)
        
        results = []
        for line in response_text.split('\n'):
            if '|' in line:
                parts = line.split('|', 1)
                title = parts[0].replace('- ', '').strip()
                category = parts[1].strip()
                results.append({'title': title, 'category': category})
        return results
    except Exception as e:
        print(f"DeepSeek API 오류: {e}")
        return []

def run_crawler():
    # 유저의 API 한도 증액(12,000원)에 따라 비용 보호 모드를 일시 비활성화하고 즉시 크롤러를 정상 가동합니다.
    print("🚀 [가동 복원] API 한도 증액 확인 완료. 비용 보호 모드를 해제하고 초저비용 모드(2.5-flash)로 즉시 작동을 시작합니다.")

    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 최신 데이터 동기화 (Git Pull)...")
    try:
        subprocess.run(['git', 'pull', '--rebase'], check=True, cwd=os.getcwd(), capture_output=True)
    except Exception as e:
        print(f"Git Pull 실패 (무시하고 진행): {e}")

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 크롤링 및 키워드 정제 시작...")
    
    # 1일 1회만 AI 실시간 학습 및 블로그 성과 모니터링 가동 (토큰 절약 및 Quota 초과 차단)
    today_date = datetime.now().strftime('%Y-%m-%d')
    date_file = 'last_ai_analysis_date.txt'
    should_run_ai_analysis = True
    
    # 6월 1일 결제 리셋 전까지 비용 극소화를 위해 고토큰 AI 자가 학습 및 성과 모니터링은 무조건 스킵합니다.
    if datetime.now() < datetime(2026, 6, 1, 0, 0, 0):
        print("📉 [비용 극최소화 모드] 6월 1일 자정 전까지 고토큰 소모가 일어나는 AI 자가학습 및 성과 모니터링을 무조건 일시 중지합니다.")
        should_run_ai_analysis = False
    elif os.path.exists(date_file):
        try:
            with open(date_file, 'r', encoding='utf-8') as df:
                last_date = df.read().strip()
                if last_date == today_date:
                    should_run_ai_analysis = False
        except Exception as de:
            print(f"⚠️ 날짜 로그 확인 에러: {de}")

    new_data = []
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    print("다음 뉴스 수집 중...")
    daum_headlines = fetch_daum_news()
    print(f"수집된 다음 헤드라인 수: {len(daum_headlines)}")
    
    print("네이트판 인기 스토리 수집 중...")
    nate_stories = fetch_nate_pann()
    print(f"수집된 네이트판 스토리 수: {len(nate_stories)}")
    
    if daum_headlines or nate_stories:
        print("\n[AI 조회수 정체 돌파 전략 수립 중 (Agonizing)...]")
        past_keywords = get_past_keywords()
        
        try:
            strategy = generate_daily_breakthrough_strategy(past_keywords)
        except Exception as se:
            print(f"⚠️ AI 전략 수립 실패 (Billing Block / API 한도 도달 우려): {se}")
            strategy = "과거 데이터가 부족하여 기본 9대 카테고리(정치, 복지, 예적금, 연금, 부동산, 세금, 이슈 등)를 유지합니다."
            
        print("================== [AI 오늘의 반성 및 전략] ==================")
        print(strategy)
        print("==============================================================\n")
        
        print("DeepSeek API로 30개의 맞춤형 황금 키워드 후보 추출 중...")
        try:
            refined_keywords = extract_golden_keywords_with_deepseek(daum_headlines, nate_stories, strategy)
        except Exception as ke:
            print(f"⚠️ AI 황금 키워드 추출 실패 (API 한도 도달): {ke}")
            refined_keywords = []
        
        # 네이버 검색량 분석
        print("네이버 검색광고 API를 통한 검색량 기반 필터링 진행 중...")
        candidates = [item['title'] for item in refined_keywords]
        volumes = get_naver_search_volumes(candidates)
        
        # [신규 추가] 가장 파급력이 높은 단 하나의 카테고리 동적 엄선
        category_scores = {}
        for item in refined_keywords:
            cat = item.get('category', '재테크/머니파이프라인')
            vol = volumes.get(item['title'], 0)
            if vol == -1 or vol is None: 
                vol = 500  # 검색량 조회 불가 시 기본 가중치 부여
            category_scores[cat] = category_scores.get(cat, 0) + vol

        chosen_category = max(category_scores, key=category_scores.get) if category_scores else '재테크/머니파이프라인'
        print(f"🎯 [단일 카테고리 엄선] 이번 주기의 최정예 카테고리로 '{chosen_category}'를 동적 선별 완료했습니다.")

        # 필터링 로직: 엄선된 카테고리에 한해 1000 ~ 50000 구간의 키워드 선별
        filtered_keywords = []
        for item in refined_keywords:
            if item.get('category') != chosen_category:
                continue  # 엄선된 카테고리가 아니면 비용 절감을 위해 전면 스킵
                
            k = item['title']
            v = volumes.get(k, -1)
            if NAVER_AD_CUSTOMER_ID and NAVER_AD_ACCESS_LICENSE and NAVER_AD_SECRET_KEY:
                if 1000 <= v <= 50000 or v == -1:
                    if v != -1:
                        item['title'] = f"{k} [검색량: {v:,}회]"
                    else:
                        item['title'] = k
                    filtered_keywords.append(item)
            else:
                # API 키가 없으면 필터링 없이 통과
                filtered_keywords.append(item)
                
        # 최종적으로 상위 5개의 핵심 키워드만 선별하여 저장 (요금 다이어트 극대화)
        filtered_keywords = filtered_keywords[:5]
        
        # [신규 추가] 가장 핫한 최상위 1위 키워드를 기반으로 실시간 네이버 블로그 검색 상위 노출 스타일 자가 학습 가동
        if filtered_keywords:
            top_k_keyword = filtered_keywords[0]['title']
            # 검색량 꼬리표가 붙어 있다면 제거 후 원래 키워드만 전달
            clean_keyword = re.sub(r'\s*\[검색량:.*\]\s*', '', top_k_keyword)
            
            if should_run_ai_analysis:
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 최신 키워드({clean_keyword}) 기반 네이버 블로그 실시간 자가 학습 가동...")
                try:
                    run_learning(clean_keyword)
                except Exception as le:
                    print(f"⚠️ 네이버 실시간 자가 학습 구동 실패 (무시하고 진행): {le}")
            else:
                print(f"\n[건너뜀] 오늘자({today_date}) 네이버 실시간 자가 학습은 이미 수행되었습니다.")
        
        for item in filtered_keywords:
            new_data.append({
                'timestamp': timestamp,
                'source': 'AI+Data Refined',
                'category': item['category'],
                'title': item['title'],
                '상태': '대기'
            })
            
    # 3. CSV 저장 및 중복 제거
    if new_data:
        df_new = pd.DataFrame(new_data)
        
        if os.path.exists(CSV_FILE):
            df_old = pd.read_csv(CSV_FILE)
            if '상태' not in df_old.columns:
                df_old['상태'] = '완료'  # 기존 데이터는 이미 완료로 처리하여 중복 발행 방지
            df_combined = pd.concat([df_old, df_new], ignore_index=True)
            # 같은 출처, 카테고리, 제목이면 중복으로 보고 제거
            df_combined.drop_duplicates(subset=['source', 'category', 'title'], keep='last', inplace=True)
        else:
            df_combined = df_new
            
        df_combined.to_csv(CSV_FILE, index=False, encoding='utf-8-sig')
        print(f"총 {len(df_new)}개의 새로운 트렌드가 {CSV_FILE}에 저장되었습니다. (누적: {len(df_combined)}개)")
    else:
        print("수집된 데이터가 없습니다.")

    # [신규 추가] 6대 멀티 블로그 일간 성과 감시 및 AI 피드백 연동
    if should_run_ai_analysis:
        try:
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 6대 블로그 성과 분석 및 AI 자가 진단 가동...")
            run_performance_monitoring()
            # AI 분석이 끝났으므로 날짜 기록
            with open(date_file, 'w', encoding='utf-8') as df:
                df.write(today_date)
        except Exception as me:
            print(f"⚠️ 블로그 성과 분석 모니터 구동 실패 (무시하고 진행): {me}")
    else:
        print(f"\n[건너뜀] 오늘자({today_date}) 블로그 성과 모니터링 및 AI 피드백 분석은 이미 수행되었습니다.")

    # 4. GitHub 자동 푸시
    push_to_github()

def push_to_github():
    print("GitHub로 변경사항을 푸시합니다...")
    try:
        # GitHub Actions 환경일 경우 봇 계정 설정
        if os.getenv('GITHUB_ACTIONS_ENV'):
            subprocess.run(['git', 'config', '--global', 'user.name', 'github-actions[bot]'], check=True, cwd=os.getcwd())
            subprocess.run(['git', 'config', '--global', 'user.email', 'github-actions[bot]@users.noreply.github.com'], check=True, cwd=os.getcwd())
            
        # git add
        subprocess.run(['git', 'add', CSV_FILE, 'naver_style_knowledge.json', 'visitor_stats.csv', 'post_performance.csv', 'blog_insight_report.json'], check=True, cwd=os.getcwd(), capture_output=True)
        
        # git commit
        commit_msg = f"Auto-update trends & blog insights: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        res = subprocess.run(['git', 'commit', '-m', commit_msg], cwd=os.getcwd(), capture_output=True)
        
        if res.returncode == 0:
            # git push
            subprocess.run(['git', 'push'], check=True, cwd=os.getcwd(), capture_output=True)
            print("GitHub 푸시 완료!")
        else:
            print("커밋할 새로운 변경사항이 없습니다.")
    except subprocess.CalledProcessError as e:
        print(f"Git 명령 실행 중 오류 발생: {e}")
        
if __name__ == "__main__":
    if os.getenv('GITHUB_ACTIONS_ENV'):
        # 클라우드 환경: 딱 한 번만 실행 후 종료
        try:
            run_crawler()
        except Exception as e:
            print(f"❌ 클라우드 크롤링 실행 실패: {e}")
            sys.exit(1)
    else:
        # 로컬 환경: 처음 1회 실행 후 3시간 간격 무한 반복
        try:
            run_crawler()
        except Exception as e:
            print(f"❌ 초기 크롤링 실행 실패 (스케줄러는 계속 유지됩니다): {e}")
            
        def safe_run_crawler():
            try:
                run_crawler()
            except Exception as e:
                print(f"❌ [스케줄러] 크롤러 주기 실행 중 예외 감지 (데몬 생존): {e}")

        # 6월 1일 이전에는 12시간 주기로 크롤러 작동을 크게 늦추어 비용을 극소화합니다.
        crawler_interval = 12 if datetime.now() < datetime(2026, 6, 1, 0, 0, 0) else 3
        schedule.every(crawler_interval).hours.do(safe_run_crawler)
        print(f"\n🚀 [{crawler_interval}시간] 간격 트렌드 크롤러가 시작되었습니다. (종료하려면 Ctrl+C를 누르세요)")
        while True:
            try:
                schedule.run_pending()
            except Exception as se:
                print(f"❌ 스케줄 대기 루프 예외 발생: {se}")
            time.sleep(60)
