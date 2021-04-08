from datetime import datetime

from matplotlib import pyplot as plt
import numpy as np
import pymongo
from telegram import *
from telegram.ext import *
import emoji
import re

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
        'sessionOn': False
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


res = get_all_questions()


def users_to_survey():
    all = users.find({})
    res = []
    now = datetime.now()
    interval = 60 * 60 * 24  # 24 hours
    for i in all:
        last = i['lastSession']
        if (last == 'dummy'):
            res.append(i['_id'])
        delta = now - last
        if (delta.total_seconds() > interval):
            res.append(i['_id'])

    return res


for s in res:
    print(s['eng'])

print('Done')


# utility functions
def make_keyboard(answer_format):
    # print(type(answer_format))
    l = len(answer_format)
    res = []
    for i in range(l):
        item = InlineKeyboardButton(answer_format[l - i - 1], callback_data=str(i))
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
                             text="Hello " + update.effective_chat.first_name + "! " + emoji.emojize(':grinning_face_with_big_eyes:')+"\n Use the command /survey to start answering questions.\n\n"
                                                                                "Type /help if you wanna discover more about my features.",
                             reply_markup=reply_kb_markup)


start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)

# inline keyboards


next_question_keyboard = [
    [
        InlineKeyboardButton("Another question "+emoji.emojize(':winking_face:'), callback_data='another'),
        InlineKeyboardButton("Enough for today "+ emoji.emojize(':sleeping_face:'), callback_data='enough'),
    ]
]


# for the command survey
def survey(update, context):
    lastSurvey = last_survey_session(update.effective_chat.id)

    if (get_session_state(update.effective_chat.id)):
        delta = datetime.now() - lastSurvey
        minutes_elapsed = delta.total_seconds() / 60
        if(minutes_elapsed>5):
            last_msg = get_last_msg(update.effective_chat.id)
            context.bot.delete_message(chat_id=update.effective_chat.id,
                               message_id=last_msg)
            close_survey_session(update.effective_chat.id)

        else:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="You already opened another survey, you should finish that one first! "+emoji.emojize(':face_with_rolling_eyes:')+"\n"
                                      "Or, you can wait for 5 minutes and you will be able to do a new survey.")
            return

    if (lastSurvey != None):
        delta = datetime.now() - lastSurvey
        minutes_elapsed = delta.total_seconds() / 60
        if (minutes_elapsed < 1):
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="You did a survey less than 5 minutes ago! "
                                          "I don't think your happiness changed that much!"+emoji.emojize(':face_with_rolling_eyes:')+
                                          " You should at least wait 5 minutes between surveys!")
            return

    start_survey_session(update.effective_chat.id)
    question = pick_question(update.effective_chat.id)
    lang = get_language(update.effective_chat.id)
    msg = context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=question[lang],
                                   reply_markup=InlineKeyboardMarkup(make_keyboard(question['format'][lang])))
    set_last_msg(update.effective_chat.id,msg.message_id)


survey_handler = CommandHandler('survey', survey)
dispatcher.add_handler(survey_handler)

# for the command settings

settings_keyboard = [
    [
        InlineKeyboardButton("Language "+emoji.emojize(':books:'), callback_data='lang')

    ]
    ,
    [
        InlineKeyboardButton("Add information about myself "+emoji.emojize(':information:'), callback_data='extraInfo')
    ]
]

language_keyboard = [[InlineKeyboardButton("English "+emoji.emojize(':United_Kingdom:'), callback_data='eng')],
                     [InlineKeyboardButton("Russian"+emoji.emojize(':Russia:'), callback_data='rus')]]

