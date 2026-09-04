import requests
from bs4 import BeautifulSoup
from urllib3.exceptions import InsecureRequestWarning
import re 

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

def get_latest_notice(department_name: str) -> str:
    """
    특정 학과/부서의 최신 공지사항 상위 3개를 크롤링하고, 본문 내용을 살짝 요약하여 반환합니다.
    (속도와 LLM 토큰 절약을 위해 상위 3개만 가져옵니다.)
    """

    board_configs = {
        "학사공지": {
            "list_url": "https://labor.dankook.ac.kr/web/kor/-390",
            "row_selector": "div.dku-list-body-item",
            "title_selector": "div.item-title a",
            "board_type": "javascript", 
            "view_base_url": "https://labor.dankook.ac.kr/web/kor/-390?p_p_id=dku_bbs_web_BbsPortlet&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view&_dku_bbs_web_BbsPortlet_cur=1&_dku_bbs_web_BbsPortlet_action=view_message&_dku_bbs_web_BbsPortlet_orderBy=createDate&_dku_bbs_web_BbsPortlet_bbsMessageId="
        },
        "모바일시스템공학과": {
            "list_url": "https://cms.dankook.ac.kr/web/mobilesystems/-8",
            "row_selector": "div.dku-list-body-item",
            "title_selector": "div.item-title a",
            "board_type": "javascript", 
            "view_base_url": "https://cms.dankook.ac.kr/web/mobilesystems/-8?p_p_id=dku_bbs_web_BbsPortlet&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view&_dku_bbs_web_BbsPortlet_action=view_message&_dku_bbs_web_BbsPortlet_bbsMessageId="
        },
        "SW대회/행사": {
            "url": "https://swcu.dankook.ac.kr/ko/-2024-#none",
            "row_selector": "table.board_list tbody tr",
            "title_selector": "a"
        }
    }

    if department_name not in board_configs:
        return f"❌ 아직 '{department_name}'의 공지사항은 연동되지 않았습니다."

    config = board_configs[department_name]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        # [STEP 1] 목록 가져오기
        response = requests.get(config["list_url"], headers=headers, verify=False, timeout=5)
        response.raise_for_status() 
        soup = BeautifulSoup(response.text, 'html.parser')
        
        rows = soup.select(config["row_selector"])
        
        if not rows:
            return f"⚠️ '{department_name}' 게시판의 HTML 구조가 변경된 것 같습니다."

        result_text = f"📢 [{department_name} 최신 공지사항 Top 3]\n\n"
        notice_count = 0
        
        
        for row in rows:
            if notice_count >= 3: 
                break
                
            title_elem = row.select_one(config["title_selector"])
            
            if title_elem:
                title = title_elem.text.strip()
                if not title: continue
                
                notice_count += 1
                result_text += f"{notice_count}. 제목: {title}\n"

                content_preview = "본문을 가져올 수 없습니다."
                
                if config["board_type"] == "javascript":
                    
                    onclick_text = title_elem.get('onclick', '')
                    match = re.search(r'viewMessage\(\s*(\d+)', onclick_text)
                    
                    if match:
                        post_id = match.group(1)
                        view_url = config["view_base_url"] + post_id
                        
                        # 본문 페이지 접속
                        try:
                            view_res = requests.get(view_url, headers=headers, verify=False, timeout=3)
                            view_soup = BeautifulSoup(view_res.text, 'html.parser')
                           
                            content_div = view_soup.select_one('table.table.mb-3 div.fr-view')

                            
                            if not content_div:
                                content_div = view_soup.select_one('table.table.mb-3 tbody tr:last-child')

                            if not content_div:
                                content_div = view_soup.select_one('table.table.mb-3')

                            if content_div:
                                
                                raw_text = ' '.join(content_div.text.split())
                                content_preview = raw_text
                            else:
                                content_preview = "본문 영역을 찾지 못했습니다."
                        except:
                            content_preview = "본문 접속 지연."
                            
                elif config["board_type"] == "standard":
                     
                     content_preview = "본문은 직접 링크를 확인해주세요."

                result_text += f"   내용 : {content_preview}\n\n"
                
        return result_text

    except Exception as e:
        return f"❌ {department_name} 서버 연결 중 오류가 발생했습니다: {e}"


# 단독 테스트 실행 구역
if __name__ == "__main__":
    print("🚀 크롤러 단독 테스트를 시작합니다...\n")
    #print(get_latest_notice("모바일시스템공학과"))
    print(get_latest_notice("학사공지"))