# 演示脚本与预设账号（B5.2）

目标：8–10 分钟内，由一人操作、一人讲解，完整展示"找路线 → 看社区 Beta → 互动 → 上传自己的视频 → 生成骨架 → 在 My Library 找回"。界面全英文，下文按钮名与界面一致。

## 1. 演示前准备（前一天完成）

1. 按 README 启动 PostgreSQL、迁移（含 012–014）、seed、API、worker 和 Vite；手机演示时按 `backend/README.md` 配置 LAN 的 `APP_ORIGINS`。
2. 复制账号模板并设置真实密码（该文件已被 Git 忽略，**密码不进仓库**）：

   ```sh
   cp demo/accounts.example.json demo/accounts.local.json
   # 编辑 demo/accounts.local.json：替换 CHANGE-ME，填入演示视频的本地路径
   backend/.venv/bin/python -m backend.db.demo_accounts demo/accounts.local.json            # 建账号与资料
   backend/.venv/bin/python -m backend.db.demo_accounts demo/accounts.local.json --upload   # API 运行时上传演示视频
   ```

   可重复执行：已有账号只更新资料（加 `--reset-passwords` 才改密码并让旧会话失效），同标题视频不会重复上传。账号直接写入数据库，因此演示时可以设置 `REGISTRATION_ENABLED=false` 关闭公开注册。
3. 演示前做一次备份并验证：`python3 -m backend.db.backup backup`，再 `verify backups/<目录>`；演示结束可用 `restore` 回到干净状态（见 README “Backup and restore”）。
4. 设备分工：电脑登录 `demo_nora`（上传者），手机登录 `demo_viewer`（观众）。两台设备同时在线，用来展示跨账号、跨设备同步。

## 2. 示例内容与用户内容的区分

| 内容 | 来源 | 界面标识 |
| --- | --- | --- |
| Movement Fishtown 的 73 张路线照片和 Corner Study | 仓库预置目录 | 场馆／路线页面 |
| Community 中 Attempt 1–3、Nora P.'s beta | 仓库预置示例视频，没有真实作者 | 作者行显示 **Public · Preset sample** 或 **Public · Preset Community Beta**；右滑提示没有作者页 |
| 演示账号上传的视频 | 真实上传（`demo_*` 账号，显示名带 “(demo)”） | 作者行显示场馆与难度，可进入作者页、Follow |
| 点赞、评论、收藏、弹幕 | 演示时真实产生，持久保存 | 示例视频也可以互动，计数对所有账号一致 |

讲解时明确说：示例视频用于展示界面，**骨架与建议只对真实上传并完成计算的视频给出**。

## 3. 演示步骤

| # | 设备／账号 | 操作 | 讲解要点 |
| --- | --- | --- | --- |
| 1 | 手机 · demo_viewer | Home → **Go Climbing** → Movement Fishtown → 选一条路线 | 路线照片只突出本条路线的岩点，其余岩点灰化 |
| 2 | 手机 | 路线卡片右侧书签 → My Library → **Want to Try** | 想爬路线跨设备保存 |
| 3 | 手机 | 底部 **Community** → 点 “Corner Study send (demo)” | 进入全屏视频，上下滑切换视频，左滑返回 |
| 4 | 手机 | 右侧依次点 ♥、收藏、评论；在评论框写一句并 **Post** | 评论框提示 “Shows on the video at 0:0x”：评论会在该时间点作为 live comment 飘过 |
| 5 | 手机 | 打开 live comments 开关，回到刚才的时间点 | 自己的弹幕高亮；可在评论里点时间标签跳转 |
| 6 | 电脑 · demo_nora | 打开同一视频的评论 | 观众的评论、点赞数已同步；作者可回复（一层回复，@对方） |
| 7 | 手机 | 在视频上**右滑**（电脑可向右拖动）→ 作者页 → **Follow** | 作者页只显示公开视频和关注数，不显示私人收藏、骨架和通知 |
| 8 | 手机 | 分享按钮 → 复制链接，在另一账号打开 | 链接直接打开该视频；私有视频不会因链接泄露 |
| 9 | 电脑 · demo_nora | 路线页 **Add my video** → 选视频 → 设 **Visibility** 与 **Share as beta** → **Upload video** | Public + Share as beta 会公开身高臂展；Private 只有本人可见 |
| 10 | 电脑 | 视频页 **Generate beta**，然后离开页面继续浏览 | 生成在后台进行；完成后 **Notifications** 有未读提示（依赖 C 的 worker） |
| 11 | 电脑 | My Library → **My skeletons** / **Saved Beta** | 刷新或重新登录后都能找回 |
| 12 | 电脑 | 把一个公开视频改为 Private，再在手机刷新 | 手机端立刻看不到该视频、内容和评论（权限由后端检查） |

## 4. 备用方案

- 生成任务耗时过长：展示已完成的真实结果（C 的备用结果），并说明这是预生成结果。
- 网络不稳定：手机改用电脑浏览器的手机尺寸窗口，账号不变。
- 数据被现场操作弄乱：`python3 -m backend.db.backup restore backups/<目录> --yes` 恢复到演示前状态（会先把当前上传和产物目录移到旁边保留）。

## 5. 演示后

- 记录每台设备的问题、负责人和修复结果（B5.3）。
- 如需清除演示账号，在数据库中删除 `demo_*` 用户：其视频记录、评论、点赞、收藏和关注会随之删除（外键级联加迁移 014 的清理触发器）；上传目录中的视频文件不会自动删除，需要手动清理或用演示前的备份恢复。

## C handoff update — 2026-11-21

Use My Page → My Library → My Skeletons; notifications are opened from the bell. New tasks show true stages and elapsed time; migration 015 adds queue/processing timing without guessing historical starts.

For new-video input review, show the full Trial3 extraction evidence (251 frames, 57 hold candidates, 1,004 limb observations; 73.94 s and 71.95 s). It is input preparation, not a generated skeleton. Demonstrate hold-center correction/addition, guided wall-panel/grid entry, contact version pinning and unknown angles. The saved real Trial3 contact draft is **not confirmed**; its initial left-foot candidate is unsupported because the foot begins on the floor. Do not enable generation or claim verified motion from that draft.

The v5 fallback remains an unchanged, checksum-verified historical real diagnostic result with failed baselines. UI-only tests verify its recorded source hashes; they do not rewrite provenance. Latest two-account lifecycle tests use explicit mock computation. No new Trial2 source fitting or technique comparison was run in this round. Do not describe mock lifecycle testing as a fresh real source→target rehearsal.

Local evidence: `backend/compute/runs/c-readiness/`. Backup verification covered the isolated acceptance database, uploads and compute files in a scratch restore; it did not replace live preview data. Keep credentials, media, archives and logs local. Confirm the presentation machine, a real phone and 3–5 participants before marking the final group rehearsal complete.

## Three-case showcase (November 23, local only)

Sign in as `betalab_showcase` using the password in ignored `demo/showcase.local.json`. In Community, open Trial1 or Trial3, choose Generate beta / Use skeleton, and show the **Pre-generated demonstration** label. Save to My Skeletons, refresh, and reopen under Saved demonstrations. Both new routes are in Movement Fishtown with venue-unverified demo metadata; their wall images come from the original recordings.

Show the fixed target body: Trial1 and Trial3 use 180 cm/template proportions, not independently personalized arm span. The focused top pane is a planar schematic; the lower pane preserves the original. Corner Study keeps its historical dimensions and failed-baseline diagnostic. Do not describe a saved demo as a new computation or a verified technique result. The offline algorithm adapter passed input checks only; live browser generation remains disabled. No Trial2 fitting or technique comparison ran.