add_info_keyboard = [[InlineKeyboardButton("Gender "+emoji.emojize(':female_sign:')+emoji.emojize(':male_sign:'), callback_data='gender')],
                     [InlineKeyboardButton("Birthdate "+emoji.emojize(':birthday_cake:'), callback_data='birthdate')],
                     [InlineKeyboardButton("Job or occupation" +emoji.emojize(':briefcase:'), callback_data='job')],
                     [InlineKeyboardButton("Nationality "+emoji.emojize(':globe_showing_Europe-Africa:'), callback_data='country')],
                     [InlineKeyboardButton("Marital status "+emoji.emojize(':heart_with_ribbon:'), callback_data='marital')],
                     [InlineKeyboardButton("Number of children "+emoji.emojize(':baby:'), callback_data='children')]]


def settings(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="-- SETTINGS --",
                             reply_markup=InlineKeyboardMarkup(settings_keyboard))


dispatcher.add_handler(CommandHandler('settings', settings))


def profile(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Give me a minute! I'm computing your happiness profile ... "+emoji.emojize(':hourglass_not_done:'))

    res = print_aspects(update.effective_chat.id)
    context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(str(update.effective_chat.id)+'.png', 'rb'))
    msg = "YOUR HAPPINESS PROFILE IS HERE "+emoji.emojize(':party_popper:')+emoji.emojize(':party_popper:')+"\n\nSo, here is a chart of your strong happiness aspects, and here are the individual scores: \n\n"
    for a in res:
        msg += a + " : " + str(int(res[a]*100)/100) + " / 10 \n"
    msg+= "\nNote: these scores are your all time scores"
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=msg)


dispatcher.add_handler(CommandHandler('happiness_profile', profile))


def help(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="You seem a bit curious about what I can do, here is some help for you! "+emoji.emojize(':information:')+"\n \n"
                                  "I support the following commands:\n"
                                  "/survey : to start a short happiness survey, I will start by asking you one question, and then you decide if you want to continue or not. I think a maximum of 10 questions a day is enough for you, so I will keep that in check.\n\n"
                                  "/settings: If you don't understand me, you can change the language here. I also offer you to share some information about yourself so that I can know the context of your life, if you don't mind of course. \n\n"
                                  "/happiness_profile: The most exciting one. Here I can reveal to you what I learnt about your happiness, I will show some fancy graphs and the evolution of your well-being over time.")


dispatcher.add_handler(CommandHandler('help', help))


# for handling inline keyboard buttons
def button(update, context):
    query = update.callback_query
    query.answer()

    # continue survey or not
    if query.data == 'another':
        question = pick_question(update.effective_chat.id)
        if question == None:
            query.message.edit_text(
                'I guess that you have answered enough questions for today! You can chill now and be happy! '+emoji.emojize(':beaming_face_with_smiling_eyes:'))
            close_survey_session(update.effective_chat.id)
            return
        lang = get_language(update.effective_chat.id)
        query.message.edit_text(question[lang])
        query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(make_keyboard(question['format'][lang])))
        return

    if query.data == 'enough':
        query.message.edit_text("Survey done, thank you for sharing with me! Have a nice day!"+emoji.emojize(':smiling_face_with_hearts:'))
        close_survey_session(update.effective_chat.id)
        return

    # settings menu
    if query.data == 'lang':
        query.message.edit_text('Choose your language')
        query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(language_keyboard))
        return

    if query.data == 'extraInfo':
        query.message.edit_text(
            'The following are additional informations about yourself, you are free to share them or not. They will be used for statistics and (in the future) to give you happiness advice')
        query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(add_info_keyboard))
        return

    # language settings
    if query.data == 'rus':
        set_language(update.effective_chat.id, 'rus')
        query.message.edit_text('Questions will now be in Russian')
        return

    if query.data == 'eng':
        set_language(update.effective_chat.id, 'eng')
        query.message.edit_text('Questions will now be in English')
        return

    # additional info settings
    if query.data == 'birthdate':
        query.message.edit_text(
            "Enter your birthdate in the following format: DD-MM-YYYY (Example: 30-06-2000) \n NOT IMPLEMENTED")
        # query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(add_info_keyboard))
        return

    if query.data == 'job':
        query.message.edit_text(
            "What is your job title (Example: Student, CTO, Business owner, Artist, Cashier ...) \n NOT IMPLEMENTED")
        # query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(add_info_keyboard))
        return

    if query.data == 'marital':
        query.message.edit_text("What is your marital status?")
        marital_keyboard = [[InlineKeyboardButton("Single", callback_data='single')],
                            [InlineKeyboardButton("Engaged/Married", callback_data='engaged')]]
        query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(marital_keyboard))
        return

    if query.data == 'single' or query.data == 'engaged':
        set_marital(update.effective_chat.id, query.data)
        query.message.edit_text("Noted. Thanks for sharing.")

    if query.data == 'country':
        query.message.edit_text("Where are you from originally? \n NOT IMPLEMENTED")
        return

    if query.data == 'children':
        query.message.edit_text(
            "How many children do you have?. \n NOT IMPLEMENTED")
        return

    # getting answers to the questions
    answer = int(query.data)

    add_answer(update.effective_chat.id,
               last_asked_question(update.effective_chat.id),
               answer, datetime.now())

    query.message.edit_text("Do you want to answer another question?")
    query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(next_question_keyboard))


