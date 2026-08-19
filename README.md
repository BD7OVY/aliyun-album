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
├── run.bat              # 启动同步
└── deploy.bat           # 一键提交并推送 GitHub（线上更新）
```

## 快速开始

> 已帮你完成：token 配置、云盘"共享相册"文件夹创建、folder_id 写入、本地 git 初始化、依赖安装。

### 第 0 步：上传照片（日常操作，手机就能做）

1. 手机/电脑打开**阿里云盘 App**
2. 进入网盘根目录的 **"共享相册"** 文件夹（已在你的云盘里建好）
3. 把要分享的照片传进去（支持 jpg/png/gif/webp/heic）
4. 完成

### 第 1 步：同步（生成相册数据）

1. 双击 **`run.bat`**
2. 等待输出 "Sync complete. N photos in manifest."
3. 完成后 `gallery/` 里就有了最新缩略图和 data.json

### 第 2 步：设置访问密码（只需一次）

```bat
run.bat --set-pass
```
输入你想分享给家人的密码。

### 第 3 步：部署到 GitHub Pages

**一次性准备（首次）：**
1. 浏览器打开 https://github.com/new
2. Repository name 填 `aliyun-album`，选 **Public**，**不要**勾选任何初始化选项，点 Create
3. 复制仓库地址（形如 `https://github.com/你的用户名/aliyun-album.git`）
4. 在项目文件夹打开命令行，执行：
   ```bat
   git remote add origin 你的仓库地址
   git push -u origin main
   ```
5. 打开 https://github.com/你的用户名/aliyun-album → Settings → Pages
6. Source 选 **Deploy from a branch** → Branch 选 **main / (root)** → Save
7. 等 1-2 分钟，访问 `https://你的用户名.github.io/aliyun-album/gallery/`

**以后每次更新（日常操作）：**
1. 阿里云盘 App 上传新照片
2. 双击 `run.bat`（同步）
3. 双击 `deploy.bat`（提交并推送，1-2 分钟后线上更新）

### 第 4 步：分享

- **查看链接**：把 `https://你的用户名.github.io/aliyun-album/gallery/` + 访问密码 发给家人
- **上传入口**：只你自己有（阿里云盘"共享相册"文件夹），家人不需要上传

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
