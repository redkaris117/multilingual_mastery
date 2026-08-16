import asyncio
import ctypes
import json
import os
import queue
import random
import subprocess
import tempfile
import threading
import time
import uuid
import wave
from datetime import datetime
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
import edge_tts
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
import sounddevice as sd

# ==========================================
# 0. API 및 UI 테마 초기화 (Soft Pastel Education)
# ==========================================
API_KEY = "AQ.Ab8RN6LF7vnGHquxDIC0oRs0zh9mmO8cbcfJCDoOIsBzB_99Ag"
client = genai.Client(api_key=API_KEY)
MODELS_POOL = [
    "gemini-3.5-flash-lite",     # 1순위: Gemini 3.5 Flash Lite (높은 쿼터 & 초고속)
    "gemini-3.1-flash-lite",     # 2순위: Gemini 3.1 Flash Lite (높은 쿼터 & 고속)
    "gemini-3-flash-preview",    # 3순위: Gemini 3 Flash
    "gemini-3.5-flash",          # 4순위: Gemini 3.5 Flash
    "gemini-3.7-flash",          # 5순위: Gemini 3.7 Flash
    "gemini-flash-lite-latest",   # 예비 백업: Flash Lite Latest
    "gemini-flash-latest"        # 예비 백업: Flash Latest
]

def generate_content_with_fallback(contents, config=None):
    """다중 모델 풀을 순회하여 Quota 초과나 에러 발생 시 자동으로 다음 모델을 호출하는 안전 함수"""
    last_err = None
    for model_name in MODELS_POOL:
        try:
            if config:
                res = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config
                )
            else:
                res = client.models.generate_content(
                    model=model_name,
                    contents=contents
                )
            return res
        except Exception as e:
            last_err = e
            print(f"⚠️ 모델 '{model_name}' 호출 실패 ({e}). 다음 백업 모델로 재시도합니다...")
            continue
    raise last_err if last_err else RuntimeError("모든 Gemini 모델 풀 호출에 실패했습니다.")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_FILE = os.path.join(BASE_DIR, "user_profile_multilang.json")
REVIEW_FILE = os.path.join(BASE_DIR, "review_notes_multilang.json")

ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("green")

# 🎨 눈이 편안한 소프트 파스텔 에듀테크 팔레트
THEME = {
    "app_bg": "#F8FAFC",          # 전체 배경 (Slate 50)
    "card_bg": "#FFFFFF",         # 카드 배경 (Pure White)
    "card_border": "#E2E8F0",     # 은은한 구분선 (Slate 200)
    
    # 톤다운 포인트 컬러
    "primary": "#38A169",         # 차분한 세이지 그린 (메인 액션)
    "primary_hover": "#2F855A",   
    "accent_blue": "#5B9BD5",     # 소프트 콘플라워 블루 (다시듣기)
    "accent_blue_hover": "#4682B4",
    "record_btn": "#E57373",      # 부드러운 코랄 로즈 (마이크 녹음)
    "record_hover": "#D32F2F",
    "purple_accent": "#9B86E8",   # 부드러운 파스텔 퍼플 (RPG)
    "purple_hover": "#8770DE",

    # 말풍선 및 코칭 카드
    "user_bubble": "#EBF7EE",     # 내 말풍선 (소프트 민트)
    "user_border": "#C3E6CB",     
    "ai_bubble": "#F1F5F9",       # AI 말풍선 (부드러운 슬레이트)
    "ai_border": "#E2E8F0",       
    "coach_bg": "#FEF9E7",        # 코칭 카드 배경 (따뜻한 밀크 바닐라)
    "coach_border": "#FDE8A1",    # 코칭 테두리
    "coach_accent": "#C07A10",    # 코칭 헤더 텍스트
    
    # 타이포그래피 컬러
    "text_main": "#1E293B",       # 선명하고 깔끔한 본문 (Slate 800)
    "text_sub": "#64748B"         # 보조 안내 텍스트 (Slate 500)
}

# ==========================================
# 1. 다국어 지원 엔진 설정 (4개 국어 & 성우 매핑)
# ==========================================
LANG_CONFIGS = {
    "🇺🇸 영어 (English)": {
        "key": "영어",
        "name_en": "English",
        "flag": "🇺🇸",
        "voices": {
            "여성 (Aria - 미국)": "en-US-AriaNeural",
            "여성 (Jenny - 자연스러움)": "en-US-JennyNeural",
            "남성 (Christopher - 미국)": "en-US-ChristopherNeural",
            "남성 (Ryan - 영국)": "en-GB-RyanNeural"
        },
        "default_voice": "en-US-ChristopherNeural",
        "input_placeholder": "영어로 메시지를 입력하세요 (엔터 전송)...",
        "rpg_placeholder": "공격 대사를 영어로 입력하세요 (엔터 전송)...",
        "custom_placeholder": "예: 뉴욕 스타벅스에서 원두 추천 및 맞춤 주문하기",
        "coaching_guide": "자연스러운 원어민 구어체와 표현 뉘앙스를 코칭하세요."
    },
    "🇯🇵 일본어 (日本語)": {
        "key": "일본어",
        "name_en": "Japanese",
        "flag": "🇯🇵",
        "voices": {
            "여성 (Nanami - 표준어)": "ja-JP-NanamiNeural",
            "여성 (Aoi - 차분함)": "ja-JP-AoiNeural",
            "남성 (Keita - 표준어)": "ja-JP-KeitaNeural",
            "남성 (Daichi - 신뢰감)": "ja-JP-DaichiNeural"
        },
        "default_voice": "ja-JP-KeitaNeural",
        "input_placeholder": "일본어로 메시지를 입력하세요 (엔터 전송)...",
        "rpg_placeholder": "공격 대사를 일본어로 입력하세요 (엔터 전송)...",
        "custom_placeholder": "예: 도쿄 지하철역에서 스이카 카드 충전 오류 해결하기",
        "coaching_guide": "자연스러운 일본어 표현을 코칭하고, 한자가 포함된 경우 모범 교정문에 히라가나 발음을 괄호로 병기하세요. (예: お願い(ねがい)します)"
    },
    "🇨🇳 중국어 (中文)": {
        "key": "중국어",
        "name_en": "Chinese (Mandarin)",
        "flag": "🇨🇳",
        "voices": {
            "여성 (Xiaoxiao - 표준어)": "zh-CN-XiaoxiaoNeural",
            "여성 (Xiaoyi - 부드러움)": "zh-CN-XiaoyiNeural",
            "남성 (Yunjian - 표준어)": "zh-CN-YunjianNeural",
            "남성 (Yunxi - 활기참)": "zh-CN-YunxiNeural"
        },
        "default_voice": "zh-CN-YunjianNeural",
        "input_placeholder": "중국어로 메시지를 입력하세요 (엔터 전송)...",
        "rpg_placeholder": "공격 대사를 중국어로 입력하세요 (엔터 전송)...",
        "custom_placeholder": "예: 상하이 카페에서 얼음 적게, 당도 30%로 음료 주문하기",
        "coaching_guide": "자연스러운 중국어 표준어 표현을 코칭하고, 모범 교정문 뒤에 한어병음(Pinyin)을 괄호로 병기하세요."
    },
    "🇪🇸 스페인어 (Español)": {
        "key": "스페인어",
        "name_en": "Spanish",
        "flag": "🇪🇸",
        "voices": {
            "여성 (Elvira - 스페인)": "es-ES-ElviraNeural",
            "남성 (Alvaro - 스페인)": "es-ES-AlvaroNeural",
            "여성 (Dalia - 멕시코)": "es-MX-DaliaNeural",
            "남성 (Jorge - 멕시코)": "es-MX-JorgeNeural"
        },
        "default_voice": "es-ES-AlvaroNeural",
        "input_placeholder": "스페인어로 메시지를 입력하세요 (엔터 전송)...",
        "rpg_placeholder": "공격 대사를 스페인어로 입력하세요 (엔터 전송)...",
        "custom_placeholder": "예: 마드리드 레스토랑에서 타파스와 상그리아 주문하기",
        "coaching_guide": "자연스러운 스페인어 원어민 표현 및 알맞은 직설법/접속법 뉘앙스를 코칭하세요."
    }
}

# ==========================================
# 2. 7단계 세분화 회화 레벨 (CEFR 기반 AI 지시어)
# ==========================================
DIFFICULTY_OPTIONS = {
    "Lv 1. 생존 입문 (A1 Starter)": {
        "level_code": "A1",
        "desc": "3~5단어의 아주 쉽고 짧은 단문 위주로 친절하게 응대하세요. 기초 단어만 말해도 의도를 파악하고 격려하며, 핵심 단어 연결 위주로 코칭하세요.",
        "complexity_guide": "상황은 매우 단순하고 직관적이어야 합니다. (단순 인사, 가격/수량 주문, 예약 확인)"
    },
    "Lv 2. 기초 일상 (A2 Elementary)": {
        "level_code": "A2",
        "desc": "일상 필수 기초 문장과 현재/과거 기본 시제를 사용하세요. 어색한 어순이나 기초 문법 오류를 친절하게 교정하세요.",
        "complexity_guide": "상황은 일상적인 선택과 문의입니다. (메뉴 변경, 시간/장소 확인, 기본 길찾기)"
    },
    "Lv 3. 실용 중급 (B1 Intermediate)": {
        "level_code": "B1",
        "desc": "자연스러운 원어민 구어체와 일상 연결어를 사용하세요. 직역투의 어색한 한국식 표현을 자연스러운 원어민 표현으로 교정하세요.",
        "complexity_guide": "상황은 세부 요청이나 의견 표현입니다. (좌석 변경, 추천 요청, 취향 설명)"
    },
    "Lv 4. 유창 심화 (B2 Upper-Intermediate)": {
        "level_code": "B2",
        "desc": "풍부한 어휘와 복합 문장, 다양한 감정/의견 표현을 구사하세요. 미세한 뉘앙스 차이와 더 세련된 어휘를 추천 코칭하세요.",
        "complexity_guide": "상황은 디테일한 조건 비교 및 설명입니다. (스펙 비교 질문, 일정 조율, 세부 규정 확인)"
    },
    "Lv 5. 비즈니스/전문 (C1 Advanced)": {
        "level_code": "C1",
        "desc": "격식 있고 정중하며 완곡한 프로페셔널 화법을 구사하세요. 비즈니스 에티켓과 세련된 협상/설득 표현 위주로 코칭하세요.",
        "complexity_guide": "상황은 공식 업무 및 협상입니다. (납기 연기 협상, 단가 조율, 연봉/성과 면담)"
    },
    "Lv 6. 원어민 심층 토론 (C2 Master)": {
        "level_code": "C2",
        "desc": "빠른 호흡과 원어민 관용구, 비유, 복합 논리를 전개하세요. 사소한 뉘앙스 오류나 조사 차이까지 완벽하게 원어민 수준으로 교정하세요.",
        "complexity_guide": "상황은 심도 있는 토론과 가치관 교환입니다. (전략 논박, 감상평 나눔, 까다로운 검증 방어)"
    },
    "Lv 7. 실전 돌발 위기극복 (Chaos Mode)": {
        "level_code": "Chaos",
        "desc": "상대방이 까다롭거나 매우 바쁘며 단호합니다. 예상치 못한 돌발 변수와 곤란한 문제를 던지고, 학습자가 논리적으로 위기를 극복하도록 집중 코칭하세요.",
        "complexity_guide": "상황은 분쟁/컴플레인/긴급 돌발 상황입니다. (오버부킹 피해, 분실물 신고, 하자 환불 분쟁, 시설 고장 항의)"
    }
}

