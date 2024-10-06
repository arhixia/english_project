from datetime import datetime
import telebot
from telebot import types
from sqlalchemy.orm import sessionmaker
from src.database import engine, SessionLocal  # Импортируйте свой файл с настройками базы данных
from src.models import Elective, Review  # Импортируйте вашу модель Elective
from sqlalchemy import select
from src.config import TOKEN
from sqlalchemy.orm import joinedload


bot = telebot.TeleBot(TOKEN, parse_mode='None')

user_elective_selections = {}
last_selection = {}  # Храним последнюю выбранную категорию элективов
user_languages = {}
user_reviews = {}

# Создание сессии базы данных
Session = sessionmaker(bind=engine)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    # Устанавливаем язык по умолчанию (если он еще не был установлен)
    if chat_id not in user_languages:
        user_languages[chat_id] = 'ru'  # По умолчанию устанавливаем русский язык

    language = user_languages[chat_id]  # Получаем язык пользователя

    if language == 'ru':
        bot.send_message(chat_id,
            "Привет! 👋\n\n"
            "Я — бот, который поможет тебе выбрать элективный курс в нашем вузе. Вот что я могу:\n"
            "- Посмотреть аннотации к элективам\n"
            "- Узнать последние отзывы от студентов\n"
            "- Оставить свой отзыв о курсе\n"
            "- Выбрать язык общения (Русский или English)\n\n"
            "Чтобы начать, используй команду /electives для просмотра доступных курсов или /language для изменения языка общения. "
            "Нажмите на меню в левом нижнем углу и посмотрите возможные команды."
        )
    else:
        bot.send_message(chat_id,
            "Hello! 👋\n\n"
            "I am a bot that will help you choose an elective course at our university. Here’s what I can do:\n"
            "- View annotations for electives\n"
            "- Learn about the latest student reviews\n"
            "- Leave your review about a course\n"
            "- Choose the language of communication (Русский or English)\n\n"
            "To get started, use the /electives command to view available courses or /language to change the language of communication. "
            "Click on the menu in the lower left corner to see possible commands."
        )

# Получение всех элективов по типу
def get_all_electives(elective_type: str, db: Session):
    stmt = select(Elective).where(Elective.elective_type == elective_type)
    electives = db.execute(stmt).scalars().all()
    return electives

# Получение информации об элективе
def get_elective_info(elective_id: str, db: Session):
    stmt = select(Elective).options(joinedload(Elective.reviews)).where(Elective.unique_id == elective_id)
    elective = db.execute(stmt).scalars().first()
    if elective:
        return {
            'name': elective.name,
            'description': elective.description,
            'reviews': [review.text for review in elective.reviews]
        }
    return None

# Обработчик команды /electives для выбора типа элективов
@bot.message_handler(commands=['electives'])
def choose_elective_type(message):
    chat_id = message.chat.id
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📚 PEP", callback_data='PEP'))
    markup.add(types.InlineKeyboardButton("📖 RIM", callback_data='RIM'))
    bot.send_message(chat_id, "Выберите тип элективов:", reply_markup=markup)

# Обработчик выбора типа элективов
@bot.callback_query_handler(func=lambda call: call.data in ['PEP', 'RIM'])
def handle_elective_type_selection(call):
    chat_id = call.message.chat.id
    user_elective_selections[chat_id] = call.data

    session = Session()
    electives = session.query(Elective).filter(Elective.elective_type == call.data).all()
    session.close()

    response = show_electives(electives)
    response += "\n\nВведите уникальный номер электива, чтобы получить его информацию:"
    bot.send_message(chat_id, response)

# Обработчик выбора электива
@bot.message_handler(func=lambda message: message.text.isdigit())
def handle_elective_selection(message):
    chat_id = message.chat.id
    unique_id = int(message.text)

    session = Session()
    elective_type = user_elective_selections.get(chat_id)

    if not elective_type:
        bot.send_message(chat_id, "Пожалуйста, выберите тип элективов перед вводом уникального номера.")
        session.close()
        return

    elective = session.query(Elective).options(joinedload(Elective.reviews)).filter(
        Elective.unique_id == unique_id).first()
    if elective:
        response = f"**{elective.name}**\n\n{elective.description}\n\nПоследние отзывы:\n"

        # Форматирование отзывов с отступами и нумерацией
        for i, review in enumerate(elective.reviews[-5:], 1):
            response += f"{i}) {review.text}\n"

        response += "\nХотите оставить отзыв? Напишите ваш отзыв ниже или нажмите /electives для возврата."
        bot.send_message(chat_id, response)
        user_reviews[chat_id] = unique_id  # Сохраняем уникальный ID электива для отзыва
    else:
        bot.send_message(chat_id, "Электив с таким уникальным ID не найден.")

    session.close()

# Обработчик отзывов
@bot.message_handler(func=lambda message: message.chat.id in user_reviews)
def leave_review(message):
    chat_id = message.chat.id
    unique_id = user_reviews[chat_id]
    review_text = message.text
    user_name = message.from_user.username or message.from_user.first_name

    # Создаем клавиатуру с кнопками "Да" и "Нет"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Да", callback_data=f'confirm_review_{unique_id}_{review_text}'))
    markup.add(types.InlineKeyboardButton("❌ Нет", callback_data='cancel_review'))

    # Отправляем сообщение с просьбой подтвердить отзыв
    bot.send_message(chat_id, f"Ваш отзыв: '{review_text}'. Подтвердите отзыв:", reply_markup=markup)




# Подтверждение отзыва
@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_review_'))
def confirm_review(call):
    chat_id = call.message.chat.id
    data = call.data.split('_')

    # Убедитесь, что у вас есть уникальный ID электива и текст отзыва
    if len(data) < 3:
        bot.send_message(chat_id, "Произошла ошибка. Попробуйте оставить отзыв снова.")
        return

    unique_id = data[2]  # Предполагаем, что третий элемент - это текст отзыва, который содержит пробелы
    review_text = '_'.join(data[3:])  # Объединяем оставшиеся части как текст отзыва

    user_name = call.from_user.username or call.from_user.first_name

    session = Session()
    elective = session.query(Elective).filter(Elective.unique_id == int(unique_id)).first()

    if elective:
        new_review = Review(
            elective_id=elective.id,
            user_name=user_name,
            text=review_text,
            date_created=str(datetime.now())
        )
        session.add(new_review)
        session.commit()
        session.close()
        bot.send_message(chat_id, "Ваш отзыв успешно оставлен!")
    else:
        bot.send_message(chat_id, "Ошибка при оставлении отзыва. Электив не найден.")

    # Удаляем запись о выбранном элективе
    del user_reviews[chat_id]




# Обработчик отмены отзыва
@bot.callback_query_handler(func=lambda call: call.data == 'cancel_review')
def cancel_review(call):
    chat_id = call.message.chat.id
    bot.send_message(chat_id, "Отзыв отменен. Вы можете продолжить выбирать элективы или оставить другой отзыв или нажмите /electives для возврата.")
    del user_reviews[chat_id]



def show_electives(electives):
    message = "Доступные элективы:\n"
    for elective in electives:
        message += f"{elective.unique_id}: {elective.name}\n"  # Добавляем уникальный ID перед названием
    return message


bot.polling()
