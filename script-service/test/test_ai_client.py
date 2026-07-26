from unittest.mock import AsyncMock, Mock

import pytest

from script_app.ai_client import (
    SCRIPT_INSTRUCTIONS,
    OpenAiClient,
)


class TestOpenAiClient:
    @pytest.mark.asyncio
    async def test_generate_script_calls_openai_responses_api(
        self,
    ) -> None:
        # given
        sdk_client = Mock()

        sdk_response = Mock()
        sdk_response.output_text = (
            "오늘 삼성전자 관련 주요 뉴스를 전해드립니다."
        )

        sdk_client.responses.create = AsyncMock(
            return_value=sdk_response
        )

        ai_client = OpenAiClient(
            client=sdk_client,
            model="test-model",
        )

        source = (
            "종목 ID: 1\n\n"
            "[뉴스 1]\n"
            "제목: 삼성전자 반도체 투자 확대\n"
            "요약: 삼성전자가 반도체 투자를 확대했다."
        )

        # when
        result = await ai_client.generate_script(source)

        # then
        assert result == (
            "오늘 삼성전자 관련 주요 뉴스를 전해드립니다."
        )

        sdk_client.responses.create.assert_awaited_once_with(
            model="test-model",
            instructions=SCRIPT_INSTRUCTIONS,
            input=source,
        )
