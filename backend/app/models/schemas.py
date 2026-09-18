"""
Pydantic 数据模型层 —— 请求/响应/业务数据验证与序列化

本模块职责：
1. 定义 API 接口的请求体和响应体模型（基于 Pydantic BaseModel）
2. 定义业务实体的数据结构（FaceRecord、PersonInfo、CameraInfo 等）
3. 定义枚举类型（IntentType 用户意图分类）
4. 提供字段级别的数据验证和默认值设置

与 models/database.py 的关系：
- database.py 定义 ORM 模型（数据库表结构）
- schemas.py 定义 Pydantic 模型（API 数据交换格式）
- 两者通过 database_agent 进行数据转换
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class IntentType(str, Enum):
    """
    用户意图类型枚举

    由 Orchestrator（编排器）根据用户消息内容识别出对应的意图类型，
    再分发到具体的 Agent（视觉/数据库）进行处理。

    枚举值说明：
    - REALTIME_CHECK: 实时查看 —— 用户想查看当前摄像头画面或实时状态
    - HISTORY_QUERY: 历史查询 —— 用户查询过去的识别记录
    - STATISTICS: 统计分析 —— 用户请求数据统计（如今日识别次数、人员分布等）
    - PERSON_MANAGE: 人员管理 —— 用户想增删改人员信息
    - ALERT_SETTING: 告警设置 —— 用户配置告警规则
    - CAMERA_MANAGE: 摄像头管理 —— 用户管理摄像头（添加/删除/配置）
    - GENERAL_CHAT: 一般对话 —— 不属于以上任何类别的普通对话
    """
    REALTIME_CHECK = "realtime_check"       # 实时查看
    HISTORY_QUERY = "history_query"          # 历史查询
    STATISTICS = "statistics"                # 统计分析
    PERSON_MANAGE = "person_manage"          # 人员管理
    ALERT_SETTING = "alert_setting"          # 告警设置
    CAMERA_MANAGE = "camera_manage"          # 摄像头管理
    GENERAL_CHAT = "general_chat"            # 一般对话


class ChatRequest(BaseModel):
    """
    对话请求模型

    用于 HTTP 对话接口（/api/chat/send 和 /api/chat/stream），
    封装用户发送的消息内容及会话上下文信息。

    Attributes:
        message: 用户输入的文本消息内容（必填）
        session_id: 会话标识，用于区分不同的对话上下文，默认 "default"
        camera_id: 可选，指定操作的目标摄像头（如用户说"查看大门摄像头"时提取）
    """
    message: str = Field(..., description="用户消息")
    session_id: str = Field(default="default", description="会话ID")
    camera_id: Optional[str] = Field(default=None, description="指定摄像头")


class ChatResponse(BaseModel):
    """
    对话响应模型

    用于 HTTP 非流式对话接口（/api/chat/send）的返回值，
    封装 AI 助手的回复内容及元信息。

    Attributes:
        session_id: 会话标识，与请求中的 session_id 对应
        message: AI 助手的完整回复文本
        intent: 本次对话识别出的用户意图类型
        data: 可选的附加数据（如查询结果、统计信息等结构化数据）
        timestamp: 响应生成的时间戳
    """
    session_id: str                          # 会话ID
    message: str                             # AI 回复文本
    intent: IntentType                       # 用户意图类型枚举
    data: Optional[dict] = None              # 附加结构化数据（查询结果等）
    timestamp: datetime = Field(default_factory=datetime.now)  # 响应时间戳


class FaceRecord(BaseModel):
    """
    人脸识别记录 Pydantic 模型

    对应数据库 face_records 表，用于 API 层的数据传输和验证。

    Attributes:
        id: 记录ID（新建时可为 None，由数据库自增生成）
        camera_id: 来源摄像头ID
        person_name: 识别出的人员姓名，默认"未知"
        confidence: 识别置信度（0~100 的浮点数）
        face_image_path: 人脸裁剪图片路径，可选
        snapshot_path: 完整截图路径，可选
        detected_at: 检测时间戳，默认当前时间
        is_unknown: 是否为未知人员
        attributes: 扩展属性字典（如年龄、性别等）
    """
    id: Optional[int] = None                 # 记录ID，新建时为 None
    camera_id: str                           # 来源摄像头ID
    person_name: str = "未知"                # 识别人员姓名
    confidence: float                        # 识别置信度
    face_image_path: Optional[str] = None    # 人脸图片路径
    snapshot_path: Optional[str] = None      # 截图路径
    detected_at: datetime = Field(default_factory=datetime.now)  # 检测时间
    is_unknown: bool = False                 # 是否未知人员
    attributes: Optional[dict] = None        # 扩展属性


class PersonInfo(BaseModel):
    """
    人员信息 Pydantic 模型

    对应数据库 person_info 表，用于人员注册、查询等 API 的数据传输。

    Attributes:
        id: 人员ID（新建时可为 None）
        name: 人员姓名（必填，全局唯一）
        face_encoding_path: 人脸特征向量文件的存储目录路径
        face_image_path: 人员代表照片的文件路径（用于前端头像展示）
        category: 人员类别 —— staff（员工）、visitor（访客）、blacklist（黑名单）
        phone: 联系电话，可选
        department: 所属部门，可选
        remarks: 备注信息，可选
        created_at: 注册时间，默认当前时间
    """
    id: Optional[int] = None                 # 人员ID
    name: str                                # 人员姓名（唯一）
    face_encoding_path: str                  # 人脸特征文件路径
    face_image_path: str                     # 人脸照片路径
    category: str = "staff"                  # 人员类别: staff / visitor / blacklist
    phone: Optional[str] = None              # 联系电话
    department: Optional[str] = None         # 所属部门
    remarks: Optional[str] = None            # 备注
    created_at: datetime = Field(default_factory=datetime.now)  # 注册时间


class CameraInfo(BaseModel):
    """
    摄像头信息 Pydantic 模型

    对应数据库 camera_info 表，用于摄像头增删改查 API 的数据传输。

    Attributes:
        id: 摄像头唯一标识（字符串，如 "phone1"、"cam_001"）
        name: 摄像头名称（如"大门摄像头"）
        source: 视频源地址 —— "0" 表示本地摄像头，"rtsp://xxx" 表示网络摄像头
        location: 安装位置描述（如"一楼大厅"）
        status: 运行状态 —— "online"（在线） / "offline"（离线）
        fps: 视频帧率，默认 5
        rotation: 画面旋转角度（0/90/180/270），用于校正倒置画面
    """
    id: str                                  # 摄像头唯一标识
    name: str                                # 摄像头名称
    source: str                              # 视频源地址: 0=本地摄像头, rtsp://xxx=网络摄像头
    location: str = ""                       # 安装位置描述
    status: str = "offline"                  # 运行状态: online / offline
    fps: int = 5                             # 视频帧率
    rotation: int = 0                        # 画面旋转角度 0/90/180/270


class AlertRule(BaseModel):
    """
    告警规则 Pydantic 模型

    对应数据库 alert_rules 表，用于告警规则的创建和配置。

    Attributes:
        id: 规则ID（新建时可为 None）
        name: 规则名称（如"黑名单人员出现告警"）
        condition_type: 触发条件类型 —— blacklist_appear（黑名单出现）/ unknown_appear（陌生人出现）/ time_range（时间段）
        condition_value: 触发条件的具体参数（JSON 字典），内容取决于 condition_type
        enabled: 是否启用该规则，默认 True
        notify_method: 告警通知方式 —— websocket / email / sms，默认 websocket
    """
    id: Optional[int] = None                 # 规则ID
    name: str                                # 规则名称
    condition_type: str                      # 条件类型: blacklist_appear / unknown_appear / time_range
    condition_value: dict                    # 条件参数（JSON格式）
    enabled: bool = True                     # 是否启用
    notify_method: str = "websocket"         # 通知方式: websocket / email / sms
"""
数据模型定义
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class IntentType(str, Enum):
    """用户意图类型"""
    REALTIME_CHECK = "realtime_check"       # 实时查看
    HISTORY_QUERY = "history_query"          # 历史查询
    STATISTICS = "statistics"                # 统计分析
    PERSON_MANAGE = "person_manage"          # 人员管理
    ALERT_SETTING = "alert_setting"          # 告警设置
    CAMERA_MANAGE = "camera_manage"          # 摄像头管理
    GENERAL_CHAT = "general_chat"            # 一般对话


