from datetime import datetime

from matplotlib import pyplot as plt
import numpy as np
import pymongo
from telegram import *
from telegram.ext import *
import emoji
import re

#BEGIN HEROKU PART

import os
PORT = int(os.environ.get('PORT', '80'))
#END HEROKU PART

# Enable logging
import logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

# install packages
# python-telegram-bot
# pymongo

# todo add language settings (Russian or English)
# todo add extra user info (age, gender, ...)
# todo make an inline keyboard for each question
# todo prevent the user from answering the survey twice in a row (using the last survey time)

# todo think about security and encryption

''' DB PART '''

client = pymongo.MongoClient("mongodb+srv://admin:q80O6vnEyKBaR49o@cluster0.d67oq.mongodb.net/test")
db = client.testdb
users = db.users
questions = db.questions
answers = db.answers


# adds a user to the db
def add_user(chatId, firstName, lastName, userName):
    user = {
        '_id': chatId,
        'firstName': firstName,
        'lastName': lastName,
        'userName': userName,
        'lang': 'eng',
        'lastSession': 'dummy',
        'sessionOn': False,
        'birthdate': 'dummy',
        'job': 'dummy',
        'country': 'dummy'
    }
    print(chatId)
    if users.find_one({'_id': chatId}) != None:
        return
    # todo support users old users re-registring on the bot
    users.insert_one(user)
    print('User added')
    return


# gets the info of the user
def get_user(chat_id):
    result = users.find_one({'_id': chat_id})
    return result['firstName'], result['lastName'], result['userName']


def set_language(chat_id, lang):
    users.update_one({'_id': chat_id}, {'$set': {'lang': lang}})


def get_language(chat_id):
    return users.find_one({'_id': chat_id})['lang']


# gets the the list of all questions in english
def get_all_questions():
    return questions.find({})


# adds an answer to the database
def add_answer(chatId, question_id, answer, time):
    entry = {
        'chatId': chatId,
        'questionId': question_id,
        'answer': answer,
        'time': time
    }
    answers.insert_one(entry)
    already_answered = users.find_one({'_id': chatId}, {'answered': 1})['answered']
    already_answered.append(question_id)
    users.update_one({'_id': chatId}, {'$set': {'answered': already_answered}})


# the user will answer questions one by one in a survey, this function initiates the survey
def start_survey_session(chatId):
    users.update_one({'_id': chatId}, {'$set': {'sessionOn': True,
                                                'lastSession': datetime.now(),
                                                'answered': ['dummy_question']}})


# picks a question that is not yet answered by the user
def pick_question(chatId):
    already_answered = users.find_one({'_id': chatId}, {'answered': 1})
    #question = questions.find_one({})
    question = list(questions.aggregate([
        {'$sample': {'size': 1}}
    ]))[0]

    if already_answered != None:
        #question = questions.find_one({'_id': {'$nin': already_answered['answered']}})
        if len(already_answered['answered'])>11:
            return None
        question = list(questions.aggregate([
            { '$match': {'_id': {'$nin': already_answered['answered']}}},
            { '$sample': {'size': 1}}
        ]))[0]
        '''for i in sample:
            question = i
            print(question)'''

    if (question == None):
        return None

    users.update_one({'_id': chatId}, {'$set': {'lastPicked': question['_id']}})
    return question

def set_last_msg(chatId,msg):
    users.update_one({'_id': chatId}, {'$set': {'last_msg': msg}})

def get_last_msg(chatId):
    return users.find_one({'_id':chatId},{'last_msg':1})['last_msg']

# checks the id of the last asked question to the user
def last_asked_question(chatId):
    return users.find_one({'_id': chatId}, {'lastPicked': 1})['lastPicked']


# closes the survey session
def close_survey_session(chatId):
    users.update_one({'_id': chatId}, {'$set': {'sessionOn': False,
                                                'answered': []}})


def last_survey_session(chatId):
    curr = users.find_one({'_id': chatId})['lastSession']
    if (curr == 'dummy'):
        return None
    return curr


def get_session_state(chatId):
    return users.find_one({'_id': chatId})['sessionOn']


