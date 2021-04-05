import pymongo
from telegram import *
from telegram.ext import *
import time

#install packages
#python-telegram-bot
#pymongo

#todo add language settings (Russian or English)
#todo add extra user info (age, gender, ...)
#todo make an inline keyboard for each question
#todo prevent the user from answering the survey twice in a row (using the last survey time)

#todo think about security and encryption
client = pymongo.MongoClient("mongodb+srv://admin:q80O6vnEyKBaR49o@cluster0.d67oq.mongodb.net/test")
db = client.testdb
users = db.users
questions = db.questions
answers = db.answers

#adds a user to the db
def add_user(chatId,firstName,lastName,userName):
    user = {
        '_id': chatId,
        'firstName': firstName,
        'lastName': lastName,
        'userName': userName
    }
    if users.find({'_id':chatId}) != None:
        return
    users.insert_one(user)
    return

#gets the info of the user
def get_user(chat_id):
    result = users.find_one({'_id':chat_id})
    return result['firstName'], result['lastName'], result['userName']

#gets the the list of all questions in english
def get_all_questions():
    return questions.find({}, {'eng': 1})

#adds an answer to the database
def add_answer(chatId,question_id,answer,time):
    entry = {
        'chatId' : chatId,
        'questionId': question_id,
        'answer' : answer,
        'time' : time
    }
    answers.insert_one(entry)
    already_answered = users.find_one({'_id': chatId},{'answered':1})['answered']
    already_answered.append(question_id)
    users.update_one({'_id': chatId}, {'$set': {'answered': already_answered}})

#the user will answer questions one by one in a survey, this function initiates the survey
def start_survey_session(chatId):
    users.update_one({'_id':chatId},{ '$set' : {'sessionOn':True ,
                                               'lastSession':time.time(),
                                               'answered': [] }})

#picks a question that is not yet answered by the user
def pick_question(chatId):
    already_answered = users.find_one({'_id': chatId},{'answered':1})
    question = questions.find_one({})
    if already_answered != None:
        question = questions.find_one({'_id': {'$nin': already_answered['answered']}})

    if(question == None):
        return None

    users.update_one({'_id': chatId}, {'$set': {'lastPicked': question['_id']}})
    return question

#checks the id of the last asked question to the user
def last_asked_question(chatId):
    return users.find_one({'_id': chatId}, {'lastPicked': 1})['lastPicked']

#closes the survey session
def close_survey_session(chatId):
    users.update_one({'_id': chatId}, {'$set': {'sessionOn': False,
                                               'answered': []}})

res = get_all_questions()

for s in res:
    print(s['eng'])


print('Done')



#telegram API part

tgbot_token = '1782336868:AAFvd7P9H4Vs09S8T5p4_86cHXuNZIOuTBg'


updater = Updater(token=tgbot_token, use_context=True)
dispatcher = updater.dispatcher

#for handling the start command
def start(update, context):
    add_user(update.effective_chat.id,update.effective_chat.first_name,update.effective_chat.last_name,update.effective_chat.username)
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Hello "+update.effective_chat.first_name+"! Use the command /survey to start answering questions.")


start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)

#inline keyboards
keyboard = [
    [
        InlineKeyboardButton("Yes", callback_data='1'),
        InlineKeyboardButton("No", callback_data='0'),
    ]
]

next_question_keyboard = [
    [
        InlineKeyboardButton("Another question", callback_data='3'),
        InlineKeyboardButton("Enough for today", callback_data='4'),
    ]
]

#for the command survey
def survey(update,context):
    start_survey_session(update.effective_chat.id)
    question = pick_question(update.effective_chat.id)

    msg = context.bot.send_message(chat_id=update.effective_chat.id, text=question['eng'],
                                    reply_markup=InlineKeyboardMarkup(keyboard))


#for handling inline keyboard buttons
def button(update,context):
    query = update.callback_query
    query.answer()

    if query.data == '3':
        question = pick_question(update.effective_chat.id)
        if question == None:
            query.message.edit_text('You have answered all the questions of the survery! You can chill now and be happy!')
            return

        query.message.edit_text(question['eng'])
        query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if query.data == '4':
        query.message.edit_text("Okay! Have a nice day!")
        close_survey_session(update.effective_chat.id)
        return

    answer = False
    if query.data == '1':
        answer = True

    add_answer(update.effective_chat.id,
               last_asked_question(update.effective_chat.id),
               answer, time.time())

    query.message.edit_text("Do you want to answer another question?")
    query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(next_question_keyboard))


survey_handler = CommandHandler('survey', survey)
dispatcher.add_handler(survey_handler)
updater.dispatcher.add_handler(CallbackQueryHandler(button))
updater.start_polling()