class ChatRequest(BaseModel):
    """对话请求"""
    message: str = Field(..., description="用户消息")
    session_id: str = Field(default="default", description="会话ID")
    camera_id: Optional[str] = Field(default=None, description="指定摄像头")


class ChatResponse(BaseModel):
    """对话响应"""
    session_id: str
    message: str
    intent: IntentType
    data: Optional[dict] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class FaceRecord(BaseModel):
    """人脸识别记录"""
    id: Optional[int] = None
    camera_id: str
    person_name: str = "未知"
    confidence: float
    face_image_path: Optional[str] = None
    snapshot_path: Optional[str] = None
    detected_at: datetime = Field(default_factory=datetime.now)
    is_unknown: bool = False
    attributes: Optional[dict] = None


class PersonInfo(BaseModel):
    """人员信息"""
    id: Optional[int] = None
    name: str
    face_encoding_path: str          # 人脸特征文件路径
    face_image_path: str             # 人脸照片路径
    category: str = "staff"          # staff / visitor / blacklist
    phone: Optional[str] = None
    department: Optional[str] = None
    remarks: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


class CameraInfo(BaseModel):
    """摄像头信息"""
    id: str
    name: str
    source: str                      # 0=本地摄像头, rtsp://xxx
    location: str = ""
    status: str = "offline"          # online / offline
    fps: int = 5
    rotation: int = 0                # 画面旋转角度 0/90/180/270


class AlertRule(BaseModel):
    """告警规则"""
    id: Optional[int] = None
    name: str
    condition_type: str              # blacklist_appear / unknown_appear / time_range
    condition_value: dict
    enabled: bool = True
    notify_method: str = "websocket" # websocket / email / sms
