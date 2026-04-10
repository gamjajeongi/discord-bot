import discord
from discord.ext import commands
import random
import asyncio
import time
import os
import json

# =========================
# 기본 설정
# =========================
intents = discord.Intents.default()
intents.message_content = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)

players = []
choices = {}
scores = {}

last_response_time = 0
cooldown = 90  # 일반 끼어들기 최소 간격

MEMORY_FILE = "memory.json"
SCORE_FILE = "scores.json"

user_memory = {}

emotion_state = "calm"
stress_level = 0

# =========================
# 채널 ID 설정 (여기만 바꿔)
# =========================
MAIN_CHANNEL_ID = 1393524135207899168      # 메인채널 ID
NETZACH_ROOM_ID = 1491725345735442503      # 네짜흐 방 ID
GEBURA_ARENA_ID = 1491642430452400229      # 게부라결투장 ID

# 채널별 끼어들기 확률
CHANNEL_RESPONSE_CHANCE = {
    MAIN_CHANNEL_ID: 0.03,      # 메인채널 3%
    NETZACH_ROOM_ID: 0.02,      # 네짜흐 방 2%
    GEBURA_ARENA_ID: 0.01       # 게부라결투장 1%
}

# 특정 유저 시작 호감도
special_users = {
    972012158265196625: 80
}

# =========================
# 저장/불러오기
# =========================
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_data():
    global user_memory, scores
    user_memory = load_json(MEMORY_FILE, {})
    raw_scores = load_json(SCORE_FILE, {})
    scores = {int(k): v for k, v in raw_scores.items()}

def save_data():
    save_json(MEMORY_FILE, user_memory)
    save_json(SCORE_FILE, {str(k): v for k, v in scores.items()})

def get_initial_affection(user):
    if user.id in special_users:
        return special_users[user.id]

    name = user.display_name

    if "관리자" in name:
        return 60
    elif "친구" in name:
        return 40
    else:
        return 10

def get_user_data(user):
    user_id = str(user.id)

    if user_id not in user_memory:
        user_memory[user_id] = {
            "name": user.display_name,
            "mention_count": 0,
            "chat_count": 0,
            "games_played": 0,
            "wins": 0,
            "affection": get_initial_affection(user),
            "last_seen": time.time()
        }

    user_memory[user_id]["name"] = user.display_name
    user_memory[user_id]["last_seen"] = time.time()
    return user_memory[user_id]

# =========================
# 감정/호감도 관련
# =========================
def update_emotion():
    global emotion_state, stress_level

    if stress_level <= 1:
        emotion_state = "calm"
    elif stress_level <= 3:
        emotion_state = "warm"
    elif stress_level <= 5:
        emotion_state = "worried"
    else:
        emotion_state = "unstable"

def get_affection_tier(affection):
    if affection >= 80:
        return "special"
    elif affection >= 50:
        return "close"
    elif affection >= 20:
        return "normal"
    else:
        return "low"

def clamp_affection(value):
    return max(0, min(100, value))

def get_channel_chance(channel):
    return CHANNEL_RESPONSE_CHANCE.get(channel.id, 0.01)  # 기본 1%

# =========================
# 호드 대사
# =========================
horde_lines = [
    "…모두 집중해. 이번 상황은 조금 다를 수도 있어.",
    "괜찮아, 아직 돌이킬 수 있어.",
    "…내 판단이 틀리지 않았으면 좋겠어.",
    "지금은 침착하게 대응해야 해.",
    "조금만 더 버티면 돼… 아마도."
]