# extra user info
def set_marital(chat_id, status):
    users.update_one({'_id': chat_id}, {'$set': {'marital': status}})


def set_birthdate(chat_id, data):
    users.update_one({'_id': chat_id}, {'$set': {'birthdate': data}})


def set_job(chat_id, data):
    users.update_one({'_id': chat_id}, {'$set': {'job': data}})


def set_children(chat_id, data):
    users.update_one({'_id': chat_id}, {'$set': {'children': data}})


def set_country(chat_id, data):
    users.update_one({'_id': chat_id}, {'$set': {'country': data}})

def set_gender(chat_id, data):
    users.update_one({'_id': chat_id}, {'$set': {'gender': data}})

def get_birthdate(chat_id):
    return users.find_one({'_id':chat_id})['birthdate']

def get_country(chat_id):
    return users.find_one({'_id':chat_id})['country']

def get_job(chat_id):
    return users.find_one({'_id':chat_id})['job']


res = get_all_questions()


def users_to_survey():
    all = users.find({})
    res = []
    now = datetime.now()
    interval = 60*60*72  # 3 days
    for i in all:
        last = i['lastSession']
        if (last == 'dummy'):
            res.append(i['_id'])
        delta = now - last
        if (delta.total_seconds() > interval and i['sessionOn']==False):
            res.append(i['_id'])

    return res




print('Done')


# utility functions
def make_keyboard(answer_format):
    # print(type(answer_format))
    l = len(answer_format)
    res = []
    for i in range(l):
        item = InlineKeyboardButton(answer_format[l - i - 1], callback_data=str(l-i-1))
        res.append([item])
    return res


'''telegram API part'''

tgbot_token = '1782336868:AAFvd7P9H4Vs09S8T5p4_86cHXuNZIOuTBg'

updater = Updater(token=tgbot_token, use_context=True)
dispatcher = updater.dispatcher

main_menu_keyboard = [[KeyboardButton('/survey'),
                       KeyboardButton('/settings'),
                       KeyboardButton('/happiness_profile')]]
reply_kb_markup = ReplyKeyboardMarkup(main_menu_keyboard,
                                      resize_keyboard=True,
                                      one_time_keyboard=True)


# for handling the start command
def start(update, context):
    add_user(update.effective_chat.id, update.effective_chat.first_name, update.effective_chat.last_name,
             update.effective_chat.username)

    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=strings['eng']['start.hello'] + update.effective_chat.first_name + strings['eng']['start.rest']
                             +'\n\n'+strings['rus']['start.hello'] + update.effective_chat.first_name + strings['rus']['start.rest'],
                             reply_markup=reply_kb_markup)


start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)

# inline keyboards





# for the command survey
def survey(update, context):
    lang = get_language(update.effective_chat.id)
    lastSurvey = last_survey_session(update.effective_chat.id)

    if (get_session_state(update.effective_chat.id)):
        delta = datetime.now() - lastSurvey
        minutes_elapsed = delta.total_seconds() / 60
        if(minutes_elapsed>4):
            last_msg = get_last_msg(update.effective_chat.id)
            context.bot.delete_message(chat_id=update.effective_chat.id,
                                       message_id=last_msg)
            close_survey_session(update.effective_chat.id)

        else:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=strings[lang]['survey.duplicate'])
            return

    if (lastSurvey != None):
        delta = datetime.now() - lastSurvey
        minutes_elapsed = delta.total_seconds() / 60
        if (minutes_elapsed < 2):
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=strings[lang]['survey.successive'])
            return

    start_survey_session(update.effective_chat.id)
    question = pick_question(update.effective_chat.id)
    msg = context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=question[lang],
                                   reply_markup=InlineKeyboardMarkup(make_keyboard(question['format'][lang])))
    set_last_msg(update.effective_chat.id,msg.message_id)


survey_handler = CommandHandler('survey', survey)
dispatcher.add_handler(survey_handler)

# for the command settings






