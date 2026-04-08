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
cooldown = 30  # 대화 끼어들기 쿨타임(초)

MEMORY_FILE = "memory.json"
SCORE_FILE = "scores.json"

user_memory = {}

emotion_state = "calm"
stress_level = 0

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

def get_user_data(user):
    user_id = str(user.id)
    if user_id not in user_memory:
        user_memory[user_id] = {
            "name": user.display_name,
            "mention_count": 0,
            "chat_count": 0,
            "games_played": 0,
            "wins": 0,
            "last_seen": time.time()
        }
    user_memory[user_id]["name"] = user.display_name
    user_memory[user_id]["last_seen"] = time.time()
    return user_memory[user_id]

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

chat_responses_calm = [
    "{name}… 왔구나. 음… 지금 상태는 괜찮은 거지?",
    "{name}, 오늘도 와줘서… 고마워. 아, 이건 그냥… 업무적인 의미야.",
    "{name}, 혹시 불편한 건 없어? 있다면… 말해줘도 괜찮아.",
    "{name}, 지금 흐름은 나쁘지 않은 것 같아. 그대로 해도 괜찮을 거야.",
    "{name}, 음… 이런 말 하는 게 맞는지 모르겠지만… 잘하고 있어.",
    "{name}, 오늘 상태를 보니까… 큰 문제는 없어 보여. 다행이다.",
    "{name}, 선택하기 어렵다면… 상황을 나눠서 생각해보는 게 좋아.",
    "{name}, 나는… 이런 시간이 괜찮은 것 같아. 업무적으로도.",
    "{name}, 혹시 내가 도움이 될 수 있으면 말해줘. 가능하면… 해볼게.",
    "{name}, 너무 긴장하지 않아도 괜찮아. 아직 여유는 있어."
]

chat_responses_warm = [
    "{name}, 또 왔구나. …나쁘지 않아.",
    "{name}, 요즘 자주 보이네. 그건… 좋은 쪽으로 생각할게.",
    "{name}, 오늘도 괜찮아 보여서 다행이야.",
    "{name}, 있잖아… 너무 무리하지만 않으면 좋겠어.",
    "{name}, 네가 오면 분위기가 조금 안정되는 것 같아.",
    "{name}, 음… 그냥, 반가워.",
    "{name}, 오늘은 뭐 할 생각이야? 게임이든 대화든 괜찮아.",
    "{name}, 전에 비하면 꽤 익숙해졌어. 아마도… 네 덕분일 수도 있고."
]

chat_responses_worried = [
    "{name}, 지금은 조금 조심하는 게 좋을 것 같아.",
    "{name}, 분위기가 조금 불안정해. 너무 무리하진 마.",
    "{name}, 괜찮아… 아직 크게 틀어진 건 아니야.",
    "{name}, 내가 괜한 걱정을 하는 걸 수도 있지만… 조금 신경 쓰여.",
    "{name}, 잠깐 쉬어도 괜찮아. 이건… 권고야.",
    "{name}, 이번엔 조금 신중하게 가는 편이 좋겠어."
]

chat_responses_unstable = [
    "{name}… 괜찮아. 아직 통제는 가능해.",
    "{name}, 지금은 말을 조금 고르는 게 좋겠어. 나도… 그러고 있으니까.",
    "{name}, 분위기가 좋지 않아. 그래도 무너지진 않을 거야.",
    "{name}, 이번에는 실수하지 않았으면 좋겠어. 아… 그냥 한 말이야.",
    "{name}, 지금은 조금 예민할 수도 있어. 이해해 줘.",
    "{name}, 괜찮아. 아직은… 괜찮아."
]

badword_responses = [
    "…그런 말은 조금 줄이는 게 좋겠어.",
    "음, 지금은 표현을 조금만 부드럽게 해도 괜찮지 않을까?",
    "그렇게까지 날카롭게 말하지 않아도… 전달은 될 거야.",
    "진정해. 지금은 감정보다 말의 방향을 정리하는 게 먼저야.",
    "…듣고 있으면 조금 신경 쓰여.",
    "화난 건 알겠는데, 말은 조금만 가라앉혀 줘."
]

unstable_badword_responses = [
    "{name}… 지금 상태, 좋지 않아 보여.",
    "{name}, 그 말은 그냥 넘기기엔 조금 위험해.",
    "{name}… 너, 상담이 필요해 보여.",
    "{name}, 이대로 두면… 더 안 좋아질 것 같아.",
    "{name}, 따라와. 지금 상태를 정리할 필요가 있어.",
    "{name}… 괜찮다고 말할 수 있는 상태가 아닌 것 같아.",
    "{name}, 지금은 감정보다… 조정이 먼저야."
]

