import asyncio
from bot.database.session import engine

async def check():
    try:
        async with engine.connect() as conn:
            pass
        print("OK")
        exit(0)
    except Exception as e:
        print(f"Error: {e}")
        exit(1)

if __name__ == "__main__":
    asyncio.run(check())
