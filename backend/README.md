# A：数据库基础

当前交付：PostgreSQL、版本化 SQL 迁移、目录种子数据，以及 FastAPI 账号／Cookie 会话／资料／场馆路线／用户视频 API；React 前端已接入登录、目录、上传和视频权限流程。点赞、收藏、评论持久化和后台任务／通知仍未完成。接口见 [API.md](API.md)。

## API 开发启动

先完成下方数据库步骤，再在仓库根目录执行：

```sh
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
python3 backend/db/manage.py migrate
backend/.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8788
```

交互文档：http://127.0.0.1:8788/docs 。浏览器 Origin 必须列在根目录 `.env` 的 `APP_ORIGINS`；修改请求另需 CSRF token，具体见 API.md。Vite 代理把账号、目录、资料和视频接口转发到 8788；算法服务仍单独使用 8787。

## 启动

需要 Docker Desktop（先打开并等引擎启动）、Compose 和 Python 3。
在仓库根目录执行：

```sh
cp .env.example .env
# 修改 .env 中的 POSTGRES_PASSWORD，不提交 .env
docker compose up -d db
docker compose ps
python3 backend/db/manage.py migrate
python3 backend/db/manage.py seed
```

上传 MP4／MOV 还需要在运行 FastAPI 的主机安装 `ffprobe`（通常随 FFmpeg 提供）；缺少时服务会返回明确安装提示。

数据库仅绑定本机 `127.0.0.1:5433`，供本地 API 连接，不开放给局域网用户。用户上传视频在本地 `data/uploads/`，该目录已加入 gitignore。局域网和隧道只暴露应用入口。换机器后重复这些步骤即可；迁移和种子可重复执行。种子不会覆盖已编辑数据。

同一 Wi-Fi 的手机展示：将 Vite 监听在 `0.0.0.0`，例如 `npm run dev -- --host 0.0.0.0 --port 5174`；把手机访问的准确 origin（`http://<Mac 局域网 IP>:5174`）加入 `.env` 的 `APP_ORIGINS` 并重启 API。手机和 Mac 访问同一个服务，Mac 需要保持开机、联网并运行 Vite、API 和 Docker 数据库。`.env` 只保存在本机，不提交。

```sh
docker compose stop
docker compose start
```

普通停止保留数据库卷。不要使用 `docker compose down -v`，它会删除数据库卷。迁移只执行一次并记录校验和；已经执行的迁移不得修改，新增编号文件。迁移先于种子执行。

## 当前数据

| Gym | 路线 ID | 名称 | 等级 | 状态 | 示例视频 |
| --- | --- | --- | --- | --- | --- |
| Gym A | r1 | Corner Study | V3 | 使用中 | trial2.mp4 |
| Gym A | r2 | Long Reach | V5 | 使用中 | trial3.mp4 |
| Gym B | — | 暂无路线 | — | — | — |

这些对应当前 `src/App.tsx`，不推测尚未提供的 Gym B 内容。媒体引用现有 `public/media`，标注为示例，不创建虚构用户上传。每条路线允许多条媒体记录，每种类型最多一条主媒体；后续可补充多视频。

Gym 的路线数量应查询未归档路线计算，不保存前端硬编码 count。新场馆路线使用稳定、唯一的 ID（可使用 UUID 文本）；名称可以修改，不用名称关联。时间为带时区时间，修改记录时由应用更新 updated_at。

## 后续分工与扩展

- A：账号／会话、资料、目录、用户视频和受保护播放的基础已实现；后续继续维护导入、存储迁移与部署文档。
- B：补齐评论与点赞／收藏的持久化 API 和前端接入；预置示例继续与用户上传记录分开。
- C：实现持久后台任务和通知；真实生成产物不可写入公开的 `public/media`。
- 用户上传使用私有本地目录，后续通过存储适配器迁移；本仓库中的 bundled 媒体仅用于公开示例。
- 大量数据使用独立导入脚本、事务和稳定 ID，不反复修改已执行的 schema 迁移；先约定导入表格格式，再补充正式数据。
- 数据库卷与视频目录需要分别备份；当前尚未提供自动备份和恢复实现。
