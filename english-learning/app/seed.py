"""首次启动时自动写入示例数据(只有数据库为空时才会写入)"""
from sqlalchemy import func, select

from .database import SessionLocal
from .models import Admin, Lesson, Word
from .security import hash_password

# 示例单词:6 个分类,共 30 个
WORDS = [
    # 颜色
    {"english": "red", "chinese": "红色", "phonetic": "/red/", "example": "The apple is red.", "example_cn": "这个苹果是红色的。", "category": "颜色"},
    {"english": "blue", "chinese": "蓝色", "phonetic": "/bluː/", "example": "The sky is blue.", "example_cn": "天空是蓝色的。", "category": "颜色"},
    {"english": "green", "chinese": "绿色", "phonetic": "/ɡriːn/", "example": "The grass is green.", "example_cn": "草是绿色的。", "category": "颜色"},
    {"english": "yellow", "chinese": "黄色", "phonetic": "/ˈjeləʊ/", "example": "She has a yellow bag.", "example_cn": "她有一个黄色的包。", "category": "颜色"},
    {"english": "black", "chinese": "黑色", "phonetic": "/blæk/", "example": "He wears a black coat.", "example_cn": "他穿着一件黑色外套。", "category": "颜色"},
    {"english": "white", "chinese": "白色", "phonetic": "/waɪt/", "example": "Snow is white.", "example_cn": "雪是白色的。", "category": "颜色"},
    # 动物
    {"english": "cat", "chinese": "猫", "phonetic": "/kæt/", "example": "The cat is sleeping.", "example_cn": "猫在睡觉。", "category": "动物"},
    {"english": "dog", "chinese": "狗", "phonetic": "/dɒɡ/", "example": "I walk my dog every day.", "example_cn": "我每天遛狗。", "category": "动物"},
    {"english": "bird", "chinese": "鸟", "phonetic": "/bɜːd/", "example": "A bird is singing in the tree.", "example_cn": "一只鸟在树上唱歌。", "category": "动物"},
    {"english": "fish", "chinese": "鱼", "phonetic": "/fɪʃ/", "example": "There are many fish in the river.", "example_cn": "河里有很多鱼。", "category": "动物"},
    {"english": "horse", "chinese": "马", "phonetic": "/hɔːs/", "example": "The horse runs fast.", "example_cn": "这匹马跑得很快。", "category": "动物"},
    {"english": "rabbit", "chinese": "兔子", "phonetic": "/ˈræbɪt/", "example": "The rabbit likes carrots.", "example_cn": "兔子喜欢胡萝卜。", "category": "动物"},
    # 食物
    {"english": "apple", "chinese": "苹果", "phonetic": "/ˈæpl/", "example": "An apple a day keeps the doctor away.", "example_cn": "一天一苹果,医生远离我。", "category": "食物"},
    {"english": "bread", "chinese": "面包", "phonetic": "/bred/", "example": "I eat bread for breakfast.", "example_cn": "我早餐吃面包。", "category": "食物"},
    {"english": "milk", "chinese": "牛奶", "phonetic": "/mɪlk/", "example": "Drink some milk before bed.", "example_cn": "睡前喝点牛奶。", "category": "食物"},
    {"english": "rice", "chinese": "米饭", "phonetic": "/raɪs/", "example": "We have rice for lunch.", "example_cn": "我们午饭吃米饭。", "category": "食物"},
    {"english": "water", "chinese": "水", "phonetic": "/ˈwɔːtə/", "example": "Please give me some water.", "example_cn": "请给我一些水。", "category": "食物"},
    {"english": "egg", "chinese": "鸡蛋", "phonetic": "/eɡ/", "example": "I have an egg every morning.", "example_cn": "我每天早上吃一个鸡蛋。", "category": "食物"},
    # 数字
    {"english": "one", "chinese": "一", "phonetic": "/wʌn/", "example": "I have one brother.", "example_cn": "我有一个哥哥。", "category": "数字"},
    {"english": "two", "chinese": "二", "phonetic": "/tuː/", "example": "I have two pens.", "example_cn": "我有两支钢笔。", "category": "数字"},
    {"english": "three", "chinese": "三", "phonetic": "/θriː/", "example": "There are three books on the desk.", "example_cn": "桌子上有三本书。", "category": "数字"},
    {"english": "ten", "chinese": "十", "phonetic": "/ten/", "example": "I am ten years old.", "example_cn": "我十岁了。", "category": "数字"},
    # 日常用语
    {"english": "hello", "chinese": "你好", "phonetic": "/həˈləʊ/", "example": "Hello, nice to meet you.", "example_cn": "你好,很高兴认识你。", "category": "日常用语"},
    {"english": "thank you", "chinese": "谢谢你", "phonetic": "/θæŋk juː/", "example": "Thank you for your help.", "example_cn": "谢谢你的帮助。", "category": "日常用语"},
    {"english": "sorry", "chinese": "对不起", "phonetic": "/ˈsɒri/", "example": "Sorry, I am late.", "example_cn": "对不起,我迟到了。", "category": "日常用语"},
    {"english": "please", "chinese": "请", "phonetic": "/pliːz/", "example": "Please open the door.", "example_cn": "请打开门。", "category": "日常用语"},
    # 学校
    {"english": "book", "chinese": "书", "phonetic": "/bʊk/", "example": "This book is very interesting.", "example_cn": "这本书很有趣。", "category": "学校"},
    {"english": "school", "chinese": "学校", "phonetic": "/skuːl/", "example": "I go to school by bike.", "example_cn": "我骑自行车上学。", "category": "学校"},
    {"english": "teacher", "chinese": "老师", "phonetic": "/ˈtiːtʃə/", "example": "Our teacher is very kind.", "example_cn": "我们的老师很和蔼。", "category": "学校"},
    {"english": "student", "chinese": "学生", "phonetic": "/ˈstjuːdnt/", "example": "I am a student.", "example_cn": "我是一名学生。", "category": "学校"},
]