def settings(update, context):
    lang = get_language(update.effective_chat.id)

    settings_keyboard = [
        [
            InlineKeyboardButton(strings[lang]['keyboard.settings.lang'], callback_data='lang')

        ]
        ,
        [
            InlineKeyboardButton(strings[lang]['keyboard.settings.info'],
                                 callback_data='extraInfo')
        ]
    ]

    context.bot.send_message(chat_id=update.effective_chat.id, text=strings[lang]['settings'],
                             reply_markup=InlineKeyboardMarkup(settings_keyboard))


dispatcher.add_handler(CommandHandler('settings', settings))


def profile(update, context):
    lang = get_language(update.effective_chat.id)
    context.bot.send_message(chat_id=update.effective_chat.id, text=strings[lang]['computing_happiness'])

    res = print_aspects(update.effective_chat.id)
    context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(str(update.effective_chat.id)+'.png', 'rb'))
    msg = strings[lang]['happiness.first']
    for a in res:
        msg += a + " : " + str(int(res[a]*100)/100) + " / 10 \n"
    msg+= strings[lang]['happiness.second']
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=msg)


dispatcher.add_handler(CommandHandler('happiness_profile', profile))


def help(update, context):
    lang = get_language(update.effective_chat.id)
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text= strings[lang]['help'])


dispatcher.add_handler(CommandHandler('help', help))



