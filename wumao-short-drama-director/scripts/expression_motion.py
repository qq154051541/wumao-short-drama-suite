#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
expression_motion.py · 表情 / 动作成品提示词库引擎（V1.1.0 套装）

定位：
  `facs-micro-expression.md` 决定「哪块肌肉动」（AU 配方），`blocking-direction.md` /
  `acting-direction.md` 决定「怎么站、怎么走、为什么这么动」。
  本引擎负责第三件事：**把决定翻译成一句可直接粘进投喂正文的中文成品短语**。

  三条公式（唯一拼装规则，权威 = references/expression-motion-prompt-bank.md）：
    ① 微表情五件套：微表情 + 眼神落点 + 嘴角变化 + 呼吸停顿 + 小动作
    ② 五官分镜六段式：眉 -> 眼 -> 瞳 -> 鼻 -> 唇 -> 脸颊
    ③ 动作槽位式：  角色 + 站姿/移动/情绪/双人/战斗/职业/剧情/镜头 八套变体

四库：
    E01~E50  micro   情绪场景型微表情（50 组 · 电影级近距离特写向）
    F01~F54  facial  五官分镜型漫剧夸张表情（6 卷 × 9 条）
    A001~A100 action 日常/情绪/移动/打斗/手部/恋爱/职场/自然/奇幻/爆发 十类动作（100 条）
    P01~P100 pose   站姿/移动/氛围/压迫/情绪/双人/战斗/职业/钩子/镜头 十册（100 条）

用法：
    python3 scripts/expression_motion.py --list micro|facial|action|pose
    python3 scripts/expression_motion.py --query "委屈 攥紧 走廊"
    python3 scripts/expression_motion.py --state project_state.json --annotate
    python3 scripts/expression_motion.py --state project_state.json --out annotated.json
    python3 scripts/expression_motion.py --self-test