# 示例课程:3 篇小短文
LESSONS = [
    {
        "title": "自我介绍 Introduce Yourself",
        "summary": "用英语介绍自己的名字、年龄和爱好",
        "content": "Hello! My name is Li Ming. I am thirteen years old. I am a student. I like English and music. Nice to meet you!",
        "content_cn": "你好!我叫李明。我今年十三岁。我是一名学生。我喜欢英语和音乐。很高兴认识你!",
    },
    {
        "title": "我的家庭 My Family",
        "summary": "介绍家庭成员和他们的职业",
        "content": "There are four people in my family: my father, my mother, my sister and me. My father is a teacher. My mother is a nurse. My sister is a student. I love my family very much.",
        "content_cn": "我家有四口人:爸爸、妈妈、妹妹和我。爸爸是老师,妈妈是护士,妹妹是学生。我非常爱我的家。",
    },
    {
        "title": "在餐厅 At the Restaurant",
        "summary": "餐厅点餐的常用对话",
        "content": "Waiter: Good evening! What would you like?\nLi Ming: I would like some rice and chicken, please.\nWaiter: Would you like something to drink?\nLi Ming: A glass of water, please. Thank you!",
        "content_cn": "服务员:晚上好!您想要点什么?\n李明:我想要一些米饭和鸡肉。\n服务员:您想喝点什么吗?\n李明:请来一杯水。谢谢!",
    },
]


def seed_if_empty():
    """数据库为空时写入示例数据,并创建默认管理员账号"""
    db = SessionLocal()
    try:
        if db.scalar(select(func.count(Word.id))) == 0:
            db.add_all(Word(**w) for w in WORDS)
        if db.scalar(select(func.count(Lesson.id))) == 0:
            db.add_all(Lesson(**l) for l in LESSONS)
        if db.scalar(select(func.count(Admin.id))) == 0:
            # 默认管理员账号:admin / cloud7372tiger(上线前已修改)
            db.add(Admin(username="admin", password_hash=hash_password("cloud7372tiger")))
        db.commit()
    finally:
        db.close()
