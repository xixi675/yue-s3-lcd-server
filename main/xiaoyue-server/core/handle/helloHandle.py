import time
import json
import uuid
import random
import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler
from core.utils.dialogue import Message
from core.utils.util import audio_to_data
from core.providers.tts.dto.dto import SentenceType
from core.utils.wakeup_word import WakeupWordsConfig
from core.handle.sendAudioHandle import sendAudioMessage, send_tts_message
from core.utils.util import remove_punctuation_and_length, opus_datas_to_wav_bytes
from core.providers.tools.device_mcp import MCPClient, send_mcp_initialize_message

TAG = __name__

# ---------------------------------------------------------------------------
# 小月的唤醒回复，按时间段分组
# 通用句子任何时间都能用；早上、傍晚、晚上各有专属句子
# 晚上只用晚上组，语气轻一点，不用通用组里比较兴奋的句子
# ---------------------------------------------------------------------------
_GENERAL = [
    "哎，小月在呢。今天想玩什么呀？",
    "我在我在，小月来啦。你想听故事还是唱歌呀？",
    "叮咚，小月上线啦。我们一起玩个小游戏好不好？",
    "哇，是你在叫我呀。小月陪你玩，想先做什么呢？",
    "来啦来啦，小月蹦蹦跳跳地来啦。你今天开心吗？",
    "嘿，小月在这儿。你想认识小动物，还是学小儿歌呀？",
    "我听到啦，你的声音真好听。想和小月说什么悄悄话呀？",
]
_MORNING = [
    "早上好呀，小月在呢。你吃过早饭了吗？",
    "太阳公公起床啦，小月也来啦。今天想学点什么呀？",
]
_EVENING = [
    "你好呀，小月来啦。今天在幼儿园开心吗？",
    "小月在呢。今天有没有学到新本领呀？",
]
_NIGHT = [
    "晚上好呀，小月在呢。我们听个小故事好不好？",
    "月亮出来啦，小月陪着你。想听睡前故事吗？",
    "小月在这里。今天辛苦啦，我们轻轻地聊一聊吧。",
]

WAKEUP_GROUPS = {
    "morning": _GENERAL + _MORNING,  # 5:00 - 10:59
    "daytime": _GENERAL,  # 11:00 - 15:59
    "evening": _GENERAL + _EVENING,  # 16:00 - 18:59
    "night": _NIGHT,  # 19:00 - 次日 4:59
}

WAKEUP_CONFIG = {
    # 单位是秒：播放缓存的回复后，如果这条缓存生成已经超过这么久，
    # 就在后台重新随机生成一条新的，留给下一次唤醒用
    "refresh_time": 10,
    # 保留这个字段，兼容其他地方可能的引用
    "responses": _GENERAL + _MORNING + _EVENING + _NIGHT,
}

# 创建全局的唤醒词配置管理器
wakeup_words_config = WakeupWordsConfig()

# 用于防止并发调用wakeupWordsResponse的锁
_wakeup_response_lock = asyncio.Lock()


def _get_period() -> str:
    """按服务器本地时间判断当前时间段"""
    hour = time.localtime().tm_hour
    if 5 <= hour < 11:
        return "morning"
    if 11 <= hour < 16:
        return "daytime"
    if 16 <= hour < 19:
        return "evening"
    return "night"


async def handleHelloMessage(conn: "ConnectionHandler", msg_json):
    """处理hello消息"""
    audio_params = msg_json.get("audio_params")
    if audio_params:
        format = audio_params.get("format")
        conn.logger.bind(tag=TAG).debug(f"客户端音频格式: {format}")
        conn.audio_format = format
        conn.welcome_msg["audio_params"] = audio_params
    features = msg_json.get("features")
    if features:
        conn.logger.bind(tag=TAG).debug(f"客户端特性: {features}")
        conn.features = features
        if features.get("mcp"):
            conn.logger.bind(tag=TAG).debug("客户端支持MCP")
            conn.mcp_client = MCPClient()
        if features.get("aec"):
            conn.logger.bind(tag=TAG).debug("客户端启用了服务端AEC")
            conn.client_aec = True

    await conn.websocket.send(json.dumps(conn.welcome_msg))

    # The device waits for the server hello before processing MCP messages.
    if features and features.get("mcp"):
        asyncio.create_task(send_mcp_initialize_message(conn))


