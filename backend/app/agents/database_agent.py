"""
数据库 Agent（Database Agent）- 负责数据存储和查询

模块职责：
    封装所有数据库操作，包括：
    1. 人脸识别记录的保存、查询、统计
    2. 人员信息库的增删查
    3. 告警规则管理
    4. 摄像头配置的 CRUD

架构说明：
    - 基于 SQLAlchemy 2.0 异步接口，使用 aiosqlite 驱动
    - 每个方法独立管理 session（with 语句自动关闭）
    - 供 monitor_tools、vision_agent、API 层调用
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_
from backend.app.models.database import (
    async_session, FaceRecordModel, PersonInfoModel,
    AlertRuleModel, CameraInfoModel,
)
from backend.app.models.schemas import FaceRecord, PersonInfo


class DatabaseAgent:
    """
    数据库操作 Agent，封装所有监控系统的 CRUD 操作。

    数据模型：
        - FaceRecordModel: 人脸识别记录（每次识别产生一条）
        - PersonInfoModel: 注册人员信息
        - AlertRuleModel: 告警规则配置
        - CameraInfoModel: 摄像头配置
    """

    # ==================== 人脸记录 ====================

    async def save_face_record(self, record: FaceRecord) -> int:
        """
        保存人脸识别记录到数据库。

        Args:
            record: FaceRecord 数据对象，包含 camera_id, person_name,
                confidence, snapshot_path, detected_at, is_unknown 等字段

        Returns:
            新插入记录的数据库 ID（int）
        """
        async with async_session() as session:
            model = FaceRecordModel(
                camera_id=record.camera_id,
                person_name=record.person_name,
                confidence=record.confidence,
                face_image_path=record.face_image_path,
                snapshot_path=record.snapshot_path,
                detected_at=record.detected_at,
                is_unknown=record.is_unknown,
                attributes=record.attributes,
            )
            session.add(model)
            await session.commit()
            return model.id  # 返回自增 ID

    async def query_records(
        self,
        person_name: Optional[str] = None,
        camera_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        is_unknown: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        查询人脸识别记录（支持多条件筛选和分页）。

        所有筛选条件均为可选，不传则不作为筛选条件。

        Args:
            person_name: 人员姓名筛选
            camera_id: 摄像头 ID 筛选
            start_time: 起始时间筛选
            end_time: 结束时间筛选
            is_unknown: 是否为陌生人筛选
            limit: 返回条数上限（int），默认 50
            offset: 分页偏移量（int），默认 0

        Returns:
            记录列表，每条为 dict，包含 id, camera_id, person_name,
            confidence, snapshot_path, detected_at, is_unknown
        """
        async with async_session() as session:
            # 动态构建查询条件，仅非空参数才加入条件
            conditions = []
            if person_name:
                conditions.append(FaceRecordModel.person_name == person_name)
            if camera_id:
                conditions.append(FaceRecordModel.camera_id == camera_id)
            if start_time:
                conditions.append(FaceRecordModel.detected_at >= start_time)
            if end_time:
                conditions.append(FaceRecordModel.detected_at <= end_time)
            if is_unknown is not None:
                conditions.append(FaceRecordModel.is_unknown == is_unknown)

            # 按检测时间降序排列，支持分页
            query = select(FaceRecordModel).where(and_(*conditions)).order_by(
                FaceRecordModel.detected_at.desc()
            ).offset(offset).limit(limit)

            result = await session.execute(query)
            records = result.scalars().all()

            return [
                {
                    "id": r.id,
                    "camera_id": r.camera_id,
                    "person_name": r.person_name,
                    "confidence": r.confidence,
                    "face_image_path": r.face_image_path,
                    "snapshot_path": r.snapshot_path,
                    "detected_at": r.detected_at.isoformat(),
                    "is_unknown": r.is_unknown,
                }
                for r in records
            ]

    async def count_records(
        self,
        person_name: Optional[str] = None,
        camera_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        is_unknown: Optional[bool] = None,
    ) -> int:
        """
        统计符合筛选条件的人脸记录总数（用于前端分页计算）。

        参数与 query_records 一致，仅返回数量不返回具体记录。

        Returns:
            匹配的记录总数（int）
        """
        async with async_session() as session:
            conditions = []
            if person_name:
                conditions.append(FaceRecordModel.person_name == person_name)
            if camera_id:
                conditions.append(FaceRecordModel.camera_id == camera_id)
            if start_time:
                conditions.append(FaceRecordModel.detected_at >= start_time)
            if end_time:
                conditions.append(FaceRecordModel.detected_at <= end_time)
            if is_unknown is not None:
                conditions.append(FaceRecordModel.is_unknown == is_unknown)

            # 使用 func.count() 进行聚合查询，避免加载全部记录
            query = select(func.count()).select_from(FaceRecordModel).where(and_(*conditions))
            result = await session.execute(query)
            return result.scalar() or 0

    async def get_person_stats(
        self,
        person_name: str,
        days: int = 7,
    ) -> Dict[str, Any]:
        """
        获取某人的统计信息：总出现次数、按日统计、最后出现时间。

        Args:
            person_name: 人员姓名（必填）
            days: 统计时间范围（天），默认 7 天

        Returns:
            dict，包含：
            - person_name: 人员姓名
            - total_appearances: 总出现次数（int）
            - days_active: 有记录的天数（int）
            - daily_breakdown: 按日期统计的 dict（key=日期, value=次数）
            - last_seen: 最后出现时间的 ISO 格式字符串（可能为 None）
        """
        async with async_session() as session:
            # 计算统计起始时间
            start_time = datetime.now() - timedelta(days=days)

            # 查询总出现次数
            count_query = select(func.count()).where(
                and_(
                    FaceRecordModel.person_name == person_name,
                    FaceRecordModel.detected_at >= start_time,
                )
            )
            count_result = await session.execute(count_query)
            total_count = count_result.scalar()

            # 查询详细记录用于按日统计
            records_query = select(FaceRecordModel).where(
                and_(
                    FaceRecordModel.person_name == person_name,
                    FaceRecordModel.detected_at >= start_time,
                )
            ).order_by(FaceRecordModel.detected_at.desc())

            records_result = await session.execute(records_query)
            records = records_result.scalars().all()

            # 按日期聚合统计出现次数
            daily_count = {}
            for r in records:
                day = r.detected_at.strftime("%Y-%m-%d")
                daily_count[day] = daily_count.get(day, 0) + 1

            return {
                "person_name": person_name,
                "total_appearances": total_count,
                "days_active": len(daily_count),
                "daily_breakdown": daily_count,
                "last_seen": records[0].detected_at.isoformat() if records else None,
            }

    async def get_top_persons(self, days: int = 7, limit: int = 10) -> List[Dict]:
        """
        获取高频出现人员排名（排除陌生人）。

        Args:
            days: 统计时间范围（天），默认 7 天
            limit: 返回排名人数，默认 10

        Returns:
            排名列表，每项包含 name（姓名）和 count（出现次数），
            按出现次数降序排列
        """
        async with async_session() as session:
            start_time = datetime.now() - timedelta(days=days)

            # 按姓名分组统计出现次数，排除陌生人，降序排列取 Top N
            query = (
                select(
                    FaceRecordModel.person_name,
                    func.count().label("count"),
                )
                .where(
                    and_(
                        FaceRecordModel.detected_at >= start_time,
                        FaceRecordModel.is_unknown == False,
                    )
                )
                .group_by(FaceRecordModel.person_name)
                .order_by(func.count().desc())
                .limit(limit)
            )

            result = await session.execute(query)
            return [
                {"name": row[0], "count": row[1]}
                for row in result.all()
            ]

    # ==================== 人员管理 ====================
    # 注册人员信息库的 CRUD 操作

    async def get_all_persons(self) -> List[Dict]:
        """
        获取所有注册人员列表。

        Returns:
            人员列表，每项包含 id, name, category, department,
            face_encoding_path, face_image_path, created_at
        """
        async with async_session() as session:
            query = select(PersonInfoModel)
            result = await session.execute(query)
            persons = result.scalars().all()
            return [
                {
                    "id": p.id,
                    "name": p.name,
                    "category": p.category,
                    "department": p.department,
                    "face_encoding_path": p.face_encoding_path,
                    "face_image_path": p.face_image_path,
                    "created_at": p.created_at.isoformat(),
                }
                for p in persons
            ]

    async def add_person(self, person: PersonInfo) -> int:
        """
        添加新注册人员到数据库。

        Args:
            person: PersonInfo 数据对象，包含 name, face_encoding_path,
                face_image_path, category, phone, department, remarks

        Returns:
            新插入记录的数据库 ID（int）
        """
        async with async_session() as session:
            model = PersonInfoModel(
                name=person.name,
                face_encoding_path=person.face_encoding_path,
                face_image_path=person.face_image_path,
                category=person.category,
                phone=person.phone,
                department=person.department,
                remarks=person.remarks,
            )
            session.add(model)
            await session.commit()
            return model.id

    async def delete_person(self, name: str) -> bool:
        """
        根据姓名删除注册人员。

        Args:
            name: 人员姓名

        Returns:
            bool，True 表示成功删除，False 表示未找到该人员
        """
        async with async_session() as session:
            query = select(PersonInfoModel).where(PersonInfoModel.name == name)
            result = await session.execute(query)
            person = result.scalar_one_or_none()
            if person:
                await session.delete(person)
                await session.commit()
                return True
            return False

    # ==================== 告警规则 ====================
    # 告警规则配置的查询和添加

    async def get_alert_rules(self) -> List[Dict]:
        """
        获取所有告警规则配置。

        Returns:
            规则列表，每项包含 id, name, condition_type,
            condition_value, enabled
        """
        async with async_session() as session:
            result = await session.execute(select(AlertRuleModel))
            rules = result.scalars().all()
            return [
                {
                    "id": r.id,
                    "name": r.name,
                    "condition_type": r.condition_type,
                    "condition_value": r.condition_value,
                    "enabled": r.enabled,
                }
                for r in rules
            ]

    async def add_alert_rule(self, rule_data: Dict) -> int:
        """
        添加新的告警规则。

        Args:
            rule_data: 规则数据字典，包含 name, condition_type,
                condition_value, enabled 等字段

        Returns:
            新插入记录的数据库 ID（int）
        """
        async with async_session() as session:
            model = AlertRuleModel(**rule_data)
            session.add(model)
            await session.commit()
            return model.id

    # ==================== 摄像头管理 ====================
    # 摄像头配置的 CRUD 操作

    async def get_cameras(self) -> List[Dict]:
        """
        获取数据库中的摄像头配置列表。

        Returns:
            摄像头列表，每项包含 id, name, source, location,
            status, fps, rotation
        """
        async with async_session() as session:
            result = await session.execute(select(CameraInfoModel))
            cameras = result.scalars().all()
            return [
                {
                    "id": c.id,
                    "name": c.name,
                    "source": c.source,
                    "location": c.location,
                    "status": c.status,
                    "fps": c.fps,
                    "rotation": c.rotation if hasattr(c, "rotation") else 0,
                }
                for c in cameras
            ]

    async def add_camera(self, camera_data: Dict) -> bool:
        """
        添加新摄像头配置到数据库。

        Args:
            camera_data: 摄像头配置字典

        Returns:
            bool，始终返回 True 表示添加成功
        """
        async with async_session() as session:
            model = CameraInfoModel(**camera_data)
            session.add(model)
            await session.commit()
            return True

    async def update_camera(self, camera_id: str, data: Dict) -> bool:
        """
        编辑摄像头配置（支持部分字段更新）。

        Args:
            camera_id: 摄像头 ID
            data: 要更新的字段字典，支持 name, source,
                location, fps, rotation, status

        Returns:
            bool，True 表示成功更新，False 表示未找到该摄像头
        """
        from sqlalchemy import update
        async with async_session() as session:
            result = await session.execute(
                select(CameraInfoModel).where(CameraInfoModel.id == camera_id)
            )
            cam = result.scalars().first()
            if not cam:
                return False
            # 仅更新 data 中存在的且属于允许字段的键值对
            upd = {}
            for field in ("name", "source", "location", "fps", "rotation", "status"):
                if field in data:
                    upd[field] = data[field]
            if upd:
                await session.execute(
                    update(CameraInfoModel)
                    .where(CameraInfoModel.id == camera_id)
                    .values(**upd)
                )
                await session.commit()
            return True

    async def delete_camera(self, camera_id: str) -> bool:
        """
        删除摄像头配置。

        Args:
            camera_id: 摄像头 ID

        Returns:
            bool，True 表示成功删除，False 表示未找到该摄像头
        """
        async with async_session() as session:
            result = await session.execute(
                select(CameraInfoModel).where(CameraInfoModel.id == camera_id)
            )
            cam = result.scalars().first()
            if not cam:
                return False
            await session.delete(cam)
            await session.commit()
            return True

    async def clear_all_records(self) -> int:
        """
        清空全部人脸识别记录（危险操作）。

        Returns:
            删除的记录行数（int）
        """
        from sqlalchemy import delete
        async with async_session() as session:
            result = await session.execute(delete(FaceRecordModel))
            await session.commit()
            return result.rowcount

    async def get_record_by_id(self, record_id: int) -> Optional[Dict]:
        """
        根据 ID 获取单条识别记录。

        Args:
            record_id: 记录 ID（int）

        Returns:
            记录字典（包含 id, camera_id, person_name, confidence,
            snapshot_path, detected_at, is_unknown），未找到时返回 None
        """
        async with async_session() as session:
            result = await session.execute(
                select(FaceRecordModel).where(FaceRecordModel.id == record_id)
            )
            r = result.scalars().first()
            if not r:
                return None
            return {
                "id": r.id,
                "camera_id": r.camera_id,
                "person_name": r.person_name,
                "confidence": r.confidence,
                "snapshot_path": r.snapshot_path,
                "detected_at": r.detected_at.isoformat(),
                "is_unknown": r.is_unknown,
            }


# 全局单例：供 monitor_tools、vision_agent 和 API 层调用
db_agent = DatabaseAgent()