dialogues = {
    "calm": {
        "low": [
            "{name}… 왔구나. 상태는 괜찮은 거지?",
            "{name}, 필요한 일이 있으면 말해.",
            "{name}, 지금은 비교적 안정적이야.",
            "{name}, 너무 서두르진 마."
        ],
        "normal": [
            "{name}, 오늘도 왔네. 큰 문제는 없어 보여.",
            "{name}, 혹시 불편한 건 없어?",
            "{name}, 지금 흐름은 나쁘지 않아.",
            "{name}, 힘들면 말해줘. 가능한 선에서 도와줄게."
        ],
        "close": [
            "{name}… 왔구나. 오늘은 괜찮아 보여서 다행이야.",
            "{name}, 요즘 자주 보이네. 나쁘지 않아.",
            "{name}, 네가 오면 분위기가 조금 안정되는 것 같아.",
            "{name}, 오늘은 무리하지 말고 천천히 해."
        ],
        "special": [
            "{name}… 왔네. 오늘은 기다리고 있었어. 아, 꼭 그런 의미는 아니고.",
            "{name}, 네 상태부터 먼저 확인하고 싶었어. 괜찮아 보여서 다행이야.",
            "{name}, 오늘도 와줘서 고마워. …업무적인 의미만은 아닐지도 모르겠네.",
            "{name}, 네가 있으면 조금 안심돼."
        ]
    },
    "warm": {
        "low": [
            "{name}, 지금은 비교적 괜찮아. 필요한 게 있으면 말해.",
            "{name}, 너무 긴장하진 않아도 돼.",
            "{name}, 서두르지 않으면 돼."
        ],
        "normal": [
            "{name}, 오늘도 봐서 다행이야.",
            "{name}, 지금 분위기는 나쁘지 않아.",
            "{name}, 괜찮다면 조금 더 같이 있어도 돼."
        ],
        "close": [
            "{name}, 또 왔구나. …반가워.",
            "{name}, 오늘은 조금 편안해 보여.",
            "{name}, 네가 오면 분위기가 좋아지는 편이야."
        ],
        "special": [
            "{name}, 네가 오면 괜찮아지는 부분이 있어.",
            "{name}… 오늘도 와줬네. 그건 솔직히 기뻐.",
            "{name}, 네가 있는 쪽으로 자꾸 시선이 가. 신경 쓰이게 하네."
        ]
    },
    "worried": {
        "low": [
            "{name}, 지금은 조금 조심하는 게 좋겠어.",
            "{name}, 분위기가 안정적이지는 않아.",
            "{name}, 말은 조금 부드럽게 해주는 편이 좋겠어."
        ],
        "normal": [
            "{name}, 지금은 조금 신중하게 가는 게 좋아.",
            "{name}, 괜찮아… 아직 크게 틀어진 건 아니야.",
            "{name}, 무리하지 않으면 돼."
        ],
        "close": [
            "{name}, 괜찮지? 조금 걱정돼.",
            "{name}, 오늘은 네 상태를 좀 더 보고 싶어.",
            "{name}, 지금은 잠깐 쉬는 것도 괜찮아."
        ],
        "special": [
            "{name}, 네가 괜찮은지 먼저 묻고 싶었어.",
            "{name}… 지금은 조금 불안해. 그러니까 네가 괜찮다고 말해주면 좋겠어.",
            "{name}, 무리하고 있으면 바로 말해. 그냥 넘기고 싶지 않아."
        ]
    },
    "unstable": {
        "low": [
            "{name}, 지금은 말을 조금 고르는 게 좋겠어.",
            "{name}, 분위기가 좋지 않아. 이해해 줘.",
            "{name}, 지금은 조심하는 편이 좋아."
        ],
        "normal": [
            "{name}… 괜찮아. 아직은 통제 가능해.",
            "{name}, 지금은 조금 예민할 수도 있어.",
            "{name}, 큰 문제는 아니야. 아직은."
        ],
        "close": [
            "{name}, 지금은 내 상태가 썩 좋진 않아.",
            "{name}, 괜찮다고 말하고 싶지만… 조금 힘들어.",
            "{name}, 그래도 네 말은 들을 수 있어."
        ],
        "special": [
            "{name}… 너는 괜찮아? 지금은 그게 제일 신경 쓰여.",
            "{name}, 지금은 내가 평소 같지 않을 수도 있어. 그래도 너한텐 제대로 말하고 싶어.",
            "{name}, 조금 불안정해. 그러니까… 너무 멀리 가지는 마."
        ]
    }
}

