# QQ 漫画助手

一个基于 QQ 官方机器人回调的本地漫画助手。

它现在能做这些事：
- 收到编号后，检查本地资源、下载漫画、生成 5 合 1 长图、按范围发图
- 查询作品简介、作者、标签、页数
- 按关键词 / 标签 / 作者 / 作品 / 角色搜索，并随机返回 5 条结果
- 用过滤命令从一整句话里提取数字，再自动查 `info`

## 快速开始

### 1. 配置内网穿透

你需要先把本机 `8080` 端口暴露到公网。

可选方案：
- `ngrok`
- `樱花穿透`

要求只有一个：
- 穿透的本地端口要指向 `8080`

如果你想改端口：
- 改 [scripts/load_env.sh.example](scripts/load_env.sh.example) 里的端口项
- Windows 改 [scripts/load_env.bat.example](scripts/load_env.bat.example) 里的端口项
- 同时把内网穿透工具的本地端口也改成同一个值

`ngrok` 示例：
```bash
ngrok http 8080
```

启动后你会拿到一个公网地址，例如：
```text
https://xxxx.ngrok-free.app
```

后面 QQ 机器人回调地址就填：
```text
https://xxxx.ngrok-free.app/qq/callback
```

如果你用樱花穿透：
- 新建一个 HTTP/HTTPS 隧道
- 本地地址填 `127.0.0.1`
- 本地端口填 `8080`
- 最终把分配给你的公网地址拼上 `/qq/callback`

### 2. 注册 QQ Bot 并填写参数

去 QQ 开放平台创建机器人后，你主要要拿这几个值：
- `AppID`
- `Secret`
- 当前是不是 `沙箱环境`

获取位置：
- QQ 开放平台 -> 机器人管理后台 -> 开发管理 / 代码开发

然后把模板复制成本地配置文件：

macOS / Linux：
```bash
cp scripts/load_env.sh.example scripts/load_env.sh
```

Windows：
```bat
copy scripts\load_env.bat.example scripts\load_env.bat
```

然后只改这几个值：
- `QQ_BOT_APP_ID`
- `QQ_BOT_SECRET`
- `QQ_BOT_IS_SANDBOX`

说明：
- 沙箱测试时，`QQ_BOT_IS_SANDBOX=1`
- 上正式环境时，再改成 `0`

QQ 平台里还要做两件事：
- 在 `使用范围和人员` 里把你自己加进白名单 / 消息列表
- 在 `回调配置` 里把地址填成你的公网地址加 `/qq/callback`

例如：
```text
https://xxxx.ngrok-free.app/qq/callback
```

### 3. 打开命令行并启动项目

先进入项目根目录：

macOS / Linux：
```bash
cd /path/to/project
```

Windows：
```bat
cd /d D:\path\to\project
```

如果你是 macOS / Linux，第一次可以先给脚本执行权限：
```bash
chmod +x scripts/start.sh
```

然后启动：

macOS / Linux：
```bash
./scripts/start.sh
```

Windows：
```bat
scripts\start.bat
```

现在启动脚本会自动做这些事：
- 自动读取 `scripts/load_env.sh` 或 `scripts/load_env.bat`
- 如果没有 `.venv`，自动创建虚拟环境
- 自动安装依赖
- 自动启动服务

也就是说，大多数情况下外行只要运行这一个启动脚本就够了。

### 4. 测试是否成功

服务启动后：
- 保持内网穿透工具在运行
- 保持项目启动脚本窗口不要关
- 去 QQ 里给机器人发消息

先发：
```text
help
```

如果能收到帮助信息，说明链路通了。

## 常用指令

### 发图

- `123456`
  默认发前 5 张长图
- `123456 5`
  只发第 5 张长图
- `123456 5-10`
  发第 5 到第 10 张长图
- `123456 5-`
  发第 5 张之后的全部长图
- `123456 -5`
  发前 5 张长图
- `123456 all`
- `123456 al`
  发全部长图

### 简介

- `123456 info`
- `123456 if`

