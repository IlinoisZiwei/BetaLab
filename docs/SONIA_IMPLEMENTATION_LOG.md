# Sonia Implementation Log

记录 Sonia 在 BetaLab 中负责的 B 侧实现、验证、合并和后续交接。本日志把此前散落在 `DEMO_IMPLEMENTATION_PLAN.md`、`SOCIAL_API.md`、`DEMO_SCRIPT.md`、README 以及 Git/PR 历史中的记录合并为一份；原文继续保留，团队总任务状态仍以实施计划为准。

最后更新：2026-11-20  
当前代码基线：`main` @ `026b6ad`  
相关交付：PR #1 `feat/community-social`、PR #2 `feat/b-round3`

## 1. 负责范围

Sonia 主要负责 B 侧的场馆／路线与 Community 体验、持久化社交互动、作者主页、手机手势、展示准备及部分运维验证。

边界如下：

- A 负责账号、资料、My Page／Calendar、上传与视频权限基础；Sonia 使用其鉴权、公开资料与视频权限接口。
- C 负责任务队列、算法 worker、真实 suggestions／生成结果和通知后端；Sonia 不把模拟结果或仅有界面当作真实算法闭环。
- Sonia 实现过备份／恢复工具并完成验证，但任务编号 A5.2 的最终复核仍归 A。
- 本日志只记录 Sonia 实际完成或参与合并验证的内容，不把团队基础提交 `cad3406` 中其他成员的实现算作 Sonia 的独立提交。

## 2. 已合并实现

### 2.1 持久化社交后端

提交：`aad36be`、`b37c4a8`、`566e34e`

- 新增社交迁移 `012_social_interactions.sql`、`013_follows.sql`、`014_social_sample_videos.sql`。
- 实现评论列表、发布、本人删除、一层回复和评论点赞。
- 实现视频点赞、收藏、分享计数、带时间点的 live comments（danmaku）和 Want to Try 路线。
- 实现 Follow／Unfollow；禁止关注自己，重复操作保持幂等，关注不会绕过视频可见性。
- 将预置 sample 视频登记为明确的公开示例，使其可使用评论、点赞、收藏和分享功能，同时继续与真实用户上传区分。
- 社交读取和写入跟随视频当前权限：他人私有视频返回 404；公开视频改回私有后撤回他人访问。
- 非法 ID、CSRF、分页、资源归属和删除权限有后端检查。

主要文件：

- `backend/routes/social.py`
- `backend/db/migrations/012_social_interactions.sql`
- `backend/db/migrations/013_follows.sql`
- `backend/db/migrations/014_social_sample_videos.sql`
- `tests/compute/test_social.py`

### 2.2 Community 前端与作者主页

提交：`140559a`、`566e34e`

- 把评论、回复、点赞、收藏、分享、Want to Try、Follow 和 live comments 接入重组后的 React 前端。
- Community 支持分页加载、加载中／空／失败状态和重试；从全屏详情返回时保留已加载页面。
- 发布评论失败时保留草稿；切换账号时清理上一账号的社交状态，避免串号。
- 点击作者头像／名字或在视频上右滑进入作者主页；电脑端支持对应拖动操作。
- 作者主页显示公开身份、关注数与授权公开视频；合并 A 的改动后遵守 Private 账号和 Library 可见性设置。
- 作者页与全屏视频页的 Follow 状态同步；左滑返回和上下切换视频继续可用。
- 预置 sample 与真实上传在界面中保持来源标识。

主要文件：

- `src/features/community/CommentSection.tsx`
- `src/features/community/Danmaku.tsx`
- `src/features/community/AuthorPage.tsx`
- `src/features/community/social.ts`
- `src/features/community/useComments.tsx`
- `src/features/community/useSocial.ts`
- `src/features/community/useRightSwipe.ts`
- `src/app/pages/CommunityPage.tsx`
- `src/app/pages/CommunityVideoPage.tsx`
- `src/styles/13-social.css`

### 2.3 手机手势与浏览器回归

提交：`3b545ec`、`41cb27c`

