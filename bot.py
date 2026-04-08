import discord
from discord.ext import commands
import random
import asyncio
import time
import os

# intents
intents = discord.Intents.default()
intents.message_content = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)

players = []
choices = {}
scores = {}

# ⏱️ 대화 끼어들기 쿨타임
last_response_time = 0
cooldown = 30  # 30초

# 🎭 게임 중 대사
horde_lines = [
    "…모두 집중해. 이번 상황은 조금 다를 수도 있어.",
    "괜찮아, 아직 돌이킬 수 있어.",
    "…내 판단이 틀리지 않았으면 좋겠어.",
    "지금은 침착하게 대응해야 해.",
    "조금만 더 버티면 돼… 아마도."
]

# 💬 호드 일상 대사
chat_responses = [
    "{name}… 왔구나. 음… 지금 상태는 괜찮은 거지?",
    "{name}, 오늘도 와줘서… 고마워. 아, 이건 그냥… 업무적인 의미야.",
    "{name}, 혹시 불편한 건 없어? 있다면… 말해줘도 괜찮아.",
    "{name}, 너무 무리하고 있는 건 아니지? 나는… 그게 조금 걱정돼.",
    "{name}, 지금 흐름은 나쁘지 않은 것 같아. 그대로 해도 괜찮을 거야.",
    "{name}, 음… 이런 말 하는 게 맞는지 모르겠지만… 잘하고 있어.",
    "{name}, 혹시 힘들면 잠깐 쉬어도 괜찮아. 이건… 허가니까.",
    "{name}, 오늘 상태를 보니까… 큰 문제는 없어 보여. 다행이다.",
    "{name}, 내가 너무 간섭하는 건 아니지…? 그래도 필요한 말은 해야 하니까.",
    "{name}, 선택하기 어렵다면… 상황을 나눠서 생각해보는 게 좋아.",
    "{name}, 음… 조금 추운 느낌인데… 괜찮아? 아니면 내가 괜한 걱정을…",
    "{name}, 손 차갑지 않아? …아, 이런 건 굳이 말 안 해도 되려나.",
    "{name}, 너희가 이렇게 모여 있는 건… 나쁘지 않은 것 같아.",
    "{name}, 나는… 이런 시간이 괜찮다고 생각해. 업무적으로도.",
    "{name}, 혹시 내가 도움이 될 수 있으면 말해줘. 가능하면… 해볼게.",
    "{name}, 지금 선택도 틀린 건 아니야. 너무 걱정하지 않아도 돼.",
    "{name}, 음… 내가 이런 말을 해도 될지 모르겠지만… 믿고 있어.",
    "{name}, 너무 긴장하지 않아도 괜찮아. 아직 여유는 있어.",
    "{name}, …괜히 분위기를 망친 건 아니지? 그런 의도는 아니었어.",
    "{name}, 오늘은… 비교적 안정적인 상태야. 계속 이렇게 유지해보자."
]

# 🎮 승패 계산
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

# ping
@bot.command()
async def ping(ctx):
    await ctx.send("퐁!")

# 참가
@bot.command()
async def 참가(ctx):
    if ctx.author not in players:
        players.append(ctx.author)
        scores[ctx.author] = 0
        await ctx.send(f"{ctx.author.display_name} 참가 완료!")
    else:
        await ctx.send("이미 참가했어.")

# 시작
@bot.command()
async def 시작(ctx):
    if len(players) < 3:
        await ctx.send("최소 3명이 필요해.")
        return

    await ctx.send("📢 접대 시작… DM을 확인해.")

    for p in players:
        try:
            await p.send("⚔️ 공격 / 🛡️ 방어 / 💨 회피 중 하나 입력해!")
        except:
            await ctx.send(f"{p.display_name} DM 못 받음!")

    choices.clear()

    await asyncio.sleep(3)
    await ctx.send(f"🎭 {random.choice(horde_lines)}")

    def check(m):
        return m.author in players and isinstance(m.channel, discord.DMChannel)

    try:
        while len(choices) < len(players):
            msg = await bot.wait_for("message", timeout=30, check=check)
            choices[msg.author] = msg.content.strip()
    except asyncio.TimeoutError:
        pass

    if len(choices) == 0:
        await ctx.send("아무도 선택하지 않았어...")
        return

    winners, result = decide_winner()

    msg = "📊 결과\n"
    for p, c in choices.items():
        msg += f"{p.display_name}: {c}\n"

    msg += "\n🏆 승자\n"
    for w in winners:
        msg += f"- {w.display_name}\n"
        scores[w] += 1

    msg += "\n📈 점수\n"
    for p, s in scores.items():
        msg += f"{p.display_name}: {s}\n"

    await ctx.send(msg)

# 다음 라운드
@bot.command()
async def 다음(ctx):
    await ctx.send("다음 라운드 시작")
    await 시작(ctx)

# 💬 메시지 반응 + 끼어들기
@bot.event
async def on_message(message):
    global last_response_time

    if message.author == bot.user:
        return

    now = time.time()

    # 멘션 반응
    if bot.user in message.mentions:
        name = message.author.display_name
        response = random.choice(chat_responses).format(name=name)
        await message.channel.send(response)

    # 대화 끼어들기
    elif now - last_response_time > cooldown:
        if random.random() < 0.1:  # 10% 확률
            name = message.author.display_name
            response = random.choice(chat_responses).format(name=name)
            await message.channel.send(response)
            last_response_time = now

    await bot.process_commands(message)

# 🟢 접속 인사
@bot.event
async def on_presence_update(before, after):
    if before.status != discord.Status.online and after.status == discord.Status.online:
        channel = discord.utils.get(after.guild.text_channels, name="일반")
        if channel:
            await channel.send(f"{after.display_name}… 왔구나. 오늘 상태는 괜찮은 거지?")

# 실행
import os
bot.run(os.getenv("TOKEN"))
