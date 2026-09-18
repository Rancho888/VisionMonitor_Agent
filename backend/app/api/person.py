"""
人像库管理 API 模块 —— 人员的查询、注册、删除、照片管理

包含的端点：
1. GET    /api/persons                       —— 获取所有人像库数据
2. POST   /api/persons/register              —— 注册新人员（支持多张照片）
3. POST   /api/persons/{person_name}/add-photo —— 对已有人员追加照片
4. GET    /api/persons/{person_name}/avatar  —— 获取人员头像（base64）
5. GET    /api/persons/{person_name}         —— 获取单个人像详情
6. DELETE /api/persons/{person_name}         —— 删除人员

模块职责：
- 提供人员（Person）的完整 CRUD 操作
- 集成 face_service 进行人脸特征提取和管理
- 支持多图注册以提升人脸识别置信度
- 数据库（db_agent）与人脸库（face_service）双写保证数据一致性
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from backend.app.agents.database_agent import db_agent
from backend.app.models.schemas import PersonInfo
from backend.app.services.face_service import face_service

# 路由前缀 /api/persons，标签为 persons（用于 Swagger 文档分组）
router = APIRouter(prefix="/api/persons", tags=["persons"])


@router.get("")
async def list_persons():
    """
    获取所有人像库数据（含照片数量）

    HTTP方法: GET
    路径: /api/persons
    功能: 查询数据库中所有已注册人员，并补充每个人在 face_db 中的照片数量

    参数: 无

    返回值:
        persons: 人员信息列表，每项包含数据库字段 + photo_count（照片数量）
        total: 人员总数
    """
    # 从数据库获取所有人员基本信息
    persons = await db_agent.get_all_persons()
    # 补充每个人员在人脸库中的照片数量（用于前端展示）
    for p in persons:
        p["photo_count"] = face_service.get_photo_count(p["name"])
    return {"persons": persons, "total": len(persons)}


@router.post("/register")
async def register_person(
    name: str = Form(...),
    category: str = Form("staff"),
    department: str = Form(""),
    images: list[UploadFile] = File(...),
):
    """
    注册新人员（可上传多张照片以提升识别精度）

    HTTP方法: POST
    路径: /api/persons/register
    功能: 创建一个新的人员记录，提取人脸特征并注册到 face_db

    参数:
        name: 人员姓名（表单字段，不能为空）
        category: 人员类别，默认 "staff"（可选 staff/visitor/blacklist）
        department: 所属部门，默认空
        images: 上传的照片文件列表（至少一张）

    返回值: {"message": "已注册 xxx，共 N 张照片", "name": "xxx", "photo_count": N}
    异常:
        400 - 姓名为空 / 未上传照片 / 人脸注册失败

    执行流程：
    1. 参数校验（姓名非空、至少一张照片）
    2. 读取第一张照片，提取人脸特征并注册到 face_db
    3. 遍历剩余照片，追加人脸特征（多角度提升识别精度）
    4. 将人员信息写入数据库
    """
    # 参数校验
    if not name.strip():
        raise HTTPException(status_code=400, detail="姓名不能为空")
    if not images:
        raise HTTPException(status_code=400, detail="请至少上传一张照片")

    # 第一步：读取第一张照片用于初始人脸注册（创建 face_db 目录和特征文件）
    first_bytes = await images[0].read()
    success = face_service.register_face_from_bytes(name.strip(), first_bytes)
    if not success:
        raise HTTPException(status_code=400, detail="人脸注册失败，请确保照片中有清晰正面人脸")

    # 第二步：追加剩余照片的人脸特征（多角度/多表情提升识别置信度）
    for img in images[1:]:
        img_bytes = await img.read()
        face_service.add_face_to_person(name.strip(), img_bytes)

    # 第三步：将人员信息写入数据库（face_image_path 取第一张照片的路径作为代表照）
    person = PersonInfo(
        name=name.strip(),
        face_encoding_path=f"./data/face_db/{name.strip()}",
        face_image_path=face_service.known_persons.get(name.strip(), {}).get("image_paths", [""])[0] if face_service.known_persons.get(name.strip()) else "",
        category=category,
        department=department,
    )
    await db_agent.add_person(person)

    photo_count = face_service.get_photo_count(name.strip())
    return {"message": f"已注册 {name}，共 {photo_count} 张照片", "name": name.strip(), "photo_count": photo_count}


@router.post("/{person_name}/add-photo")
async def add_person_photo(
    person_name: str,
    images: list[UploadFile] = File(...),
):
    """
    对已有人员追加照片（提升识别置信度）

    HTTP方法: POST
    路径: /api/persons/{person_name}/add-photo
    功能: 为已注册的人员追加人脸照片，增加特征样本数量以提高识别准确率

    参数:
        person_name: 人员姓名（路径参数）
        images: 上传的照片文件列表（至少一张）

    返回值: {"message": "已追加 N 张照片", "name": "xxx", "photo_count": N}
    异常: 404 - 人员不存在

    执行流程：
    1. 校验人员是否存在
    2. 遍历上传的照片，逐个提取特征并追加到该人员的人脸库中
    3. 统计成功追加的照片数量
    """
    # 校验人员是否存在
    persons = await db_agent.get_all_persons()
    matched = [p for p in persons if p["name"] == person_name]
    if not matched:
        raise HTTPException(status_code=404, detail="人员不存在")

    # 遍历照片，逐个追加人脸特征，统计成功数量
    added = 0
    for img in images:
        img_bytes = await img.read()
        if face_service.add_face_to_person(person_name, img_bytes):
            added += 1

    photo_count = face_service.get_photo_count(person_name)
    return {"message": f"已追加 {added} 张照片", "name": person_name, "photo_count": photo_count}


@router.get("/{person_name}/avatar")
async def get_person_avatar(person_name: str):
    """
    获取人员头像（base64 编码）

    HTTP方法: GET
    路径: /api/persons/{person_name}/avatar
    功能: 返回指定人员的代表头像，以 base64 编码格式供前端直接展示

    参数:
        person_name: 人员姓名

    返回值: {"name": "xxx", "avatar_base64": "data:image/jpeg;base64,..."}
    异常: 404 - 头像不存在
    """
    b64 = face_service.get_person_avatar(person_name)
    if not b64:
        raise HTTPException(status_code=404, detail="头像不存在")
    return {"name": person_name, "avatar_base64": b64}


@router.get("/{person_name}")
async def get_person(person_name: str):
    """
    获取单个人像详情

    HTTP方法: GET
    路径: /api/persons/{person_name}
    功能: 查询指定人员的完整信息（含照片数量）

    参数:
        person_name: 人员姓名

    返回值: 人员完整信息字典（数据库字段 + photo_count）
    异常: 404 - 人员不存在
    """
    persons = await db_agent.get_all_persons()
    matched = [p for p in persons if p["name"] == person_name]
    if not matched:
        raise HTTPException(status_code=404, detail="人员不存在")
    result = dict(matched[0])
    result["photo_count"] = face_service.get_photo_count(person_name)
    return result


@router.delete("/{person_name}")
async def delete_person(person_name: str):
    """
    删除人员（数据库 + face_db 同步清理）

    HTTP方法: DELETE
    路径: /api/persons/{person_name}
    功能: 完整移除人员信息，包括数据库记录和人脸库中的特征文件

    参数:
        person_name: 人员姓名

    返回值: {"message": "已删除 xxx"}
    异常: 404 - 人员不存在

    执行流程：
    1. 从数据库中删除人员记录
    2. 从 face_service（face_db）中删除该人员的人脸特征文件和目录
    """
    # 第一步：从数据库中删除人员记录
    success = await db_agent.delete_person(person_name)
    if not success:
        raise HTTPException(status_code=404, detail="人员不存在")
    # 第二步：从人脸库中删除特征文件和目录
    face_service.remove_face(person_name)
    return {"message": f"已删除 {person_name}"}
"""
人像库管理 API - 查询、注册、删除人员
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from backend.app.agents.database_agent import db_agent
from backend.app.models.schemas import PersonInfo
from backend.app.services.face_service import face_service