"""
import argparse
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BANK_PATH = os.path.join(SCRIPT_DIR, "expression_motion_bank.json")

# ------------------------------------------------------------------ 公式常量
# ③ 动作槽位式八套变体（逐字取自 references/expression-motion-prompt-bank.md §二·2）
FORMULAS = {
    "pose_stand": "角色 + 站姿 + 手部动作 + 视线方向 + 镜头 + 环境光",
    "move": "角色 + 移动方向 + 步伐节奏 + 衣摆动态 + 跟拍方式 + 环境光",
    "atmos": "角色 + 身体倾角 + 手部位置 + 眼神状态 + 镜头距离 + 氛围光",
    "press": "角色 + 身体姿态 + 手部位置 + 头部方向 + 镜头 + 光影压迫感",
    "emotion": "眼神 + 眉形 + 嘴角 + 肩部状态 + 手部动作 + 呼吸感 + 镜头距离",
    "duo": "人物A动作 + 人物B反应 + 接触位置 + 距离 + 视线 + 镜头运动",
    "combat": "起始姿势 + 攻击方向 + 脚步重心 + 动作轨迹 + 镜头速度 + 冲击效果",
    "career": "职业 + 制服/服装 + 专业工具 + 标准动作 + 真实工作场景",
    "hook": "角色 + 身体姿态 + 手部动作 + 头部方向 + 镜头 + 光影氛围",
    "camera": "人物动作 + 摄影机位置 + 移动方向 + 运动速度 + 景别变化 + 情绪表达",
}
FORMULA_DESC = {
    "pose_stand": "基础入场站姿 / 角色出场第一眼",
    "move": "走、跑、停、转场移动",
    "atmos": "氛围感姿态 / 唯美空镜人物",
    "press": "上位者压迫感 / 强势气场",
    "emotion": "情绪反应特写 / 情绪落点",
    "duo": "双人互动 / 关系推进",
    "combat": "打戏 / 追逐 / 爆发",
    "career": "行业职业动作 / 职场戏",
    "hook": "前 3 秒钩子 / 高潮段落",
    "camera": "运镜与景别变化设计",
}

# ② 五官分镜六段式（expr2 原文页脚口径）
FACE_ORDER = ("眉", "眼", "瞳", "鼻", "唇", "脸颊")

# ① 微表情五件套（expr1 原文口径）
MICRO_SLOT_ORDER = ("face", "gaze", "mouth", "breath", "small")
MICRO_SLOT_LABEL = {
    "face": "微表情", "gaze": "眼神落点", "mouth": "嘴角变化",
    "breath": "呼吸停顿", "small": "小动作",
}

# 修饰词：命中后从动作名里剔除，剩下的才是「动作本体」，避免「缓缓喝咖啡」只匹配到「缓缓」
_ADVERBS = ("缓缓", "慢慢", "轻轻", "微微", "骤然", "忽然", "猛地", "猛然", "突然",
            "快速", "用力", "随意", "自然地", "快步", "小跑", "大步", "缓缓地")

# 同义词表：把剧本/分镜里最常见的口语触发词映射到库里条目
SYNONYMS = {
    # —— 情绪（micro）——
    "委屈": "强忍委屈", "强忍": "强忍委屈", "想哭": "强忍委屈", "忍泪": "强忍委屈",
    "假装": "假装镇定", "镇定": "假装镇定", "强撑": "假装镇定", "背锅": "假装镇定",
    "秘密": "秘密被戳破", "戳破": "秘密被戳破", "身份暴露": "秘密被戳破",
    "心动": "忽然心动", "愣住": "忽然心动", "耳根红": "忽然心动",
    "冷淡": "强装冷淡", "嘴硬": "强装冷淡", "半垂": "强装冷淡",
    "怒": "怒意压住", "压怒": "怒意压住", "咬牙": "怒意压住",
    "重逢": "失而复得", "失而复得": "失而复得", "久别": "失而复得",
    "心虚": "心虚躲闪", "躲闪": "心虚躲闪", "撒谎": "心虚躲闪", "隐瞒": "心虚躲闪",
    "冷笑": "冷笑反击", "反击": "冷笑反击", "打脸": "冷笑反击",
    "不甘": "不甘认输", "认输": "不甘认输", "爆发": "不甘认输",
    "欲言又止": "欲言又止", "话到嘴边": "欲言又止", "表白": "欲言又止",
    "坏消息": "听到坏消息", "噩耗": "听到坏消息", "战败": "听到坏消息",
    "识破": "识破谎言", "谎言": "识破谎言", "权谋": "识破谎言",
    "心疼": "心疼不敢靠近", "不敢靠近": "心疼不敢靠近", "探望": "心疼不敢靠近",
    "吃醋": "轻微吃醋", "醋意": "轻微吃醋",
    "误会解除": "误会解除", "和好": "误会解除",
    "温柔": "被温柔击中", "心动瞬间": "被温柔击中",
    "悔意": "悔意涌上", "后悔": "悔意涌上",
    "破防": "破防瞬间", "最疼的一句": "破防瞬间",
    "执念": "放下执念", "反派": "放下执念",
    "试探": "邪魅试探", "危险暧昧": "邪魅试探",
    "疏离": "礼貌疏离", "假面": "礼貌疏离",
    "审视": "压迫感审视", "问责": "压迫感审视",
    "黑化": "黑化前一秒", "熄灯": "黑化前一秒",
    "无辜": "伪装无辜", "绿茶": "伪装无辜",
    "胜券在握": "胜券在握", "布局": "胜券在握",
    "杀意": "杀意一闪", "暗杀": "杀意一闪",
    "被将": "被反将一军", "翻车": "被反将一军",
    "疯": "疯感失控", "疯批": "疯感失控", "执念崩塌": "疯感失控",
    "怜悯": "高位者怜悯", "帝王": "高位者怜悯", "掌门": "高位者怜悯",
    "白月光": "白月光回眸", "初恋": "白月光回眸",
    "病弱": "病弱强撑", "虚弱": "病弱强撑",
    "魔尊": "魔尊冷情", "淡漠": "魔尊冷情", "蝼蚁": "魔尊冷情",
    "威压": "仙门威压", "宗门": "仙门威压",
    "记忆苏醒": "记忆苏醒", "前世": "记忆苏醒",
    "宿命": "宿命感心动", "命定": "宿命感心动",
    "克制": "师徒克制", "禁忌": "师徒克制",
    "悲悯": "神女悲悯", "牺牲": "神女悲悯",
    "蛊惑": "妖族蛊惑", "魅惑": "妖族蛊惑",
    "忍痛": "剑修忍痛", "战损": "剑修忍痛",
    "诀别": "忍痛告别", "放手": "忍痛告别",
    "死里逃生": "死里逃生", "追杀": "死里逃生",
    "默默守护": "默默守护", "守护": "默默守护",
    "旧爱": "旧爱相见", "重逢修罗": "旧爱相见",
    "熟悉的声音": "听见熟悉声音", "回忆": "听见熟悉声音",
    "旧物": "看到旧物", "遗物": "看到旧物", "定情信物": "看到旧物",
    "不服输": "战损不服输", "反杀": "战损不服输",
    "大梦初醒": "大梦初醒", "穿越醒来": "大梦初醒",
    "原谅": "最后原谅", "和解": "最后原谅",
    "释然": "终局释然", "大结局": "终局释然",

    # —— 运镜（cam_move / cam_basic · P16 新增）——
    "追车": "疾速追尾镜", "追逐": "疾速追尾镜", "贴身跟拍": "疾速追尾镜",
    "跟拍距离": "疾速追尾镜", "第一视角": "疾速追尾镜",
    "跳崖": "飞跃俯冲镜", "跳伞": "飞跃俯冲镜", "俯冲": "飞跃俯冲镜", "速度线": "飞跃俯冲镜",
    "肉搏": "打斗穿梭镜", "对拳": "打斗穿梭镜", "交战": "打斗穿梭镜",
    "大招": "旋转攻击镜", "范围伤害": "旋转攻击镜", "环绕旋转": "旋转攻击镜",
    "闪避": "躲避晃动镜", "颠簸": "躲避晃动镜",
    "子弹时间": "时间凝滞镜", "时间静止": "时间凝滞镜", "绝杀": "时间凝滞镜",
    "形状匹配": "匹配形状转场", "车轮齿轮": "匹配形状转场",
    "遮挡转场": "遮挡切换转场", "前景遮挡": "遮挡切换转场",
    "视线转场": "视线引导转场", "眼神引导": "视线引导转场",
    "色调转场": "色彩渐变转场", "冷暖切换": "色彩渐变转场",
    "空间穿越": "空间折叠镜", "梦境潜入": "空间折叠镜", "维度": "空间折叠镜",
    "残影": "分身残像镜", "分身": "分身残像镜", "极速移动": "分身残像镜",
    "透视内构": "穿透透视镜", "剖面": "穿透透视镜", "机械内构": "穿透透视镜",
    "回忆杀": "记忆闪回镜", "闪回": "记忆闪回镜", "身世": "记忆闪回镜",
    "蒙太奇": "多镜组合序列", "开场序列": "多镜组合序列", "史诗感": "多镜组合序列",
    "水平摇": "水平摇", "俯仰": "俯仰", "变焦": "变焦", "移动机位": "移动机位", "横向跟随": "横向跟随",
    "Pan": "水平摇", "Tilt": "俯仰", "Zoom": "变焦", "Dolly": "移动机位", "Truck": "横向跟随",

    # —— 动作（action / pose）——
    "喝咖啡": "坐在椅子上缓缓喝咖啡", "看手机": "低头看手机", "玩手机": "低头看手机",
    "看书": "伸手拿起桌上的书本", "拿书": "伸手拿起桌上的书本",
    "整理头发": "抬手整理耳边碎发", "碎发": "抬手整理耳边碎发",
    "点头": "微笑着轻轻点头回应", "回应": "微笑着轻轻点头回应",
    "吃饭": "端起碗筷开始吃饭", "碗筷": "端起碗筷开始吃饭",
    "弯腰": "弯腰捡起掉落的物品", "捡起": "弯腰捡起掉落的物品",
    "推门": "推开房门缓步走入", "进门": "推开房门缓步走入",
    "窗边": "站在窗边望向远方", "望远方": "站在窗边望向远方",
    "抽屉": "伸手拉开抽屉寻找物品",
    "注视": "眼神温柔地注视对方", "爱意": "眼神温柔地注视对方",
    "低头": "低下头，眼眶逐渐湿润", "湿润": "低下头，眼眶逐渐湿润",
    "瞪大双眼": "突然瞪大双眼，露出震惊表情", "震惊": "突然瞪大双眼，露出震惊表情",
    "皱眉": "紧皱眉头，缓缓握紧拳头", "握拳": "紧皱眉头，缓缓握紧拳头",
    "捂住嘴": "捂住嘴巴，难以置信地后退", "后退": "捂住嘴巴，难以置信地后退",
    "擦眼泪": "转过身去，偷偷擦拭眼泪", "背对镜头": "转过身去，偷偷擦拭眼泪",
    "深呼吸": "深吸一口气，缓缓闭上双眼", "闭眼": "深吸一口气，缓缓闭上双眼",
    "行走": "沿着街道自然地向前行走", "走路": "沿着街道自然地向前行走",
    "穿过人群": "快步穿过拥挤的人群", "人群": "快步穿过拥挤的人群",
    "转身": "缓缓转身，衣摆随动作摆动", "回眸": "缓缓转身，衣摆随动作摆动",
    "追赶": "小跑着追赶前方的人",
    "摔倒": "跟跑后退几步险些摔倒", "失去平衡": "跟跑后退几步险些摔倒",
    "跨过": "近步跨过地上的障碍物",
    "犹豫": "走到门前，停下脚步犹豫", "门把手": "走到门前，停下脚步犹豫",
    "猛然回头": "猛然回头，寻找身后的声音", "警惕回头": "猛然回头，寻找身后的声音",
    "迎风": "迎着风大步向前走去", "大风": "迎着风大步向前走去",
    "走向镜头": "缓缓走向镜头，目光直视前方",
    "挥拳": "猛烈挥拳，朝对手方向打去", "闪避": "侧身闪避迎面袭来的攻击",
    "跃起": "腾空跃起，在空中旋身踢腿", "踢腿": "腾空跃起，在空中旋身踢腿",
    "拔剑": "快速拔剑，横剑挡住攻击", "格挡": "快速拔剑，横剑挡住攻击",
    "劈下": "双手握刀，蓄力后奋力劈下", "蓄力": "双手握刀，蓄力后奋力劈下",
    "翻滚": "向后翻滚，迅速起身反击",
    "抓手腕": "伸手抓住对手手腕，顺势推开",
    "挥剑": "连续挥剑，快速完成数次攻防",
    "单膝跪地": "单膝跪地稳住身形，再次起身",
    "收剑": "收剑入鞘，转身冷静离去", "入鞘": "收剑入鞘，转身冷静离去",
    "敲桌面": "手指轻轻敲击桌面", "敲击": "手指轻轻敲击桌面",
    "握紧": "缓缓握紧手中的信件", "信件": "缓缓握紧手中的信件",
    "抚摸": "指尖轻抚照片上的人物", "照片": "指尖轻抚照片上的人物",
    "花瓣": "伸手接住空中飘落的花瓣",
    "擦泪": "用拇指轻轻擦去脸上的泪水",
    "松拳": "慢慢松开紧握的拳头",
    "剑身": "手指轻轻划过剑身",
    "戒指": "将戒指缓缓戴上手指",
    "触碰脸颊": "伸手轻触对方的脸颊",
    "摊开": "掌心缓缓摊开，露出戴着的物品",
    "四目相对": "两人四目相对，缓缓靠近", "靠近": "两人四目相对，缓缓靠近",
    "低头脸红": "害羞地低下头，脸颊微微泛红", "娇羞": "害羞地低下头，脸颊微微泛红",
    "牵手": "轻轻牵起对方的手", "牵手了": "轻轻牵起对方的手",
    "拥抱": "张开双臂，将对方拥入怀中",
    "依偎": "依偎在对方肩头，轻轻闭上眼睛",
    "整理衣领": "伸手替对方整理衣领",
    "抬下巴": "轻轻抬起对方的下巴",
    "手停住": "伸出手，却在即将触碰时停下",
    "回头张望": "转身离开，又忍不住回头张望",
    "并肩": "两人并肩向前走，手指逐渐交握",
    "敲键盘": "坐在电脑前快速敲击键盘", "键盘": "坐在电脑前快速敲击键盘",
    "翻文件": "翻阅文件，认真核对内容",
    "讲解": "站在会议室前自信讲解方案",
    "推眼镜": "抬手推了推眼镜，目光变得锐利",
    "合上文件夹": "合上文件夹，起身离开会议室",
    "回消息": "拿起手机，快速回复消息",
    "重放文件": "将文件重放在桌上表达不满",
    "插口袋": "站在落地窗前，双手插入口袋",
    "整理桌面": "整理桌面，将文件分类摆放",
    "进办公室": "走进办公室，迎面接受众人注视",
    "雨中抬头": "站在雨中，缓缓抬头望向天空",
    "接雪花": "伸手接住飘落的雪花",
    "风吹起": "长发被微风轻轻吹起", "微风": "长发被微风轻轻吹起",
    "海边": "坐在海边，望着远处的海浪",
    "遮阳": "抬手遮挡夕阳，眯眼眺望远方",
    "落叶": "踩过落叶铺满的小路",
    "摸花": "轻轻抚摸盛开的花朵",
    "躺草地": "在草地上缓缓躺下，望向天空",
    "撑伞": "撑开雨伞，迈步走进雨幕",
    "山顶": "站在山顶张开双臂，迎接山风",
    "凝聚能量": "缓缓抬起双手，掌心凝聚发光能量",
    "悬浮": "双脚离地，身体缓缓悬浮",
    "冲击波": "手臂前一挥，释放能量冲击波",
    "结印": "双手快速结印，周身浮现符文",
    "旋转": "身体旋转，衣袍随气流剧烈翻飞",
    "召回武器": "伸手召回远处悬浮的武器",
    "瞬移": "突然瞬移至对手身后",
    "撑地": "单手撑地，爆发力量震开周围尘土",
    "异样光芒": "双眼逐渐亮起异样光芒",
    "光翼": "缓缓张开双臂，身后展开巨大的光翼",
    "转身质问": "猛然转身，怒声质问对方",
    "闯入": "一把推开房门，大步闯入",
    "杯子滑落": "震惊之下，手中的杯子突然滑落",
    "站起身": "猛地站起身，椅子向后滑动",
    "指向对方": "抬手指向对方，眼神充满愤怒",
    "冲向前": "猛然冲向前方，衣摆剧烈摆动",
    "接住坠落": "在千钧一发之际，伸手接住坠落之物",
    "意味深长": "缓缓抬起头，露出意味深长的笑容",
    "回眸": "背对镜头站立，随后缓缓回眸",
    "动作停止": "动作突然停止，目光直视镜头",
}

# ------------------------------------------------------------------ 工具
_BANK = None
_SHINGLE_CACHE = {}
_CHAR_CACHE = {}

# 功能词与高频虚词：做字符重合度时必须剔除，否则「的/了/在/是」会让所有条目都沾边
STOP_CHARS = set("的了是在有和就不人都一个上也很到说要去你我他会着没看好自己这那什么怎么这样吧与及其对于把被从但如若则所以因为可以能够以及等等我们你们他们自己一点什么样子时候怎么这样那样这个那个不是没有就是还会要去做来去说个只把被让给向于再又更最都很非常真的好像仿佛似乎似乎".replace(" ", ""))

# 过泛的二字词，做分片命中时直接剔除（否则「站在」「双手」「表情」会命中一切）
STOP_SHINGLES = {
    "人物", "女生", "男生", "女主", "男主", "表情", "动作", "自然", "眼神", "看着",
    "站在", "双手", "身体", "周围", "画面", "镜头", "一个", "一条", "眼睛", "嘴巴",
    "微微", "轻轻", "缓缓", "慢慢", "猛地", "缓缓地", "动作自", "然流畅",
}


def bank():
    global _BANK
    if _BANK is None:
        with open(BANK_PATH, encoding="utf-8") as f:
            _BANK = json.load(f)
    return _BANK


def _strip_adverbs(name):
    out = name
    for a in _ADVERBS:
        out = out.replace(a, "")
    return out


FAMILIES = ("micro", "facial", "action", "pose", "cam_move", "cam_basic", "image", "portrait")


def _triggers(entry):
    """从条目里抽出可匹配的触发词。"""
    name = entry.get("name", "")
    trg = set()
    if name:
        trg.add(name)
        # 「瞳孔骤缩式惊骇」-> 拆出「瞳孔骤缩」与「惊骇」
        for part in re.split(r"[式·\-—、，,]", name):
            part = part.strip()
            if len(part) >= 2:
                trg.add(part)
        core = _strip_adverbs(name)
        if len(core) >= 2:
            trg.add(core)
            for part in re.split(r"[，,、；;]", core):
                part = part.strip()
                if len(part) >= 2:
                    trg.add(part)
    # 英文术语（en）也是内部检索键：编导常直接搜 "Bullet Time" / "Match Cut"
    if entry.get("en"):
        trg.add(entry["en"])
        for part in re.split(r"[\s/&]+", entry["en"]):
            if len(part) >= 3:
                trg.add(part)
    # 提示词里的高辨识度名词（3~4 字），兜住「动作名不含关键词」的情况。
    # 全族统一只有唯一成品字段 prompt。
    prompt = (entry.get("prompt") 
              or entry.get("prompt") or "")
    for tok in re.findall(r"[一-龥]{3,4}", prompt[:200]):
        if tok not in ("表情自然", "眼神柔和"):
            trg.add(tok)
    # 适用场景 / 类别 / 册名：口语触发词常常只出现在「适用场景」里
    # （例：E09 冷笑反击 的 use = "打脸、强势反击" ——「打脸」两个字库名里根本没有）
    for extra in (entry.get("use", ""), entry.get("cat", ""), entry.get("book", "")):
        for part in re.split(r"[、，,；;·]", extra or ""):
            part = part.strip()
            if len(part) >= 2:
                trg.add(part)
    return sorted(trg, key=len, reverse=True)


def _shingles(entry):
    """把触发词切成可命中的分片（长片优先），结果缓存。

    ⚠️ 必须生成**所有长度**（2 ~ min(len,6)）的分片，不能只生成最长那一档：
    「猛然回头」若只留 4 字分片，文本里写「回头张望」就永远匹配不上
    （2026-11-15 实测：P58 争执对峙 因只有「争执对峙」整词而漏召回）。
    误召回由**打分**兜住——最长命中优先，短的只在前者没命中时才生效。
    """
    key = entry["id"]
    cached = _SHINGLE_CACHE.get(key)
    if cached is not None:
        return cached
    best = {}
    for t in _triggers(entry):
        if len(t) < 2:
            continue
        # ★英文术语**不切片**：「Dolly」切成 "Do"/"oll"/"ll" 会误命中
        #   「Dodge & Shake」「Bullet Time」等一堆不相关条目（2026-11-15 实测）。
        #   英文只做整词匹配，分值封在 4 字档，避免长英文压过中文实证命中。
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 &/&\-]*", t):
            if len(t) >= 3 and t not in best:
                best[t] = min(len(t), 4) * 10
            continue
        for n in range(min(len(t), 6), 1, -1):
            for i in range(0, len(t) - n + 1):
                sh = t[i:i + n]
                if sh in STOP_SHINGLES:
                    continue
                if n * 10 > best.get(sh, 0):
                    best[sh] = n * 10
    out = sorted(((sh, n) for sh, n in best.items()), key=lambda x: -x[1])
    _SHINGLE_CACHE[key] = out
    return out


def _entry_index(family):
    return bank().get(family, [])


def _char_set(entry):
    """条目的有效字符集合（名字 + 成品短语，去功能词），用于字符重合度兜底打分。"""
    key = entry["id"]
    cached = _CHAR_CACHE.get(key)
    if cached is not None:
        return cached
    src = (entry.get("name", "") or "") + (entry.get("prompt")  or "")
    cs = {c for c in src if "\u4e00" <= c <= "\u9fff" and c not in STOP_CHARS}
    _CHAR_CACHE[key] = cs
    return cs


def _score(entry, text):
    """在 text 里找最长匹配，返回 (分值, 命中词)。

    分片分 = 长度 × 10（2 字=20 / 4 字=40 / 6 字=60）——**长片绝对优先**，
    这样「猛然回头」不会被「回头」这种短片抢走。
    字符重合分 = 重合数 × 12（**≥3 字才计**，否则纯属噪声）——兜住
    「瞳孔骤缩」↔「瞳孔骤紧」这种**同义不同字**的近邻命中（分片匹配对这类无能为力）。
    两者取大，不相加：相加会让噪声条目虚高。
    """
    best = (0, "")
    for sh, n in _shingles(entry):
        if sh and sh in text:
            best = (n, sh)          # n 已是分值（中文片长×10 / 英文整词封顶 40）
            break
    cs = _char_set(entry)
    if cs:
        overlap = len(cs & _text_chars(text))
        # ⚠️ **重合数封顶 3**：否则长条目（F 族一条 60+ 字）会靠字数堆出高重合，
        #    系统性地压过短条目（E 族 15 字）——那是长度偏置，不是相关性。
        #    封顶后，长条目只能与短条目「同分」，再由分片命中分出高下。
        if overlap >= 3:
            cand = (min(overlap, 3) * 12, "字符重合×%d" % min(overlap, 3))
            if cand[0] > best[0]:
                best = cand
    return best


def _text_chars(text):
    return {c for c in text if "\u4e00" <= c <= "\u9fff"}


def _syn_hits(text):
    """扫描文本里的同义词触发词，返回 [(分值, 词, 目标条目名)]。

    同义词分 = 字数 × 6，**刻意低于同长度分片分（×10）**——
    同义词只在分片完全没命中时顶上来，绝不压过更长的实证命中（防误召回）。
    """
    out = []
    for word, target in SYNONYMS.items():
        if word in text:
            out.append((len(word) * 6, word, target))
    out.sort(key=lambda x: -x[0])
    return out


def find(family, text, limit=3, min_score=2):
    """在自由文本里检索表情/动作条目，返回按分值降序的条目列表 [(条目, 命中词)]。

    打分 = 分片最长命中（同长度按条目号稳定排序），
    同义词表命中额外加权（保证「吃醋」「吃雹」「打脸」这类口语能直接命中库里条目）。
    """
    if not text:
        return []
    syn = {t: (s, w) for s, w, t in _syn_hits(text)}
    hits = []
    for e in _entry_index(family):
        s, w = _score(e, text)
        tgt = e.get("name")
        if tgt in syn:
            ss, sw = syn[tgt]
            if ss > s:
                s, w = ss, sw
        if s >= min_score:
            hits.append((s, w, e))
    hits.sort(key=lambda x: (-x[0], x[2]["id"]))
    out = []
    for s, w, e in hits[:limit]:
        e["_score"] = s          # 置信度随条目带出（仅内存态，不回写 bank.json）
        out.append((e, w))
    return out


def find_by_name(family, name, limit=1):
    """按条目名精确/模糊取条目（支持 'E01'、'强忍委屈'、'瞳孔骤缩式惊骇'）。"""
    out = []
    for e in _entry_index(family):
        if e["id"].lower() == str(name).lower() or e["name"] == name:
            out.append(e)
            if len(out) >= limit:
                return out
    return out


def find_by_synonym(word):
    """同义词 -> 条目（跨 micro/action/pose 三族）。"""
    tgt = SYNONYMS.get(word)
    if not tgt:
        return []
    for family in ("micro", "action", "pose"):
        r = find_by_name(family, tgt)
        if r:
            return r
    return []


# ------------------------------------------------------------------ 组装
# 与 scripts/validate_prompt.py 的 C25_BLAND_FACE **同表**（两份必须同步，
# 否则成品短语会被自家机检 C25a 拦下——2026-11-15 端到端实测踩过：
# 「表情平静而坚定」「表情复杂」直接被 C25a 判为抽象神态词）。
C25_BLAND = ("表情平静", "神色复杂", "神情复杂", "面露", "眼神凌厉", "无表情",
             "神色平静", "表情复杂", "一脸平静", "神色凝重", "表情严肃", "神情平静")
FACE_PREFIX = ("表情", "神情", "神色", "神态")
CONCRETE = ("眼", "眉", "嘴", "唇", "牙", "鼻", "颊", "脸", "头", "肩", "手", "指",
            "身", "脚", "腰", "发", "耳", "喉", "胸", "视", "光", "瞳", "呼吸")


def scrub_bland(s):
    """剥离抽象神态词（结果词），只留看得见的肌肉/身体动作。

    ① 命中 C25_BLAND 同表的词 -> 整片删（含「面露不悦」这类变体）；
    ② 以「表情/神情/神色/神态」起头、且**不含任何具体器官词**的片 -> 整片删
       （「表情凶狠」「神情专注」「神态自然」是结果词；「眼神柔和」含器官词，保留）。
    """
    if not s:
        return s
    frags = [f.strip() for f in re.split(r"[，,；;。]", s) if f.strip()]
    out = []
    for f in frags:
        if any(w in f for w in C25_BLAND):
            continue
        if any(f.startswith(p) for p in FACE_PREFIX) and not any(c in f for c in CONCRETE):
            continue
        out.append(f)
    return "，".join(out)


def strip_subject(s):
    """剥掉硬编码的性别主体——主体由镜行的「画面主体」提供，短语只管「做什么」。"""
    if not s:
        return s
    return re.sub(r"^(女主|女生|男主|男生)\s*[，,]?\s*", "", s.strip())


def _clean_body(s):
    return strip_subject(scrub_bland(s)).strip("，,；;。 ")


def expression_clause(source, label="面部"):
    """把表情条目组装成一句可直接进投喂正文的短语。

    source: micro 条目 / facial 条目 / 条目名 / id / 列表
    返回：'面部：眼尾泛红、眉心松又拧、视线滑开、嘴角下压'
    规则：micro 族按五件套槽位顺序拼（微表情→眼神落点→嘴角变化→呼吸停顿→小动作）；
          facial 族整体输出（五官分镜六段式本身已是一条完整描述）。
    """
    entries = _as_entries(source, "micro")
    chunks = []
    for e in entries:
        if e["family"] == "facial":
            body = _clean_body(e.get("prompt") or e["prompt"])
            if body:
                chunks.append(body)
            continue
        slots = e.get("slots") or {}
        for key in MICRO_SLOT_ORDER:
            v = _clean_body(slots.get(key) or "")
            if v:
                chunks.append(v)
    if not chunks:
        return ""
    seen, uniq = set(), []
    for c in chunks:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return "%s：%s" % (label, "、".join(uniq))


def motion_clause(source, label="动作"):
    """把动作条目组装成一句可直接进投喂正文的短语。"""
    entries = _as_entries(source, "action")
    chunks = []
    for e in entries:
        if e["family"] == "pose":
            body = e.get("prompt")  or ""
        else:
            body = e.get("prompt") or e.get("prompt") or ""
        body = _clean_body(body)
        if body:
            chunks.append(body)
    if not chunks:
        return ""
    return "%s：%s" % (label, "，".join(chunks))


def formula_clause(key, **slots):
    """按动作槽位式公式拼一句（未给的槽位直接略过，不写空槽）。"""
    if key not in FORMULAS:
        raise KeyError("未知公式键：%s（可选：%s）" % (key, " / ".join(sorted(FORMULAS))))
    parts = []
    for k, v in slots.items():
        if v:
            parts.append(str(v))
    if not parts:
        return ""
    return "%s：%s" % (FORMULAS[key].split(" + ")[0], "，".join(parts))


def camera_clause(source):
    """把运镜条目转成**可直接进 P4 投喂正文**的中文写法 + 机检接线信息。

    返回 dict（不是字符串），因为运镜必须同时给出三样东西：
      body   —— 中文画面描述（进镜行正文，**英文术语已被剔除**，见 C12）
      spec   —— 本包 CAM_FAMILIES 认得的中文运镜词（进镜行头 spec 槽，
                否则 C18g 会报「镜行未标注运镜」）
      guard  —— 本包冲突裁决 / 禁用提醒（人读，不进稿）
      route  —— 若该手法已有权威，给指针（不另立规则）
    """
    e = (_as_entries(source, "cam_move") or [None])[0]
    if not e:
        return {}
    return {
        "id": e.get("id"),
        "name": e.get("name"),
        "en_internal": e.get("en", ""),
        "body": (e.get("prompt") or "").strip(),
        "spec": e.get("fam", ""),
        "param": e.get("param", ""),
        "guard": e.get("guard", ""),
        "route": e.get("route", ""),
    }


def asset_clause(source, label="出图"):
    """把生图条目按**万能六槽公式**拼成一句 P2 出图提示词。

    ⚠️ 产出**只用于 P2/P2.5 资产出图**，⛔ 不得进 P4 视频投喂正文
    （C12 / C25 / 中英混排禁令只管视频投喂稿，不管静态出图提示词）。
    """
    entries = _as_entries(source, "image")
    parts = []
    for e in entries:
        p = (e.get("prompt") or "").strip().rstrip("。")
        if p:
            parts.append(p)
    if not parts:
        return ""
    return "%s：%s" % (label, "；".join(parts))


def formula_table():
    """返回 11 套公式：10 套动作槽位式 + 1 套生图万能六槽。"""
    d = dict(FORMULAS)
    d["image"] = bank().get("image_formula", "主体 + 场景 + 风格 + 光影色调 + 构图质感 + 比例用途")
    return d


# ------------------------------------------------------------------ 运镜守卫
# 2026-11-15 端到端对照实测：照搬外部写法写「Bullet Time 全场静止 2 秒，Match Cut 转场」
# 且 spec 用英文 Dynamic Follow —— validate_prompt.py 只拦到 C12(Match Cut) 与
# C18g(英文 spec 无中文运镜族)，**「静止 2 秒」与 Bullet Time 静默放行，稿件仍 PASSED**。
# 那两条是语义层纪律、机检无对应子码；本守卫补上工具兜底，不改动 C 码结构。
CAMERA_GUARD = [
    (r"静止\s*[2两]\s*秒|停住\s*[2两]\s*秒",
     "时间凝滞镜：本包裁决为「命中瞬间定格 1~2 帧」，⛔ 禁 2 秒静止（camera-specs-15rules §二/§四：同运镜≤2秒、升格默认禁用）"),
    (r"重叠\s*3\s*秒|扩散\s*3\s*秒",
     "记忆闪回镜：本包裁决为 ≤2 秒或拆成两个镜行"),
    (r"\b(?:Bullet\s*Time|Match\s*Cut|Wipe\s*/?\s*Mask|Eye-?trace|Color\s*Grade|"
     r"Dynamic\s*Follow|Dive\s*&\s*Soar|Combat\s*Weave|Spin\s*Attack|Dodge\s*&\s*Shake|"
     r"Spatial\s*Folding|Motion\s*Trail|Afterimage|See-?Through|X-?Ray|Flashback|"
     r"Montage\s*Sequence|Dolly\s*Zoom|J-?cut|L-?cut|Whip\s*Pan)\b",
     "英文运镜/转场术语禁入 P4 投喂正文（C12 / C18g）；只作内部检索键，正文改写中文画面描述"),
    (r"透明度\s*递增",
     "分身残像镜：原文正文「逐级递减」与配图「递增30%」矛盾，已裁决为**递减**"),
    (r"一镜.{0,6}(?:推|横移|拉远).{0,20}(?:推|横移|拉远)",
     "多镜组合序列是三镜序列，⛔ 必须拆进三行镜行（C18 一镜多运镜）"),
]


def check_camera_text(text):
    """检查一段待投喂文字里的运镜违规，返回 [(命中片段, 裁决建议)]。

    定位：**语义层纪律的轻量工具兜底**，不是 C 码机检的替代。
    出稿前对镜行正文跑一次，把 §四 五条裁决变成可执行的检查。
    """
    issues = []
    for pat, advice in CAMERA_GUARD:
        for m in re.finditer(pat, text, re.I):
            issues.append((m.group(0), advice))
    return issues


def _as_entries(source, default_family):
    """把 source 规整成条目列表。支持：条目 dict / 名称 / id / 列表 / None。"""
    if source is None:
        return []
    if isinstance(source, dict):
        return [source]
    if isinstance(source, (list, tuple)):
        out = []
        for s in source:
            out.extend(_as_entries(s, default_family))
        return out
    s = str(source).strip()
    if not s:
        return []
    for family in ("micro", "facial", "action", "pose"):
        r = find_by_name(family, s)
        if r:
            return r
    r = find_by_synonym(s)
    if r:
        return [r[0]]
    return []


# ------------------------------------------------------------------ 台账标注
def annotate_state(state, overwrite=False, verbose=True):
    """给 project_state.json 的每个镜头自动补 `expression` / `motion` 槽。

    只填**空槽**（已有内容不覆盖，除非 overwrite=True）。
    判定依据：镜行的 action + dialogue + 段类型 + 站位声明 + 音效摘要。
    产出是**建议**，最终仍由编导人确认；不自动写回磁盘（由调用方决定）。

    ⚠️ **置信度必须带出来**：每条建议同时写 `expression_ref` / `motion_ref`
    （库条目 id + 命中分值 + 命中词）。命中分值 < 40（约 4 字以内的弱命中）
    意味着**只是词面沾边**，几乎一定不是编导想要的情绪——这类镜必须人工重填。
    """
    segs = state.get("segments", []) or []
    filled = {"expression": 0, "motion": 0}
    weak = []
    for seg in segs:
        seg_blob = " ".join([
            seg.get("segment_type", ""), seg.get("emotion_anchor_id", ""),
            " ".join(seg.get("standing", []) or []), seg.get("sfx_summary", ""),
        ])
        for sh in seg.get("shots", []) or []:
            blob = " ".join([sh.get("action", ""), sh.get("dialogue", ""), seg_blob])
            no = sh.get("no")
            if not sh.get("expression") or overwrite:
                hit = None
                for fam in ("micro", "facial"):
                    hs = find(fam, blob, limit=1)
                    if hs:
                        hit = (fam, hs[0][0], hs[0][1])
                        break
                if hit:
                    sh["expression"] = expression_clause(hit[1])
                    sh["expression_ref"] = {"id": hit[1]["id"], "score": hit[1].get("_score", 0),
                                            "hit": hit[2], "family": hit[0]}
                    filled["expression"] += 1
            if not sh.get("motion") or overwrite:
                hit = None
                for fam in ("action", "pose"):
                    hs = find(fam, blob, limit=1)
                    if hs:
                        hit = (fam, hs[0][0], hs[0][1])
                        break
                if hit:
                    sh["motion"] = motion_clause(hit[1])
                    sh["motion_ref"] = {"id": hit[1]["id"], "score": hit[1].get("_score", 0),
                                        "hit": hit[2], "family": hit[0]}
                    filled["motion"] += 1
            for slot in ("expression_ref", "motion_ref"):
                r = sh.get(slot) or {}
                if r and r.get("score", 0) < 40:
                    weak.append((no, slot.replace("_ref", ""), r.get("id"), r.get("score")))
    if verbose:
        print("[+] 已标注：表情 %d 镜 / 动作 %d 镜" % (filled["expression"], filled["motion"]))
        if weak:
            print("[!] 弱命中 %d 处（分值 < 40，约 4 字以内词面沾边）——**必须人工重填**："
                  % len(weak))
            for w in weak[:12]:
                print("      镜头%s · %s · %s（分值 %d）" % w)
    return filled


# ------------------------------------------------------------------ CLI
def _print_table(family, limit=200):
    rows = _entry_index(family)
    print("=== %s（%d 条）===" % (family, len(rows)))
    for e in rows[:limit]:
        if family == "micro":
            print("%s | %s | %s | 适用：%s" % (e["id"], e["name"], e["prompt"], e["use"]))
        elif family == "facial":
            print("%s | %s | %s | %s" % (e["id"], e["vol"], e["name"], e["prompt"]))
        elif family == "action":
            print("%s | %s | %s | %s" % (e["id"], e["cat"], e["name"], e["prompt"]))
        elif family == "pose":
            print("%s | %s | %s | 用途：%s | 镜头：%s" % (e["id"], e["book"], e["name"], e["use"], e["cam"]))
        elif family == "cam_move":
            print("%s | %s [%s] | %s | 参数：%s | spec族：%s" % (
                e["id"], e["name"], e.get("en", ""), e["prompt"][:46], e.get("param", ""), e.get("fam", "")))
        elif family == "cam_basic":
            print("%s | %s %s | %s | 本包合法运镜词：%s" % (
                e["id"], e["en"], e["cn"], e["desc"], e["fam"]))
        elif family == "image":
            print("%s | %s | %s | %s" % (e["id"], e["cat"], e["name"], e["prompt"]))
        elif family == "portrait":
            print("%s | %s | %s | %d 字 | %s" % (
                e["id"], e["ratio"], e["name"], len(e["prompt"]), e["prompt"][:40]))


def main():
    ap = argparse.ArgumentParser(description="提示词成品库引擎（表情 / 动作 / 运镜 / 生图）")
    ap.add_argument("--list", choices=FAMILIES)
    ap.add_argument("--query", help="自由文本检索（跨全族）")
    ap.add_argument("--camera", help="查运镜：给中文名 / 英文术语 / 场景词，返回正文写法 + spec 运镜族 + 裁决")
    ap.add_argument("--guard", help="出稿前守卫：检查一段文字/文件里的运镜违规（英文术语 / 2秒静止 / 3秒重叠 / 残像方向）")
    ap.add_argument("--formula", action="store_true", help="列出全部拼装公式")
    ap.add_argument("--state", help="project_state.json 路径")
    ap.add_argument("--annotate", action="store_true", help="自动给镜头补 expression/motion 槽")
    ap.add_argument("--overwrite", action="store_true", help="覆盖已有槽（默认只填空槽）")
    ap.add_argument("--out", help="标注结果写出的 JSON 路径")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if args.list:
        _print_table(args.list)
        return 0
    if args.guard:
        _txt = args.guard
        if os.path.isfile(_txt):
            with open(_txt, encoding="utf-8") as f:
                _txt = f.read()
        issues = check_camera_text(_txt)
        if not issues:
            print("[+] 运镜守卫：0 违规（英文术语 / 超时静止 / 转场术语 / 残像方向 / 一镜多运镜 均未命中）")
            return 0
        print("[!] 运镜守卫：%d 处违规" % len(issues))
        for hit, advice in issues[:20]:
            print("  · 命中「%s」→ %s" % (hit, advice))
        return 1
    if args.formula:
        for k, v in sorted(formula_table().items()):
            print("  %-12s %s  （%s）" % (k, v, FORMULA_DESC.get(k, "AI 生图万能六槽")))
        return 0
    if args.camera:
        # 两族一起查再按分值合并：查「Dolly」应得基础机位、查「追车」应得进阶运镜
        allh = [(e, w) for e, w in find("cam_move", args.camera, limit=4)]
        allh += [(e, w) for e, w in find("cam_basic", args.camera, limit=3)]
        allh.sort(key=lambda x: -x[0].get("_score", 0))
        hits = allh[:3]
        if not hits:
            print("[!] 未命中运镜条目。试试：追车 / 子弹时间 / 残影 / 回忆杀 / 遮挡 / Pan / 变焦")
            return 0
        for e, w in hits:
            print("--- %s %s [%s]（命中 %s / %d）---" % (
                e["id"], e["name"], e.get("en", e.get("cn", "")), w, e.get("_score", 0)))
            if e["family"] == "cam_basic":
                print("  定义：%s" % e["desc"])
                print("  spec 可写：%s" % e["fam"])
                continue
            print("  正文可写：%s" % e["prompt"])
            print("  spec 运镜族：%s" % e["fam"])
            print("  参数：%s" % e.get("param", ""))
            if e.get("route"):
                print("  归属权威：%s" % e["route"])
            if e.get("guard"):
                print("  ⚠️ 裁决：%s" % e["guard"])
        return 0
    if args.query:
        print("--- 表情 ---")
        for e, w in find("micro", args.query, limit=5):
            print("  %s %s  命中[%s](%d)  %s" % (e["id"], e["name"], w, e.get("_score", 0), e["prompt"]))
        for e, w in find("facial", args.query, limit=3):
            print("  %s %s  命中[%s](%d)  %s" % (e["id"], e["name"], w, e.get("_score", 0), e["prompt"]))
        print("--- 动作 ---")
        for e, w in find("action", args.query, limit=5):
            print("  %s %s  命中[%s](%d)  %s" % (e["id"], e["name"], w, e.get("_score", 0), e["prompt"]))
        for e, w in find("pose", args.query, limit=5):
            print("  %s %s  命中[%s](%d)  %s" % (e["id"], e["name"], w, e.get("_score", 0), e["prompt"]))
        print("--- 运镜 ---")
        for e, w in find("cam_move", args.query, limit=5):
            print("  %s %s [%s]  命中[%s](%d)  %s" % (
                e["id"], e["name"], e.get("en", ""), w, e.get("_score", 0), e["prompt"][:60]))
        print("--- 生图 ---")
        for e, w in find("image", args.query, limit=5):
            print("  %s %s | %s  命中[%s](%d)  %s" % (
                e["id"], e["cat"], e["name"], w, e.get("_score", 0), e["prompt"][:60]))
        for e, w in find("portrait", args.query, limit=2):
            print("  %s %s | %s  命中[%s](%d)" % (
                e["id"], e["ratio"], e["name"][:26], w, e.get("_score", 0)))
        return 0
    if args.state:
        with open(args.state, encoding="utf-8") as f:
            state = json.load(f)
        if args.annotate:
            annotate_state(state, overwrite=args.overwrite)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            print("[+] 已写出：%s" % args.out)
        else:
            for seg in state.get("segments", []) or []:
                for sh in seg.get("shots", []) or []:
                    print("[镜头%s] %s" % (sh.get("no"), sh.get("expression", "")))
                    print("         %s" % sh.get("motion", ""))
        return 0
    ap.print_help()
    return 2


def self_test():
    b = bank()
    assert len(b["micro"]) == 50, "micro 条数不对：%d" % len(b["micro"])
    assert len(b["facial"]) == 54, "facial 条数不对：%d" % len(b["facial"])
    assert len(b["action"]) == 100, "action 条数不对：%d" % len(b["action"])
    assert len(b["pose"]) == 100, "pose 条数不对：%d" % len(b["pose"])

    # 卷号映射不得错位（6 卷 x 9）
    vols = {}
    for e in b["facial"]:
        vols[e["vol"]] = vols.get(e["vol"], 0) + 1
    assert len(vols) == 6 and all(v == 9 for v in vols.values()), "facial 卷映射错位：%s" % vols

    # 五件套槽位顺序：微表情 -> 眼神落点 -> 嘴角变化 -> 呼吸停顿 -> 小动作
    e = find_by_name("micro", "强忍委屈")[0]
    assert list(e["slots"].keys()) == list(MICRO_SLOT_ORDER)
    assert "眼尾泛红" in e["slots"]["face"] and "视线滑开" in e["slots"]["gaze"]

    # 组装：micro 族走五件套
    c = expression_clause("强忍委屈")
    assert c.startswith("面部：") and "眼尾泛红" in c and "视线滑开" in c, c
    # facial 族整体输出
    c2 = expression_clause(find_by_name("facial", "瞳孔骤缩式惊骇")[0])
    assert c2.startswith("面部：") and "瞳孔缩成针尖" in c2, c2

    # 动作组装
    m = motion_clause(find_by_name("action", "低头看手机，手指快速滑动屏幕")[0])
    assert m.startswith("动作：") and "手机" in m, m

    # 检索：按情绪词查到对应条目
    hits = find("micro", "他眼眶泛红，嘴唇颤抖，强忍着没哭出来")
    assert hits and "委屈" in hits[0][0]["name"], hits
    hits2 = find("action", "她推开房门走进来")
    assert hits2 and "门" in hits2[0][0]["name"], hits2

    # 同义词映射
    assert find_by_synonym("吃醋"), "同义词表未命中「吃醋」"

    # 公式拼装
    fc = formula_clause("emotion", 眼神="盯着对方", 嘴角="压住", 肩部="端平")
    assert fc.startswith("眼神："), fc

    # 情绪结果词必须被剥离（投喂正文只留画面语言）
    f = find_by_name("facial", "瞳孔骤缩式惊骇")[0]
    assert "惊骇到定格" not in f["prompt"], f["prompt"]
    assert "瞳孔缩成针尖" in f["prompt"], f["prompt"]

    # ★成品短语必须与自家机检 C25a 兼容（抽象神态词零残留）
    _all = b["micro"] + b["facial"] + b["action"] + b["pose"]
    _c25_bad = [(e["id"], e["prompt"]) for e in _all
                if any(w in e["prompt"] for w in C25_BLAND)]
    assert not _c25_bad, "成品短语残留 C25 抽象神态词：%s" % _c25_bad[:5]
    # ★成品短语必须角色中性（不得硬编码「女主/男主」——主体由镜行画面主体提供）
    _subj = [(e["id"], e["prompt"][:16]) for e in _all
             if re.match(r"^(女主|女生|男主|男生)", e["prompt"])]
    assert not _subj, "成品短语残留性别主体：%s" % _subj[:5]
    # 组装结果同样干净
    _m = motion_clause(find_by_name("action", "缓缓走向镜头，目光直视前方")[0])
    assert "表情" not in _m, _m
    assert not _m.startswith("动作：女主"), _m
    assert "目光直视前方" in _m, _m

    # ---- P16 新族（运镜 / 生图 / 角色设计）----
    assert len(b["cam_move"]) == 15 and len(b["cam_basic"]) == 5
    assert len(b["image"]) == 100 and len(b["portrait"]) == 5
    assert [e["no"] for e in b["image"]] == list(range(1, 101)), "生图 100 条编号不连续"
    assert [e["no"] for e in b["cam_move"]] == list(range(1, 16))
    assert len(b["portrait_dims"]) == 10 and len(b["image_pitfalls"]) == 4

    # 运镜三件套：中文正文 / 合法 spec 运镜族 / 冲突裁决，缺一不可
    cc = camera_clause(find_by_name("cam_move", "时间凝滞镜")[0])
    assert cc["body"] and cc["spec"] == "定格" and "降级" in cc["guard"], cc
    assert "Bullet Time" not in cc["body"], "英文术语泄漏进投喂正文（C12）"
    # 所有 15 条的正文都不得含英文术语
    _leak = [(e["id"], e["en"]) for e in b["cam_move"]
             if e["en"] and e["en"] in e["prompt"]]
    assert not _leak, "运镜正文混入英文术语：%s" % _leak
    # 已有权威的 4 条转场必须写成指针，不另立规则
    for no in (7, 8, 9, 10):
        e = next(x for x in b["cam_move"] if x["no"] == no)
        assert e["route"], "C%02d 缺归属权威指针（会与 creative-transition-library 撞车）" % no
    # 分身残像的矛盾必须被裁决为「递减」
    _trail = next(x for x in b["cam_move"] if x["no"] == 12)
    assert "递减" in _trail["prompt"] and "矛盾" in _trail["guard"], _trail

    # 生图六槽公式与出图组句
    assert formula_table()["image"].count("+") == 5
    # 运镜守卫：端到端对照实验里机检漏掉的两条，这里必须抓到
    _bad = "Bullet Time 全场静止 2 秒，Match Cut 转场，残像透明度递增"
    _iss = [a for _, a in check_camera_text(_bad)]
    assert len(_iss) >= 4, _iss
    assert any("1~2 帧" in a for a in _iss) and any("递减" in a for a in _iss), _iss
    assert not check_camera_text("镜头紧随目标同步前进，弯道带惯性延迟，沿位移方向动态模糊")
    _a = asset_clause(find_by_name("image", "雨夜情绪人像")[0])
    assert _a.startswith("出图：") and len(_a) > 30, _a
    assert "；" in _a and "。" in _a.rstrip("。") + "。", _a
    # 基础机位：只收录可确证的 5 个，不编造补齐
    assert all(x["fam"] for x in b["cam_basic"]), "基础机位缺本包合法运镜词对照"
    assert len({x["id"] for x in b["cam_move"] + b["cam_basic"] + b["image"] + b["portrait"]}) == 125

    print("[+] expression_motion self-test PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
