from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from script_app.ai_client import (
    AiResponseInvalidError,
    OpenAiClient,
    create_openai_client,
    load_common_section_prompt,
    load_personal_sections_prompt,
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

    def test_prompts_define_target_reading_times(self) -> None:
        common_prompt = load_common_section_prompt()
        personal_prompt = load_personal_sections_prompt()

        assert "약 1분" in common_prompt
        assert "300~350자" in common_prompt
        assert "공백 포함" in common_prompt
        assert "최대 10건" in common_prompt
        assert "핵심 사건 2~3개만 선정" in common_prompt
        assert "선정하지 않은 뉴스는 생략" in common_prompt
        assert "전체 lines는 2~4개의 발화" in common_prompt
        assert "하나의 설명 흐름으로 압축" in common_prompt
        assert "모든 사업 영역을 빠짐없이" in common_prompt
        assert "확인된 사실처럼 바꾸지 마세요" in common_prompt
        assert "업종 전체의 수요" in common_prompt
        assert "해당 기업의 실적과 사업" in common_prompt
        assert "지난 24시간의 핵심 뉴스" in common_prompt
        assert "오늘 이후 확인할 관전 포인트" in common_prompt
        assert "호재나 악재로 단정하지 말고" in common_prompt
        assert "글자 수를 스스로 확인" in common_prompt
        assert "중요도가 가장 낮은 세부 정보" in common_prompt
        assert "기호 % 대신 퍼센트" in common_prompt
        assert "opening의 두 발화는 합계 약 1분" in (
            personal_prompt
        )
        assert "코스와 코미의 짧은 상호 인사" in (
            personal_prompt
        )
        assert "모든 브리핑은 아침" in personal_prompt
        assert "남아 있는 불확실성" in (
            personal_prompt
        )
        assert "행동해야 하는 체크리스트" in personal_prompt
        assert "행동 지침처럼 표현하지 마세요" in (
            personal_prompt
        )
        assert "코스피" not in personal_prompt
        assert "코스닥" not in personal_prompt
        assert "관심 키워드" not in personal_prompt
        assert "약 10초" in personal_prompt
        assert "50~60자" in personal_prompt
        assert "closing은 약 30초" in personal_prompt
        assert "150~175자" in personal_prompt
        assert "기호 % 대신 퍼센트" in personal_prompt

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
