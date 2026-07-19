from abc import ABC, abstractmethod


class AiClient(ABC):
    @abstractmethod
    def generate_script(self, source: str) -> str:
        """
        뉴스 요약 내용을 바탕으로 스크립트를 생성한다.
        """
        pass
