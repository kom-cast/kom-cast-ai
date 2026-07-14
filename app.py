import streamlit as st

st.set_page_config(
    page_title="KomCast AI",
    page_icon="🎙️",
)

st.title("🎙️ KomCast AI")
st.write("제공된 뉴스를 요약하고 팟캐스트 스크립트를 생성합니다.")

if st.button("브리핑 생성하기"):
    st.success("브리핑 생성 완료")

    st.subheader("뉴스 요약")
    st.write("AI 반도체 시장의 성장과 HBM 수요 증가가 예상됩니다.")

    st.subheader("팟캐스트 스크립트")
    st.write(
        """
        안녕하세요. 오늘의 금융 뉴스 브리핑입니다.

        오늘은 AI 반도체 시장과 HBM 수요에 대해 살펴보겠습니다.

        생성형 AI 투자가 확대되면서 AI 서버에 필요한 고대역폭 메모리 수요도
        함께 증가할 가능성이 있습니다.

        지금까지 오늘의 브리핑이었습니다.
        """
    )
