import os
from dotenv import load_dotenv
import ast
import logging
from telethon import TelegramClient,errors,events
from telethon.sessions import StringSession
from datetime import timezone
from telethon.tl.types import MessageMediaWebPage,MessageService,KeyboardButtonUrlAuth,ReplyInlineMarkup
from telethon.tl.custom.button import Button
from telethon.tl import functions
import asyncio

logging.basicConfig(format='[%(asctime)s --- %(filename)s line %(lineno)d --- %(levelname)s] --- %(message)s', level=logging.INFO) #for detailed logging

load_dotenv() #loading environment variables from .env file

str1 = os.environ.get("STREAMS") #loading the environment variable "STREAMS" to a variable str1
str2 = str1.split(";") #splitting at the semi-colons ; which is used as the separator between different forwarding streams
str3 = ["[" + x + "]" for x in str2] #enclosing each of the forwarding streams in square brackets
str4 = ','.join(str3) #joining the forwarding streams together, separated by commas
str5 = "[" + str4 + "]" #enclosing the entire thing in square brackets, which is relevant for correct recognition as a list of a list when there is only one stream
chatids = ast.literal_eval(str5) #converting the string into an array
#print(chatids)

def appendto(a,alist): #defining a function which is used repeatedly later in the code
    '''if given a value, adds it to the given list, and if given a list, adds its elements to the given list'''
    if isinstance(a,list): #if 'a' is a list
        alist += a #equivalent to alist = alist + a, combining the two lists together
    else:
        alist.append(a) #.append() for adding a single element
    return alist

idsdict = {} #initialise a dictionary, to contain each source chat (as a key) with a list of its destination chats as its value
for x in chatids: #iterate through the forwarding streams
    if isinstance(x[0],list): #i.e. if there are multiple sources in this stream, such that they have been put in a list (as dictated by the syntax, enclosing them in square brackets)
        for i in x[0]: #iterate through the sources of the stream
            #this assigns to the key (the source) a list of its destination chats as its key:
            #print(i)
            idsdict[i] = appendto(x[1],idsdict.get(i,[])) #idsdict.get(i,[]) returns the value (which should be a list by construction) of i if it already exists as a key in idsdict, else it returns an empty list, and either way adds x[1] to the list (or adds the elements of x[1] if it itself is a list)
    else: #if there's only one source in the stream, such that x[0] corresponds to only one source
        #print(x[0])
        idsdict[x[0]] = appendto(x[1],idsdict.get(x[0],[]))
#print(idsdict)

ss = os.environ.get("SESSION_STRING")
bt = os.environ.get("BOT_TOKEN")

apiid = os.environ.get("API_ID")
apihash = os.environ.get("API_HASH")

client = TelegramClient(StringSession(ss),apiid,apihash,connection_retries=None,sequential_updates=True,flood_sleep_threshold=0) #connection_retries=None to keep on trying to reconnect when connection is lost, flood_sleep_threshold=0 so it doesn't automatically sleep for any floodwait errors
client.parse_mode = None #to avoid the text of Message objects being parsed as markdown etc
bot = TelegramClient(None,apiid,apihash,connection_retries=None,sequential_updates=True,flood_sleep_threshold=0)
bot.parse_mode = None

sourceids = [*idsdict] #a list of the keys of idsdict, i.e. a list of the source chats
#print(sourceids)

async def start_clients():
    await asyncio.gather(client.start(),bot.start(bot_token=bt))
client.loop.run_until_complete(start_clients())

msgids = {} #initialise a dictionary, to contain each source chat (as a key) with the ID of the most recent message as its value.
async def get_latest_message():
    async for x in client.iter_dialogs(): #iterating through all the user's dialogs
        if x.id in sourceids:
            msgids[x.id] = x.message.id #the ID of the top message in the chat; this may not actually be the most recent message if the most recent message was deleted, leaving an earlier message on top, but this has little practical effect (see below)
            #logging.info('retrieved last message of chat {}'.format(x.id))
            #print(len(msgids))
client.loop.run_until_complete(get_latest_message())

msgblist = {} #a blacklist of messages not to be copied; this is for messages sent to destination channels that are also source channels
for id in sourceids:
    msgblist[id] = []

