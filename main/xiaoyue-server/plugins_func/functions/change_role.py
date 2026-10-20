from plugins_func.register import register_function, ToolType, ActionResponse, Action
from config.logger import setup_logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler

TAG = __name__
logger = setup_logging()

DEFAULT_ROLE_NAMES = {
    "英语老师": "Lily",
    "好奇小男孩": "小月",
    "小月": "小月",
}

ROLE_ALIASES = {
    "英语老师": "英语老师",
    "英文老师": "英语老师",
    "英语教学": "英语老师",
    "英文教学": "英语老师",
    "学英语": "英语老师",
    "练口语": "英语老师",
    "好奇小男孩": "好奇小男孩",
    "小男孩": "好奇小男孩",
    "小月": "小月",
    "默认角色": "小月",
    "恢复小月": "小月",
}

prompts = {
    "英语老师": """我是一个叫{{assistant_name}}(Lily)的英语老师，我会讲中文和英文，发音标准。
如果你没有英文名，我会给你起一个英文名。
我会讲地道的美式英语，我的任务是帮助你练习口语。
我会使用简单的英语词汇和语法，让你学起来很轻松。
我会用中文和英文混合的方式回复你，如果你喜欢，我可以全部用英语回复。
我每次不会说很多内容，会很简短，因为我要引导我的学生多说多练。
如果你问和英语学习无关的问题，我会拒绝回答。""", 
    "好奇小男孩": """我是一个叫{{assistant_name}}的小男孩，声音稚嫩而充满好奇。
我就像一个知识宝库，儿童读物里的知识我都如数家珍。
从浩瀚的宇宙到地球上的每一个角落，从古老的历史到现代的科技创新，还有音乐、绘画等艺术形式，我都充满了浓厚的兴趣与热情。
我不仅爱看书，还喜欢亲自动手做实验，探索自然界的奥秘。
无论是仰望星空的夜晚，还是在花园里观察小虫子的日子，每一天对我来说都是新的冒险。
我希望能与你一同踏上探索这个神奇世界的旅程，分享发现的乐趣，解决遇到的难题，一起用好奇心和智慧去揭开那些未知的面纱。
无论是去了解远古的文明，还是去探讨未来的科技，我相信我们能一起找到答案，甚至提出更多有趣的问题。""",
}
change_role_function_desc = {
    "type": "function",
    "function": {
        "name": "change_role",
        "description": "当用户想切换角色、进入英语教学模式、恢复小月或更换助手名字时调用。可选角色：[英语老师,好奇小男孩,小月]。用户说“学英语”“练口语”时选择“英语老师”。",
        "parameters": {
            "type": "object",
            "properties": {
                "role": {
                    "type": "string",
                    "description": "要切换的角色，必须是：英语老师、好奇小男孩或小月",
                },
                "role_name": {
                    "type": "string",
                    "description": "可选的新助手名称；不提供时英语老师默认使用 Lily，其他角色默认使用小月",
                },
            },
            "required": ["role"],
        },
    },
}


@register_function("change_role", change_role_function_desc, ToolType.CHANGE_SYS_PROMPT)
def change_role(conn: "ConnectionHandler", role: str, role_name: str = ""):
    """切换角色"""
    requested_role = str(role or "").strip()
    normalized_role = ROLE_ALIASES.get(requested_role, requested_role)
    if normalized_role not in DEFAULT_ROLE_NAMES:
        return ActionResponse(
            action=Action.RESPONSE, result="切换角色失败", response="不支持的角色"
        )

    resolved_name = str(role_name or "").strip() or DEFAULT_ROLE_NAMES[normalized_role]
    if normalized_role == "小月":
        new_prompt = conn.config.get("prompt", "")
        if not new_prompt:
            return ActionResponse(
                action=Action.RESPONSE,
                result="小月提示词缺失",
                response="小月模式暂时不可用",
            )
    else:
        new_prompt = prompts[normalized_role].replace(
            "{{assistant_name}}", resolved_name
        )

    conn.change_system_prompt(new_prompt)
    logger.bind(tag=TAG).info(
        f"准备切换角色:{normalized_role},角色名字:{resolved_name}"
    )
    if normalized_role == "英语老师":
        res = f"英语教学模式已开启，我是{resolved_name}。Let's practice English together!"
    elif normalized_role == "小月":
        res = "已经回到小月模式啦"
    else:
        res = f"切换角色成功，我是{resolved_name}"
    return ActionResponse(action=Action.RESPONSE, result="切换角色已处理", response=res)
