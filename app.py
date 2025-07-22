import streamlit as st
from reg_dscore import RAGSystem

# 페이지 설정
st.set_page_config(
    page_title="DSCore UX 컴포넌트 검색",
    page_icon="🔍",
    layout="wide"
)

# 제목
st.title("🔍 DSCore UX 컴포넌트 검색")
st.markdown("---")

# 세션 상태 초기화
if 'rag_system' not in st.session_state:
    try:
        st.session_state.rag_system = RAGSystem()
        st.session_state.system_ready = True
    except Exception as e:
        st.session_state.system_ready = False
        st.session_state.error_message = str(e)

# 검색 결과 저장용
if 'last_question' not in st.session_state:
    st.session_state.last_question = ""
if 'last_answer' not in st.session_state:
    st.session_state.last_answer = ""

# 시스템 상태 확인
if not st.session_state.system_ready:
    st.error(f"❌ 시스템 연결 오류: {st.session_state.error_message}")
    st.stop()

# 메인 영역
col1, col2 = st.columns([3, 1])

with col1:
    st.header("질문하기")
    
    # 질문 입력 (세션 상태에서 선택된 질문이 있으면 사용)
    default_question = st.session_state.get('selected_question', '')
    question = st.text_area(
        "질문을 입력하세요:",
        value=default_question,
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
            st.session_state.selected_question = ""
            st.rerun()
    
    # 검색 실행 함수
    def perform_search(query):
        if query.strip():
            with st.spinner("문서를 검색하고 답변을 생성하고 있습니다..."):
                try:
                    answer = st.session_state.rag_system.ask(query)
                    st.session_state.last_question = query
                    st.session_state.last_answer = answer
                    return True
                except Exception as e:
                    st.error(f"검색 중 오류가 발생했습니다: {e}")
                    return False
        else:
            st.warning("⚠️ 질문을 입력해주세요.")
            return False
    
    # 검색 버튼 클릭 또는 예시 질문 선택 시 검색 실행
    should_search = False
    current_question = question
    
    if search_clicked:
        should_search = True
        current_question = question
    elif 'selected_question' in st.session_state and st.session_state.selected_question:
        should_search = True
        current_question = st.session_state.selected_question
        # 선택된 질문 초기화
        st.session_state.selected_question = ""
    
    if should_search:
        perform_search(current_question)
    
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
            st.session_state.selected_question = eq
            st.rerun()
    
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
            test_result = st.session_state.rag_system.search_documents("test", top_k=1)
            if test_result:
                st.success("✅ 시스템이 정상적으로 작동하고 있습니다!")
                st.info(f"📊 검색 가능한 문서: {len(test_result)}개 확인됨")
            else:
                st.warning("⚠️ 문서를 찾을 수 없습니다. 인덱스를 확인해주세요.")
        except Exception as e:
            st.error(f"❌ 시스템 오류: {e}")

# 하단 정보
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666; font-size: 0.8em;'>
        🚀 Powered by Azure OpenAI & Azure AI Search<br>
        📖 DSCore UX Frame 표준정책서 기반
    </div>
    """, 
    unsafe_allow_html=True
)