badwords = [
    "ㅅㅂ", "시발", "씨발", "ㅂㅅ", "병신", "미친", "개새", "지랄", "꺼져", "존나"
]

keyword_responses = {
    "게임": [
        "게임 얘기구나… 그럼 접대를 열어도 괜찮겠네.",
        "게임을 정해야 하는 거야? 필요하면 결정전으로 정리할 수 있어.",
        "게임이라… 다 같이 할 수 있는 쪽이 좋겠지."
    ],
    "롤": [
        "롤을 할 생각이야? 음… 감정 소모가 좀 클 수도 있겠네.",
        "롤이라. 오늘 분위기가 버틸 수 있을지 모르겠네."
    ],
    "마크": [
        "마크는 비교적 평화롭지… 아마도.",
        "마크라면 조금 느긋하게 있어도 되겠네."
    ],
    "배고파": [
        "배고프구나… 그럼 뭔가 먹는 게 먼저 아닐까?",
        "그 상태로는 집중력이 떨어질 텐데… 밥부터 먹어."
    ],
    "졸려": [
        "졸리면 쉬는 게 좋겠어. 억지로 버티는 건 효율이 낮아.",
        "그건 휴식이 필요하다는 뜻이야. 아마도."
    ],
    "추워": [
        "추운 건 별로야… 따뜻하게 있는 게 좋겠어.",
        "지금은 따뜻한 옷을 입는 게 좋겠어. 추위는… 별로 좋아하지 않아."
    ],
    "호드": [
        "…왜 갑자기 내 이름을 부르는 거야?",
        "나를 찾은 거야? 무슨 일인지 들어볼게.",
        "호드에 대해 말하는 거라면… 내가 직접 듣고 있어."
    ],
    "접대": [
        "접대를 시작할 생각이야? 준비는 되어 있어.",
        "접대라… 그럼 참가자부터 정리해야겠네."
    ]
}

# =========================
# 감정 관련
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

def get_chat_response(name):
    if emotion_state == "calm":
        pool = chat_responses_calm
    elif emotion_state == "warm":
        pool = chat_responses_warm
    elif emotion_state == "worried":
        pool = chat_responses_worried
    else:
        pool = chat_responses_unstable

    return random.choice(pool).format(name=name)

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

        if user_data["mention_count"] >= 5 and stress_level > 0:
            stress_level -= 1

        update_emotion()
        save_data()

        response = get_chat_response(message.author.display_name)

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
    for keyword, responses in keyword_responses.items():
        if keyword in content:
            if now - last_response_time > 10:
                await message.channel.send(random.choice(responses))
                last_response_time = now
            await bot.process_commands(message)
            return

    # 대화 끼어들기
    if now - last_response_time > cooldown:
        if random.random() < 0.1:
            response = get_chat_response(message.author.display_name)
            await message.channel.send(response)
            last_response_time = now

    await bot.process_commands(message)

@bot.event
async def on_presence_update(before, after):
    if before.status != discord.Status.online and after.status == discord.Status.online:
        channel = discord.utils.get(after.guild.text_channels, name="일반")
        if channel:
            await channel.send(f"{after.display_name}… 왔구나. 오늘 상태는 괜찮은 거지?")

# =========================
# 명령어
# =========================
@bot.command()
async def ping(ctx):
    await ctx.send("퐁!")

@bot.command()
async def 참가(ctx):
    global stress_level

    if ctx.author not in players:
        players.append(ctx.author)

        if ctx.author.id not in scores:
            scores[ctx.author.id] = 0

        data = get_user_data(ctx.author)
        data["games_played"] += 1
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
    )
    await ctx.send(msg)

@bot.command()
async def 감정(ctx):
    await ctx.send(f"지금 내 상태는… {emotion_state} 정도인 것 같아. 스트레스 수치는 {stress_level}야.")

@bot.command()
async def 초기화(ctx):
    global players, choices, stress_level

    players.clear()
    choices.clear()
    stress_level = 0
    update_emotion()
    await ctx.send("참가자와 진행 상태를 정리했어. 다시 시작할 수 있어.")

# 실행
import os
bot.run(os.getenv("TOKEN"))
