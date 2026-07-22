from typing import TypedDict


from app.models.entity.column_info import ColumnInfo
from app.models.entity.metric_info import MetricInfo
from app.models.entity.value_info import ValueInfo

class MetricInfoState(TypedDict):
    name: str  # 指标名称
    description: str  # 指标描述
    relevant_columns: list[str]  # 指标相关的字段
    alias: list[str]  # 指标别名
class TableInfoState(TypedDict):
    name: str  # 表名
    role: str  # 表角色
    discription: str  # 表描述
    columns: list  # 表字段信息
class ColumnInfoState(TypedDict):
    name: str  # 字段名
    type: str  # 字段类型
    role: str  # 字段角色
    description: str  # 字段描述
    examples: list  # 字段示例值
    alias: list[str]  # 字段别名
class DateInfoState(TypedDict):
    date: str
    weekday: str
    quarter: str
class DbInfoState(TypedDict):
    version: str
    dialect: str

class DataAgentState(TypedDict):
    error: str  # 校验sql语句时出现的错误信息
    query: str  # 用户输入
    keywords: list[str]  # 用户输入的关键字
    retrieved_column_infos: list[ColumnInfo]  # 从Qdrant中召回的字段信息
    retrieved_metric_infos: list[MetricInfo] # 从Qdrant中召回的指标信息
    retrieved_value_infos: list[ValueInfo] # 从Qdrant中召回的值信息
    table_infos: list[TableInfoState]
    metric_infos: list[MetricInfoState]
    date_info: DateInfoState
    db_info: DbInfoState
    sql: str  # 生成的sql语句