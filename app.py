import os
from dotenv import load_dotenv
import ast
import logging
from pyrogram import Client,filters,errors
from datetime import datetime
import time

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
            idsdict[i] = appendto(x[1],idsdict.get(i,[])) #idsdict.get(i,[]) returns the value (which should be a list by construction) of i if it already exists as a key in idsdict, else it returns an empty list, and either way adds x[1] to the list (or adds the elements of x[1] if it itself is a list)
    else: #if there's only one source in the stream, such that x[0] corresponds to only one source
        idsdict[x[0]] = appendto(x[1],idsdict.get(x[0],[]))
#print(idsdict)

client = Client(os.environ.get("SESSION_STRING"),os.environ.get("API_ID"),os.environ.get("API_HASH"),workers=1) #workers=1 so that the order of the messages comes out correctly

sourceids = [*idsdict] #a list of the keys of idsdict, i.e. a list of the source chats
#print(sourceids)

client.start()
msgids = {} #initialise a dictionary, to contain each source chat (as a key) with the ID of the most recent message as its value.
co = client.get_dialogs_count() #the total number of dialogs the user has
for x in client.iter_dialogs(co+(co//100)): #iterating through all the user's dialogs; using this instead of 'client.iter_dialogs()' due to a bug in Pyrogram 1.2.9
    idc = x.chat.id #the ID of the dialog
    if idc in sourceids:
        msgids[idc] = x.top_message.message_id #the ID of the top message in the chat; this may not actually be the most recent message if the most recent message was deleted, leaving an earlier message on top, but this has little practical effect (see below)
        #logging.info('retrieved last message of chat {}'.format(idc))
client.stop()
#print(msgids)

def copy_message(message,source): #defining a function which is used repeatedly later in the code
    '''copy the given message, with the appropriate added text/caption, to the destination chats of the given source chat'''
    string = '\n\nchat_ID: ' + str(source) + '\nmessage_ID: ' + str(message.message_id) #initialising the string to be added to the text/caption of the copied message
    if message.edit_date: #if the message is a previous message edited, then edit_date is the date of the most recent edit, which is what I want to output
        date = datetime.utcfromtimestamp(message.edit_date).strftime('%Y-%m-%d %H:%M:%S UTC') #converts the date from UNIX time to a more readable format
        string += ' (a_previous_message_edited)' + '\ndate: ' + date
    else: #i.e. if the message is brand new
        date = datetime.utcfromtimestamp(message.date).strftime('%Y-%m-%d %H:%M:%S UTC')
        string += '\ndate: ' + date
    if message.reply_to_message:
        string += '\nin_reply_to_message_ID: ' + str(message.reply_to_message.message_id)
    if message.forward_date: #if this property exists, it indicates the message is forwarded
        fdate = datetime.utcfromtimestamp(message.forward_date).strftime('%Y-%m-%d %H:%M:%S UTC')
        if message.forward_from_chat: #if this property exists, then what appears in the 'Forwarded from:' tag seems to be either a channel or an anonymous group admin
            if message.forward_from_chat.type == 'supergroup':
                string += '\nforwarded_from_chat_ID: ' + str(message.forward_from_chat.id) + ' (supergroup)\nforwarded_from_message_date: ' + fdate #it seems the message is forwarded from an anonymous group admin
            elif message.forward_from_message_id: #in which case I think it is a channel, in which case the ID of the original message is also accessible
                string += '\nforwarded_from_chat_ID: ' + str(message.forward_from_chat.id) + '\nforwarded_from_message_ID: ' + str(message.forward_from_message_id) + '\nforwarded_from_message_date: ' + fdate
        elif message.forward_sender_name: #in which case I think the 'Forwarded from:' tag contains a user's name (even if their original message was sent in a group rather than a private chat) and in this case the user didn't allow linking to their account when forwarding their messages
            string += '\nforwarded_from_user_name: ' + str(message.forward_sender_name) + '\nforwarded_from_message_date: ' + fdate
        elif message.forward_from.id: #in which case I think the 'Forwarded from:' tag contains a user's or bot's name (even if their original message was sent in a group rather than a private chat) and if it's a user then they have allowed linking to their account when forwarding their messages
            string += '\nforwarded_from_user_ID: ' + str(message.forward_from.id) + '\nforwarded_from_message_date: ' + fdate
        else:
            logging.info("This message has the `.forward_date attribute` but none of `.forward_from_chat`, `.forward_sender_name` or `.forward_from.id` attributes. I'm not adding the 'Forwarded from:' part of the caption to it; look into it. Here it is printed out:")
            print(message)
    if message.media:
        if message.text: #I did find a message with media type messageMediaWebPage because of a hyperlink therein, hence this
            if len(message.text + string) <= 4096: #to ensure it doesn't go above the limit for text messages, which I think is 4096 characters
                message.text += string #adding the above string to the text of the message
                for dest in idsdict[source]: #iterating through the destination chats corresponding to the source
                    message.copy(dest) #copy the message (not forward) to the destination chat
            else: #if the combined string would be over the limit for text messages, send the message without the added string and send the string as a reply to it
                for dest in idsdict[source]:    
                    a = message.copy(dest)
                    a.reply_text(string[2:],quote=True) #remove the line breaks at the beginning of the above string, as it's not being added to previously existing text so nothing to separate it from
        elif message.caption: #media that already has a caption
            if len(message.caption + string) <= 1024:
                message.caption += string #adding the above string to the caption
                for dest in idsdict[source]:
                    message.copy(dest)
            else:
                for dest in idsdict[source]:    
                    a = message.copy(dest)
                    a.reply_text(string[2:],quote=True)
        else: #if the media doesn't already have a caption...
            cap = string[2:]
            for dest in idsdict[source]:
                message.copy(dest,cap) #...copy the message with the above string as a caption
    else:
        if len(message.text + string) <= 4096:
            message.text += string
            for dest in idsdict[source]:
                message.copy(dest)
        else:
            for dest in idsdict[source]:    
                a = message.copy(dest)
                a.reply_text(string[2:],quote=True)

@client.on_message(filters.chat(sourceids)) #only process message sent to the source chats, not messages sent to other chats
def function(client,message):
    source = message.chat.id #the ID of the chat in which the message was sent
    while True: #infinite looping; this is to try the commands again for this message if the below-specified exception is raised
        try:
            cid = msgids[source] + 1 #this is the expected ID of the next message that gets sent to the source chat: that of the most recent message plus one
            if message.message_id > cid: #if the ID of this message is higher than the expected ID, copy over all messages from the expected ID onwards, just in case something has been missed
                msglist = client.iter_history(source,offset_id=cid,reverse=True) #iterate through all messages from the expected ID to the most recent message; 'reverse=True' to iterate from older message to newer
                for msg in msglist:
                    if not msg.service: #if it's a service message, then I don't think it's possible to copy it and trying to do so may return an error, so skip it; the if statement could be triggered if the most recent message(s) in the source channel had been deleted and the next message was a service message
                        copy_message(msg,source)
                    msgids[source] = msg.message_id #update the ID of the most recent message to be that of the message just sent
            #Note that had the top message not actually been the most recent message, cid would be lower than the expected ID, so even if this message had the expected ID, the above if statement would still be true, but all messages between cid and the expected ID are deleted so the only messages that get copied are from the expected ID onwards
            elif message.service: #if it's a service message and hence can't be copied, still update the message ID of the most recent message to its ID, so that the if statement above doesn't get unnecessarily triggered on the next non-service message
                msgids[source] = message.message_id
            elif message.edit_date: #if the message is just a previous message edited, then it retains its original ID, so the ID is less than the expected ID, so copy the message without updating the ID of the most recent message
                copy_message(message,source)
            elif message.message_id < cid: #if the message's ID is less than the expected ID but it's not an edited message, then it's not clear so might be worth looking at; one case where this does occur is when a large no. messages is forwarded to the source
                logging.error('expected ID of next message in chat {0} is {1} but this message has ID {2}; not copying it'.format(source,cid,message.message_id))
            else: #if the message is brand new with the expected ID
                copy_message(message,source)
                msgids[source] = message.message_id
        except errors.FloodWait as e:
            logging.info('FloodWait error encountered, retrying after {} seconds'.format(e.x))
            time.sleep(e.x) #the error has a property x giving the number of seconds to wait before retrying
            logging.info('Retrying')
            continue #continue to the next iteration of the while loop
        break #the code in the 'try:' statement executed successfully and the while loop needs to be brokem manually

client.run() #now `function(client,message)` should be run upon updates to the `@client.on_message(...)` handler