返回：
- 标题
- 作者
- 页数
- 标签
- 简介

### 搜索

- `search 关键词`
- `sr 关键词`
  通用搜索

- `search tag 纯爱`
- `sr tg 纯爱`

- `search author MANA`
- `sr au MANA`

- `search work 原神`
- `sr wk 原神`

- `search actor 雷电将军`
- `sr ac 雷电将军`

搜索会：
- 先拿第一页
- 再随机抽若干页
- 去重
- 最后随机返回 5 条结果

### 过滤提取数字

- `guolv 一整句话`
- `filter 一整句话`
- `fl 一整句话`

例如：
```text
guolv 做完近视手术之后4天之内不能碰水6天之后才能洗澡91天之后才能正常去游乐园玩99天之后才算彻底养好
```

会提取成：
```text
469199 info
```

### 帮助

- `help`
- `hp`

### 最近日志

- `log`

会返回最近 10 条编号命令日志。
如果内容较多，会拆成 2 条消息，每条最多 5 条记录。

### 清空本地图片缓存

- `rm`

会清空：
- `downloads/` 里的原图
- `downloads_longimg/` 里的长图
- `downloads_pdf/` 里的 PDF
- SQLite 里的缓存记录

## 项目结构

### 入口层

- [app/main.py](app/main.py)
  FastAPI 应用入口，负责创建服务和启动时维护任务

- [app/routes/qq_callback.py](app/routes/qq_callback.py)
  QQ webhook 回调入口，负责验签、解析命令、分发业务

- [app/routes/files.py](app/routes/files.py)
  提供 `/files/...` 静态文件路由，给 QQ 平台拉取长图

### 服务层

- [app/services/qq_api.py](app/services/qq_api.py)
  统一封装 QQ 发消息、发图片、重试、`msg_seq` 管理

- [app/services/jm_service.py](app/services/jm_service.py)
  统一封装内容源的详情查询、下载、搜索

- [app/services/cache_service.py](app/services/cache_service.py)
  本地缓存 LRU 管理，状态落在 SQLite

### 业务层

- [biz/album_send.py](biz/album_send.py)
  处理发图主流程

- [biz/album_info.py](biz/album_info.py)
  处理 `info` 查询

- [biz/search.py](biz/search.py)
  处理统一搜索命令

- [biz/help.py](biz/help.py)
  处理帮助命令

### 工具层

- [utils/command_parser.py](utils/command_parser.py)
  文本命令解析

- [utils/image_merge.py](utils/image_merge.py)
  5 合 1 长图生成、压缩、更新判断

- [utils/progress.py](utils/progress.py)
  下载进度消息格式化

### 启动与配置

- [scripts/start.sh](scripts/start.sh)
  macOS / Linux 启动脚本

- [scripts/start.bat](scripts/start.bat)
  Windows 启动脚本

- [scripts/load_env.sh.example](scripts/load_env.sh.example)
- [scripts/load_env.bat.example](scripts/load_env.bat.example)
  环境变量模板

- [app/config.py](app/config.py)
  所有配置的默认值入口

## 数据流

大概是这样：

```text
QQ客户端
-> QQ服务器
-> 你的公网回调地址
-> 内网穿透
-> 本机 8080
-> FastAPI
-> 业务逻辑
-> 需要发图时再通过 /files/... 给 QQ 拉图
```

也就是说：
- 回调是 `POST /qq/callback`
- 发图不是把本地文件直接推给 QQ
- 而是给 QQ 一个 URL，让 QQ 自己来拉图

## 备注

- 本地私密配置文件：
  - `scripts/load_env.sh`
  - `scripts/load_env.bat`
  已经被 `.gitignore` 忽略，不会进仓库

- 本地缓存 LRU 状态会落到 SQLite：
  - `.autojm_cache.db`

- 默认监听端口是 `8080`
- 如果改端口，记得同时改：
  - 模板文件里的端口项
  - 内网穿透配置
  - QQ 回调地址对应的转发目标
