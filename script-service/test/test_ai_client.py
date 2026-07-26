from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from script_app.ai_client import (
    AiResponseInvalidError,
    OpenAiClient,
    create_openai_client,
)
from script_app.config import ModelSettings, OpenAiSettings
from script_app.schemas import (
    CommonSectionAiResponse,
    PersonalSectionsAiResponse,
)


class TestOpenAiClient:
    @staticmethod
    def create_test_client(sdk_client: Mock) -> OpenAiClient:
        return OpenAiClient(
            client=sdk_client,
            common_model="common-model",
            common_reasoning_effort="medium",
            personal_model="personal-model",
            personal_reasoning_effort="none",
        )

    def test_create_client_applies_request_timeout(
        self,
        monkeypatch,
    ) -> None:
        sdk_client = Mock()
        async_openai = Mock(return_value=sdk_client)
        monkeypatch.setattr(
            "script_app.ai_client.AsyncOpenAI",
            async_openai,
        )
        monkeypatch.setattr(
            "script_app.ai_client.get_openai_settings",
            lambda profile="production": OpenAiSettings(
                api_key="test-key",
                timeout_seconds=45.0,
                common=ModelSettings(
                    model="common-model",
                    reasoning_effort="medium",
                ),
                personal=ModelSettings(
                    model="personal-model",
                    reasoning_effort="none",
                ),
            ),
        )

        client = create_openai_client()

        async_openai.assert_called_once_with(
            api_key="test-key",
            timeout=45.0,
        )
        assert client.client is sdk_client
        assert client.common_model == "common-model"
        assert client.personal_model == "personal-model"

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
        ai_client = self.create_test_client(sdk_client)

        result = await ai_client.generate_common_section(
            "공통 섹션 입력"
        )

        assert result is parsed_response
        sdk_client.responses.parse.assert_awaited_once_with(
            model="common-model",
            reasoning={"effort": "medium"},
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
        ai_client = self.create_test_client(sdk_client)

        result = await ai_client.generate_personal_sections(
            "사용자 섹션 입력",
            content_section_count=2,
        )

        assert result is parsed_response
        sdk_client.responses.parse.assert_awaited_once_with(
            model="personal-model",
            reasoning={"effort": "none"},
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
        ai_client = self.create_test_client(sdk_client)

        with pytest.raises(AiResponseInvalidError):
            await ai_client.generate_common_section("입력")

    @pytest.mark.asyncio
    async def test_generate_common_section_converts_validation_error(
        self,
    ) -> None:
        with pytest.raises(ValidationError) as error_info:
            CommonSectionAiResponse(lines=[])

        sdk_client = Mock()
        sdk_client.responses.parse = AsyncMock(
            side_effect=error_info.value
        )
        ai_client = self.create_test_client(sdk_client)

        with pytest.raises(
            AiResponseInvalidError,
            match="응답 형식이 올바르지 않습니다",
        ):
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
        ai_client = self.create_test_client(sdk_client)

        with pytest.raises(
            AiResponseInvalidError,
            match="bridge count",
        ):
            await ai_client.generate_personal_sections(
                "입력",
                content_section_count=2,
            )