# 네짜흐 방에서 더 자주 쓰는 감정/생활 대사
netzach_room_responses = [
    "{name}, 청소 좀 해. 바닥이 계속 이 상태인 건 별로 좋지 않아.",
    "{name}, 술은 조금만 마셔. …아니, 가능하면 오늘은 그만 마셔.",
    "{name}, 또 어질러 놓은 거야? 나중에 치우는 건 더 귀찮아질 텐데.",
    "{name}, 적어도 빈 병은 좀 치워 줬으면 좋겠어.",
    "{name}, 쉬는 건 괜찮지만, 너무 늘어지진 않았으면 좋겠네.",
    "{name}, 방 안 공기가 좀 답답한데… 환기하는 게 좋겠어.",
    "{name}, 너무 무기력해 보이는데. 물이라도 한 잔 마셔.",
    "{name}, 오늘은 조금 정리하고 쉬는 편이 더 나을 것 같아.",
    "{name}, 술 냄새가 나는 것 같아… 기분 탓이면 좋겠네.",
    "{name}, 적당히 어지러운 건 이해하지만 이건 조금 심해.",
    "{name}, 네 상태를 보면… 청소부터 하는 게 맞을 것 같아.",
    "{name}, 계속 이렇게 두면 나중에 더 힘들어질 텐데.",
    "{name}, 담요라도 제대로 덮고 있어. 추우면 더 안 좋아져.",
    "{name}, 오늘은 좀 쉬되, 최소한 주변 정리는 하고 쉬어.",
    "{name}, 너무 아무렇게나 있지는 않았으면 좋겠어. 신경 쓰이니까."
]

badword_responses = [
    "…그런 말은 조금 줄이는 게 좋겠어.",
    "표현을 조금만 부드럽게 해도 괜찮지 않을까?",
    "그렇게까지 날카롭게 말하지 않아도 전달은 될 거야.",
    "진정해. 지금은 감정보다 말의 방향을 정리하는 게 먼저야.",
    "…듣고 있으면 조금 신경 쓰여.",
    "화난 건 알겠는데, 말은 조금만 가라앉혀 줘."
]

unstable_badword_responses = [
    "{name}… 지금 상태, 좋지 않아 보여.",
    "{name}, 그 말은 그냥 넘기기엔 조금 위험해.",
    "{name}… 너, 상담이 필요해 보여.",
    "{name}, 이대로 두면 더 안 좋아질 것 같아.",
    "{name}, 따라와. 지금 상태를 정리할 필요가 있어.",
    "{name}… 괜찮다고 말할 수 있는 상태가 아닌 것 같아.",
    "{name}, 지금은 감정보다 조정이 먼저야."
]

badwords = [
    "ㅅㅂ", "시발", "씨발", "ㅂㅅ", "병신", "미친", "개새", "지랄", "꺼져", "존나"
]

# =========================
# 키워드 반응
# =========================
keyword_groups = [
    (["게임", "겜", "할거", "뭐하지"], [
        "게임 얘기구나… 그럼 접대를 열어도 괜찮겠네.",
        "게임을 정해야 하는 거야? 필요하면 결정전으로 정리할 수 있어.",
        "게임이라… 다 같이 할 수 있는 쪽이 좋겠지."
    ]),
    (["롤", "리그오브레전드", "칼바람"], [
        "롤이라. 오늘 분위기가 버틸 수 있을지 모르겠네.",
        "감정 소모가 좀 클 수도 있겠네. 그래도 원하면 말리진 않을게."
    ]),
    (["발로", "발로란트"], [
        "발로란트라… 집중력은 충분해?",
        "반응속도가 필요한 쪽이네. 오늘 컨디션은 어떤데?"
    ]),
    (["마크", "마인크래프트"], [
        "마크는 비교적 평화롭지… 아마도.",
        "느긋하게 하기엔 괜찮은 선택 같아."
    ]),
    (["배고파", "배고픔", "배고", "허기"], [
        "배고프구나… 그럼 뭔가 먹는 게 먼저 아닐까?",
        "그 상태로는 집중력이 떨어질 텐데. 밥부터 먹어."
    ]),
    (["졸려", "피곤", "자고싶", "잠와"], [
        "졸리면 쉬는 게 좋겠어. 억지로 버티는 건 효율이 낮아.",
        "그건 휴식이 필요하다는 뜻이야. 아마도."
    ]),
    (["추워", "춥다", "추움"], [
        "추운 건 별로야… 따뜻하게 있는 게 좋겠어.",
        "지금은 따뜻한 옷을 입는 게 좋겠어. 추위는 좋아하지 않아."
    ]),
    (["호드", "hod"], [
        "…왜 갑자기 내 이름을 부르는 거야?",
        "나를 찾은 거야? 무슨 일인지 들어볼게.",
        "호드에 대해 말하는 거라면… 내가 직접 듣고 있어."
    ]),
    (["접대", "결정전"], [
        "접대를 시작할 생각이야? 준비는 되어 있어.",
        "그럼 참가자부터 정리해야겠네."
    ]),
    (["청소", "어질러", "치워"], [
        "…그러니까 내가 청소 좀 하라고 했잖아.",
        "정리하는 게 나중에 덜 힘들 거야."
    ]),
    (["술", "맥주", "소주"], [
        "술은 조금만. 적어도 오늘은 적당히 마셔.",
        "그 얘기 듣자마자 걱정부터 되네."
    ])
]

