# Ported from
# https://github.com/ConnorSwis/casino-bot

import os, asyncio, bisect
import requests
import emoji
from secrets import token_hex
from swibots import (
    BotApp,
    BotContext,
    CommandEvent,
    MessageEvent,
    CallbackQueryEvent,
    BotCommand,
    EmbeddedMedia,
    EmbedInlineField,
    Message,
    regexp,
    InlineMarkup,
    InlineKeyboardButton,
    BotCommand,
)
from PIL import Image
import numpy as np
from random import randint
from decouple import config

import random, asyncio
from typing import List, Tuple


import logging

logging.basicConfig(level=logging.INFO)

app = BotApp(config("BOT_TOKEN", default=""))
app.set_bot_commands(
    [
        BotCommand("blackjack", "Start blackjack", True),
        BotCommand("slot", "Run Slot machine", True),
        BotCommand("play2048", "start 2048", True),
        BotCommand("flip", "Flip a coin", True),
        BotCommand("roll", "Roll a dice", True),
    ]
)

DEFAULT_BET = 4

GLOBAL = {}


class Card:
    suits = ["clubs", "diamonds", "hearts", "spades"]

    def __init__(self, suit: str, value: int, down=False):
        self.suit = suit
        self.value = value
        self.down = down
        self.symbol = self.name[0].upper()

    @property
    def name(self) -> str:
        """The name of the card value."""
        if self.value <= 10:
            return str(self.value)
        else:
            return {
                11: "jack",
                12: "queen",
                13: "king",
                14: "ace",
            }[self.value]

    @property
    def image(self):
        return (
            f"{self.symbol if self.name != '10' else '10'}"
            f"{self.suit[0].upper()}.png"
            if not self.down
            else "red_back.png"
        )

    def flip(self):
        self.down = not self.down
        return self

    def __str__(self) -> str:
        return f"{self.name.title()} of {self.suit.title()}"

    def __repr__(self) -> str:
        return str(self)


def calc_hand(hand: List[List[Card]]) -> int:
    """Calculates the sum of the card values and accounts for aces"""
    non_aces = [c for c in hand if c.symbol != "A"]
    aces = [c for c in hand if c.symbol == "A"]
    sum = 0
    for card in non_aces:
        if not card.down:
            if card.symbol in "JQK":
                sum += 10
            else:
                sum += card.value
    for card in aces:
        if not card.down:
            if sum <= 10:
                sum += 11
            else:
                sum += 1
    return sum