# for handling inline keyboard buttons
def button(update, context):
    query = update.callback_query
    lang = get_language(update.effective_chat.id)
    query.answer()

    next_question_keyboard = [
        [
            InlineKeyboardButton(strings[lang]['keyboard.continue_survey'], callback_data='another'),
            InlineKeyboardButton(strings[lang]['keyboard.stop_survey'], callback_data='enough'),
        ]
    ]

    # continue survey or not
    if query.data == 'another':
        question = pick_question(update.effective_chat.id)
        if question == None:
            query.message.edit_text(strings[lang]['survey.enough'])
            close_survey_session(update.effective_chat.id)
            return

        query.message.edit_text(question[lang])
        query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(make_keyboard(question['format'][lang])))
        return

    if query.data == 'enough':
        query.message.edit_text(strings[lang]['survey.done'])
        close_survey_session(update.effective_chat.id)
        return

    # settings menu

    language_keyboard = [[InlineKeyboardButton("English " + emoji.emojize(':United_Kingdom:'), callback_data='eng')],
                         [InlineKeyboardButton("Русский " + emoji.emojize(':Russia:'), callback_data='rus')]]

    add_info_keyboard = [[InlineKeyboardButton(strings[lang]['keyboard.settings.info.gender'], callback_data='gender')],
                         [InlineKeyboardButton(strings[lang]['keyboard.settings.info.birthdate'],
                                               callback_data='birthdate')],
                         [InlineKeyboardButton(strings[lang]['keyboard.settings.info.job'],
                                               callback_data='job')],
                         [InlineKeyboardButton(strings[lang]['keyboard.settings.info.country'],
                                               callback_data='country')],
                         [InlineKeyboardButton(strings[lang]['keyboard.settings.info.marital'],
                                               callback_data='marital')],
                         [InlineKeyboardButton(strings[lang]['keyboard.settings.info.children'],
                                               callback_data='children')]]
    if query.data == 'lang':
        query.message.edit_text(strings[lang]['settings.lang'])
        query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(language_keyboard))
        return

    if query.data == 'extraInfo':
        query.message.edit_text(strings[lang]['settings.info'])
        query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(add_info_keyboard))
        return

    # language settings
    if query.data == 'rus':
        set_language(update.effective_chat.id, 'rus')
        query.message.edit_text(strings['rus']['settings.lang.rus'])
        return

    if query.data == 'eng':
        set_language(update.effective_chat.id, 'eng')
        query.message.edit_text(strings['eng']['settings.lang.eng'])
        return

    # additional info settings
    if query.data == 'birthdate':
        query.message.edit_text(strings[lang]['settings.info.birthdate'])
        set_birthdate(update.effective_chat.id,'waiting')
        #query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(birthdate_keyboard))
        return

    if query.data == 'job':
        query.message.edit_text(strings[lang]['settings.info.job'])
        set_job(update.effective_chat.id, 'waiting')
        # query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(add_info_keyboard))
        return

    if query.data == 'marital':
        query.message.edit_text(strings[lang]['settings.info.marital'])
        marital_keyboard = [[InlineKeyboardButton(strings[lang]['keyboard.marital.single'], callback_data='single')],
                            [InlineKeyboardButton(strings[lang]['keyboard.marital.partner'], callback_data='partner')],
                            [InlineKeyboardButton(strings[lang]['keyboard.marital.married'], callback_data='engaged')]]
        query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(marital_keyboard))
        return


    #adding extra data to the db
    if query.data == 'single' or query.data == 'engaged' or query.data=='partner':
        set_marital(update.effective_chat.id, query.data)
        query.message.edit_text(strings[lang]['settings.info.thanks'])
        return

    if query.data == 'country':
        set_country(update.effective_chat.id, 'waiting')
        query.message.edit_text(strings[lang]['settings.info.country'])
        return


    if query.data == 'children':
        query.message.edit_text(
            strings[lang]['settings.info.children'])

        children_keyboard = [[InlineKeyboardButton(strings[lang]['keyboard.children.none'], callback_data='none')],
                            [InlineKeyboardButton(strings[lang]['keyboard.children.one'], callback_data='one')],
                            [InlineKeyboardButton(strings[lang]['keyboard.children.two'], callback_data='two')],
                             [InlineKeyboardButton(strings[lang]['keyboard.children.threeplus'], callback_data='threeplus')]]
        query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(children_keyboard))
        return
    if query.data=='none' or query.data=='one'or query.data=='two' or query.data=='threeplus':
        number = {
            'none':0,
            'one':1,
            'two':2,
            'threeplus': '3+'
        }
        set_children(update.effective_chat.id, number[query.data])
        query.message.edit_text(strings[lang]['settings.info.thanks'])
        return

    if query.data=='gender':
        query.message.edit_text(strings[lang]['settings.info.gender'])
        gender_keyboard = [[InlineKeyboardButton(strings[lang]['keyboard.gender.male'], callback_data='male')],
                            [InlineKeyboardButton(strings[lang]['keyboard.gender.female'], callback_data='female')],
                            [InlineKeyboardButton(strings[lang]['keyboard.gender.other'], callback_data='other')]]
        query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(gender_keyboard))
        return

    if query.data=='male' or query.data=='female'  or query.data=='other':
        set_gender(update.effective_chat.id,query.data)
        query.message.edit_text(strings[lang]['settings.info.thanks'])
        return

    # getting answers to the questions
    answer = int(query.data)

    add_answer(update.effective_chat.id,
               last_asked_question(update.effective_chat.id),
               answer, datetime.now())

    query.message.edit_text(strings[lang]['survey.continue_question'])
    query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(next_question_keyboard))


updater.dispatcher.add_handler(CallbackQueryHandler(button))


# text input handler
def text(update,context):
    print("We got some text:")
    lang = get_language(update.effective_chat.id)
    print(update.message.text)
    birthdate = get_birthdate(update.effective_chat.id)

    if birthdate == 'waiting':
        x = re.search("[0-3]?[0-9]-[0-3]?[0-9]-(?:[0-9]{2})?[0-9]{2}",
                      update.message.text)
        if x==None:
            return

        set_birthdate(update.effective_chat.id, x.group())
        print(x)
        context.bot.send_message(chat_id=update.effective_chat.id,text=strings[lang]['settings.info.thanks'])

    country = get_country(update.effective_chat.id)

    if country=='waiting':
        set_country(update.effective_chat.id,update.message.text)
        context.bot.send_message(chat_id=update.effective_chat.id, text=strings[lang]['settings.info.thanks'])

    job = get_job(update.effective_chat.id)

    if job == 'waiting':
        set_job(update.effective_chat.id, update.message.text)
        context.bot.send_message(chat_id=update.effective_chat.id, text=strings[lang]['settings.info.thanks'])

    return None


updater.dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, text))