- 修复移动浏览器横向手势与应用内导航冲突，使手势在应用边界内处理。
- 增加触屏事件检查，覆盖上下切视频、右滑作者主页、左滑返回和评论面板内滑动。
- 增加可见性矩阵，覆盖本人／他人／未登录与 Private／Public／Public+Beta 的组合。
- 增加切换账号、请求失败、重试、草稿保留以及社交状态不串号的检查。

主要文件：

- `src/app/hooks/useNavigation.ts`
- `tests/compute/test_social_browser.py`
- `tests/compute/test_visibility_matrix.py`

这些是自动化浏览器与权限检查，不等同于真实 iPhone／Android 和跨设备验收。

### 2.4 备份与恢复验证

提交：`7fcdb09`

- 实现 `python3 -m backend.db.backup backup|verify|restore [--direct]`。
- 备份范围包含 PostgreSQL、上传目录和计算产物目录。
- `verify` 会恢复到临时数据库、逐表核对，并检查数据库引用的上传文件与计算产物是否存在且一致。
- 演示数据中验证过删除评论、点赞和产物文件后的恢复；损坏文件和缺失产物会明确失败。

主要文件：`backend/db/backup.py`。

此实现已随 PR #1 合并，但 A5.2 仍需由 A 或非作者按文档独立复现后最终勾选。

### 2.5 Demo 账号与展示脚本

提交：`b3cfeb0`

- 新增 `backend/db/demo_accounts.py`，从 Git 忽略的 `demo/accounts.local.json` 创建或更新演示账号。
- 支持注册关闭时直接准备账号，并可用 `--upload` 通过 API 上传演示视频。
- 脚本可重复执行、不打印密码，并拒绝模板中的占位密码。
- 仓库只提供 `demo/accounts.example.json`；真实密码、token 和本地账号文件不进入 Git。
- 新增 `docs/DEMO_SCRIPT.md`，包含 12 步展示流程、设备分工、sample 与用户内容的区别以及失败时的备用方案。

本地已检查创建账号、重复执行跳过、重置密码后登录和占位密码拒绝。

### 2.6 文档与界面文案

提交：`916aead`、`9d0df39`、`336628e`、`00765ac`

- 建立并维护 `docs/SOCIAL_API.md`，记录社交接口、分页、权限、错误结构和 N1.2 私有账号提案。
- 同步 README 中英版本、备份恢复说明、实施计划的 B 侧状态和 Demo 使用方式。
- 将应用中面向用户的播放／审核提示统一为英文。
- 修正 Social API 文档中的错误响应结构，更新 Round 3 的验收边界。

## 3. PR 与合并时间线

### 2026-11-19：PR #1

PR #1 将持久化社交、Community 前端、Follow、作者主页、示例视频社交化、备份工具和接口文档合并到 `main`，合并提交为 `375277a`。

与 A 的 My Page／隐私实现合并时保留双方历史，并让作者主页遵守 A 的 Private 账号和 Library 可见性规则。实施计划记录的当次合并回归结果为：34 项后端、10 项前端、生产构建和 TypeScript 均通过。该结果是当次历史记录，不代表 2026-11-20 再次完整运行同一套环境。

### 2026-11-19：PR #2

PR #2 增加移动端手势修复、可见性矩阵、手机浏览器检查、Demo 账号和演示脚本。合并前把最新 `main` 合入功能分支，在 `docs/DEMO_IMPLEMENTATION_PLAN.md` 解决双方都修改同一任务状态造成的冲突；保留 A 的状态更新和 B 的 Round 3 证据，并修复表格列数与过时的 PR #1 描述。

冲突解决提交为 `fbc5b4c`，PR #2 合并提交为 `026b6ad`。GitHub Pages 部署成功。

### 2026-11-20：合并后复查

对 `main` @ `026b6ad` 的复查结果：

