import asyncio
from sqlalchemy import text
from app.conf.app_config import DbConfig, appconfig
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

class MySQLClientManager:
    def __init__(self, config: DbConfig):
        # engine 会维护一个数据库连接池
        self.engine: AsyncEngine | None = None
        self.session_factory = None
        self.config = config

    def _get_url(self):
        return f"mysql+asyncmy://{self.config.user}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}"
    
    def init(self):
        self.engine = create_async_engine(self._get_url(),pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False, autoflush=False)

    async def close(self):
        await self.engine.dispose()

meta_mysql_client_manager = MySQLClientManager(appconfig.db_meta)
dw_mysql_client_manager = MySQLClientManager(appconfig.db_dw)
if __name__ == '__main__':
    dw_mysql_client_manager.init()
    engine = dw_mysql_client_manager.engine
    async def test():
        # expire_on_commit=False--> 异步Engine不支持expire_on_commit(因为访问过期对象时底层会自动调用查询方法，而你又不能在一个对象的属性前写await)
        async with AsyncSession(engine, expire_on_commit=False, auto_flush=False) as session:
            sql = "select * from fact_order"
            result = await session.execute(text(sql))
            print(result.mappings().fetchall())
    asyncio.run(test())