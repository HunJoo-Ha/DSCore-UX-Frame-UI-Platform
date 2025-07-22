import os
from openai import AzureOpenAI
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv

load_dotenv()

class RAGSystem:
    def __init__(self):
        # Azure OpenAI 클라이언트
        self.openai_client = AzureOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2024-02-01"
        )
        
        # Azure Search 클라이언트
        self.search_client = SearchClient(
            endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
            index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
            credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_API_KEY"))
        )
    
    def get_index_fields(self):
        """인덱스의 실제 필드명을 확인"""
        try:
            results = self.search_client.search(
                search_text="*",
                top=1,
                include_total_count=True
            )
            
            for result in results:
                print("사용 가능한 필드:", list(result.keys()))
                return list(result.keys())
        except Exception as e:
            print(f"필드 확인 오류: {e}")
            return []
    
    def search_documents(self, query, top_k=3):
        """문서 검색 - 실제 필드명 사용"""
        try:
            # 먼저 필드명 확인
            sample_results = self.search_client.search(
                search_text="*",
                top=1
            )
            
            available_fields = []
            for result in sample_results:
                available_fields = list(result.keys())
                break
            
            print(f"사용 가능한 필드: {available_fields}")
            
            # 텍스트 콘텐츠가 들어있을 가능성이 높은 필드들
            content_fields = [
                "content_text", "content", "merged_content", "text", "body", 
                "document", "extracted_content", "people", 
                "organizations", "locations"
            ]
            
            # 실제 존재하는 콘텐츠 필드 찾기
            actual_content_field = None
            for field in content_fields:
                if field in available_fields:
                    actual_content_field = field
                    break
            
            if not actual_content_field:
                print("콘텐츠 필드를 찾을 수 없습니다. 사용 가능한 필드:", available_fields)
                return []
            
            print(f"사용할 콘텐츠 필드: {actual_content_field}")
            
            # 검색 실행 (디버깅 정보 추가)
            results = self.search_client.search(
                search_text=query,
                top=top_k,
                select=[actual_content_field]
            )
            
            documents = []
            result_count = 0
            for result in results:
                result_count += 1
                content = result.get(actual_content_field, "")
                print(f"검색 결과 {result_count}: {str(content)[:200]}...")
                
                if content and len(str(content).strip()) > 0:
                    documents.append(str(content))
            
            print(f"총 검색 결과: {result_count}개, 유효한 문서: {len(documents)}개")
            
            # 검색 결과가 없으면 전체 문서에서 가져오기
            if not documents:
                print("검색 결과가 없어서 전체 문서에서 샘플 가져오기...")
                all_results = self.search_client.search(
                    search_text="*",
                    top=top_k,
                    select=[actual_content_field]
                )
                
                for result in all_results:
                    content = result.get(actual_content_field, "")
                    if content and len(str(content).strip()) > 0:
                        documents.append(str(content))
                        print(f"샘플 문서: {str(content)[:200]}...")
            
            return documents
            
        except Exception as e:
            print(f"검색 오류: {e}")
            return []
    
    def generate_answer(self, query, context):
        """답변 생성 (UI 컴포넌트 문서용)"""
        if not context:
            return "죄송합니다. 관련 문서를 찾을 수 없습니다. 인덱스가 올바르게 설정되었는지 확인해주세요."
        
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
        
        response = self.openai_client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            messages=[
                {"role": "system", "content": "당신은 UI 컴포넌트 문서를 바탕으로 개발자들에게 도움이 되는 답변을 제공하는 AI 어시스턴트입니다. 코드 예시와 실용적인 사용법을 포함하여 답변하세요."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1500
        )
        
        return response.choices[0].message.content
    
    def ask(self, query):
        """RAG 파이프라인 실행"""
        try:
            # 1. 문서 검색
            relevant_docs = self.search_documents(query)
            
            if not relevant_docs:
                return "검색 결과가 없습니다. 인덱스 설정을 확인해주세요."
            
            # 2. 컨텍스트 구성
            context = "\n\n".join(relevant_docs)
            
            # 3. 답변 생성
            answer = self.generate_answer(query, context)
            
            return answer
            
        except Exception as e:
            return f"오류가 발생했습니다: {e}"

# 디버깅을 위한 인덱스 정보 확인 함수
def debug_index():
    """인덱스 상태와 필드 정보 확인"""
    try:
        rag = RAGSystem()
        
        print("=== 인덱스 디버깅 정보 ===")
        
        # 1. 인덱스 내 문서 수 확인
        results = rag.search_client.search(
            search_text="*",
            include_total_count=True,
            top=0
        )
        print(f"총 문서 수: {results.get_count()}")
        
        # 2. 샘플 문서의 필드 확인
        sample = rag.search_client.search(search_text="*", top=1)
        for doc in sample:
            print(f"사용 가능한 필드: {list(doc.keys())}")
            for key, value in doc.items():
                print(f"  {key}: {str(value)[:100]}...")
            break
            
    except Exception as e:
        print(f"디버깅 오류: {e}")

# 터미널에서 테스트
if __name__ == "__main__":
    print("인덱스 정보를 확인하시겠습니까? (y/n): ")
    if input().lower() == 'y':
        debug_index()
    
    rag = RAGSystem()
    
    while True:
        question = input("\n질문을 입력하세요 (종료: 'quit'): ")
        if question.lower() == 'quit':
            break
        
        answer = rag.ask(question)
        print(f"\n답변: {answer}")
