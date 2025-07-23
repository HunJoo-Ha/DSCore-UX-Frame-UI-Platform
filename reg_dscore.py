import os
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv

# openai 버전 호환성 처리
try:
    # openai 1.0+ 버전
    from openai import AzureOpenAI
    USE_NEW_OPENAI = True
except ImportError:
    # openai 0.x 버전
    import openai
    USE_NEW_OPENAI = False

# 로컬 개발환경에서만 .env 파일 로드
if os.path.exists('.env'):
    load_dotenv()

class RAGSystem:
    def __init__(self):
        # 환경 변수 확인
        required_vars = [
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_API_KEY", 
            "AZURE_OPENAI_DEPLOYMENT_NAME",
            "AZURE_SEARCH_ENDPOINT",
            "AZURE_SEARCH_INDEX_NAME",
            "AZURE_SEARCH_API_KEY"
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise Exception(f"필수 환경 변수가 설정되지 않았습니다: {', '.join(missing_vars)}")
        
        # OpenAI 클라이언트 설정 (버전별 처리)
        if USE_NEW_OPENAI:
            # openai 1.0+ 버전
            self.openai_client = AzureOpenAI(
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version="2024-02-01"
            )
        else:
            # openai 0.x 버전
            openai.api_type = "azure"
            openai.api_base = os.getenv("AZURE_OPENAI_ENDPOINT")
            openai.api_version = "2024-02-01"
            openai.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        
        self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        
        # Azure Search 클라이언트
        self.search_client = SearchClient(
            endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
            index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
            credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_API_KEY"))
        )
        
        # 초기화 시 인덱스 상태 확인
        self._debug_index()
    
    def _debug_index(self):
        """인덱스 상태를 디버깅하는 함수"""
        try:
            print("=== 인덱스 디버깅 시작 ===")
            
            # 1. 전체 문서 수 확인
            count_results = self.search_client.search(
                search_text="*",
                include_total_count=True,
                top=0
            )
            total_count = count_results.get_count()
            print(f"총 문서 수: {total_count}")
            
            if total_count == 0:
                print("⚠️ 인덱스에 문서가 없습니다!")
                return
            
            # 2. 샘플 문서 확인
            sample_results = self.search_client.search(
                search_text="*",
                top=3
            )
            
            print("\n=== 샘플 문서들 ===")
            for i, doc in enumerate(sample_results):
                print(f"\n--- 문서 {i+1} ---")
                print(f"필드들: {list(doc.keys())}")
                
                for field_name, field_value in doc.items():
                    if isinstance(field_value, str):
                        preview = field_value[:100] + "..." if len(field_value) > 100 else field_value
                        print(f"  {field_name}: {preview}")
                    else:
                        print(f"  {field_name}: {type(field_value)} - {field_value}")
                        
                # 첫 번째 문서만 자세히 보기
                if i == 0:
                    self.content_field = self._find_content_field(doc)
                    print(f"\n✅ 사용할 콘텐츠 필드: {self.content_field}")
                    
        except Exception as e:
            print(f"디버깅 중 오류: {e}")
            self.content_field = None
    
    def _find_content_field(self, sample_doc):
        """실제 콘텐츠가 들어있는 필드를 찾는 함수"""
        # 일반적인 콘텐츠 필드명들
        content_field_candidates = [
            "content", "merged_content", "text", "body", "document", 
            "extracted_content", "description", "content_text"
        ]
        
        # 1. 일반적인 필드명 확인
        for field in content_field_candidates:
            if field in sample_doc:
                content = sample_doc.get(field, "")
                if isinstance(content, str) and len(content.strip()) > 50:
                    print(f"  ✅ '{field}' 필드 찾음 (길이: {len(content)})")
                    return field
        
        # 2. 가장 긴 텍스트 필드 찾기
        text_fields = {}
        for field_name, field_value in sample_doc.items():
            if isinstance(field_value, str) and len(field_value.strip()) > 20:
                text_fields[field_name] = len(field_value)
        
        if text_fields:
            longest_field = max(text_fields, key=text_fields.get)
            print(f"  ✅ 가장 긴 텍스트 필드 '{longest_field}' 사용 (길이: {text_fields[longest_field]})")
            return longest_field
        
        print("  ❌ 적절한 콘텐츠 필드를 찾을 수 없음")
        return None
    
    def search_documents(self, query, top_k=3):
        """문서 검색"""
        try:
            print(f"\n=== 검색 시작: '{query}' ===")
            
            if not hasattr(self, 'content_field') or not self.content_field:
                print("❌ 콘텐츠 필드가 설정되지 않음")
                return []
            
            # 검색 실행
            results = self.search_client.search(
                search_text=query,
                top=top_k
            )
            
            documents = []
            result_count = 0
            
            for result in results:
                result_count += 1
                content = result.get(self.content_field, "")
                
                print(f"검색 결과 {result_count}:")
                print(f"  필드: {self.content_field}")
                print(f"  내용: {str(content)[:200]}...")
                
                if content and len(str(content).strip()) > 0:
                    documents.append(str(content))
            
            print(f"✅ 총 {result_count}개 검색됨, {len(documents)}개 유효")
            return documents
            
        except Exception as e:
            print(f"❌ 검색 오류: {e}")
            return []
    
    def generate_answer(self, query, context):
        """답변 생성 (버전별 처리)"""
        if not context:
            return "죄송합니다. 관련 문서를 찾을 수 없습니다."
        
        prompt = f"""
다음 UI 컴포넌트 문서를 바탕으로 질문에 답변하세요:

문서 내용:
{context}

질문: {query}

답변 규칙:
- 컴포넌트의 사용법, Props, 예시 코드 등을 포함하여 답변하세요
- 코드 예시가 있다면 마크다운 형식으로 보여주세요
- 간결하고 실용적인 정보를 제공하세요

답변:
"""
        
        try:
            print("=== OpenAI 답변 생성 중 ===")
            
            if USE_NEW_OPENAI:
                # openai 1.0+ 버전
                response = self.openai_client.chat.completions.create(
                    model=self.deployment_name,
                    messages=[
                        {"role": "system", "content": "당신은 UI 컴포넌트 문서를 바탕으로 개발자들에게 도움이 되는 답변을 제공하는 AI 어시스턴트입니다."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=1500
                )
                answer = response.choices[0].message.content
            else:
                # openai 0.x 버전
                response = openai.ChatCompletion.create(
                    engine=self.deployment_name,
                    messages=[
                        {"role": "system", "content": "당신은 UI 컴포넌트 문서를 바탕으로 개발자들에게 도움이 되는 답변을 제공하는 AI 어시스턴트입니다."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=1500
                )
                answer = response.choices[0].message.content
            
            print(f"✅ 답변 생성 완료 (길이: {len(answer)})")
            return answer
            
        except Exception as e:
            print(f"❌ 답변 생성 오류: {e}")
            return f"답변 생성 중 오류가 발생했습니다: {e}"
    
    def ask(self, query):
        """RAG 파이프라인 실행"""
        try:
            print(f"\n🔍 질문: {query}")
            
            # 1. 문서 검색
            relevant_docs = self.search_documents(query)
            
            if not relevant_docs:
                return "검색 결과가 없습니다. 다른 키워드로 검색해보세요."
            
            # 2. 컨텍스트 구성
            context = "\n\n".join(relevant_docs[:3])
            print(f"📝 컨텍스트 길이: {len(context)}")
            
            # 3. 답변 생성
            answer = self.generate_answer(query, context)
            
            return answer
            
        except Exception as e:
            print(f"❌ 전체 프로세스 오류: {e}")
            return f"오류가 발생했습니다: {e}"

if __name__ == "__main__":
    rag = RAGSystem()
    
    while True:
        question = input("\n질문을 입력하세요 (종료: 'quit'): ")
        if question.lower() == 'quit':
            break
        
        answer = rag.ask(question)
        print(f"\n답변: {answer}")