# scheduled surveys
def scheduled_survey(context: CallbackContext):
    user_list = users_to_survey()
    for id in user_list:
        lang = get_language(id)
        context.bot.send_message(chat_id=id, text=strings[lang]['auto_survey'])

        # starts a survey session with the user
        start_survey_session(id)
        question = pick_question(id)
        msg = context.bot.send_message(chat_id=id,
                                       text=question[lang],
                                       reply_markup=InlineKeyboardMarkup(make_keyboard(question['format'][lang])))
        set_last_msg(id, msg.message_id)


# set this to run repeatedly
updater.job_queue.run_repeating(scheduled_survey, 60*60*24)


# trying radar chart

# utility functions
def user_answers(chatId=None):
    if chatId==None:
        return answers.find({})
    return answers.find({'chatId': chatId})


def get_aspects():
    res = []
    questions = get_all_questions()
    for q in questions:
        for t in q['tags']:
            if not t in res:
                res.append(t)
    return res


def question_scale(questionId):
    q = questions.find_one({'_id': questionId})
    return len(q['format']['eng'])-1


def scale_answer(answer):
    #print((float(answer['answer']) / question_scale(answer['questionId'])) * 10)
    return (float(answer['answer']) / question_scale(answer['questionId'])) * 10


def get_tags_from_answer(questionId):
    res = questions.find_one({'_id': questionId})
    if res == None:
        return None
    return res['tags']


def get_scores(chatId=None):
    aspects = get_aspects()
    #print(aspects)

    res = {}
    sum = {}
    count = {}

    answers = user_answers(chatId)

    for a in aspects:
        sum[a] = 0
        count[a] = 0

    for answer in answers:
        tags = get_tags_from_answer(answer['questionId'])
        if tags==None:
            continue
        for tag in aspects:
            if tag in tags:
                sum[tag] += scale_answer(answer)
                count[tag]+=1

    for a in aspects:

        if count[a] != 0:
            res[a] = sum[a] / count[a]

    return res


def print_aspects(chatId):
    res = get_scores(chatId)
    all = get_scores()
    print(res)
    used_aspects = {}
    for a in all:
        if a in res:
            used_aspects[a] = all[a]

    make_chart(res,used_aspects,chatId = chatId)
    return res


def make_chart(scores: dict,all_scores: dict,chatId = None):
    # some other things we need
    labels = list(scores.keys())
    points = len(labels)
    labels += labels[:1]
    angles = np.linspace(0, 2 * np.pi, points, endpoint=False).tolist()
    angles += angles[:1]
    print(angles)
    values = list(scores.values())
    values += values[:1]
    all_values = list(all_scores.values())
    all_values+=all_values[:1]
    print(values)
    ## Create plot object
    fig, ax = plt.subplots(figsize=(6, 6),
                           subplot_kw=dict(polar=True))  ## Plot a new diamond with the add_to_star function

    ax.plot(angles, values, color='#d42cea', linewidth=1, label='Your happiness chart')
    ax.fill(angles, values, color='#d42cea', alpha=0.25)

    ax.plot(angles, all_values, color='#1aaf6c', linewidth=1, label='Happiness of Innopolis')
    ax.fill(angles, all_values, color='#1aaf6c', alpha=0.25)

    # making it look pretty

    ## Fix axis to star from top
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)  ## Edit x axis labels
    for label, angle in zip(ax.get_xticklabels(), angles):
        if angle in (0, np.pi):
            label.set_horizontalalignment('center')
        elif 0 < angle < np.pi:
            label.set_horizontalalignment('left')
        else:
            label.set_horizontalalignment(
                'right')  ## Customize your graphic# Change the location of the gridlines or remove them


    ax.set_rgrids([2, 4, 6, 8])
    ax.tick_params(colors='#222222')

    # Make the y-axis labels larger, smaller, or remove by setting fontsize
    ax.tick_params(axis='y', labelsize=0)

    # Make the x-axis labels larger or smaller.
    ax.tick_params(axis='x', labelsize=13)

    # Change the circle background color
    ax.set_facecolor('#FAFAFA')

    ax.set_thetagrids(np.degrees(angles), labels)
    lang = get_language(chatId)
    ax.set_title(strings[lang]['chart.title'], y=1.18)
    ax.legend(loc='upper right', bbox_to_anchor=(0.2, 1.2))

    '''
    # ax.set_rgrids([]) # This removes grid lines# Change the color of the ticks
    
    # Change the color of the circular gridlines.
    ax.grid(color='#AAAAAA')
    # Change the color of the outer circle
    ax.spines['polar'].set_color('#222222')
    # Add title and legend
    
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
    
       # Draw axis lines for each angle and label.
     '''

    print("Done with plotting !!!!!!!!!!!!")
    plt.tight_layout()
    #plt.show()

    if(chatId==None):
        fig.savefig('foo.png')
    else:
        fig.savefig(str(chatId)+'.png')


