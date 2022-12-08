# Copy-bot
A userbot for automatically copying new messages from channels and groups to which you're subscribed to channels in which you're an admin that can send messages.

The types of source chats the userbot is catered to so far are channels and groups (including regular groups, supergroups/megagroups and gigagroups/broadcast groups). The types of destination chats tested so far are mainly channels. The script would likely work for other types of source and destination chats, but these are the ones which have been tested and catered for.

- [Features](#Features)
- [Getting started](#Getting-started)
- [Background](#Background)
- [How it works](#How-it-works)
- [Handling floodwaits](#Handling-floodwaits)
- [The caption added to messages](#The-caption-added-to-messages)
- [Other notes](#Other-notes)

# Features

- Messages are copied to the destination chat without the 'Forwarded from:' tag
- You can maintain multiple copying streams, with a destination chat receiving messages from multiple source chats and copying messages from a source chat to multiple destination chats.
- Messages are copied to the destination chat in the same order in which they were sent to the source chat.
- All new messages that are sent to the source chat get copied to the destination chat, even if a large number were sent at once.
- When the script is disconnected from the internet or the system goes to sleep, it doesn't terminate – it just continues attempting to reconnect until the connection is restored and then resumes working and copies any messages that were sent whilst the internet was down (even if they were then deleted whilst the internet was still down).
- Adds a detailed caption to copied messages, giving various details about the original message
- When a message is edited in the source chat, it gets copied to the destination chat (with the caption indicating they are previous messages edited).
- Handling of floodwait errors
- Messages with buttons get copied fully with their buttons, and to do so, any login URLs are replaced with regular URLs.

# Getting started
The environment variables are to be given in a .env file. An example is shown in example.env.

1. Make an app with the Telegram API: [https://my.telegram.org/apps](https://my.telegram.org/apps) and fill in the API\_ID and API\_HASH environment variables in the .env file with the App api\_id and App api\_hash respectively.
2. Choose which user client you want to use to copy messages and obtain a Pyrogram session string for it, e.g. using option 1 of [this script](https://github.com/code29563/Telethon-Pyrogram-session-strings). Fill the envrionment variable SESSION_STRING with this session string.
3. Choose a bot client and fill the environment variable BOT_TOKEN with its bot token.
4. Ensure that the user has joined the channel/group from which messages are to be copied, and that both the bot and user are admins that can send messages in the destination channel.
3. Fill in the STREAMS environment variable, which gives details of the source chats from which messages are to be copied and the destination chats to which they are copied. You can split the streams on multiple lines, and leave spaces between the IDs and the brackets/commas/semi-colons, if you want. The syntax is as follows:
	```
	STREAMS = "
	-1000000000000,-1000000000001;
	[-1000000000002,-1000000000003],-1000000000004;
	-1000000000005,[-1000000000006,-1000000000007];
	[-1000000000008,-1000000000009],[-1000000000010,-1000000000011]
	"
	```
	means that:
	- New messages from -1000000000000 are copied to -1000000000001
	- New messages from -1000000000002 and -1000000000003 are copied to -1000000000004
	- New messages from -1000000000005 are copied to -1000000000006 and -1000000000007
	- New messages from -1000000000008 and -1000000000009 are copied to -1000000000010 and -1000000000011.

	Ensure you don't put a semi-colon on the end of the last stream listed.
	
	You can find the IDs of the chats in various ways, like with [this script](https://github.com/code29563/List-Telegram-Chat-IDs), @username\_to\_id\_bot, or exporting your Telegram data from the app as 'Machine-readable JSON' where you can find the IDs of chats you're subcribed to in results.json (but be sure to append -100 to them before inserting them in STREAMS - if they're channels or megagroups/gigagroups).
	
	Note that if a chat is a source for one chat and a destination for another, e.g.
	```
	STREAMS = "-1000000000000,-1000000000001;-1000000000001,-1000000000002"
	```
	then messages sent to -1000000000000 get copied to -1000000000001, but those messages don't then get copied from -1000000000001 to -1000000000002. If you also want to have those messages copied to -1000000000002, they can be copied directly from -1000000000000:
	```
	STREAMS = "-1000000000000,[-1000000000001,-1000000000002];-1000000000001,-1000000000002"
	```
4. Install the requirements if they're not already installed by running ‘pip install -r requirements.txt’, then run the script using 'python app.py'.

# Background
There are multiple userbots for copying new messages between chats, but they have had various issues with them.

Some of them would terminate entirely after some time when disconnected from the internet. This would specifically happen with userbots using Telethon, but could be dealt with by using the `connection_retries=None` argument to the TelegramClient object to continue trying to reconnect with no upper limit on the number of attempts. Even with this though, messages sent to the source channel whilst the internet was down and the userbot was trying to reconnect didn't get copied over to the destination channel when the connection was restored.

Other userbots using Pyrogram wouldn't terminate when disconnected from the internet. They would just wait until the connection was restored, and then copy to the destination channel any messages that were sent whilst the internet was down. Even if a message was sent to the source channel and deleted whilst the internet was down, it would still get sent to the destination channel thereafter.

They had another issue though: when the connection was restored, the messages would be sent to the destination channel in a different order to the order in which they were sent in the source channel.

This also occurred when a multiple messages are forwarded to the source channel at once - their order in the destination channel would turn out different to their order in the source channel (which would be the same as their order in the original chat from which they were forwarded).

I found this issue could also be dealt with, in Telethon by using the `sequential_updates=True` argument in the TelegramClient object, and in Pyrogram by using the `workers=1` argument in the Client object.

But they would then encounter yet another issue: When a large number of messages, usually above 50 and up to 100 (which seems to be the limit for the offical app) is forwarded to the source channel, they sometimes don't all get copied to the destination channel, whereas sometimes they would. When they didn't all get copied over to the destination channel, the number that did would vary.

If some number of messages got forwarded to the source channel and didn't all get copied over, later on the same number of messages could get forwarded to the source channel and all get copied over, so there didn't seem to be any hard boundary between when this behaviour did and didn't occur.

A pattern I did find though was related to something observable in the official Telegram app. When a large number of messages is forwarded to a chat, they might appear to come out in that chat in a different order to their order in the original chat from which they were forwarded. After closing and re-opening the app though, the order of the messages in the chat to which they were forwarded does appear the same as their order in the chat from which they were forwarded. Sometimes they would appear in the same order as in the original chat though, without having to close and re-open the app.

I found that when the latter case occurred with the source channel, they did all get copied to the destination channel. When the former case occurred with the source channel, the messages that would get copied to the destination channel were the first messages in the initial order in which they appeared in the source channel (before closing and re-opening the app), until the final message in the order of the original channel from which they were forwarded, after which messages in the initial order of the source channel wouldn't get copied. E.g. the situation would look something like this:

Original channel from which they were forwarded:
```
message 1
message 2
message 3
.
.
.
message 78
message 79
message 80
message 81
message 82
.
.
.
message 98
message 99
message 100
```

Source channel to which they were forwarded (before closing and re-opening the app):
```
message 80
message 81
message 82
.
.
.
message 98
message 99
message 100
message 1
message 2
.
.
.
message 78
message 79
```

Destination channel to which they were copied:
```
message 80
message 81
message 82
.
.
.
message 98
message 99
```


It seems this was an issue with Telegram's API, and that the userbot was receiving updates of new messages in the wrong order that they appeared in before closing and re-opening the app.

My solution to this is described below.

# How it works

Based on the input the value of the environment variable STREAMS, the script makes a list of destination chats for each source chat.

The script obtains a list of all the [dialogs](https://core.telegram.org/constructor/dialog) and checks those that correspond to the source chats. From the dialog, the 'top message' of each source chat is recorded. This is the ID of the most recent still-existing message sent to the source chat. I specify 'still-existing' as the actual most recent message sent to a chat could have been deleted.

The userbot is run and receives updates of new messages sent in the the source chats or old messages edited. Assume that the top message of a particular source chat was the actual most recent message sent in it (i.e. it hadn't been deleted). The ID of the next new message sent there is expected to be the ID of that top message plus 1.

If the userbot receives an update of a message with an ID equal to this expected ID, then the message is copied to the destination chats with its caption, and the recorded ID of the top message is updated to be the ID of this new message, which as far as the script is concerned is now the most recent message in the source chat.

When a message is edited, it retains its original ID. If the update was due to an old message being edited, then its ID is less than the expected ID of the next new message (top message +1), which is expected knowing that it's an old message receiving an edit and it's not the new most recent message in the source chat, so this newly edited message is copied to the destination chats and the recorded ID of the top message is left at its current value and not updated.

If an update received is for a message with an ID greater than the expected ID, then it may be encountering a situation like what's mentioned above, where a large number of messages were forwarded to the source chat at once and the userbot receives the updates in the wrong order. In this case the userbot separately retrieves all messages with ID >= the expected ID, up to the most recent message, then copies them one by one to the destination chats. As each message gets copied, the recorded ID of the top message is updated to be its ID, (the reason for which is explained in the next section).

So in the above example, the userbot receives the update of message 80 first, which has an ID that's 79 greater than the expected ID (the ID of message 1), so the userbot retrieves messages all messages with ID >= the expected ID (that of message 1), up to the most recent message (which is message 100), and copies them one by one to the destination chats, updating the recorded ID of the top message each iteration.

If the update received is for a message with an ID less than the expected ID and the message is not an edited message, it's neither copied nor is the ID of the top message updated. So in the above example, after receiving the update of message 80, then iterating through from message 1 to 100, copying each message and updating the ID of the top message until it's that of message 100, the userbot then receives the update for message 81, 82, ... 98, 99, which all have IDs less than the new expected ID (that of message 100 +1). It already copied those messages after receiving the update of message 80, retrieving messages 1 to 100, and copying them, so no further action is required. The script instead just outputs an error message which we know in this case isn't a cause for alarm. This is the only situation in which I envision the update being for a non-edited message with its ID less than the expected ID.

The exception to all this is a service message, e.g. that a message has been pinned in the chat or chat photo updated. Such messages can't be copied as far as I'm aware. If a service message is encountered, the ID of the top message is updated to the ID of this new service message, but no attempt is made to copy it.

If the original assumption isn't true, i.e. the top message wasn't actually the most recent message, rather the most recent message(s) had been deleted leaving an earlier message 'at the top', and hence the next new message was expected to have an ID greater than that of the top message +1, then the process described above is still implemented and no problems arise from that.

If the update is for the next new message in the source chat, then it has an ID greater than that of the top message +1 so the userbot retrieves all messages with ID >= the recorded ID of the top message +1, up to the most recent message, but all messages between the recorded top message and this new message were the (former) most recent messages that had been deleted, so nothing is retrived for their IDs and the only message that ends up getting copied is this new message for which the update was received.

Similarly, in the above example, if the messages immediately before message 1 had been deleted in the source chat, then the userbot would retrieve all messages with ID >= the recorded ID of the top message +1, through message 1, up to message 100, but those messages before message 1 have been deleted so nothing is retrieved for them, and it ends up iterating only through messages 1 to 100 and copying them, just as before.

# Messages with buttons
User clients can't send messages with inline keyboard buttons as far as I'm aware, so the userbot copies the message without its buttons, and then a bot client is used to edit the copied message and add the buttons to it (hence the need for a bot token).

If the buttons in the original message contain a login URL (or authorisation URL), then it's converted to a regular URL first and then included in the copied message. This is because login URLs have to be specifically configured for a bot as far as I'm aware, so if the bot tries to copy a message with a login URL that isn't configured for it, it throws an error.

# Handling floodwaits

The API method used when retrieving messages is messages.getHistory, and the method used when sending messages is messages.sendMessage for text messages or messages.sendMedia for media messages.

A userbot may receive a 420 FLOOD (floodwait) error if it makes a request with a particular method more than a particular number of times within some timeframe. The error includes a time the userbot is required to wait before it can successfully send another request with that method.

The script handles that by waiting the required time and then retrying the same process due to which it received a floodwait.

So in the above example, when the userbot receives the update of message 80, it retrieves all messages with ID >= the expected ID of the next message, that ID being the ID of message 1. So it retrieves messages 1 to 100 and starts copying them one by one to the destination chats, updating the recorded ID of the top message each time to be the ID of the message just copied. If it encounters a floodwait after copying message 50 and when attempting to copy message 51, then the recorded ID of the top message at this point is the ID of message 50. The userbot waits the required time, then repeats the process: it's still working with the same update which was that of message 80, which has an ID greater than the recorded ID of the top message +1 (i.e. the ID of message 50 +1, which is the ID of message 51), so it retrieves all messages with ID >= the recorded ID of the top message +1, i.e. message 51 to message 100, and then copies them one by one.

This is why the recorded ID of the top message is updated after each message sent, rather than just updating it at the end of the iterations to be the ID of message 100. In that case, the userbot starts copying messages 1 to 100, receives a floodwait after copying message 50 and when attempting to copy message 51, at which point the recorded ID of the top message is still that of whatever message was immediately before message 1. After it has waited the required time and repeats the process, it retrieves all messages with ID greater than recorded ID of the top message +1 (which hasn't changed), so it retrieves messages 1 to 100 again and starts copying from message 1 even though messages 1 to 50 were already copied.

# The caption added to messages

Not all messages accept a text component, but those that do include text messages (obviously), videos, photos, documents, and audio. The script adds a caption to whichever message can have a text component. The caption consists of the following components:

- For every message, the first line of the caption is 'chat\_ID: ' followed by the ID of the source chat from which the message has been copied
- The second line is 'message\_ID: ' followed by the ID of the message in the source channel. If the message in the source chat has been edited since it was first sent there, this is followed by ' (a\_previous\_message\_edited)'.
- The third line is 'date: ' followed by the date and time at which the message was sent in the source chat, except if the message has been edited since it was first sent, in which case it's the date and time at which the message was last edited instead of that at which it was first sent. The format of the date in both cases is 'YYYY-MM-DD hh:mm:ss UTC' with the time being given in UTC.
- If the source chat is a group, the next line is 'sender_ID: ' followed by the ID of the sender of the message in the group, which can either be a user/bot, a channel (if it's linked to the group or the message was sent by a user as a channel), or an anonymous group admin (in which case the ID is the group's ID).
- If the message is a reply to a previous message, the next line is 'in\_reply\_to\_message\_ID: ' followed by the ID of the message to which it was a reply.
- If the message in the source chat had been forwarded from somewhere else, such that it had a 'Forwarded from: ' tag, then:
  - If the message was forwarded from an anonymous group admin, the next line is 'forwarded\_from\_chat\_ID: {ID} (supergroup)' where {ID} is the ID of the group from which it was forwarded
  - If the message was forwarded from a channel, the next line is 'forwarded\_from\_chat\_ID: ' followed by the ID of that channel, and the line after that is 'forwarded\_from\_message\_ID: ' followed by the ID of the original message in that channel
  - If the message is forwarded from an individual user/bot, even if that original message was sent in a group rather than a private chat, then:
    - If it's a bot, or a user that allowed linking to their account in messages forwarded from them, the next line is 'forwarded\_from\_user\_ID: ' followed by the ID of the user/bot
    - Otherwise, if it's a user that didn't allow linking to their account in messages forwarded from them, the next line is 'forwarded\_from\_user\_name: ' followed by the name of the user, as it appears in the 'Forwarded from: ' tag
	
  The next line is then 'forwarded\_from\_message\_date: ' followed by the date and time at which the original message was sent in the chat from which it was forwarded to the source chat. The format of the date is likewise 'YYYY-MM-DD hh:mm:ss UTC' with the time being given in UTC.

	The issue of the attributes of the Message object of a forwarded message is still somewhat vague, so if none of the attributes exist which are used to determine which of the above cases applies, the message is copied without this part of the caption, and a message is printed to the terminal which should provide relevant details to look into it if you wish.

If the message already has text, then two line breaks are inserted at the end, followed by the above caption. If the message doesn't already have text (e.g. a document with no caption), then the caption is inserted without being preceded by two line breaks.

This applies if the text a message already contains wouldn't exceed the limit if the caption was added to it. The limit is 4096 characters for text messages and 1024 characters for the caption of media messages. If it would exceed the limit, the message is instead copied without a caption added to it, and the caption is sent in a new message in reply to the copied message immediately afterwards.