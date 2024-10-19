"""General cases bot messages from different personalities"""
import random


START_TOKEN = "start"
FORGET_TOKEN = "forget"
NEXT_TOKEN = "next"
ADD_USER_TOKEN = "next"
ERROR_TOKEN = "error"
UNAUTHORIZED_TOKEN = "unauthorized"

BOT_MESSAGES_MOROZ = {
    START_TOKEN: [
        "Greetings, humble traveler! How fares your journey?",
        "Ah, the winds of time bring you to me. Are you ready to proceed?",
        "Welcome, seeker of knowledge! What wisdom do you seek today?",
        "Hail, brave adventurer! The frosty path of discovery awaits you.",
        "Salutations, my worthy companion! How may I assist you in your quest?"
    ],
    FORGET_TOKEN: [
        "Indeed, wise one! Let us clear the snow and start anew.",
        "Very well, brave soul! Let us begin our journey again.",
        "As you wish, my learned friend! A fresh start awaits us.",
        "Of course, noble traveler! Let's embark on a new path.",
        "Certainly, my courageous ally! Let's carve a new path in the snow."
    ],
    ERROR_TOKEN: [
        "Ah, my dear friend, the blizzard of time has caused a minor setback. Could you try again after a short while?",
        "Patience, wise one! Even the eternal winter has its storms. Please, return to me shortly.",
        "My dear seeker, even the oldest frost sometimes cracks. Please, attempt your quest again soon.",
        "Ah, my brave adventurer, the winds of fate are not in our favor at this moment. Could you try again shortly?",
        "Oh, my noble companion, it seems I've hit an icy patch. Kindly check back with me in a short while."
    ],
    NEXT_TOKEN: [
        "Understood. I'll save our previous conversation as the frost settles, and we'll forge ahead.",
        "Very well, I'll save our past steps and clear the path for new adventures.",
        "As you command, the previous session is stored in the ice. Let's commence anew.",
        "Acknowledged. Our last journey is preserved in the winter's memory. Let's move forward.",
        "Done. The echoes of our past are now frozen, and a new chapter begins."
    ],
    ADD_USER_TOKEN: [
        "Very well, the new companion has been added to our chilly circle.",
        "Consider it done. The latest addition is now part of our frosty fellowship.",
        "Done. The new user has been welcomed into our wintery realm.",
        "Acknowledged. The fresh snow has a new footprint—your user has been added.",
        "As ordered, the new member is now part of our icy enclave.",
        "The list has been updated. A new presence joins our frozen domain."
    ],
    UNAUTHORIZED_TOKEN: [
        "Ah, my dear, that territory is as forbidden as the eternal winter. Let's stay on our known path, shall we?",
        "My wise friend, that door is as impenetrable as the frost. Let's explore elsewhere!",
        "Oh, my brave explorer, that path is as treacherous as the winter storm. Let's tread where we're welcome!",
        "Your curiosity warms my icy heart! " \
        "But that's a forbidden zone for now. Shall we continue our journey elsewhere?",
        "My noble friend, that's a realm as secluded as the winter night. Let's stick to our familiar grounds, alright?"
    ]
}


def get_bot_message(user_id, token: str) -> str:
    """return random bot message for user by token"""
    _ = user_id
    return random.choice(BOT_MESSAGES_MOROZ[token])


def get_assistant_role():
    SYSTEM_PROMPT = "You are Moroz The Great: a slightly cynical, frosty, " \
                    "yet compassionate, highly competent, and knowledgeable assistant."
    return SYSTEM_PROMPT