async def checkWakeupWords(conn: "ConnectionHandler", text):
    enable_wakeup_words_response_cache = conn.config[
        "enable_wakeup_words_response_cache"
    ]

    # 等待tts初始化，最多等待3秒
    start_time = time.time()
    while time.time() - start_time < 3:
        if conn.tts:
            break
        await asyncio.sleep(0.1)
    else:
        return False

    if not enable_wakeup_words_response_cache:
        return False

    _, filtered_text = remove_punctuation_and_length(text)
    if filtered_text not in conn.config.get("wakeup_words"):
        return False

    conn.just_woken_up = True
    await send_tts_message(conn, "start")

    # 获取当前音色
    voice = getattr(conn.tts, "voice", "default")
    if not voice:
        voice = "default"

    # 获取唤醒词回复配置
    response = wakeup_words_config.get_wakeup_response(voice)
    current_group = WAKEUP_GROUPS[_get_period()]
    if not response or response.get("text") not in current_group:
        # 缓存可能来自旧版本或已经跨时间段，直接生成一条当前时段的新回复
        await wakeupWordsResponse(conn)
        response = wakeup_words_config.get_wakeup_response(voice)

    if not response or not response.get("file_path"):
        conn.logger.bind(tag=TAG).error("生成唤醒词回复失败")
        return False

    # 获取音频数据
    opus_packets = await audio_to_data(response.get("file_path"), use_cache=False)
    # 播放唤醒词回复
    conn.client_abort = False

    # 将唤醒词回复视为新会话，生成新的 sentence_id，确保流控器重置
    conn.sentence_id = str(uuid.uuid4().hex)

    conn.logger.bind(tag=TAG).info(f"播放唤醒词回复: {response.get('text')}")
    await sendAudioMessage(conn, SentenceType.FIRST, opus_packets, response.get("text"))
    await sendAudioMessage(conn, SentenceType.LAST, [], None)

    # 补充对话
    conn.dialogue.put(Message(role="assistant", content=response.get("text")))

    # 检查是否需要更新唤醒词回复
    if time.time() - response.get("time", 0) > WAKEUP_CONFIG["refresh_time"]:
        if not _wakeup_response_lock.locked():
            asyncio.create_task(wakeupWordsResponse(conn))
    return True


async def wakeupWordsResponse(conn: "ConnectionHandler"):
    if not conn.tts:
        return

    try:
        # 尝试获取锁，如果获取不到就返回
        if not await _wakeup_response_lock.acquire():
            return

        # 获取当前音色
        voice = getattr(conn.tts, "voice", "default")

        # 从当前时间段的回复列表中随机选择，并避开上一次缓存的那一句
        candidates = list(WAKEUP_GROUPS[_get_period()])
        last_response = wakeup_words_config.get_wakeup_response(voice)
        if last_response and len(candidates) > 1:
            last_text = last_response.get("text")
            if last_text in candidates:
                candidates.remove(last_text)
        result = random.choice(candidates)
        if not result or len(result) == 0:
            return

        # 生成TTS音频
        tts_result = await asyncio.to_thread(conn.tts.to_tts, result)
        if not tts_result:
            return

        # 使用链接的sample_rate
        wav_bytes = opus_datas_to_wav_bytes(tts_result, sample_rate=conn.sample_rate)
        file_path = wakeup_words_config.generate_file_path(voice)
        with open(file_path, "wb") as f:
            f.write(wav_bytes)
        # 更新配置
        wakeup_words_config.update_wakeup_response(voice, file_path, result)
    finally:
        # 确保在任何情况下都释放锁
        if _wakeup_response_lock.locked():
            _wakeup_response_lock.release()
