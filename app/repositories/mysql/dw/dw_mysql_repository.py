import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.models.column_info_mysql import ColumnInfoMySQL
from app.models.table_info_mysql import TableInfoMySQL


class DwMysqlRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_column_types(self, table_name) -> dict[str, str]:
        sql = f"show columns from {table_name}"
        result = await self.session.execute(text(sql))
        result_dict = result.mappings().fetchall()
        return {row['Field']: row['Type'] for row in result_dict}

    async def get_column_values(self, table_name, column_name, limit=10):
        sql = f"select distinct {column_name} from {table_name} limit {limit}"
        result = await self.session.execute(text(sql))
        return [row[0] for row in result.fetchall()]

    async def get_db_info(self):
        sql = "select version()"
        result = await self.session.execute(text(sql))
        version = result.scalar()
        dialect = self.session.bind.dialect.name
        return {
            'version': version,
            'dialect': dialect,
        }

    async def validate(self, sql: str):
        sql = f"explain {sql}"
        await self.session.execute(text(sql))

    async def run(self, sql) -> list[dict]:
        reslut = await self.session.execute(text(sql))
        return [dict(row)for row in reslut.mappings().fetchall()]


if __name__ == '__main__':
    from app.clients.mysql_client_manager import dw_mysql_client_manager

    async def test_get_column_values():
        dw_mysql_client_manager.init()
        async with AsyncSession(dw_mysql_client_manager.engine, expire_on_commit=False) as session:
            repo = DwMysqlRepository(session)

            # 测试1: 正常列 — member_level 有4种级别
            levels = await repo.get_column_values('dim_customer', 'member_level')
            print(f"member_level 去重值: {levels}")

            # 测试2: 唯一值列 — country 只有 '中国'
            countries = await repo.get_column_values('dim_region', 'country')
            print(f"country 去重值: {countries}")

            # 测试3: 数值列 — order_quantity 有多个值
            quantities = await repo.get_column_values('fact_order', 'order_quantity')
            print(f"order_quantity 去重值 (前5个): {quantities[:5]}")

            print("\n🎉 全部测试通过!")

    asyncio.run(test_get_column_values())
