from datetime import datetime
import telebot
from telebot import types
from sqlalchemy.orm import sessionmaker
from src.database import engine
from src.models import Elective, Review
from sqlalchemy import select
from src.config import TOKEN
from sqlalchemy.orm import joinedload
from googletrans import Translator

bot = telebot.TeleBot(TOKEN, parse_mode='None')
translator = Translator()

user_elective_selections = {}
user_languages = {}
user_reviews = {}

Session = sessionmaker(bind=engine)


def translate_message(text, language):
    return translator.translate(text, dest='en').text if language == 'en' else text


def send_translated_message(chat_id, message, language):
    bot.send_message(chat_id, translate_message(message, language))


def get_language(chat_id):
    return user_languages.get(chat_id, 'ru')


def show_electives(electives, language):
    response = "Доступные элективы:\n" + "\n".join(f"- {elective.unique_id}: {elective.name}" for elective in electives)
    return translate_message(response, language)


@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    language = user_languages.setdefault(chat_id, 'ru')
    welcome_message = (
        "Привет! 👋\n\n"
        "Я — бот, который поможет тебе выбрать элективный курс в нашем вузе. Вот что я могу:\n"
        "- Посмотреть аннотации к элективам\n"
        "- Узнать последние отзывы от студентов\n"
        "- Оставить свой отзыв о курсе\n"
        "- Выбрать язык общения (Русский или English)\n\n"
        "Чтобы начать, используй команду /electives для просмотра доступных курсов или /language для изменения языка общения."
    )
    send_translated_message(chat_id, welcome_message, language)


@bot.callback_query_handler(func=lambda call: call.data.startswith('set_language_'))
def set_language(call):
    chat_id = call.message.chat.id
    language = call.data.split('_')[-1]
    user_languages[chat_id] = language
    confirmation = "Language changed to English." if language == 'en' else "Язык изменен на русский."
    bot.send_message(chat_id, confirmation)


@bot.message_handler(commands=['language'])
def choose_language(message):
    chat_id = message.chat.id
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Русский", callback_data='set_language_ru'))
    markup.add(types.InlineKeyboardButton("English", callback_data='set_language_en'))
    bot.send_message(chat_id, "Выберите язык:", reply_markup=markup)


@bot.message_handler(commands=['electives'])
def choose_elective_type(message):
    chat_id = message.chat.id
    language = get_language(chat_id)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📚 PEP", callback_data='PEP'))
    markup.add(types.InlineKeyboardButton("📖 RIM", callback_data='RIM'))
    elective_choice_message = "Выберите тип элективов:" if language == 'ru' else "Choose the type of electives:"
    bot.send_message(chat_id, elective_choice_message, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data in ['PEP', 'RIM'])
def handle_elective_type_selection(call):
    chat_id = call.message.chat.id
    user_elective_selections[chat_id] = call.data
    language = get_language(chat_id)

    with Session() as session:
        electives = session.query(Elective).filter(Elective.elective_type == call.data).all()

    response = show_electives(electives, language)
    elective_prompt = "\n\nВведите уникальный номер электива, чтобы получить его информацию:"
    response += translate_message(elective_prompt, language)
    bot.send_message(chat_id, response)


@bot.message_handler(func=lambda message: message.text.isdigit())
def handle_elective_selection(message):
    chat_id = message.chat.id
    unique_id = int(message.text)
    language = get_language(chat_id)
    elective_type = user_elective_selections.get(chat_id)

    if not elective_type:
        bot.send_message(chat_id, "Пожалуйста, выберите тип элективов перед вводом уникального номера.")
        return

    with Session() as session:
        elective = session.query(Elective).options(joinedload(Elective.reviews)).filter(
            Elective.unique_id == unique_id).first()

    if elective:
        response = f"**{elective.name}**\n\n{elective.description}\n\nПоследние отзывы:\n"
        response += "\n".join(f"{i}) {review.text}" for i, review in enumerate(elective.reviews[-5:], 1))
        response += "\nХотите оставить отзыв? Напишите ваш отзыв ниже или нажмите /electives для возврата."
        bot.send_message(chat_id, translate_message(response, language))
        user_reviews[chat_id] = unique_id
    else:
        bot.send_message(chat_id, "Электив с таким уникальным ID не найден.")


@bot.message_handler(func=lambda message: message.chat.id in user_reviews)
def leave_review(message):
    chat_id = message.chat.id
    unique_id = user_reviews[chat_id]
    review_text = message.text
    user_name = message.from_user.username or message.from_user.first_name
    language = get_language(chat_id)

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Да", callback_data=f'confirm_review_{unique_id}_{review_text}'))
    markup.add(types.InlineKeyboardButton("❌ Нет", callback_data='cancel_review'))
    confirmation_message = f"Ваш отзыв: '{review_text}'. Подтвердите отзыв:"
    bot.send_message(chat_id, translate_message(confirmation_message, language), reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_review_'))
def confirm_review(call):
    chat_id = call.message.chat.id
    data = call.data.split('_')

    unique_id, review_text = data[2], '_'.join(data[3:])
    user_name = call.from_user.username or call.from_user.first_name

    with Session() as session:
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

    language = get_language(chat_id)
    bot.send_message(chat_id, translate_message("Ваш отзыв успешно оставлен!", language))
    user_reviews.pop(chat_id, None)


@bot.callback_query_handler(func=lambda call: call.data == 'cancel_review')
def cancel_review(call):
    chat_id = call.message.chat.id
    bot.send_message(chat_id, translate_message("Отзыв отменен.", get_language(chat_id)))
    user_reviews.pop(chat_id, None)


@bot.message_handler(commands=['help'])
def send_help(message):
    chat_id = message.chat.id
    help_text = (
        "Я могу помочь вам с выбором элективов. Вот основные команды:\n"
        "/electives - Посмотреть доступные элективы\n"
        "/language - Изменить язык общения\n"
        "/help - Получить помощь по использованию бота\n"
    )
    bot.send_message(chat_id, translate_message(help_text, get_language(chat_id)))


if __name__ == '__main__':
    bot.polling(none_stop=True)
