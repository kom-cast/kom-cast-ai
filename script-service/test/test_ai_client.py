from unittest.mock import AsyncMock, Mock

import pytest

from script_app.ai_client import AiResponseInvalidError, OpenAiClient
from script_app.schemas import (
    CommonSectionAiResponse,
    PersonalSectionsAiResponse,
)


class TestOpenAiClient:
    @pytest.mark.asyncio
    async def test_generate_script_calls_openai_responses_api(
        self, monkeypatch
    ) -> None:
        # given
        fake_instructions = "가짜 프롬프트 지침"
        monkeypatch.setattr(
            "script_app.ai_client.load_prompt",
            lambda: fake_instructions,
        )

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
            instructions=fake_instructions,
            input=source,
        )

    @pytest.mark.asyncio
    async def test_generate_common_section_uses_structured_output(
        self,
        monkeypatch,
    ) -> None:
        monkeypatch.setattr(
            "script_app.ai_client.load_common_section_prompt",
            lambda: "공통 섹션 프롬프트",
        )
        parsed_response = CommonSectionAiResponse(
            lines=[
                {
                    "talker": "코스",
                    "content": "주요 소식을 살펴보겠습니다.",
                }
            ]
        )
        sdk_response = Mock(output_parsed=parsed_response)
        sdk_client = Mock()
        sdk_client.responses.parse = AsyncMock(
            return_value=sdk_response
        )
        ai_client = OpenAiClient(
            client=sdk_client,
            model="test-model",
        )

        result = await ai_client.generate_common_section(
            "공통 섹션 입력"
        )

        assert result is parsed_response
        sdk_client.responses.parse.assert_awaited_once_with(
            model="test-model",
            instructions="공통 섹션 프롬프트",
            input="공통 섹션 입력",
            text_format=CommonSectionAiResponse,
        )

    @pytest.mark.asyncio
    async def test_generate_personal_sections_validates_bridges(
        self,
        monkeypatch,
    ) -> None:
        monkeypatch.setattr(
            "script_app.ai_client.load_personal_sections_prompt",
            lambda: "사용자 섹션 프롬프트",
        )
        parsed_response = PersonalSectionsAiResponse(
            opening=[
                {
                    "talker": "코스",
                    "content": "브리핑을 시작하겠습니다.",
                }
            ],
            bridges=[
                [
                    {
                        "talker": "코스",
                        "content": "다음 소식입니다.",
                    }
                ]
            ],
            closing=[
                {
                    "talker": "코미",
                    "content": "브리핑을 마치겠습니다.",
                }
            ],
        )
        sdk_response = Mock(output_parsed=parsed_response)
        sdk_client = Mock()
        sdk_client.responses.parse = AsyncMock(
            return_value=sdk_response
        )
        ai_client = OpenAiClient(
            client=sdk_client,
            model="test-model",
        )

        result = await ai_client.generate_personal_sections(
            "사용자 섹션 입력",
            content_section_count=2,
        )

        assert result is parsed_response
        sdk_client.responses.parse.assert_awaited_once_with(
            model="test-model",
            instructions="사용자 섹션 프롬프트",
            input="사용자 섹션 입력",
            text_format=PersonalSectionsAiResponse,
        )

    @pytest.mark.asyncio
    async def test_generate_common_section_rejects_unparsed_output(
        self,
    ) -> None:
        sdk_client = Mock()
        sdk_client.responses.parse = AsyncMock(
            return_value=Mock(output_parsed=None)
        )
        ai_client = OpenAiClient(
            client=sdk_client,
            model="test-model",
        )

        with pytest.raises(AiResponseInvalidError):
            await ai_client.generate_common_section("입력")

    @pytest.mark.asyncio
    async def test_generate_personal_sections_rejects_wrong_bridges(
        self,
    ) -> None:
        parsed_response = PersonalSectionsAiResponse(
            opening=[
                {
                    "talker": "코스",
                    "content": "브리핑을 시작하겠습니다.",
                }
            ],
            bridges=[],
            closing=[
                {
                    "talker": "코미",
                    "content": "브리핑을 마치겠습니다.",
                }
            ],
        )
        sdk_client = Mock()
        sdk_client.responses.parse = AsyncMock(
            return_value=Mock(output_parsed=parsed_response)
        )
        ai_client = OpenAiClient(
            client=sdk_client,
            model="test-model",
        )

        with pytest.raises(
            AiResponseInvalidError,
            match="bridge count",
        ):
            await ai_client.generate_personal_sections(
                "입력",
                content_section_count=2,
            )
