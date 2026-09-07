from agent.database import get_recent_messages


def get_conversation_context():
    messages = get_recent_messages(10)
    # messages is already a list of Message namedtuples
    return messages
