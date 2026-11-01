from agent.auth import get_google_credentials

creds = get_google_credentials()

print(f"It is {creds != None} that there are credentials")
