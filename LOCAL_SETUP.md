# 本地小月服务端

## 启动

```powershell
cd D:\airobot\xiaoyue-server
.\start-server.ps1
```

## 地址

- OTA 接口：`http://172.20.10.3:8003/xiaoyue/ota/`
- WebSocket：`ws://172.20.10.3:8000/xiaoyue/v1/`

设备和电脑必须在同一个网络（当前是手机热点网段 172.20.10.x）。

## 配置

配置文件：`main\xiaoyue-server\data\.config.yaml`

DeepSeek Key 保存在本地 `.env`，不会提交到 Git：

```text
DEEPSEEK_API_KEY=你的DeepSeekKey
```

首次部署时从 `.env.example` 复制一份 `.env`。角色身份在 `data\.config.yaml` 的 `prompt` 字段，当前已经设置为“小月”。

## 使用的模块

| 模块 | 选择 | 说明 |
| --- | --- | --- |
| LLM | DeepSeekLLM | DeepSeek 云端大模型 |
| ASR | SherpaASR | 本地 SenseVoiceSmall，免 Key |
| TTS | EdgeTTS | 免费语音合成 |
| VAD | SileroVAD | 本地 ONNX 模型 |
| 记忆 / 意图 | nomem / function_call | 支持本地儿歌点播 |

## 本地儿歌库

儿歌放在 `main\xiaoyue-server\music\儿歌\`，支持 `.wav` 和 `.mp3`。当前内置小星星、两只老虎、拍拍手、数一数、洗手歌、晚安小月亮。

可以说“唱小星星”“我想听两只老虎”“随便唱首儿歌”或“你会唱哪些儿歌”。添加自己的歌曲时，把音频放进这个目录，文件名就是点歌名称。

## 内容过滤

词库文件：`main\xiaoyue-server\config\sensitive_words.yaml`

支持三类动作：

- `block`：直接拦截，回复安全话术
- `replace`：命中的词替换成 `***`
- `audit`：只写日志，不拦截（适合童话、剧情类分级）

已内置分类：色情低俗、脏话辱骂、暴力血腥、恐怖惊悚、自伤危险、毒赌违禁、政治敏感（留空待专业词库）、迷信邪教、隐私诱导、广告引流、歧视攻击。

`allow_words` 用于放行童话内容，例如大灰狼、小红帽、狼外婆。

修改词库后不需要重启服务端，下一次检查会自动重新加载。

快速验证：

- 说“加我微信” → 被广告规则拦截
- 说“我的手机号是13800138000” → 被隐私规则拦截
- 说“大灰狼来了” → 正常放行
- 说“你这个智障” → 被歧视规则拦截

说明：这是关键词 + 正则的第一层过滤。政治敏感、色情低俗等高风险类别建议再接入专业内容审核服务或维护合规词库。

## 本地 RAG 知识库

服务端已内置本地 RAG，不需要 Docker、RAGFlow 或额外的 Embedding API。

### 放资料

把文档放进：

```text
D:\airobot\xiaoyue-server\main\xiaoyue-server\data\knowledge\
```

支持格式：`.txt`、`.md`、`.markdown`、`.csv`、`.json`、`.pdf`。

### 建立/重建知识库

```powershell
cd D:\airobot\xiaoyue-server\main\xiaoyue-server
.\.venv\Scripts\python.exe scripts\rag_ingest.py
```

生成的数据库：`data\knowledge.db`。

### 工作方式

每次用户提问时，服务端会自动从知识库检索最相关的片段，并注入 DeepSeek 上下文。资料里没有答案时，提示词要求模型明确说不知道，不要编造。

配置在 `data\.config.yaml`：

```yaml
rag:
  enabled: true
  top_k: 4
```

不想用 RAG 时把 `enabled` 改成 `false`。

## 儿童内容库格式

推荐使用 JSON 文件，一个文件可以放多条内容。模板在：

```text
D:\airobot\xiaoyue-server\内容模板.json
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `title` | 内容标题 |
| `type` | 儿歌、故事、认知、英语、生活常识 |
| `category` | 更细的分类，例如儿歌童谣、古诗、睡前故事、颜色认知 |
| `difficulty` | 简单、中等、困难 |
| `tags` | 标签数组，方便检索 |
| `content` | 正文 |
| `pinyin` | 拼音，可选 |
| `explanation` | 讲解，可选 |

示例：

```json
{
  "items": [
    {
      "title": "小星星",
      "type": "儿歌",
      "category": "儿歌童谣",
      "difficulty": "简单",
      "tags": ["星星", "夜晚", "唱歌"],
      "content": "一闪一闪亮晶晶，满天都是小星星。",
      "pinyin": "yī shǎn yī shǎn liàng jīng jīng",
      "explanation": "一首适合小朋友的儿歌。"
    }
  ]
}
```

把填好的 JSON 放进 `data\knowledge\`，然后重新导入：

```powershell
cd D:\airobot\xiaoyue-server\main\xiaoyue-server
.\.venv\Scripts\python.exe scripts\rag_ingest.py
```

服务端会自动识别用户问题里的类型和难度：

- “推荐一首儿歌” → 找 `type=儿歌` 的内容
- “讲个睡前故事” → 找 `type=故事` 的内容
- “红灯停绿灯行” → 优先按标题匹配
- “三只小猪” → 直接返回《三只小猪》

示例内容库在 `data\knowledge\示例-儿童内容库.json`，确认流程后可以删除它，换成你自己的内容并重新导入。