def center(*hands: Tuple[Image.Image]) -> Image.Image:
    """Creates blackjack table with cards placed"""
    bg: Image.Image = Image.open(
        # os.path.join(ABS_PATH, 'modules/', 'table.png')
        "table.png"
    )
    bg_center_x = bg.size[0] // 2
    bg_center_y = bg.size[1] // 2

    img_w = hands[0][0].size[0]
    img_h = hands[0][0].size[1]

    start_y = bg_center_y - (((len(hands) * img_h) + ((len(hands) - 1) * 15)) // 2)
    for hand in hands:
        start_x = bg_center_x - (((len(hand) * img_w) + ((len(hand) - 1) * 10)) // 2)
        for card in hand:
            bg.alpha_composite(card, (start_x, start_y))
            start_x += img_w + 10
        start_y += img_h + 15
    return bg


def hand_to_images(hand: List[Card]) -> List[Image.Image]:
    return [Image.open(os.path.join("cards/", card.image)) for card in hand]


@app.on_command("blackjack")
async def blackjack(ctx: BotContext[CommandEvent]):
    #        self.check_bet(ctx, bet)
    bet = 1
    deck = [Card(suit, num) for num in range(2, 15) for suit in Card.suits]
    random.shuffle(deck)  # Generate deck and shuffle it

    player_hand: List[Card] = []
    dealer_hand: List[Card] = []

    player_hand.append(deck.pop())
    dealer_hand.append(deck.pop())
    player_hand.append(deck.pop())
    dealer_hand.append(deck.pop().flip())

    player_score = calc_hand(player_hand)
    dealer_score = calc_hand(dealer_hand)

    def output(name, *hands: Tuple[List[Card]]) -> None:
        center(*map(hand_to_images, hands)).save(f"{name}.png")

    async def out_table(msg, inline_markup=None, **kwargs) -> Message:
        """Sends a picture of the current table"""
        output(ctx.event.user.id, dealer_hand, player_hand)
        embed = EmbeddedMedia(
            f"{ctx.event.message.user_id}.png",
            **kwargs,
        )
        if msg:
            return await msg.edit_text("Blackjack", embed_message=embed, inline_markup=inline_markup)
        return await ctx.event.message.send("BlackJack", embed_message=embed, inline_markup=inline_markup)
 
    standing = False
    event = ctx.event.message
    msg = None
    while True:
        player_score = calc_hand(player_hand)
        dealer_score = calc_hand(dealer_hand)
        if player_score == 21:  # win condition
            bet = int(bet * 1.5)
            result = ("Blackjack!", "won")
            break
        elif player_score > 21:  # losing condition
            result = ("Player busts", "lost")
            break
        msg_id = ctx.event.message.id
        msg = await out_table(
            msg,
            title="Your Turn",
            description=f"Your hand: {player_score}\n" f"Dealer's hand: {dealer_score}",
            inline_fields=[[EmbedInlineField("", "", "Output")]],
            header_name="Blackjack",
            header_icon="https://img.icons8.com/?size=512&id=BdrGOzAgTJx3&format=png",
            footer_icon="https://img.icons8.com/?size=512&id=BdrGOzAgTJx3&format=png",
            footer_title="Continue playing..",
            inline_markup=InlineMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "H", callback_data=f"blkj_H_{msg_id}_{ctx.event.user_id}"
                        ),
                        InlineKeyboardButton(
                            "S", callback_data=f"blkj_S_{msg_id}_{ctx.event.user_id}"
                        ),
                    ]
                ]
            ),
        )
        if not GLOBAL.get(event.user_id):
            GLOBAL[event.user_id] = {}
        GLOBAL[event.user_id][msg_id] = None

        async def getClick():
            while not GLOBAL.get(event.user_id, {}).get(msg_id):
                await asyncio.sleep(0.05)

        try:
            task = asyncio.create_task(getClick())
            await asyncio.wait_for(task, timeout=60 * 3)
        except asyncio.TimeoutError:
            try:
                del GLOBAL[event.user_id][msg_id]
            except KeyError:
                pass
            await msg.delete()
            return
        option = GLOBAL[event.user_id][msg_id]
        if option == "H":
            player_hand.append(deck.pop())
            continue
        elif option == "S":
            standing = True
            try:
                del GLOBAL[event.user_id][msg_id]
            except KeyError:
                pass
            break

    if standing:
        dealer_hand[1].flip()
        player_score = calc_hand(player_hand)
        dealer_score = calc_hand(dealer_hand)

        while dealer_score < 17:  # dealer draws until 17 or greater
            dealer_hand.append(deck.pop())
            dealer_score = calc_hand(dealer_hand)

        if dealer_score == 21:  # winning/losing conditions
            result = ("Dealer blackjack", "lost")
        elif dealer_score > 21:
            result = ("Dealer busts", "won")
        elif dealer_score == player_score:
            result = ("Tie!", "kept")
        elif dealer_score > player_score:
            result = ("You lose!", "lost")
        elif dealer_score < player_score:
            result = ("You win!", "won")
    try:
        del GLOBAL[event.user_id][ctx.event.message_id]
    except KeyError:
        pass
    msg = await out_table(
        msg,
        title=result[0],
        description=(
            f"**You {result[1]} ${bet}**\nYour hand: {player_score}\n"
            + f"Dealer's hand: {dealer_score}"
        ),
        header_name="Blackjack",
        header_icon="https://img.icons8.com/?size=512&id=BdrGOzAgTJx3&format=png",
        footer_icon="https://img.icons8.com/?size=512&id=BdrGOzAgTJx3&format=png",
        footer_title="Play again!",
        inline_fields=[[EmbedInlineField("", "", "Output")]],
    )
    os.remove(f"./{ctx.event.user_id}.png")


@app.on_callback_query(regexp(r"blkj_(.*)"))
async def oncall(e: BotContext[CallbackQueryEvent]):
    query = e.event.callback_data
    userAction = int(e.event.action_by_id)
    input = query.split("_")
    option = input[1]
    msgId = int(input[2])
    userId = int(input[3])
    if not GLOBAL.get(userAction) or userId != userAction:
        return
    GLOBAL[userAction][msgId] = option


