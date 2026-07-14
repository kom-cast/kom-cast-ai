import pandas as pd
import streamlit as st

from datetime import datetime

from seed import seed_news
from services import NewsService, ScriptService, SummaryService


st.set_page_config(
    page_title="KomCast AI",
    page_icon="🎙️",
    layout="wide",
)

# 애플리케이션 시작 시 초기 뉴스 삽입
seed_news()

news_service = NewsService()
summary_service = SummaryService()
script_service = ScriptService()


st.title("🎙️ KomCast AI")
st.caption("뉴스 요약 및 팟캐스트 스크립트 생성 시안")


news_tab, summary_tab, script_tab = st.tabs(
    [
        "뉴스 추가",
        "뉴스 요약",
        "스크립트 생성",
    ]
)

with news_tab:
    st.header("뉴스 추가")

    with st.form("news_create_form", clear_on_submit=True):
        title = st.text_input(
            "뉴스 제목",
            placeholder="뉴스 제목을 입력하세요.",
        )

        content = st.text_area(
            "뉴스 내용",
            placeholder="뉴스 내용을 입력하세요.",
            height=250,
        )

        published_date = st.date_input(
            "뉴스 생성 날짜",
            value=datetime.now().date(),
        )

        published_time = st.time_input(
            "뉴스 생성 시간",
            value=datetime.now().time().replace(
                second=0,
                microsecond=0,
            ),
        )

        submit_button = st.form_submit_button(
            "뉴스 저장",
            use_container_width=True,
        )

    if submit_button:
        try:
            published_at = datetime.combine(
                published_date,
                published_time,
            )

            news = news_service.create_news(
                title=title,
                content=content,
                published_at=published_at,
            )

            st.success(
                f"뉴스가 저장되었습니다. "
                f"뉴스 ID: {news.id}"
            )

        except ValueError as error:
            st.warning(str(error))

        except Exception as error:
            st.error(
                f"뉴스 저장 중 오류가 발생했습니다: {error}"
            )

with summary_tab:
    st.header("뉴스 요약")

    col1, col2 = st.columns(2)

    with col1:
        summarize_button = st.button(
            "요약하기",
            use_container_width=True,
        )

    with col2:
        show_summary_button = st.button(
            "요약본 확인",
            use_container_width=True,
        )

    if summarize_button:
        try:
            result = summary_service.summarize_unsummarized_news()

            if result.created_count == 0:
                st.info("새롭게 요약할 뉴스가 없습니다.")
            else:
                st.success(
                    f"{result.created_count}개의 뉴스 요약을 저장했습니다."
                )

        except Exception as error:
            st.error(f"요약 처리 중 오류가 발생했습니다: {error}")

    if show_summary_button:
        summaries = summary_service.get_all_summaries()

        if not summaries:
            st.info("저장된 요약본이 없습니다.")

        else:
            summary_rows = [
                {
                    "뉴스 ID": summary.news.id,
                    "제목": summary.news.title,
                    "뉴스 생성 시간": summary.news.published_at,
                    "요약": summary.content,
                    "요약 생성 시간": summary.created_at,
                }
                for summary in summaries
            ]

            dataframe = pd.DataFrame(summary_rows)

            st.dataframe(
                dataframe,
                use_container_width=True,
                hide_index=True,
            )


with script_tab:
    st.header("스크립트 생성")

    st.info(
        "현재는 저장된 모든 요약본을 사용합니다. "
        "추후 시간과 주제 필터를 연결할 수 있습니다."
    )

    if st.button(
        "스크립트 생성",
        use_container_width=True,
    ):
        try:
            script = script_service.create_script()

            st.success("스크립트를 생성하고 저장했습니다.")

            st.text_area(
                label="생성된 스크립트",
                value=script.content,
                height=400,
            )

            st.download_button(
                label="스크립트 다운로드",
                data=script.content,
                file_name="komcast_script.txt",
                mime="text/plain",
                use_container_width=True,
            )

        except ValueError as error:
            st.warning(str(error))

        except Exception as error:
            st.error(f"스크립트 생성 중 오류가 발생했습니다: {error}")