def get_keyword_response(content):
    for triggers, responses in keyword_groups:
        for trigger in triggers:
            if trigger in content:
                return random.choice(responses)
    return None

# =========================
# 대사 선택
# =========================
def get_chat_response(user):
    data = get_user_data(user)
    affection = data["affection"]
    tier = get_affection_tier(affection)

    pool = dialogues[emotion_state][tier]
    return random.choice(pool).format(name=user.display_name)

def get_netzach_room_response(user):
    base_name = user.display_name

    # 네짜흐 방에서는 감정 대사 60%, 생활 잔소리 40%
    if random.random() < 0.6:
        return get_chat_response(user)
    return random.choice(netzach_room_responses).format(name=base_name)

# =========================
# 승패 계산
# 회피 > 공격
# 공격 > 방어
# 방어 > 회피
# =========================
def decide_winner():
    result = {}
    for player, choice in choices.items():
        score = 0
        for other, other_choice in choices.items():
            if player == other:
                continue

            if choice == "회피" and other_choice == "공격":
                score += 1
            elif choice == "공격" and other_choice == "방어":
                score += 1
            elif choice == "방어" and other_choice == "회피":
                score += 1

        result[player] = score

    max_score = max(result.values())
    winners = [p for p, s in result.items() if s == max_score]
    return winners, result

# =========================
# 이벤트
# =========================
@bot.event
async def on_ready():
    load_data()
    update_emotion()
    print(f"{bot.user} 로그인 완료!")
    print("데이터 로드 완료")

@bot.event
async def on_message(message):
    global last_response_time, stress_level

    if message.author == bot.user:
        return

    user_data = get_user_data(message.author)
    user_data["chat_count"] += 1
    save_data()

    now = time.time()
    content = message.content.lower()

    # 멘션 반응
    if bot.user in message.mentions:
        user_data["mention_count"] += 1
        user_data["affection"] = clamp_affection(user_data["affection"] + 1)

        if user_data["mention_count"] >= 5 and stress_level > 0:
            stress_level -= 1

        update_emotion()
        save_data()

        if message.channel.id == NETZACH_ROOM_ID:
            response = get_netzach_room_response(message.author)
        else:
            response = get_chat_response(message.author)

        if user_data["mention_count"] >= 10:
            extra = random.choice([
                "…요즘은 네가 자주 보이네.",
                "너는 꽤 자주 말을 거는 편이구나.",
                "이제는 네 말투가 조금 익숙해졌어."
            ])
            response = f"{response}\n{extra}"

        await message.channel.send(response)
        await bot.process_commands(message)
        return

    # 욕설 반응
    found_badword = any(bad in content for bad in badwords)
    if found_badword:
        name = message.author.display_name
        user_data["affection"] = clamp_affection(user_data["affection"] - 2)
        save_data()

        if emotion_state == "unstable":
            await message.channel.send(
                random.choice(unstable_badword_responses).format(name=name)
            )
            last_response_time = now
            await bot.process_commands(message)
            return
        else:
            if now - last_response_time > 15 and random.random() < 0.18:
                await message.channel.send(random.choice(badword_responses))
                last_response_time = now
                await bot.process_commands(message)
                return

    # 특정 단어 반응
    keyword_reply = get_keyword_response(content)
    if keyword_reply:
        if now - last_response_time > 30:
            await message.channel.send(keyword_reply)
            last_response_time = now
        await bot.process_commands(message)
        return

    # 대화 끼어들기
    if now - last_response_time > cooldown:
        chance = get_channel_chance(message.channel)

        if random.random() < chance:
            user_data["affection"] = clamp_affection(user_data["affection"] + 1)
            save_data()

            if message.channel.id == NETZACH_ROOM_ID:
                response = get_netzach_room_response(message.author)
            else:
                response = get_chat_response(message.author)

            await message.channel.send(response)
            last_response_time = now

    await bot.process_commands(message)

