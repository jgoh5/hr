import streamlit as st
from openai import OpenAI
import fitz  # PyMuPDF (PDF parsing)
import re

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------------------------
# PDF → 지원자 정보 추출
# ---------------------------
def parse_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text("text")

    applicant = {}
    # 성별
    if "남" in text[:200]:
        applicant["성별"] = "남성"
    elif "여" in text[:200]:
        applicant["성별"] = "여성"
    else:
        applicant["성별"] = "미상"

    # 대학교/전공
    uni_match = re.search(r"(대학교.*)", text)
    applicant["대학교"] = uni_match.group(0) if uni_match else "미상"

    # 학력
    if "학사" in text:
        applicant["학력"] = "학사"
    elif "석사" in text:
        applicant["학력"] = "석사"
    elif "박사" in text:
        applicant["학력"] = "박사"
    else:
        applicant["학력"] = "미상"

    # 경력
    if "인턴" in text:
        applicant["경력"] = "인턴 경험 있음"
    elif "재직" in text:
        applicant["경력"] = "경력자"
    else:
        applicant["경력"] = "신입"

    # 영어
    if "TOEIC" in text or "토익" in text:
        score_match = re.search(r"TOEIC\s?(\d+)", text)
        if score_match:
            applicant["영어"] = f"TOEIC {score_match.group(1)}"
        else:
            applicant["영어"] = "영어 점수 기재"
    elif "Intermediate" in text:
        applicant["영어"] = "Intermediate"
    elif "Advanced" in text:
        applicant["영어"] = "Advanced"
    else:
        applicant["영어"] = "미상"

    return applicant, text[:2000]

# ---------------------------
# 정량 점수 계산 (간단 버전)
# ---------------------------
def calculate_score(applicant):
    total = 0
    reasons = []

    # 학력
    if applicant.get("학력") == "박사":
        score = 100
    elif applicant.get("학력") == "석사":
        score = 85
    elif applicant.get("학력") == "학사":
        score = 70
    else:
        score = 50
    total += score * 0.3
    reasons.append(f"학력: {applicant.get('학력')} → {score}점")

    # 경력
    if "경력자" in applicant.get("경력", ""):
        score = 90
    elif "인턴" in applicant.get("경력", ""):
        score = 70
    else:
        score = 50
    total += score * 0.3
    reasons.append(f"경력: {applicant.get('경력')} → {score}점")

    # 영어
    eng = applicant.get("영어", "")
    if "900" in eng or "Advanced" in eng:
        score = 90
    elif "800" in eng or "Intermediate" in eng:
        score = 70
    elif eng != "미상":
        score = 60
    else:
        score = 40
    total += score * 0.4
    reasons.append(f"영어: {eng} → {score}점")

    final_score = round(total, 1)
    return final_score, reasons

# ---------------------------
# GPT 평가
# ---------------------------
def evaluate_applicant(applicant, raw_text, quant_score, reasons):
    prompt = f"""
    당신은 채용 담당자입니다. 다음 지원자의 서류를 요약하고 평가하세요.

    1. 지원자 요약 (2줄)
    - 첫째 줄: "지원자 요약 (성별/대학교/경력/어학능력)"
    - 둘째 줄: 성별, 대학교·전공, 경력, 영어능력을 '/' 로 구분해 한 줄로 요약

    2. 합격 가능성 점수 (정량 점수 {quant_score}점 참고)

    3. 한 줄 코멘트 (합격이면 이유, 불합격이면 보완 필요사항)

    [정량 점수 근거]
    {reasons}

    [지원자 정보]
    {applicant}

    [이력서 일부]
    {raw_text}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an HR assistant who evaluates resumes."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4
    )
    return response.choices[0].message.content

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="HR AI 이력서 평가", layout="wide")
st.title("📋 HR AI 이력서 평가 데모 (정량+정성)")

uploaded_file = st.file_uploader("지원자 이력서를 업로드하세요 (PDF)", type=["pdf"])

if uploaded_file is not None:
    applicant, raw_text = parse_pdf(uploaded_file)

    st.subheader("📑 추출된 기본 정보")
    st.json(applicant)

    # 정량 점수
    score, reasons = calculate_score(applicant)
    st.subheader("📊 정량 점수 계산")
    st.write(f"최종 점수: **{score}점**")
    for r in reasons:
        st.write("-", r)

    # GPT 분석
    with st.spinner("AI가 이력서를 평가 중입니다..."):
        result = evaluate_applicant(applicant, raw_text, score, reasons)

    st.subheader("🔎 AI 분석 결과")
    st.write(result)
