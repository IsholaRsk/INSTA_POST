from bot.scheduler import Bot
from bot.config import BotConfig


def main():
    Bot(BotConfig.load()).run_forever()


if __name__ == "__main__":
    main()