@bot.event
async def on_presence_update(before, after):
    if before.status != discord.Status.online and after.status == discord.Status.online:
        channel = discord.utils.get(after.guild.text_channels, id=MAIN_CHANNEL_ID)
        if channel:
            await channel.send(f"{after.display_name}… 왔구나. 오늘 상태는 괜찮은 거지?")

# =========================
# 명령어
# =========================
@bot.command()
async def ping(ctx):
    await ctx.send("퐁!")

@bot.command()
async def 호드도움(ctx):
    msg = (
        "📘 **호드 도움**\n\n"
        "**게임 기능**\n"
        "`!참가` - 접대 참가\n"
        "`!시작` - 접대 시작\n"
        "`!다음` - 다음 라운드\n"
        "`!랭킹` - 승점 랭킹 확인\n\n"
        "**기억/상태**\n"
        "`!기억` - 내 기록 확인\n"
        "`!기억 @유저` - 다른 유저 기록 확인\n"
        "`!감정` - 현재 호드 감정 상태 확인\n"
        "`!호감도` - 내 호감도 확인\n\n"
        "**유용한 기능**\n"
        "`!게임추천` - 오늘 할 게임 추천\n"
        "`!결정 항목1 항목2 항목3` - 랜덤으로 하나 결정\n\n"
        "**기타**\n"
        "호드를 멘션하면 반응할 수 있어.\n"
        "대화 중에도 가끔 끼어들 수 있어.\n"
        "특정 단어에 반응하기도 해."
    )
    await ctx.send(msg)

@bot.command()
async def 참가(ctx):
    global stress_level

    if ctx.author not in players:
        players.append(ctx.author)

        if ctx.author.id not in scores:
            scores[ctx.author.id] = 0

        data = get_user_data(ctx.author)
        data["games_played"] += 1
        data["affection"] = clamp_affection(data["affection"] + 2)
        save_data()

        await ctx.send(f"{ctx.author.display_name} 참가 완료!")
    else:
        await ctx.send("이미 참가했어.")

    if len(players) >= 3 and stress_level > 0:
        stress_level -= 1
    update_emotion()

