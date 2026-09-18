"""
数据库模型层 - SQLite + SQLAlchemy 异步ORM

本模块职责：
1. 定义所有数据库表的 ORM 模型（SQLAlchemy Declarative Mapping）
2. 配置异步数据库引擎和会话工厂
3. 提供数据库初始化函数和会话获取工具函数

使用的数据库：SQLite（通过 aiosqlite 实现异步访问）
ORM 框架：SQLAlchemy 2.0 异步模式（Mapped + mapped_column）
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Float, Boolean, DateTime, Text, JSON, Integer
from datetime import datetime
import os

# 数据库连接 URL，优先从环境变量读取，默认使用项目根目录下的 data/monitor.db
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/monitor.db")

# 创建异步数据库引擎（echo=False 表示不输出 SQL 日志）
engine = create_async_engine(DATABASE_URL, echo=False)
# 创建异步会话工厂，expire_on_commit=False 表示提交后不过期已加载的属性，避免异步上下文中的惰性加载问题
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """
    SQLAlchemy 声明式基类

    所有 ORM 模型类必须继承此基类，Base.metadata 收集所有子类定义，
    用于在 init_db() 中统一创建/同步数据表结构。
    """
    pass


class FaceRecordModel(Base):
    """
    人脸识别记录表 —— 存储每次人脸检测/识别的结果

    业务说明：
    - 每当摄像头画面中检测到人脸并完成识别后，生成一条记录
    - 记录包含识别结果（人员姓名、置信度）、截图路径、检测时间等
    - is_unknown 标记该人脸是否为未知人员（未在人脸库中注册）
    - attributes 存储扩展属性（如年龄、性别等未来可能增加的检测维度）
    """
    __tablename__ = "face_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)           # 主键，自增ID
    camera_id: Mapped[str] = mapped_column(String(50))                               # 来源摄像头ID，关联 camera_info.id
    person_name: Mapped[str] = mapped_column(String(100), default="未知")            # 识别出的人员姓名，默认"未知"
    confidence: Mapped[float] = mapped_column(Float)                                 # 识别置信度（0~100），越高越可信
    face_image_path: Mapped[str] = mapped_column(String(500), nullable=True)         # 人脸裁剪图片的存储路径，可为空
    snapshot_path: Mapped[str] = mapped_column(String(500), nullable=True)           # 完整监控截图的存储路径，可为空
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)    # 检测发生的时间戳，默认当前时间
    is_unknown: Mapped[bool] = mapped_column(Boolean, default=False)                 # 是否为未知人员：True=陌生人, False=已注册人员
    attributes: Mapped[dict] = mapped_column(JSON, nullable=True)                    # 扩展属性（JSON格式），如年龄、性别等


class PersonInfoModel(Base):
    """
    人员信息表 —— 存储已注册人员的基本信息

    业务说明：
    - 每个注册到人脸库的人员在此表中有一条记录
    - name 字段唯一，作为人员标识
    - face_encoding_path 指向人脸特征向量文件的存储目录
    - face_image_path 指向该人员的代表照片（用于前端展示）
    - category 区分人员类型：staff（员工）、visitor（访客）、blacklist（黑名单）
    """
    __tablename__ = "person_info"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)            # 主键，自增ID
    name: Mapped[str] = mapped_column(String(100), unique=True)                      # 人员姓名，全局唯一
    face_encoding_path: Mapped[str] = mapped_column(String(500))                     # 人脸特征编码文件路径（face_db 目录下）
    face_image_path: Mapped[str] = mapped_column(String(500))                        # 人脸照片路径（用于前端头像展示）
    category: Mapped[str] = mapped_column(String(20), default="staff")               # 人员类别：staff/visitor/blacklist
    phone: Mapped[str] = mapped_column(String(20), nullable=True)                    # 联系电话，可选
    department: Mapped[str] = mapped_column(String(100), nullable=True)              # 所属部门，可选
    remarks: Mapped[str] = mapped_column(Text, nullable=True)                        # 备注信息，可选
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)     # 注册时间，默认当前时间


class AlertRuleModel(Base):
    """
    告警规则表 —— 定义监控系统的自动告警触发条件

    业务说明：
    - 管理员可配置多条告警规则，如"黑名单人员出现"、"未知人员在特定时间段出现"等
    - condition_type 定义规则类型，condition_value 以 JSON 存储具体条件参数
    - enabled 控制规则是否生效，notify_method 指定告警通知方式
    """
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)            # 主键，自增ID
    name: Mapped[str] = mapped_column(String(100))                                   # 规则名称（如"黑名单告警"）
    condition_type: Mapped[str] = mapped_column(String(50))                          # 条件类型：blacklist_appear / unknown_appear / time_range
    condition_value: Mapped[dict] = mapped_column(JSON)                              # 条件参数（JSON格式），具体内容取决于 condition_type
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)                     # 是否启用：True=生效, False=停用
    notify_method: Mapped[str] = mapped_column(String(50), default="websocket")      # 通知方式：websocket / email / sms


class CameraInfoModel(Base):
    """
    摄像头配置表 —— 存储系统中注册的摄像头信息

    业务说明：
    - 每个摄像头有全局唯一的 id（通常为自定义字符串标识）
    - source 为视频源地址：可以是本地摄像头编号（如 "0"）或 RTSP 流地址
    - status 标记摄像头在线状态：online / offline
    - fps 控制帧率，rotation 控制画面旋转角度
    """
    __tablename__ = "camera_info"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)                    # 摄像头唯一标识（字符串主键，如 "phone1"）
    name: Mapped[str] = mapped_column(String(100))                                   # 摄像头名称（如"大门摄像头"）
    source: Mapped[str] = mapped_column(String(500))                                 # 视频源地址：0=本地摄像头，rtsp://xxx=网络摄像头
    location: Mapped[str] = mapped_column(String(200), default="")                   # 安装位置描述（如"一楼大厅"），默认空
    status: Mapped[str] = mapped_column(String(20), default="offline")               # 运行状态：online=在线, offline=离线
    fps: Mapped[int] = mapped_column(Integer, default=15)                            # 视频帧率（每秒帧数），默认15
    rotation: Mapped[int] = mapped_column(Integer, default=0)                        # 画面旋转角度（0/90/180/270），用于校正倒置画面


async def init_db():
    """
    初始化数据库

    执行流程：
    1. 确保 data/ 目录存在（SQLite 数据库文件存放位置）
    2. 通过 Base.metadata.create_all 创建所有 ORM 模型对应的数据表
       - 如果表已存在则跳过，不会重复创建
       - 使用 run_sync 在同步连接中执行 DDL 操作
    """
    os.makedirs("data", exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """
    获取数据库会话（异步生成器）

    用于 FastAPI 的 Depends() 注入，提供数据库会话的依赖项。
    会话在使用完毕后自动关闭（通过 async with 上下文管理）。

    Yields:
        AsyncSession: 异步数据库会话实例
    """
    async with async_session() as session:
        yield session
"""
数据库操作 - SQLite + SQLAlchemy
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Float, Boolean, DateTime, Text, JSON, Integer
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/monitor.db")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class FaceRecordModel(Base):
    """人脸识别记录表"""
    __tablename__ = "face_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(String(50))
    person_name: Mapped[str] = mapped_column(String(100), default="未知")
    confidence: Mapped[float] = mapped_column(Float)
    face_image_path: Mapped[str] = mapped_column(String(500), nullable=True)
    snapshot_path: Mapped[str] = mapped_column(String(500), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    is_unknown: Mapped[bool] = mapped_column(Boolean, default=False)
    attributes: Mapped[dict] = mapped_column(JSON, nullable=True)


class PersonInfoModel(Base):
    """人员信息表"""
    __tablename__ = "person_info"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    face_encoding_path: Mapped[str] = mapped_column(String(500))
    face_image_path: Mapped[str] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(String(20), default="staff")
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    department: Mapped[str] = mapped_column(String(100), nullable=True)
    remarks: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AlertRuleModel(Base):
    """告警规则表"""
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    condition_type: Mapped[str] = mapped_column(String(50))
    condition_value: Mapped[dict] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_method: Mapped[str] = mapped_column(String(50), default="websocket")


class CameraInfoModel(Base):
    """摄像头配置表"""
    __tablename__ = "camera_info"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    source: Mapped[str] = mapped_column(String(500))
    location: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(20), default="offline")
    fps: Mapped[int] = mapped_column(Integer, default=15)
    rotation: Mapped[int] = mapped_column(Integer, default=0)  # 画面旋转角度 0/90/180/270


async def init_db():
    """初始化数据库"""
    os.makedirs("data", exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """获取数据库会话"""
    async with async_session() as session:
        yield session