async def process_message(msg,source,too_long=False,string=None):
    """copy the message to the destinatoin chats"""
    for dest in idsdict[source]:
        step = 1 #the step is to keep track of which step of processing the message we are on, so we don't repeat that step when retrying after a floodwait, and instead move straight to the step on which we encountered the floodwait
        while True: #infinite looping; this is to try the commands again for this message if the below-specified exception is raised
            try:
                if step == 1:
                    a = await client.send_message(dest,msg)
                    if dest in sourceids: #if the destination chat is also a source chat ...
                        msgblist[dest].append([dest,a.id,None]) #... add the message to the blacklist so it doesn't get copied
                    #logging.info(f'message {msg.id} from chat {msg.chat_id} copied')
                    step = 2 #copying the message is copmlete, so moving onto the next step
                if msg.buttons and step == 2: #'msg.buttons' as step 2 is only to be carried out on messages with buttons, and 'step == 2' so as not to repeat it if it's completed successfully and we're encountering a floodwait on step 3
                    #if the message was copied by a user, then it was copied without its buttons ...
                    b = await bot.edit_message(a,buttons=msg.buttons) #... so add them on using a bot client
                    if dest in sourceids:
                        msgblist[dest].append([dest,b.id,b.edit_date])
                    #logging.info(f'message {msg.id} from chat {msg.chat_id} edited')
                    step = 3
                if too_long: #stpe 3 only applicable if the character limit of msg.message is exceeded, to send the caption separately; no need to check for 'step == 3' as this is last anyway
                    c = await bot.send_message(dest,string[2:],reply_to=a) #remove the line breaks at the beginning of the above string, as it's not being added to previously existing text so nothing to separate it from
                    if dest in sourceids:
                        msgblist[dest].append([dest,c.id,None])
                    #logging.info(f'message {msg.id} from chat {msg.chat_id} captioned')
            except errors.FloodWaitError as e:
                logging.info('FloodWait error encountered, retrying after {} seconds'.format(e.seconds))
                await asyncio.sleep(e.seconds)
                logging.info('Retrying')
                continue #continue to the next iteration of the while loop
            break #the code in the 'try:' statement executed successfully and the while loop needs to be brokem manually

async def copy_message(message,source): #defining a function which is used repeatedly later in the code
    """edit the buttons of the message as necessary and add the caption"""
        
    if type(message.reply_markup) == ReplyInlineMarkup: #checking if the message has reply_markup and if so, then is it inline keyboard buttons
        #print(print(message.reply_markup.__dict__))
        for i in range(len(message.reply_markup.rows)): #iterating through each row of buttons
            #print(row.__dict__)
            for j in range(len(message.reply_markup.rows[i].buttons)): #iterating through the button in each row
                if type(message.reply_markup.rows[i].buttons[j]) == KeyboardButtonUrlAuth: #change any login urls to regular urls
                    #print(message.reply_markup.rows[i].buttons[j].__dict__)
                    #print(message.buttons[i][j].button.__dict__)
                    message.reply_markup.rows[i].buttons[j] = Button.url(text = message.reply_markup.rows[i].buttons[j].text, url = message.reply_markup.rows[i].buttons[j].url)
                    message.buttons[i][j].button = message.reply_markup.rows[i].buttons[j]
                    #print(message.reply_markup.rows[i].buttons[j].__dict__)
                    #print(message.buttons[i][j].button.__dict__)
    
    string = '\n\nchat_ID: ' + str(message.chat_id) + '\nmessage_ID: ' + str(message.id) #initialising the string to be added to the text/caption of the copied message
    if message.edit_date: #if the message is a previous message edited, then edit_date is the date of the most recent edit, which is what I want to output
        date = message.edit_date.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC') #converts the date from UNIX time to a more readable format
        string += ' (a_previous_message_edited)' + '\ndate: ' + date
    else: #i.e. if the message is brand new
        date = message.date.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        string += '\ndate: ' + date
    if message.is_group: #if the message was sent in a group (including megagroups and gigagroups)
        if message.sender: #in which case the sender seems to be either a user/bot or a channel that's linked to the group
            string += '\nsender_ID: ' + str(message.sender_id)
        else: #in which case the sender seems to be an anonymous group admin
            string += '\nsender_ID: ' + str(message.chat_id) #i.e. just the ID of the group in which it's been sent
    if message.reply_to:
        string += '\nin_reply_to_message_ID: ' + str(message.reply_to.reply_to_msg_id)
    if message.fwd_from: #if this property exists, it indicates the message is forwarded
        fdate = message.fwd_from.date.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')   
        if message.forward._sender_id: #in which case I think the 'Forwarded from:' tag contains a user's or bot's name (even if their original message was sent in a group rather than a private chat) and if it's a user then they have allowed linking to their account when forwarding their messages
            string += '\nforwarded_from_user_ID: ' + str(message.forward._sender_id) + '\nforwarded_from_message_date: ' + fdate
        elif message.fwd_from.from_name: #in which case I think the 'Forwarded from:' tag contains a user's name (even if their original message was sent in a group rather than a private chat) and in this case the user didn't allow linking to their account when forwarding their messages
            string += '\nforwarded_from_user_name: ' + str(message.fwd_from.from_name) + '\nforwarded_from_message_date: ' + fdate
        elif message.forward._chat.megagroup or (hasattr(message.forward._chat,'gigagroup') and message.forward._chat.gigagroup): #Using hasattr for gigagroup because when dealing with an inaccessible channel (ChannelForbidden object) I got an AttributeError when using just 'if message.forward._chat.gigagroup' as the object didn't have the 'gigagroup' attribute
            string += '\nforwarded_from_chat_ID: ' + '-100' + str(message.fwd_from.from_id.channel_id) + ' (supergroup)\nforwarded_from_message_date: ' + fdate #it seems the message is forwarded from an anonymous group admin
        elif message.fwd_from.from_id.channel_id: #in which case, with neither ._chat.megagroup nor ._chat.megagroup being 'true, I think it's forwarded from a channel, in which case the ID of the original message is also accessible
            string += '\nforwarded_from_chat_ID: ' + '-100' + str(message.fwd_from.from_id.channel_id) + '\nforwarded_from_message_ID: ' + str(message.forward.channel_post) + '\nforwarded_from_message_date: ' + fdate
        else:
            logging.info("This message has the `.fwd_from attribute` but none of `.forward._sender_id`, `.fwd_from.from_name`, `.forward._chat.megagroup`, `.forward._chat.gigagroup` or `.fwd_from.from_id.channel_id` attributes. I'm not adding the 'Forwarded from:' part of the caption to it; look into it. Here it is printed out:")
            print(message)
            logging.info('and here is message.forward:')
            print(vars(message.forward))    
    if message.media:
        if type(message.media) == MessageMediaWebPage: #a media type, but not subject to the 1024 character restriction
            if len(message.message + string) <= 4096: #to ensure it doesn't go above the limit for text messages, which I think is 4096 characters
                message.message += string #adding the above string to the text of the message
                await process_message(message,source) #copy the message (not forward) to the destination chat
            else: #if the combined string would be over the limit for text messages, send the message without the added string and send the string as a reply to it
                await process_message(message,source,True,string)
        elif message.message: #media that already has a caption
            if len(message.message + string) <= 1024: #to ensure it doesn't go above the limit for captions on media messages, which I think is 1024 characters
                message.message += string #adding the above string to the caption of the message
                await process_message(message,source)
            else:
                await process_message(message,source,True,string)
        else: #if it doesn't already have a caption, make the above string its caption
            message.message = string[2:]
            await process_message(message,source)
    else:
        if len(message.message + string) <= 4096:
            message.message += string
            await process_message(message,source) 
        else:
            await process_message(message,source,True,string)