- `npx tsc --noEmit`：通过。
- `npm run build`：通过。
- Python `unittest discover`：发现 109 项；17 项通过，92 项因数据库、浏览器或科学环境为 opt-in 而跳过。
- Node 测试：12 项通过；另 2 项受当前环境限制，分别为 sandbox 不允许监听端口，以及 Node 26 strip-only 模式不支持 TypeScript parameter property。
- GitHub Pages workflow：成功。

环境限制项没有被记为产品逻辑通过，也没有据此取消真实设备和完整服务验收。

### 2026-11-20：N2／N3 续作

- 新增 `GET /api/me/social-stats`，把 My Page 原先硬编码的四个 0 接到持久化点赞、收藏、Followers 和 Following 数据。
- My Page 统计增加加载状态、失败提示和 Try again；视频改为 Private 不会删除 owner-only 历史获赞／收藏统计。
- 修正 N3.1 作者页矩阵的前置条件，并新增 Account Private／Library hidden 与单条 Public 视频直接访问互不混淆的组合检查。
- 更新 B4.3 浏览器流程以使用当前 `My Page → Edit profile → Sign out` 路径，覆盖统计接口失败重试和账号切换后的真实统计。
- 扩展 N3.2 自动化，除 390×844 触屏外，新增桌面右拖进入作者页、左拖返回和 Calendar 月份拖动。
- 验证通过：完整 compute 发现 111 项（77 通过、34 按环境跳过），其中含 22 项 Social API、6 项可见性矩阵和 5 项 Profile／Privacy；另有 16 项前端／构建、1 项完整 Chromium 手机／桌面流程、TypeScript 和生产构建通过。
- 将 `ApiError` 的 TypeScript parameter property 改为等价显式字段，并更新 README 测试命令，使 Node 26 strip-only 模式可直接执行全部前端测试。

### 2026-11-20：Community 播放、Following feed 与 Attempts 可见性

- Community 全屏小视频新增常驻时间轴，可拖动到指定秒数，并显示当前时间／总时长；时间轴会阻止横滑手势误触。
- Community 列表在作者旁显示 Public／Preset 标识，并可直接 Follow／Unfollow；新增 All / Following 切换。
- Following feed 使用服务端 `GET /api/videos?owned=false&following=true` 筛选，只返回已关注账号的 Public 上传，不包含预置视频，也不会解锁 Private 内容。
- My Attempts 在缩略图上直接显示 Public／Private badge，并提供 `Change visibility` 快捷入口，直接打开现有 Edit video 表单切换。
- 验证通过：23 项 Social API、16 项前端／构建测试、TypeScript、生产构建及完整 Chromium 手机／桌面社交流程。Attempts 浏览器用例的新增断言已写入，但当前机器缺少该用例要求的 `BETA_TRANSLATOR_ROOT` 科学夹具，因此未将它记为通过。

## 4. 当前状态

| 任务 | 当前状态 | 仍需完成 |
| --- | --- | --- |
| B1.3 / B2.4 / N2.6 评论与社交 | 实现与自动化自查完成 | 真实跨设备及团队阶段验收 |
| N2.7 Follow／Unfollow | 实现、状态同步、列表快捷按钮、Following feed 与 My Page 统计完成 | 私有账号关注批准与 Followers／Following 列表需先确认 N1.2 产品规则 |
| N2.8 作者主页与手势入口 | 手机／桌面自动化自查完成 | 真实手机与 A 的隐私组合联合验收 |
| B4.3 / N3.1–N3.3 B 侧检查 | 数据库矩阵和 Chromium 手机／桌面流程完成 | 目录、通知真实任务、旧数据恢复、C 任务连续性和真正跨设备联合验收 |
| A5.2 备份恢复工具 | Sonia 已实现并验证 | A 或非作者独立复现后确认 |
| B5.2 Demo 账号与脚本 | 已实现并合并 | 在最终展示机器准备真实的 Git 忽略账号文件 |
| B5.3 多人演练 | 未完成 | 记录设备、3–5 人同时操作、问题负责人和修复结果 |

## 5. 尚未实现或不能由 Sonia 单独宣称完成

### 可由 Sonia 独立继续

