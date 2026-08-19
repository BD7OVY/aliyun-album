# 阿里云盘共享相册

利用阿里云盘大容量存储，搭建带密码访问的共享相册。

## 架构

```
aliyun-album/
├── config.json          # 配置（相册名、密码哈希、缩略图参数）
├── .env                 # 阿里云盘 refresh_token（从 .env.example 复制）
├── .env.example         # .env 模板
├── harness/             # 工作流引擎（Python，确定性逻辑）
│   ├── aliyun_client.py # 阿里云盘 API 封装
│   ├── auth.py          # 认证辅助（env/cache/扫码登录）
│   ├── get_token.py     # 一键获取/保存 refresh_token
│   ├── thumbnail.py     # 缩略图生成（Pillow）
│   ├── manifest.py      # 数据清单管理
│   ├── sync.py          # 同步主流程
│   └── validate.py      # 输出校验
├── gallery/             # 静态画廊（纯 HTML/CSS/JS）
│   ├── index.html       # 画廊页面
│   ├── style.css        # 样式
│   ├── app.js           # 交互逻辑
│   ├── data.json        # 照片数据（harness 自动生成）
│   └── thumbnails/      # 缩略图（harness 自动生成）
├── setup.bat            # 安装依赖
└── run.bat              # 启动同步
```

## 快速开始

### 1. 安装依赖
```bat
setup.bat
```

### 2. 登录阿里云盘（三选一）

**方式 A：浏览器复制 refresh_token（不用安装 aligo 即可拿到）**
1. 浏览器打开 https://www.aliyundrive.com 或 https://www.alipan.com 登录
2. F12 → Console（控制台）
3. 粘贴并运行：
   ```js
   JSON.parse(localStorage.token).refresh_token
   ```
4. 复制返回的字符串，粘贴到 `.env` 的 `ALIYUN_REFRESH_TOKEN=` 后面

**方式 B：扫码登录（最简单，无需手动找 token）**
```bat
copy .env.example .env
setup.bat
python harness/get_token.py
```
按提示用阿里云盘 App 扫描二维码即可。token 会自动保存到 `.env`。

**方式 C：首次同步时自动扫码登录**
直接运行 `run.bat`，如果没有配置 token，它会自动弹出二维码让你扫描。

### 3. 配置相册文件夹
编辑 `config.json`，设置 `aliyun.folder_id` 为相册文件夹 ID。获取方式：在阿里云盘网页版打开目标文件夹，地址栏最后一段就是 folder_id。

### 4. 设置访问密码
```bat
run.bat --set-pass
```

### 5. 同步
```bat
run.bat
```
Harness 会：列出云盘图片 → 下载原图 → 生成缩略图 → 创建分享链接 → 写入 data.json

### 6. 预览 / 部署
```bat
cd gallery
python -m http.server 8090
```
浏览器打开 http://localhost:8090

部署：将 `gallery/` 目录上传到任意静态托管（GitHub Pages、对象存储等）。

## 工作流

```
管理员上传照片到阿里云盘
        ↓
run.bat → harness/sync.py
        ↓
  列出云盘文件 → 对比已有清单
        ↓
  新照片: 下载原图 → 生成缩略图 → 创建分享链接 → 写入清单
  已删照片: 删缩略图 + 删清单条目
        ↓
  保存 data.json → 验证完整性
        ↓
画廊加载 data.json → 密码校验 → 瀑布流展示缩略图
        ↓
点击照片 → 灯箱预览 → 查看原图 → 跳转阿里云盘下载
```

## 设计原则

1. **Harness 管确定性，LLM 管创意**：API 调用、缩略图生成、清单管理全部用代码确定性完成，不靠提示词约束。
2. **缩略图本地、原图云端**：缩略图(~4KB/张)存静态站点，原图(几MB/张)留阿里云盘 1.7T。
3. **不过度工程化**：纯静态画廊 + Python 脚本，无后端服务、无数据库、无 CI/CD。