@client.on(events.NewMessage(chats=sourceids))
@client.on(events.MessageEdited(chats=sourceids))
async def function(update):
    message = update.message
    #logging.info('id and chat of this update:', message.id, message.chat_id)
    source = message.chat_id #the ID of the chat in which the message was sent
    cid = msgids[source] + 1 #this is the expected ID of the next message that gets sent to the source chat: that of the most recent message plus one
    copy = True
    for idx,msgdetails in enumerate(msgblist[source]): #first, if the update is the result of a blacklisted message, don't copy it
        if msgdetails == [source,message.id,message.edit_date]:
            copy = False
            msgblist[source].pop(idx) #remove the message from the blacklist now, so that it can be copied subsequently in the unlikely event it's edited again the same second (resulting in same edit_date)
            break
    if message.id > cid: #if the ID of this message is higher than the expected ID, copy over all messages from the expected ID onwards, just in case something has been missed
        async for msg in client.iter_messages(source,offset_id=cid-1,reverse=True): #iterate through all messages from the expected ID to the most recent message; 'reverse=True' to iterate from older message to newer:
            if not type(msg) == MessageService: #if it's a service message, then I don't think it's possible to copy it and trying to do so may return an error, so skip it; the if statement could be triggered if the most recent message(s) in the source channel had been deleted and the next message was a service message
                if msg.id==message.id and not copy: #for the message of the update, only copy if copy==True, otherwise just move to next message in the for loop without
                    continue
                await copy_message(msg,source)
            msgids[source] = msg.id #update the ID of the most recent message to be that of the message just sent
    #Note that had the top message not actually been the most recent message, cid would be lower than the expected ID, so even if this message had the expected ID, the above if statement would still be true, but all messages between cid and the expected ID are deleted so the only messages that get copied are from the expected ID onwards
    elif type(message) == MessageService: #if it's a service message and hence can't be copied, still update the message ID of the most recent message to its ID, so that the if statement above doesn't get unnecessarily triggered on the next non-service message
        msgids[source] = message.id
    elif message.edit_date: #if the message is just a previous message edited, then it retains its original ID, so the ID is less than the expected ID, so copy the message without updating the ID of the most recent message
        if copy:
            await copy_message(message,source) #otherwise, proceed as planned
    elif message.id < cid: #if the message's ID is less than the expected ID but it's not an edited message, then it's not clear so might be worth looking at; one case where this does occur is when a large no. messages is forwarded to the source
        logging.error('expected ID of next message in chat {0} is {1} but this message has ID {2}; not copying it'.format(source,cid,message.id))
    else: #if the message is brand new with the expected ID
        if copy:
            await copy_message(message,source)
        msgids[source] = message.id

client.start()
client.run_until_disconnected()