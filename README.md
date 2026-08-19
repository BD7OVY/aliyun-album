# 培训照片共享相册

面向培训场景：**摄影师通过网页上传照片 → 自动存阿里云盘 + 生成相册 → 分享链接供所有人查看下载**。

阿里云盘只做照片存储，摄影师全程不需要接触你的阿里云盘账户。

## 三个入口

| 入口 | 给谁 | 地址 | 密码 |
|------|------|------|------|
| 📤 **上传入口** | 摄影师 | `http://电脑IP:8091/` | 上传码（.env 的 ALBUM_UPLOAD_CODE） |
| 🛠 **管理入口** | 你自己 | `http://电脑IP:8091/admin` | 管理码（.env 的 ALBUM_ADMIN_CODE） |
| 👀 **查看入口** | 所有人 | GitHub Pages 链接 | 访问密码（run.bat --set-pass 设置） |

## 目录结构

```
aliyun-album/
├── config.json          # 配置（相册名、folder_id、缩略图参数）
├── .env                 # 阿里云盘 token + 上传码 + 管理码（不入库）
├── harness/             # 工作流引擎（Python，确定性逻辑）
│   ├── aliyun_client.py # 阿里云盘 API 封装
│   ├── auth.py          # 认证辅助（env/缓存/扫码）
│   ├── thumbnail.py     # 缩略图生成（Pillow）
│   ├── manifest.py      # 数据清单管理
│   ├── sync.py          # 同步主流程（手动上传云盘后的同步）
│   └── validate.py      # 输出校验
├── server/              # 上传服务（Flask）
│   ├── app.py           # 上传 + 管理接口
│   ├── templates/       # 上传页 + 管理页
│   └── _inbox/          # 上传临时缓冲（自动清理）
├── gallery/             # 静态画廊（部署到 GitHub Pages）
│   ├── index.html       # 画廊页面
│   ├── app.js / style.css
│   ├── data.json        # 照片数据（自动生成）
│   ├── thumbnails/      # 缩略图（自动生成，~4KB/张）
│   └── originals/       # 原图（自动生成，随部署上线）
├── setup.bat            # 安装依赖（一次）
├── run.bat              # 同步（手动流程用）
├── upload_server.bat    # 启动上传服务（培训时双击）
└── deploy.bat           # 一键提交推送 GitHub（线上更新）
```

## 快速开始

> 已帮你完成：token 配置、云盘"共享相册"文件夹创建、依赖安装、本地 git 初始化。

### 第 1 步：设置访问密码（只需一次）

```bat
run.bat --set-pass
```
输入你想分享给所有人的查看密码。

### 第 2 步：启动上传服务（培训时）

双击 **`upload_server.bat`**，窗口会显示：

```
上传入口(给摄影师): http://192.168.x.x:8091/
管理入口(给自己):   http://192.168.x.x:8091/admin
```

- **首次运行** Windows 防火墙弹窗请点"允许访问"
- 摄影师连同一个 WiFi，手机浏览器打开上传入口即可传照片
- 上传后**自动完成**：原图存本地 + 备份到阿里云盘 + 生成缩略图 + 更新相册数据

### 第 3 步：部署到 GitHub Pages（一次性）

1. 打开 https://github.com/new ，仓库名填 `aliyun-album`，选 **Public**，不勾选任何初始化项，点 Create
2. 复制仓库地址（`https://github.com/你的用户名/aliyun-album.git`），发给我帮你推送
3. 推送完成后：仓库 Settings → Pages → Source 选 **Deploy from a branch** → **main / (root)** → Save
4. 等 1-2 分钟
5. 把查看链接 `https://你的用户名.github.io/aliyun-album/gallery/` 填进 `config.json` 的 `site.base_url`

### 第 4 步：分享

- **给摄影师**：上传入口链接 + 上传码
- **给学员/家人**：查看链接 + 访问密码

### 日常使用（培训当天）

```
摄影师手机连 WiFi → 打开上传链接 → 输入上传码 → 传照片（自动进云盘+相册）
        ↓
你双击 deploy.bat → 1-2 分钟后线上相册更新
```

## 工作流

```
摄影师浏览器 ──上传照片──▶ 上传服务 (Flask, 电脑 8091 端口)
                              │ 校验上传码
                              ▼
                     本地原图 gallery/originals/  ←─ 查看原图用
                              │ 备份
                              ▼
                     阿里云盘「共享相册」文件夹（1.7T 存储）
                              │
                              ▼
                     缩略图 + data.json 更新
                              │ git push
                              ▼
                     GitHub Pages 查看链接（密码访问）
```

补充：你自己手机传照片到云盘后，双击 `run.bat` 同样会同步进相册（自动下载原图 + 生成缩略图）。

## 设计原则

1. **Harness 管确定性**：上传、转存、缩略图、清单、发布全部代码完成，不靠提示词约束。
2. **原图双存**：本地一份（查看/下载用）+ 阿里云盘一份（备份 + 1.7T 利用）。
3. **不依赖阿里云盘分享 API**（官方已限制第三方分享，仅 4 小时有效）——查看原图直接走本地原图。
4. **不过度工程化**：Flask 单文件服务 + 静态画廊，无数据库、无复杂部署。
