# API v0.1：供 B、C 并行接入

当前实现账号、资料、场馆路线和用户视频上传／访问及 Beta 分享标记；评论、持久任务和通知尚未实现。

## 启动和代理

API 运行在 127.0.0.1:8788；保留已有算法服务 8787。B 在 Vite 中将 `/api/auth`、`/api/profile`、`/api/gyms`、`/api/routes` 和后续用户视频接口代理到 8788，旧 `/api/skeleton-jobs` 继续代理到 8787。不要直接替换旧算法代理。

浏览器只访问前端同源 `/api`，不直接请求 8788。开发请求使用 `credentials: 'same-origin'`；无需跨域 CORS。APP_ORIGINS 配置实际浏览器地址（协议、主机、端口），不是代理目标；局域网需添加实际局域网地址。HTTPS 隧道展示设置 COOKIE_SECURE=true 并配置准确的 HTTPS origin，重启 API 后重新登录。

## 会话与错误

用户名 3–32 位，仅英文字母、数字、下划线，大小写不敏感；密码 8–128 位。注册同时登录。Cookie 为 HttpOnly、SameSite=Lax，服务端会话 7 天到期；数据库只保存会话 token 的哈希。密码使用 Argon2。

注册、登录以及 me 返回 `{ "user": {...}, "csrf_token": "..." }`。B 在内存中保存 csrf_token，刷新后通过 me 恢复。已登录的修改请求添加 `X-CSRF-Token`；不要尝试读取 HttpOnly Cookie。所有修改请求都必须来自 APP_ORIGINS，包括注册登录（浏览器自动发送 Origin）。命令行调试也需提供 Origin。

错误格式：`{"error":{"message":"..."}}`。401 表示需要登录，403 表示权限／Origin／CSRF 问题，409 用户名冲突，422 参数错误，429 频率超限。登录注册按连接 IP 合计限制每分钟 10 次，当前单进程内存限流；重启会重置，同代理用户可能共享额度，公开部署前需升级为共享限流并谨慎配置可信代理。

用户字段：`id`（UUID 字符串）、`username`、`display_name`、`height_cm`、`arm_span_cm`。未填写身材参数为 null。

## 用户视频

用户视频最长 90 秒、最大 200 MiB，仅接受 MP4/MOV；服务端用 ffprobe 实际探测媒体并检查容器签名。ffprobe 需安装在运行 API 的机器上。文件写入 `UPLOAD_DIR`（默认仓库根目录 `data/uploads/`，gitignore 排除），数据库保存元数据和相对存储标识。

| 方法 | 路径 | 输入／返回 |
| --- | --- | --- |
| POST | /api/videos | multipart: `route_id`、`visibility`（private/public，不区分大小写）、可选 `share_as_beta`（默认 false；只能和 public 同用）、可选 `title`（默认文件名，最多 120 字符）、可选 `description`（最多 500 字符）、`video`；201 返回元数据和受保护 `content_url` |
| GET | /api/videos?owned=true | 当前用户上传；`owned=false` 返回所有公开视频，不要求开启 Beta；支持 `route_id`、`share_as_beta`、limit/offset |
| GET | /api/videos/{id} | 上传者或登录用户（仅 public） |
| GET | /api/videos/{id}/content | 上传者或登录用户（仅 public）；支持 HTTP Range 播放 |
| PATCH | /api/videos/{id} | JSON `{"visibility":"public","share_as_beta":true}`；仅上传者。private 必须同时令 share_as_beta=false |
| DELETE | /api/videos/{id} | 仅上传者；删除元数据及文件 |

上传/修改/删除需登录、Origin 和 `X-CSRF-Token`。不存在或无权访问的视频统一返回 404，避免泄露私有资源是否存在。上传先写临时文件，验证完成后移动到私有目录并创建记录；失败会删除临时文件。浏览器不能播放某些 MOV 编码时目前会原样提供；转码策略待确认。

公开视频列表附带 `username` 和 `display_name`。只有 `share_as_beta=true` 的公开视频会附带上传者 `height_cm` 和 `arm_span_cm`；普通公开分享不暴露这两项资料。Community 展示所有 Public 用户视频，Community Beta 按路线只查询 Public 且 `share_as_beta=true` 的视频。仓库内预置示例视频不属于此 API 的用户视频记录。

| 方法 | 路径 | 输入／返回 |
| --- | --- | --- |
| GET | /api/health | 数据库连接正常返回 ready=true |
| POST | /api/auth/register | username、password；201 返回 user、csrf_token |
| POST | /api/auth/login | username、password；返回 user、csrf_token |
| GET | /api/auth/me | 返回当前 user、csrf_token；未登录 401 |
| POST | /api/auth/logout | 需 CSRF；204，无响应体 |
| PUT | /api/profile | 需 CSRF；display_name、height_cm、arm_span_cm；返回 user |
| GET | /api/gyms | 需登录；返回 items，含 active_route_count |
| GET | /api/routes | 需登录；gym_id 可选，include_archived 默认 false，limit 默认 50 最大 100，offset 默认 0 |
| GET | /api/routes/{id} | 需登录；路线及 media；不存在 404 |

PUT profile 是完整资料更新：display_name 必填，省略或传 null 的身材字段会清空。身高 100–230 cm，臂展 80–260 cm。UI 注册流程可随后补填资料。

路线保留 r1/r2/r3；Gym ID 为 gym-a/gym-b。时间字段为带时区 ISO 字符串。媒体的 storage_backend=bundled 时，storage_key 相对于前端 public 根目录，如 media/trial2.mp4；这是公开示例。不要把未来私有上传转成 public URL。

## 模块协作

A 维护 app.py、账号／目录模块与公共鉴权；B、C 后续独立建 APIRouter，通过 Depends(current_session) 获取用户并自动校验修改请求 CSRF。不要接受客户端 user_id 作为资源归属依据。引入路由时再拆公共依赖到独立模块，避免循环导入。

新增迁移使用独立递增编号，合并前协调编号；已执行文件不修改。注册不会自动创建示例上传、评论或任务。预设账号通过注册接口创建，密码通过本地渠道保存，不写入种子或仓库。