- 为通知和结果补齐独立 mock fixtures，覆盖 loading／empty／success／failure，并明确标注模拟来源（B1.4）。
- 完善 suggestion 时间链接边界：重复点击、媒体未加载、时间超出视频长度（B4.2）。
- 把现有社交持久化数据接入授权的公开点赞／收藏列表；My Page 四项本人统计已完成。
- 在实际手机和桌面浏览器逐项执行 Community、评论、作者页和手势检查，并记录设备与结果。
- 由非作者按 README 独立执行备份／验证／恢复，补充复现记录。

### 需要 A 协作

- N1.2 私有账号 Follow approval、Followers／Following 可见性和公开分类规则定稿。
- 公开点赞／收藏分类的页面接入；My Page 四项真实社交统计已完成。
- Private 账号、Library 隐私、作者主页和公开资源组合的实机验收。
- 局域网、Cookie／Origin 和可选隧道环境下的登录、上传和播放。

### 需要 C 协作

- 用户上传触发的真实 suggestions、生成结果和来源标识（B4.1）。
- 真实任务、通知、结果跳转和失败重试的完整链路。
- 派生 Skeleton／结果的权限继承、任务连续性及算法环境验收。

### 需要全组完成

- 3–5 人同时登录、浏览、上传、评论和排队任务的演练。
- 真实手机／跨设备、服务重启、备份恢复和临时隧道验收。
- 最终展示问题清单、负责人、修复结果和已知限制。

## 6. 已知限制与安全约束

- Community 搜索和筛选目前只作用于已加载页面；视频 API 尚无服务端搜索。
- 自动化触屏测试不能替代真实移动浏览器的 autoplay、系统返回手势和网络行为。
- Follow 不会解锁私有视频；私有账号的关注批准流程尚未实现。
- sample 视频必须继续标注为预置内容，不能冒充用户上传或真实算法现场结果。
- `.env`、`demo/accounts.local.json`、密码、会话 token、数据库卷、用户上传和计算产物不得提交到 Git。
- 本地磁盘不是备份；数据库、上传和计算产物必须作为同一恢复点验证。

## 7. 提交索引

| 提交 | 内容 |
| --- | --- |
| `aad36be` | 持久化评论、回复、点赞、收藏、弹幕、分享与 Want to Try API |
| `140559a` | Community 持久化社交前端接入 |
| `7fcdb09` | 数据库、上传和计算产物的备份／验证／恢复 |
| `b37c4a8` | Follow／Unfollow |
| `916aead` | README、Social API、备份说明和任务记录 |
| `9d0df39` | 面向用户的英文播放／审核提示 |
| `566e34e` | sample 视频互动、作者主页与右滑入口 |
| `336628e` | Social API、N1.2 提案与 checklist |
| `375277a` | PR #1 合并 |
| `3b545ec` | 移动浏览器横向手势边界修复 |
| `41cb27c` | 可见性矩阵与手机浏览器自动化检查 |
| `b3cfeb0` | Demo 账号工具和逐步演示脚本 |
| `00765ac` | Round 3 状态与 Social API 错误结构修正 |
| `fbc5b4c` | 合并 `main` 并解决 Implementation 冲突 |
| `026b6ad` | PR #2 合并 |

## 8. 关联文档

- 团队总计划与逐项验收：[DEMO_IMPLEMENTATION_PLAN.md](DEMO_IMPLEMENTATION_PLAN.md)
- 社交接口和权限约定：[SOCIAL_API.md](SOCIAL_API.md)
- 展示步骤和账号准备：[DEMO_SCRIPT.md](DEMO_SCRIPT.md)
- A 侧历史与工程决策：[YIRU_ENGINEERING_LOG.md](YIRU_ENGINEERING_LOG.md)
- 项目启动、备份与部署说明：[README.zh-CN.md](../README.zh-CN.md)

后续 Sonia 的 B 侧实现、验证或合并记录统一追加到本文件；团队任务勾选仍同步更新 `DEMO_IMPLEMENTATION_PLAN.md`。