updater.dispatcher.add_handler(CallbackQueryHandler(button))


# text input handler
def text(context, update):
    print("We got some text:")

    x = re.search("^([1-9] |1[0-9]| 2[0-9]|3[0-1])(.|-)([1-9] | 0[1-9] |1[0-2])(.|-|)[1-2](0|9)[0-9][0-9]$",
                  update.message.text)
    print(x)
    # job = job_queue.run_repeating(sayhi, 5, context=update)
    return None


updater.dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, text))


# scheduled surveys
def scheduled_survey(context: CallbackContext):
    user_list = users_to_survey()
    for id in user_list:
        context.bot.send_message(chat_id=id, text='It seems that you didn\'t check in on your happiness lately'
                                                  'in a while. Let me ask you a random question!')

        # starts a survey session with the user
        start_survey_session(id)
        question = pick_question(id)
        lang = get_language(id)
        msg = context.bot.send_message(chat_id=id,
                                       text=question[lang],
                                       reply_markup=InlineKeyboardMarkup(make_keyboard(question['format'][lang])))
        set_last_msg(id, msg.message_id)


# set this to run repeatedly
updater.job_queue.run_repeating(scheduled_survey, 3600)


# trying radar chart

# utility functions
def user_answers(chatId):
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
    return len(q['format']['eng'])


def scale_answer(answer):
    return (float(question_scale(answer['questionId'])-answer['answer']) / question_scale(answer['questionId'])) * 10


def get_tags_from_answer(questionId):
    res = questions.find_one({'_id': questionId})
    if res == None:
        return None
    return res['tags']


def get_scores(chatId):
    aspects = get_aspects()
    print(aspects)

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
                sum[tag] = scale_answer(answer)
                count[tag]+=1

    for a in aspects:

        if count[a] != 0:
            res[a] = sum[a] / count[a]

    return res


def print_aspects(chatId):
    res = get_scores(chatId)
    print(res)
    make_chart(res,chatId = chatId)
    return res


def make_chart(scores: dict,chatId = None):
    # some other things we need
    labels = list(scores.keys())
    points = len(labels)
    labels += labels[:1]
    angles = np.linspace(0, 2 * np.pi, points, endpoint=False).tolist()
    angles += angles[:1]
    print(angles)
    values = list(scores.values())
    values += values[:1]
    print(values)
    ## Create plot object
    fig, ax = plt.subplots(figsize=(6, 6),
                           subplot_kw=dict(polar=True))  ## Plot a new diamond with the add_to_star function

    ax.plot(angles, values, color='#1aaf6c', linewidth=1, label='Your happiness chart')
    ax.fill(angles, values, color='#1aaf6c', alpha=0.25)

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
    ax.set_title('Your happiness chart', y=1.18)

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
updater.start_polling()