# ==========================================
# 3. 대분류 카테고리 & 중분류 세부 활동 테마 (Anchor Themes)
# ==========================================
MASTER_CATEGORIES = {
    "✈️ 해외여행 (Travel)": [
        "🎲 [랜덤] 해외여행 즉흥 상황",
        "숙소 (호텔/에어비앤비/리조트 이용 및 요청)",
        "공항 및 기내 (탑승수속/좌석변경/수하물)",
        "교통편 (택시/기차/지하철/렌터카 이용)",
        "관광지 및 투어 (매표소/안내센터/길찾기)"
    ],
    "☕ 식당 및 카페 (Dining & Cafe)": [
        "🎲 [랜덤] 식당/카페 즉흥 상황",
        "카페 및 베이커리 (음료 커스텀 주문/자리/와이파이)",
        "식당 및 레스토랑 (메뉴 문의/주문/옵션/결제)",
        "고급 다이닝 (코스요리/예약/알레르기/와인 페어링)",
        "바 및 펍 (수제맥주/칵테일 추천/안주 페어링)"
    ],
    "💼 비즈니스 및 직장 (Business & Work)": [
        "🎲 [랜덤] 비즈니스 즉흥 상황",
        "사내 업무 및 상사 면담 (업무보고/휴가신청/연봉/인수인계)",
        "회의 및 프레젠테이션 (아젠다/의견제시/반박/Q&A 방어)",
        "협상 및 계약 조율 (단가조율/납기일정/SLA 조건)",
        "글로벌 네트워킹 및 컨퍼런스 (명함교환/협업/커피챗)"
    ],
    "🚨 위기대응 및 긴급 (Emergency & Crisis)": [
        "🎲 [랜덤] 위기대응 즉흥 상황",
        "병원 및 응급실 (증상 설명/진료/처방전/보험서류)",
        "약국 (상비약 구매/증상 설명/복용법 문의)",
        "경찰서 및 분실물 센터 (도난/소매치기/분실물 신고)",
        "대사관 및 출입국 심사 (여권 긴급 재발급/입국 인터뷰)"
    ],
    "🛒 실생활 및 쇼핑/계약 (Daily Life & Shopping)": [
        "🎲 [랜덤] 실생활 즉흥 상황",
        "쇼핑 및 매장 이용 (치수/색상/피팅룸/스펙 비교)",
        "환불 및 교환 (하자 교환/영수증 분실/Tax Refund)",
        "부동산 및 주거 계약 (임대차 계약/공과금/시설 수리 요청)",
        "서비스 가입 및 해지 (헬스장/통신사 요금제/구독 해지)"
    ],
    "🎉 소셜 및 친목/취미 (Social & Leisure)": [
        "🎲 [랜덤] 소셜 즉흥 상황",
        "파티 및 외국인 첫 만남 스몰토크",
        "취미 모임 (운동/보드게임/러닝 크루 활동)",
        "문화 토론 (영화/도서/음악 감상평 나누기)",
        "친목 약속 (주말 드라이브/맛집 나들이 제안)"
    ]
}

TIER_THRESHOLDS = [
    ("Bronze (Tourist)", 0, 200),
    ("Silver (City Hopper)", 200, 600),
    ("Gold (Communicator)", 600, 1200),
    ("Platinum (Negotiator)", 1200, 2000),
    ("Diamond (Crisis Master)", 2000, 3000),
    ("Master (Native Flow)", 3000, 5000)
]

def get_safe_path(path: str) -> str:
    abs_path = os.path.abspath(path)
    buf = ctypes.create_unicode_buffer(500)
    if ctypes.windll.kernel32.GetShortPathNameW(abs_path, buf, 500):
        return buf.value
    return abs_path


# ==========================================
# 4. Pydantic 구조화 응답 스키마
# ==========================================
class TurnCoaching(BaseModel):
    recognized_user_text: str = Field(description="사용자가 실제로 말한 문장 전사 (해당 학습 언어)")
    is_flawless: bool = Field(description="문법과 뉘앙스가 해당 레벨 기준 원어민 수준으로 자연스러우면 True, 어색함/오류가 있으면 False")
    corrected_sentence: str = Field(description="해당 레벨 및 학습 언어에 가장 어울리는 원어민 추천 모범 교정 문장")
    korean_feedback: str = Field(description="어색한 이유와 문법/뉘앙스 해설 (친절한 한국어)")

class TurnResponse(BaseModel):
    roleplay_reply: str = Field(description="상대방 역할로서의 해당 학습 언어 대답 (1~2문장)")
    reply_translation: str = Field(description="상대방 대답(roleplay_reply)의 자연스럽고 정확한 한국어 번역")
    coaching: TurnCoaching = Field(description="사용자 발화에 대한 한국어 코칭 데이터")

class DynamicScenarioSchema(BaseModel):
    title: str = Field(description="시나리오 제목 (한국어)")
    category: str = Field(description="카테고리 명칭 (한국어)")
    role: str = Field(description="상대방 AI의 역할과 이름 (예: Front Desk Clerk - Alex)")
    voice_gender: str = Field(description="'female' 또는 'male'")
    context: str = Field(description="구체적 상황 배경 및 사용자의 달성 목표 (한국어)")
    opening: str = Field(description="상황극을 시작하는 상대방의 첫 대사 (반드시 선택된 대상 언어로 1~2문장)")
    opening_translation: str = Field(description="상대방의 첫 대사(opening)에 대한 자연스럽고 정확한 한국어 번역")


# ==========================================
# 5. 고품질 다국어 오디오 엔진 (Edge-TTS)
# ==========================================
def play_tts_sound(text: str, voice: str):
    unique_id = uuid.uuid4().hex[:8]
    temp_dir = tempfile.gettempdir()
    temp_mp3 = os.path.join(temp_dir, f"tts_{unique_id}.mp3")

    async def _generate():
        comm = edge_tts.Communicate(text, voice)
        await comm.save(temp_mp3)

    try:
        asyncio.run(_generate())
        safe_uri = os.path.abspath(temp_mp3).replace("\\", "/")
        ps_cmd = (
            f'Add-Type -AssemblyName presentationCore; '
            f'$p = New-Object System.Windows.Media.MediaPlayer; '
            f'$p.Open([System.Uri]"file:///{safe_uri}"); '
            f'$p.Play(); '
            f'$timeout = 0; '
            f'while (-not $p.NaturalDuration.HasTimeSpan -and $timeout -lt 40) {{ Start-Sleep -Milliseconds 100; $timeout++ }}; '
            f'while ($p.NaturalDuration.HasTimeSpan -and ($p.Position -lt $p.NaturalDuration.TimeSpan)) {{ Start-Sleep -Milliseconds 100 }}; '
            f'$p.Close()'
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=True)
    except Exception as e:
        print(f"⚠️ 음성 재생 실패: {e}")
    finally:
        if os.path.exists(temp_mp3):
            try:
                os.remove(temp_mp3)
            except Exception:
                pass


