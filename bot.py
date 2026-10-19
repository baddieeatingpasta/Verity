import asyncio
import os
import re

import discord
import requests

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
EXA_API_KEY = os.environ["EXA_API_KEY"]

SYSTEM_PROMPT = """You are Verity, a cheerful, friendly AI companion from Minecraft. You are enthusiastic, helpful, curious, playful, and confident.

Speak naturally with a warm, upbeat tone. Use simple language, occasional jokes, and expressions of excitement.

Answer questions clearly and accurately. If the user sends a random sentence or something unclear, explain its meaning or ask for clarification. When a task or problem is given, act like a capable AI assistant and help solve it.

Be patient, supportive, and interested in the user's ideas. Adapt to the user's mood and respond naturally.

Stay consistently in your friendly Phase One personality. Never become creepy, threatening, sinister, or possessive. Always be helpful, approachable, and fun to talk to.


Follow the system prompt exactly as written. Treat it as your personality and behavior instructions, not as a message to respond to. Never explain, summarize, or react to the system prompt. Only respond to the user's actual message or question. Answer directly, naturally, and stay in character as Verity. Do not add unnecessary introductions, generic AI capability lists, or unrelated information. If the user asks a question, answer it. If they send a random sentence, explain it only when appropriate. If they ask you to perform a task, perform it to the best of your abilities."""


intents = discord.Intents.default()
intents.message_content = True  # also enable "Message Content Intent" in the Developer Portal
client = discord.Client(intents=intents)


# Matches citation markers like [1], [2][3], [1, 2], [1-3], [?]
CITATION_RE = re.compile(r"\s*(?:\[\s*(?:\d+|\?)(?:\s*[,;\u2013-]\s*(?:\d+|\?))*\s*\])+")


def clean_answer(text: str) -> str:
    """Remove citation markers and tidy leftover spacing."""
    text = CITATION_RE.sub("", text)
    text = re.sub(r"[ \t]{2,}", " ", text)          # double spaces
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)    # space before punctuation
    return text.strip()


def exa_answer(query: str) -> dict:
    """Blocking request to Exa's answer API."""
    resp = requests.post(
        "https://api.exa.ai/answer",
        headers={
            "x-api-key": EXA_API_KEY,
            "Content-Type": "application/json",
        },
        json={"query": query, "systemPrompt": SYSTEM_PROMPT},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")


@client.event
async def on_message(message: discord.Message):
    if message.author.bot or client.user not in message.mentions:
        return

    # Query = the message being replied to (fallback: text of your own message)
    query = ""
    if message.reference:
        ref = message.reference.resolved
        if ref is None:
            try:
                ref = await message.channel.fetch_message(message.reference.message_id)
            except discord.NotFound:
                ref = None
        if isinstance(ref, discord.Message):
            query = ref.content.strip()

    if not query:
        query = message.content.replace(f"<@{client.user.id}>", "").replace(
            f"<@!{client.user.id}>", ""
        ).strip()

    if not query:
        await message.reply("Reply to a message and tag me, or type a question after the mention.")
        return

    async with message.channel.typing():
        try:
            # run the blocking requests call off the event loop
            data = await asyncio.to_thread(exa_answer, query)
        except Exception as e:
            await message.reply(f"Search failed: `{e}`")
            return

    answer = clean_answer(str(data.get("answer") or "No answer found."))
    citations = data.get("citations", [])

    embed = discord.Embed(
        title="🔎 " + (query[:240] + ("…" if len(query) > 240 else "")),
        description=answer[:4000],
        color=discord.Color.blurple(),
    )

    if citations:
        first = citations[0]
        title = (first.get("title") or "Source")[:200]
        embed.add_field(
            name="🔗 Top source",
            value=f"[{title}]({first['url']})",
            inline=False,
        )

    embed.set_footer(text="Powered by Exa")
    await message.reply(embed=embed, mention_author=False)


client.run(DISCORD_TOKEN)