router = APIRouter(prefix="/api/persons", tags=["persons"])


@router.get("")
async def list_persons():
    """获取所有人像库数据（含照片数量）"""
    persons = await db_agent.get_all_persons()
    for p in persons:
        p["photo_count"] = face_service.get_photo_count(p["name"])
    return {"persons": persons, "total": len(persons)}


@router.post("/register")
async def register_person(
    name: str = Form(...),
    category: str = Form("staff"),
    department: str = Form(""),
    images: list[UploadFile] = File(...),
):
    """注册新人员（可上传多张照片）"""
    if not name.strip():
        raise HTTPException(status_code=400, detail="姓名不能为空")
    if not images:
        raise HTTPException(status_code=400, detail="请至少上传一张照片")

    # 读取第一张图片用于注册 face_db
    first_bytes = await images[0].read()
    success = face_service.register_face_from_bytes(name.strip(), first_bytes)
    if not success:
        raise HTTPException(status_code=400, detail="人脸注册失败，请确保照片中有清晰正面人脸")

    # 追加剩余照片
    for img in images[1:]:
        img_bytes = await img.read()
        face_service.add_face_to_person(name.strip(), img_bytes)

    # 写数据库
    person = PersonInfo(
        name=name.strip(),
        face_encoding_path=f"./data/face_db/{name.strip()}",
        face_image_path=face_service.known_persons.get(name.strip(), {}).get("image_paths", [""])[0] if face_service.known_persons.get(name.strip()) else "",
        category=category,
        department=department,
    )
    await db_agent.add_person(person)

    photo_count = face_service.get_photo_count(name.strip())
    return {"message": f"已注册 {name}，共 {photo_count} 张照片", "name": name.strip(), "photo_count": photo_count}


