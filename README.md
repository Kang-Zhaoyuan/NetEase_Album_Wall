# 网易云收藏专辑导出小工具

这是一个用于导出「网易云音乐 - 我收藏的专辑」列表的小工具。

结果会导出为一个干净的 CSV 文件（默认：`my_netease_albums.csv`）。

> 安全提示：`MUSIC_U` 相当于登录凭证，请像密码一样保管，避免泄露。

---


## 快速开始（3 步）

1) 安装依赖

```bash
pip install -r requirements.txt
```

2) 运行脚本

```bash
python netease_album_exporter.py
```

3) 在弹出的 Chrome 页面扫码登录

登录成功后会在当前目录生成：

- `cookies.json`（下次复用登录态）
- `my_netease_albums.csv`（导出结果）

---

## 登录方式
### 方式 A：自动登录（推荐）

直接运行：

```bash
python netease_album_exporter.py
```

说明：

- 如果当前目录下存在 `cookies.json`，会优先读取并校验其中的 `MUSIC_U`
- 若 `cookies.json` 不存在或已过期：会打开 Chrome 到登录页，请在弹出的页面扫码登录
- 登录成功后，会自动把 `MUSIC_U`（以及部分 Cookie 信息）保存到 `cookies.json`，下次可复用



### 方式 B：手动提供 MUSIC_U

如果你不想用 Selenium，或本机未安装Google Chorme，也可以手动把 `MUSIC_U` 传给脚本：
（手动获得`MUSIC_U`的教程在下方，建议直接使用 Google Chorme ）
```bash
python netease_album_exporter.py --music-u "write_your_MUSIC_U_here"
```

也可以直接粘贴浏览器里复制出来的完整 Cookie 字符串（脚本会自动解析其中的 `MUSIC_U=`）：

```bash
python netease_album_exporter.py --music-u "MUSIC_U=xxxx; __csrf=yyyy; ..."
```

---



## 输出 CSV 字段说明

CSV 列名如下：

- `Album Name`：专辑名称
- `Artist Name(s)`：歌手（多个用英文逗号分隔）
- `Track Count`：曲目数
- `Album ID`：专辑 ID
- `Cover Image URL`：封面图片链接
- `Subscribe Time`：收藏/订阅日期（`YYYY-MM-DD`）

文件编码为 `utf-8-sig`，方便 Excel 直接打开不乱码。

---

## 如何在浏览器里找到 MUSIC_U（手动方式）

1) 打开浏览器并登录 https://music.163.com/
2) 按 `F12` 打开开发者工具（DevTools）
3) 切到 `Network`（网络）面板，然后刷新页面
4) 在请求列表里找到一个发往 `music.163.com` 的请求，点开后查看：
   - `Headers` -> `Request Headers` -> `Cookie`
5) 在 Cookie 字符串中找到 `MUSIC_U=...`，复制其值即可

---

## cookies.json 说明

自动登录成功后会生成/更新 `cookies.json`，用于下次复用登录态。结构大致如下：

```json
{
  "music_u": "...",
  "saved_at": "2026-03-03T12:34:56",
  "cookies": [
    {"name": "MUSIC_U", "value": "...", "domain": "music.163.com"}
  ]
}
```

你可以删除 `cookies.json` 来强制重新登录。

---