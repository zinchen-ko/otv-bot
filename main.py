from pymongo import MongoClient
from urllib.parse import quote_plus as quote
import telebot
from apscheduler.schedulers.background import BackgroundScheduler
import re
from telebot import types
import datetime
import boto3


class DailyPlanner(object):
    def __init__(self):
        url = 'mongodb://{user}:{pw}@{hosts}/?replicaSet={rs}&authSource={auth_src}'.format(
            user=quote('otv_user'),
            pw=quote('otv_user'),
            hosts=','.join([
                'rc1d-nkdwgkm1bd0c5gcu.mdb.yandexcloud.net:27018'
            ]),
            rs='rs01',
            auth_src='db1')
        self._client = MongoClient(
            url,
            tls=True,
            tlsCAFile='root.crt'
        )['db1']
        self._collection = self._client['note']

    def get_all_notes(self, chat_id=None):
        if chat_id is None:
            data = self._collection.find()
            return data
        else:
            try:
                data = self._collection.find({"user": chat_id})
                print("Get all users")
                return data
            except Exception as ex:
                print("[get_all] Some problem...")
                print(ex)

    def add_note(self, note):
        try:
            self._collection.insert_one(note)
            print(f"Added New note: {note.get('text')}")
        except Exception as ex:
            print("[create_note] Some problem...")
            print(ex)

    def get_note_by_text(self, text, chat_id):
        data = self._collection.find({"user": chat_id, "text": text})
        return data[0]

    def edit_note(self, name_of_note, param, param_value):
        filter = {'name': name_of_note}
        newvalues = {"$set": {f'{param}': param_value}}
        self._collection.update_one(filter, newvalues)

    def delete_note(self, name_of_note, chat_id):
        self._collection.delete_one({"user": chat_id, "name": name_of_note})


class Note(object):
    def __init__(self,
                 name=None,
                 text=None,
                 date=None,
                 tag=None,
                 theme=None,
                 user=None,
                 img_id=None):
        self.name = name
        self.text = text
        self.date = date
        self.tag = tag
        self.theme = theme
        self.user = user
        self.img_id = img_id

    def to_string(self) -> str:
        return (
                f"Name = {self.name}\n" +
                f"Text = {self.text}\n" +
                f"Date = {self.date}\n" +
                f"Tag = {self.tag}\n" +
                f"Theme = {self.theme}"
        )


bot = telebot.TeleBot('6421102978:AAER1O_b4hv_NPfqQzpYFXDMD02Cad__rdA')
bot.remove_webhook()
planner = DailyPlanner()
scheduler = BackgroundScheduler()
session = boto3.session.Session()
s3 = session.client(
    service_name='s3',
    aws_access_key_id='YCAJEMZNmoPgldt2QGJ0SePi8',
    aws_secret_access_key='YCMtWZe2r_XP1AHmn2gqO0YmcDrU1BeD0MGtxlGy',
    endpoint_url='https://storage.yandexcloud.net'
)


def print_note(note):
    return f"Name = {note['name']}\n" + f"Text = {note['text']}\n" + f"Date = {note['date']}\n" + f"Tag = {note['tag']}\n" + f"Theme = {note['theme']}"


def get_all_notes(message):
    notes = planner.get_all_notes(message.chat.id)
    for note in notes:
        bot.send_message(message.chat.id, print_note(note))
        print(note)
        if note.get("img_id") is not None:
            with open(f'{note.get("img_id")}', 'wb') as f:
                s3.download_fileobj("zinchenko", note.get("img_id"), f)
            img = open(f'{note.get("img_id")}', 'rb')
            bot.send_photo(message.chat.id, img)


def send_message_by_time():
    notes = planner.get_all_notes()
    current_date = datetime.datetime.now().strftime('%d/%m/%Y')
    for note in notes:
        if note.get("date") == current_date:
            bot.send_message(note.get("user"), print_note(note))


scheduler.add_job(send_message_by_time, 'cron', day_of_week='mon-sun', hour=14, minute=15)


@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Привет! Я ежедневник, во мне ты можешь хранить свои заметки")


@bot.message_handler(commands=['help'])
def help(message):
    bot.reply_to(
        message,
        "/add_note - добавление заметки\n" +
        "/get_notes - посмотреть текущие заметки\n" +
        "/edit_note - изменение заметки\n" +
        "/delete_note - удаление заметки\n" +
        "/add_img - добавление картинку к заметке\n" +
        "/delete_img - удаление картинку заметки\n"
    )


@bot.message_handler(commands=['add_note'])
def add_note(message):
    note = Note()
    bot.send_message(message.chat.id, "Введите имя вашей заметки")
    bot.register_next_step_handler(message, add_name, note)


