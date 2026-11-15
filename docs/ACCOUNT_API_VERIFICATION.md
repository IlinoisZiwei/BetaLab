# 本地 Demo 启动与页面验证

当前本地 Demo 已接通账号注册／登录／退出、Cookie 会话恢复、资料保存、数据库场馆路线、MP4/MOV 上传、Private／Public 权限、Share as beta 和受保护的视频播放。Community 列表、Community Beta 列表和全屏视频浏览已接入用户视频；仓库预置示例仍使用 bundled 媒体。点赞／收藏／评论持久化和后台生成任务／完成通知尚未完成。

## 启动

在仓库根目录执行；先启动 Docker Desktop。

```sh
docker compose up -d db
python3 backend/db/manage.py migrate
python3 backend/db/manage.py seed
backend/.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8788
```

另开终端。手机同 Wi-Fi 展示时使用 `--host 0.0.0.0`，并按下一节配置 Origin：

```sh
npm run dev -- --host 127.0.0.1 --port 5174
```

浏览器打开 http://127.0.0.1:5174 。不要打开旧 8443 服务或 GitHub Pages 来验证本地 API。

首次环境初始化见 [backend/README.md](../backend/README.md)。根目录 `.env` 的 `APP_ORIGINS` 必须包含浏览器访问的完整 origin（协议、主机、端口）。手机访问时添加 `http://<Mac 局域网 IP>:5174`，Vite 用 `--host 0.0.0.0` 监听，修改后重启 API。不要提交 `.env` 或 `data/uploads/`。

## 验证表

| 操作 | 预期 |
| --- | --- |
| 首页右上角账号 → Sign up；输入新用户名和至少 8 位密码 | 创建真实账号并进入资料页；无邮箱要求 |
| 填写名字、身高 170、臂展 175 → Save | 显示 Profile saved |
| 刷新页面，再点击右上角账号 | 保持登录，名字及身材信息保留 |
| 修改资料保存后刷新 | 显示新值 |
| 清空两个身材字段并保存 | 可清空为未填写，不变成 0 |
| 输入身高 20 并保存 | 显示参数错误，不提示保存成功 |
| Go Climbing → Gym A | 数据库返回 2 条 active routes，目录含 3 条路线，其中 Old Slab 为归档 |
| 进入 Gym B | 显示没有路线 |
| 资料页 Sign out，然后刷新 | 不再登录，目录提示登录 |
| 用错误密码登录 | 显示错误，不会进入登录状态 |
| 用正确密码登录 | 原资料恢复 |
| 用已有用户名注册 | 显示用户名冲突 |
| 无痕窗口注册第二账号 | 资料独立，不读取第一个账号资料 |
| 停止并重启 API，刷新登录页面 | Cookie 会话和数据库资料仍有效 |
| Go Climbing → Gym A | 数据库显示 Corner Study 与 Long Reach 两条 active routes |
| 上传 MP4/MOV，填写标题并选择 Public | 保存到 PostgreSQL 元数据和本机私有视频目录；出现在 My Library 与 Community |
| 上传时选择 Public 且 Share as beta | 同时出现在普通 Community 和该路线 Community Beta |
| 上传时选择 Public、不选 Share as beta | 出现在普通 Community，不出现在 Community Beta |
| 将已上传视频改为 Private | 其他登录用户看不到，上传者仍能从 My Library 进入 |
| Community 列表点开视频 | 进入全屏纵向视频浏览；视频尝试带声音自动播放，若浏览器拦截则点播放按钮 |
| 浏览预置 sample | Community 中标注为 Preset sample，不代表数据库里的用户上传记录 |
| 手机与 Mac 连同一 Wi-Fi | 手机用 `http://<Mac 局域网 IP>:5174` 访问同一个本地服务；电脑仍可同时访问 |

用户名 3–32 位，英文字母、数字和下划线，大小写不敏感。身高 100–230、臂展 80–260 cm。登录注册合计每连接 IP 每分钟最多 10 次，密集测试遇到 429 等一分钟即可。

浏览器开发者工具 Network 中检查 /api/auth/me、/api/profile、/api/gyms 和 /api/routes。登录后 me 返回 user 与 csrf_token；profile 修改带 X-CSRF-Token；页面不把会话 Cookie 存入 localStorage。不要截图或分享真实密码、Cookie 和 token。

若连接失败，检查数据库和 API 是否启动；403 检查 APP_ORIGINS；请求返回 HTML 时检查是否打开了正确的 Vite 服务及代理是否加载；401 通常需要重新登录。

## 验证范围

开发侧执行 `npm run build`、Python 语法检查和 `git diff --check`。手机布局、浏览器声音自动播放策略、多设备访问及完整上传权限流程仍需团队在实际设备上按表人工验收。暂不自动勾选主实施计划的任务状态，待负责人验收并提交代码后记录。