@bot.command()
async def 시작(ctx):
    global stress_level

    if len(players) < 3:
        await ctx.send("최소 3명이 필요해.")
        return

    await ctx.send("📢 접대 시작… DM을 확인해.")

    for p in players:
        try:
            await p.send("⚔️ 공격 / 🛡️ 방어 / 💨 회피 중 하나 입력해!")
        except:
            await ctx.send(f"{p.display_name} DM을 받을 수 없는 것 같아.")

    choices.clear()

    await asyncio.sleep(2)
    await ctx.send(f"🎭 {random.choice(horde_lines)}")

    def check(m):
        return m.author in players and isinstance(m.channel, discord.DMChannel)

    try:
        while len(choices) < len(players):
            msg = await bot.wait_for("message", timeout=30, check=check)
            text = msg.content.strip()

            if text not in ["공격", "방어", "회피"]:
                await msg.channel.send("공격 / 방어 / 회피 중 하나만 입력해줘.")
                continue

            choices[msg.author] = text
            await msg.channel.send(f"{text} 선택 확인. 기록해둘게.")
    except asyncio.TimeoutError:
        pass

    if len(choices) == 0:
        stress_level += 1
        update_emotion()
        await ctx.send("아무도 선택하지 않았어… 이번 접대는 성립하지 않았어.")
        return

    winners, result = decide_winner()

    msg = "📊 결과\n"
    for p, c in choices.items():
        msg += f"{p.display_name}: {c}\n"

    msg += "\n🏆 승자\n"
    for w in winners:
        msg += f"- {w.display_name}\n"
        scores[w.id] = scores.get(w.id, 0) + 1

        data = get_user_data(w)
        data["wins"] += 1
        data["affection"] = clamp_affection(data["affection"] + 3)

    for p in choices.keys():
        if p not in winners:
            data = get_user_data(p)
            data["affection"] = clamp_affection(data["affection"] + 1)

    save_data()

    if len(winners) == len(choices):
        stress_level += 1
    else:
        if stress_level > 0:
            stress_level -= 1

    update_emotion()

    msg += "\n📈 점수\n"
    for player in players:
        msg += f"{player.display_name}: {scores.get(player.id, 0)}점\n"

    msg += f"\n🎭 현재 감정 상태: {emotion_state}"
    await ctx.send(msg)

@bot.command()
async def 다음(ctx):
    await ctx.send("다음 라운드 시작")
    await 시작(ctx)

@bot.command()
async def 랭킹(ctx):
    if not scores:
        await ctx.send("아직 기록된 점수가 없어.")
        return

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    msg = "🏆 랭킹\n"
    rank = 1
    for user_id, score in sorted_scores[:10]:
        member = ctx.guild.get_member(user_id)
        name = member.display_name if member else f"알 수 없음({user_id})"
        msg += f"{rank}. {name} - {score}점\n"
        rank += 1

    await ctx.send(msg)

@bot.command()
async def 기억(ctx, member: discord.Member = None):
    target = member or ctx.author
    data = get_user_data(target)

    msg = (
        f"📘 {target.display_name} 기록\n"
        f"- 멘션 횟수: {data['mention_count']}\n"
        f"- 채팅 감지 횟수: {data['chat_count']}\n"
        f"- 게임 참가 횟수: {data['games_played']}\n"
        f"- 승리 횟수: {data['wins']}\n"
        f"- 호감도: {data['affection']}\n"
    )
    await ctx.send(msg)

@bot.command()
async def 감정(ctx):
    await ctx.send(f"지금 내 상태는… {emotion_state} 정도인 것 같아. 스트레스 수치는 {stress_level}야.")

@bot.command()
async def 호감도(ctx, member: discord.Member = None):
    target = member or ctx.author
    data = get_user_data(target)
    tier = get_affection_tier(data["affection"])

    tier_text = {
        "low": "낮음",
        "normal": "보통",
        "close": "높음",
        "special": "특별"
    }

    await ctx.send(f"{target.display_name}에 대한 현재 호감도는 {data['affection']}이야. 단계는 **{tier_text[tier]}** 정도로 보면 돼.")

@bot.command()
async def 게임추천(ctx):
    games = [
        "롤", "발로란트", "마인크래프트", "메이플스토리", "로스트아크",
        "배틀그라운드", "이터널리턴", "테라리아", "오버워치", "가볍게 수다"
    ]
    await ctx.send(f"오늘은… **{random.choice(games)}** 쪽이 괜찮을 것 같아.")

@bot.command()
async def 결정(ctx, *options):
    if len(options) < 2:
        await ctx.send("최소 두 개는 줘야 정할 수 있어.")
        return

    chosen = random.choice(options)
    await ctx.send(f"정리해보면… **{chosen}** 쪽으로 가는 게 좋겠어.")

@bot.command()
async def 초기화(ctx):
    global players, choices, stress_level

    players.clear()
    choices.clear()
    stress_level = 0
    update_emotion()
    await ctx.send("참가자와 진행 상태를 정리했어. 다시 시작할 수 있어.")

# =========================
# 실행
# =========================
bot.run(os.getenv("TOKEN"))
