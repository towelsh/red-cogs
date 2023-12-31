from redbot.core import commands, Config
from discord import Message
from redbot.core.commands import Context
from redbot.core.bot import Red
import logging
from openai._client import AsyncOpenAI
from openai._exceptions import OpenAIError, NotFoundError

class GPT(commands.Cog):
    def __init__(self, bot: Red):
        self.logger = logging.getLogger("GPT")
        self.bot: Red = bot
        self.client: AsyncOpenAI | None = None
        self.config = Config.get_conf(self, identifier=124987269) 
        self.config.register_guild(prompt="You are a helpful assistant.", model="gpt-3.5-turbo")

    async def _get_client(self) -> AsyncOpenAI:
        return AsyncOpenAI(api_key=(await self.bot.get_shared_api_tokens("openai")).get("api"))

    @commands.command()
    async def chat(self, ctx: Context, *args):
        query = " ".join(args[:])

        if self.client is None:
            try:
                self.client = await self._get_client()
            except OpenAIError:
                await ctx.reply("Failed to connect to OpenAI: API token `openai.api` must be set. If you own this bot, run `[prefix]set api`.")
                return

        prompt: str = "You are a helpful assistant."
        model = "gpt-3.5-turbo"
        if ctx.guild is not None:
            prompt = await self.config.guild(ctx.guild).prompt()
            model = await self.config.guild(ctx.guild).model()

        async with ctx.typing():
            self.logger.info(f"{ctx.author} asks '{query}' in guild {ctx.guild}")
            try:
                comp = await self.client.chat.completions.create(
                    model=model,
                    messages=[{
                        "role": "system",
                        "content": prompt
                    }, {
                        "role": "user",
                        "content": query
                    }]
                )
                await ctx.reply(comp.choices[0].message.content)
            except NotFoundError as e:
                self.logger.error(f"OpenAI API returned a NotFoundError. Check that completions model '{model}' is valid. Otherwise, create an issue on GitHub.")
                self.logger.exception(e)
                await ctx.reply(f"Unable to send to OpenAI. Please contact the owner of this bot.\n`help: check completions model '{model}' is valid (further details logged)`")

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author == self.bot.user:
            return

        # we assume that the bot is already logged in here, since it is recieving this message
        assert self.bot.user is not None
        if message.content.startswith(f"<@{self.bot.user.id}>"):
            await self.chat(await self.bot.get_context(message), message.content.lstrip(f"<@{self.bot.user.id}> "))
            return

        if message.reference is None:
            return

        if self.client is None:
            try:
                self.client = await self._get_client()
            except OpenAIError:
                await message.reply("Failed to connect to OpenAI: API token `openai.api` must be set. If you own this bot, run `[prefix]set api`.")
                return

        assert message.reference.message_id is not None
        replied_to = await message.channel.fetch_message(message.reference.message_id)
        if replied_to.author == self.bot.user:
            async with message.channel.typing():
                self.logger.info(f"{message.author} asks '{message.content}' in guild {message.guild} in reply to {message.reference}")

                prompt: str = "You are a helpful assistant."
                model = "gpt-3.5-turbo"
                if message.guild is not None:
                    prompt = await self.config.guild(message.guild).prompt()
                    model = await self.config.guild(message.guild).model()

                assert replied_to.reference is not None
                assert replied_to.reference.message_id is not None
                try:
                    comp = await self.client.chat.completions.create(
                        model=model,
                        messages=[{
                            "role": "system",
                            "content": prompt
                        }, {
                            "role": "user",
                            "content": (await message.channel.fetch_message(replied_to.reference.message_id)).content
                        }, {
                            "role": "assistant",
                            "content": replied_to.content
                        }, {
                            "role": "user",
                            "content": message.content
                        }]
                    )
                    await message.reply(comp.choices[0].message.content)
                except NotFoundError as e:
                    self.logger.error(f"OpenAI API returned a NotFoundError. Check that completions model '{model}' is valid. Otherwise, create an issue on GitHub.")
                    self.logger.exception(e)
                    await message.reply(f"Unable to send to OpenAI. Please contact the owner of this bot.\n`help: check completions model '{model}' is valid (further details logged)`")

    @commands.admin()
    @commands.command()
    async def setprompt(self, ctx: Context, *args):
        prompt = " ".join(args[:])

        if ctx.guild is None:
            await ctx.reply("You must run this command from within a server!")
            return

        await self.config.guild(ctx.guild).prompt.set(prompt)
        await ctx.reply(f"System prompt set to {prompt}.")

    @commands.admin()
    @commands.command()
    async def getprompt(self, ctx: Context):
        if ctx.guild is None:
            await ctx.reply("You must run this command from within a server!")
            return
        await ctx.reply(f"Current system prompt: {await self.config.guild(ctx.guild).prompt()}")

    @commands.admin()
    @commands.command()
    async def setmodel(self, ctx: Context, model: str):
        if ctx.guild is None:
            await ctx.reply("You must run this command from within a server!")
            return

        await self.config.guild(ctx.guild).model.set(model)
        await ctx.reply(f"Model was set to {model}")

    @commands.admin()
    @commands.command()
    async def getmodel(self, ctx: Context):
        if ctx.guild is None:
            await ctx.reply("You must run this command from within a server!")
            return
        await ctx.reply(f"Current model: {await self.config.guild(ctx.guild).model()}")

