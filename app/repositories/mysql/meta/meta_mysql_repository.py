from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.log import logger
from app.models.column_info_mysql import ColumnInfoMySQL
from app.models.entity.column_info import ColumnInfo
from app.models.entity.column_metric import ColumnMetric
from app.models.entity.metric_info import MetricInfo
from app.models.entity.table_info import TableInfo
from app.models.table_info_mysql import TableInfoMySQL
from app.repositories.mysql.meta.mappers.column_info_mapper import ColumnInfoMapper
from app.repositories.mysql.meta.mappers.column_metric_mapper import ColumnMetricMapper
from app.repositories.mysql.meta.mappers.metric_info_mapper import MetricInfoMapper
from app.repositories.mysql.meta.mappers.table_info_mapper import TableInfoMapper


class MetaMysqlRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def clear_all(self):
        """清空 table_info 和 column_info 表"""
        await self.session.execute(text("DELETE FROM column_info"))
        await self.session.execute(text("DELETE FROM table_info"))
        logger.info("[MySQL] 旧数据已清空")

    # 因为session的autoflush=False,没有进行网络层的IO操作,所以这里不需要await
    def save_column_infos(self, column_infos):
        self.session.add_all([ColumnInfoMapper.to_model(column_info) for column_info in column_infos])

    def save_table_infos(self, table_infos):
        self.session.add_all([TableInfoMapper.to_model(table_info) for table_info in table_infos])

    async def sav_metric_infos(self, metric_infos: list[MetricInfo]):
        self.session.add_all([MetricInfoMapper.to_model(metric_info) for metric_info in metric_infos])

    async def save_column_metrics(self, column_metrics: list[ColumnMetric]):
        self.session.add_all([ColumnMetricMapper.to_model(column_metric) for column_metric in column_metrics])

    async def get_column_info_by_id(self, id: str) -> ColumnInfo | None:
        column_info: ColumnInfoMySQL | None = await self.session.get(ColumnInfoMySQL(), id)
        if column_info:
            return ColumnInfoMapper.to_entity(column_info)
        else: return None

    async def get_table_info_by_id(self, id) -> TableInfo | None:
        table_info: TableInfoMySQL | None = await self.session.get(TableInfoMySQL, id)
        if table_info:
            return TableInfoMapper.to_entity(table_info)
        else:
            return None

    async def get_key_columns_by_table_id(self, table_id):
        sql = "select * from column_info where table_id = :table_id and role in ('primary_key','foreign_key')"
        result = await self.session.execute(text(sql),{'table_id': table_id})
        [ColumnInfo(**row) for row in result.mappings().fetchall()]