@router.post("/{person_name}/add-photo")
async def add_person_photo(
    person_name: str,
    images: list[UploadFile] = File(...),
):
    """对已有人员追加照片（提升识别置信度）"""
    persons = await db_agent.get_all_persons()
    matched = [p for p in persons if p["name"] == person_name]
    if not matched:
        raise HTTPException(status_code=404, detail="人员不存在")

    added = 0
    for img in images:
        img_bytes = await img.read()
        if face_service.add_face_to_person(person_name, img_bytes):
            added += 1

    photo_count = face_service.get_photo_count(person_name)
    return {"message": f"已追加 {added} 张照片", "name": person_name, "photo_count": photo_count}


@router.get("/{person_name}/avatar")
async def get_person_avatar(person_name: str):
    """获取人员头像 base64"""
    b64 = face_service.get_person_avatar(person_name)
    if not b64:
        raise HTTPException(status_code=404, detail="头像不存在")
    return {"name": person_name, "avatar_base64": b64}


@router.get("/{person_name}")
async def get_person(person_name: str):
    """获取单个人像详情"""
    persons = await db_agent.get_all_persons()
    matched = [p for p in persons if p["name"] == person_name]
    if not matched:
        raise HTTPException(status_code=404, detail="人员不存在")
    result = dict(matched[0])
    result["photo_count"] = face_service.get_photo_count(person_name)
    return result


@router.delete("/{person_name}")
async def delete_person(person_name: str):
    """删除人员（数据库 + face_db 同步清理）"""
    success = await db_agent.delete_person(person_name)
    if not success:
        raise HTTPException(status_code=404, detail="人员不存在")
    face_service.remove_face(person_name)
    return {"message": f"已删除 {person_name}"}
