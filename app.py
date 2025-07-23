import streamlit as st
import requests
import json
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
import os

# 환경 변수 로드
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # Azure에서는 dotenv가 필요없음

# 페이지 설정
st.set_page_config(
    page_title="DSCore UX 컴포넌트 검색",
    page_icon="🔍",
    layout="wide"
)

# 제목
st.title("🔍 DSCore UX 컴포넌트 검색")
st.markdown("---")

class SimpleRAG:
    def __init__(self):
        try:
            self.search_client = SearchClient(
                endpoint=os.environ.get("AZURE_SEARCH_ENDPOINT", ""),
                index_name=os.environ.get("AZURE_SEARCH_INDEX_NAME", ""),
                credential=AzureKeyCredential(os.environ.get("AZURE_SEARCH_API_KEY", ""))
            )
            self.ready = True
        except Exception as e:
            self.ready = False
            self.error = str(e)
    
    def search_documents(self, query):
        try:
            # 더 많은 결과 검색
            results = self.search_client.search(search_text=query, top=5)
            docs = []
            
            print(f"=== 검색어: {query} ===")
            
            for i, result in enumerate(results):
                print(f"\n--- 문서 {i+1} ---")
                print(f"필드들: {list(result.keys())}")
                
                # 모든 필드를 확인해서 가장 긴 텍스트 내용 찾기
                best_content = ""
                best_field = ""
                
                for key, value in result.items():
                    if isinstance(value, str) and len(value.strip()) > len(best_content):
                        best_content = value.strip()
                        best_field = key
                        
                if best_content:
                    print(f"선택된 필드: {best_field}")
                    print(f"내용 미리보기: {best_content[:200]}...")
                    docs.append(best_content)
            
            print(f"총 {len(docs)}개 문서 수집")
            return docs if docs else ["관련 문서를 찾을 수 없습니다."]
            
        except Exception as e:
            print(f"검색 오류: {e}")
            return [f"검색 중 오류: {str(e)}"]
    
    def generate_answer(self, query, documents):
        if not documents or documents[0].startswith("검색 중 오류") or documents[0].startswith("관련 문서를"):
            return documents[0]
        
        # Azure OpenAI API 직접 호출
        try:
            endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip('/')
            deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "")
            api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
            
            url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version=2024-02-01"
            
            headers = {
                "Content-Type": "application/json",
                "api-key": api_key
            }
            
            # 여러 문서를 모두 포함 (더 많은 컨텍스트)
            context = "\n\n=== 문서 내용 ===\n\n".join(documents[:3])
            
            prompt = f"""다음 UI 컴포넌트 문서를 바탕으로 질문에 답변해주세요:

{context}

질문: {query}

답변 규칙:
1. 컴포넌트의 사용법과 설명을 포함하세요
2. 예시 코드가 문서에 있다면 반드시 포함하세요 
3. Props나 속성 정보가 있다면 포함하세요
4. 마크다운 형식으로 답변하세요
5. 코드는 ```html 또는 ```javascript 형식으로 작성하세요

상세하고 실용적인 답변을 제공해주세요."""

            data = {
                "messages": [
                    {"role": "system", "content": "당신은 UI 컴포넌트 문서 전문가입니다. 개발자가 실제로 사용할 수 있도록 상세한 예시 코드와 설명을 제공하세요."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
                "max_tokens": 1500
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                # API 호출 실패시 원본 문서 내용 반환
                return f"**관련 문서를 찾았습니다:**\n\n{context[:1000]}..."
                
        except Exception as e:
            # 오류 발생시 검색된 문서 내용 반환
            return f"**관련 문서를 찾았습니다:**\n\n{documents[0][:1000]}..."

# RAG 시스템 초기화
@st.cache_resource
def init_rag():
    return SimpleRAG()

rag = init_rag()

# 세션 상태 초기화
if 'last_question' not in st.session_state:
    st.session_state.last_question = ""
if 'last_answer' not in st.session_state:
    st.session_state.last_answer = ""

# 시스템 상태 확인
if not rag.ready:
    st.error(f"❌ 시스템 연결 오류: {rag.error}")
    st.stop()

# 메인 영역
col1, col2 = st.columns([3, 1])

with col1:
    st.header("질문하기")
    
    # 질문 입력
    question = st.text_area(
        "질문을 입력하세요:",
        height=100,
        placeholder="예: button에 대해 설명해주세요",
        help="DSCore UI 컴포넌트에 대한 질문을 입력하세요"
    )
    
    # 검색 버튼
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 4])
    
    with col_btn1:
        search_clicked = st.button("🔍 검색", type="primary", use_container_width=True)
    
    with col_btn2:
        if st.button("🗑️ 초기화", use_container_width=True):
            st.session_state.last_question = ""
            st.session_state.last_answer = ""
            st.rerun()
    
    # 검색 실행
    if search_clicked and question.strip():
        with st.spinner("문서를 검색하고 답변을 생성하고 있습니다..."):
            try:
                # 문서 검색
                documents = rag.search_documents(question)
                
                # 답변 생성
                answer = rag.generate_answer(question, documents)
                
                st.session_state.last_question = question
                st.session_state.last_answer = answer
                
            except Exception as e:
                st.error(f"검색 중 오류가 발생했습니다: {e}")
    
    elif search_clicked:
        st.warning("⚠️ 질문을 입력해주세요.")
    
    # 검색 결과 표시
    if st.session_state.last_question and st.session_state.last_answer:
        st.markdown("---")
        st.markdown("### 📋 검색 결과")
        
        # 질문 표시
        st.markdown(f"**질문:** {st.session_state.last_question}")
        
        # 답변 표시
        st.markdown("**답변:**")
        st.markdown(st.session_state.last_answer)

with col2:
    st.header("사용 가이드")
    
    # 예시 질문들
    st.markdown("### 💡 예시 질문")
    example_questions = [
        "button에 대해 설명해",
        "테이블 컴포넌트 사용법",
        "페이지네이션 구현 방법",
        "CTA 버튼이 뭐야?",
        "회원가입 화면 구성",
        "에러 페이지 버튼들"
    ]
    
    for i, eq in enumerate(example_questions, 1):
        if st.button(f"{i}. {eq}", key=f"example_{i}", use_container_width=True):
            st.session_state.last_question = eq
            # 즉시 검색 실행
            with st.spinner("문서를 검색하고 답변을 생성하고 있습니다..."):
                try:
                    documents = rag.search_documents(eq)
                    answer = rag.generate_answer(eq, documents)
                    st.session_state.last_answer = answer
                    st.rerun()
                except Exception as e:
                    st.error(f"검색 중 오류가 발생했습니다: {e}")
    
    # 사용 팁
    st.markdown("---")
    st.markdown("### 📌 사용 팁")
    st.markdown("""
    - **구체적인 질문**을 하면 더 정확한 답변을 얻을 수 있어요
    - **컴포넌트 이름**을 포함해서 질문해보세요
    - **사용법, 예시, 코드** 등을 요청할 수 있어요
    - 한 번에 여러 질문을 해도 괜찮아요
    """)
    
    # 시스템 정보
    st.markdown("---")
    st.markdown("### ⚙️ 시스템 정보")
    if st.button("🔧 연결 상태 확인", use_container_width=True):
        try:
            # 간단한 테스트 검색
            test_result = rag.search_documents("test")
            if test_result and not test_result[0].startswith("검색 중 오류"):
                st.success("✅ 시스템이 정상적으로 작동하고 있습니다!")
                st.info(f"📊 검색 테스트 완료")
            else:
                st.warning("⚠️ 문서를 찾을 수 없습니다. 인덱스를 확인해주세요.")
        except Exception as e:
            st.error(f"❌ 시스템 오류: {e}")

# 하단 정보
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666; font-size: 0.9em;'>
        🚀 Powered by Azure OpenAI & Azure AI Search<br>
        📖 DSCore UX Frame 표준정책서 기반
    </div>
    """, 
    unsafe_allow_html=True
)