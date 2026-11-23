# BetaLab

[English](README.md) · [简体中文](README.zh-CN.md)

BetaLab 是一个使用 React、TypeScript、Vite、FastAPI 和 PostgreSQL 的移动端优先攀岩原型。本手册描述 **截至 2026 年 11 月 23 日在本地核验的实现**，不代表已部署网站包含全部功能。本手册统一替代此前分散的阶段报告和交接说明。原文仅保存在本地归档包中，不随 Git 提交或推送。

## 目录

1. [项目概览](#overview)
2. [当前实现状态](#status)
3. [仓库目录结构](#structure)
4. [本地配置与启动](#setup)
5. [产品流程](#workflows)
6. [后端与接口约定](#api)
7. [视频与骨架流水线](#pipeline)
8. [数据与资源](#data)
9. [结果与已知限制](#results)
10. [测试与性能](#testing)
11. [展示与故障处理](#demo)
12. [分工与下一步](#next)
13. [引用与版本历史](#history)

<a id="overview"></a>
## 1. 项目概览

BetaLab 将路线浏览、攀岩视频和基于身体比例的骨架预览连接起来。目标流程是分析上传者动作，在固定接触顺序和时序的基础上，按另一人的身高和臂展适配，再在验证通过后比较少量适用技巧。

本地应用已有真实账号、持久化上传、私有媒体、后台任务和通知。算法能力范围更窄：Trial2 支持源动作和目标身材的诊断预览；其他视频目前支持输入提取与标定核查，尚未完成完整骨架适配。

[GitHub Pages 页面](https://ilinoisziwei.github.io/BetaLab/)是静态前端部署，不运行本地 API、数据库、私有上传或 worker。Git push 不会传输本地用户数据或科学计算模型资源。

<a id="status"></a>
## 2. 当前实现状态

| 模块 | 本地已实现 | 剩余工作 |
| --- | --- | --- |
| 账号与视频 | 登录、资料、关联路线的上传、播放、可见性和删除；数据库、上传和计算产物的备份恢复（含校验） | 部署完善、更广泛设备测试 |
| 路线目录 | Movement Fishtown、73张高亮路线图及 r1 | 核查不确定图片标注，补充其他目录数据 |
| 任务与通知 | 持久队列、单 worker、重试、通知、受保护产物 | 更广泛运行与性能验证 |
| 上传后分析 | 自动提交、提交恢复、失败重试、刷新恢复 | 更多真实视频异常场景和更具体的处理提示 |
| Community → My Library | 绑定源视频的生成请求、身材输入、任务状态、诊断播放 | 将生成能力推广到已标定 Trial2 以外的视频 |
| 新视频输入 | 输入提取、人工接触版本、局部标定；有测量输入时的墙面拼接/相机对齐与统一导出 | 真实手持视频标定数据、自动移动相机恢复、人体深度/源动作重建及适配 |
| Trial2 几何 | v5 源动作与目标身材诊断预览 | 基线仍失败；源动作调查目前暂缓 |
| 结果展示 | 示例、诊断和设有准入条件的技巧结果分开 | 当前流程尚未实现完整模型检查和真实技巧比较 |
| 社区互动 | 持久化评论及一层回复、评论点赞、按时间点出现的弹幕（界面称 live comments）、视频点赞/收藏/转发、想爬路线、关注，上传视频与预置示例均支持；点击作者或右滑进入作者主页（N2.8）；All / Following 公开视频流；可拖动的小视频时间轴；Attempts 中清晰的可见性切换；My Page 真实社交统计；Community 分页；分享链接 | 私有账号关注批准、公开点赞/收藏列表和真实设备演练；接口见 `docs/SOCIAL_API.md` |

任务完成表示计算和保存结束，不表示攀爬动作已通过几何或物理验证。

<a id="structure"></a>
## 3. 仓库目录结构

```text
BetaLab-github/
├── README.md / README.zh-CN.md   英文主文档及对应中文版
├── src/                         React 主应用和共享 API 客户端
│   ├── app/                     页面、会话/导航 hooks 和跨页面协调
│   ├── features/                目录、评论和视频功能 hooks / 视频 reducer
│   ├── components/              共享控件与媒体组件
│   ├── styles/                  按原始级联顺序加载的主界面样式
│   ├── compute/                 任务、上传、输入核查与结果界面
│   └── data/                    路线图片目录元数据
├── backend/
│   ├── app.py                   应用组装、中间件和健康检查
│   ├── auth.py / database.py    会话认证与数据库连接
│   ├── routes/                  账户、场馆/路线目录和视频接口
│   ├── media.py                 共享文件分段传输
│   ├── db/                      版本化迁移和目录种子
│   └── compute/                 任务服务、worker 与科学计算适配器
├── public/media/                公开的预置演示媒体
├── vite/plugins/                5个独立 Vite 预览/构建插件
├── tests/build/                 插件契约与真实开发服务器回归
├── scripts/                     资源准备和导入工具
├── tests/frontend/              前端结果分类测试
├── tests/compute/               契约、API、科学计算和浏览器测试
│   └── support/                 隔离数据库与浏览器环境辅助代码
├── docs/compute/examples/       机器可读 schema 和请求/结果示例
├── local-server/                历史无认证 Trial2 实验
├── compute.html                 独立的认证计算联调页
└── compose.yaml / .env.example  本地数据库与环境配置
```

`backend/README.md` 是指向英文主文档的兼容符号链接，不是单独维护的文档；现有代码注释中的引用仍可打开。

普通入口为 `/`；`/compute.html` 用于开发联调。`local-server/` 和 `/api/skeleton-jobs` 属于端口8787的旧实验；当前主页面计算通过8788的 `/api/tasks`。旧实验耗时和产物不能与 v5 混用。

`backend/compute/` 内：`api`、`service`、`storage`、`runner`、`worker`、`media` 负责执行和访问；`real_job` 及拟合/几何模块负责 Trial2；`input_job`、`input_schema`、`input_calibration`、`input_review` 负责新视频输入；`contact_schema`、`contact_review` 负责人工接触版本与逐帧导出；`world_schema`、`world_geometry`、`world_job`、`world_review` 负责全局几何及版本；`preflight`、`standby` 支持展示；`mock` 明确用于模拟。本次文档整理没有改变代码位置或算法逻辑。

生成目录 `dist/`、私有 `data/`、虚拟环境和 `backend/compute/runs/` 不属于源码文档。旧的 `before-*.css` 备份已移到仓库外本地保留，不属于源代码或本次提交。

第一轮基础去重后，主页面与计算联调页共用 `src/api.ts`，支持 JSON/multipart 请求和显式 CSRF；两者共用 `src/compute/results.ts` 中的 Task/Result/Moment/Note 类型，联调页将 CSRF 保存在组件状态。上传进度仍使用原有 XHR 路径。共享的 `backend/media.py` 只负责分段传输；调用方继续执行各自的权限、路径和产物校验和检查，并保留接口原有响应头与 Range 处理规则。测试通过 `tests/compute/support/` 准备环境，不再调用其他测试类的生命周期方法。辅助代码为每个隔离测试环境单独保存登录限流状态，生产限流不变。求解器、引擎版本、证据和旧算法代码均未改变。第二轮已拆分 App/页面和业务接口；第三轮完成 CSS 分区和 Vite 插件提取。

第二轮中，`src/App.tsx` 负责页面选择、导航外壳和全局弹窗；`src/app/pages/` 保存页面展示，`useAppController.tsx` 协调跨页面动作并提供各页面所需的数据与回调。会话/导航 hooks 位于 `app/hooks/`；目录加载、示例评论和上传/视频列表位于 `features/`。视频新增、可见性变更和删除由同一个 reducer 同步更新个人、公开和路线 Beta 列表；历史展示记录从个人视频派生，切换账号时清空状态并取消旧列表请求。示例数据与真实视频保持分离。后端 `auth.py` 提供共享认证，`routes/accounts.py`、`catalog.py`、`videos.py` 分别处理业务接口；端点、权限、CSRF、上传规则和算法逻辑不变。

第三轮中，`src/index.css` 只保留字体、Tailwind 和12个有序样式导入。`src/styles/01–05` 保留基础、字体/动效、工作区、主题与社区控件的原有层级；`06–12` 保留导航/媒体、首页、目录、共享修饰、路线/上传、内页和社区/视口的后续覆盖。编号代表级联顺序，不能按名称重新排序；本轮没有删除看似重复但可能依赖上下文的声明。`src/compute/*.css` 仍由各自组件加载。

`vite.config.ts` 保留构建入口、插件顺序、别名、代理和私有目录访问限制。网站元信息、错误重放、React 热更新回退、Make kit 和链接包 sourcemap 分别位于 `vite/plugins/`；sourcemap 插件显式接收项目根目录，避免移动文件后改变路径解析。没有新增依赖，也没有改动 Figma 配置、业务代码或算法。

<a id="setup"></a>
## 4. 本地配置与启动

所有命令从仓库根目录执行。需要 Node.js 22.12+、运行 API 的 Python、Docker Desktop/Compose 或已有 PostgreSQL，以及 FFmpeg/ffprobe。真实计算还需要固定版本 CIS5810 工程及经过验证的 Python 3.12 环境、模型和证据文件。尚未独立验证从空白机器完整安装科学环境。

### 安装与配置

```sh
npm ci
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
cp .env.example .env
```

仅在新建配置时复制 `.env.example`；已有 `.env` 应保留。设置本地数据库密码，然后配置：

| 变量 | 设置要求 |
| --- | --- |
| `POSTGRES_HOST/PORT/DB/USER/PASSWORD` | API 与 worker 指向同一数据库；Compose 默认主机127.0.0.1、端口5433 |
| `APP_ORIGINS` | 精确浏览器 origin；按下方命令启动需加入 `http://127.0.0.1:5173` |
| `UPLOAD_DIR` | 私有上传目录；默认 `./data/uploads` |
| `COMPUTE_MODE` | `real`；`mock` 仅用于明确标记的模拟开发/测试 |
| `COMPUTE_STORAGE_DIR` | 私有产物目录；默认 `./data/compute`，不能放入 `public/` |
| `BETA_TRANSLATOR_ROOT` | 固定版本 Beta_Translator 本地工程的绝对路径 |
| `BETA_TRANSLATOR_PYTHON` | 可选覆盖；默认使用该工程的 `.venv/bin/python` |
| `COMPUTE_TIMEOUT_SECONDS` | 默认1800；单任务超时，不是延迟承诺 |
| `REGISTRATION_ENABLED` / `COOKIE_SECURE` | 本地注册策略；HTTPS 部署使用安全 Cookie |

`.env.example` 的 origin 列表尚未包含5173；若 Vite 使用其他端口，应按实际地址配置。密码和私有数据不进入 Git。

### 数据库

```sh
docker compose up -d db
backend/.venv/bin/python -m backend.db.manage migrate
backend/.venv/bin/python -m backend.db.manage seed
```

使用已有宿主机 PostgreSQL 时，配置 `POSTGRES_*`，改用 `migrate --direct` / `seed --direct`。已执行迁移不能修改，应新增编号迁移。目录种子和迁移可重复执行。

### 分别开启三个终端

```sh
# API
backend/.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8788
```

```sh
# 预检通过后启动唯一持久 worker
backend/.venv/bin/python -m backend.compute.preflight run
```

```sh
# 前端
npm run dev -- --host 127.0.0.1 --port 5173
```

打开 `http://127.0.0.1:5173`；API 文档为 `http://127.0.0.1:8788/docs`。当前预检同时检查 Trial2 证据和科学环境，并不是完整的新视频模型安装器。API 与 worker 必须使用相同数据库和存储设置。终端已导出的环境变量可能覆盖 `.env`。

使用 `npm run build` 构建；`npm run preview` 预览静态产物，不替代 API/worker 开发环境。停止或重启 Compose 数据库且保留卷，使用 `docker compose stop` / `docker compose start`。

局域网测试时让 Vite 监听 `0.0.0.0`，把精确局域网 origin 加入 `APP_ORIGINS`，API 继续通过同源代理访问。服务主机需持续运行。HTTPS、隧道、实体手机验收和数据库/媒体备份恢复仍需协作验证。

<a id="workflows"></a>
## 5. 产品流程

- **上传：**选择路线 → Add my video → 标题和 Private/Public → 上传。保存与分析提交是两个独立操作；分析失败不会删除视频。刷新可以恢复任务；若提交未到达服务器，可显示 Start analysis。重试创建新 attempt。
- **Community：**已登录用户可浏览公开用户视频。Community Beta 筛选 `share_as_beta=true` 的公开视频；该主动分享允许显示上传者身材作比较。预置 sample 仍是示例，不是用户上传记录。
My Page 内的 My Library 包含 My Skeletons 分类；通知铃铛可打开任务通知。从 Community 提交生成后自动打开对应任务，后台轮询不占用首页布局。

- **个人骨架：**打开真实 Community 视频 → Generate beta → 获取该视频的源分析 → 输入身高臂展 → 提交 → My Library / My skeletons → 通知或已保存结果。请求绑定实际视频与分析版本，不用同路线其他视频替代。目前仅支持已有 Trial2 源分析的诊断生成。
- **新视频核查：**输入准备完成后打开 New video inputs → 查看候选和参考图 → 核查标定 → 保存。输入完成不解锁个人生成。
- **结果：**示例建议单独展示；真实诊断时间点跳转到当前任务视频。个人产物保持私有，访问仍依赖原视频权限。

<a id="api"></a>
## 6. 后端与接口约定

浏览器使用同源 `/api`、会话 Cookie；已认证修改请求附带 `X-CSRF-Token`。包括注册/登录在内的修改请求，其 origin 必须匹配 `APP_ORIGINS`。资源归属来自会话。Cookie 为 HttpOnly；刷新后通过 `/api/auth/me` 恢复 CSRF 状态。

| 接口组 | 路由与用途 |
| --- | --- |
| 账号 | `POST /auth/register`、`/auth/login`、`/auth/logout`；`GET /auth/me`；`PUT /profile` |
| 目录/健康 | `GET /health`、`/gyms`、`/routes`、`/routes/{id}` |
| 上传 | `POST /videos`；`GET /videos`、`/videos/{id}`、`/videos/{id}/content`；`PATCH` / `DELETE /videos/{id}` |
| 上传分析编排 | `GET` / `POST /tasks/upload-analysis/{video_id}`；仅上传者 |
| 任务 | `POST /tasks/analyze`、`/tasks/generate`；`GET /tasks`、`/tasks/{id}`、`/tasks/{id}/result` |
| 重试 | `POST /tasks/{id}/retry`；新 attempt，保留原失败记录 |
| 源引用 | `GET /tasks/source-analysis/{video_id}`；返回可用源 ID/版本和质量，不返回他人的私人任务 |
| 产物 | `GET /tasks/{id}/artifacts/{name}`；共享源预览使用 `/tasks/source-analysis/{video_id}/artifacts/{name}`，限允许的预览类型 |
| 输入核查 | `GET` / `POST /tasks/{id}/input-review`；拥有者专用、标定版本化 |
| 接触核查 | `GET` / `POST /tasks/{id}/contact-review`；GET 可指定 `version`；拥有者专用 |
| 接触计算输入 | `GET /tasks/{id}/contact-review/export?version=...`；必须为已确认版本 |
| 全局几何 | `GET` / `POST /tasks/{id}/world-review`；拥有者专用，GET可指定version |
| 全局计算输入 | `GET /tasks/{id}/world-review/export?version=...`；显式版本，包含未解决状态 |
| 通知 | `GET /notifications`；`PATCH /notifications/{id}/read` |
| 评论 | `GET` / `POST /videos/{id}/comments`（一级评论，分页，含 `total_with_replies`）；`GET /comments/{id}/replies`；`DELETE /comments/{id}`（仅作者）；`PUT` / `DELETE /comments/{id}/like` |
| 视频互动 | `PUT` / `DELETE /videos/{id}/like` 与 `/videos/{id}/save`；`POST /videos/{id}/share`；`GET /videos/{id}/danmaku`；`GET /social/videos?ids=`（最多 100 个视频的计数与本人状态）；`GET /me/saved-videos` |
| 路线与关注 | `GET /me/wanted-routes`；`PUT` / `DELETE /routes/{id}/want`；`PUT` / `DELETE` / `GET /users/{id}/follow`；`GET /me/following`；`GET /users/{id}/profile`（作者主页，仅公开视图） |

以上路由均有 `/api` 前缀。精确请求结构以交互 OpenAPI 为准。计算 [schema 和 fixture](docs/compute/examples/) 保留为机器可读示例；实际模型以 `contracts.py`、`input_schema.py` 为准。在 API 环境使用 `python -m backend.compute.export_examples` 导出示例。

上传默认限制：MP4/MOV、最长90秒、最大200 MiB，使用 ffprobe 验证。multipart 字段包括路线、可见性、可选 Beta 分享标记、标题、描述和视频。私有视频不能分享为 Beta。若 MOV 容器被接受但编码不受浏览器支持，上传环节目前不会自动转码。

资料身高范围100–230 cm，臂展80–260 cm。缺失值可为 null；`PUT /profile` 是完整更新，省略或传 null 会清空对应尺寸。生成需要本人输入或人工校正的目标尺寸。

任务状态为 `queued → running → succeeded / failed`。stage 表示实际步骤，不显示虚构百分比。算法可能以证据不足状态完成。analyze/generate/retry 使用幂等键避免重复接受；同键不同参数返回409。通知与终态结果一起提交。单 worker 锁保护执行；恢复时被中断的 running 任务成为可重试失败。

错误格式为 `{"error":{"message":"..."}}`；任务失败另有结构化 `Task.error`。常见状态码：401登录、403 Origin/CSRF、404不存在或无权、409冲突/过期/未就绪、422参数错误。上传和任务列表使用各自接口的分页参数。

产物私有且进行校验和验证。任务处理和读取时检查源视频可见性/删除状态；源权限撤回后，查看者失去派生产物访问权。撤权不等于完整的磁盘保留/垃圾清理策略。个人任务与通知仅拥有者可见。

<a id="pipeline"></a>
## 7. 视频与骨架流水线

### Trial2 诊断路径

原始录像通过 SHA-256 精确匹配，使用路线 `r1`、引擎 `trial2-source-fit-v5`、标定 `trial2-grid143-v2` 和参考帧450，共976帧、30 fps。同路线的另一上传不能继承这些证据。

已确认输入：横纵相邻孔中心距均为14.3 cm；上方墙相对水平70°，中间/起始墙28°；上下折线和地面图像线已确认。身高约173 cm；臂展176 cm 是允许采用的假设，不是实测值。底部墙面几何、相机假设和地面接触尚未完全确定。

源动作拟合与目标适配保持声明的接触顺序/时序。当前基线失败，因此产物仍是诊断结果。预览后不会自动续跑完整力学或真实技巧比较。

### 独立新视频路径

`video-inputs-v1` 在新的任务目录内准备输入，以宽720、最高15 fps 采样并保留原始帧/时间戳映射，提取 RTMW 全身姿态和 MediaPipe 跟踪，构建墙面/岩点候选、预测接触并发布核查输入。记录源视频、模型和代码哈希，不复用上游 Trial2 输出缓存。

产物包括采样视频、参考图、编号岩点、mask、姿态、身份/对齐数据、帧映射、接触记录/事件、摘要与来源。视频是采样输入录像，**不是生成的骨架**。检测分数和 `accepted_model` 接触不等于人工确认；缺失观测、单应变换和视差仍有局限。

标定编辑器提供墙面与网格的引导式输入，并保留高级 JSON 视图。选择岩点 ID；每面墙填写凸多边形、按墙面网格左上 → 右上 → 右下 → 左下排序的四角、横纵孔间隔数、相对水平角度（未知为 null）及测量说明。点击参考图可读取像素坐标。填写的是孔间隔数，不是孔数量。

保存生成不可变版本，拒绝过期更新、未知岩点、错误参考帧或非法几何。输出为各墙面局部厘米坐标；位于所有面外或多个面重叠区的岩点保持未分配/歧义状态。核查人物后才确认身份；标定 JSON 的 `contact_reviewed` 保持 false，接触确认通过独立版本记录。全局墙面/相机核查现有独立入口，但真实录像尚缺测量数据，且源动作适配未接入；新视频继续保持 `generation_ready=false`。

### 人工接触核查

在 My skeletons 打开已完成的新视频输入任务 → New video inputs → Contact and release review。可载入自动候选，修改四肢、岩点、接触起始帧与释放帧，增加/删除区间，标记 hold、free 或 unknown，并记录观察说明。对照编号岩点图和独立的视频播放器，可跳转到接触与释放位置。自动候选不会自动成为人工确认；编辑后需要重新勾选核查确认，也可先保存草稿。

时间轴为采样后的分析帧，区间采用 `[start_frame, release_frame)`。例如15 fps 时 [3,9) 包含第3–8帧，对应0.2–0.6秒；释放帧可等于总帧数。上游 Beta Translator 的闭区间 `end_frame` 转换为 `release_frame=end_frame+1`，代码中已注明来源。未覆盖区间及不确定的墙面/地面接触保持 unknown；只有观察到离开墙面时才标记 free。不同肢体可同时接触同一岩点，同一肢体的区间不能重叠。岩点必须来自该任务的候选或明确固定的人工岩点版本；可在参考图编辑器中补充漏检岩点。

保存绑定任务、源视频和五个原始产物的 SHA-256，形成独立不可变版本，保存在私有 `COMPUTE_STORAGE_DIR/contact-reviews/{task_id}/`。原始预测、标定和 Trial2 证据均不被覆盖。并发旧版本更新返回409；页面保留未保存编辑，用户可选择重新加载。可查看当前/上一版本，旧版本可以继续按 ID 读取。保存确认仅代表人工审核这些区间，不表示未知区间已解决或几何/力学通过。

后续计算使用 `GET /api/tasks/{id}/contact-review/export?version={完整版本哈希}`，或调用 `contact_review.export(task_id, owner_id, version)`；必须明确指定已确认版本，草稿返回409。导出包含规范化区间、四肢逐帧 hold/free/unknown 状态、岩点 ID、源帧与源时间映射及输入哈希；读取时重新检查拥有者权限、源视频访问和内容完整性。该接口已可供后续模块使用，当前 worker 尚未实现新视频源动作重建，不会因导出而启动适配。

### 全局墙面与相机核查

入口：已完成的新视频输入任务 → Global wall and camera alignment。先保存身份已确认的墙面标定和已确认接触版本，再填写几何 JSON。空白模板保留未知数为 null，不能当作有效标定保存。该步骤使用独立科学进程，不调用 Trial2 源动作诊断或技巧比较。

- **拼接**：厘米、右手坐标系、Y向上。根墙面提供原点和对应局部网格的正交单位 u/v 轴；原点可任意选择，不会由此推断离地高度。每条父/子墙面连接提供两边对应的有序局部折线端点与有符号折角（沿父端点方向按右手规则）。所有面组成连通树，边长差≤0.1 cm，拼接姿态与独立填写的墙面倾角误差≤2°。
- **相机**：需要准确对应采样录像分辨率/裁切的 fx/fy/cx/cy、[k1,k2,p1,p2,k3] 畸变参数与来源；不能直接填原始手机分辨率的内参。每个相机帧至少6个跨折面、分布充分的非共面拟合点及2个不同的独立核查点，均为“墙面局部厘米位置↔像素”对应。PnP只求外参，不猜内参；要求拟合 RMSE≤5 px、核查最大误差≤8 px，且控制点位于相机前方。页面显示参考帧观测/重投影叠图与误差。
- **手持录像**：默认不复用参考相机。每个要对齐的帧需控制点；没有数据的帧保持未对齐，不做相机插值，也不把折墙上的单应变换当作3D运动恢复。仅在明确确认固定拍摄时，才对跟踪状态有效且最大图像位移≤3 px的帧复用参考相机。这是保守筛查，不是独立相机准确性证明。
- **统一输出**：岩点像素去畸变后与其分配墙面求交，得到墙面上的三维锚点；二维人体姿态输出同一世界坐标下的射线原点/方向及原始分数，不伪造深度。未观测身份、低分（<0.3）、无效点或未标定帧保留空值。接触沿用指定人工版本的源帧/时间映射，绑定到对应世界岩点目标；它不是关节真实位置，也未测量岩点凸起厚度。未知身体深度、完整动作和物理可行性仍待后续重建。

保存为独立 `world-reviews/{task_id}/{version}.json`，绑定墙面、接触、输入产物和实现代码哈希；不覆盖原始数据。GET核查支持历史版本；导出必须指定完整版本，重新验证权限及依赖完整性，并包含墙面坐标架、相机外参、每帧相机索引、岩点、姿态射线、接触目标和未对齐帧列表。标定完成不解锁生成，`generation_ready=false`。

**真实数据状态（用户已确认）**：现有录像为手持，未选定验收视频，没有墙面倾角/折线测量，也没有相机内参；只确认14.3 cm孔距。代码与合成验收已完成，真实录像的全局三维标定未完成。后续需要选定一条录像，测量墙面折线对应孔位和倾角，取得匹配录像尺寸/焦距/裁切的相机标定，并提供各目标帧控制点。仅靠孔距不足以验证这套实现中的相机与墙面几何。不会把此前 Trial2 的28°/70°套到新视频。

<a id="data"></a>
## 8. 数据与资源

Movement Fishtown 保留场馆 ID `gym-a`。图片导入加入 IMG_7518–IMG_7544 的73个条目，加上 r1 共74个目录条目。Long Reach（`r2`）从浏览中移除；迁移009在已有上传引用时通过归档路线保留这些上传。不同照片可能对应同一条真实路线；导入没有对真实路线去重。

- 目录：`src/data/movementRoutes.json`；导入迁移008、移除迁移009。
- 图片：`public/media/movement-facetime/`。历史目录拼写为兼容保留；界面场馆名为 Movement Fishtown。
- 原始媒体来源：[MEDIA-SOURCES.txt](MEDIA-SOURCES.txt)。
- 高亮图片是视觉编辑，不是精确分割 mask 或已标定算法输入。未提供等级为 Unrated；IMG_7536 的白色路线和 IMG_7539 的小青色岩点需核查。
- `scripts/import-route-photos.py` 从独立的全质量交付文件夹准备资源，不是启动步骤。Gym B 尚无提供的路线录像。

私有上传使用 `UPLOAD_DIR`；任务工作文件、发布产物和不可变核查记录使用 `COMPUTE_STORAGE_DIR`。本地测试报告和备用包在被忽略的 `backend/compute/runs/` 下，属于本机证据，不保证全新 clone 中存在。数据库、上传文件和计算存储需要分别纳入备份。

### 备份与恢复

数据库、上传视频和计算产物必须一起备份，否则恢复后记录和文件会对不上。在仓库根目录、使用 API 环境运行（默认通过 Docker；与 `manage` 一样，加 `--direct` 改用本机 PostgreSQL 工具）：

```sh
python3 -m backend.db.backup backup                  # 写入 backups/<UTC 时间>/
python3 -m backend.db.backup verify backups/<目录>    # 恢复到临时库并逐表核对
python3 -m backend.db.backup restore backups/<目录> --yes
```

备份包含 `db.dump`、`uploads.tar.gz`、`compute.tar.gz` 和 `manifest.json`（各表行数、数据库引用的全部上传与发布产物路径、每个文件的 SHA-256）。**每次备份后都运行 `verify`**：它恢复到 `<POSTGRES_DB>_restore_check`，逐表核对行数并检查每个被引用的文件都在归档中，然后删除临时库；文件损坏或缺少视频/产物都会报错并以非零状态退出。`restore` 需要 `--yes`，运行前先停止 API 和 worker；当前上传和计算目录会改名为 `<目录>.before-restore-<时间>`，不会被删除。`backups/` 已加入 `.gitignore`：其中有用户数据和密码哈希，不要提交，应复制到另一块磁盘或另一台机器保存。

<a id="results"></a>
## 9. 结果与已知限制

| 结果类别 | 含义 |
| --- | --- |
| Example | 界面说明或 mock 内容，不是当前上传的观测 |
| Diagnostic | 真实模型误差或证据不足，时间点绑定来源 |
| Technique result | 仅在非 mock 证据、基线通过、候选已比较且完成 `full_model` 检查时展示；当前未运行此类比较 |

最新 v5 几何证据：

| 指标 | 源动作，173/176 cm | 目标，170/175 cm |
| --- | ---: | ---: |
| 已知墙面最大接触误差 | 16.74 cm | 16.66 cm |
| 超过5 cm诊断阈值的帧数 | 6 | 4 |
| 速率违规 | 0 | 0 |
| 已知墙面关节中心穿墙超过1 cm的帧数 | 0 | 0 |
| 总体基线 | failed | failed |

剩余源动作片段：左手 H137，第175–178帧（5.833–5.933秒）；右脚 H149 → H163，第298–299帧（9.933–9.967秒）。修改证据前应核查释放/换点时刻和实际脚部接触模式。已确认的墙角和折线无需重复确认。地面保留78个未验证候选样本；H109右脚第239–253帧继续标记证据不足。

关节中心检查不能证明完整身体碰撞、平衡、接触力或物理可行性。新视频全局三维重建、可靠自动人体测量、完整力学和技巧优化尚未完成。Trial1 的二维技巧约束不能直接当作 Trial2 三维模型已验证的约束。

<a id="testing"></a>
## 10. 测试与性能

### 可复现检查

```sh
npx tsc --noEmit
npm run build
node --test tests/frontend/*.test.ts tests/build/*.test.ts
backend/.venv/bin/pip install -r backend/requirements-test.txt
backend/.venv/bin/python -m unittest discover -s tests/compute -v
```

数据库测试需通过 `POSTGRES_*` 明确配置可丢弃的测试数据库，不得指向业务数据，然后启用 `BETALAB_TEST_DB=1`。测试创建隔离 schema；部分 worker 锁作用于整个数据库，因此 worker/浏览器专项应顺序运行。

浏览器测试还需安装 `backend/requirements-browser.txt`，并执行 `backend/.venv/bin/python -m playwright install chromium`。科学测试使用已验证的 Beta Translator Python 环境。专项开关示例：

浏览器测试默认从 PATH 查找 Node；若使用其他安装位置，设置 `BETALAB_NODE` 为可执行文件的绝对路径。测试不再依赖个人机器上的固定路径。

| 测试文件 | 额外开关 |
| --- | --- |
| `test_community_browser.py` | `BETALAB_COMMUNITY_TEST=1` |
| `test_upload_browser.py` | `BETALAB_UPLOAD_BROWSER_TEST=1` |
| `test_result_browser.py` | `BETALAB_RESULT_BROWSER_TEST=1` |
| `test_input_browser.py` | `BETALAB_INPUT_BROWSER=1` |
| `test_world_review.py` | `BETALAB_WORLD_TEST=1` |
| `test_world_browser.py` | `BETALAB_WORLD_BROWSER=1` |
| `test_world_geometry.py` | 科学 Python（OpenCV/NumPy） |
| `test_review_client_browser.py` | `BETALAB_REVIEW_CLIENT_TEST=1` |
| `test_video_management_browser.py` | `BETALAB_VIDEO_BROWSER_TEST=1` |
| `test_new_inputs.py` | `BETALAB_TEST_INPUTS=1` |
| `test_phase5_rehearsal.py` | `BETALAB_REHEARSAL_TEST=1` |
| `test_social_browser.py` | `BETALAB_SOCIAL_BROWSER=1`（无需录像；覆盖触屏手势、示例视频、失败状态与切换账号；可用 `BETALAB_CHROME` 指定 Chrome） |

这些专项还依赖其说明中的本地录像/报告与源环境；全新 clone 运行前需检查 setup 条件。部分浏览器测试明确导入已核验预生成产物，不重新运行源拟合。

### 最新回归与历史算法证据

全局标定验收通过41项普通后端测试（发现74项，33项按环境跳过）、2项单独启用的科学接口测试、4项已知真值几何测试、15项前端/构建测试和6项浏览器用例（另跳过3项），类型检查和生产构建通过。覆盖折线拼接、相机/岩点真值、世界姿态射线与接触锚点、手持缺帧、固定相机移动拒绝、非法标定、版本/旧更新冲突、权限/完整性、UI错误、重投影叠图和刷新。几何与界面成功用例使用明确标记的合成测量，真实手持标定仍因缺数据而未完成。已有计算文件除API路由注册外内容完全未变，未执行Trial2重拟合或技巧比较。证据：`backend/compute/runs/world-alignment-acceptance/`。

人工接触核查验收通过41项后端测试（发现67项，26项按环境跳过）、15项前端/构建测试、5项已启用浏览器用例（另跳过3项），以及类型检查和生产构建。6项接触专项测试覆盖时间边界、重叠/岩点校验、未知区间、版本、草稿禁止导出、并发冲突、源数据/版本篡改与权限。输入核查浏览器用例修改四肢、岩点和接触/释放帧，验证保存、跳转、导出及刷新恢复，并检查手机/桌面视口。测试中的人工修正为合成操作，不是已核实的攀爬证据。现有 Trial2/科学计算模块未变，未重跑源动作拟合或真实技巧比较。证据：`backend/compute/runs/contact-review-acceptance/`。

第三轮结构整理通过15项前端/构建测试（原有9项前端用例、5项插件契约和1项真实开发服务器测试）、5项已启用浏览器用例，以及35项后端测试（发现61项，26项按环境跳过）；浏览器发现阶段另跳过3项需额外启用的用例。类型检查、生产构建与 diff 检查通过。生成的8个 JS/CSS/HTML/robots 文件与整理前逐字节一致；拼接后的 CSS 声明及顺序完全一致。其余88个已快照源文件，包括计算和旧实验代码，均未改变。插件回归覆盖元信息、错误重放、热更新回退、Make kit、链接包 sourcemap、API 代理及私有文件访问限制。未重跑源动作拟合或技巧比较。本地证据：`backend/compute/runs/refactor-round3/`。

第二轮结构整理回归通过35项 API/契约/运行测试（发现61项，26项按环境跳过）、9项前端测试和6项单独启用的浏览器用例：上传/重试、结果播放、输入核查、计算联调、视频可见性/删除/刷新，以及 Community 重试/账号隔离。类型检查和生产构建通过。拆分前后的 OpenAPI 完全一致；快照中的31个计算 Python 文件和主 CSS 文件内容完全未变。未重跑源动作拟合或技巧比较。本地记录：`backend/compute/runs/refactor-round2/`。

第一轮去重回归通过33项 API/契约/运行测试（发现58项，25项按环境跳过）、7项前端测试、4项单独启用的浏览器用例（上传/重试、结果播放、输入核查、计算联调页登录/上传/通知/播放），以及科学环境中的1项标定/来源测试。类型检查、生产构建和 diff 空白检查通过。媒体测试覆盖逐字节比对的部分/开放结尾/后缀读取、非法 Range、接口兼容差异、私有访问和完整性。快照中的39个计算/旧实验模块（媒体模块除外）内容完全未变。未重跑源动作拟合或技巧比较。本地记录：`backend/compute/runs/refactor-round1/`。

普通 API 测试不要启用科学计算前置条件；科学测试使用 Beta Translator 的 Python 环境。浏览器专项需要源工程，但 API 解释器不必加载科学依赖。共享测试辅助代码按 schema 隔离登录限流状态，避免无关测试耗尽同一份内存限额。

此前的新输入更新记录为发现56项测试：32项通过、24项按环境跳过。另行执行通过了2项真实新输入 worker 测试、1项科学平面标定测试、输入核查和上传浏览器专项，以及4项前端分类测试。类型检查和生产构建通过。跳过不等于通过；这些是历史执行证据，不表示本次重构时重新运行了算法。

| 实测 | 输入 | 耗时与范围 |
| --- | --- | --- |
| v5源分析 | Trial2，32.533秒，976帧 | 分析371.44秒 |
| v5目标 | 同一源，170/175 cm | 生成93.93秒 |
| 新视频提取 | Trial3原录像第5秒起截取4秒；720×1280、60个分析帧 | 首次直接运行34.07秒；队列验收科学处理约22–24秒 |

新视频片段得到50个岩点候选、240条四肢观测；不代表完整 Trial3 验收。记录中的本机为 Apple M5、16 GiB内存。CPU竞争、文件/模型缓存及排队会影响耗时。尚未确定手机延迟或稳定预览时间目标。

本地证据路径：`backend/compute/runs/phase3-real-62fc330f/validation.json`，以及同一 runs 目录下的 `new-inputs-acceptance/validation.json`、`new-inputs-suite.log`、`community-v5-*/`。Chromium 视口测试不等于实体 iOS/Safari 或多台手机验收。

<a id="demo"></a>
## 11. 展示与故障处理

逐步演示脚本、预设账号以及示例与用户内容的区分见 `docs/DEMO_SCRIPT.md`。演示账号从被 Git 忽略的 `demo/accounts.local.json` 创建：`backend/.venv/bin/python -m backend.db.demo_accounts demo/accounts.local.json [--upload]`，密码不进仓库。

启动本地服务并登录，使用真实上传视频展示权限。Trial2 使用未改动的原录像上传至 r1，运行分析，再用另一账号进行个人生成。播放和诊断跳转时同时展示基线标签。新视频展示提取输入与标定核查，不宣称完整适配已完成。

现有离线 v5 备用页为 `backend/compute/runs/standby-v5-community/index.html`，同级 ZIP 为 `standby-v5-community.zip`。它包含真实预生成的源/目标诊断结果，基线失败，不是现场任务。校验命令：

```sh
backend/.venv/bin/python -m backend.compute.standby verify backend/compute/runs/standby-v5-community
```

ZIP SHA-256：`64dcfe608ee71f8e92457991708e17ce065c94cb380ea072ef913337f654de67`。它被 Git 忽略，换机器需单独复制。这是结果备用包，不是完整数据库/应用备份。旧 v2 包仅作历史保留。

| 现象 | 处理 |
| --- | --- |
| 登录或修改请求被拒绝 | 核对准确 origin、会话和 CSRF；配置改变后重启 API |
| 队列不推进 | 检查数据库/存储设置和唯一 worker；第二个 worker 按设计被拒绝 |
| worker 中断 | 使用同一配置重启；显式重试失败 attempt |
| 源或版本不匹配 | 使用正确录像和当前分析，不能重新标记旧文件冒充新结果 |
| 输入提取失败 | 查看私有 `work/<task-id>/worker.log`；已保存上传仍可使用 |
| 标定冲突 | 先重新加载保存版本；填写实测几何，不能选取仅为让检查通过的猜测值 |
| 产物访问被拒绝 | 检查当前源可见性和账号，不能通过静态链接绕过保护 |
| 基线失败 | 展示诊断并保留失败状态，不能宣称技巧可行 |

<a id="next"></a>
## 12. 分工与下一步

A 负责账号/视频基础、存储、部署和备份恢复；B 负责目录/社区体验、持久社交互动与统一视觉；C 负责算法适配、任务执行、结果契约和通知服务。C 还已接通主页面计算流程，因此旧计划中“此整合全部待 B 完成”的描述已被更新。

建议 C 按以下顺序推进：

1. 人工接触修正闭环已完成；接下来用真实录像逐段核查候选，并在未来重建任务中绑定明确的接触版本。
2. 全局标定代码已通过已知真值合成验收；收集真实手持视频墙面/相机测量与逐帧控制点，完成真实数据验收。自动相机自标定/SfM 尚未实现。
3. 接入新视频源动作重建，再接目标身材适配，用一条非 Trial2 完整录像验收。
4. 恢复源动作调查后，解决 Trial2 剩余两个接触片段，不放宽阈值或删除失败样本。
5. 基线有效后实现完整模型检查及有限适用技巧比较，提供可复现评分与解释。首版固定接触顺序/时序，最多比较3个候选；相近时保留基线。
6. 测量完整录像耗时、测试真实设备、与 B 改善开发用标定编辑器，并在算法改变后更新备用包和交接证据。

按当前项目决定，源动作诊断和真实技巧比较继续暂缓。社交持久化、部署和设备演练需要 A/B 协作。邮件找回密码、系统级推送、用户创建场馆/路线、云端扩容和自动备份工具不属于已完成原型。

### C 本轮交付与验收 — 2026-11-21

基于 main `2185169`。没有改动或重跑 Trial2 源动作拟合，没有改变失败基线，也没有运行真实技巧比较。实现完成与最终验收分开记录，详见 `docs/DEMO_IMPLEMENTATION_PLAN.md`。

| 项目 | 本轮已交付 | 仍需验收的边界 |
| --- | --- | --- |
| 1. 状态核对 | 按代码与证据修正 C 任务表 | 实现勾选不代表全组最终签收 |
| 2. 新版界面联调 | My Page／My Skeletons、通知跳转、刷新恢复；修复 Skeletons 混入 Want to Try 内容 | 新版完整实时 Trial2 源→目标计算仍暂停；流程用明确标识的模拟计算，播放用不可变历史真实结果 |
| 3. 双账号权限 | API 权限矩阵及浏览器源视频改私有后撤权 | 真实跨设备演练 |
| 4. 运行恢复 | 幂等、单 worker、进程中断恢复、重启持久化、结果与通知原子性测试 | 最终 3–5 人现场演练 |
| 5. 进度与错误 | 真实阶段、已耗时、最后更新时间、排队/处理分段及重试指引 | 不显示虚构百分比或 ETA |
| 6. 耗时 | 完整 Trial3 输入提取 73.94 秒和 71.95 秒；251 帧、15 fps、720×1280 | 暂定本录像/本机输入准备目标≤120秒，不是通用骨架预览承诺；尚无受控冷启动/实机性能结论 |
| 7. 完整视频输入核查 | 结构审计、全片概览、候选核查，独立验收库中保存接触草稿 | 精确接触/释放边界未全部确认；草稿不是动作真值 |
| 8. 岩点修正 | 在参考图补漏检岩点或改中心点；不可变版本、边界、来源和权限检查 | 不猜测掩膜和岩点大小，每项仍需核查 |
| 9. 引导式标定 | 墙面边界/网格点击、撤销点、孔距区间数、未知角度、身份和备注；保留高级 JSON | 全局折线拼接/相机数值仍使用高级编辑器；真实测量验收待完成 |
| 10. 固定重建输入 | 接触/标定岩点版本一致性校验、不可变重建输入包 | 不等同于重建 worker、深度求解或生成骨架 |
| 11. 展示准备 | 本机 preflight、历史 v5 校验、独立库/上传/产物备份与临时库恢复、交接步骤 | 确认展示机器、真实手机及 3–5 位参与者 |

**新输入流程：**已完成的新视频任务 → Correct or add holds → 保存 → 重新核查接触，只确认有证据的区间 → 保存墙面标定 → 全局对齐。新增岩点 ID 以 `manual-` 开头，坐标基于采样参考图；中心修正不推断分割掩膜。自动产物不被覆盖。接触与标定固定 `hold_review_version`，两者一致才允许全局对齐；历史导出仍可读取。新岩点版本不会静默修改旧接触或几何。岩点输入变化时保留未保存的接触编辑，需明确重新加载才采用新版本。

新增 API 均需登录且仅限拥有者：`GET/POST /api/tasks/{id}/hold-review`；`POST /api/tasks/{id}/reconstruction-inputs`（`world_version` 及可选、带来源的 `source_body`）；`GET /api/tasks/{id}/reconstruction-inputs/{version}`。输入包固定视频、标定、接触、全局版本、代码/输入哈希与覆盖范围，始终保留 `generation_ready=false`；新视频深度重建/适配尚未实现。重启 API/worker 前先应用 **015_compute_timing.sql**。旧任务的 `started_at`/`finished_at` 保持空值，不伪造排队与处理时间。

**Trial3 实际发现：**开头左脚 H056 候选覆盖从地面移到墙面的过程，不能整段确认为同一岩点接触。已在草稿中改为 unknown；其他候选尚未确认，包括约 10.8–13.7 秒模型接受率偏低的右手事件。两次提取均得到 57 个岩点和 1,004 条四肢观测；模型接受率与对齐标记不代表独立精度验证。没有套用 Trial2 角度。2026-11-19 实测的 Trial2 源/目标总耗时仍作为历史记录：353.62 秒和 88.22 秒，均为诊断结果；本轮未重新测量。

**验证：**普通后端 84 项通过（发现 120 项、按环境跳过 36 项）；另启用科学 API 3 项、科学几何 5 项、前端/构建 16 项、浏览器 4 项均通过；TypeScript 和生产构建通过。浏览器覆盖新版双账号模拟流程与撤权、不可变历史真实结果播放、新岩点/接触编辑及合成全局标定。历史结果夹具只允许已知提示文案和渲染文件的版本差异，核对其 `73a8daa` 原始哈希，不改写来源、不授权真实求解复用。备份恢复到独立临时库验证：18 张表、1 个原视频和 13 个计算产物匹配；没有覆盖用户的实时预览库。

证据保留在 Git 忽略的 `backend/compute/runs/c-readiness/`：`acceptance-summary.json`、`full-trial3/audit.json`、`trial3-review-receipt.json`、测试日志、`preview-preflight.json`、备份和备用包校验。测试凭据、原视频和产物只留本地。只读审计命令：`python -m backend.compute.input_audit <提取产物目录>`。原 v5 包未改动，已校验且仍明确标为历史预生成结果；不能为匹配最新代码哈希而将它重新标成新计算结果。


### 11月22日：放大对比播放

诊断预览改为骨架在上、原视频在下；各画面为960×540，合成为960×1180的同步视频。只绘制有效墙面接触记录涉及的岩点；这是显示筛选，不代表新增接触真值验证。已有本地结果使用单独校验哈希的 `display_video` / `display_poster` / `display_provenance` 展示产物，保留原视频和科学计算来源记录。不重跑源动作拟合、诊断或技巧比较。新增展示回归覆盖上下顺序、尺寸、帧数及未使用/未获支持岩点的隐藏。

骨架画面使用固定、等比例的聚焦范围，覆盖整段投影动作与有效接触岩点，四周各留12%余量，避免动态缩放抖动。原视频不裁剪，时间轴和诊断结论保持不变。

### 11月23日：三个案例的本地展示账号

`betalab_showcase` 账号已保存三个**预生成演示**。Movement Fishtown 下新增两条演示路线，明确标注 `Demo case · venue unverified`；目录归类不代表已确认拍摄岩馆。原视频在本地 Community 公开，账号自己的已保存列表保持私有。密码放在被 Git 忽略的 `demo/showcase.local.json`，不会提交，也禁止通过 Vite 直接下载。

| 案例 | 已准备结果 | 范围 |
| --- | --- | --- |
| Trial1 · Demo Study | 417帧／13.90秒，模型身高180cm | 已有 refined-support 二维轨迹；原攀爬者尺寸未知，未单独设定臂展 |
| Corner Study · Demo | 976帧／32.53秒，界面显示原结果目标尺寸 | 历史 Trial2 聚焦诊断；基线失败结论保持不变 |
| Trial3 · Demo Study | 503帧／16.77秒，模型身高180cm | 已有 full-sequence 二维轨迹；原攀爬者尺寸未知，未单独设定臂展 |

操作路径：Community → **Generate beta／Use skeleton** → **Prepared skeleton demo** → **Save demo to My Skeletons** → My Page → My Skeletons → Saved demonstrations。重复保存不会重复添加，也不会排队计算或修改演示的身体尺寸。保留诊断和限制；上方为聚焦的二维骨架／接触示意，下方为完整原视频，竖屏录像留边、不拉伸。墙面缩略图来自各自原录像，不是合成标定几何。

迁移 `016_demo_previews.sql` 将预生成演示、个人保存与计算任务分开。`/api/demo-previews` 接口在读取元数据、已保存列表、墙图及视频分段时检查登录与原视频可见性，并校验媒体哈希。原视频改私有或删除后，其他账号失去访问权限。演示源拒绝提交分析；普通上传和已有 Trial2 流程保持原行为。

**算法接入边界：** `backend.compute.demo_algorithm` 是对固定版本 CIS5810 `trial1_refinement_pipeline` 和 `full_sequence_pipeline` 的本地离线适配入口，尚不是新增网页计算 worker。两个输入加载器均已通过本地核查，没有执行求解。默认只检查输入；执行还必须同时指定 `--execute` 和 `BETALAB_DEMO_COMPUTE_ENABLED=1`，产物写到上游独立运行目录，不调用 Trial2 或技巧比较。这两个入口支持身高与模板比例，不支持独立输入臂展；网页实时生成继续关闭，待 worker 接入及验证。

```sh
# 使用科学计算 Python；以下仅核查输入，不运行求解器。
"$BETA_TRANSLATOR_ROOT/.venv/bin/python" -m backend.compute.demo_algorithm trial1 --source "$BETA_TRANSLATOR_ROOT"
"$BETA_TRANSLATOR_ROOT/.venv/bin/python" -m backend.compute.demo_algorithm trial3 --source "$BETA_TRANSLATOR_ROOT"
# 启动／重启 API 前应用迁移。
backend/.venv/bin/python -m backend.db.manage migrate --direct
# 准备本地产物并填写被忽略的配置后：
backend/.venv/bin/python -m backend.db.demo_catalog demo/showcase.local.json
```

`demo/showcase.example.json` 不含真实密码；复制成本地配置后替换密码与 `<BETA_TRANSLATOR_ROOT>` 占位符。`backend.compute.demo_render SOURCE RUN DESTINATION` 校验原视频、轨迹及已生成视频哈希，再从已有关节坐标独立导出展示，不重做拟合。当前源结果目录是 `outputs/trial1/refined_support/target_180cm_f1456408fd1d` 和 `outputs/trial3/full_sequence/target_180cm_787124fd4c70`。保留 summary、展示来源和产物哈希；渲染必须使用新目录。Corner Study 导入保留历史结果来源。重复 seed 复用原视频和保存项，不重置密码。视频与产物均在忽略目录 `data/uploads/`、`data/compute/`；此次不部署公开后端。

验证：普通后端88项通过（本次发现125项，37项按环境跳过）；新增4项覆盖保存、隔离／撤权、分段／完整性／CSRF及算法默认关闭。另行运行的本地浏览器演示测试通过 Community → 保存 → 刷新重开、三个视频及两张墙图接口检查；渲染回归、16项前端／构建、TypeScript和生产构建通过。浏览器测试需 `BETALAB_DEMO_BROWSER=1`；截图在 `backend/compute/runs/showcase-check/`。输入验证日志明确 `algorithm_run=false`，不能当作拟合成功。

<a id="history"></a>
## 13. 引用与版本历史

算法来源：CIS5810 **Beta_Translator**，commit `ff85726da2fbbd2616c409b01d6c03833ab62ce9`。代码中的引用保留。涉及 `trials`、`trial2_scene3d`、`body_regions`、`body_legs`、notebook第8D节 / `trial1_technique_pipeline`，以及新视频 `trial_pipeline` / `wholebody_pose` 入口。借鉴思路与新编写的 BetaLab 校验/编排分别说明；本次文档整理没有修改原工程。

原始 Trial2 视频 SHA-256：`9964d27ca051953d77cf10ee94a1772bd73e30d7e23fa09a54983c3630e8a068`。版本、哈希和实际置信度应随产物记录，不能只依靠展示名称。

| 历史阶段 | 当前解读 |
| --- | --- |
| 纯前端 / local-server 实验 | 属于历史；仅会话状态的描述及快速/详细耗时不代表当前认证服务 |
| A 的基础和 Yiru 工程日志 | 保留账号、目录、私有上传和分享决策；后续任务实现替代了旧“任务待完成”描述 |
| B 的 Sonia Implementation Log | 汇总持久化社交、作者主页、手势、Demo 准备、PR 合并验证及剩余联调边界；见 `docs/SONIA_IMPLEMENTATION_LOG.md` |
| C 阶段1–5 | 契约 → 持久化 → 真实产物 → 诊断 → 运行演练；阶段完成不等于算法可行 |
| v3/v4源动作研究 | 历史几何假设与结果，不作为当前墙面测量或性能 |
| v5几何修复 | 已确认墙角/边界，源/目标拟合改善；基线仍失败 |
| 后续产品整合 | Community生成、上传/重试、结果分类、独立新视频输入已接通 |
| 文档统一 | 两种语言同步维护，原文归档；代码、算法和产物路径未改变 |
| 第一轮基础去重 | 共享前端客户端/类型、媒体传输和独立测试辅助代码；算法行为与来源指纹保留 |
| 第二轮结构整理 | 拆分页面与功能 hooks、统一视频状态更新、拆分后端认证/目录/视频模块；保留接口与算法逻辑 |
| 第三轮结构整理 | 按原始级联顺序拆分 CSS，提取5个 Vite 插件；生产产物保持逐字节一致 |
| 人工接触核查 | 独立不可变人工修正版本与逐帧导出；新视频源动作重建仍待接入 |
| 全局几何核查 | 有测量输入的拼接/相机流程与世界坐标导出；合成验收通过，真实手持数据待补 |

本地（Git 忽略，不推送）的 `docs/archive/documentation-2026-11-19.zip` 归档包包含此前全部23份文档：README.txt、实施计划、Yiru日志、backend/local-server说明及15份compute文档。ZIP内的 `MANIFEST.json` 记录原始路径和逐文件 SHA-256。归档包 SHA-256：`1288612b30634c28fe4189432c341cd8e97dd16712a9cb6f8e265455cc4b469a`。查看历史时解压至独立目录，避免覆盖本手册。原文和作者记录保留；历史描述不作为当前操作指引。

两种语言应同时维护。操作说明集中在这里，schema 留在现有机器可读目录，详细运行证据保存在私有/本地产物存储中。后续更新不再为每个阶段另建 README。