#sample = {'social': 50.0, 'freedom': 12.5, 'financial': 25.0, 'environment': 20.833333333333332,
         # 'generic': 33.333333333333336, 'Health': 7.0, 'Political': 40.0, 'Psychological': 90.0}

#make_chart(sample)

for s in res:
    print(s['eng'])
    print(question_scale(s['_id']))
    
#if running locally    
#updater.start_polling()

#if running on heroku
updater.start_webhook(listen="0.0.0.0",
                          port=int(PORT),
                          url_path=tgbot_token)
updater.bot.setWebhook('https://inno-happiness-tg-bot.herokuapp.com/' + tgbot_token)
    
updater.idle()

#extra stuff
strings = {
    'eng': {
        'help': "You seem a bit curious about what I can do, here is some help for you! "+emoji.emojize(':information:')+"\n \n"
                                  "I support the following commands:\n"
                                  "/survey : to start a short happiness survey, I will start by asking you one question, and then you decide if you want to continue or not. I think a maximum of 10 questions a day is enough for you, so I will keep that in check.\n\n"
                                  "/settings: If you don't understand me, you can change the language here. I also offer you to share some information about yourself so that I can know the context of your life, if you don't mind of course. \n\n"
                                  "/happiness_profile: The most exciting one. Here I can reveal to you what I learnt about your happiness, I will show some fancy graphs and the evolution of your well-being over time."


        , 'survey.enough': 'I guess that you have answered enough questions for today! You can chill now and be happy! '+emoji.emojize(':beaming_face_with_smiling_eyes:')
        , 'survey.done': "Survey done, thank you for sharing with me! Have a nice day!"+emoji.emojize(':smiling_face_with_hearts:')
        , 'settings.lang': "Choose your language"
        , 'settings.info':  'The following are additional informations about yourself, you are free to share them or not. They will be used for statistics and (in the future) to give you happiness advice'
        , 'settings.lang.rus': 'Questions will now be in Russian'
        , 'settings.lang.eng': 'Questions will now be in English'
        , 'settings.info.birthdate': "Enter your birthdate below, it should be in the format DD-MM-YYYY (Example: 30-06-2000)"
        , 'settings.info.job': "What is your job title (Example: Student, CTO, Business owner, Artist, Cashier ...)"
        , 'settings.info.marital': "What is your marital status?"
        , 'settings.info.children' : "How many children do you have?",
        'settings.info.country': "Where are you from originally?",
        'settings.info.gender': "Choose your gender",
        'auto_survey': 'It seems that you didn\'t check in on your happiness lately'
                                                  'in a while. Let me ask you a random question!',
        'settings.info.thanks': "Noted. Thanks for sharing.",
        'chart.title': 'Your happiness chart',
        'start.hello': 'Hello ',
        'start.rest' : "! " + emoji.emojize(':grinning_face_with_big_eyes:')+"\nUse the command /survey to start answering questions.\n\n"
                                                                                "Type /help if you wanna discover more about my features.",
        'survey.continue_question' : "Do you want to answer another question?",
        'keyboard.continue_survey': "Another question "+emoji.emojize(':winking_face:'),
        'keyboard.stop_survey': "Enough for today "+ emoji.emojize(':sleeping_face:'),
        'survey.duplicate': "You already opened another survey, you should finish that one first! "+emoji.emojize(':face_with_rolling_eyes:')+"\n"
                                      "Or, you can wait for 5 minutes and you will be able to do a new survey.",
        'survey.successive': "You did a survey less than 5 minutes ago! "
                                          "I don't think your happiness changed that much!"+emoji.emojize(':face_with_rolling_eyes:')+
                                          " You should at least wait 5 minutes between surveys!",
        'keyboard.settings.lang': "Language "+emoji.emojize(':books:'),
        'keyboard.settings.info': "Add information about myself " + emoji.emojize(':information:'),
        'keyboard.settings.info.gender': "Gender "+emoji.emojize(':female_sign:')+emoji.emojize(':male_sign:'),
        'keyboard.settings.info.birthdate' : "Birthdate "+emoji.emojize(':birthday_cake:'),
        'keyboard.settings.info.job' : "Job or occupation" +emoji.emojize(':briefcase:'),
        'keyboard.settings.info.country' : "Nationality "+emoji.emojize(':globe_showing_Europe-Africa:'),
        'keyboard.settings.info.marital' : "Marital status "+emoji.emojize(':heart_with_ribbon:'),
        'keyboard.settings.info.children' : "Number of children "+emoji.emojize(':baby:'),
        'settings': 'Settings',
        'computing_happiness': "Give me a minute! I'm computing your happiness profile ... "+emoji.emojize(':hourglass_not_done:'),
        'happiness.first': "YOUR HAPPINESS PROFILE IS HERE "+emoji.emojize(':party_popper:')+emoji.emojize(':party_popper:')+"\n\nSo, here is a chart of your strong happiness aspects, and here are the individual scores: \n\n",
        'happiness.second' : "\nNote: these scores are your all time scores",
        'keyboard.marital.single' : 'Single',
        'keyboard.marital.partner' : 'I have a partner',
        'keyboard.marital.married' : 'Engaged/Married',
        'keyboard.children.none' : "I don't have children",
        'keyboard.children.one' : "I have one child",
        'keyboard.children.two' : "I have 2 children",
        'keyboard.children.threeplus' : "I have 3 or more children",
        'keyboard.gender.male' : "Male",
        'keyboard.gender.female' : 'Female',
        'keyboard.gender.other' : 'Other'

    },
    'rus': {
        'help': "Вам, кажется, немного любопытно, что я могу сделать, вот вам и помощь! "+emoji.emojize(':information:')+"\n \n"
                                  "Я поддерживаю следующие команды:\n"
                                  "/survey : чтобы начать краткий опрос счастья, я начну с того, что задам вам один вопрос, а затем вы решите, хотите ли вы продолжать или нет. Я думаю, что вам достаточно максимум 10 вопросов в день, так что я буду держать это под контролем.\n\n"
                                  "/settings: Если вы не понимаете меня, вы можете изменить язык здесь. Я также предлагаю вам поделиться некоторыми сведениями о себе, чтобы я мог узнать контекст вашей жизни, если вы, конечно, не возражаете. \n\n"
                                  "/happiness_profile: Самый волнующий. Здесь я могу рассказать вам, что я узнал о вашем счастье, я покажу некоторые причудливые графики и эволюцию вашего благополучия с течением времени."


        , 'survey.enough': 'Я думаю, что на сегодня вы ответили на достаточно вопросов! Теперь ты можешь расслабиться и быть счастливой! '+emoji.emojize(':beaming_face_with_smiling_eyes:')
        , 'survey.done': "Опрос закончен, спасибо, что поделились со мной! Хорошего дня!"+emoji.emojize(':smiling_face_with_hearts:')
        , 'settings.lang': "Выберите свой язык"
        , 'settings.info':  'Ниже приведены дополнительные сведения о себе, вы вольны ими делиться или нет. Они будут использоваться для статистики и (в будущем) давать вам советы по счастью'
        , 'settings.lang.rus': 'Вопросы теперь будут на русском языке'
        , 'settings.lang.eng': 'Вопросы теперь будут на английском'
        , 'settings.info.birthdate': "Введите свою дату рождения ниже, она должна быть в формате ДД-ММ-ГГГГ (пример: 30-06-2000)"
        , 'settings.info.job': "Какова ваша должность (Пример: Студент, технический директор, Владелец бизнеса, Художник, Кассир ...)"
        , 'settings.info.marital': "Каково ваше семейное положение?"
        , 'settings.info.children' : "Сколько у вас детей?",
        'settings.info.country': "Откуда вы родом?",
        'settings.info.gender': "Выберите свой пол",
        'auto_survey': "Похоже, ты давно не проверял свое счастье. Позвольте мне задать вам случайный вопрос!",
        'settings.info.thanks': "Отмеченный. Спасибо, что поделились.",
        'chart.title': 'Ваша карта счастья',
        'start.hello': 'Привет ',
        'start.rest' : "! " + emoji.emojize(':grinning_face_with_big_eyes:')+"\nИспользуйте команду /survey, чтобы начать отвечать на вопросы.\n\n"
                                                                                "Введите /help, если вы хотите узнать больше о моих функциях.",
        'survey.continue_question' : "Хотите ответить еще на один вопрос?",
        'keyboard.continue_survey': "Еще один вопрос "+emoji.emojize(':winking_face:'),
        'keyboard.stop_survey': "На сегодня хватит "+ emoji.emojize(':sleeping_face:'),
        'survey.duplicate': "Вы уже открыли еще один опрос, вы должны закончить его первым! "+emoji.emojize(':face_with_rolling_eyes:')+"\n"
                                      "Или вы можете подождать 5 минут, и вы сможете сделать новый опрос.",
        'survey.successive': "Вы провели опрос менее 5 минут назад! "
                                          "Не думаю, что твое счастье так уж сильно изменилось!"+emoji.emojize(':face_with_rolling_eyes:')+
                                          " Вы должны хотя бы подождать 5 минут между опросами!",
        'keyboard.settings.lang': "Язык "+emoji.emojize(':books:'),
        'keyboard.settings.info': "Добавить информацию о себе " + emoji.emojize(':information:'),
        'keyboard.settings.info.gender': "Пол "+emoji.emojize(':female_sign:')+emoji.emojize(':male_sign:'),
        'keyboard.settings.info.birthdate' : "Дата рождения "+emoji.emojize(':birthday_cake:'),
        'keyboard.settings.info.job' : "Работа или профессия" +emoji.emojize(':briefcase:'),
        'keyboard.settings.info.country' : "Национальность "+emoji.emojize(':globe_showing_Europe-Africa:'),
        'keyboard.settings.info.marital' : "Семейное положение "+emoji.emojize(':heart_with_ribbon:'),
        'keyboard.settings.info.children' : "Количество детей "+emoji.emojize(':baby:'),
        'settings': 'Настройки',
        'computing_happiness': "Дай мне минутку! Я вычисляю твой профиль счастья ... "+emoji.emojize(':hourglass_not_done:'),
        'happiness.first': "ВАШ ПРОФИЛЬ СЧАСТЬЯ ЗДЕСЬ "+emoji.emojize(':party_popper:')+emoji.emojize(':party_popper:')+"\n\nИтак, вот диаграмма ваших сильных аспектов счастья, а вот индивидуальные оценки: \n\n",
        'happiness.second' : "\nПримечание: эти баллы-ваши баллы за все время",
        'keyboard.marital.single' : 'Одиночный',
        'keyboard.marital.partner' : 'У меня есть партнер',
        'keyboard.marital.married' : 'Помолвлен/Женат',
        'keyboard.children.none' : "У меня нет детей",
        'keyboard.children.one' : "У меня один ребенок",
        'keyboard.children.two' : "У меня 2 ребенка",
        'keyboard.children.threeplus' : "У меня есть 3 или более детей",
        'keyboard.gender.male' : "Мужчина",
        'keyboard.gender.female' : 'Женский',
        'keyboard.gender.other' : 'Другой'

    }
}