def add_name(message, note):
    note.name = message.text
    bot.send_message(message.chat.id, "Введите текст вашей заметки")
    bot.register_next_step_handler(message, add_text, note)


def add_text(message, note):
    note.text = message.text
    bot.send_message(message.chat.id, "Введите дату оповещения в формате: DD/MM/YYYY")
    bot.register_next_step_handler(message, add_date, note)


def add_date(message, note):
    date = message.text
    if re.match("^[0-9]{1,2}\\/[0-9]{1,2}\\/[0-9]{4}$", date):
        note.date = date
        bot.send_message(message.chat.id, "Введите тег для заметки")
        bot.register_next_step_handler(message, add_tag, note)
    else:
        bot.send_message(message.chat.id, "Неверный формат даты, введите команду /add_note еще раз")


def add_tag(message, note):
    note.tag = message.text
    bot.send_message(message.chat.id, "Введите тему заметки")
    bot.register_next_step_handler(message, add_theme, note)


def add_theme(message, note):
    note.theme = message.text
    note.user = message.chat.id
    planner.add_note(note.__dict__)


@bot.message_handler(commands=['get_notes'])
def get_notes(message):
    get_all_notes(message)


def choose_param(message):
    name_of_note = message.text
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    name_button = types.KeyboardButton("name")
    tag_button = types.KeyboardButton("tag")
    theme_button = types.KeyboardButton("theme")
    text_button = types.KeyboardButton("text")
    markup.add(name_button, tag_button, theme_button, text_button)
    bot.send_message(message.chat.id, text="Выберите параметр который вы хотите изменить", reply_markup=markup)
    bot.register_next_step_handler(message, edit_note, name_of_note)


def edit_note(message, name_of_note):
    param = message.text
    bot.reply_to(message, "Введите новое значение параметра")
    bot.register_next_step_handler(message, edit, name_of_note, param)


def edit(message, name_of_note, param):
    param_value = message.text
    planner.edit_note(name_of_note, param, param_value)
    bot.reply_to(message, "Успешно заменено")


@bot.message_handler(commands=['edit_note'])
def choose_note(message):
    notes = planner.get_all_notes(message.chat.id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for note in notes:
        button = types.KeyboardButton(note.get("name"))
        markup.add(button)
    bot.send_message(message.chat.id, text="Выберите заметку которую вы хотите изменить", reply_markup=markup)
    bot.register_next_step_handler(message, choose_param)


def delete(message):
    planner.delete_note(message.text, message.chat.id)
    bot.reply_to(message, "Успешно удалено")


@bot.message_handler(commands=['delete_note'])
def delete_note(message):
    notes = planner.get_all_notes(message.chat.id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for note in notes:
        button = types.KeyboardButton(note.get("name"))
        markup.add(button)
    bot.send_message(message.chat.id, text="Выберите заметку которую хотите удалить", reply_markup=markup)
    bot.register_next_step_handler(message, delete)


def add_img_in_note(message, name_of_note):
    raw = message.photo[2].file_id
    name = raw + ".jpg"
    file_info = bot.get_file(raw)
    downloaded_file = bot.download_file(file_info.file_path)
    with open(name, 'wb') as new_file:
        new_file.write(downloaded_file)
    s3.upload_file(name, "zinchenko", name)
    planner.edit_note(name_of_note, "img_id", name)
    bot.send_message(message.chat.id, text="Файл успешно загружен")


def add_img_for_note(message):
    name_of_note = message.text
    bot.send_message(message.chat.id, text="Пришлите картинку которую хотите прикрепить")
    bot.register_next_step_handler(message, add_img_in_note, name_of_note)


@bot.message_handler(commands=['add_img'])
def add_img(message):
    notes = planner.get_all_notes(message.chat.id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for note in notes:
        button = types.KeyboardButton(note.get("name"))
        markup.add(button)
    bot.send_message(message.chat.id, text="Выберите заметку к которой надо прикрепить картинку", reply_markup=markup)
    bot.register_next_step_handler(message, add_img_for_note)


def delete_img_for_note(message):
    name_of_note = message.text
    planner.edit_note(name_of_note, "img_id", None)
    bot.send_message(message.chat.id, text="Картинка успешно удалена")


@bot.message_handler(commands=['delete_img'])
def delete_img(message):
    notes = planner.get_all_notes(message.chat.id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for note in notes:
        button = types.KeyboardButton(note.get("name"))
        markup.add(button)
    bot.send_message(message.chat.id, text="Выберите заметку у которой хотите удалить картинку", reply_markup=markup)
    bot.register_next_step_handler(message, delete_img_for_note)


scheduler.start()

bot.polling(none_stop=True, interval=0)
