import os
import openai
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv

load_dotenv()

# OpenAI API 설정
openai.api_type = "azure"
openai.api_base = os.getenv("AZURE_OPENAI_ENDPOINT")
openai.api_key = os.getenv("AZURE_OPENAI_API_KEY")
openai.api_version = "2024-02-01"

class RAGSystem:
    def __init__(self):
        # Azure Search 클라이언트
        self.search_client = SearchClient(
            endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
            index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
            credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_API_KEY"))
        )
    
    def get_index_fields(self):
        try:
            results = self.search_client.search(
                search_text="*",
                top=1,
                include_total_count=True
            )
            for result in results:
                return list(result.keys())
        except Exception as e:
            print(f"필드 확인 오류: {e}")
            return []
    
    def search_documents(self, query, top_k=3):
        try:
            sample_results = self.search_client.search(search_text="*", top=1)
            available_fields = []
            for result in sample_results:
                available_fields = list(result.keys())
                break

            content_fields = [
                "content_text", "content", "merged_content", "text", "body", 
                "document", "extracted_content", "people", 
                "organizations", "locations"
            ]

            actual_content_field = None
            for field in content_fields:
                if field in available_fields:
                    actual_content_field = field
                    break

            if not actual_content_field:
                print("콘텐츠 필드를 찾을 수 없습니다. 사용 가능한 필드:", available_fields)
                return []

            results = self.search_client.search(
                search_text=query,
                top=top_k,
                select=[actual_content_field]
            )

            documents = []
            for result in results:
                content = result.get(actual_content_field, "")
                if content and len(str(content).strip()) > 0:
                    documents.append(str(content))

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
            return documents
            
        except Exception as e:
            print(f"검색 오류: {e}")
            return []

    def generate_answer(self, query, context):
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

        try:
            response = openai.ChatCompletion.create(
                engine=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 UI 컴포넌트 문서를 바탕으로 개발자들에게 도움이 되는 답변을 제공하는 AI 어시스턴트입니다. 코드 예시와 실용적인 사용법을 포함하여 답변하세요."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            return response["choices"][0]["message"]["content"]
        except Exception as e:
            return f"OpenAI 응답 오류: {e}"

    def ask(self, query):
        try:
            relevant_docs = self.search_documents(query)
            if not relevant_docs:
                return "검색 결과가 없습니다. 인덱스 설정을 확인해주세요."

            context = "\n\n".join(relevant_docs)
            answer = self.generate_answer(query, context)
            return answer
        except Exception as e:
            return f"오류가 발생했습니다: {e}"

# 테스트용 진입점
if __name__ == "__main__":
    rag = RAGSystem()
    while True:
        question = input("\n질문을 입력하세요 (종료: 'quit'): ")
        if question.lower() == 'quit':
            break
        answer = rag.ask(question)
        print(f"\n답변: {answer}")
