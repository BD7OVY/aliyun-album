# 培训照片共享相册

面向培训场景：摄影师通过**阿里云盘收集链接**上传照片 → 你回家双击 `publish.bat` → 照片自动发布到 GitHub Pages 在线相册 → 分享链接给所有人查看。

**不需要带电脑去现场**，只需要把阿里云盘收集链接分享给摄影师即可。

## 工作流

```
摄影师打开网盘收集链接 → 免登录上传照片（手机/电脑都行）
                                    │
                    你回家后从网盘下载照片到 incoming/ 文件夹
                                    │
                            双击 publish.bat
                    （自动：去重 → 缩略图 → 原图 → 推送 GitHub）
                                    │
                    访客打开链接 → 输入密码 → 查看相册 + 下载原图
```

阿里云盘作为照片备份存储（1.7T），原图同时存在本地 `gallery/originals/` 和阿里云盘。

## 目录结构

```
aliyun-album/
├── config.json          # 配置（相册名、folder_id、缩略图参数、Pages URL）
├── .env                 # 阿里云盘 token + 上传码 + 管理码（不入库）
├── harness/             # 工作流引擎（Python，确定性逻辑）
│   ├── publish.py       # 核心：incoming/ 照片 → 画廊发布
│   ├── aliyun_client.py # 阿里云盘 API 封装（备份用）
│   ├── auth.py          # 认证辅助
│   ├── thumbnail.py     # 缩略图生成（Pillow，含 EXIF 方向修正）
│   ├── manifest.py      # 数据清单管理
│   ├── sync.py          # 云盘同步（手动上传云盘后的同步）
│   └── validate.py      # 输出校验
├── gallery/             # 静态画廊（部署到 GitHub Pages）
│   ├── index.html       # 画廊页面（密码门 + 瀑布流 + 灯箱）
│   ├── app.js / style.css
│   ├── data.json        # 照片数据（自动生成）
│   ├── thumbnails/      # 缩略图（自动生成）
│   └── originals/       # 原图（自动生成，随部署上线）
├── incoming/            # 放待处理照片（网盘下载到这）
├── .nojekyll            # 禁用 GitHub Pages Jekyll
├── index.html           # 根重定向页 → gallery/
├── setup.bat            # 安装依赖（只需一次）
├── run.bat              # 云盘同步 / 设置密码（run.bat --set-pass）
├── publish.bat          # 一键处理照片 + 发布（日常使用）
└── deploy.bat           # 仅推送 GitHub（publish.bat 已包含）
```

## 快速开始

### 第 1 步：设置访问密码（只需一次）

```bat
run.bat --set-pass
```
输入你想分享给访客的查看密码。密码哈希存入 `config.json`，推送到 GitHub 后生效。

### 第 2 步：分享网盘收集链接给摄影师

1. 打开阿里云盘（App 或网页版 aliyundrive.com）→ 新建一个文件夹（如「培训照片」）
2. 选中该文件夹 → **分享** → 勾选 **「允许上传」**（这就是文件收集，对方免登录就能传）
3. 把生成的分享链接发给摄影师 —— 他们**免登录**、手机电脑都能传，照片直接进你的「培训照片」文件夹

### 第 3 步：下载照片 + 发布

1. 从网盘把收集到的照片下载到 `incoming/` 文件夹
2. 双击 **`publish.bat`**
3. 脚本自动完成：
   - 内容哈希去重（同名副本自动跳过）
   - 复制原图到 `gallery/originals/`
   - 生成缩略图到 `gallery/thumbnails/`（含 EXIF 方向修正、HEIC 支持）
   - 更新 `gallery/data.json`
   - 推送到 GitHub → Pages 1-2 分钟后自动更新

### 第 4 步：分享查看链接

把 GitHub Pages 链接 + 访问密码分享给学员/家人：

```
链接：https://bd7ovy.github.io/aliyun-album/
密码：你设置的访问密码
```

## 日常使用（培训当天）

```
培训现场：摄影师收到网盘收集链接 → 拍完就传（手机直接传）
        ↓
你回家：网盘下载照片到 incoming/ → 双击 publish.bat → 完成
        ↓
分享查看链接 + 密码 → 所有人随时看相册、下载原图
```

## publish.py 处理逻辑

| 步骤 | 说明 |
|------|------|
| 扫描 | 遍历 `incoming/` 下所有文件，识别图片（jpg/png/heic 等），跳过 zip/rar |
| 去重 | 按文件内容 SHA-1 哈希分组，同内容只保留最短文件名的那个 |
| 跨批次去重 | 与 `data.json` 已有照片哈希对比，重复的自动跳过 |
| 缩略图 | Pillow 生成 480px 宽 JPEG，自动修正 EXIF 方向（手机竖拍不倒） |
| 原图 | 复制到 `gallery/originals/<hash>_<原名>`，部署后可直接下载 |
| 归档 | 处理完的文件移入 `incoming/done/`（保留备查） |

## 设计原则

1. **Harness 管确定性**：去重、缩略图、清单、发布全部代码完成，不靠提示词约束。
2. **原图双存**：本地一份（查看/下载用）+ 阿里云盘一份（备份 + 1.7T 利用）。
3. **不依赖阿里云盘分享 API**（官方已限制第三方分享）——查看原图直接走本地文件。
4. **不过度工程化**：静态画廊 + Python 脚本，无数据库、无服务端。