@app.on_command("slot")
async def slots(ctx: BotContext[CommandEvent]):
    bet = 1
    path = "slots/"
    facade = Image.open(f"{path}slot-face.png").convert("RGBA")
    reel = Image.open(f"{path}slot-reel.png").convert("RGBA")

    rw, rh = reel.size
    item = 180
    items = rh // item

    s1 = random.randint(1, items - 1)
    s2 = random.randint(1, items - 1)
    s3 = random.randint(1, items - 1)

    win_rate = 12 / 100

    if random.random() < win_rate:
        symbols_weights = [3.5, 7, 15, 25, 55]  #
        x = round(random.random() * 100, 1)
        pos = bisect.bisect(symbols_weights, x)
        s1 = pos + (random.randint(1, (items / 6) - 1) * 6)
        s2 = pos + (random.randint(1, (items / 6) - 1) * 6)
        s3 = pos + (random.randint(1, (items / 6) - 1) * 6)
        # ensure no reel hits the last symbol
        s1 = s1 - 6 if s1 == items else s1
        s2 = s2 - 6 if s2 == items else s2
        s3 = s3 - 6 if s3 == items else s3

    images = []
    speed = 6
    for i in range(1, (item // speed) + 1):
        bg = Image.new("RGBA", facade.size, color=(255, 255, 255))
        bg.paste(reel, (25 + rw * 0, 100 - (speed * i * s1)))
        bg.paste(
            reel, (25 + rw * 1, 100 - (speed * i * s2))
        )  # dont ask me why this works, but it took me hours
        bg.paste(reel, (25 + rw * 2, 100 - (speed * i * s3)))
        bg.alpha_composite(facade)
        images.append(bg)

    fp = str(id(ctx.event.user_id)) + ".gif"
    images[0].save(
        fp,
        save_all=True,
        append_images=images[1:],
        duration=50,
    )

    result = ("lost", bet)
    if (1 + s1) % 6 == (1 + s2) % 6 == (1 + s3) % 6:
        symbol = (1 + s1) % 6
        reward = [4, 80, 40, 25, 10, 5][symbol] * bet
        result = ("won", reward)

    embed = EmbeddedMedia(
        thumbnail=fp,
        title=(
            f"You {result[0]} {result[1]} credits"
            + ("." if result[0] == "lost" else "!")
        ),
        inline_fields=[[EmbedInlineField("", " ", "Output")]],
        header_name="Slot Game",
        header_icon="https://img.icons8.com/?size=512&id=75kpjKJhIQUK&format=png",
        footer_icon="https://img.icons8.com/?size=512&id=75kpjKJhIQUK&format=png",
        description="Play games to earn more credits.",
        footer_title="Better luck next time!"
        if result[0] == "lost"
        else "Play again to earn MORE!",
    )
    await ctx.event.message.send("Slots", embed_message=embed)

    os.remove(fp)


@app.on_command("flip")
async def flip(ctx: BotContext[CommandEvent]):
    param = ctx.event.params or ""
    if param.lower() not in ["h", "t"]:
        await ctx.event.message.reply_text(
            "You this command as\n/flip h: to bet on head\n/flip t: to bet on tail"
        )
        return
    choices = {"h": True, "t": False}
    choice = param.lower()
    if choice in choices.keys():
        if random.choice(list(choices.keys())) == choice:
            return await ctx.event.message.reply_text("Correct!\nYou own...")
        await ctx.event.message.reply_text("Wrong!\nBetter Luck Next time..")


@app.on_command("roll")
async def roll(
    ctx: BotContext[CommandEvent],
):
    param = ctx.event.params
    if not param:
        await ctx.event.message.reply_text("Provide a dice output to make a bet!")
        return
    try:
        choice = param = int(param)
        assert param in list(range(1, 7))
    except Exception:
        await ctx.event.message.reply_text("Provide a value between 1-6")
        return
    choices = range(1, 7)
    if choice in choices:
        if random.choice(choices) == choice:
            return await ctx.event.message.reply_text("Correct!\nYou won...")
        await ctx.event.message.reply_text("Wrong!\nBetter Luck Next time..")


numbers = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
]
DATA = {
    0: "0️⃣",
    1: "1️⃣",
    2: "2️⃣",
    3: "3️⃣",
    4: "4️⃣",
    5: "5️⃣",
    6: "6️⃣",
    7: "7️⃣",
    8: "8️⃣",
    9: "9️⃣",
}


def array_to_string(array_in, user):
    string = ""
    string2 = ""
    rows = array_in.shape[0]
    cols = array_in.shape[1]

    for x in range(0, rows):
        for y in range(0, cols):
            string += str(array_in[x][y]).replace(".0", "")
            for i in range(
                0,
                len(str(np.amax(array_in)).replace(".0", ""))
                - len(str(array_in[x][y]).replace(".0", "")),
            ):
                string2 += ":new_moon:"
            for char in str(array_in[x][y]).replace(".0", ""):
                if char == "0" and str(array_in[x][y]).replace(".0", "") == "0":
                    string2 += ":new_moon:"
                else:
                    string2 += f"{DATA[int(char)]}"
            if y != 3:
                string += ","
                if len(str(np.amax(array_in)).replace(".0", "")) > 1:
                    string2 += "   "
                else:
                    string2 += "   "
        if x != 3:
            string += "|"
            string2 += "\n"
            for i in range(0, len(str(np.amax(array_in)).replace(".0", ""))):
                string2 += "\n"
    string += "[]%s" % user
    return string, emoji.emojize(string2)


def string_to_array(string):
    output = np.zeros((4, 4))
    x_num = 0
    y_num = 0
    for x in string.split("[]")[0].split("|"):
        for y in x.split(","):
            output[x_num][y_num] = y
            y_num += 1
        y_num = 0
        x_num += 1
    user = string.split("[]")[1]
    return output, user


async def delete_game(reaction):
    await reaction.message.edit(content="*Game removed*", embed=None)


def check_valid(output2):
    rows = output2.shape[0]
    cols = output2.shape[1]
    found = False
    original = output2

    for j in range(0, 4):
        output2 = np.zeros(shape=(4, 4))
        output = original
        output = np.rot90(output, j)
        for i in range(0, 3):
            output2 = np.zeros(shape=(4, 4))
            for x in range(0, cols):
                for y in range(0, rows):
                    if y != 0:
                        if output[x][y - 1] == 0:
                            output2[x][y - 1] = output[x][y]
                        else:
                            output2[x][y] = output[x][y]
                    else:
                        output2[x][y] = output[x][y]
            output = output2

        # Combine adjacent equal tiles
        output3 = np.zeros(shape=(4, 4))
        for x in range(0, cols):
            for y in range(0, rows):
                if y != 0:
                    if output2[x][y - 1] == output2[x][y]:
                        output3[x][y - 1] = output2[x][y] * 2
                    else:
                        output3[x][y] = output2[x][y]
                else:
                    output3[x][y] = output2[x][y]

        output = output3

        # Move over two more times
        for i in range(0, 1):
            output3 = np.zeros(shape=(4, 4))
            for x in range(0, cols):
                for y in range(0, rows):
                    if y != 0:
                        if output[x][y - 1] == 0:
                            output3[x][y - 1] = output[x][y]
                        else:
                            output3[x][y] = output[x][y]
                    else:
                        output3[x][y] = output[x][y]
            output = output3

        output2 = output3
        output2 = np.rot90(output2, 4 - j)

        if np.array_equal(original, output2) is False:
            found = True

    if found is True:
        return True
    return False


E2048mbed = [
    EmbedInlineField("https://img.icons8.com/?size=512&id=35315&format=png"),
    EmbedInlineField("https://img.icons8.com/?size=1x&id=35313&format=png"),
    EmbedInlineField("https://img.icons8.com/?size=1x&id=35320&format=png"),
    EmbedInlineField("https://img.icons8.com/?size=1x&id=35328&format=png"),
]


@app.on_command("play2048")
async def on_message(ctx: BotContext[CommandEvent]):
    message = ctx.event.message
    # Generate Random Game Board
    start_array = np.zeros(shape=(4, 4))

    first = randint(0, 3)
    second = randint(0, 3)
    start_array[first][second] = randint(1, 2) * 2

    found = False
    while found is not True:
        first_2 = randint(0, 3)
        second_2 = randint(0, 3)
        if first_2 == first and second_2 == second:
            None
        else:
            found = True
            start_array[first_2][second_2] = randint(1, 2) * 2

    string, string2 = array_to_string(start_array, message.user.username)

    media = EmbeddedMedia(
        thumbnail=None,
        title=f"{message.user.name}'s Game!",
        header_name="Play 2048",
        description="It's not easy as it looks!",
        header_icon="https://img.icons8.com/?size=512&id=42174&format=png",
        inline_fields=[
            [EmbedInlineField("", string2, "Try to get the 2048 tile!")],
        ],
        footer_icon="",
        footer_title=string,
    )
    new_msg = await message.send(
        "2048",
        embed_message=media,
        inline_markup=get2048Markup(message.user_id),
    )


def get2048Markup(user_id):
    return InlineMarkup(
        [
            [
                InlineKeyboardButton("⬆", callback_data=f"mvup_{user_id}"),
                InlineKeyboardButton("⬅", callback_data=f"mvlf_{user_id}"),
                InlineKeyboardButton("➡", callback_data=f"mvrt_{user_id}"),
                InlineKeyboardButton("⬇", callback_data=f"mvdn_{user_id}"),
            ]
        ]
    )


@app.on_callback_query(regexp(r"mv(.*)"))
async def on_2048(ctx: BotContext[CallbackQueryEvent]):
    message = ctx.event.message
    # Stop the bot from going when it adds its own reactions
    callback = ctx.event.callback_data[2:].split("_")
    try:
        reaction = {"up": "⬆", "dn": "⬇", "rt": "➡", "lf": "⬅"}[callback[0]]
    except KeyError:
        reaction = "x"
    user_id = int(callback[1])
    embedded = message.embed_message
    user = ctx.event.action_by.name
    # If the message that was reacted on was one sent by the bot, guaranteeing it's a game
    if (
        int(ctx.event.action_by_id) == user_id
    ):  # reaction.message.author == dbot.user: # TODO:
        # Game is over and anyone can delete the game board and reactions by reacting the X emoji
        if reaction == "🇽" and embedded.footer_title == "Game over!":
            await delete_game(reaction)
        else:
            # decode footer from base91
            footer = embedded.footer_title
            try:
                output, user2 = string_to_array(footer)
            except ValueError:
                return
            # if the user is the same one that started the game
            if user2 == ctx.event.action_by.username:
                original = output

                rows = output.shape[0]
                cols = output.shape[1]
                output2 = np.zeros(shape=(4, 4))

                if reaction == "🇽":
                    # Game is still going and original user can decide to delete game
                    await delete_game(reaction)
                    return
                # Rotate arrays to all be facing to the left to make actions on them easier
                elif reaction == "⬅":
                    output = np.rot90(output, 0)
                elif reaction == "➡":
                    output = np.rot90(output, 2)
                elif reaction == "⬆":
                    output = np.rot90(output, 1)
                elif reaction == "⬇":
                    output = np.rot90(output, 3)
                else:
                    return

                # Move everything to the left 4 times to be sure to get everything
                for i in range(0, 3):
                    output2 = np.zeros(shape=(4, 4))
                    for x in range(0, cols):
                        for y in range(0, rows):
                            if y != 0:
                                if output[x][y - 1] == 0:
                                    output2[x][y - 1] = output[x][y]
                                else:
                                    output2[x][y] = output[x][y]
                            else:
                                output2[x][y] = output[x][y]
                    output = output2

                # Combine adjacent equal tiles
                output3 = np.zeros(shape=(4, 4))
                for x in range(0, cols):
                    for y in range(0, rows):
                        if y != 0:
                            if output2[x][y - 1] == output2[x][y]:
                                output3[x][y - 1] = output2[x][y] * 2
                                output2[x][y] = 0
                            else:
                                output3[x][y] = output2[x][y]
                        else:
                            output3[x][y] = output2[x][y]

                output = output3

                # Move over two more times and check if the board has a 2048 in it or if it's completely full
                found_win = False
                found_end = True
                for i in range(0, 1):
                    output3 = np.zeros(shape=(4, 4))
                    for x in range(0, cols):
                        for y in range(0, rows):
                            if y != 0:
                                if output[x][y - 1] == 0:
                                    output3[x][y - 1] = output[x][y]
                                else:
                                    output3[x][y] = output[x][y]
                            else:
                                output3[x][y] = output[x][y]
                            if output3[x][y] == 2048:
                                found_win = True
                            if output3[x][y] == 0:
                                found_end = False
                    output = output3

                output2 = output3

                # Undo the rotations from before
                if reaction == "⬅":
                    output2 = np.rot90(output2, 0)
                if reaction == "➡":
                    output2 = np.rot90(output2, 2)
                if reaction == "⬆":
                    output2 = np.rot90(output2, 3)
                if reaction == "⬇":
                    output2 = np.rot90(output2, 1)

                # If there's a 2048 on the board, the player won! Add the win gif
                if found_win is True:
                    e = EmbeddedMedia(
                        thumbnail="game_over.jpg",
                        title="Play 2048",
                        header_name="2048 🎉",
                        header_icon="https://img.icons8.com/?size=512&id=42174&format=png",
                        description="Congrats, you are the lucky wizard!",
                        inline_fields=[
                            [
                                EmbedInlineField(
                                    "", "%s got the 2048 tile!" % user, "You did it!!"
                                )
                            ]
                        ],
                        footer_title="Game Over!",
                    )
                    #                    msg = ctx.event.message._prepare_response()
                    await message.edit_text("2048", embed_message=e)
                # If the array changed from how it was before and if there are any empty spaces on the board, add a random tile
                elif np.array_equal(output2, original) is False and found_end is False:
                    found = False
                    while found is not True:
                        first_2 = randint(0, 3)
                        second_2 = randint(0, 3)
                        if output2[first_2][second_2] == 0:
                            found = True
                            output2[first_2][second_2] = randint(1, 2) * 2

                    string, string2 = array_to_string(
                        output2, ctx.event.action_by.username
                    )

                    #                    print(string)
                    e = EmbeddedMedia(
                        thumbnail=None,
                        inline_fields=[
                            [EmbedInlineField("", string2, "Try to get 2048 tile!")]
                        ],
                        title="Play 2048",
                        header_icon="https://img.icons8.com/?size=512&id=42174&format=png",
                        header_name="Keep playing...",
                        description=f"{user}'s Game",
                        footer_title=string,
                    )
                    await message.edit_text(
                        "2048",
                        embed_message=e,
                        inline_markup=get2048Markup(user_id),
                    )

                    # Check if there are valid moves and if not, end the game
                    if check_valid(output2) is False:
                        # If there are no 0's, check if there are any valid moves. If there aren't, say the game is over.
                        e = EmbeddedMedia(
                            thumbnail="game_over.jpg",
                            footer_title="Play again!",
                            title="Game Over!",
                            header_name="Play 2048",
                            description=f"{user}'s Game",
                            header_icon="https://img.icons8.com/?size=512&id=CLhD2jKvHsDB&format=png",
                            inline_fields=[
                                [
                                    EmbedInlineField(
                                        "",
                                        "%s is unable to make any more moves." % user,
                                        "🥲",
                                    )
                                ]
                            ],
                        )
                        #                        msg = ctx.event.message._prepare_response()
                        await message.edit_text("Game Over", embed_message=e)

                elif check_valid(output2) is False:
                    e = EmbeddedMedia(
                        thumbnail="game_over.jpg",
                        header_icon="https://img.icons8.com/?size=512&id=42174&format=png",
                        inline_fields=[
                            [
                                EmbedInlineField(
                                    "",
                                    "%s is unable to make any more moves." % user,
                                    "🥹",
                                )
                            ]
                        ],
                        header_name="Game Over!",
                        title="Play 2048",
                        description=f"{user}'s Game",
                        footer_title="Try again!",
                    )
                    await message.edit_text("Game over", embed_message=e)
                else:
                    # They made a valid move, but it didn't change anything, so don't add a new tile
                    string, string2 = array_to_string(
                        output2, ctx.event.action_by.username
                    )

                    e = EmbeddedMedia(
                        thumbnail=None,
                        header_name="Play 2048",
                        header_icon="https://img.icons8.com/?size=512&id=42174&format=png",
                        title=f"{user}'s Game!",
                        inline_fields=[[EmbedInlineField("", string2, "")]],
                        footer_title=string,
                        description="Try to get the 2048 tile!",
                    )
                    await message.edit_text(
                        "2048",
                        embed_message=e,
                        inline_markup=get2048Markup(user_id),
                    )


app.run()
