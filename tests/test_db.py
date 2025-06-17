import asyncio
from app.config.database import init_db, close_db

async def test_db():
    try:
        await init_db()
        print('✅ Database connection successful')
        await close_db()
    except Exception as e:
        print(f'❌ Database connection failed: {e}')
        print('Please check your DATABASE_URL in .env file')

asyncio.run(test_db())