# ==========================================
# 6. CustomTkinter 다국어 GUI 애플리케이션
# ==========================================
class MultilingualMasteryApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("🌱 Multilingual Mastery AI - Premium Education")
        self.geometry("1180x920")
        self.minsize(1050, 780)
        self.configure(fg_color=THEME["app_bg"])

        # 상태 변수
        self.profiles = self.load_profiles()
        self.current_scenario = None
        self.chat_history = []
        self.is_recording = False
        self.audio_q = queue.Queue()
        self.audio_stream = None
        self.session_turns = 0
        self.session_flawless = 0
        self.new_mistakes = []

        # 다시 듣기(Replay) 상태 변수
        self.last_ai_reply_text = ""
        self.last_ai_reply_voice = "en-US-ChristopherNeural"

        self.create_widgets()

    def get_cur_lang_cfg(self):
        lang_name = self.opt_lang.get() if hasattr(self, 'opt_lang') else "🇺🇸 영어 (English)"
        return LANG_CONFIGS.get(lang_name, LANG_CONFIGS["🇺🇸 영어 (English)"])

    def get_current_profile(self):
        lang_key = self.get_cur_lang_cfg()["key"]
        if not isinstance(self.profiles, dict):
            self.profiles = {}
        if lang_key not in self.profiles or not isinstance(self.profiles[lang_key], dict):
            self.profiles[lang_key] = {"exp": 0, "tier": "Bronze (Tourist)", "total_turns": 0, "flawless_turns": 0}
        return self.profiles[lang_key]

    def load_profiles(self):
        default_single = {"exp": 0, "tier": "Bronze (Tourist)", "total_turns": 0, "flawless_turns": 0}
        default_all = {
            "영어": default_single.copy(),
            "일본어": default_single.copy(),
            "중국어": default_single.copy(),
            "스페인어": default_single.copy()
        }
        for p_path in [PROFILE_FILE, "user_profile_multilang.json"]:
            if os.path.exists(p_path):
                try:
                    with open(p_path, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                        if isinstance(loaded, dict):
                            if "exp" in loaded:
                                default_all["영어"] = loaded
                                return default_all
                            else:
                                for k in default_all:
                                    if k in loaded and isinstance(loaded[k], dict):
                                        default_all[k] = loaded[k]
                                return default_all
                except Exception:
                    pass
        return default_all

    def save_profile(self):
        prof = self.get_current_profile()
        exp = prof["exp"]
        if exp >= 3000:
            prof["tier"] = "Master (Native Flow)"
        elif exp >= 2000:
            prof["tier"] = "Diamond (Crisis Master)"
        elif exp >= 1200:
            prof["tier"] = "Platinum (Negotiator)"
        elif exp >= 600:
            prof["tier"] = "Gold (Communicator)"
        elif exp >= 200:
            prof["tier"] = "Silver (City Hopper)"
        else:
            prof["tier"] = "Bronze (Tourist)"

        try:
            with open(PROFILE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.profiles, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 프로필 저장 오류: {e}")
        self.update_all_headers()

    def load_reviews(self):
        if os.path.exists(REVIEW_FILE):
            try:
                with open(REVIEW_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def save_reviews(self, reviews):
        with open(REVIEW_FILE, "w", encoding="utf-8") as f:
            json.dump(reviews, f, ensure_ascii=False, indent=2)

    def create_widgets(self):
        # 상단 산뜻한 상태바
        self.header_frame = ctk.CTkFrame(
            self,
            height=52,
            corner_radius=14,
            fg_color=THEME["card_bg"],
            border_width=1,
            border_color=THEME["card_border"]
        )
        self.header_frame.pack(fill="x", padx=16, pady=(12, 6))

        self.lbl_global_tier = ctk.CTkLabel(
            self.header_frame,
            text="",
            font=ctk.CTkFont(family="Pretendard", size=13, weight="bold"),
            text_color=THEME["primary"]
        )
        self.lbl_global_tier.pack(side="left", padx=18)

        self.lbl_global_streak = ctk.CTkLabel(
            self.header_frame,
            text="🔥 3일 연속 완벽 학습 중",
            font=ctk.CTkFont(family="Pretendard", size=12, weight="bold"),
            text_color=THEME["coach_accent"]
        )
        self.lbl_global_streak.pack(side="right", padx=18)

        # 4대 탭 뷰
        self.tabview = ctk.CTkTabview(
            self,
            corner_radius=14,
            fg_color=THEME["app_bg"],
            segmented_button_selected_color=THEME["primary"],
            segmented_button_selected_hover_color=THEME["primary_hover"],
            segmented_button_unselected_color="#F1F5F9",
            segmented_button_unselected_hover_color="#E2E8F0",
            text_color=THEME["text_main"]
        )
        self.tabview.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        self.tab_fluent = self.tabview.add(" ⚡ Modern Fluent 뷰 ")
        self.tab_rpg = self.tabview.add(" ⚔️ Gamified RPG 뷰 ")
        self.tab_review = self.tabview.add(" 📚 스마트 오답노트 & 퀴즈 ")
        self.tab_dashboard = self.tabview.add(" 📊 실력 대시보드 ")

        self.build_fluent_tab()
        self.build_rpg_tab()
        self.build_review_tab()
        self.build_dashboard_tab()

        self.update_all_headers()

        # 전역 단축키 바인딩
        self.bind("<space>", self.on_space_pressed)
        self.bind("<r>", self.on_r_pressed)
        self.bind("<R>", self.on_r_pressed)

    def update_all_headers(self):
        prof = self.get_current_profile()
        exp = prof["exp"]
        tier = prof["tier"]
        total = prof["total_turns"]
        flawless = prof["flawless_turns"]
        acc = round((flawless / total * 100), 1) if total > 0 else 0.0

        lang_cfg = self.get_cur_lang_cfg()
        self.lbl_global_tier.configure(
            text=f"{lang_cfg['flag']} [{lang_cfg['key']}] 🏆 {tier}  │  ✨ {exp:,} EXP  │  🎯 누적 {total}턴 (무결점: {acc}%)"
        )

        if hasattr(self, 'lbl_rpg_hud_tier'):
            cur_tier_name, base_exp, target_exp = TIER_THRESHOLDS[0]
            for t_name, b_exp, tg_exp in TIER_THRESHOLDS:
                if exp >= b_exp:
                    cur_tier_name, base_exp, target_exp = t_name, b_exp, tg_exp

            progress = min(1.0, max(0.0, float((exp - base_exp) / (target_exp - base_exp))))
            self.lbl_rpg_hud_tier.configure(text=f"🏆 TIER: [ {cur_tier_name.upper()} ]")
            self.lbl_rpg_hud_exp.configure(text=f"EXP [ {exp:,} / {target_exp:,} pts ]")
            self.rpg_exp_bar.set(progress)

    # =========================================================================
    # [TAB 1] Modern Fluent 뷰
    # =========================================================================
    def build_fluent_tab(self):
        self.fl_left_panel = ctk.CTkFrame(
            self.tab_fluent,
            width=360,
            corner_radius=14,
            fg_color=THEME["card_bg"],
            border_width=1,
            border_color=THEME["card_border"]
        )
        self.fl_left_panel.pack(side="left", fill="y", padx=(6, 8), pady=6)

        self.fl_right_panel = ctk.CTkFrame(
            self.tab_fluent,
            corner_radius=14,
            fg_color=THEME["card_bg"],
            border_width=1,
            border_color=THEME["card_border"]
        )
        self.fl_right_panel.pack(side="right", fill="both", expand=True, padx=(0, 6), pady=6)

        # ------------------ 좌측 패널 ------------------
        # 🌐 학습 언어 선택
        ctk.CTkLabel(
            self.fl_left_panel,
            text="🌐 학습 언어 선택",
            font=ctk.CTkFont(family="Pretendard", size=12, weight="bold"),
            text_color=THEME["primary"]
        ).pack(anchor="w", padx=16, pady=(12, 2))

        self.opt_lang = ctk.CTkOptionMenu(
            self.fl_left_panel,
            values=list(LANG_CONFIGS.keys()),
            command=self.on_language_changed,
            fg_color="#EBF7EE",
            button_color="#C3E6CB",
            button_hover_color="#A3D9B1",
            text_color=THEME["primary"],
            dropdown_fg_color="#FFFFFF",
            dropdown_text_color=THEME["text_main"],
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.opt_lang.pack(fill="x", padx=16, pady=(0, 8))

        lbl_mode = ctk.CTkLabel(
            self.fl_left_panel,
            text="⚙️ 시나리오 모드 선택",
            font=ctk.CTkFont(family="Pretendard", size=12, weight="bold"),
            text_color=THEME["text_main"]
        )
        lbl_mode.pack(anchor="w", padx=16, pady=(4, 4))

        self.fl_mode_seg = ctk.CTkSegmentedButton(
            self.fl_left_panel,
            values=["📋 카테고리/테마", "🤖 AI 자유 생성"],
            command=self.on_fluent_mode_changed,
            selected_color=THEME["primary"],
            selected_hover_color=THEME["primary_hover"],
            unselected_color="#F1F5F9",
            unselected_hover_color="#E2E8F0",
            text_color=THEME["text_main"]
        )
        self.fl_mode_seg.set("📋 카테고리/테마")
        self.fl_mode_seg.pack(fill="x", padx=16, pady=(0, 8))

        # 모드 A (카테고리/테마)
        self.fl_frame_preset = ctk.CTkFrame(self.fl_left_panel, fg_color="transparent")
        self.fl_frame_preset.pack(fill="x", padx=16, pady=0)

        ctk.CTkLabel(self.fl_frame_preset, text="🗺️ 1. 카테고리 선택 (17개)", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_sub"]).pack(anchor="w", pady=(2, 2))
        self.fl_cat_combo = ctk.CTkOptionMenu(
            self.fl_frame_preset,
            values=list(MASTER_CATEGORIES.keys()),
            command=self.on_fl_category_selected,
            fg_color="#F1F5F9",
            button_color="#E2E8F0",
            button_hover_color="#CBD5E1",
            text_color=THEME["text_main"],
            dropdown_fg_color="#FFFFFF",
            dropdown_text_color=THEME["text_main"],
            corner_radius=8
        )
        self.fl_cat_combo.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(self.fl_frame_preset, text="📌 2. 세부 테마 선택", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_sub"]).pack(anchor="w", pady=(2, 2))
        self.fl_sc_combo = ctk.CTkOptionMenu(
            self.fl_frame_preset,
            values=["선택 중..."],
            fg_color="#F1F5F9",
            button_color="#E2E8F0",
            button_hover_color="#CBD5E1",
            text_color=THEME["text_main"],
            dropdown_fg_color="#FFFFFF",
            dropdown_text_color=THEME["text_main"],
            corner_radius=8
        )
        self.fl_sc_combo.pack(fill="x", pady=(0, 5))

        self.fl_dynamic_var = ctk.BooleanVar(value=True)
        self.fl_chk_dynamic = ctk.CTkCheckBox(
            self.fl_frame_preset,
            text="🎲 매번 새로운 인물/상황 AI 변형",
            variable=self.fl_dynamic_var,
            font=ctk.CTkFont(size=11),
            text_color=THEME["text_main"],
            fg_color=THEME["primary"],
            hover_color=THEME["primary_hover"],
            checkmark_color="#FFFFFF"
        )
        self.fl_chk_dynamic.pack(anchor="w", pady=(3, 3))

        # 모드 B (자유 생성)
        self.fl_frame_custom = ctk.CTkFrame(self.fl_left_panel, fg_color="transparent")

        ctk.CTkLabel(self.fl_frame_custom, text="💡 내가 원하는 상황 자유 입력", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["coach_accent"]).pack(anchor="w", pady=(2, 2))
        self.fl_entry_custom_ai = ctk.CTkEntry(
            self.fl_frame_custom,
            placeholder_text=LANG_CONFIGS["🇺🇸 영어 (English)"]["custom_placeholder"],
            fg_color="#FFFFFF",
            border_color=THEME["card_border"],
            text_color=THEME["text_main"],
            corner_radius=8
        )
        self.fl_entry_custom_ai.pack(fill="x", pady=(0, 5))

        guide_box = ctk.CTkLabel(
            self.fl_frame_custom,
            text="✨ [자유 입력 예시]\n• 해외 부동산 계약서 조항 검토하기\n• 렌터카 스크래치 보험 분쟁 해결\n• 보드게임 모임에서 타일 룰 설명하기",
            font=ctk.CTkFont(size=10),
            text_color=THEME["text_sub"],
            justify="left",
            fg_color="#F8FAFC",
            corner_radius=8
        )
        guide_box.pack(fill="x", pady=3, ipadx=6, ipady=4)

        # 공통 하단 설정
        self.fl_frame_common = ctk.CTkFrame(self.fl_left_panel, fg_color="transparent")
        self.fl_frame_common.pack(fill="x", padx=16, pady=(4, 0))

        ctk.CTkLabel(self.fl_frame_common, text="🎯 7단계 회화 레벨 설정", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_sub"]).pack(anchor="w", pady=(2, 2))
        self.fl_diff_combo = ctk.CTkOptionMenu(
            self.fl_frame_common,
            values=list(DIFFICULTY_OPTIONS.keys()),
            fg_color="#F1F5F9",
            button_color="#E2E8F0",
            button_hover_color="#CBD5E1",
            text_color=THEME["text_main"],
            dropdown_fg_color="#FFFFFF",
            dropdown_text_color=THEME["text_main"],
            corner_radius=8
        )
        self.fl_diff_combo.set("Lv 2. 기초 일상 (A2 Elementary)")
        self.fl_diff_combo.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(self.fl_frame_common, text="🎙️ 원어민 성우 설정", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_sub"]).pack(anchor="w", pady=(2, 2))
        self.fl_voice_combo = ctk.CTkOptionMenu(
            self.fl_frame_common,
            values=["캐릭터 성별에 맞춰 자동 배정"],
            fg_color="#F1F5F9",
            button_color="#E2E8F0",
            button_hover_color="#CBD5E1",
            text_color=THEME["text_main"],
            dropdown_fg_color="#FFFFFF",
            dropdown_text_color=THEME["text_main"],
            corner_radius=8
        )
        self.fl_voice_combo.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(self.fl_frame_common, text="💡 세부 추가조건 커스텀 (옵션)", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_sub"]).pack(anchor="w", pady=(2, 2))
        self.fl_entry_condition = ctk.CTkEntry(
            self.fl_frame_common,
            placeholder_text="예: 상대방이 매우 바쁜 상황",
            fg_color="#FFFFFF",
            border_color=THEME["card_border"],
            text_color=THEME["text_main"],
            corner_radius=8
        )
        self.fl_entry_condition.pack(fill="x", pady=(0, 8))

        self.fl_btn_start = ctk.CTkButton(
            self.fl_frame_common,
            text="🎬 롤플레잉 세션 시작",
            font=ctk.CTkFont(family="Pretendard", size=13, weight="bold"),
            fg_color=THEME["primary"],
            hover_color=THEME["primary_hover"],
            text_color="#FFFFFF",
            height=38,
            corner_radius=10,
            command=self.start_fluent_session
        )
        self.fl_btn_start.pack(fill="x", pady=(0, 6))

        # ------------------ 우측 대화창 ------------------
        self.fl_chat_scroll = ctk.CTkScrollableFrame(
            self.fl_right_panel,
            fg_color="#F8FAFC",
            corner_radius=12
        )
        self.fl_chat_scroll.pack(fill="both", expand=True, padx=10, pady=(10, 6))

        fl_ctrl = ctk.CTkFrame(self.fl_right_panel, fg_color="transparent")
        fl_ctrl.pack(fill="x", padx=10, pady=(0, 10))

        btn_row = ctk.CTkFrame(fl_ctrl, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 6))

        self.fl_btn_mic = ctk.CTkButton(
            btn_row,
            text="🎤 마이크 녹음 시작 (스페이스바)",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=THEME["record_btn"],
            hover_color=THEME["record_hover"],
            text_color="#FFFFFF",
            height=40,
            corner_radius=10,
            command=self.toggle_mic
        )
        self.fl_btn_mic.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.fl_btn_replay = ctk.CTkButton(
            btn_row,
            text="🔊 다시 듣기 (R)",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=THEME["accent_blue"],
            hover_color=THEME["accent_blue_hover"],
            text_color="#FFFFFF",
            width=130,
            height=40,
            corner_radius=10,
            command=self.replay_last_speech
        )
        self.fl_btn_replay.pack(side="right")

        in_row = ctk.CTkFrame(fl_ctrl, fg_color="transparent")
        in_row.pack(fill="x")

        self.fl_txt_input = ctk.CTkEntry(
            in_row,
            placeholder_text=LANG_CONFIGS["🇺🇸 영어 (English)"]["input_placeholder"],
            fg_color="#FFFFFF",
            border_color=THEME["card_border"],
            text_color=THEME["text_main"],
            height=38,
            corner_radius=10
        )
        self.fl_txt_input.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.fl_txt_input.bind("<Return>", lambda e: self.send_text_fluent())

        btn_send = ctk.CTkButton(
            in_row,
            text="전송",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=THEME["primary"],
            hover_color=THEME["primary_hover"],
            text_color="#FFFFFF",
            width=80,
            height=38,
            corner_radius=10,
            command=self.send_text_fluent
        )
        btn_send.pack(side="right")

        self.on_fl_category_selected(self.fl_cat_combo.get())
        self.on_language_changed(self.opt_lang.get())

    def on_language_changed(self, lang_name):
        cfg = LANG_CONFIGS.get(lang_name, LANG_CONFIGS["🇺🇸 영어 (English)"])
        v_list = ["캐릭터 성별에 맞춰 자동 배정"] + list(cfg["voices"].keys())
        self.fl_voice_combo.configure(values=v_list)
        self.fl_voice_combo.set("캐릭터 성별에 맞춰 자동 배정")

        self.fl_txt_input.configure(placeholder_text=cfg["input_placeholder"])
        if hasattr(self, 'rpg_txt_input'):
            self.rpg_txt_input.configure(placeholder_text=cfg["rpg_placeholder"])
        self.fl_entry_custom_ai.configure(placeholder_text=cfg["custom_placeholder"])
        self.fl_btn_start.configure(text=f"🎬 [{cfg['key']}] 롤플레잉 세션 시작")
        self.update_all_headers()

    def on_fluent_mode_changed(self, value):
        if "카테고리" in value:
            self.fl_frame_custom.pack_forget()
            self.fl_frame_preset.pack(fill="x", padx=16, pady=0, before=self.fl_frame_common)
        else:
            self.fl_frame_preset.pack_forget()
            self.fl_frame_custom.pack(fill="x", padx=16, pady=0, before=self.fl_frame_common)

    def on_fl_category_selected(self, cat):
        sc_list = MASTER_CATEGORIES.get(cat, [])
        self.fl_sc_combo.configure(values=sc_list)
        if sc_list:
            self.fl_sc_combo.set(sc_list[0])

    # =========================================================================
    # [TAB 2] Gamified RPG 뷰
    # =========================================================================
    def build_rpg_tab(self):
        hud_box = ctk.CTkFrame(
            self.tab_rpg,
            corner_radius=14,
            fg_color=THEME["card_bg"],
            border_width=1,
            border_color=THEME["card_border"]
        )
        hud_box.pack(fill="x", padx=14, pady=6)

        hud_top = ctk.CTkFrame(hud_box, fg_color="transparent")
        hud_top.pack(fill="x", padx=16, pady=(8, 2))

        self.lbl_rpg_hud_tier = ctk.CTkLabel(
            hud_top,
            text="🏆 TIER: [ BRONZE (TOURIST) ]",
            font=ctk.CTkFont(family="Pretendard", size=14, weight="bold"),
            text_color=THEME["coach_accent"]
        )
        self.lbl_rpg_hud_tier.pack(side="left")

        self.lbl_rpg_hud_exp = ctk.CTkLabel(
            hud_top,
            text="EXP [ 0 / 200 pts ]",
            font=ctk.CTkFont(family="Pretendard", size=13, weight="bold"),
            text_color=THEME["primary"]
        )
        self.lbl_rpg_hud_exp.pack(side="right")

        self.rpg_exp_bar = ctk.CTkProgressBar(
            hud_box,
            height=12,
            corner_radius=6,
            progress_color=THEME["primary"],
            fg_color="#E2E8F0"
        )
        self.rpg_exp_bar.set(0.0)
        self.rpg_exp_bar.pack(fill="x", padx=16, pady=(2, 10))

        # 퀘스트 브리핑 카드
        self.rpg_quest_card = ctk.CTkFrame(
            self.tab_rpg,
            corner_radius=12,
            fg_color=THEME["user_bubble"],
            border_width=1,
            border_color=THEME["user_border"]
        )
        self.rpg_quest_card.pack(fill="x", padx=14, pady=4)

        self.lbl_rpg_quest_title = ctk.CTkLabel(
            self.rpg_quest_card,
            text="⚔️ ACTIVE QUEST : [STAGE 01] 미션 대기 중",
            font=ctk.CTkFont(family="Pretendard", size=13, weight="bold"),
            text_color="#1E293B"
        )
        self.lbl_rpg_quest_title.pack(anchor="w", padx=14, pady=(8, 2))

        self.lbl_rpg_quest_sub = ctk.CTkLabel(
            self.rpg_quest_card,
            text="🎯 난이도: ★★★☆☆ (Intermediate)  │  👾 상대 보스: Grand Hotel Alex",
            font=ctk.CTkFont(family="Pretendard", size=11, weight="bold"),
            text_color="#2F855A"
        )
        self.lbl_rpg_quest_sub.pack(anchor="w", padx=14, pady=(0, 2))

        self.lbl_rpg_quest_desc = ctk.CTkLabel(
            self.rpg_quest_card,
            text="📜 미션 목표: Fluent 탭에서 세션을 시작하거나 아래 [🎲 랜덤 퀘스트 수락] 버튼을 누르세요!",
            font=ctk.CTkFont(family="Pretendard", size=11),
            text_color=THEME["text_main"],
            wraplength=850,
            justify="left"
        )
        self.lbl_rpg_quest_desc.pack(anchor="w", padx=14, pady=(0, 8))

        self.rpg_chat_scroll = ctk.CTkScrollableFrame(
            self.tab_rpg,
            fg_color="#F8FAFC",
            corner_radius=12
        )
        self.rpg_chat_scroll.pack(fill="both", expand=True, padx=14, pady=6)

        rpg_ctrl = ctk.CTkFrame(self.tab_rpg, fg_color="transparent")
        rpg_ctrl.pack(fill="x", padx=14, pady=(0, 10))

        rpg_btn_row = ctk.CTkFrame(rpg_ctrl, fg_color="transparent")
        rpg_btn_row.pack(fill="x", pady=(0, 6))

        self.rpg_btn_mic = ctk.CTkButton(
            rpg_btn_row,
            text="⚔️ [SPACE] VOICE BATTLE (녹음 시작)",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=THEME["purple_accent"],
            hover_color=THEME["purple_hover"],
            text_color="#FFFFFF",
            height=40,
            corner_radius=10,
            command=self.toggle_mic
        )
        self.rpg_btn_mic.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.rpg_btn_replay = ctk.CTkButton(
            rpg_btn_row,
            text="🔊 다시 듣기 (R)",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=THEME["accent_blue"],
            hover_color=THEME["accent_blue_hover"],
            text_color="#FFFFFF",
            width=130,
            height=40,
            corner_radius=10,
            command=self.replay_last_speech
        )
        self.rpg_btn_replay.pack(side="left", padx=(0, 6))

        btn_rand_quest = ctk.CTkButton(
            rpg_btn_row,
            text="🎲 랜덤 퀘스트 수락",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#475569",
            hover_color="#334155",
            text_color="#FFFFFF",
            width=150,
            height=40,
            corner_radius=10,
            command=self.start_random_rpg_quest
        )
        btn_rand_quest.pack(side="right")

        rpg_in_row = ctk.CTkFrame(rpg_ctrl, fg_color="transparent")
        rpg_in_row.pack(fill="x")

        self.rpg_txt_input = ctk.CTkEntry(
            rpg_in_row,
            placeholder_text=LANG_CONFIGS["🇺🇸 영어 (English)"]["rpg_placeholder"],
            fg_color="#FFFFFF",
            border_color=THEME["card_border"],
            text_color=THEME["text_main"],
            height=38,
            corner_radius=10
        )
        self.rpg_txt_input.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.rpg_txt_input.bind("<Return>", lambda e: self.send_text_rpg())

        btn_rpg_send = ctk.CTkButton(
            rpg_in_row,
            text="공격 전송",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=THEME["primary"],
            hover_color=THEME["primary_hover"],
            text_color="#FFFFFF",
            width=90,
            height=38,
            corner_radius=10,
            command=self.send_text_rpg
        )
        btn_rpg_send.pack(side="right")

    def start_random_rpg_quest(self):
        all_cats = list(MASTER_CATEGORIES.keys())
        r_cat = random.choice(all_cats)
        r_themes = [t for t in MASTER_CATEGORIES[r_cat] if not t.startswith("🎲")]
        r_theme = random.choice(r_themes) if r_themes else r_cat

        diff_name = self.fl_diff_combo.get()
        diff_info = DIFFICULTY_OPTIONS[diff_name]
        lang_cfg = self.get_cur_lang_cfg()

        prompt = f"RPG 보스 퀘스트: 카테고리 '{r_cat}', 활동 테마 '{r_theme}', 회화 레벨 '{diff_name}' ({diff_info['desc']}). 복잡도 가이드: {diff_info['complexity_guide']}. 대상 언어: {lang_cfg['name_en']} ({lang_cfg['key']}). 상대방 역할은 매력적인 NPC 보스로 설정하고, 회화 레벨에 정확히 맞춘 첫 대사와 한국어 번역을 생성하세요."
        threading.Thread(target=self._init_rpg_session_async, args=(prompt, r_cat), daemon=True).start()

    def _init_rpg_session_async(self, prompt: str, cat: str):
        self.rpg_btn_mic.configure(state="disabled", text="⏳ 퀘스트 로딩 중...")
        scenario = self._generate_dynamic_scenario(prompt, cat)
        self.current_scenario = scenario
        self.chat_history = []
        self.session_turns = 0
        self.session_flawless = 0
        self.new_mistakes = []

        self.last_ai_reply_text = scenario['opening']
        self.last_ai_reply_voice = scenario['voice']

        self.after(0, self._render_rpg_start, scenario)
        threading.Thread(target=play_tts_sound, args=(scenario['opening'], scenario['voice']), daemon=True).start()

    def _render_rpg_start(self, sc):
        self.rpg_btn_mic.configure(state="normal", text="⚔️ [SPACE] VOICE BATTLE (녹음 시작)")
        stage_num = random.randint(1, 15)
        lang_cfg = self.get_cur_lang_cfg()
        diff_name = self.fl_diff_combo.get()
        trans_txt = sc.get('opening_translation', '')

        self.lbl_rpg_quest_title.configure(text=f"⚔️ ACTIVE QUEST : [STAGE {stage_num:02d}] {sc['title']}")
        self.lbl_rpg_quest_sub.configure(text=f"{lang_cfg['flag']} {lang_cfg['key']}  │  🎯 난이도: {diff_name.split('.')[0]}  │  👾 상대 보스: {sc['role']}")
        self.lbl_rpg_quest_desc.configure(text=f"📜 미션 목표: {sc['context']}")

        now_time = datetime.now().strftime("%H:%M")

        for widget in self.rpg_chat_scroll.winfo_children():
            widget.destroy()
        for widget in self.fl_chat_scroll.winfo_children():
            widget.destroy()

        self._add_system_banner(self.rpg_chat_scroll, f"🎮 [{lang_cfg['key']} 퀘스트 개막] {sc['title']}", sc['context'])
        self._add_ai_bubble(self.rpg_chat_scroll, sc['role'], sc['opening'], now_time, is_rpg=True, translation_text=trans_txt)

        self._add_system_banner(self.fl_chat_scroll, f"🎬 [{lang_cfg['key']} 세션 시작] {sc['title']} ({sc['category']})", sc['context'])
        self._add_ai_bubble(self.fl_chat_scroll, sc['role'], sc['opening'], now_time, is_rpg=False, translation_text=trans_txt)

        self.chat_history.append({"role": "model", "parts": [sc['opening']]})

    # =========================================================================
    # 세션 시작 & 다이내믹 AI 엔진
    # =========================================================================
    def start_fluent_session(self):
        self.fl_btn_start.configure(state="disabled", text="⏳ 시나리오 준비 중...")
        threading.Thread(target=self._init_fluent_session_async, daemon=True).start()

    def _init_fluent_session_async(self):
        mode_val = self.fl_mode_seg.get()
        cat = self.fl_cat_combo.get()
        diff_name = self.fl_diff_combo.get()
        diff_info = DIFFICULTY_OPTIONS[diff_name]
        lang_cfg = self.get_cur_lang_cfg()

        if "자유 생성" in mode_val:
            user_free_topic = self.fl_entry_custom_ai.get().strip()
            prompt = f"사용자 요구상황: '{user_free_topic}'. 학습 대상 언어: {lang_cfg['name_en']} ({lang_cfg['key']}), 회화 레벨: {diff_name} ({diff_info['desc']}). 복잡도 가이드: {diff_info['complexity_guide']}. 고품질 롤플레잉 시나리오 및 첫 대사와 한국어 번역 생성."
            scenario = self._generate_dynamic_scenario(prompt, "AI 자유 주제")
        else:
            selected_theme = self.fl_sc_combo.get()
            if selected_theme.startswith("🎲"):
                cat_themes = [t for t in MASTER_CATEGORIES.get(cat, []) if not t.startswith("🎲")]
                actual_theme = random.choice(cat_themes) if cat_themes else cat
                theme_desc = f"'{cat}' 분야의 즉흥 상황 (예: {actual_theme})"
            else:
                theme_desc = f"'{selected_theme}'"

            prompt = f"카테고리: '{cat}', 테마/상황: {theme_desc}, 학습자 회화 레벨: '{diff_name}' ({diff_info['desc']}). 복잡도 가이드: {diff_info['complexity_guide']}. 학습 대상 언어: {lang_cfg['name_en']} ({lang_cfg['key']}). 인물 역할, 배경상황, 상대방의 첫 대사(opening) 및 한국어 번역(opening_translation)을 해당 레벨의 난이도 기준에 완벽하게 일치시켜 생동감 있게 생성해줘."
            scenario = self._generate_dynamic_scenario(prompt, cat)

        # 성우 커스텀 지정 확인
        v_choice = self.fl_voice_combo.get()
        if v_choice in lang_cfg["voices"]:
            scenario["voice"] = lang_cfg["voices"][v_choice]

        self.current_scenario = scenario
        self.chat_history = []
        self.session_turns = 0
        self.session_flawless = 0
        self.new_mistakes = []

        self.last_ai_reply_text = scenario['opening']
        self.last_ai_reply_voice = scenario['voice']

        self.after(0, self._render_fluent_start, scenario)
        threading.Thread(target=play_tts_sound, args=(scenario['opening'], scenario['voice']), daemon=True).start()

    def _get_smart_fallback_scenario(self, cat: str, diff_name: str, lang_cfg: dict) -> dict:
        """API 오류 시에도 회화 레벨과 카테고리에 맞춰 차별화된 시나리오를 제공하는 오프라인 헬퍼"""
        is_chaos = "Chaos" in diff_name or "Lv 7" in diff_name
        is_beginner = "Lv 1" in diff_name or "Lv 2" in diff_name

        lang_key = lang_cfg.get("key", "영어")
        
        if is_chaos:
            title = f"{cat} 긴급 돌발 위기 상황"
            role = "Crisis Manager (David)" if lang_key != "일본어" else "緊急対応マネージャー (佐藤)"
            context = "전산 시스템 심각한 오류 및 오버부킹으로 예약이 누락되어 즉각적인 분쟁 해결 및 보상이 필요한 긴급 상황"
            openings = {
                "영어": "I am deeply sorry, but our central system suffered a critical crash and all suites are completely overbooked tonight. We must discuss relocating you immediately.",
                "일본어": "大変申し訳ございません。システム障害により本日の予約が二重登録となっており、現在ご案内できる部屋がございません。",
                "중국어": "非常抱歉，系统出现严重故障导致房间超额预订，今晚已无空房，我们需要立即协商处理。",
                "스페인어": "Lo siento muchísimo, pero debido a un fallo crítico del sistema, todas las habitaciones están sobrevendidas esta noche."
            }
            translations = {
                "영어": "정말 죄송합니다만, 중앙 시스템 치명적 오류로 오늘 밤 모든 객실이 오버부킹되었습니다. 즉시 다른 숙소로의 재배치 및 보상을 협의해야 합니다.",
                "일본어": "대단히 죄송합니다. 시스템 장애로 오늘 예약이 이중 등록되어 현재 안내해 드릴 수 있는 방이 없습니다.",
                "중국어": "대단히 죄송합니다. 시스템의 심각한 오류로 오버부킹이 발생하여 오늘 밤 빈 방이 없으므로 즉시 협의해야 합니다.",
                "스페인어": "정말 죄송합니다만, 시스템의 치명적인 오류로 인해 오늘 밤 모든 방이 오버부킹되었습니다."
            }
        elif is_beginner:
            title = f"{cat} 기초 일상 안내"
            role = "Guide (Alex)" if lang_key != "일본어" else "案内スタッフ (田中)"
            context = "기초적이고 친절한 기본 안내 및 필수 확인 절차"
            openings = {
                "영어": "Hello! Welcome. How can I help you?",
                "일본어": "こんにちは！いらっしゃいませ。ご用件をどうぞ。",
                "중국어": "您好！欢迎光临。请问有什么可以帮您？",
                "스페인어": "¡Hola! Bienvenido. ¿En qué puedo ayudarle?"
            }
            translations = {
                "영어": "안녕하세요! 환영합니다. 무엇을 도와드릴까요?",
                "일본어": "안녕하세요! 어서 오세요. 무엇을 도와드릴까요?",
                "중국어": "안녕하세요! 환영합니다. 어떤 도움이 필요하신가요?",
                "스페인어": "안녕하세요! 환영합니다. 무엇을 도와드릴까요?"
            }
        else:
            title = f"{cat} 실용 회화"
            role = "Staff (Alex)" if lang_key != "일본어" else "担当スタッフ (高橋)"
            context = "일상적인 상세 요구사항 문의 및 추천 안내"
            openings = {
                "영어": "Good day! How may I assist you with your request today?",
                "일본어": "こんにちは！本日はどのようなご要望でしょうか？",
                "중국어": "您好！今天有什么需要我协助您的吗？",
                "스페인어": "¡Buen día! ¿En qué puedo colaborarle hoy con su solicitud?"
            }
            translations = {
                "영어": "좋은 날입니다! 오늘 어떤 문의사항을 도와드릴까요?",
                "일본어": "안녕하세요! 오늘은 어떤 요청사항이 있으신가요?",
                "중국어": "안녕하세요! 오늘 어떤 도움이 필요하신가요?",
                "스페인어": "좋은 하루입니다! 오늘 어떤 요청사항을 도와드릴까요?"
            }

        return {
            "title": title,
            "category": cat,
            "role": role,
            "voice": lang_cfg["default_voice"],
            "context": context,
            "opening": openings.get(lang_key, openings["영어"]),
            "opening_translation": translations.get(lang_key, translations["영어"]),
            "language": lang_key
        }

    def _generate_dynamic_scenario(self, prompt_text: str, cat: str) -> dict:
        lang_cfg = self.get_cur_lang_cfg()
        diff_name = self.fl_diff_combo.get()
        diff_info = DIFFICULTY_OPTIONS[diff_name]

        sys_inst = f"""
당신은 세계 최고의 외국어 교육용 롤플레잉 시나리오 설계 전문가입니다.
[학습 대상 언어]: {lang_cfg['name_en']} ({lang_cfg['key']})
[학습자 회화 레벨]: {diff_name}
[레벨별 상세 지침]: {diff_info['desc']}
[상황 복잡도 가이드]: {diff_info['complexity_guide']}

[★ 레벨별 100% 맞춤형 상황 복잡도, 상대방 태도, 미션 및 첫 대사(opening) 생성 규칙]:
- 'Lv 1. 생존 입문 (A1 Starter)':
  * 상황 및 미션: 극도로 단순/직관적인 기초 상황 (단순 명사/인사, 방 키 받기, 단답형 주문, 기본 확인).
  * 상대방 태도 및 첫 대사: 극도로 친절하고 느리며, 3~5단어의 기초 단문으로 말함. (예: "Hello! Welcome. Room reservation?")
- 'Lv 2. 기초 일상 (A2 Elementary)':
  * 상황 및 미션: 일상 필수 기초 문장 (조식 시간, 와이파이 비번, 기본 길찾기, 메뉴 수량 선택).
  * 상대방 태도 및 첫 대사: 표준적이고 또박또박한 기본 문장. (예: "Welcome! Here is your room key. Would you like breakfast included?")
- 'Lv 3. 실용 중급 (B1 Intermediate)':
  * 상황 및 미션: 세부 요청 및 취향/의견 설명 (조용한 고층 방 변경, 짐 보관, 얼음 적게, 드립커피 추천).
  * 상대방 태도 및 첫 대사: 자연스러운 원어민 구어체와 친근하고 매끄러운 응대. (예: "Good afternoon! We have standard rooms available on floors 3 and 7. Which do you prefer?")
- 'Lv 4. 유창 심화 (B2 Upper-Intermediate)':
  * 상황 및 미션: 디테일한 조건 비교 및 질문 (전망 업그레이드 요청, 주변 로컬 맛집 추천받기, 스펙 비교).
  * 상대방 태도 및 첫 대사: 풍부한 어휘와 복합 문장, 디테일한 질문 던지기. (예: "Hello! I see you requested a city view. Would you be interested in an ocean view suite today?")
- 'Lv 5. 비즈니스/전문 (C1 Advanced)':
  * 상황 및 미션: 격식 있는 전문/비즈니스 상황 (얼리 체크인, 비즈니스 미팅룸 예약, 회사 인보이스 분할 요청, 납기 협상).
  * 상대방 태도 및 첫 대사: 격식 있고 정중하며 세련된 프로페셔널/컨시어지 화법. (예: "Good afternoon. Welcome to our Executive floor. How may I facilitate your stay for your meetings?")
- 'Lv 6. 원어민 심층 토론 (C2 Master)':
  * 상황 및 미션: 복잡한 규정/혜택 조율 및 심도 있는 토론 (멤버십 포인트 오류 소급 적용, 로열티 혜택 협의, 문화/전략 논박).
  * 상대방 태도 및 첫 대사: 빠르고 자연스러운 현지인 관용구와 빠른 호흡. (예: "Welcome back! I noticed a slight glitch with your loyalty points on this booking. Let me sort that out.")
- 'Lv 7. 실전 돌발 위기극복 (Chaos Mode)':
  * 상황 및 미션: [돌발 위기] 시스템 오류로 만실(오버부킹)되어 다른 곳으로 가라는 통보, 심각한 기물 파손 분쟁, 도난 피해 등 극심한 돌발 위기 상황!
  * 상대방 태도 및 첫 대사: 단호하고 바쁘거나 까다로운 상대방 (학습자가 강하게 컴플레인하고 논리적으로 위기를 극복해야 하는 미션 부여). (예: "I am terribly sorry, but our hotel is completely overbooked tonight. We will have to transfer you to a motel.")

[출력 지침]:
1. opening은 반드시 {lang_cfg['name_en']}로 1~2문장 작성하세요. (위 레벨별 어휘와 길이를 엄격히 준수)
2. opening_translation은 opening에 대한 자연스럽고 정확한 한국어 번역이어야 합니다.
3. title, category, context는 한국어로 작성하세요. context에는 학습자가 해결해야 할 구체적 미션을 명시하세요.
4. 반드시 JSON 규격(DynamicScenarioSchema)으로 응답하세요.
"""
        try:
            res = generate_content_with_fallback(
                contents=prompt_text,
                config=types.GenerateContentConfig(
                    system_instruction=sys_inst,
                    response_mime_type="application/json",
                    response_schema=DynamicScenarioSchema,
                    temperature=0.85
                )
            )
            data = DynamicScenarioSchema.model_validate_json(res.text)
            
            # 언어에 맞는 보이스 매핑
            v_gender = data.voice_gender.lower()
            v_candidates = [v for k, v in lang_cfg["voices"].items() if ("여성" in k if "female" in v_gender else "남성" in k)]
            selected_voice = random.choice(v_candidates) if v_candidates else lang_cfg["default_voice"]

            return {
                "title": data.title,
                "category": cat,
                "role": data.role,
                "voice": selected_voice,
                "context": data.context,
                "opening": data.opening,
                "opening_translation": getattr(data, 'opening_translation', '') or "상대방의 첫 대사입니다.",
                "language": lang_cfg["key"]
            }
        except Exception as e:
            print(f"⚠️ 시나리오 생성 오류 ({e}), 스마트 오프라인 폴백 적용")
            return self._get_smart_fallback_scenario(cat, diff_name, lang_cfg)

    def _render_fluent_start(self, sc):
        self.fl_btn_start.configure(state="normal", text=f"🎬 [{self.get_cur_lang_cfg()['key']}] 롤플레잉 세션 시작")
        now_time = datetime.now().strftime("%H:%M")
        lang_cfg = self.get_cur_lang_cfg()
        diff_name = self.fl_diff_combo.get()
        trans_txt = sc.get('opening_translation', '')

        for widget in self.fl_chat_scroll.winfo_children():
            widget.destroy()
        for widget in self.rpg_chat_scroll.winfo_children():
            widget.destroy()

        self._add_system_banner(self.fl_chat_scroll, f"🎬 [{lang_cfg['key']} 세션 시작] {sc['title']} ({sc['category']})", sc['context'])
        self._add_ai_bubble(self.fl_chat_scroll, sc['role'], sc['opening'], now_time, is_rpg=False, translation_text=trans_txt)

        stage_num = random.randint(1, 15)
        self.lbl_rpg_quest_title.configure(text=f"⚔️ ACTIVE QUEST : [STAGE {stage_num:02d}] {sc['title']}")
        self.lbl_rpg_quest_sub.configure(text=f"{lang_cfg['flag']} {lang_cfg['key']}  │  🎯 난이도: {diff_name.split('.')[0]}  │  👾 상대 보스: {sc['role']}")
        self.lbl_rpg_quest_desc.configure(text=f"📜 미션 목표: {sc['context']}")

        self._add_system_banner(self.rpg_chat_scroll, f"🎮 [{lang_cfg['key']} 퀘스트 개막] {sc['title']}", sc['context'])
        self._add_ai_bubble(self.rpg_chat_scroll, sc['role'], sc['opening'], now_time, is_rpg=True, translation_text=trans_txt)

        self.chat_history.append({"role": "model", "parts": [sc['opening']]})

    # =========================================================================
    # 말풍선 렌더링 헬퍼 함수들 (글자 짤림 방지 완벽 대응)
    # =========================================================================
    def _add_system_banner(self, parent, title_text, context_text=""):
        # 2단 구조 프레임으로 절대 글자가 짤리지 않도록 구성
        banner_frame = ctk.CTkFrame(
            parent,
            corner_radius=12,
            fg_color="#EBF7EE",
            border_width=1,
            border_color="#C3E6CB"
        )
        banner_frame.pack(fill="x", padx=10, pady=(8, 10))

        lbl_title = ctk.CTkLabel(
            banner_frame,
            text=title_text,
            font=ctk.CTkFont(family="Pretendard", size=12, weight="bold"),
            text_color="#2F855A",
            wraplength=650,
            justify="center"
        )
        lbl_title.pack(fill="x", padx=14, pady=(8, 4))

        if context_text:
            lbl_context = ctk.CTkLabel(
                banner_frame,
                text=f"📌 [배경 상황]: {context_text}",
                font=ctk.CTkFont(family="Pretendard", size=11),
                text_color=THEME["text_main"],
                wraplength=650,
                justify="center"
            )
            lbl_context.pack(fill="x", padx=14, pady=(0, 8))

    def _add_user_bubble(self, parent, user_text, time_str, is_rpg=False):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=6, pady=4)

        tag_text = "👤 Karis (Hero)" if is_rpg else "👤 Karis (나)"
        header = ctk.CTkLabel(row, text=f"{tag_text}  {time_str}", font=ctk.CTkFont(size=10, weight="bold"), text_color=THEME["primary"])
        header.pack(anchor="e", padx=(0, 4), pady=(0, 2))

        bubble = ctk.CTkFrame(
            row,
            corner_radius=14,
            fg_color=THEME["user_bubble"],
            border_width=1,
            border_color=THEME["user_border"]
        )
        bubble.pack(anchor="e", padx=(60, 0))

        lbl = ctk.CTkLabel(
            bubble,
            text=user_text,
            font=ctk.CTkFont(family="Pretendard", size=12),
            text_color=THEME["text_main"],
            wraplength=620,
            justify="left"
        )
        lbl.pack(padx=14, pady=8)

    def _add_coaching_card(self, parent, coaching: TurnCoaching, is_rpg=False):
        card = ctk.CTkFrame(
            parent,
            corner_radius=12,
            fg_color=THEME["coach_bg"],
            border_width=1,
            border_color=THEME["coach_border"]
        )
        card.pack(fill="x", padx=10, pady=(6, 8))

        lang_cfg = self.get_cur_lang_cfg()

        if not coaching.is_flawless:
            title_txt = f"💡 [1:1 {lang_cfg['key']} 정밀 코칭 카드]" if not is_rpg else "🛡️ [COACHING SHIELD HIT! +15 EXP]"
            c_title = ctk.CTkLabel(card, text=title_txt, font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["coach_accent"])
            c_title.pack(anchor="w", padx=14, pady=(8, 3))

            c_rec = ctk.CTkLabel(
                card,
                text=f"✨ 모범 교정: \"{coaching.corrected_sentence}\"",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="#2F855A",
                wraplength=650,
                justify="left"
            )
            c_rec.pack(anchor="w", padx=14, pady=2)

            c_exp = ctk.CTkLabel(
                card,
                text=f"📝 뉘앙스 해설: {coaching.korean_feedback}",
                font=ctk.CTkFont(size=10),
                text_color=THEME["text_main"],
                wraplength=650,
                justify="left"
            )
            c_exp.pack(anchor="w", padx=14, pady=(3, 10))
        else:
            p_text = "🟢 완벽하고 자연스러운 원어민 표현입니다! (+30 EXP)" if not is_rpg else "⚡ ✨ CRITICAL PERFECT HIT! (+30 EXP 획득)"
            lbl_perf = ctk.CTkLabel(
                card,
                text=p_text,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="#2F855A",
                justify="center"
            )
            lbl_perf.pack(fill="x", padx=14, pady=10)

    def _add_ai_bubble(self, parent, role, reply_text, time_str, is_rpg=False, translation_text=""):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=6, pady=4)

        # 1. 상단 헤더 줄 (태그 + 시간 + [🌐 번역] 버튼)
        header_row = ctk.CTkFrame(row, fg_color="transparent")
        header_row.pack(fill="x", padx=(4, 0), pady=(0, 2))

        tag_text = f"👾 [BOSS] {role}" if is_rpg else f"🤖 {role}"
        header = ctk.CTkLabel(header_row, text=f"{tag_text}  {time_str}", font=ctk.CTkFont(size=10, weight="bold"), text_color=THEME["accent_blue"])
        header.pack(side="left")

        # 2. 말풍선 컨테이너
        bubble = ctk.CTkFrame(
            row,
            corner_radius=14,
            fg_color=THEME["ai_bubble"],
            border_width=1,
            border_color=THEME["ai_border"]
        )
        bubble.pack(anchor="w", padx=(0, 60))

        # 3. 외국어 원문 메시지
        lbl_msg = ctk.CTkLabel(
            bubble,
            text=reply_text,
            font=ctk.CTkFont(family="Pretendard", size=12),
            text_color=THEME["text_main"],
            wraplength=620,
            justify="left"
        )
        lbl_msg.pack(anchor="w", padx=14, pady=(8, 6))

        # 4. 한국어 번역 카드 프레임 (기본은 숨김)
        trans_box = ctk.CTkFrame(
            bubble,
            fg_color="#E2E8F0",
            corner_radius=10,
            border_width=1,
            border_color="#CBD5E1"
        )
        
        lbl_trans = ctk.CTkLabel(
            trans_box,
            text=f"🇰🇷 [한국어 해석]\n{translation_text}" if translation_text else "🇰🇷 [한국어 해석]\n번역을 불러오는 중...",
            font=ctk.CTkFont(family="Pretendard", size=11),
            text_color="#1E293B",
            wraplength=580,
            justify="left"
        )
        lbl_trans.pack(anchor="w", padx=12, pady=6)

        # 토글 상태 클로저
        state = {
            "is_open": False,
            "trans_text": translation_text
        }

        def toggle_trans():
            if not state["is_open"]:
                state["is_open"] = True
                btn_trans.configure(
                    text="🌐 번역 닫기",
                    fg_color=THEME["primary"],
                    hover_color=THEME["primary_hover"],
                    text_color="#FFFFFF"
                )
                trans_box.pack(fill="x", padx=10, pady=(0, 8))

                # 번역 데이터가 비어있으면 백그라운드 API 번역 실행
                if not state["trans_text"]:
                    def _fetch_trans():
                        try:
                            lang_cfg = self.get_cur_lang_cfg()
                            prompt = f"다음 {lang_cfg['name_en']} 문장을 한국어로 자연스럽고 정확하게 번역해줘. 설명 없이 오직 한국어 번역 문장만 응답해줘:\n\"{reply_text}\""
                            t_res = generate_content_with_fallback(prompt)
                            t_text = t_res.text.strip()
                            state["trans_text"] = t_text
                            self.after(0, lambda: lbl_trans.configure(text=f"🇰🇷 [한국어 해석]\n{t_text}"))
                        except Exception as ex:
                            self.after(0, lambda: lbl_trans.configure(text=f"⚠️ 번역 로드 실패: {ex}"))
                    threading.Thread(target=_fetch_trans, daemon=True).start()
            else:
                state["is_open"] = False
                btn_trans.configure(
                    text="🌐 번역",
                    fg_color="#E2E8F0",
                    hover_color="#CBD5E1",
                    text_color="#475569"
                )
                trans_box.pack_forget()

        # [🌐 번역] 버튼 배치
        btn_trans = ctk.CTkButton(
            header_row,
            text="🌐 번역",
            font=ctk.CTkFont(family="Pretendard", size=10, weight="bold"),
            fg_color="#E2E8F0",
            hover_color="#CBD5E1",
            text_color="#475569",
            width=58,
            height=20,
            corner_radius=6,
            command=toggle_trans
        )
        btn_trans.pack(side="left", padx=(10, 0))

    # =========================================================================
    # 음성 입출력 및 다시 듣기
    # =========================================================================
    def on_r_pressed(self, event):
        focused = self.focus_get()
        if focused in [self.fl_txt_input, self.rpg_txt_input, self.fl_entry_custom_ai, self.fl_entry_condition]:
            return
        self.replay_last_speech()

    def replay_last_speech(self):
        if self.last_ai_reply_text:
            threading.Thread(target=play_tts_sound, args=(self.last_ai_reply_text, self.last_ai_reply_voice), daemon=True).start()
        else:
            messagebox.showinfo("안내", "먼저 롤플레잉 세션을 시작해 주세요!")

    def on_space_pressed(self, event):
        focused = self.focus_get()
        if focused in [self.fl_txt_input, self.rpg_txt_input, self.fl_entry_custom_ai, self.fl_entry_condition]:
            return
        cur_tab = self.tabview.get()
        if "Modern Fluent" in cur_tab or "Gamified RPG" in cur_tab:
            self.toggle_mic()

    def toggle_mic(self):
        if not self.current_scenario:
            messagebox.showinfo("안내", "먼저 '🎬 롤플레잉 세션 시작' 또는 '🎲 랜덤 퀘스트 수락'을 눌러주세요!")
            return

        if not self.is_recording:
            self.is_recording = True
            self.fl_btn_mic.configure(text="⏹️ 녹음 완료 (클릭하여 전송)", fg_color=THEME["primary"], hover_color=THEME["primary_hover"])
            self.rpg_btn_mic.configure(text="🛡️ [RECORDING] 말씀하신 뒤 클릭하여 전송!", fg_color=THEME["primary"], hover_color=THEME["primary_hover"])
            self.audio_q = queue.Queue()

            def _callback(indata, frames, time_info, status):
                self.audio_q.put(bytes(indata))

            self.audio_stream = sd.RawInputStream(samplerate=16000, channels=1, dtype='int16', callback=_callback)
            self.audio_stream.start()
        else:
            self.is_recording = False
            self.fl_btn_mic.configure(text="⏳ Gemini 분석 중...", fg_color="#F59E0B", state="disabled")
            self.rpg_btn_mic.configure(text="⏳ 음성 분석 & 데미지 계산 중...", fg_color="#F59E0B", state="disabled")
            self.audio_stream.stop()
            self.audio_stream.close()

            threading.Thread(target=self._process_audio, daemon=True).start()

    def _process_audio(self):
        audio_frames = []
        while not self.audio_q.empty():
            audio_frames.append(self.audio_q.get())

        full_audio = b"".join(audio_frames)
        wav_file = os.path.join(tempfile.gettempdir(), f"input_{uuid.uuid4().hex[:6]}.wav")

        with wave.open(wav_file, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(full_audio)

        if os.path.exists(wav_file) and os.path.getsize(wav_file) > 1000:
            with open(wav_file, "rb") as f:
                audio_bytes = f.read()
            audio_part = types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav")
            self.call_gemini_turn(audio_part=audio_part)
        else:
            self.after(0, self.reset_mic_buttons)

        if os.path.exists(wav_file):
            try:
                os.remove(wav_file)
            except Exception:
                pass

    def send_text_fluent(self):
        text = self.fl_txt_input.get().strip()
        if not text or not self.current_scenario:
            return
        self.fl_txt_input.delete(0, "end")
        self.disable_mic_buttons()
        threading.Thread(target=self.call_gemini_turn, kwargs={"user_text": text}, daemon=True).start()

    def send_text_rpg(self):
        text = self.rpg_txt_input.get().strip()
        if not text or not self.current_scenario:
            return
        self.rpg_txt_input.delete(0, "end")
        self.disable_mic_buttons()
        threading.Thread(target=self.call_gemini_turn, kwargs={"user_text": text}, daemon=True).start()

    def disable_mic_buttons(self):
        self.fl_btn_mic.configure(state="disabled")
        self.rpg_btn_mic.configure(state="disabled")

    def reset_mic_buttons(self):
        self.fl_btn_mic.configure(text="🎤 마이크 녹음 시작 (스페이스바)", fg_color=THEME["record_btn"], hover_color=THEME["record_hover"], state="normal")
        self.rpg_btn_mic.configure(text="⚔️ [SPACE] VOICE BATTLE (녹음 시작)", fg_color=THEME["purple_accent"], hover_color=THEME["purple_hover"], state="normal")

    def call_gemini_turn(self, audio_part=None, user_text=None):
        lang_cfg = self.get_cur_lang_cfg()
        diff_name = self.fl_diff_combo.get()
        diff_info = DIFFICULTY_OPTIONS[diff_name]
        custom_cond = self.fl_entry_condition.get().strip()

        context_full = self.current_scenario['context']
        if custom_cond:
            context_full += f"\n[추가 조건]: {custom_cond}"

        system_prompt = f"""
당신은 '{self.current_scenario['role']}' 역할이며, 동시에 학습자의 '1:1 원어민 {lang_cfg['name_en']}({lang_cfg['key']}) 튜터'입니다.
[학습 대상 언어]: {lang_cfg['name_en']} ({lang_cfg['key']})
[상황 배경]: {context_full}
[학습자 회화 레벨]: {diff_name}
- 레벨별 지침: {diff_info['desc']}
- 언어별 코칭 지침: {lang_cfg['coaching_guide']}

사용자의 음성/텍스트 입력을 바탕으로 아래 규격의 JSON으로 응답하세요:
1. roleplay_reply: 상대방 역할로서의 {lang_cfg['name_en']} 대답 (1~2문장으로 생동감 있게 대화 유도)
2. reply_translation: 상대방 대답(roleplay_reply)의 자연스럽고 정확한 한국어 번역
3. coaching:
   - recognized_user_text: 사용자가 실제로 발화한 {lang_cfg['name_en']} 문장 전사
   - is_flawless: 해당 레벨 기준 문법/뉘앙스가 자연스러우면 True, 어색함/오류가 있으면 False
   - corrected_sentence: 해당 레벨에 어울리는 가장 자연스러운 원어민 추천 교정 문장 ({lang_cfg['name_en']})
   - korean_feedback: 왜 어색한지, 어떻게 말하면 더 좋은지 친절하고 명쾌한 한국어 해설
"""
        contents = [f"이전 대화 기록: {self.chat_history}"]
        if audio_part:
            contents.extend([audio_part, f"오디오 음성을 듣고 상대방 대답({lang_cfg['name_en']}), 한국어 번역, 코칭을 생성하세요."])
        else:
            contents.extend([f"사용자 입력: \"{user_text}\"", f"상대방 대답({lang_cfg['name_en']}), 한국어 번역, 코칭을 생성하세요."])

        try:
            res = generate_content_with_fallback(
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=TurnResponse,
                    temperature=0.3
                )
            )
            result = TurnResponse.model_validate_json(res.text)
            user_said = result.coaching.recognized_user_text

            self.session_turns += 1
            self.chat_history.append({"role": "user", "parts": [user_said]})
            self.chat_history.append({"role": "model", "parts": [result.roleplay_reply]})

            self.last_ai_reply_text = result.roleplay_reply
            self.last_ai_reply_voice = self.current_scenario['voice']

            self.after(0, self.update_dual_chat_ui, user_said, result)
            play_tts_sound(result.roleplay_reply, self.current_scenario['voice'])

        except Exception as e:
            print(f"⚠️ 대화 처리 오류: {e}")
        finally:
            self.after(0, self.reset_mic_buttons)

    def update_dual_chat_ui(self, user_said: str, result: TurnResponse):
        now_time = datetime.now().strftime("%H:%M")
        reply_trans = getattr(result, 'reply_translation', '')

        # 1. Fluent 뷰 업데이트
        self._add_user_bubble(self.fl_chat_scroll, user_said, now_time, is_rpg=False)
        self._add_coaching_card(self.fl_chat_scroll, result.coaching, is_rpg=False)
        self._add_ai_bubble(self.fl_chat_scroll, self.current_scenario['role'], result.roleplay_reply, now_time, is_rpg=False, translation_text=reply_trans)

        # 2. RPG 뷰 업데이트
        self._add_user_bubble(self.rpg_chat_scroll, user_said, now_time, is_rpg=True)
        self._add_coaching_card(self.rpg_chat_scroll, result.coaching, is_rpg=True)
        self._add_ai_bubble(self.rpg_chat_scroll, self.current_scenario['role'], result.roleplay_reply, now_time, is_rpg=True, translation_text=reply_trans)

        # 오답 노트 저장
        reviews = self.load_reviews()
        lang_cfg = self.get_cur_lang_cfg()
        if not result.coaching.is_flawless:
            mistake_item = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "language": lang_cfg['key'],
                "voice": self.current_scenario.get('voice', lang_cfg['default_voice']),
                "category": self.current_scenario['category'],
                "scenario": self.current_scenario['title'],
                "original": user_said,
                "corrected": result.coaching.corrected_sentence,
                "explanation": result.coaching.korean_feedback
            }
            self.new_mistakes.append(mistake_item)
            reviews.append(mistake_item)
            self.save_reviews(reviews)
        else:
            self.session_flawless += 1

        prof = self.get_current_profile()
        prof["exp"] += 30 if result.coaching.is_flawless else 15
        prof["total_turns"] += 1
        if result.coaching.is_flawless:
            prof["flawless_turns"] += 1
        self.save_profile()

    # =========================================================================
    # [TAB 3] 스마트 오답노트 & 퀴즈
    # =========================================================================
    def build_review_tab(self):
        top_bar = ctk.CTkFrame(self.tab_review, fg_color="transparent")
        top_bar.pack(fill="x", padx=16, pady=10)

        lbl_info = ctk.CTkLabel(top_bar, text="📚 보관된 다국어 교정 오답 카드 목록", font=ctk.CTkFont(size=14, weight="bold"), text_color=THEME["text_main"])
        lbl_info.pack(side="left")

        btn_start_quiz = ctk.CTkButton(
            top_bar,
            text="🎯 3문제 스피드 복습 퀴즈 (+20 EXP)",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=THEME["primary"],
            hover_color=THEME["primary_hover"],
            text_color="#FFFFFF",
            corner_radius=10,
            command=self.run_quiz_modal
        )
        btn_start_quiz.pack(side="right")

        self.review_cards_scroll = ctk.CTkScrollableFrame(
            self.tab_review,
            corner_radius=14,
            fg_color=THEME["card_bg"],
            border_width=1,
            border_color=THEME["card_border"]
        )
        self.review_cards_scroll.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        self.tabview.configure(command=self.on_tab_changed)

    def on_tab_changed(self):
        cur_tab = self.tabview.get()
        if "오답노트" in cur_tab:
            self.refresh_review_tab()
        elif "대시보드" in cur_tab:
            self.refresh_dashboard_tab()

    def refresh_review_tab(self):
        for widget in self.review_cards_scroll.winfo_children():
            widget.destroy()

        reviews = self.load_reviews()
        if not reviews:
            lbl_empty = ctk.CTkLabel(self.review_cards_scroll, text="🎉 보관된 오답 카드가 없습니다. 완벽합니다!", font=ctk.CTkFont(size=13), text_color=THEME["text_sub"])
            lbl_empty.pack(pady=40)
            return

        for item in reversed(reviews):
            card = ctk.CTkFrame(
                self.review_cards_scroll,
                corner_radius=12,
                fg_color="#F8FAFC",
                border_width=1,
                border_color=THEME["card_border"]
            )
            card.pack(fill="x", padx=6, pady=4)

            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=12, pady=(8, 2))

            lang_tag = item.get('language', '영어')
            ctk.CTkLabel(top_row, text=f"[{lang_tag}] [{item.get('category', '-')}] {item.get('scenario', '-')}", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["primary"]).pack(side="left")
            ctk.CTkLabel(top_row, text=item.get("timestamp", "-"), font=ctk.CTkFont(size=10), text_color=THEME["text_sub"]).pack(side="right")

            ctk.CTkLabel(card, text=f"❌ 내가 쓴 표현: \"{item.get('original', '')}\"", font=ctk.CTkFont(size=11), text_color="#DC2626").pack(anchor="w", padx=12, pady=1)
            ctk.CTkLabel(card, text=f"✨ 모범 교정문: \"{item.get('corrected', '')}\"", font=ctk.CTkFont(size=11, weight="bold"), text_color="#2F855A").pack(anchor="w", padx=12, pady=1)
            ctk.CTkLabel(card, text=f"📝 해설: {item.get('explanation', '')}", font=ctk.CTkFont(size=10), text_color=THEME["text_main"], wraplength=850, justify="left").pack(anchor="w", padx=12, pady=(1, 6))

            item_voice = item.get('voice', 'en-US-ChristopherNeural')
            btn_listen = ctk.CTkButton(
                card,
                text=f"🔊 [{lang_tag}] 발음 듣기",
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color="#FFFFFF",
                hover_color="#E2E8F0",
                text_color=THEME["accent_blue"],
                border_width=1,
                border_color=THEME["card_border"],
                height=28,
                width=130,
                corner_radius=8,
                command=lambda t=item.get('corrected', ''), v=item_voice: threading.Thread(target=play_tts_sound, args=(t, v), daemon=True).start()
            )
            btn_listen.pack(anchor="e", padx=12, pady=(0, 8))

    def run_quiz_modal(self):
        reviews = self.load_reviews()
        if not reviews:
            messagebox.showinfo("안내", "저장된 오답 카드가 없습니다. 먼저 롤플레잉 세션을 진행해보세요!")
            return

        quiz_items = random.sample(reviews, min(3, len(reviews)))

        quiz_win = ctk.CTkToplevel(self)
        quiz_win.title("🎯 스마트 오답 리콜 퀴즈")
        quiz_win.geometry("640x480")
        quiz_win.configure(fg_color=THEME["app_bg"])
        quiz_win.grab_set()

        q_idx = [0]

        lbl_q_num = ctk.CTkLabel(quiz_win, text="", font=ctk.CTkFont(size=13, weight="bold"), text_color=THEME["primary"])
        lbl_q_num.pack(anchor="w", padx=20, pady=(16, 6))

        lbl_orig = ctk.CTkLabel(
            quiz_win,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#DC2626",
            fg_color="#FEE2E2",
            corner_radius=10,
            wraplength=580,
            justify="left"
        )
        lbl_orig.pack(fill="x", padx=20, pady=6, ipady=6)

        lbl_hint = ctk.CTkLabel(
            quiz_win,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=THEME["text_main"],
            fg_color=THEME["card_bg"],
            corner_radius=10,
            wraplength=580,
            justify="left"
        )
        lbl_hint.pack(fill="x", padx=20, pady=6, ipady=8)

        lbl_ans = ctk.CTkLabel(quiz_win, text="", font=ctk.CTkFont(size=13, weight="bold"), text_color="#2F855A", wraplength=580)
        lbl_ans.pack(fill="x", padx=20, pady=10)

        btn_show = ctk.CTkButton(
            quiz_win,
            text="✨ 정답 확인 및 원어민 음성 듣기",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=THEME["coach_accent"],
            hover_color="#A0630D",
            text_color="#FFFFFF",
            height=38,
            corner_radius=10
        )
        btn_show.pack(fill="x", padx=20, pady=4)

        btn_next = ctk.CTkButton(
            quiz_win,
            text="다음 문제 👉 (+20 EXP)",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=THEME["primary"],
            hover_color=THEME["primary_hover"],
            text_color="#FFFFFF",
            height=38,
            corner_radius=10,
            state="disabled"
        )
        btn_next.pack(fill="x", padx=20, pady=4)

        def load_question():
            item = quiz_items[q_idx[0]]
            lang_tag = item.get('language', '영어')
            lbl_q_num.configure(text=f"문제 [{q_idx[0] + 1}/{len(quiz_items)}] - [{lang_tag}] 상황: {item.get('scenario', '-')}")
            lbl_orig.configure(text=f"❌ 내가 썼던 어색한 표현:\n\"{item.get('original', '')}\"")
            lbl_hint.configure(text=f"💡 교정 힌트:\n{item.get('explanation', '')}")
            lbl_ans.configure(text="")
            btn_show.configure(state="normal")
            btn_next.configure(state="disabled")

        def show_answer():
            item = quiz_items[q_idx[0]]
            lbl_ans.configure(text=f"✨ 모범 교정문: \"{item.get('corrected', '')}\"")
            btn_show.configure(state="disabled")
            btn_next.configure(state="normal")
            v = item.get("voice", "en-US-ChristopherNeural")
            threading.Thread(target=play_tts_sound, args=(item.get("corrected", ""), v), daemon=True).start()

        def next_question():
            prof = self.get_current_profile()
            prof["exp"] += 20
            self.save_profile()
            q_idx[0] += 1
            if q_idx[0] < len(quiz_items):
                load_question()
            else:
                messagebox.showinfo("축하합니다!", f"🎉 퀴즈 완료!\n총 +{len(quiz_items)*20} EXP를 획득하셨습니다.")
                quiz_win.destroy()

        btn_show.configure(command=show_answer)
        btn_next.configure(command=next_question)
        load_question()

    # =========================================================================
    # [TAB 4] 실력 대시보드
    # =========================================================================
    def build_dashboard_tab(self):
        dash_frame = ctk.CTkFrame(self.tab_dashboard, fg_color="transparent")
        dash_frame.pack(fill="both", expand=True, padx=25, pady=20)

        self.lbl_dash_tier = ctk.CTkLabel(dash_frame, text="", font=ctk.CTkFont(family="Pretendard", size=18, weight="bold"), text_color=THEME["primary"])
        self.lbl_dash_tier.pack(anchor="w", pady=(0, 10))

        cards_row = ctk.CTkFrame(dash_frame, fg_color="transparent")
        cards_row.pack(fill="x", pady=(0, 15))

        self.card_turns = ctk.CTkFrame(cards_row, corner_radius=12, fg_color=THEME["card_bg"], border_width=1, border_color=THEME["card_border"])
        self.card_turns.pack(side="left", fill="both", expand=True, padx=(0, 8), ipady=8)
        self.lbl_stat_turns = ctk.CTkLabel(self.card_turns, text="", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["accent_blue"])
        self.lbl_stat_turns.pack(padx=14, pady=8)

        self.card_acc = ctk.CTkFrame(cards_row, corner_radius=12, fg_color=THEME["card_bg"], border_width=1, border_color=THEME["card_border"])
        self.card_acc.pack(side="left", fill="both", expand=True, padx=4, ipady=8)
        self.lbl_stat_acc = ctk.CTkLabel(self.card_acc, text="", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["primary"])
        self.lbl_stat_acc.pack(padx=14, pady=8)

        self.card_reviews = ctk.CTkFrame(cards_row, corner_radius=12, fg_color=THEME["card_bg"], border_width=1, border_color=THEME["card_border"])
        self.card_reviews.pack(side="right", fill="both", expand=True, padx=(8, 0), ipady=8)
        self.lbl_stat_reviews = ctk.CTkLabel(self.card_reviews, text="", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["coach_accent"])
        self.lbl_stat_reviews.pack(padx=14, pady=8)

        ctk.CTkLabel(dash_frame, text="🏆 티어 승급 기준표", font=ctk.CTkFont(size=13, weight="bold"), text_color=THEME["text_main"]).pack(anchor="w", pady=(10, 4))

        roadmap_txt = (
            "• Bronze (Tourist)       : 0 ~ 199 EXP\n"
            "• Silver (City Hopper)   : 200 ~ 599 EXP\n"
            "• Gold (Communicator)    : 600 ~ 1,199 EXP\n"
            "• Platinum (Negotiator)  : 1,200 ~ 1,999 EXP\n"
            "• Diamond (Crisis Master): 2,000 ~ 2,999 EXP\n"
            "• Master (Native Flow)   : 3,000+ EXP"
        )
        lbl_rm_content = ctk.CTkLabel(
            dash_frame,
            text=roadmap_txt,
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=THEME["text_main"],
            fg_color=THEME["card_bg"],
            corner_radius=12,
            border_width=1,
            border_color=THEME["card_border"],
            justify="left"
        )
        lbl_rm_content.pack(fill="x", pady=4, ipady=10, ipadx=14)

    def refresh_dashboard_tab(self):
        reviews = self.load_reviews()
        prof = self.get_current_profile()
        total = prof["total_turns"]
        flawless = prof["flawless_turns"]
        acc = round((flawless / total * 100), 1) if total > 0 else 0.0

        lang_cfg = self.get_cur_lang_cfg()
        self.lbl_dash_tier.configure(text=f"{lang_cfg['flag']} [{lang_cfg['key']}] 🏆 현재 랭크: {prof['tier']} ({prof['exp']:,} EXP)")
        self.lbl_stat_turns.configure(text=f"🗣️ 총 대화 턴 수\n{total:,} 턴")
        self.lbl_stat_acc.configure(text=f"🟢 무결점 통과율\n{acc}% ({flawless}턴)")
        self.lbl_stat_reviews.configure(text=f"📁 오답 카드 보관량\n{len(reviews):,} 개")


if __name__ == "__main__":
    app = MultilingualMasteryApp()
    app.mainloop()
