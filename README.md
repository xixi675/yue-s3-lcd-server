# yue-s3-lcd-server

小月语音助手服务端，配套固件仓库：

<https://github.com/xixi675/yue-s3-lcd>

## 功能

- 本地 SenseVoiceSmall 语音识别
- DeepSeek 对话
- EdgeTTS 语音合成
- 本地 RAG 儿童知识库
- 儿童内容安全过滤
- 本地儿歌点播
- 小月角色提示词

## 启动

建议使用 Python 3.10。

```powershell
cd main\xiaoyue-server
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
Copy-Item data\.config.example.yaml data\.config.yaml
Copy-Item .env.example .env
```

把 `data\.config.yaml` 里的 `你的电脑局域网IP` 改成运行服务端电脑的局域网地址，然后在 `.env` 中填写：

```text
DEEPSEEK_API_KEY=你的Key
```

然后回到仓库根目录启动：

```powershell
cd ..\..
.\start-server.ps1
```

服务默认监听：

- HTTP / OTA：`8003`
- WebSocket：`8000`

具体配置和使用说明见 [LOCAL_SETUP.md](LOCAL_SETUP.md)。

## 本地儿歌

儿歌放在 `main/xiaoyue-server/music/儿歌/`，支持 `.wav` 和 `.mp3`。当前内置小星星、两只老虎、拍拍手、数一数、洗手歌、晚安小月亮。

可以说：

- “唱小星星”
- “我想听两只老虎”
- “随便唱首儿歌”
- “你会唱哪些儿歌”

## 安全

- `.env`、`data/.config.yaml`、虚拟环境、模型文件、日志和旧音乐不会提交。
- 新机器需要自行安装依赖并下载语音模型。
- 不要把 DeepSeek Key、设备凭据或其他私有配置提交到 Git。
