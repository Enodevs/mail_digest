from agent.auth import get_google_credentials

creds = get_google_credentials()
print(f"Valid: {creds.valid}")

# from agent.tools import get_emails, read_email, search_emails

# # # print(search_emails("is:unread"))
# # email = read_email("19f5c7586794e360")
# # print(email["subject"])
# # print(email["body"])

# emails = get_emails("is:unread", 3)

# for email in emails:
#     print("=" * 50)
#     print(email["from"])
#     print(email["subject"])
#     print(email["body"][:500])
#
